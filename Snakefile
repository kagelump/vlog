"""
Snakemake workflow for video ingestion from SD card.

This workflow orchestrates the complete video ingestion pipeline:
1. Copy main file from SD card to main folder
2. Copy or create preview file in preview folder
3. Transcribe preview file to generate subtitles
4. Clean subtitle file
5. Describe preview file and save results to JSON

Usage:
    snakemake --cores 1 --configfile config.yaml
    
    # Or with custom config:
    snakemake --cores 1 --config sd_card_path=/Volumes/MYCARD main_folder=output/main
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
PREVIEW_SUFFIX = config.get("preview_suffix", "_preview")
PREVIEW_EXT = config.get("preview_extension", "mp4")

# Preview settings
PREVIEW_SETTINGS = config.get("preview_settings", {})
PREVIEW_WIDTH = PREVIEW_SETTINGS.get("width", 1280)
PREVIEW_CRF = PREVIEW_SETTINGS.get("crf", 23)
PREVIEW_PRESET = PREVIEW_SETTINGS.get("preset", "medium")

# Transcribe settings
TRANSCRIBE = config.get("transcribe", {})
TRANSCRIBE_MODEL = TRANSCRIBE.get("model", "mlx-community/whisper-large-v3-turbo")

# Describe settings
DESCRIBE = config.get("describe", {})
DESCRIBE_MODEL = DESCRIBE.get("model", "mlx-community/Qwen3-VL-8B-Instruct-4bit")
DESCRIBE_MAX_PIXELS = DESCRIBE.get("max_pixels", 224)


# Discover videos on SD card
def discover_videos():
    """Discover video files on the SD card."""
    script_path = "scripts/discover_videos.py"
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


# Rule: Process all videos
rule all:
    input:
        # Final output: JSON files for all videos
        expand(f"{PREVIEW_FOLDER}/{{stem}}.json", stem=VIDEO_STEMS)


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
                    "scripts/create_preview.py",
                    input.main,
                    output[0],
                    str(PREVIEW_WIDTH),
                    str(PREVIEW_CRF),
                    PREVIEW_PRESET
                ]
                subprocess.run(cmd, check=True)


# Rule: Transcribe preview file to generate subtitles
rule transcribe:
    input:
        f"{PREVIEW_FOLDER}/{{stem}}.{PREVIEW_EXT}"
    output:
        f"{PREVIEW_FOLDER}/{{stem}}.srt"
    params:
        model=TRANSCRIBE_MODEL
    shell:
        """
        mlx_whisper --model {params.model} -f srt --task transcribe {input}
        """


# Rule: Clean subtitle file
rule clean_subtitles:
    input:
        f"{PREVIEW_FOLDER}/{{stem}}.srt"
    output:
        f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt"
    run:
        import sys
        
        # Add src to path
        project_root = Path(workflow.basedir)
        sys.path.insert(0, str(project_root / "src"))
        
        from vlog.srt_cleaner import parse_srt, clean_subtitles, reassemble_srt
        
        print(f"Cleaning subtitle file: {input[0]}")
        
        # Parse the SRT file
        subtitles = parse_srt(input[0])
        
        # Clean the subtitles
        cleaned_subtitles = clean_subtitles(subtitles)
        
        # Write the cleaned subtitles
        with open(output[0], 'w', encoding='utf-8') as f:
            f.write(reassemble_srt(cleaned_subtitles))


# Rule: Describe video and save to JSON
rule describe:
    input:
        video=f"{PREVIEW_FOLDER}/{{stem}}.{PREVIEW_EXT}",
        subtitle=f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt"
    output:
        f"{PREVIEW_FOLDER}/{{stem}}.json"
    params:
        model=DESCRIBE_MODEL,
        max_pixels=DESCRIBE_MAX_PIXELS
    shell:
        """
        python3 scripts/describe_to_json.py "{input.video}" "{input.subtitle}" "{output}" "{params.model}" 1.0 {params.max_pixels}
        """


# Rule: Import JSON results to database (optional)
# This rule is used by auto-ingest to save results to the database
rule json_to_db:
    input:
        f"{PREVIEW_FOLDER}/{{stem}}.json"
    output:
        touch(f"{PREVIEW_FOLDER}/{{stem}}.db_imported")
    run:
        import sys
        import json
        
        # Add src to path
        project_root = Path(workflow.basedir)
        sys.path.insert(0, str(project_root / "src"))
        
        from vlog.db import insert_result, initialize_db
        
        # Initialize database
        initialize_db()
        
        # Load JSON data
        with open(input[0], 'r') as f:
            data = json.load(f)
        
        print(f"Importing {data['filename']} to database")
        
        # Insert into database
        insert_result(
            filename=data['filename'],
            video_description_long=data.get('video_description_long', ''),
            video_description_short=data.get('video_description_short', ''),
            primary_shot_type=data.get('primary_shot_type', ''),
            tags=data.get('tags', []),
            classification_time_seconds=data.get('classification_time_seconds', 0.0),
            classification_model=data.get('classification_model', ''),
            video_length_seconds=data.get('video_length_seconds', 0.0),
            video_timestamp=data.get('video_timestamp', ''),
            video_thumbnail_base64=data.get('video_thumbnail_base64', ''),
            in_timestamp=data.get('in_timestamp'),
            out_timestamp=data.get('out_timestamp'),
            rating=data.get('rating', 0.0),
            segments=data.get('segments')
        )
        
        print(f"Successfully imported {data['filename']} to database")
