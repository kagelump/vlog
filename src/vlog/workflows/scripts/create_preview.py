#!/usr/bin/env python3
"""
Create a preview/proxy video file using ffmpeg.

This script creates a lower-resolution preview file from a main video file
for faster processing during the describe workflow.
"""

import os
import sys
import subprocess
from pathlib import Path


def create_preview_file(
    input_file: str,
    output_file: str,
    width: int = 1280,
    vcodec: str = "libx264",
    crf: int = 23,
    preset: str = "medium"
) -> bool:
    """
    Create a preview file using ffmpeg.
    
    Args:
        input_file: Path to the input video file
        output_file: Path where the preview file should be saved
        width: Target width in pixels (height auto-calculated)
        vcodec: Video codec to use
        crf: Constant Rate Factor (18-28, lower = better quality)
        preset: Encoding preset
    
    Returns:
        True if successful, False otherwise
    """
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file does not exist: {input_file}", file=sys.stderr)
        return False
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build ffmpeg command
    # Scale to width, maintain aspect ratio (-1 for height)
    # Use high quality encoding with CRF
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vf", f"scale={width}:-1",
        "-c:v", vcodec,
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "aac",
        "-b:a", "128k",
        "-y",  # Overwrite output file if it exists
        str(output_path)
    ]
    
    try:
        print(f"Creating preview file: {output_file}")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        print(f"Successfully created preview file: {output_file}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error creating preview file:", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: ffmpeg not found. Please install ffmpeg.", file=sys.stderr)
        return False


def main():
    """Main entry point for preview file creation."""
    if len(sys.argv) < 3:
        print("Usage: create_preview.py <input_file> <output_file> [width] [crf] [preset]", file=sys.stderr)
        print("Example: create_preview.py input.mp4 output_preview.mp4 1280 23 medium", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    crf = int(sys.argv[4]) if len(sys.argv) > 4 else 23
    preset = sys.argv[5] if len(sys.argv) > 5 else "medium"
    
    success = create_preview_file(input_file, output_file, width, crf=crf, preset=preset)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
