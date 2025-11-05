"""
Snakemake workflow for describing videos using ML model.

Stage 3: Describe videos and save results to JSON.

This workflow:
1. Starts describe daemon (if not already running)
2. Describes each video using the daemon
3. Saves results to JSON files
4. Stops daemon on completion (optional)

The daemon is shared across all video descriptions for efficiency.

Usage:
    # Start daemon first:
    python -m vlog.describe_daemon --model mlx-community/Qwen3-VL-8B-Instruct-4bit &
    
    # Then run workflow:
    snakemake --snakefile src/ingest_pipeline/Snakefile.describe --cores 1 --configfile config.yaml
    
    # Or let the workflow manage the daemon:
    snakemake --snakefile src/ingest_pipeline/Snakefile.describe --cores 1 --configfile config.yaml --config manage_daemon=true
"""

from pathlib import Path
import atexit
import glob
import os
import requests
import subprocess
import time


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
MANAGE_DAEMON = config.get("manage_daemon", False)


# Global daemon process handle
DAEMON_PROCESS = None


def start_daemon():
    """Start the describe daemon if manage_daemon is enabled."""
    global DAEMON_PROCESS
    
    if not MANAGE_DAEMON:
        print("Daemon management disabled. Expecting daemon to be running externally.")
        return
    
    print(f"Starting describe daemon on {DAEMON_HOST}:{DAEMON_PORT}...")
    
    cmd = [
        "python", "-m", "vlog.describe_daemon",
        "--host", DAEMON_HOST,
        "--port", str(DAEMON_PORT),
        "--model", DESCRIBE_MODEL
    ]
    
    DAEMON_PROCESS = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for daemon to be ready
    import requests
    max_wait = 60
    waited = 0
    while waited < max_wait:
        try:
            response = requests.get(f"http://{DAEMON_HOST}:{DAEMON_PORT}/health", timeout=2)
            if response.status_code == 200:
                print("Daemon started successfully")
                return
        except:
            pass
        time.sleep(1)
        waited += 1
    
    print("Warning: Daemon may not have started properly")


def stop_daemon():
    """Stop the describe daemon if we started it."""
    global DAEMON_PROCESS
    
    if DAEMON_PROCESS:
        print("Stopping describe daemon...")
        DAEMON_PROCESS.terminate()
        try:
            DAEMON_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            DAEMON_PROCESS.kill()
        DAEMON_PROCESS = None


# Start daemon on workflow initialization if configured
if MANAGE_DAEMON:
    start_daemon()
    atexit.register(stop_daemon)


# Discover existing preview videos with cleaned subtitles
def discover_videos_with_subtitles():
    """Discover preview videos that have cleaned subtitle files."""
    subtitle_pattern = f"{PREVIEW_FOLDER}/*_cleaned.srt"
    subtitle_files = glob.glob(subtitle_pattern)
    # Extract stem by removing _cleaned.srt
    stems = [Path(f).stem.replace("_cleaned", "") for f in subtitle_files]
    return stems


# Get list of video stems
VIDEO_STEMS = discover_videos_with_subtitles()


# Rule: Describe all videos
rule describe_all:
    input:
        # JSON description files
        expand(f"{PREVIEW_FOLDER}/{{stem}}.json", stem=VIDEO_STEMS)


# Rule: Describe video and save to JSON
rule describe:
    input:
        video=f"{PREVIEW_FOLDER}/{{stem}}.{PREVIEW_EXT}",
        subtitle=f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt"
    output:
        f"{PREVIEW_FOLDER}/{{stem}}.json"
    params:
        model=DESCRIBE_MODEL,
        max_pixels=DESCRIBE_MAX_PIXELS,
        fps=DESCRIBE_FPS,
        daemon_host=DAEMON_HOST,
        daemon_port=DAEMON_PORT
    shell:
        """
        python src/ingest_pipeline/describe_to_json.py \
            "{input.video}" \
            "{input.subtitle}" \
            "{output}" \
            "{params.model}" \
            {params.fps} \
            {params.max_pixels} \
            {params.daemon_host} \
            {params.daemon_port}
        """


# Note: The daemon cleanup is handled by atexit if manage_daemon=true
