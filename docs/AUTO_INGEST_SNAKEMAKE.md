# Auto-Ingest with Snakemake

The Snakemake-based auto-ingest feature provides automatic monitoring and processing of video files using the complete Snakemake ingestion pipeline with real-time progress tracking.

## Overview

This is the **new and recommended** approach for auto-ingesting video files. Unlike the legacy auto-ingest which runs a partial pipeline, this version:

1. **Monitors** a directory for new video files (`.mp4`, `.mov`, `.avi`, `.mkv`)
2. **Invokes the full Snakemake pipeline** for each new file:
   - Stage 1: Copy videos (if needed)
   - Stage 2: Transcribe audio and clean subtitles
   - Stage 3: Describe videos using ML model
3. **Tracks progress** via the Snakemake logger plugin API
4. **Displays real-time status** in the UI with per-stage breakdown
5. **Queues files** for batch processing

## Key Features

### Full Snakemake Pipeline Integration

- **Complete workflow**: Runs all 3 stages of the Snakemake pipeline
- **Consistent processing**: Same logic as manual SD card ingestion
- **Robust error handling**: Snakemake's dependency tracking and recovery
- **Configurable resources**: Control CPU cores and memory usage

### Real-Time Progress Tracking

The service integrates with the Snakemake logger plugin to provide:

- **Per-rule progress**: See completion status for each stage (transcribe, clean_subtitles, describe)
- **Job counts**: Total, pending, running, completed, and failed jobs
- **Live updates**: Progress updates every second via REST API
- **Visual indicators**: Progress bars in the UI showing percentage completion

### Flexible Configuration

- **Watch directory**: Main folder to monitor (also used as output folder)
- **Preview folder**: Optional separate folder for preview files (defaults to watch directory)
- **Model selection**: Choose which ML model to use for video description
- **Resource limits**: Configure CPU cores and memory for Snakemake
- **Logger integration**: Connects to Snakemake logger plugin on configurable port

## Using the Web Interface

### Starting Auto-Ingest

1. **Open the launcher** at http://localhost:5432

2. **Set your working directory**:
   - Enter the path or use the "Browse..." button
   - Click "Set Directory" to confirm

3. **Configure the Auto-Ingest with Snakemake section**:
   - **Preview Folder** (optional): Leave empty to use working directory, or specify a separate folder
   - **Cores**: Number of CPU cores for Snakemake (default: 8)
   - **Memory (GB)**: Memory limit for the pipeline (default: 12)
   - **Model**: ML model for video description (inherited from main configuration)

4. **Click "Start Auto-Ingest"** in the Snakemake section (marked with "NEW" badge)

5. **Monitor progress**:
   - Watch the status indicator (changes to green "Running")
   - View the "Pipeline Progress" section for real-time updates
   - See per-rule breakdown with progress bars

### Stopping Auto-Ingest

- Click "Stop Auto-Ingest" button
- The service will gracefully stop the running Snakemake process
- Any queued files will be processed before shutdown

## Using the REST API

### Start Auto-Ingest

```bash
curl -X POST http://localhost:5432/api/auto-ingest-snakemake/start \
  -H "Content-Type: application/json" \
  -d '{
    "watch_directory": "/path/to/videos",
    "preview_folder": "/path/to/previews",
    "model_name": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
    "cores": 8,
    "resources_mem_gb": 12
  }'
```

**Parameters:**
- `watch_directory` (required): Directory to monitor
- `preview_folder` (optional): Separate preview folder. If omitted, uses watch_directory
- `model_name` (optional): ML model name. Default: `mlx-community/Qwen3-VL-8B-Instruct-4bit`
- `cores` (optional): Number of CPU cores. Default: 8
- `resources_mem_gb` (optional): Memory limit in GB. Default: 12

**Response:**
```json
{
  "success": true,
  "message": "Auto-ingest Snakemake started, monitoring: /path/to/videos (cores=8, mem=12GB)"
}
```

### Get Status

```bash
curl http://localhost:5432/api/auto-ingest-snakemake/status
```

**Response:**
```json
{
  "available": true,
  "is_running": true,
  "watch_directory": "/path/to/videos",
  "preview_folder": "/path/to/previews",
  "model_name": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
  "cores": 8,
  "resources_mem_gb": 12,
  "queued_files": 2,
  "is_processing": true,
  "logger_port": 5556
}
```

**Fields:**
- `available`: Whether the service is available (dependencies installed)
- `is_running`: Whether monitoring is active
- `watch_directory`: Directory being monitored
- `preview_folder`: Preview folder being used
- `model_name`: ML model being used
- `cores`: CPU cores allocated
- `resources_mem_gb`: Memory limit in GB
- `queued_files`: Number of files waiting to be processed
- `is_processing`: Whether Snakemake is currently running
- `logger_port`: Port for the Snakemake logger plugin API

### Get Progress

```bash
curl http://localhost:5432/api/auto-ingest-snakemake/progress
```

**Response:**
```json
{
  "total_jobs": 15,
  "completed_jobs": 8,
  "failed_jobs": 0,
  "running_jobs": 2,
  "pending_jobs": 5,
  "rules": {
    "transcribe": {
      "total": 5,
      "pending": 1,
      "running": 1,
      "completed": 3,
      "failed": 0
    },
    "clean_subtitles": {
      "total": 5,
      "pending": 2,
      "running": 0,
      "completed": 3,
      "failed": 0
    },
    "describe": {
      "total": 5,
      "pending": 2,
      "running": 1,
      "completed": 2,
      "failed": 0
    }
  }
}
```

**Note:** Progress data comes from the Snakemake logger plugin. If the logger plugin is not running or unreachable, the response will include `"available": false`.

### Stop Auto-Ingest

```bash
curl -X POST http://localhost:5432/api/auto-ingest-snakemake/stop
```

**Response:**
```json
{
  "success": true,
  "message": "Auto-ingest Snakemake service stopped"
}
```

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│  FileSystemEventHandler (watchdog)      │
│  - Monitors directory for new files     │
└──────────────┬──────────────────────────┘
               │ New video file detected
               ▼
┌─────────────────────────────────────────┐
│  AutoIngestSnakemakeService             │
│  - Manages file queue                   │
│  - Starts Snakemake processes           │
└──────────────┬──────────────────────────┘
               │ Runs Snakemake command
               ▼
┌─────────────────────────────────────────┐
│  Snakemake Workflow                     │
│  - Stage 1: Copy (if needed)            │
│  - Stage 2: Transcribe & Clean          │
│  - Stage 3: Describe via daemon         │
└──────────────┬──────────────────────────┘
               │ Reports progress to
               ▼
┌─────────────────────────────────────────┐
│  Snakemake Logger Plugin                │
│  - Tracks job lifecycle events          │
│  - Exposes REST API on port 5556        │
└──────────────┬──────────────────────────┘
               │ Queried by
               ▼
┌─────────────────────────────────────────┐
│  Launcher UI / API Clients              │
│  - Displays real-time progress          │
│  - Shows per-rule breakdown             │
└─────────────────────────────────────────┘
```

### File Processing Flow

1. **File Detection**: watchdog detects new video file
2. **Queue Addition**: File added to internal queue
3. **Snakemake Invocation**: Background thread starts Snakemake workflow
4. **Config Generation**: Temporary YAML config created with all settings
5. **Pipeline Execution**: Snakemake runs all 3 stages:
   - Copy videos to main/preview folders
   - Transcribe audio to SRT subtitles
   - Clean subtitles (remove duplicates/hallucinations)
   - Describe videos using ML model via daemon
6. **Progress Tracking**: Logger plugin captures job events
7. **Status Updates**: UI polls progress API every second
8. **Completion**: Results saved to database, JSON files created

## Configuration

### Snakemake Command

The service builds a Snakemake command similar to:

```bash
snakemake \
  --snakefile src/vlog/workflows/Snakefile \
  --configfile /tmp/config_XXXXX.yaml \
  --config preview_folder=/path/to/previews \
  --logger vlog \
  --cores=8 \
  --resources mem_gb=12
```

### Generated Config File

The service creates a temporary YAML configuration:

```yaml
sd_card_path: /path/to/videos
main_folder: /path/to/videos
preview_folder: /path/to/previews
video_extensions: [mp4, MP4, mov, MOV, avi, AVI, mkv, MKV]
preview_suffix: _preview
preview_extension: mp4
preview_settings:
  width: 1280
  crf: 23
  preset: medium
transcribe:
  model: mlx-community/whisper-large-v3-turbo
  format: srt
  task: transcribe
describe:
  model: mlx-community/Qwen3-VL-8B-Instruct-4bit
  max_pixels: 224
  fps: 1.0
daemon_host: 127.0.0.1
daemon_port: 5555
daemon_signal_file: status/daemon_running.signal
daemon_pid_file: status/daemon.pid
daemon_log_file: logs/daemon.log
```

## Requirements

### Dependencies

- **Python 3.11+**
- **Flask** - Web server for API
- **watchdog** - File system monitoring
- **Snakemake** - Workflow management
- **requests** - HTTP client for logger plugin API
- **PyYAML** - Configuration file parsing
- **MLX-VLM** - Vision language model (for describe stage)
- **mlx_whisper** - Audio transcription (for transcribe stage)

### Snakemake Logger Plugin

The logger plugin must be installed and configured:

```bash
# Logger plugin is included in the vlog package
# Starts automatically when Snakemake runs with --logger vlog
```

The logger plugin API runs on port 5556 by default. You can query it directly:

```bash
# Check logger status
curl http://127.0.0.1:5556/status

# Health check
curl http://127.0.0.1:5556/health

# Reset status
curl -X POST http://127.0.0.1:5556/reset
```

## Troubleshooting

### Service Not Starting

**Symptom**: "Failed to start auto-ingest Snakemake service"

**Solutions:**
1. Check that the watch directory exists
2. Verify you have write permissions to the directory
3. Ensure Snakemake is installed: `uv run -- snakemake --version`
4. Check server logs for detailed error messages

### No Progress Updates

**Symptom**: Progress section remains empty or shows "Logger API unavailable"

**Solutions:**
1. Verify logger plugin is running: `curl http://127.0.0.1:5556/health`
2. Check Snakemake is using the logger: `--logger vlog` in command
3. Ensure port 5556 is not blocked by firewall
4. Look for logger plugin startup in Snakemake output

### Files Not Being Processed

**Symptom**: New files detected but Snakemake doesn't run

**Solutions:**
1. Check the "queued_files" count in status API
2. Verify Snakefile exists at `src/vlog/workflows/Snakefile`
3. Check for errors in the Snakemake output (logged to console)
4. Ensure the file has a supported video extension (mp4, mov, avi, mkv)

### Processing Failures

**Symptom**: Jobs shown as "failed" in progress

**Solutions:**
1. Check video file integrity
2. Verify sufficient disk space
3. Review Snakemake error messages
4. Check ML model availability
5. Ensure FFmpeg is installed (for preview creation)

## Performance Considerations

### Resource Usage

- **CPU**: Snakemake can parallelize jobs up to `cores` limit
- **Memory**: ML model loading requires significant RAM (8-16GB recommended)
- **Disk I/O**: Transcription and preview generation are I/O intensive
- **Network**: Model downloads on first run (can be several GB)

### Processing Time

Approximate times per video (varies by length and hardware):

- **Transcription**: 1-5 minutes (can run in parallel)
- **Subtitle cleaning**: 1-10 seconds (fast)
- **Description**: 2-5 minutes (ML model inference)
- **Total per file**: ~5-15 minutes depending on video length

### Recommendations

- **For real-time processing**: Use 8+ cores, 16GB+ RAM
- **For background processing**: Use 4+ cores, 12GB+ RAM
- **For batch imports**: Increase `cores` to maximize parallelism
- **For memory-constrained systems**: Reduce `resources_mem_gb` and `cores`

## Comparison with Legacy Auto-Ingest

| Feature | Legacy Auto-Ingest | Snakemake Auto-Ingest |
|---------|-------------------|----------------------|
| Pipeline Coverage | Partial (transcribe → describe) | Complete (all 3 stages) |
| Progress Tracking | Basic (queued files count) | Detailed (per-rule breakdown) |
| Resource Control | Fixed | Configurable (cores, memory) |
| Preview Handling | Uses existing previews | Can create previews |
| Batch Processing | Yes (with daemon) | Yes (via Snakemake parallelism) |
| Error Recovery | Manual | Snakemake dependency tracking |
| Configuration | Limited | Full Snakemake config |
| UI Feedback | Status text only | Progress bars + percentages |

**Recommendation**: Use Snakemake Auto-Ingest for all workflows - it provides the complete pipeline with real-time progress tracking.

## See Also

- [Snakemake Workflow](SNAKEMAKE_WORKFLOW.md) - Detailed pipeline documentation
- [Status Logger Plugin](STATUS_LOGGER.md) - Logger plugin details
- [Main README](../README.md) - General project documentation
