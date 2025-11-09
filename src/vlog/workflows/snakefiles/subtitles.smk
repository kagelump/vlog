"""
Stage 2: Subtitle generation and cleaning

This stage:
1. Transcribes preview videos to generate subtitles
2. Cleans subtitle files (removes duplicates and hallucinations)

Usage:
    snakemake --snakefile src/vlog/workflows/Snakefile.subtitles --cores 1 --configfile config.yaml
"""

import sys
import os
import glob
from pathlib import Path
import logging

# Import helper for communicating with status logger
from vlog.snakemake_logger_plugin.helpers import set_expected_total


# Ensure parent folder (src/vlog/workflows) is on sys.path so local modules can be imported
# Path(__file__).parents[0] -> snakefiles, parents[1] -> workflows
parent_dir = Path(__file__).resolve().parents[1]
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

logging.basicConfig(level=logging.DEBUG)

# Configuration is inherited from the main Snakefile that includes this file
# DO NOT use configfile directive here - it would reload config and lose command-line overrides

# Get output folders from config
PREVIEW_FOLDER = config.get("preview_folder", "videos/preview")
PREVIEW_EXT = config.get("preview_extension", "mp4")

# Transcribe settings
TRANSCRIBE = config.get("transcribe", {})
TRANSCRIBE_MODEL = TRANSCRIBE.get("model", "mlx-community/whisper-large-v3-turbo")


# Discover existing preview videos
def discover_preview_videos():
    """Discover preview video files in the preview folder."""
    preview_pattern = f"{PREVIEW_FOLDER}/*.{PREVIEW_EXT}"
    # Logger for debug tracing
    logger = logging.getLogger(__name__)
    try:
        logger.debug("Discovering preview videos with pattern: %s", preview_pattern)
        video_files = glob.glob(preview_pattern)
        logger.debug("Found %d preview files: %s", len(video_files), video_files)
        stems = [Path(f).stem for f in video_files]
        logger.debug("Derived stems: %s", stems)
        
        # Report expected total to status logger
        set_expected_total("transcribe", len(stems))
        set_expected_total("clean_subtitles", len(stems))
        
        return stems
    except Exception as e:
        # Log the full exception stack at debug level so callers can enable debug to investigate
        logger.exception("Error while discovering preview videos: %s", e)
        # Return empty list so Snakemake has a safe fallback (no inputs)
        return []


# Get list of video stems
VIDEO_STEMS = discover_preview_videos()


# Rule: Process all subtitles
rule subtitles_all:
    input:
        # Cleaned subtitle files
        expand(f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt", stem=VIDEO_STEMS)


# Rule: Transcribe preview file to generate JSON with word timestamps
rule transcribe:
    resources:
        mem_gb=5
    input:
        f"{PREVIEW_FOLDER}/{{stem}}.{PREVIEW_EXT}"
    output:
        f"{PREVIEW_FOLDER}/{{stem}}_whisper.json"
    log:
        "logs/transcribe/{stem}.log"
    params:
        model=TRANSCRIBE_MODEL,
        preview_folder=PREVIEW_FOLDER,
    script:
        "../scripts/transcribe.py"


# Rule: Clean subtitle file (convert JSON to clean SRT)
rule clean_subtitles:
    input:
        json=f"{PREVIEW_FOLDER}/{{stem}}_whisper.json"
    output:
        cleaned=f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt"
    # Use Snakemake's script directive to run the cleaner as a separate script.
    # This keeps the Snakefile declarative and lets the script handle imports.
    script:
        "../scripts/srt_cleaner.py"
