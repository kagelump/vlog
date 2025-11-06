"""
Snakemake workflow for managing the describe daemon.

This workflow handles starting and stopping the MLX-VLM describe daemon
that is used by the describe stage (stage 3).

The daemon is started automatically when needed and creates a signal file
that other rules can depend on to ensure the daemon is running.

Usage:
    # Start daemon (usually called automatically by stage 3)
    snakemake --snakefile src/ingest_pipeline/snakefiles/daemon.smk --cores 1 start_daemon
    
    # Stop daemon (cleanup)
    snakemake --snakefile src/ingest_pipeline/snakefiles/daemon.smk --cores 1 stop_daemon
"""

import os


# Load configuration
configfile: "config.yaml"


# Get folders from config
PREVIEW_FOLDER = config.get("preview_folder", "videos/preview")
PREVIEW_SUFFIX = config.get("preview_suffix", "_preview")

# Describe settings
DESCRIBE = config.get("describe", {})
DESCRIBE_MODEL = DESCRIBE.get("model", "mlx-community/Qwen3-VL-8B-Instruct-4bit")

# Daemon settings
DAEMON_HOST = config.get("daemon_host", "127.0.0.1")
DAEMON_PORT = config.get("daemon_port", 5555)


# Helper function to discover preview videos (for dependency tracking)
def discover_preview_videos():
    """Discover all preview videos that have been created."""
    from pathlib import Path
    import glob
    
    preview_dir = Path(PREVIEW_FOLDER)
    if not preview_dir.exists():
        return []
    
    # Find all preview videos
    pattern = f"{PREVIEW_FOLDER}/*{PREVIEW_SUFFIX}.mp4"
    videos = glob.glob(pattern)
    
    # Extract stems (remove folder path and suffix+extension)
    stems = []
    for video in videos:
        basename = Path(video).stem  # Remove .mp4
        stem = basename.replace(PREVIEW_SUFFIX, "")  # Remove _preview suffix
        stems.append(stem)
    
    return stems


# Mark these as local rules (don't submit to cluster if using one)
localrules: start_daemon, stop_daemon


rule start_daemon:
    """Start the describe daemon and create a signal file."""
    input:
        # Optionally depend on all subtitles being ready
        # This ensures we don't start the daemon until we have work to do
        expand(
            f"{PREVIEW_FOLDER}/{{stem}}{PREVIEW_SUFFIX}_cleaned.srt", 
            stem=discover_preview_videos() 
        )
    output:
        temp("status/daemon_running.signal")
    params:
        model=DESCRIBE_MODEL,
        host=DAEMON_HOST,
        port=DAEMON_PORT,
        log_file="logs/daemon.log",
        pid_file="status/daemon.pid"
    log:
        "logs/daemon_start.log"
    message:
        "Starting describe daemon on {params.host}:{params.port}"
    shell:
        """
        # Create status directory if needed
        mkdir -p status logs
        
        # Run the daemon start script
        bash src/ingest_pipeline/start_daemon.sh \
            "{params.model}" \
            "{params.host}" \
            "{params.port}" \
            "{params.log_file}" \
            "{params.pid_file}" \
            "{output}" \
            > {log} 2>&1
        """


rule stop_daemon:
    """Stop the describe daemon and clean up signal file."""
    input:
        signal="status/daemon_running.signal",
        pid="status/daemon.pid"
    params:
        host=DAEMON_HOST,
        port=DAEMON_PORT
    log:
        "logs/daemon_stop.log"
    message:
        "Stopping describe daemon"
    shell:
        """
        bash src/ingest_pipeline/stop_daemon.sh \
            "{input.pid}" \
            "{input.signal}" \
            "{params.host}" \
            "{params.port}" \
            > {log} 2>&1
        """
