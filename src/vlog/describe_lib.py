"""
Core library for video description using MLX-VLM.

This module contains the business logic for analyzing videos with vision language models.
It can be used by both CLI scripts and daemon services.
"""
import os
import json
from typing import Any, Sequence, Tuple, cast
from jinja2 import Template
from pydantic import BaseModel, ValidationError
from mlx_vlm import load
from mlx_vlm.video_generate import generate
from mlx_vlm.utils import load_config
from mlx_vlm.video_generate import process_vision_info
import mlx.core as mx


# Locate prompts directory relative to this file
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_PROMPT_PATH = os.path.join(ROOT_DIR, 'prompts', 'describe_v1.md')
DEFAULT_PROMPT_META = os.path.join(ROOT_DIR, 'prompts', 'describe_v1.yaml')


class Segment(BaseModel):
    """Represents a video segment with in and out timestamps."""
    in_timestamp: str
    out_timestamp: str


class DescribeOutput(BaseModel):
    """Structured output from the video description model."""
    description: str
    short_name: str
    primary_shot_type: str
    tags: list[str]
    thumbnail_frame: int
    rating: float
    camera_movement: str
    in_timestamp: str
    out_timestamp: str
    segments: list[Segment] | None = None


def load_prompt_template(path: str) -> str:
    """Return the prompt template text from `path`.

    Falls back to the embedded default in case the file is missing.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # best-effort fallback
        return "Describe this video."


def render_prompt(template_text: str, subtitle: str | None) -> str:
    """Render the prompt template with optional subtitle."""
    tpl = Template(template_text)
    rendered = tpl.render(subtitle=subtitle or "")
    # If the template did not include the subtitle placeholder, append it
    if subtitle and subtitle not in rendered:
        rendered = rendered + f"\n\n# Transcript for this video:\n\n{subtitle}\n"
    return rendered


def load_subtitle_file(path: str) -> str | None:
    """Load subtitle file if it exists."""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def validate_model_output(parsed: Any) -> dict:
    """Validate parsed JSON from the model against DescribeOutput.

    Returns the dictified model if valid, otherwise raises ValidationError.
    """
    # Use Pydantic v2 API (model_validate + model_dump) for forward compatibility
    obj = DescribeOutput.model_validate(parsed)
    return obj.model_dump()


def describe_video(
    model,
    processor,
    config,
    video_path: str,
    prompt: str | None = None,
    fps: float = 1.0,
    subtitle: str | None = None,
    max_pixels: int = 224 * 224,
    **generate_kwargs
) -> dict:
    """
    Describe a single video using mlx-vlm.

    Args:
        model: The loaded MLX-VLM model
        processor: The loaded processor
        config: The model configuration
        video_path: Path to the video file
        prompt: Optional prompt template. If None, uses default template.
        fps: Frames per second to sample from video
        subtitle: Optional subtitle text to include in the prompt
        max_pixels: Maximum pixel size for frames
        **generate_kwargs: Additional arguments passed to generate()

    Returns:
        dict: Validated description output as dictionary

    Raises:
        Exception: If the model output cannot be parsed or validated
    """
    # Format prompt template text
    if prompt is None:
        # render default template
        prompt_template = load_prompt_template(DEFAULT_PROMPT_PATH)
        prompt = render_prompt(prompt_template, subtitle)

    # append subtitle to the prompt if provided (safe now that `prompt` is a string)
    if subtitle:
        prompt = (prompt or "") + f"\n\n# Transcript for this video:\n\n{subtitle}\n"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": video_path,
                    "fps": fps,
                    "max_pixels": max_pixels,
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    # Process vision info (videos etc) — convert to model-ready inputs
    # upstream type hints for `process_vision_info` are unreliable. Cast the
    # returned value to the types we actually expect so the editor/type-checker
    # understands the real shapes without changing runtime behaviour.
    _, video_inputs = cast(
        Tuple[Sequence[Any], Sequence[Any]], process_vision_info(messages)
    )

    inputs = processor(
        text=[text],
        images=None,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
        video_metadata={'fps': fps, 'total_num_frames': video_inputs[0].shape[0]}
    )

    input_ids = mx.array(inputs["input_ids"])
    mask = mx.array(inputs["attention_mask"])
    video_grid_thw = mx.array(inputs["video_grid_thw"])

    # include kwargs for video layout grid info
    extra = {"video_grid_thw": video_grid_thw}

    pixel_values = inputs.get(
        "pixel_values_videos", inputs.get("pixel_values", None)
    )
    if pixel_values is None:
        raise ValueError("Please provide a valid video or image input.")
    pixel_values = mx.array(pixel_values)

    response = generate(
        model=model,
        processor=processor,
        prompt=text,
        input_ids=input_ids,
        pixel_values=pixel_values,
        mask=mask,
        **extra,
        **generate_kwargs,
    )

    try:
        parsed = json.loads(response.text)
    except Exception:
        raise Exception(f'Could not deserialize {response.text}')

    # validate and return structured output
    try:
        validated = validate_model_output(parsed)
        return validated
    except ValidationError as e:
        # return raw parsed JSON but surface validation error in message
        raise Exception(f'Output did not match expected schema: {e}\nRaw: {parsed}')


def load_model(model_name: str):
    """Load the MLX-VLM model and processor.

    Args:
        model_name: Name or path of the model to load

    Returns:
        tuple: (model, processor, config)
    """
    model, processor = load(model_name)
    config = load_config(model_name)
    return model, processor, config


def calculate_adaptive_fps(video_length: float, base_fps: float) -> float:
    """Calculate adaptive FPS based on video length.

    Args:
        video_length: Length of video in seconds
        base_fps: Base frames per second

    Returns:
        float: Adjusted FPS for the video
    """
    fps = float(base_fps)
    if video_length > 120:
        fps = fps / 2.0
    if video_length > 300:
        fps = fps / 2.0
    return fps
