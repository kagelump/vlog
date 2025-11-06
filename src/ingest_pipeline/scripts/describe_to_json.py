#!/usr/bin/env python3
"""
Video description to JSON output.

This script connects to the describe daemon to process videos and outputs
the results to a JSON file. The daemon should be started separately
(typically by the Snakemake workflow).
"""

import os
import sys
import json
from pathlib import Path

# Add src to path so we can import vlog modules
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "src"))

from vlog.describe_client import DaemonManager


def describe_to_json(
    video_file: str,
    subtitle_file: str,
    output_json: str,
    model_name: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit",
    fps: float = 1.0,
    max_pixels: int = 224,
    daemon_host: str = "127.0.0.1",
    daemon_port: int = 5555,
) -> bool:
    """
    Describe a video using the daemon and save results to JSON file.
    
    Args:
        video_file: Path to the video file
        subtitle_file: Path to the cleaned subtitle file (used by daemon)
        output_json: Path where JSON output should be saved
        model_name: Name of the model (informational, daemon uses its own model)
        fps: Frames per second to sample (adaptive fps calculated by daemon)
        max_pixels: Maximum pixels for image processing
        daemon_host: Daemon host address
        daemon_port: Daemon port
    
    Returns:
        True if successful, False otherwise
    """
    video_path = Path(video_file)
    output_path = Path(output_json)
    
    # Validate input file exists
    if not video_path.exists():
        print(f"Error: Video file does not exist: {video_file}", file=sys.stderr)
        return False
    
    # Subtitle file is checked by the daemon (it looks for <video>.srt automatically)
    
    try:
        # Connect to daemon
        daemon = DaemonManager(host=daemon_host, port=daemon_port)
        
        # Check if daemon is running
        if not daemon.is_daemon_running():
            print(f"Error: Daemon not running at {daemon_host}:{daemon_port}", file=sys.stderr)
            print("Start the daemon first with: python -m vlog.describe_daemon", file=sys.stderr)
            return False
        
        print(f"Describing video: {video_file}")
        
        # Convert max_pixels if needed (same logic as before)
        mp = int(max_pixels)
        if mp > 0 and mp < 1000:
            mp = mp * mp
        
        # Send video to daemon for description
        description = daemon.describe_video(
            video_path=str(video_path),
            fps=fps,
            max_pixels=mp,
        )
        
        if not description:
            print(f"Error: Failed to get description from daemon", file=sys.stderr)
            return False
        
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON output
        with open(output_path, 'w') as f:
            json.dump(description, f, indent=2)
        
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
        print("Usage: describe_to_json.py <video_file> <subtitle_file> <output_json> [model_name] [fps] [max_pixels] [daemon_host] [daemon_port]", file=sys.stderr)
        print("Example: describe_to_json.py video.mp4 video_cleaned.srt video.json", file=sys.stderr)
        print("\nNote: This script connects to a running describe daemon.", file=sys.stderr)
        print("Start the daemon first: python -m vlog.describe_daemon", file=sys.stderr)
        sys.exit(1)
    
    video_file = sys.argv[1]
    subtitle_file = sys.argv[2]
    output_json = sys.argv[3]
    model_name = sys.argv[4] if len(sys.argv) > 4 else "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    fps = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
    max_pixels = int(sys.argv[6]) if len(sys.argv) > 6 else 224
    daemon_host = sys.argv[7] if len(sys.argv) > 7 else "127.0.0.1"
    daemon_port = int(sys.argv[8]) if len(sys.argv) > 8 else 5555
    
    success = describe_to_json(
        video_file,
        subtitle_file,
        output_json,
        model_name=model_name,
        fps=fps,
        max_pixels=max_pixels,
        daemon_host=daemon_host,
        daemon_port=daemon_port,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
