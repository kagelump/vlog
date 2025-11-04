#!/usr/bin/env python3
"""
SD card video discovery utility.

This script scans an SD card for video files and identifies main files
and their corresponding preview files (if they exist).
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple


def find_video_files(sd_card_path: str, extensions: List[str]) -> List[Path]:
    """
    Find all video files on the SD card with the given extensions.
    
    Args:
        sd_card_path: Path to the SD card mount point
        extensions: List of file extensions to search for (e.g., ['mp4', 'MP4'])
    
    Returns:
        List of Path objects for video files found
    """
    video_files = []
    sd_path = Path(sd_card_path)
    
    if not sd_path.exists():
        print(f"Error: SD card path does not exist: {sd_card_path}", file=sys.stderr)
        return []
    
    # Recursively search for video files
    for ext in extensions:
        video_files.extend(sd_path.rglob(f"*.{ext}"))
    
    return sorted(video_files)


def identify_preview_files(video_files: List[Path], preview_suffix: str = "_preview") -> Dict[str, Tuple[Path, Path | None]]:
    """
    Identify main files and their corresponding preview files.
    
    Args:
        video_files: List of video file paths
        preview_suffix: Suffix used to identify preview files
    
    Returns:
        Dictionary mapping main file stem to tuple of (main_file_path, preview_file_path or None)
    """
    # Separate main and preview files
    preview_files = {}
    main_files = {}
    
    for video_file in video_files:
        stem = video_file.stem
        
        if stem.endswith(preview_suffix):
            # This is a preview file
            main_stem = stem[:-len(preview_suffix)]
            preview_files[main_stem] = video_file
        else:
            # This is a main file
            main_files[stem] = video_file
    
    # Match main files with preview files
    result = {}
    for stem, main_file in main_files.items():
        preview_file = preview_files.get(stem)
        result[stem] = (main_file, preview_file)
    
    return result


def main():
    """
    Main entry point for SD card video discovery.
    
    Outputs JSON with list of video files and their preview status.
    """
    if len(sys.argv) < 3:
        print("Usage: discover_videos.py <sd_card_path> <extensions_json>", file=sys.stderr)
        print("Example: discover_videos.py /Volumes/SDCARD '[\"mp4\", \"MP4\", \"mov\", \"MOV\"]'", file=sys.stderr)
        sys.exit(1)
    
    sd_card_path = sys.argv[1]
    extensions = json.loads(sys.argv[2])
    preview_suffix = sys.argv[3] if len(sys.argv) > 3 else "_preview"
    
    # Find all video files
    video_files = find_video_files(sd_card_path, extensions)
    
    if not video_files:
        print(json.dumps({"videos": [], "count": 0}))
        return
    
    # Identify main and preview files
    video_pairs = identify_preview_files(video_files, preview_suffix)
    
    # Format output
    output = {
        "videos": [
            {
                "stem": stem,
                "main_file": str(main_file),
                "preview_file": str(preview_file) if preview_file else None,
                "has_preview": preview_file is not None
            }
            for stem, (main_file, preview_file) in video_pairs.items()
        ],
        "count": len(video_pairs)
    }
    
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
