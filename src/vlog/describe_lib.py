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


# Locate prompts directory relative to this file (now in the package)
PACKAGE_DIR = os.path.dirname(__file__)
DEFAULT_PROMPT_PATH = os.path.join(PACKAGE_DIR, 'prompts', 'describe_v1.md')
DEFAULT_PROMPT_META = os.path.join(PACKAGE_DIR, 'prompts', 'describe_v1.yaml')


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
    """Load subtitle file and convert to compact format if it exists.
    
    Converts SRT format to compact timestamp format:
    [HH:MM:SS] Transcript text.
    
    Args:
        path: Path to the subtitle file (SRT format)
        
    Returns:
        Compact formatted subtitle text or None if file doesn't exist
    """
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        return convert_srt_to_compact(srt_content)
    return None


def convert_srt_to_compact(srt_text: str) -> str:
    """Convert SRT format to compact timestamp format.
    
    Input (SRT format):
        1
        00:00:15,000 --> 00:00:23,000
        Now we look at the key components of the VLM architecture.
        
        2
        00:00:23,000 --> 00:00:30,000
        The Visual Encoder handles all the video frames.
    
    Output (compact format):
        [00:00:15] Now we look at the key components of the VLM architecture.
        [00:00:23] The Visual Encoder handles all the video frames.
    
    Args:
        srt_text: SRT formatted subtitle text
        
    Returns:
        Compact formatted subtitle text
    """
    lines = srt_text.strip().split('\n')
    compact_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
            
        # Skip sequence numbers (lines that are just digits)
        if line.isdigit():
            i += 1
            continue
        
        # Check if this is a timestamp line (contains -->)
        if '-->' in line:
            # Extract start timestamp (before -->)
            timestamp_part = line.split('-->')[0].strip()
            # Convert from 00:00:15,000 to [00:00:15]
            timestamp = timestamp_part.split(',')[0]
            
            # Collect all text lines until we hit an empty line or next sequence number
            text_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                # Stop at empty line or digit (next subtitle sequence)
                if not next_line or (next_line.isdigit() and i + 1 < len(lines) and '-->' in lines[i + 1]):
                    break
                text_lines.append(next_line)
                i += 1
            
            # Combine multiple text lines with space
            if text_lines:
                text = ' '.join(text_lines)
                compact_lines.append(f'[{timestamp}] {text}')
        else:
            i += 1
    
    return '\n'.join(compact_lines)


def validate_model_output(parsed: Any) -> dict:
    """Validate parsed JSON from the model against DescribeOutput.

    Returns the dictified model if valid, otherwise raises ValidationError.
    """
    # Use Pydantic v2 API (model_validate + model_dump) for forward compatibility
    obj = DescribeOutput.model_validate(parsed)
    return obj.model_dump()


def augment_model_output(validated: dict, fps: float) -> dict:
    """Return an augmented copy of the validated model output.

    Currently this synthesizes a `thumbnail_timestamp` field from
    `thumbnail_frame` and `fps`. The function returns a shallow copy of
    the input dict with the added field. If timestamp generation fails
    the field will be set to None.
    """
    out = dict(validated)
    try:
        tf = out.get('thumbnail_frame')
        if tf is not None:
            out['thumbnail_timestamp'] = frame_to_timestamp(int(tf), fps)
        else:
            out['thumbnail_timestamp'] = None
    except Exception:
        out['thumbnail_timestamp'] = None

    return out


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

    _, video_inputs = cast(Tuple[Sequence[Any], Sequence[Any]], process_vision_info(messages))

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
        return augment_model_output(validated, fps)
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


def frame_to_timestamp(frame: int, fps: float) -> str:
    """Convert a frame index and fps into an HH:MM:SS.sss timestamp string.

    Args:
        frame: Frame index (integer, zero-based assumed).
        fps: Frames per second used to sample the video. Must be > 0.

    Returns:
        A string formatted as HH:MM:SS.sss (hours, minutes, seconds with
        millisecond precision).
    """
    # Guard against division by zero
    try:
        fps_val = float(fps) if fps else 0.0
    except Exception:
        fps_val = 0.0

    total_seconds = 0.0
    if fps_val > 0:
        total_seconds = float(frame) / fps_val

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    # Format seconds with 3 decimal places (milliseconds)
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
