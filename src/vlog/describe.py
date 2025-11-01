import os
import json
import time
from vlog.db import check_if_file_exists, insert_result, initialize_db
from mlx_vlm import load
from mlx_vlm.video_generate import generate  # or the appropriate import
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
from mlx_vlm.video_generate import process_vision_info
import mlx.core as mx
from typing import Any, Sequence, Tuple, cast
from jinja2 import Template
from pydantic import BaseModel, ValidationError

# locate prompts directory relative to this file
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_PROMPT_PATH = os.path.join(ROOT_DIR, 'prompts', 'describe_v1.md')
DEFAULT_PROMPT_META = os.path.join(ROOT_DIR, 'prompts', 'describe_v1.yaml')
from vlog.video import get_video_length_and_timestamp, get_video_thumbnail

def describe_video(
    model, processor, config, video_path, prompt: str | None = None,
    fps=1.0, subtitle=None, max_pixels=224*224, **generate_kwargs):
    """
    Describe a single video using mlx-vlm.
    """
    # create message format (this is inferred from how video inference is done in mlx-vlm)
    # the `prompt` value (possibly rendered from a template) is attached below

    # format prompt template text
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

    # process vision info (videos etc) — convert to model-ready inputs
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

def load_subtitle_file(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


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
    tpl = Template(template_text)
    rendered = tpl.render(subtitle=subtitle or "")
    # If the template did not include the subtitle placeholder, append it
    if subtitle and subtitle not in rendered:
        rendered = rendered + f"\n\n# Transcript for this video:\n\n{subtitle}\n"
    return rendered


class Segment(BaseModel):
    in_timestamp: str
    out_timestamp: str


class DescribeOutput(BaseModel):
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


def validate_model_output(parsed: Any) -> dict:
    """Validate parsed JSON from the model against DescribeOutput.

    Returns the dictified model if valid, otherwise raises ValidationError.
    """
    # Use Pydantic v2 API (model_validate + model_dump) for forward compatibility
    obj = DescribeOutput.model_validate(parsed)
    return obj.model_dump()


def describe_videos_in_dir(directory, model_name, prompt="Describe this video", fps=1.0, **generate_kwargs):
    """
    Iterate through video files in `directory` and generate descriptions.
    Returns a dict mapping filename → description.
    """
    # load model & processor & config
    model, processor = load(model_name)
    config = load_config(model_name)

    results = {}
    for fname in sorted(os.listdir(directory)):
        if not fname.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            print('Skipping non-video file:', fname)
            continue
        f = check_if_file_exists(fname)
        if f:
            print('Already processed', f)
            continue
        full = os.path.join(directory, fname)
        if not os.path.isfile(full):
            continue

        subtitle_file = os.path.splitext(full)[0] + '.srt'
        subtitle_text = load_subtitle_file(subtitle_file)

        video_length, video_timestamp = get_video_length_and_timestamp(full)
        if video_length > 120:
            fps = fps / 2.0
        if video_length > 300:
            fps = fps / 2.0
        # filter by extension (e.g. .mp4, .mov, .avi). adjust as needed
        ext = os.path.splitext(fname)[1].lower()

        start_time = time.time()
        if ext not in (".mp4", ".mov", ".avi", ".mkv"):
            continue
        try:
            desc = describe_video(
                model, processor, config, full, prompt=prompt, 
                fps=fps, subtitle=subtitle_text, **generate_kwargs)
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        desc['timing_sec'] = time.time() - start_time
        print(fname, desc)
        results[fname] = desc
        thumbnail_frame = int(desc['thumbnail_frame'])
        thumbnail_base64 = get_video_thumbnail(full, thumbnail_frame, fps)
        insert_result(
            fname,
            desc['description'],
            desc['short_name'],
            desc.get('primary_shot_type'),
            desc.get('tags', []),
            time.time() - start_time,
            model_name,
            video_length,
            video_timestamp,
            thumbnail_base64,
            desc.get('in_timestamp'),
            desc.get('out_timestamp'),
            desc.get('rating', 0.0),
            desc.get('segments')
        )
    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Describe all videos in a directory.")
    parser.add_argument("directory", type=str, help="Path to the directory containing videos")
    # 8B is good enough, Thinking would be better but too slow.  30B would not run well in 24GB RAM.
    parser.add_argument("--model", type=str, default="mlx-community/Qwen3-VL-8B-Instruct-4bit",
                        help="The model path to use in mlx-vlm")
    parser.add_argument("--prompt", type=str, default=None,
                        help="Prompt to pass to the model for describing videos")
    parser.add_argument("--fps", type=float, default=1.0, help="Frames per second to sample from video")
    parser.add_argument("--max_pixels", type=int, default=224*224, help="Max pixel size for frames")
    parser.add_argument("--max_tokens", type=int, default=10000, help="Max generation tokens")
    args = parser.parse_args()
    initialize_db()

    descs = describe_videos_in_dir(
        args.directory,
        args.model,
        prompt=args.prompt,
        fps=args.fps,
        max_pixels=args.max_pixels,
        max_tokens=args.max_tokens,
        temperature=0.7,
    )
    for fname, desc in descs.items():
        print(f"--- {fname} ---")
        print(desc)
        print()
