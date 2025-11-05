"""
Video description module using MLX-VLM.

This module provides high-level functions for describing videos and storing
results in the database. It uses the describe_lib module for core functionality.
"""
import os
import time
from vlog.db import check_if_file_exists, insert_result, initialize_db
from vlog.describe_lib import (
    describe_video,
    load_model,
    load_subtitle_file,
    calculate_adaptive_fps,
    Segment,
    DescribeOutput,
    validate_model_output,
)
# Re-export prompt helpers and defaults from describe_lib for backwards compatibility
from vlog.describe_lib import (
    DEFAULT_PROMPT_PATH,
    load_prompt_template,
    render_prompt,
)
# Re-export helpers used by tests/other modules
from vlog.describe_lib import process_vision_info
from vlog.describe_lib import generate
from vlog.describe_lib import mx
from vlog.video import get_video_length_and_timestamp, save_video_thumbnail_to_file


def describe_and_insert_video(
    full: str,
    fname: str,
    model,
    processor,
    config,
    prompt: str | None,
    fps: float,
    model_name: str,
    **generate_kwargs,
) -> dict | None:
    """Describe a single video file and insert the result into the DB.

    This encapsulates the per-file logic previously in
    `describe_videos_in_dir` so it can be reused and exported.

    Returns the validated description dict on success, or None on error.
    """
    # Load subtitle if present
    subtitle_file = os.path.splitext(full)[0] + '.srt'
    subtitle_text = load_subtitle_file(subtitle_file)

    # Determine video length and timestamp
    video_length, video_timestamp = get_video_length_and_timestamp(full)

    # Calculate adaptive FPS
    local_fps = calculate_adaptive_fps(video_length, fps)

    # extension filter
    ext = os.path.splitext(fname)[1].lower()
    if ext not in (".mp4", ".mov", ".avi", ".mkv"):
        return None

    start_time = time.time()
    try:
        desc = describe_video(
            model,
            processor,
            config,
            full,
            prompt=prompt,
            fps=local_fps,
            subtitle=subtitle_text,
            **generate_kwargs,
        )
    except Exception as e:
        print(f"ERROR describing {fname}: {e}")
        return None

    timing = time.time() - start_time
    desc['timing_sec'] = timing

    try:
        thumbnail_frame = int(desc['thumbnail_frame'])
    except Exception:
        print(f"Invalid thumbnail_frame for {fname}: {desc.get('thumbnail_frame')}")
        return None

    # Save thumbnail as JPG file next to the video
    save_video_thumbnail_to_file(full, thumbnail_frame, local_fps)

    # Insert into DB (tags and segments already validated by pydantic)
    # video_thumbnail_base64 is deprecated - thumbnails are now saved as JPG files
    insert_result(
        fname,
        desc['description'],
        desc['short_name'],
        desc.get('primary_shot_type'),
        desc.get('tags', []),
        timing,
        model_name,
        video_length,
        video_timestamp,
        "",  # video_thumbnail_base64 is deprecated
        desc.get('in_timestamp'),
        desc.get('out_timestamp'),
        desc.get('rating', 0.0),
        desc.get('segments'),
    )

    return desc


def describe_videos_in_dir(directory, model_name, prompt="Describe this video", fps=1.0, **generate_kwargs):
    """
    Iterate through video files in `directory` and generate descriptions.
    Returns a dict mapping filename → description.
    """
    # load model & processor & config
    model, processor, config = load_model(model_name)

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

        desc = describe_and_insert_video(
            full=full,
            fname=fname,
            model=model,
            processor=processor,
            config=config,
            prompt=prompt,
            fps=fps,
            model_name=model_name,
            **generate_kwargs,
        )

        if desc is None:
            # error already printed inside helper
            continue

        print(fname, desc)
        results[fname] = desc

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

