# Auto-Ingest Feature

The auto-ingest feature provides automatic monitoring and processing of video files in a directory. When enabled, vlog will automatically detect new video files and run them through the complete ingestion pipeline.

## Overview

Auto-ingest eliminates the need to manually run ingestion scripts for each new video file. Once enabled, it:

1. **Monitors** a directory for new video files (`.mp4`, `.mov`, `.avi`, `.mkv`)
2. **Transcribes** videos using mlx_whisper
3. **Cleans** subtitles to remove duplicates and hallucinations
4. **Describes** videos using the ML vision model
5. **Saves** all results to the database

## Key Features

### Idempotent Processing

The auto-ingest service is **idempotent** - it will not reprocess files that are already in the database. This means:

- You can safely restart the service without worrying about duplicate processing
- Existing files in the directory won't be reprocessed when you start auto-ingest
- Only new files (not in the database) will be processed

The idempotency check is performed using the `check_if_file_exists()` function, which queries the database before any processing begins.

### Complete Pipeline Integration

Auto-ingest runs the full ingestion pipeline for each new video:

1. **Transcription** (`mlx_whisper`)
   - Generates `.srt` subtitle files
   - Uses the whisper-large-v3-turbo model
   - 10-minute timeout per video

2. **Subtitle Cleaning** (`srt_cleaner.py`)
   - Removes duplicate subtitle entries
   - Detects and removes ASR hallucinations
   - Creates `*_cleaned.srt` files

3. **Video Description** (`describe.py`)
   - Analyzes video content using ML vision model
   - Extracts metadata (shot type, tags, timestamps, etc.)
   - Generates thumbnails
   - Saves results to database

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
  "model_name": null
}
```

#### Start Auto-Ingest
```bash
curl -X POST http://localhost:5432/api/auto-ingest/start \
  -H "Content-Type: application/json" \
  -d '{
    "watch_directory": "/path/to/videos",
    "model_name": "mlx-community/Qwen3-VL-8B-Instruct-4bit"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Auto-ingest started, monitoring: /path/to/videos"
}
```

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

### Model Selection

By default, auto-ingest uses `mlx-community/Qwen3-VL-8B-Instruct-4bit`. You can specify a different model when starting:

- Via UI: Change the "Model" field before clicking "Start Auto-Ingest"
- Via API: Set the `model_name` parameter in the start request

### FPS Adjustment

Auto-ingest automatically adjusts the frame sampling rate based on video length:
- Videos < 120s: 1.0 FPS
- Videos 120-300s: 0.5 FPS
- Videos > 300s: 0.25 FPS

This optimization reduces processing time for longer videos while maintaining quality.

## Requirements

Auto-ingest requires the following dependencies:

- `flask>=3.1.2` - Web server
- `watchdog>=3.0.0` - File system monitoring
- `mlx-vlm>=0.3.5` - Vision language model
- `mlx-whisper` - Audio transcription (install separately)

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

- **Memory usage**: The ML model is loaded once and reused for all files
- **Processing time**: Varies by video length and system performance
  - Transcription: ~1-5 minutes per video
  - Subtitle cleaning: ~1-10 seconds
  - Description: ~2-5 minutes per video
- **Concurrent processing**: One file at a time (sequential processing)
- **Resource usage**: CPU/GPU intensive during ML inference

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
    ├─> _transcribe_video() → mlx_whisper
    ├─> _clean_subtitles() → srt_cleaner
    └─> _describe_and_save() → describe.py → database
```

### Idempotency Implementation

```python
def _process_video_file(self, file_path: str) -> None:
    filename = os.path.basename(file_path)
    
    # Idempotency check
    if check_if_file_exists(filename):
        logger.info(f"File already processed, skipping: {filename}")
        return
    
    # Process only if not in database
    self._transcribe_video(file_path)
    self._clean_subtitles(srt_path)
    self._describe_and_save(file_path, cleaned_srt_path)
```

### Database Integration

Results are saved using the standard `insert_result()` function, which stores:
- Video metadata (length, timestamp, filename)
- Classification results (description, shot type, tags, rating)
- Timing information (in/out timestamps, segments)
- Thumbnails (base64-encoded)

## See Also

- [Main README](../README.md) - General project documentation
- [DaVinci Integration](DAVINCI_INTEGRATION.md) - Using results with DaVinci Resolve
