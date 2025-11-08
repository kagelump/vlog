# Staged Workflow Guide

The vlog ingestion pipeline has been split into 3 independent stages for better control and debugging.

## Overview

The pipeline consists of 3 stages:

1. **Stage 1: Copy** - Copy videos from SD card and create/copy previews
2. **Stage 2: Subtitles** - Generate and clean subtitles
3. **Stage 3: Describe** - Describe videos using ML model

Each stage can be run independently or all together using the master workflow.

## File Structure

```
src/vlog/workflows/
├── Snakefile              # Master workflow (runs all 3 stages)
├── Snakefile.copy         # Stage 1: Copy videos
├── Snakefile.subtitles    # Stage 2: Generate subtitles
├── Snakefile.describe     # Stage 3: Describe videos
├── discover_videos.py     # Helper: Find videos on SD card
├── create_preview.py      # Helper: Create preview videos
└── describe_to_json.py    # Helper: Describe video via daemon
```

## Running the Workflows

### Option 1: Run All Stages Together

Use the master Snakefile to run the complete pipeline:

```bash
# Run all stages
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml

# Or use make target
make snakemake
```

You can also run specific stage targets from the master file:

```bash
# Run only stage 1
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml stage1

# Run only stage 2
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml stage2

# Run only stage 3
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml stage3
```

### Option 2: Run Stages Independently

Run each stage file individually for maximum control:

#### Stage 1: Copy Videos

```bash
snakemake --snakefile src/vlog/workflows/Snakefile.copy --cores 1 --configfile config.yaml
```

**What it does:**
- Discovers videos on SD card (or local directory)
- Copies main video files to `videos/main/`
- Copies or creates preview files in `videos/preview/`

**Output:**
- `videos/main/*.mp4` - Main video files
- `videos/preview/*_preview.mp4` - Preview files (lower resolution)

#### Stage 2: Generate Subtitles

```bash
snakemake --snakefile src/vlog/workflows/Snakefile.subtitles --cores 1 --configfile config.yaml
```

**What it does:**
- Discovers existing preview videos
- Transcribes each video using `mlx_whisper`
- Cleans subtitle files (removes duplicates and hallucinations)

**Output:**
- `videos/preview/*_preview.srt` - Raw subtitle files
- `videos/preview/*_preview_cleaned.srt` - Cleaned subtitle files

**Requirements:**
- Stage 1 must be completed first (preview files must exist)

#### Stage 3: Describe Videos

```bash
snakemake --snakefile src/vlog/workflows/Snakefile.describe --cores 1 --configfile config.yaml
```

**What it does:**
- Discovers videos with cleaned subtitles
- Describes each video using the ML model via daemon
- Saves results to JSON files

**Output:**
- `videos/preview/*_preview.json` - Video description JSON files

**Requirements:**
- Stage 1 and 2 must be completed first
- Describe daemon must be running (or use `--config manage_daemon=true`)

## Daemon Management

The describe stage requires a running describe daemon. You have two options:

### Option 1: Manual Daemon Management (Recommended)

Start the daemon manually before running stage 3:

```bash
# Start daemon
python -m vlog.describe_daemon --model mlx-community/Qwen3-VL-8B-Instruct-4bit &

# Run stage 3
snakemake --snakefile src/vlog/workflows/Snakefile.describe --cores 1 --configfile config.yaml

# Stop daemon when done
pkill -f describe_daemon
```

### Option 2: Automatic Daemon Management

Let the workflow manage the daemon lifecycle:

```bash
snakemake --snakefile src/vlog/workflows/Snakefile.describe \
    --cores 1 \
    --configfile config.yaml \
    --config manage_daemon=true
```

**Note:** Automatic daemon management starts/stops the daemon for each Snakemake run, which may be inefficient if running multiple times.

## Configuration

All stages use the same `config.yaml` file. Key settings:

```yaml
# Source and destination
sd_card_path: "/Volumes/SDCARD"
main_folder: "videos/main"
preview_folder: "videos/preview"

# Preview generation
preview_settings:
  width: 1280
  crf: 23
  preset: "medium"

# Transcription
transcribe:
  model: "mlx-community/whisper-large-v3-turbo"

# Description
describe:
  model: "mlx-community/Qwen3-VL-8B-Instruct-4bit"
  max_pixels: 224
  fps: 1.0

# Daemon settings
daemon_host: "127.0.0.1"
daemon_port: 5555
```

## Workflow Dependencies

```
Stage 1 (Copy)
    ↓
    Creates: videos/preview/*_preview.mp4
    ↓
Stage 2 (Subtitles)
    ↓
    Creates: videos/preview/*_preview_cleaned.srt
    ↓
Stage 3 (Describe)
    ↓
    Creates: videos/preview/*_preview.json
```

## Use Cases

### Scenario 1: Process Everything at Once

You have videos on an SD card and want to process them completely:

```bash
# Run all stages
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml
```

### Scenario 2: Staged Processing

You want to copy videos first, then process subtitles later:

```bash
# Day 1: Copy videos
snakemake --snakefile src/vlog/workflows/Snakefile.copy --cores 1 --configfile config.yaml

# Day 2: Generate subtitles
snakemake --snakefile src/vlog/workflows/Snakefile.subtitles --cores 1 --configfile config.yaml

# Day 3: Describe videos
python -m vlog.describe_daemon --model mlx-community/Qwen3-VL-8B-Instruct-4bit &
snakemake --snakefile src/vlog/workflows/Snakefile.describe --cores 1 --configfile config.yaml
```

### Scenario 3: Re-describe with Different Model

You already have videos and subtitles, but want to re-describe with a different model:

```bash
# Start daemon with new model
python -m vlog.describe_daemon --model mlx-community/different-model &

# Re-run describe stage (will skip copy and subtitle steps)
snakemake --snakefile src/vlog/workflows/Snakefile.describe \
    --cores 1 \
    --configfile config.yaml \
    --config describe.model=mlx-community/different-model \
    --forceall  # Force re-running even if JSON files exist
```

### Scenario 4: Process New Videos

You have new videos on the SD card and want to process only the new ones:

```bash
# Run all stages - Snakemake will automatically detect and process only new files
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml
```

## Debugging

### Check What Will Run

Use `--dry-run` to see what Snakemake will do:

```bash
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml --dry-run
```

### Force Re-run

Force re-running all rules even if outputs exist:

```bash
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml --forceall
```

### Force Specific Rule

Force re-running a specific rule:

```bash
snakemake --snakefile src/vlog/workflows/Snakefile.describe \
    --cores 1 \
    --configfile config.yaml \
    --forcerun describe
```

### Check Daemon Status

```bash
# Check if daemon is running
curl http://127.0.0.1:5555/health

# Check daemon model
curl http://127.0.0.1:5555/model
```

## Advantages of Staged Workflow

1. **Better Control** - Run only the stages you need
2. **Faster Iteration** - Re-run only changed stages during development
3. **Easier Debugging** - Isolate problems to specific stages
4. **Resource Management** - Start daemon once for multiple describe runs
5. **Flexibility** - Mix and match processing based on needs

## Migration from Original Workflow

The original monolithic Snakefile has been replaced with the master workflow. Usage is mostly the same:

**Old:**
```bash
snakemake --cores 1 --configfile config.yaml
```

**New (equivalent):**
```bash
snakemake --snakefile src/vlog/workflows/Snakefile --cores 1 --configfile config.yaml
```

The master workflow includes all the same rules and produces the same outputs, just organized into 3 logical stages.
