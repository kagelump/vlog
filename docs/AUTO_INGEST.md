# Auto-Ingest Feature

The auto-ingest feature provides automatic monitoring and processing of video files in a directory. When enabled, vlog will automatically detect new video files and run them through the complete ingestion pipeline using the Snakemake workflow.

**NEW: Batch Processing** - As of v0.1.0, auto-ingest now uses batch processing to significantly improve efficiency by loading the ML model once per batch instead of once per file.

## Overview

Auto-ingest eliminates the need to manually run ingestion scripts for each new video file. Once enabled, it:

1. **Monitors** a directory for new video files (`.mp4`, `.mov`, `.avi`, `.mkv`)
2. **Batches** multiple files together (configurable batch size and timeout)
3. **Invokes Snakemake** to preprocess files through transcription and subtitle cleaning
4. **Describes** all videos in the batch using a single ML model instance (via describe daemon)
5. **Imports** JSON results to the database
6. **Saves** all results to the database

## Key Features

### Batch Processing (NEW)

Auto-ingest now processes videos in **batches** for improved efficiency:

- **Configurable batch size**: Set how many files to accumulate before processing (default: 5)
- **Batch timeout**: Maximum time to wait for incomplete batches (default: 60 seconds)
- **Model loading efficiency**: ML model loaded once per batch instead of once per file
- **Parallel preprocessing**: Transcription and subtitle cleaning can run in parallel
- **Graceful shutdown**: Remaining queued files are processed before stopping

Benefits:
- **Faster processing**: Amortize model loading cost across multiple videos
- **Resource efficiency**: Less overhead from repeated model initialization
- **Better throughput**: Process multiple videos with minimal idle time

Configuration example:
```json
{
  "watch_directory": "/path/to/videos",
  "model_name": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
  "batch_size": 10,
  "batch_timeout": 120.0
}
```

### Idempotent Processing

The auto-ingest service is **idempotent** - it will not reprocess files that are already in the database. This means:

- You can safely restart the service without worrying about duplicate processing
- Existing files in the directory won't be reprocessed when you start auto-ingest
- Only new files (not in the database) will be processed

The idempotency check is performed using the `check_if_file_exists()` function, which queries the database before any processing begins.

### Snakemake Pipeline Integration

Auto-ingest now uses the **Snakemake workflow** to process each new video file. This provides:

- **Consistency**: Same processing pipeline as batch SD card ingestion
- **Robustness**: Snakemake's dependency tracking and error handling
- **Flexibility**: Easy to modify pipeline by editing the Snakefile

The pipeline runs for each new video:

1. **Transcription** (Snakemake `transcribe` rule)
   - Generates `.srt` subtitle files
   - Uses the whisper-large-v3-turbo model
   - Timeout managed by Snakemake

2. **Subtitle Cleaning** (Snakemake `clean_subtitles` rule)
   - Removes duplicate subtitle entries
   - Detects and removes ASR hallucinations
   - Creates `*_cleaned.srt` files

3. **Video Description** (Snakemake `describe` rule)
   - Analyzes video content using ML vision model
   - Extracts metadata (shot type, tags, timestamps, etc.)
   - Generates thumbnails
   - Outputs to JSON file

4. **Database Import** (auto-ingest service)
   - Reads JSON output from Snakemake
   - Inserts results into SQLite database
   - Maintains compatibility with existing tools

## Using Auto-Ingest

### Web Interface (Recommended)

1. **Start the web server:**
   ```bash
   cd /path/to/vlog
   ./scripts/launch_web.sh
   ```

2. **Open the launcher** in your browser: http://localhost:5432

3. **Set the working directory** to the folder containing your videos

4. **Click "Start Auto-Ingest"** in the Auto-Ingest section

5. **Monitor progress** in the console output

The UI will show:
- **Status indicator**: "Status: Off" (gray) or "Status: Running" (green)
- **Currently monitoring**: Shows which directory is being watched
- **Toggle button**: Changes between "Start Auto-Ingest" (green) and "Stop Auto-Ingest" (red)

### API Usage

You can also control auto-ingest programmatically using the REST API:

#### Get Status
```bash
curl http://localhost:5432/api/auto-ingest/status
```

Response:
```json
{
  "available": true,
  "is_running": false,
  "watch_directory": null,
  "model_name": null,
  "batch_size": null,
  "batch_timeout": null,
  "queued_files": 0,
  "processing_batch": false
}
```

Status fields:
- `available`: Whether auto-ingest dependencies are installed
- `is_running`: Whether the service is currently monitoring
- `watch_directory`: Directory being monitored (null if not running)
- `model_name`: ML model being used (null if not running)
- `batch_size`: Number of files per batch (null if not running)
- `batch_timeout`: Timeout for incomplete batches in seconds (null if not running)
- `queued_files`: Number of files currently in the batch queue
- `processing_batch`: Whether a batch is currently being processed

#### Start Auto-Ingest
```bash
curl -X POST http://localhost:5432/api/auto-ingest/start \
  -H "Content-Type: application/json" \
  -d '{
    "watch_directory": "/path/to/videos",
    "model_name": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
    "batch_size": 10,
    "batch_timeout": 120.0
  }'
```

Response:
```json
{
  "success": true,
  "message": "Auto-ingest started, monitoring: /path/to/videos (batch_size=10, timeout=120.0s)"
}
```

Parameters:
- `watch_directory` (required): Directory to monitor for new videos
- `model_name` (optional): ML model to use (default: Qwen3-VL-8B-Instruct-4bit)
- `batch_size` (optional): Number of files per batch (default: 5, minimum: 1)
- `batch_timeout` (optional): Seconds to wait for incomplete batch (default: 60.0, minimum: 1.0)

#### Stop Auto-Ingest
```bash
curl -X POST http://localhost:5432/api/auto-ingest/stop
```

Response:
```json
{
  "success": true,
  "message": "Auto-ingest stopped"
}
```

## Configuration

### Batch Configuration (NEW)

You can tune batch processing parameters for your workload:

#### Batch Size
- **What it does**: Number of files to accumulate before processing
- **Default**: 5 files
- **Minimum**: 1 file (effectively disables batching)
- **Recommendation**: 
  - Small batches (3-5): Lower latency, good for real-time processing
  - Large batches (10-20): Higher throughput, better for bulk imports

#### Batch Timeout
- **What it does**: Maximum time (in seconds) to wait for incomplete batches
- **Default**: 60 seconds
- **Minimum**: 1 second
- **Recommendation**:
  - Short timeout (30-60s): Faster processing of small batches
  - Long timeout (120-300s): Wait longer for larger batches

Example: For a camera that generates 3-5 videos per hour, use:
```json
{
  "batch_size": 3,
  "batch_timeout": 180.0
}
```

## Requirements

Auto-ingest requires the following dependencies:

- `flask>=3.1.2` - Web server
- `snakemake>=8.0.0` - Workflow management system (new requirement)
- `watchdog>=3.0.0` - File system monitoring
- `mlx-vlm>=0.3.5` - Vision language model
- `mlx-whisper` - Audio transcription (install separately)
- `ffmpeg` - Video processing (for preview creation if needed)

If any dependencies are missing, the auto-ingest feature will be unavailable and the API will return a 503 status.

## File System Monitoring

Auto-ingest uses the `watchdog` library to monitor file system events:

- **Events monitored**: File creation events
- **File types**: `.mp4`, `.mov`, `.avi`, `.mkv` (case-insensitive)
- **Debouncing**: 2-second delay after file creation to ensure files are fully written
- **Threading**: Processing happens in background threads to avoid blocking

## Troubleshooting

### Auto-Ingest Not Available

If the UI shows "Status: Unavailable" or API returns 503:

1. Check that all dependencies are installed:
   ```bash
   pip install flask watchdog mlx-vlm
   ```

2. Check the server logs for import errors

3. Verify mlx-vlm is properly installed and accessible

### Files Not Being Processed

1. **Check file extensions**: Only `.mp4`, `.mov`, `.avi`, `.mkv` are supported
2. **Check database**: Files already in the database won't be reprocessed
3. **Check directory**: Ensure the watch directory is correct
4. **Check logs**: Look at console output for error messages

### Processing Failures

If individual files fail to process:

1. **Check video file integrity**: Ensure videos aren't corrupted
2. **Check disk space**: Ensure enough space for temporary files
3. **Check timeouts**: Very long videos may timeout during transcription
4. **Check model availability**: Ensure the ML model can be loaded

## Performance Considerations

### Batch Processing Performance (NEW)

With batch processing enabled:

- **Model loading**: Once per batch (typically 30-60 seconds)
- **Preprocessing**: Can run in parallel for multiple files
- **Description**: Sequential within batch, but model stays loaded
- **Total time per file**: Reduced by 30-50% compared to sequential processing

Example timing for a batch of 5 videos:
- Without batching: 5 × (model load + process) = ~25-30 minutes
- With batching: 1 × model load + 5 × process = ~15-20 minutes

### Resource Usage

- **Memory usage**: The ML model is loaded once per batch and reused
- **Processing time**: Varies by video length and system performance
  - Transcription: ~1-5 minutes per video (can run in parallel)
  - Subtitle cleaning: ~1-10 seconds per video (can run in parallel)
  - Description: ~2-5 minutes per video (sequential, but model loaded once)
  - Model loading overhead: ~30-60 seconds per batch (amortized)
- **Concurrent processing**: Preprocessing stages can run in parallel; description is sequential
- **Resource usage**: CPU/GPU intensive during ML inference

### Throughput Recommendations

- **Real-time monitoring**: batch_size=3-5, batch_timeout=60s
- **Bulk import**: batch_size=10-20, batch_timeout=300s
- **Single file mode**: batch_size=1, batch_timeout=1s (legacy behavior)

## Best Practices

1. **Start small**: Test with a few videos before enabling for large directories
2. **Monitor logs**: Watch the console output for errors or issues
3. **Disk space**: Ensure adequate space for subtitle files and database
4. **Stop when done**: Stop auto-ingest when not actively adding videos to save resources
5. **Database backups**: Regularly backup `video_results.db`

## Technical Details

### Architecture

```
VideoFileHandler (watchdog.events.FileSystemEventHandler)
    ↓
AutoIngestService
    ↓
    ├─> _process_video_file() → Add to batch queue
    │
    ├─> _on_batch_timeout() OR batch full → _process_batch()
    │       ↓
    │       └─> _process_batch_worker() (background thread)
    │               ↓
    │               ├─> _run_batch_preprocessing() → Snakemake (per file)
    │               │       ↓
    │               │       ├─> rule transcribe → mlx_whisper
    │               │       └─> rule clean_subtitles → srt_cleaner
    │               │
    │               ├─> _run_batch_describe() → describe_daemon (batch)
    │               │       ↓
    │               │       ├─> Start daemon (load model ONCE)
    │               │       ├─> Process all videos (model stays loaded)
    │               │       └─> Stop daemon
    │               │
    │               └─> _import_json_to_database() → database (per file)
```

### Batch Processing Implementation (NEW)

```python
def _process_video_file(self, file_path: str) -> None:
    filename = os.path.basename(file_path)
    
    # Idempotency check
    if check_if_file_exists(filename):
        logger.info(f"File already processed, skipping: {filename}")
        return
    
    # Add to batch queue
    with self._batch_lock:
        self._batch_queue.append(file_path)
        
        # Process batch if full
        if len(self._batch_queue) >= self.batch_size:
            self._process_batch()
        else:
            # Start timeout timer for incomplete batch
            self._batch_timer = threading.Timer(self.batch_timeout, self._on_batch_timeout)
            self._batch_timer.start()

def _process_batch_worker(self, batch_files: list[str]) -> None:
    # Step 1: Preprocess files (transcribe, clean_subtitles)
    preprocessed_files = self._run_batch_preprocessing(batch_files)
    
    # Step 2: Describe all videos using daemon (model loaded once)
    described_files = self._run_batch_describe(preprocessed_files)
    
    # Step 3: Import results to database
    for json_path in described_files:
        self._import_json_to_database(json_path)
```

### Snakemake Integration

For batch processing, auto-ingest runs Snakemake in two stages:

**Stage 1: Preprocessing (per file)**
```python
# Target: cleaned subtitle file (stops before describe)
subtitle_target = f"{video_dir}/{stem}_cleaned.srt"

config = {
    'sd_card_path': str(video_dir),
    'main_folder': str(video_dir),
    'preview_folder': str(video_dir),
    'video_extensions': [extension],
    'transcribe': {'model': 'mlx-community/whisper-large-v3-turbo'},
}
```

**Stage 2: Description (batch via daemon)**
```python
# Start daemon (loads model once)
daemon_manager = DaemonManager(model=self.model_name)
daemon_manager.start_daemon()

# Describe all videos in batch
for video_path in batch_files:
    description = daemon_manager.describe_video(video_path)
    # Save to JSON

# Stop daemon
daemon_manager.stop_daemon()
```

### Database Integration

Results are loaded from JSON and saved using the standard `insert_result()` function, which stores:
- Video metadata (length, timestamp, filename)
- Classification results (description, shot type, tags, rating)
- Timing information (in/out timestamps, segments)
- Thumbnails (base64-encoded)

## See Also

- [Main README](../README.md) - General project documentation
- [Snakemake Workflow](SNAKEMAKE_WORKFLOW.md) - Detailed Snakemake pipeline documentation
- [DaVinci Integration](DAVINCI_INTEGRATION.md) - Using results with DaVinci Resolve
