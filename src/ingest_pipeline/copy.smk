"""
Snakemake workflow for copying videos from SD card to working directory.

Stage 1: Copy videos from SD card and create/copy preview files.

This workflow:
1. Discovers videos on SD card
2. Copies main video files to main folder
3. Copies existing preview files or creates new ones

Usage:
    snakemake --snakefile src/ingest_pipeline/Snakefile.copy --cores 1 --configfile config.yaml
"""

import os
import json
import subprocess
from pathlib import Path


# Load configuration
configfile: "config.yaml"


# Get SD card path and output folders from config
SD_CARD = config.get("sd_card_path", "/Volumes/SDCARD")
MAIN_FOLDER = config.get("main_folder", "videos/main")
PREVIEW_FOLDER = config.get("preview_folder", "videos/preview")
VIDEO_EXTENSIONS = config.get("video_extensions", ["mp4", "MP4", "mov", "MOV"])
PREVIEW_EXT = config.get("preview_extension", "mp4")

# Preview settings
PREVIEW_SETTINGS = config.get("preview_settings", {})
PREVIEW_WIDTH = PREVIEW_SETTINGS.get("width", 1280)
PREVIEW_CRF = PREVIEW_SETTINGS.get("crf", 23)
PREVIEW_PRESET = PREVIEW_SETTINGS.get("preset", "medium")


# Discover videos on SD card
def discover_videos():
    """Discover video files on the SD card."""
    script_path = "src/ingest_pipeline/scripts/discover_videos.py"
    extensions_json = json.dumps(VIDEO_EXTENSIONS)
    
    cmd = ["python3", script_path, SD_CARD, extensions_json, PREVIEW_SUFFIX]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        videos_data = json.loads(result.stdout)
        return videos_data.get("videos", [])
    except subprocess.CalledProcessError as e:
        print(f"Error discovering videos: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing video discovery output: {e}")
        return []


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
        # Main files
        expand(f"{MAIN_FOLDER}/{{stem}}.mp4", stem=VIDEO_STEMS),
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
        main=f"{MAIN_FOLDER}/{{stem}}.mp4"
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
                    "src/ingest_pipeline/create_preview.py",
                    input.main,
                    output[0],
                    str(PREVIEW_WIDTH),
                    str(PREVIEW_CRF),
                    PREVIEW_PRESET
                ]
                subprocess.run(cmd, check=True)
