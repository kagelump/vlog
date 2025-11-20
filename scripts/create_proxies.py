#!/usr/bin/env python3
"""
One-off video proxy creation script.

This script:
- Looks for all *.mp4 and *.MP4 files in descendant directories (from cwd)
- Excludes pre-existing proxies in proxy directories
- Creates a "proxy" directory under each file's parent directory
- Runs ffmpeg to compress into a 1080p file with all existing metadata

Requirements: ffmpeg, ffprobe

Usage:
    cd /path/to/your/video/directory
    python3 /path/to/scripts/create_proxies.py
    
    # Or from repository root:
    python3 scripts/create_proxies.py --root /path/to/video/directory
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def find_video_files(root_dir: Path) -> List[Path]:
    """
    Find all .mp4 and .MP4 files recursively, excluding proxy directories.
    
    Args:
        root_dir: Root directory to search from
        
    Returns:
        List of Path objects for video files
    """
    video_files = []
    
    # Find all .mp4 files (case-insensitive by checking both extensions)
    for pattern in ['**/*.mp4', '**/*.MP4']:
        for video_path in root_dir.glob(pattern):
            # Skip files in proxy directories
            if 'proxy' in video_path.parts:
                continue
            video_files.append(video_path)
    
    # Remove duplicates (in case filesystem is case-insensitive)
    video_files = list(set(video_files))
    video_files.sort()
    
    return video_files


def get_video_framerate(video_path: Path) -> str:
    """
    Get the frame rate of a video using ffprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Frame rate string (e.g., "30000/1001" or "24"), or empty string on error
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=r_frame_rate',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(video_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def create_proxy(video_path: Path, proxy_dir: Path, overwrite: bool = False) -> Tuple[bool, str]:
    """
    Create a 1080p proxy for a video file.
    
    Args:
        video_path: Path to the source video file
        proxy_dir: Path to the proxy directory
        overwrite: Whether to overwrite existing proxy files
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Create proxy directory if it doesn't exist
    proxy_dir.mkdir(parents=True, exist_ok=True)
    
    # Proxy file has the same name as the source
    proxy_path = proxy_dir / video_path.name
    
    # Check if proxy already exists
    if proxy_path.exists() and not overwrite:
        return True, f"Skipping (exists): {proxy_path}"
    
    # Get source frame rate
    fps = get_video_framerate(video_path)
    
    # Build ffmpeg command
    # Settings:
    # - 1080p (scale to height 1080, width auto with divisible-by-2 constraint)
    # - CRF 28 (good balance of quality and file size)
    # - preset "slower" (better compression)
    # - profile high, level 4.1 (common compatibility)
    # - AAC audio at 64k, mono
    # - preserve metadata
    # - faststart for web playback
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-hide_banner',
        '-loglevel', 'error',
        '-i', str(video_path),
        '-map_metadata', '0',  # Copy all metadata
        '-c:v', 'libx264',
        '-preset', 'slower',
        '-crf', '28',
        '-profile:v', 'high',
        '-level', '4.1',
        '-pix_fmt', 'yuv420p',
        '-vf', 'scale=-2:1080',  # Scale to 1080p, width divisible by 2
    ]
    
    # Add frame rate if detected
    if fps:
        cmd.extend(['-r', fps, '-vsync', 'cfr'])
    
    # Add audio settings
    cmd.extend([
        '-c:a', 'aac',
        '-b:a', '64k',
        '-ac', '1',  # Mono audio
        '-movflags', '+faststart',
        str(proxy_path)
    ])
    
    try:
        print(f"Encoding: {video_path} -> {proxy_path} (fps={fps})")
        subprocess.run(cmd, check=True, capture_output=True)
        return True, f"Done: {proxy_path}"
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        return False, f"Error encoding {video_path}: {error_msg}"
    except FileNotFoundError:
        return False, "Error: ffmpeg not found. Please install ffmpeg."


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Create 1080p proxy videos in proxy subdirectories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--root',
        type=Path,
        default=Path.cwd(),
        help='Root directory to search for videos (default: current directory)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing proxy files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually creating proxies'
    )
    
    args = parser.parse_args()
    
    # Validate root directory
    if not args.root.exists():
        print(f"Error: Directory {args.root} does not exist", file=sys.stderr)
        return 1
    
    if not args.root.is_dir():
        print(f"Error: {args.root} is not a directory", file=sys.stderr)
        return 1
    
    # Find all video files
    print(f"Searching for video files in {args.root}...")
    video_files = find_video_files(args.root)
    
    if not video_files:
        print("No video files found.")
        return 0
    
    print(f"Found {len(video_files)} video file(s)")
    
    # Process each video
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for video_path in video_files:
        # Proxy directory is a subdirectory of the video's parent directory
        proxy_dir = video_path.parent / "proxy"
        
        if args.dry_run:
            print(f"Would create: {proxy_dir / video_path.name}")
            continue
        
        success, message = create_proxy(video_path, proxy_dir, args.overwrite)
        print(message)
        
        if success:
            if "Skipping" in message:
                skip_count += 1
            else:
                success_count += 1
        else:
            error_count += 1
    
    # Print summary
    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"Dry run complete. Would process {len(video_files)} file(s)")
    else:
        print(f"Complete!")
        print(f"  Created: {success_count}")
        print(f"  Skipped: {skip_count}")
        print(f"  Errors:  {error_count}")
    
    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
