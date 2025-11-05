"""
Snakemake workflow for describing videos using ML model.

Stage 3: Describe videos and save results to JSON.

This workflow describes videos using the MLX-VLM daemon. The daemon should be
started externally before running this workflow for best results.

Usage:
    # Recommended: Start daemon first in a separate terminal
    python -m vlog.describe_daemon --model mlx-community/Qwen3-VL-8B-Instruct-4bit &
    
    # Then run workflow:
    snakemake --snakefile src/ingest_pipeline/describe.smk --cores 1 --configfile config.yaml

Notes:
    - The daemon should be running before starting this workflow
    - All describe jobs will reuse the same daemon instance for efficiency
    - The daemon keeps the model loaded in memory across all video processing
"""

from pathlib import Path
import glob
import os


# Load configuration
configfile: "config.yaml"


# Get output folders from config
PREVIEW_FOLDER = config.get("preview_folder", "videos/preview")
PREVIEW_EXT = config.get("preview_extension", "mp4")

# Describe settings
DESCRIBE = config.get("describe", {})
DESCRIBE_MODEL = DESCRIBE.get("model", "mlx-community/Qwen3-VL-8B-Instruct-4bit")
DESCRIBE_MAX_PIXELS = DESCRIBE.get("max_pixels", 224)
DESCRIBE_FPS = DESCRIBE.get("fps", 1.0)

# Daemon settings
DAEMON_HOST = config.get("daemon_host", "127.0.0.1")
DAEMON_PORT = config.get("daemon_port", 5555)
DAEMON_WATCH_FILE = config.get("daemon_watch_file", "daemon_watch.txt")

# If there are cleaned subtitle files, it is ready for this stage.
def discover_videos_with_subtitles():
    return glob_wildcards(f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt").stem

rule all:
    input:
        expand(f"{PREVIEW_FOLDER}/{{stem}}.json", stem=discover_videos_with_subtitles())

localrules: start_daemon, stop_daemon

rule describe:
    threads: 1
    input:
        video=f"{PREVIEW_FOLDER}/{{stem}}.mp4",
        subtitle=f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt"
        daemon_watch=DAEMON_WATCH_FILE
    output:
        f"{PREVIEW_FOLDER}/{{stem}}.json"
    params:
        model=DESCRIBE_MODEL,
        max_pixels=DESCRIBE_MAX_PIXELS,
        fps=DESCRIBE_FPS,
        daemon_host=DAEMON_HOST,
        daemon_port=DAEMON_PORT
    log:
        "logs/describe/{stem}.log"
    message:
        "Describing video: {wildcards.stem}"
    shell:
        """
        uv run -- python src/ingest_pipeline/describe_to_json.py \
            "{input.video}" \
            "{input.subtitle}" \
            "{output}" \
            "{params.model}" \
            {params.fps} \
            {params.max_pixels} \
            {params.daemon_host} \
            {params.daemon_port} \
            2>&1 | tee {log}
        """
