# Copilot Instructions for vlog

## Project Overview
This is a video logging and analysis application that uses machine learning (MLX-VLM) to automatically classify and describe video clips. The system includes:
- Video analysis using MLX-VLM (Vision Language Model)
- SQLite database for storing metadata
- Flask web server for UI and API (legacy results viewer)
- FastAPI service for video description (describe daemon)
- Snakemake workflow for automated video ingestion from SD cards
- Auto-ingest feature for monitoring directories and automatic processing
- DaVinci Resolve integration for importing classified clips
- HTML/JavaScript frontend for video review and editing

## System Architecture

### Core Workflows

**1. Manual Ingestion (scripts/ingest.sh)**
- Run transcription, subtitle cleaning, and description on local videos
- Saves results directly to database
- Best for ad-hoc processing of individual videos

**2. Snakemake Pipeline (staged)**
- Orchestrated workflow split into 3 stage files under `src/ingest_pipeline/snakefiles/`
- Steps: copy main → copy/create preview → transcribe → clean subtitles → describe → JSON output
- Configuration-driven via config.yaml
- Handles both SD card and local directory modes
- Best for importing from cameras/SD cards with preview files

**3. Auto-Ingest (auto_ingest.py)**
- Monitors directory for new video files using watchdog
- Automatically invokes Snakemake pipeline for each new file
- Idempotent (skips files already in database)
- Provides REST API for control (start/stop/status)
- Best for automated background processing

**4. Describe Daemon (describe_daemon.py)**
- FastAPI service for video description requests
- Async processing of description tasks
- Client/server architecture (describe_client.py)
- Best for distributed or long-running description workloads

### User Interfaces

**1. Launcher UI (launcher.html, launcher.py)**
- Web-based interface for running scripts and monitoring progress
- Point-and-click execution of ingestion workflows
- Real-time console output and status
- Configuration of working directories and model settings
- Control panel for auto-ingest feature

**2. Results Viewer (index.html, web.py)**
- Browse and filter classified videos
- Edit metadata (descriptions, tags, ratings, in/out points)
- View thumbnails and video details
- Export selections to DaVinci Resolve

**3. DaVinci Resolve Integration (davinci_clip_importer.py)**
- Script runs inside DaVinci Resolve
- Imports clips with metadata and in/out points
- Supports multiple segments per clip
- Automatic project discovery via HTTP/config/env var

## Technology Stack
- **Python 3.11+**: Primary programming language (pinned in `.python-version`)
- **UV**: Modern Python package manager for dependency management and virtual environments
- **Flask**: Web framework for API and serving frontend (legacy/results viewer)
- **FastAPI/Uvicorn**: Modern async web framework for describe daemon and API services
- **Snakemake**: Workflow management system for orchestrating video ingestion pipeline
- **MLX-VLM**: Vision language model for video analysis
- **OpenCV (cv2)**: Video processing and thumbnail extraction
- **SQLite3**: Database for storing video metadata
- **Protocol Buffers**: Data schema definition (describe.proto)
- **Pydantic**: Data validation and settings management
- **Watchdog**: File system monitoring for auto-ingest feature
- **Requests**: HTTP client library for API communication
- **PyYAML**: Configuration file parsing (config.yaml, prompts)
- **FFmpeg**: External tool for video transcoding and preview generation
- **mlx_whisper**: Audio transcription for generating subtitles
- **HTML/CSS/JavaScript**: Frontend interface

## Coding Style & Conventions

### Python Code
- Follow PEP 8 style guidelines
- Use type hints where appropriate (e.g., `-> tuple[float, str]`)
- Use descriptive variable names (snake_case for variables and functions)
- Add docstrings to all functions explaining purpose, parameters, and return values
- Keep functions focused and single-purpose
- Use context managers for resource management (database connections, video captures)
- Use Pydantic models for data validation and API schemas
- Use async/await for FastAPI endpoints when doing I/O operations

### Dependency Management Philosophy
- **All Python dependencies are managed via UV** and declared in `pyproject.toml`
- **Assume all declared dependencies are available** - do not write defensive try/except ImportError blocks
- When adding a new library dependency:
  1. First update `pyproject.toml` with `uv add <package>`
  2. Then write code that imports and uses the library directly
  3. Run `uv sync` to install and lock dependencies
- **DO NOT** write fallback code like `try: import X except ImportError: use subprocess` 
- **DO NOT** check if a library is installed before importing it
- If a library is needed, add it to `pyproject.toml` as the first step, then use it confidently
- The UV environment ensures all dependencies are available when code runs

### Snakemake Code
- Use meaningful rule names that describe the operation (e.g., `transcribe`, `clean_subtitles`)
- Define clear input/output dependencies
- Use `params:` for configuration values, not hardcoded in run/shell blocks
- Add docstrings to complex rules explaining what they do
- Use `run:` blocks for Python code, `shell:` blocks for external commands
- Import modules within `run:` blocks, not at the top of Snakefile
- Use `workflow.basedir` to construct paths relative to Snakefile

### Error Handling
- Always use try/except blocks when working with external resources (files, database, video)
- Provide informative error messages
- Log errors with descriptive context
- Release resources (video captures, database connections) in finally blocks
- For FastAPI, use HTTPException with appropriate status codes
- For Snakemake, let errors propagate to stop the workflow

### Database Operations
- Use the centralized `db.py` module for all database operations
- Always use parameterized queries to prevent SQL injection
- Set `row_factory = sqlite3.Row` for dictionary-like row access
- Handle `sqlite3.Error` exceptions appropriately

## Security Guidelines

### General Security
- Never hardcode secrets, API keys, or passwords in source code
- Use environment variables for sensitive configuration
- Validate all user input before processing
- Use parameterized SQL queries to prevent SQL injection
- Set secure Flask configuration (SECRET_KEY should be random and not committed)

### Flask Security
- Set httpOnly, secure, and sameSite attributes for cookies if used
- Validate file paths to prevent directory traversal attacks
- Sanitize user input in API endpoints
- Use appropriate HTTP status codes for errors

### FastAPI Security
- Use Pydantic models for request validation (automatic)
- Validate file paths before processing
- Use dependency injection for shared resources
- Return appropriate HTTP status codes via HTTPException
- Consider authentication/authorization for production deployments

### Snakemake Security
- Validate all input paths before processing
- Use parameterized values from config, not user input directly in shell commands
- Be cautious with shell injection when constructing commands
- Sanitize any user-provided configuration values

## Dependencies & Libraries

### Package Management with UV
- **This project uses UV exclusively** for Python package management
- UV manages the virtual environment and all dependencies via `pyproject.toml` and `uv.lock`
- **All dependencies are assumed to be available** - the UV environment ensures this
- **Never write defensive import code** - if a library is needed, add it to pyproject.toml first

### Adding New Dependencies
**Workflow for adding a new library:**
1. Add the dependency: `uv add <package>` (or `uv add --dev <package>` for dev-only)
2. Sync the environment: `uv sync` (this updates `uv.lock`)
3. Write code that imports and uses the library directly (no try/except ImportError)
4. Commit both `pyproject.toml` and `uv.lock` changes

**Guidelines:**
- Only add new dependencies if absolutely necessary
- Document why the dependency is needed in commit messages
- Check for security vulnerabilities before adding
- Prefer well-maintained packages with good documentation

### Running Python Code
- Always use UV to run Python: `uv run -- python script.py`
- Or activate the UV environment first, then run normally
- UV ensures the correct Python version and all dependencies are available

### Required Libraries
Core dependencies used throughout the project:
- `mlx-vlm` - Video analysis with vision language models
- `mlx-whisper` - Audio transcription for subtitle generation  
- `opencv-python` (`cv2`) - Video processing and thumbnail extraction
- `flask` - Web server for legacy results viewer
- `fastapi` and `uvicorn` - Modern async API services (describe daemon)
- `sqlite3` (built-in) - Database operations
- `snakemake` - Workflow orchestration
- `pydantic` - Data validation and settings management
- `watchdog` - File system monitoring (auto-ingest)
- `requests` - HTTP client operations
- `pyyaml` - Configuration file parsing
- `protobuf` - Schema definitions (describe.proto)
- `jinja2` - Prompt templating

## Project-Specific Guidelines

### Video Processing
- Always release video captures with `cap.release()` after use
- Handle cases where video files cannot be opened
- Provide fallback values (e.g., BLACK_PIXEL_BASE64 for failed thumbnails)
- Use appropriate frame rate calculations for thumbnail extraction

### Subtitle Processing (SRT)
The project includes subtitle generation and cleaning functionality:
- `transcribe` Snakemake rule generates `.srt` files using mlx_whisper
- `clean_subtitles` rule removes duplicates and hallucinations
- `srt_cleaner.py` module provides parsing and cleaning functions
- Subtitles are used as input to video description for better context
- Clean subtitles are saved with `_cleaned.srt` suffix

**Key Functions:**
- `parse_srt(file_path)` - Parse SRT file into list of subtitle entries
- `clean_subtitles(subtitles)` - Remove duplicates and hallucinations
- `reassemble_srt(subtitles)` - Convert subtitle list back to SRT format

**Cleaning Rules:**
- Remove consecutive duplicate subtitle text
- Detect ASR hallucinations (repeated phrases, common artifacts)
- Preserve timing information
- Maintain SRT format compliance

### Database Schema
The main table (`results`) stores the following fields (in schema order):
- `filename`: Video filename (PRIMARY KEY)
- `video_description_long`: AI-generated long description
- `video_description_short`: AI-generated short description
- `primary_shot_type`: pov, insert, or establishing
- `tags`: JSON-encoded list (static, dynamic, closeup, medium, wide)
- `last_updated`: ISO format timestamp of last modification
- `classification_time_seconds`: Time taken for AI classification
- `classification_model`: Name of the model used
- `video_length_seconds`: Duration in seconds
- `video_timestamp`: ISO format timestamp of video file
- `video_thumbnail_base64`: Base64-encoded JPEG thumbnail
- `clip_cut_duration`: Optional duration for trimming
- `keep`: Boolean flag for user selection (1=keep, 0=discard, default: 1)
- `in_timestamp`: Start timestamp for clip trimming (format: "HH:MM:SS.sss")
- `out_timestamp`: End timestamp for clip trimming (format: "HH:MM:SS.sss")
- `rating`: Quality rating (0.0 to 1.0)
- `segments`: JSON-encoded array of segment objects with in/out timestamps (supports multiple segments per video)

Note: Tags and segments are stored as JSON strings in the database but returned as Python lists/dicts in API responses.

The database schema is also defined in Protocol Buffers format in `src/proto/describe.proto` for type safety and schema documentation.

### Snakemake Workflow
The project uses Snakemake for orchestrating the video ingestion pipeline from SD cards or local directories.

**Workflow Overview:**

The pipeline has been split into 3 independent stages for better control:

1. **Stage 1: Copy** (`snakefiles/copy.smk`) - Copy main video files and create/copy preview files
2. **Stage 2: Subtitles** (`snakefiles/subtitles.smk`) - Generate and clean subtitle files  
3. **Stage 3: Describe** (`snakefiles/describe.smk`) - Analyze videos and save results to JSON

**Master Workflow:**
- `src/ingest_pipeline/Snakefile` - Orchestrates all 3 stages, can run them together or individually
- Each stage can also be run independently using its own Snakefile

**Running the workflow:**
```bash
# Run all stages together (master orchestrator)
snakemake --snakefile src/ingest_pipeline/Snakefile --cores 1 --configfile config.yaml

# Run individual stages (now stored under src/ingest_pipeline/snakefiles)
snakemake --snakefile src/ingest_pipeline/snakefiles/copy.smk --cores 1 --configfile config.yaml
snakemake --snakefile src/ingest_pipeline/snakefiles/subtitles.smk --cores 1 --configfile config.yaml
snakemake --snakefile src/ingest_pipeline/snakefiles/describe.smk --cores 1 --configfile config.yaml

# Run specific stage from master file
snakemake --snakefile src/ingest_pipeline/Snakefile --cores 1 --configfile config.yaml stage1
```

**Configuration:**
- Main config: `config.yaml` (SD card path, folders, model settings)
- Workflow definitions: `src/ingest_pipeline/Snakefile*`
- Helper scripts in `src/ingest_pipeline/` directory

**Key Guidelines:**
- Use Snakemake rules for pipeline steps, not standalone scripts when possible
- Follow the pattern of input/output file dependencies
- Use `run:` blocks for Python code within rules
- Use `shell:` blocks for external commands
- Configuration should be in config.yaml, not hardcoded
- Handle both SD card and local directory modes (check if source == destination)
- Import modules within `run:` blocks to avoid parse-time dependency issues
- Each stage file has its own discovery function for flexibility

### Auto-Ingest Feature
The auto-ingest feature monitors a directory for new video files and automatically processes them through the Snakemake pipeline.

**Key Components:**
- `src/vlog/auto_ingest_snakemake.py` - Main auto-ingest service using watchdog
- File system monitoring with `watchdog.observers.Observer`
- Idempotent processing (checks database before processing)
- Integration with Snakemake workflow for each new file
- REST API endpoints for control (start/stop/status)
- Real-time progress tracking via Snakemake logger plugin

**Key Guidelines:**
- Always check if file exists in database before processing (`check_if_file_exists()`)
- Use the Snakemake workflow for consistency with manual ingestion
- Provide status endpoints for monitoring
- Handle errors gracefully and log them
- Support starting/stopping via API or web UI
- Track progress via the Snakemake logger plugin API

### DaVinci Resolve Integration
The project includes integration with DaVinci Resolve for importing classified video clips.

**Key Components:**
- `src/vlog/davinci_clip_importer.py` - Main importer script
- Automatic project discovery via HTTP endpoint, config file, or environment variable
- Support for multiple segments per video clip
- Sets in/out points, metadata, and organizes clips in bins

**Key Guidelines:**
- Script should be copy-friendly to DaVinci's Fusion Scripts directory
- Use the `Resolve` API object for DaVinci operations
- Handle missing project gracefully with clear error messages
- Support multiple discovery methods (HTTP > config > env var)
- Import each segment as a separate clip instance
- Set clip metadata (description, tags, rating)

### Protocol Buffers
The project uses Protocol Buffers to define the data schema for video descriptions.

**Schema Location:** `src/proto/describe.proto`

**Key Guidelines:**
- Define message types for structured data (VideoDescription, Segment)
- Use `protoc` to generate Python code: `make proto`
- Keep proto definitions in sync with database schema
- Use proto messages for type-safe data exchange
- Consider using proto for future API communication

### YAML Configuration
The project uses YAML for configuration files.

**Configuration Files:**
- `config.yaml` - Main Snakemake workflow configuration
- `prompts/describe_v1.yaml` - Model prompt configuration

**Key Guidelines:**
- Use YAML for hierarchical configuration
- Parse with `pyyaml` library
- Provide sensible defaults
- Document configuration options in comments
- Validate configuration values before use

### Launcher and Directory Browser
The launcher UI provides a web-based interface for running scripts and managing workflows.

**Key Components:**
- `launcher.py` - FastAPI backend for launcher
- `launcher_utils.py` - Utility functions (directory browsing, etc.)
- `static/launcher/launcher.html` - Frontend UI

**Key Guidelines:**
- `browse_server_directory()` function provides safe directory listing
- Prevent directory traversal attacks (validate paths)
- Return directory contents as JSON with file/directory indicators
- Provide working directory configuration
- Real-time script execution output via streaming or polling
- Track script execution state (running, completed, failed)

### API Endpoints
- Follow RESTful conventions
- Use `/api/` prefix for all API routes
- Return JSON responses with appropriate status codes
- Include error messages in JSON format: `{"success": false, "message": "..."}`
- Separate data retrieval (GET) from modification (POST)

### MLX-VLM Integration
- Use the default prompt defined in prompts/describe_v1.yaml or describe_v1.md for consistency
- Parse JSON responses from the model
- Handle cases where model output is malformed
- Model is now used via PyPI package (`mlx-vlm`), not a submodule
- Support both local model execution and describe daemon (FastAPI service)
- Use `describe_client.py` for client-side API calls to the daemon
- Use `describe_daemon.py` for running the description service
- Prompts use Jinja2 templating for variable substitution (e.g., subtitle text, configuration values)

## Testing Requirements
- Test database operations with various inputs
- Test API endpoints for both success and error cases
- Test video processing with different video formats
- Test Snakemake workflow rules individually and as a pipeline
- Test auto-ingest monitoring and idempotency
- Verify error handling for missing files and invalid data
- Test Flask and FastAPI routes return correct status codes
- Test DaVinci Resolve integration (if DaVinci is available)
- Use pytest as the testing framework
- Use fixtures from `tests/conftest.py` for database and file setup
 - Use fixtures from `tests/conftest.py` for database and file setup
 - Run tests with: `uv run -- pytest tests/ -v`
     - A convenience Makefile target is available: `make test` (runs `uv run -- pytest`).
 - Check coverage with: `uv run -- pytest tests/ --cov=src/vlog`

## Documentation Standards
- Add clear docstrings to all functions
- Include parameter types and return types in docstrings
- Document any assumptions or limitations
- Keep README.md updated with setup instructions
- Document the database schema if modified

## File Organization
- `src/vlog/db.py`: All database operations (create, read, update)
- `src/vlog/video.py`: Video processing utilities (length, timestamp, thumbnail)
- `src/vlog/describe.py`: ML model integration and video analysis (legacy)
- `src/vlog/describe_lib.py`: Core description logic (refactored)
- `src/vlog/describe_daemon.py`: FastAPI service for video description
- `src/vlog/describe_client.py`: Client for communicating with describe daemon
- `src/vlog/web.py`: Flask application and API endpoints (legacy results viewer)
- `src/vlog/auto_ingest_snakemake.py`: Automated video monitoring and ingestion with Snakemake
- `src/vlog/srt_cleaner.py`: Subtitle file cleaning and processing
- `src/vlog/davinci_clip_importer.py`: DaVinci Resolve integration script
- `src/proto/describe.proto`: Protocol Buffers schema definition
- `src/ingest_pipeline/`: Snakemake pipeline files and helper scripts
    - `Snakefile`: Master workflow orchestrating all 3 stages
    - `snakefiles/`: Directory containing stage-specific Snakemake files
        - `copy.smk`: Stage 1 - Copy videos from SD card
        - `subtitles.smk`: Stage 2 - Generate and clean subtitles
        - `describe.smk`: Stage 3 - Describe videos using daemon
  - `create_preview.py`: Generate preview videos with ffmpeg
  - `describe_to_json.py`: Describe video via daemon and save to JSON
  - `discover_videos.py`: Discover video files on SD card
- `config.yaml`: Main configuration file for Snakemake workflow
- `scripts/`: Executable scripts for various operations
  - `ingest.sh`: Manual ingestion pipeline
  - `launch_web.sh`: Start web UI launcher
  - `run_snakemake.sh`: Run Snakemake workflow
  - `setup_davinci_config.sh`: DaVinci Resolve configuration setup
  - `verify_snakemake_env.py`: Verify Snakemake environment
- `static/index.html`: Frontend UI for results viewer
- `static/launcher/launcher.html`: Frontend UI for launcher
- `prompts/`: Model prompts in YAML and Markdown formats
- `docs/`: Detailed documentation
  - `AUTO_INGEST_SNAKEMAKE.md`: Auto-ingest with Snakemake pipeline
  - `DAEMON_MANAGEMENT.md`: Daemon management in Snakemake workflow
  - `DAVINCI_INTEGRATION.md`: DaVinci Resolve integration guide
  - `EXAMPLE_WORKFLOW.md`: Complete example workflow from SD card
  - `SNAKEMAKE_QUICKSTART.md`: Quick start guide for Snakemake ingestion
  - `SNAKEMAKE_WORKFLOW.md`: Detailed Snakemake workflow documentation
  - `STAGED_WORKFLOW.md`: Staged workflow guide
  - `STATUS_LOGGER.md`: Status logger plugin documentation
  - `STATUS_LOGGER_QUICKREF.md`: Status logger quick reference
  - `VAD_TRANSCRIPTION.md`: Voice activity detection transcription
- `tests/`: Test suite (pytest-based)

## Common Patterns

### Database Connection in Flask
```python
def get_db_connection():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db
```

### Video Capture Pattern
```python
cap = cv2.VideoCapture(file_path)
if cap.isOpened():
    try:
        # Process video
        pass
    except Exception as e:
        # Handle error
        pass
    finally:
        cap.release()
```

### API Response Pattern
```python
try:
    # Perform operation
    return jsonify({"success": True, "message": "..."}), 200
except Exception as e:
    return jsonify({"success": False, "message": str(e)}), 500
```

### Snakemake Rule Pattern
```python
# Rule with Python code
rule process_video:
    input:
        "input/{stem}.mp4"
    output:
        "output/{stem}.json"
    run:
        import sys
        from pathlib import Path
        
        # Add src to path for imports
        project_root = Path(workflow.basedir)
        sys.path.insert(0, str(project_root / "src"))
        
        from vlog.describe_lib import describe_video
        
        # Process the video
        result = describe_video(input[0])
        
        # Save result
        import json
        with open(output[0], 'w') as f:
            json.dump(result, f)

# Rule with shell command
rule transcribe:
    input:
        "videos/{stem}.mp4"
    output:
        "videos/{stem}.srt"
    params:
        model="mlx-community/whisper-large-v3-turbo"
    shell:
        """
        mlx_whisper --model {params.model} -f srt --task transcribe {input}
        """
```

### FastAPI Endpoint Pattern
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class DescribeRequest(BaseModel):
    video_path: str
    model: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit"

@app.post("/describe")
async def describe_video(request: DescribeRequest):
    try:
        # Perform operation
        result = process_video(request.video_path, request.model)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Watchdog File Monitoring Pattern
```python
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

class VideoHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            # Check if it's a video file
            if event.src_path.endswith(('.mp4', '.mov', '.avi')):
                # Process the video
                self.process_video(event.src_path)
    
    def process_video(self, path):
        # Video processing logic
        pass

observer = Observer()
handler = VideoHandler()
observer.schedule(handler, path="/path/to/watch", recursive=False)
observer.start()
```

### Configuration Loading Pattern
```python
import yaml

def load_config(config_path: str = "config.yaml"):
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

# Usage
config = load_config()
sd_card_path = config.get("sd_card_path", "/Volumes/SDCARD")
model = config.get("describe", {}).get("model", "default-model")
```

### Protocol Buffers Usage Pattern
```python
from proto import describe_pb2

# Create a message
video_desc = describe_pb2.VideoDescription()
video_desc.filename = "video.mp4"
video_desc.video_description_long = "A long description"
video_desc.rating = 0.85

# Add segments
segment = video_desc.segments.add()
segment.in_timestamp = "00:00:10.000"
segment.out_timestamp = "00:00:20.000"

# Serialize
serialized = video_desc.SerializeToString()

# Deserialize
new_desc = describe_pb2.VideoDescription()
new_desc.ParseFromString(serialized)
```
