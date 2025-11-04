# Quick Start Guide: Snakemake Video Ingestion

This guide walks you through using the Snakemake workflow to ingest videos from an SD card.

## Step 1: Prepare Your Environment

1. **Install dependencies:**
   ```bash
   cd /path/to/vlog
   
   # Using uv (recommended):
   uv add snakemake pyyaml
   uv sync
   
   # Or using pip:
   pip install snakemake pyyaml
   ```

2. **Ensure ffmpeg and mlx_whisper are installed:**
   ```bash
   # Install ffmpeg
   brew install ffmpeg  # macOS
   # or
   sudo apt-get install ffmpeg  # Ubuntu/Debian
   
   # Install mlx_whisper
   pip install mlx-whisper
   ```

## Step 2: Configure the Workflow

1. **Mount your SD card** and note the mount path:
   ```bash
   # On macOS, it's usually:
   /Volumes/SDCARD
   
   # On Linux, it might be:
   /media/username/SDCARD
   ```

2. **Edit `config.yaml`** to set your SD card path and preferences:
   ```yaml
   # SD Card mount point
   sd_card_path: "/Volumes/SDCARD"
   
   # Output directories (will be created if they don't exist)
   main_folder: "videos/main"
   preview_folder: "videos/preview"
   ```

## Step 3: Run the Workflow

### Preview the Workflow (Dry Run)

First, see what will happen without actually running anything:

```bash
cd /path/to/vlog
snakemake --cores 1 --configfile config.yaml --dry-run
```

This will show you:
- Which videos will be processed
- What files will be created
- The order of operations

### Run the Full Workflow

```bash
snakemake --cores 1 --configfile config.yaml
```

The workflow will:
1. ✅ Discover videos on your SD card
2. ✅ Copy main files to `videos/main/`
3. ✅ Copy or create preview files in `videos/preview/`
4. ✅ Transcribe preview files to generate `.srt` subtitles
5. ✅ Clean subtitle files to create `_cleaned.srt` versions
6. ✅ Describe videos and save results to `.json` files

### Process Specific Videos

To process only specific videos:

```bash
# Process only myvideo.mp4
snakemake --cores 1 videos/preview/myvideo.json

# Process multiple specific videos
snakemake --cores 1 videos/preview/video1.json videos/preview/video2.json
```

## Step 4: Review the Results

After the workflow completes, your files will be organized like this:

```
videos/
├── main/
│   ├── video1.mp4           # Full-resolution main file
│   └── video2.mp4
└── preview/
    ├── video1.mp4           # Preview file (1280px width)
    ├── video1.srt           # Original subtitles
    ├── video1_cleaned.srt   # Cleaned subtitles
    ├── video1.json          # Description results ⭐
    ├── video2.mp4
    ├── video2.srt
    ├── video2_cleaned.srt
    └── video2.json          # Description results ⭐
```

### View Description Results

The `.json` files contain complete video analysis:

```bash
# Pretty-print a result file
cat videos/preview/video1.json | python3 -m json.tool

# Example output:
{
  "filename": "video1.mp4",
  "video_description_long": "A detailed description of the video content...",
  "video_description_short": "Brief summary...",
  "primary_shot_type": "pov",
  "tags": ["dynamic", "medium", "outdoor"],
  "classification_time_seconds": 145.3,
  "classification_model": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
  "video_length_seconds": 62.5,
  "video_timestamp": "2024-01-15T14:30:00",
  "rating": 0.85,
  "segments": [
    {
      "in_timestamp": "00:00:05.000",
      "out_timestamp": "00:00:25.000",
      "description": "Best segment..."
    }
  ]
}
```

## Common Workflows

### Processing a Fresh SD Card

When you insert a new SD card:

```bash
# 1. Update the SD card path if needed
# 2. Run the workflow
snakemake --cores 1 --configfile config.yaml

# All new videos will be processed automatically
```

### Reprocessing After Failure

If the workflow fails partway through, just run it again:

```bash
snakemake --cores 1 --configfile config.yaml
```

Snakemake will automatically:
- ✅ Skip files that are already processed
- ✅ Resume from where it left off
- ✅ Only process missing outputs

### Forcing a Rerun

To force reprocessing of all files:

```bash
snakemake --cores 1 --configfile config.yaml --forceall
```

Or to rerun from a specific step:

```bash
# Rerun only the describe step for all videos
snakemake --cores 1 --forcerun describe
```

## Customization

### Using Different Models

Edit `config.yaml`:

```yaml
# Transcription settings
transcribe:
  model: "mlx-community/whisper-large-v3-turbo"  # Fast and accurate

# Describe settings
describe:
  model: "mlx-community/Qwen3-VL-8B-Instruct-4bit"  # Or try other models
  max_pixels: 224
```

### Adjusting Preview Quality

Edit `config.yaml`:

```yaml
preview_settings:
  width: 1920        # Higher resolution (vs default 1280)
  crf: 18            # Better quality (vs default 23)
  preset: "slow"     # Better compression (vs default "medium")
```

### Parallel Processing

Process multiple videos at once:

```bash
# Use 4 CPU cores for parallel processing
snakemake --cores 4 --configfile config.yaml
```

**Note:** ML models (transcribe, describe) use significant memory. Don't use too many cores or you may run out of RAM.

## Troubleshooting

### "No videos found"

If the workflow finds no videos:

1. Check that your SD card is mounted:
   ```bash
   ls /Volumes/SDCARD  # macOS
   ls /media/username/SDCARD  # Linux
   ```

2. Check that `sd_card_path` in `config.yaml` is correct

3. Check that video files have supported extensions (`.mp4`, `.MP4`, `.mov`, `.MOV`)

### "ffmpeg not found"

Install ffmpeg:

```bash
brew install ffmpeg  # macOS
sudo apt-get install ffmpeg  # Ubuntu/Debian
```

### "mlx_whisper: command not found"

Install mlx-whisper:

```bash
pip install mlx-whisper
# or
uv add mlx-whisper
```

### Model download is slow

ML models are large (several GB). First run will be slow while downloading. Subsequent runs will use cached models.

To download models in advance:

```bash
# Download whisper model
mlx_whisper --model mlx-community/whisper-large-v3-turbo --help

# Download vision model (use Python)
python3 -c "from mlx_vlm import load; load('mlx-community/Qwen3-VL-8B-Instruct-4bit')"
```

## Next Steps

- Import JSON results into the database for web UI access
- Use results with DaVinci Resolve integration
- Customize prompts and models for your specific needs

See the full documentation at [docs/SNAKEMAKE_WORKFLOW.md](SNAKEMAKE_WORKFLOW.md)
