"""
Snakemake workflow for describing videos using ML model.

Stage 3: Describe videos and save results to JSON.

This workflow describes videos using the MLX-VLM daemon. The daemon is
automatically started by the master workflow (via daemon.smk) and will be
available before any describe jobs run.

Usage:
    # Run with master workflow (recommended - daemon managed automatically):
    snakemake --snakefile src/ingest_pipeline/Snakefile --cores 1 --configfile config.yaml stage3
    
    # Or run independently (requires daemon to be started first):
    snakemake --snakefile src/ingest_pipeline/snakefiles/describe.smk --cores 1 --configfile config.yaml

Notes:
    - When run via master workflow, daemon is started automatically
    - All describe jobs reuse the same daemon instance for efficiency
    - The daemon keeps the model loaded in memory across all video processing
    - Daemon management is handled in daemon.smk
"""

from pathlib import Path
import glob
import os


# Configuration is inherited from the main Snakefile that includes this file
# DO NOT use configfile directive here - it would reload config and lose command-line overrides

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
DAEMON_SIGNAL_FILE = config.get("daemon_signal_file", "status/daemon_running.signal")


# If there are cleaned subtitle files, it is ready for this stage.
def discover_videos_with_subtitles():
    return glob_wildcards(f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt").stem


rule describe:
    resources:
        mem_gb=8
    input:
        video=f"{PREVIEW_FOLDER}/{{stem}}.mp4",
        subtitle=f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt",
        daemon_signal=DAEMON_SIGNAL_FILE
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
        uv run -- python src/ingest_pipeline/scripts/describe_to_json.py \
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
