"""
Snakemake workflow for copying videos from SD card to working directory.

Stage 1: Copy videos from SD card and create/copy preview files.

This workflow:
1. Discovers videos on SD card
2. (Optional) Copies main video files to main folder (if set)
3. Copies existing preview files or creates new ones

Usage:
    snakemake --snakefile src/vlog/workflows/Snakefile.copy --cores 1 --configfile config.yaml
"""

import os
import subprocess
from pathlib import Path

# Import helper for communicating with status logger
from vlog.snakemake_logger_plugin.helpers import set_expected_total


# Load configuration
configfile: "config.yaml"


# Get SD card path(s) and output folders from config
# SD_CARD can be a single path string or a comma-separated list of paths
sd_card_raw = config.get("sd_card_path", "/Volumes/SDCARD")
SD_CARD_PATHS = [p.strip() for p in sd_card_raw.split(",")] if isinstance(sd_card_raw, str) else sd_card_raw
MAIN_FOLDER = config.get("main_folder")  # Optional: set to None or empty to skip copying main files
PREVIEW_FOLDER = config.get("preview_folder", "videos/preview")
VIDEO_EXTENSIONS = config.get("video_extensions", ["mp4", "MP4", "mov", "MOV"])
PREVIEW_EXT = config.get("preview_extension", "mp4")
PREVIEW_SUFFIX = config.get("preview_suffix", "_preview")

# Preview settings
PREVIEW_SETTINGS = config.get("preview_settings", {})
PREVIEW_WIDTH = PREVIEW_SETTINGS.get("width", 1280)
PREVIEW_CRF = PREVIEW_SETTINGS.get("crf", 23)
PREVIEW_PRESET = PREVIEW_SETTINGS.get("preset", "medium")


# Discover videos on SD card(s)
def discover_videos():
    """
    Discover video files on the SD card(s).
    
    Searches all paths in SD_CARD_PATHS recursively for video files
    with extensions in VIDEO_EXTENSIONS, and identifies main files
    and their corresponding preview files.
    
    Returns:
        List of dictionaries with video metadata:
        - stem: base filename without extension
        - main_file: path to main video file
        - has_preview: whether a preview file exists
        - preview_file: path to preview file (if exists)
    """
    from pathlib import Path
    
    # Find all video files across all SD card paths
    all_video_files = []
    for sd_path_str in SD_CARD_PATHS:
        sd_path = Path(sd_path_str)
        
        if not sd_path.exists():
            print(f"Warning: SD card path does not exist: {sd_path_str}")
            continue
        
        # Recursively search for video files with matching extensions
        for ext in VIDEO_EXTENSIONS:
            all_video_files.extend(sd_path.rglob(f"*.{ext}"))
    
    # Sort for consistent ordering
    all_video_files = sorted(all_video_files)
    
    # Identify main files and preview files
    # Preview files have PREVIEW_SUFFIX in the stem (e.g., "video_preview.mp4")
    preview_files = {}
    main_files = {}
    
    for video_file in all_video_files:
        stem = video_file.stem
        
        if PREVIEW_SUFFIX in stem:
            # This is a preview file
            # Extract the main file stem by removing the preview suffix
            main_stem = stem.replace(PREVIEW_SUFFIX, "")
            preview_files[main_stem] = video_file
        else:
            # This is a main file
            main_files[stem] = video_file
    
    # Build the result list
    videos = []
    for stem, main_file in main_files.items():
        video_info = {
            "stem": stem,
            "main_file": str(main_file),
            "has_preview": stem in preview_files,
        }
        if stem in preview_files:
            video_info["preview_file"] = str(preview_files[stem])
        
        videos.append(video_info)
    
    # Report expected total to status logger
    set_expected_total("copy_main", len(videos))
    set_expected_total("copy_or_create_preview", len(videos))
    
    return videos


# Get list of videos
VIDEOS = discover_videos()
VIDEO_STEMS = [v["stem"] for v in VIDEOS]


# Helper function to check if source and destination are the same
def should_skip_copy(src, dst):
    """Check if source and destination paths are the same (local mode)."""
    from pathlib import Path
    src_path = Path(src).resolve()
    dst_path = Path(dst).resolve()
    return src_path == dst_path


# Rule: Copy all videos and create previews
rule copy_all:
    input:
        # Main files (only if MAIN_FOLDER is set)
        (expand(f"{MAIN_FOLDER}/{{stem}}.mp4", stem=VIDEO_STEMS) if MAIN_FOLDER else []),
        # Preview files
        expand(f"{PREVIEW_FOLDER}/{{stem}}.{PREVIEW_EXT}", stem=VIDEO_STEMS)


# Rule: Copy main video file from SD card
rule copy_main:
    input:
        lambda wildcards: next(
            (v["main_file"] for v in VIDEOS if v["stem"] == wildcards.stem),
            None
        )
    output:
        f"{MAIN_FOLDER}/{{stem}}.mp4"
    run:
        import shutil
        from pathlib import Path
        
        os.makedirs(MAIN_FOLDER, exist_ok=True)
        
        # Check if source and destination are the same (local mode)
        if should_skip_copy(input[0], output[0]):
            print(f"Source and destination are the same, skipping copy: {input[0]}")
        else:
            print(f"Copying main file: {input[0]} -> {output[0]}")
            shutil.copy2(input[0], output[0])


# Rule: Copy preview file if it exists, otherwise create it
rule copy_or_create_preview:
    input:
        # Only depend on main file if MAIN_FOLDER is set, otherwise use source directly
        main=lambda wildcards: (
            f"{MAIN_FOLDER}/{wildcards.stem}.mp4" if MAIN_FOLDER 
            else next((v["main_file"] for v in VIDEOS if v["stem"] == wildcards.stem), None)
        )
    output:
        f"{PREVIEW_FOLDER}/{{stem}}.{PREVIEW_EXT}"
    run:
        import shutil
        from pathlib import Path
        
        os.makedirs(PREVIEW_FOLDER, exist_ok=True)
        
        # Check if source and destination are the same (local mode)
        if should_skip_copy(input.main, output[0]):
            print(f"Source and destination are the same (local mode), skipping copy: {input.main}")
        else:
            # Check if preview file exists on SD card
            video_info = next((v for v in VIDEOS if v["stem"] == wildcards.stem), None)
            
            if video_info and video_info.get("has_preview"):
                # Copy existing preview file
                preview_src = video_info["preview_file"]
                print(f"Copying existing preview file: {preview_src} -> {output[0]}")
                shutil.copy2(preview_src, output[0])
            else:
                # Create preview file using ffmpeg
                print(f"Creating preview file from: {input.main}")
                cmd = [
                    "python3",
                    "src/vlog/workflows/scripts/create_preview.py",
                    input.main,
                    output[0],
                    str(PREVIEW_WIDTH),
                    str(PREVIEW_CRF),
                    PREVIEW_PRESET
                ]
                subprocess.run(cmd, check=True)
