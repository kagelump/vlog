"""
Stage 2: Subtitle generation and cleaning

This stage:
1. Transcribes preview videos to generate subtitles
2. Cleans subtitle files (removes duplicates and hallucinations)

Usage:
    snakemake --snakefile src/ingest_pipeline/Snakefile.subtitles --cores 1 --configfile config.yaml
"""

import os
import glob
from pathlib import Path


# Load configuration
configfile: "config.yaml"


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
    video_files = glob.glob(preview_pattern)
    stems = [Path(f).stem for f in video_files]
    return stems


# Get list of video stems
VIDEO_STEMS = discover_preview_videos()


# Rule: Process all subtitles
rule subtitles_all:
    input:
        # Cleaned subtitle files
        expand(f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt", stem=VIDEO_STEMS)


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
        f"{PREVIEW_FOLDER}/{{stem}}{PREVIEW_SUFFIX}.srt"
    output:
        f"{PREVIEW_FOLDER}/{{stem}}{PREVIEW_SUFFIX}_cleaned.srt"
    run:
        # Import here to avoid parse-time dependency issues
        from srt_cleaner import process_srt_file
        
        cleaned_srt_output = process_srt_file(input[0])
        with open(output[0], 'w', encoding='utf-8') as f:
            f.write(cleaned_srt_output)
