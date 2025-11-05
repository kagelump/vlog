#!/usr/bin/env python3
"""
Video description to JSON output.

This script runs the video description process and outputs the results
to a JSON file instead of inserting into the database.
"""

import os
import sys
import json
import time
from pathlib import Path

# Add src to path so we can import vlog modules
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "src"))

from vlog.describe_lib import (
    describe_video,
    load_model,
    load_subtitle_file,
    calculate_adaptive_fps,
    validate_model_output,
)
from vlog.video import get_video_length_and_timestamp, save_video_thumbnail_to_file


def describe_to_json(
    video_file: str,
    subtitle_file: str,
    output_json: str,
    model_name: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit",
    fps: float = 1.0,
    # `max_pixels` may be provided as either a side length (e.g. 224) or
    # as a total pixel budget (e.g. 224*224). The downstream mlx_vlm
    # implementation expects a pixel budget; if callers pass a small
    # integer like 224 we treat that as the side length and square it.
    max_pixels: int = 224,
    prompt: str | None = None
) -> bool:
    """
    Describe a video and save results to JSON file.
    
    Args:
        video_file: Path to the video file
        subtitle_file: Path to the cleaned subtitle file
        output_json: Path where JSON output should be saved
        model_name: Name of the model to use
        fps: Frames per second to sample (will be adaptive)
        max_pixels: Maximum pixels for image processing
        prompt: Optional custom prompt
    
    Returns:
        True if successful, False otherwise
    """
    video_path = Path(video_file)
    subtitle_path = Path(subtitle_file)
    output_path = Path(output_json)
    
    # Validate input files exist
    if not video_path.exists():
        print(f"Error: Video file does not exist: {video_file}", file=sys.stderr)
        return False
    
    if not subtitle_path.exists():
        print(f"Warning: Subtitle file does not exist: {subtitle_file}", file=sys.stderr)
        subtitle_text = None
    else:
        subtitle_text = load_subtitle_file(str(subtitle_path))
    
    try:
        print(f"Loading model: {model_name}")
        start_time = time.time()
        
        # Load the model
        model, processor, config = load_model(model_name)
        
        # Get video metadata
        video_length, video_timestamp = get_video_length_and_timestamp(str(video_path))
        
        # Calculate adaptive FPS
        local_fps = calculate_adaptive_fps(video_length, fps)
        print(f"Using adaptive FPS: {local_fps} for video length: {video_length}s")
        
        # Describe the video
        print(f"Describing video: {video_file}")
        # Convert small max_pixels (commonly provided as a side length)
        # to a pixel budget expected by mlx_vlm. If the user passed a
        # reasonably large value we assume it's already a pixel budget.
        mp = int(max_pixels)
        if mp > 0 and mp < 1000:
            mp = mp * mp

        description = describe_video(
            video_path=str(video_path),
            model=model,
            processor=processor,
            config=config,
            prompt=prompt,
            fps=local_fps,
            max_pixels=mp,
            subtitle_text=subtitle_text,
        )
        
        # Validate the output
        validated_desc = validate_model_output(description)

        # Save video thumbnail to file (use thumbnail_frame from model output if present)
        thumbnail_frame = validated_desc.get("thumbnail_frame", 0)
        save_video_thumbnail_to_file(str(video_path), thumbnail_frame)
        
        # Calculate processing time
        classification_time = time.time() - start_time
        
        # Build output JSON
        output_data = {
            "filename": video_path.name,
            "video_description_long": validated_desc.get("video_description_long", ""),
            "video_description_short": validated_desc.get("video_description_short", ""),
            "primary_shot_type": validated_desc.get("primary_shot_type", ""),
            "tags": validated_desc.get("tags", []),
            "classification_time_seconds": classification_time,
            "classification_model": model_name,
            "video_length_seconds": video_length,
            "video_timestamp": video_timestamp,
            # video_thumbnail_base64 is deprecated - thumbnails are now saved as JPG files
            "rating": validated_desc.get("rating", 0.5),
            "segments": validated_desc.get("segments", []),
        }
        
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON output
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Successfully saved results to: {output_json}")
        return True
        
    except Exception as e:
        print(f"Error describing video: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for describe to JSON."""
    if len(sys.argv) < 4:
        print("Usage: describe_to_json.py <video_file> <subtitle_file> <output_json> [model_name] [fps] [max_pixels]", file=sys.stderr)
        print("Example: describe_to_json.py video.mp4 video_cleaned.srt video.json", file=sys.stderr)
        sys.exit(1)
    
    video_file = sys.argv[1]
    subtitle_file = sys.argv[2]
    output_json = sys.argv[3]
    model_name = sys.argv[4] if len(sys.argv) > 4 else "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    fps = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
    max_pixels = int(sys.argv[6]) if len(sys.argv) > 6 else 224
    
    success = describe_to_json(
        video_file,
        subtitle_file,
        output_json,
        model_name=model_name,
        fps=fps,
        max_pixels=max_pixels
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
