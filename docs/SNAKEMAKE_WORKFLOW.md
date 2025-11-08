# Snakemake Video Ingestion Workflow

This document describes the Snakemake-based video ingestion workflow for processing videos from an SD card.

## Overview

The Snakemake workflow automates the complete video ingestion pipeline:

1. **Copy main file** - Copies the full-resolution video from SD card to a main storage folder
2. **Copy or create preview** - Copies preview file if it exists on the SD card, or creates one using ffmpeg
3. **Transcribe** - Generates subtitles for the preview file using mlx_whisper
4. **Clean subtitles** - Removes duplicate and hallucinated subtitle entries
5. **Describe** - Analyzes the preview video and saves results to JSON

## Prerequisites

### Software Requirements

- Python 3.11+
- Snakemake 8.0+
- ffmpeg (for preview file creation)
- mlx_whisper (for transcription)
- mlx-vlm (for video description)

### Installation

1. Install dependencies using uv:
   ```bash
   cd /path/to/vlog
   uv add snakemake
   uv sync
   ```

2. Or using pip:
   ```bash
   pip install snakemake>=8.0.0
   ```

3. Ensure ffmpeg is installed:
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   ```

## Configuration

Edit `config.yaml` to configure the workflow:

```yaml
# SD Card mount point
sd_card_path: "/Volumes/SDCARD"

# Output directories
main_folder: "videos/main"
preview_folder: "videos/preview"

# Video file extensions to process
video_extensions:
  - "mp4"
  - "MP4"
  - "mov"
  - "MOV"

# Preview file settings
preview_suffix: "_preview"
preview_extension: "mp4"

# FFmpeg settings for preview generation
preview_settings:
  width: 1280
  vcodec: "libx264"
  crf: 23
  preset: "medium"

# Transcription settings
transcribe:
  model: "mlx-community/whisper-large-v3-turbo"
  format: "srt"
  task: "transcribe"

# Describe settings
describe:
  model: "mlx-community/Qwen3-VL-8B-Instruct-4bit"
  max_pixels: 224
```

## Usage

### Basic Usage

1. **Mount your SD card** and note the mount path (e.g., `/Volumes/SDCARD`)

2. **Update config.yaml** with your SD card path:
   ```yaml
   sd_card_path: "/Volumes/SDCARD"
   ```

3. **Run the workflow**:
   ```bash
   cd /path/to/vlog
   snakemake --cores 1 --configfile config.yaml
   ```

### Advanced Usage

#### Dry Run (Preview)

See what will be executed without actually running:

```bash
snakemake --cores 1 --configfile config.yaml --dry-run
```

#### Visualize Workflow

Generate a workflow diagram:

```bash
snakemake --dag | dot -Tpdf > workflow.pdf
```

#### Custom Configuration

Override config values from the command line:

```bash
snakemake --cores 1 --config sd_card_path=/Volumes/MYCARD main_folder=output/main
```

#### Process Specific Videos

Process only specific videos by providing target files:

```bash
snakemake --cores 1 videos/preview/myvideo.json
```

#### Parallel Processing

Use multiple cores for parallel processing:

```bash
snakemake --cores 4 --configfile config.yaml
```

## Workflow Details

### Rule: copy_main

Copies the main video file from the SD card to the main folder.

**Input:** Video file on SD card  
**Output:** `{main_folder}/{stem}.mp4`

### Rule: copy_or_create_preview

Copies the preview file if it exists on the SD card, otherwise creates a lower-resolution preview using ffmpeg.

**Input:** `{main_folder}/{stem}.mp4`  
**Output:** `{preview_folder}/{stem}.mp4`

Preview files are created with:
- Resolution: 1280px width (height auto-scaled)
- Codec: H.264
- CRF: 23 (constant quality)
- Audio: AAC @ 128kbps

### Rule: transcribe

Generates subtitles for the preview file using mlx_whisper.

**Input:** `{preview_folder}/{stem}.mp4`  
**Output:** `{preview_folder}/{stem}.srt`

Uses the whisper-large-v3-turbo model by default.

### Rule: clean_subtitles

Removes duplicate subtitle entries and ASR hallucinations.

**Input:** `{preview_folder}/{stem}.srt`  
**Output:** `{preview_folder}/{stem}_cleaned.srt`

Cleaning process:
- Removes consecutive duplicate subtitle text
- Detects and removes repetitive hallucinations
- Re-indexes subtitles sequentially

### Rule: describe

Analyzes the video content and saves results to JSON.

**Input:**
- Video: `{preview_folder}/{stem}.mp4`
- Subtitles: `{preview_folder}/{stem}_cleaned.srt`

**Output:** `{preview_folder}/{stem}.json`

Output JSON contains:
```json
{
  "filename": "video.mp4",
  "video_description_long": "...",
  "video_description_short": "...",
  "primary_shot_type": "pov|insert|establishing",
  "tags": ["static", "dynamic", "closeup", "medium", "wide"],
  "classification_time_seconds": 123.45,
  "classification_model": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
  "video_length_seconds": 60.5,
  "video_timestamp": "2024-01-01T12:00:00",
  "video_thumbnail_base64": "...",
  "rating": 0.8,
  "segments": [...]
}
```

## File Organization

After running the workflow, your files will be organized as follows:

```
videos/
├── main/
│   └── video1.mp4           # Full-resolution main file
└── preview/
    ├── video1.mp4           # Preview file (copied or created)
    ├── video1.srt           # Original subtitles
    ├── video1_cleaned.srt   # Cleaned subtitles
    └── video1.json          # Description results
```

## SD Card File Structure

The workflow expects videos on the SD card to be organized as:

```
/Volumes/SDCARD/
├── video1.mp4              # Main file
├── video1_preview.mp4      # Optional preview file
├── video2.mp4
└── video2_preview.mp4
```

If a preview file (with `_preview` suffix) exists, it will be copied. Otherwise, a preview will be created from the main file.

## Troubleshooting

### SD Card Not Found

**Error:** `Error: SD card path does not exist`

**Solution:** 
- Verify the SD card is mounted
- Update `sd_card_path` in `config.yaml`
- Check mount point with `df -h` or `mount`

### ffmpeg Not Found

**Error:** `Error: ffmpeg not found`

**Solution:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

### mlx_whisper Not Found

**Error:** `mlx_whisper: command not found`

**Solution:**
```bash
# Install mlx-whisper
pip install mlx-whisper
```

### Model Download Issues

If models fail to download, ensure you have:
- Stable internet connection
- Sufficient disk space (models can be several GB)
- Access to Hugging Face (check firewall/proxy settings)

### Preview Creation Fails

If preview creation fails, check:
- Input video file is valid and not corrupted
- Sufficient disk space for output
- ffmpeg is properly installed
- Check ffmpeg error messages in the log

## Performance Considerations

- **Processing time:** Varies by video length and hardware
  - Transcription: ~1-5 minutes per video
  - Preview creation: ~30 seconds - 2 minutes
  - Description: ~2-5 minutes per video

- **Disk space:** Ensure adequate space for:
  - Main videos (original size)
  - Preview videos (~30-50% of main file size)
  - Subtitle files (~1-5 MB each)
  - JSON outputs (~50-200 KB each)

- **Memory:** ML models require significant RAM:
  - Whisper: ~2-4 GB
  - Vision model: ~4-8 GB

## Integration with Existing Tools

### Database Import

To import JSON results into the database:

```python
import json
from vlog.db import insert_result, initialize_db

initialize_db()

with open('videos/preview/video1.json', 'r') as f:
    data = json.load(f)
    insert_result(data)
```

### DaVinci Resolve Integration

JSON outputs are compatible with the DaVinci Resolve importer. Simply point the importer to the preview folder containing JSON files.

## See Also

- [Main README](../README.md) - General project documentation
- [Auto-Ingest Documentation](AUTO_INGEST_SNAKEMAKE.md) - Automatic video ingestion
- [DaVinci Integration](DAVINCI_INTEGRATION.md) - Using results with DaVinci Resolve
