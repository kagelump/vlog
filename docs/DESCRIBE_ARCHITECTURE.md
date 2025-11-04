# Video Description Architecture

The video description functionality has been split into three main components for better modularity and reusability.

## Components

### 1. `describe_lib.py` - Core Library
The business logic for video description using MLX-VLM.

**Key functions:**
- `describe_video()` - Describe a single video using the MLX-VLM model
- `load_model()` - Load the MLX-VLM model and processor
- `calculate_adaptive_fps()` - Adjust FPS based on video length
- `load_prompt_template()` - Load prompt templates
- `validate_model_output()` - Validate model output against schema

**Models:**
- `DescribeOutput` - Pydantic model for video description output
- `Segment` - Pydantic model for video segments

This module contains no I/O or database operations, making it easily reusable.

### 2. `describe_daemon.py` - FastAPI Service
A FastAPI daemon that hosts a REST API for video description.

**Features:**
- Loads model once at startup (faster for batch processing)
- REST API endpoint: `POST /describe`
- Health check endpoint: `GET /health`
- Uses protobuf-compatible request/response models
- Automatic thumbnail extraction
- Subtitle support

**Usage:**
```bash
# Start the daemon
python -m vlog.describe_daemon --host 127.0.0.1 --port 5555

# Or with custom model
python -m vlog.describe_daemon --model mlx-community/Qwen3-VL-8B-Instruct-4bit
```

**Environment Variables:**
- `DESCRIBE_MODEL` - Model name to load (default: mlx-community/Qwen3-VL-8B-Instruct-4bit)

### 3. `describe_client.py` - CLI Client
A command-line tool for interacting with the daemon.

**Features:**
- Automatically starts/stops the daemon
- Processes single or multiple video files
- Saves results as JSON files next to videos
- Optional custom output directory
- Keep daemon running option for reuse

**Usage:**
```bash
# Describe a single video (starts daemon, processes, stops daemon)
python -m vlog.describe_client video.mp4

# Describe multiple videos
python -m vlog.describe_client video1.mp4 video2.mp4 video3.mp4

# Save JSON to custom directory
python -m vlog.describe_client video.mp4 --output-dir ./descriptions

# Keep daemon running for faster subsequent calls
python -m vlog.describe_client video.mp4 --keep-daemon

# Use existing daemon (don't start new one)
python -m vlog.describe_client video.mp4 --use-existing

# Custom parameters
python -m vlog.describe_client video.mp4 --fps 2.0 --max-tokens 5000 --temperature 0.5
```

**Options:**
- `--host` - Daemon host (default: 127.0.0.1)
- `--port` - Daemon port (default: 5555)
- `--model` - Model to use if starting daemon
- `--output-dir` - Output directory for JSON files
- `--fps` - Frames per second to sample (default: 1.0)
- `--max-pixels` - Maximum pixel size (default: 50176)
- `--max-tokens` - Maximum generation tokens (default: 10000)
- `--temperature` - Generation temperature (default: 0.7)
- `--keep-daemon` - Don't stop daemon after processing
- `--use-existing` - Use existing daemon without starting new one

### 4. `describe.py` - Legacy Interface
Refactored to use `describe_lib.py` while maintaining the original interface.

**Functions:**
- `describe_and_insert_video()` - Describe video and insert into database
- `describe_videos_in_dir()` - Batch process directory of videos

This maintains backward compatibility with existing code that imports from `describe.py`.

## Workflows

### Single Video Processing
```bash
# Option 1: Use the client (recommended)
python -m vlog.describe_client video.mp4

# Option 2: Use original batch interface
python -m vlog.describe /path/to/video/directory --model mlx-community/Qwen3-VL-8B-Instruct-4bit
```

### Batch Processing with Daemon
```bash
# Start daemon
python -m vlog.describe_daemon &

# Process videos (daemon stays running)
python -m vlog.describe_client --use-existing video1.mp4
python -m vlog.describe_client --use-existing video2.mp4
python -m vlog.describe_client --use-existing video3.mp4

# Stop daemon when done
pkill -f describe_daemon
```

### Programmatic Usage
```python
from vlog.describe_lib import describe_video, load_model

# Load model once
model, processor, config = load_model("mlx-community/Qwen3-VL-8B-Instruct-4bit")

# Describe multiple videos
for video_path in video_paths:
    result = describe_video(
        model, processor, config, video_path,
        fps=1.0, max_pixels=224*224, max_tokens=10000
    )
    print(result)
```

## API Reference

### Daemon API

#### POST /describe
Describe a video file.

**Request Body:**
```json
{
  "filename": "/absolute/path/to/video.mp4",
  "fps": 1.0,
  "max_pixels": 50176,
  "max_tokens": 10000,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "filename": "video.mp4",
  "video_description_long": "Detailed description...",
  "video_description_short": "Short name",
  "primary_shot_type": "pov",
  "tags": ["dynamic", "closeup"],
  "classification_time_seconds": 12.5,
  "classification_model": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
  "video_length_seconds": 30.0,
  "video_timestamp": "2024-01-01T12:00:00",
  "video_thumbnail_base64": "...",
  "in_timestamp": "00:00:00.000",
  "out_timestamp": "00:00:30.000",
  "rating": 0.8,
  "segments": [
    {"in_timestamp": "00:00:00.000", "out_timestamp": "00:00:15.000"}
  ],
  "camera_movement": "pan",
  "thumbnail_frame": 15
}
```

#### GET /health
Check daemon health.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_name": "mlx-community/Qwen3-VL-8B-Instruct-4bit"
}
```

## Benefits of New Architecture

1. **Modularity**: Core logic separated from I/O and API concerns
2. **Reusability**: Library can be used in different contexts
3. **Performance**: Daemon keeps model in memory for faster batch processing
4. **Flexibility**: Easy to switch between daemon and direct usage
5. **Testability**: Pure business logic easier to test
6. **API-First**: REST API enables integration with other tools/languages
7. **Backward Compatible**: Original interface still works

## Migration Guide

If you're using the old `describe.py` directly:
- **No changes needed** - the interface remains the same
- **Optional**: Switch to client for better performance with multiple videos
- **Optional**: Use daemon for server-based workflows

If you're importing functions from `describe.py`:
- Most functions are now in `describe_lib.py`
- Imports from `describe.py` still work but may be deprecated in future
- Recommended to import from `describe_lib.py` for new code
