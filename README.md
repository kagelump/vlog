## Project Structure

The project follows modern Python project organization conventions:

```
vlog/
├── src/vlog/                    # Main Python package
│   ├── workflows/               # Snakemake workflows for video ingestion
│   │   ├── Snakefile            # Master workflow orchestrator
│   │   ├── snakefiles/          # Individual stage workflows (.smk files)
│   │   └── scripts/             # Workflow helper scripts
│   ├── static/                  # Web UI assets
│   │   ├── index.html           # Results viewer
│   │   └── launcher/            # Launcher UI
│   ├── prompts/                 # AI model prompts
│   ├── snakemake_logger_plugin/ # Status logger plugin
│   ├── web.py                   # Flask web server
│   ├── video.py                 # Video processing utilities
│   ├── describe_lib.py          # Video description using ML models
│   ├── describe_daemon.py       # FastAPI service for descriptions
│   ├── auto_ingest_snakemake.py # Auto-ingest with Snakemake
│   └── ...                      # Other modules
├── scripts/                     # User-facing executable scripts
│   ├── ingest.sh                # Manual ingestion pipeline
│   ├── launch_web.sh            # Start web UI
│   └── ...                      # Other utility scripts
├── examples/                    # Example configurations
│   └── config.yaml              # Example workflow config
├── tests/                       # Test suite
├── docs/                        # Documentation
├── config.yaml                  # Working config (not in git)
├── pyproject.toml               # Project dependencies and metadata
└── README.md
```

## Usage

### UI Launcher (Recommended)

The easiest way to use vlog is through the integrated web UI launcher (recommended):

```bash
# Preferred: run inside the uv-managed venv as a module so imports are resolved
cd /path/to/vlog
uv run -- python -m vlog.web

# Or use the convenience script that wraps the uv command (supports --port, --detached):
./scripts/launch_web.sh --port 5432
```

Then open your browser to http://localhost:5432

The launcher provides:
- Point-and-click script execution
- Real-time progress tracking and console output
- Working directory configuration
- Model and FPS settings
- **Auto-Ingest**: Automatic monitoring and processing of new video files
- Easy navigation to classification results

### Auto-Ingest Feature

**NEW: Snakemake-Based Auto-Ingest** - The recommended approach for automatic video ingestion.

Auto-ingest automatically monitors a directory for new video files and runs the complete ingestion pipeline without manual intervention. There are two versions:

#### Auto-Ingest with Snakemake (Recommended)

The new Snakemake-based auto-ingest provides:
- **Full pipeline**: All 3 stages (copy → transcribe → clean subtitles → describe)
- **Real-time progress**: Per-stage breakdown via Snakemake logger plugin
- **Resource control**: Configure CPU cores and memory limits
- **Visual feedback**: Progress bars and status indicators in the UI

See the [Auto-Ingest with Snakemake Documentation](docs/AUTO_INGEST_SNAKEMAKE.md) for detailed usage.

#### Legacy Auto-Ingest

The original auto-ingest is still available for backward compatibility:
- **Idempotent**: Won't reprocess files already in the database
- **Automatic**: Detects new files as they're added
- **Batch processing**: Efficient multi-file processing

See the [Auto-Ingest Documentation](docs/AUTO_INGEST.md) for legacy auto-ingest information.

### Snakemake Workflow (SD Card Ingestion)

For automated ingestion from SD cards with a complete orchestrated pipeline, use the Snakemake workflow:

```bash
cd /path/to/vlog
# Edit config.yaml to set your SD card path
snakemake --cores 1 --configfile config.yaml
```

The Snakemake workflow provides:
- **Organized**: Separate main and preview file storage
- **Flexible**: Copy or create preview files as needed
- **Complete**: Full pipeline from SD card to JSON output
- **Reproducible**: Workflow-based processing with dependency tracking
- **Monitored**: Built-in status logger plugin with REST API to track progress

See the [Snakemake Quick Start Guide](docs/SNAKEMAKE_QUICKSTART.md) or [Snakemake Workflow Documentation](docs/SNAKEMAKE_WORKFLOW.md) for detailed usage.

#### Monitoring Workflow Progress

vlog includes a custom Snakemake logger plugin that provides real-time status via REST API:

```bash
# Run Snakemake with status logger
python3 scripts/run_with_status_logger.py

# In another terminal, query status
python3 scripts/snakemake_status.py
python3 scripts/snakemake_status.py --watch 2  # refresh every 2 seconds
```

See the [Status Logger Documentation](docs/STATUS_LOGGER.md) for detailed usage and API reference.

### Command Line Usage

To run the ingestion pipeline directly:

```bash
cd /path/to/video/directory
/path/to/vlog/scripts/ingest.sh
```

To start the original web server (results viewer only):

```bash
cd /path/to/vlog
PYTHONPATH=src python3 src/vlog/web.py
```

## DaVinci Resolve Integration

vlog includes integration with DaVinci Resolve to automatically import classified video clips with proper in/out points and metadata. The script can automatically discover your vlog project via HTTP endpoint (if web server is running), config file, or environment variable. See the [DaVinci Integration Guide](docs/DAVINCI_INTEGRATION.md) for detailed setup and usage instructions.

**New:** vlog now supports multiple in/out segments per clip! The AI model can identify multiple good segments in long videos, and each segment will be imported to DaVinci Resolve as a separate clip instance.

Quick start (easiest method with web server):
```bash
# 1. Classify your videos
cd /path/to/videos
/path/to/vlog/scripts/ingest.sh

# 2. Start vlog web server (for project discovery)
cd /path/to/vlog
./scripts/launch_web.sh

# 3. Copy importer to DaVinci Resolve
cp src/vlog/davinci_clip_importer.py "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/"

# 4. Run from DaVinci Console - it will auto-discover the project!
```


## Dependency management with `uv`

This project recommends using `uv` (https://docs.astral.sh/uv) to manage Python versions, virtual environments and dependencies.

Why `uv`?
- Fast dependency resolution and caching
- Easy Python version management and project-local virtualenvs (`.venv`)
- Script-aware dependency handling (`uv add --script`) and a familiar pip-compatible interface

Quickstart (macOS / zsh):

1. Install `uv` (one of):

```bash
# via the installer (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# or via pipx
pipx install uv
```

2. Initialize the project (optional) and pin Python:

```bash
cd /path/to/vlog
uv init
uv python pin 3.11
```

3. Create the project venv and install runtime deps (example: Flask):

```bash
uv venv
uv add flask
```

4. Install `mlx-vlm` into the uv-managed environment.
	 You have two options:

	 - Install the published package from PyPI:

		 ```bash
		 uv add mlx-vlm
		 ```

	 - Install directly from the GitHub repository (recommended if you want the latest or a branch):

		 ```bash
		 uv run -- python -m pip install git+https://github.com/Blaizzy/mlx-vlm.git
		 ```

	 - If you previously had a local copy in `third_party/mlx-vlm` and want to keep editing it,
		 install it editable into the env:

		 ```bash
		 uv run -- python -m pip install -e third_party/mlx-vlm
		 ```

5. Lock and sync (optional, for reproducible installs):

```bash
uv lock
uv sync
```

Running the app with `uv`:

```bash
# Run the Flask server
uv run -- python web.py

# Run the describe script
uv run -- python src/vlog/describe.py /path/to/videos --model "mlx-community/Qwen3-VL-8B-Instruct-4bit"
```

CI / GitHub Actions snippet (minimal):

```yaml
- name: Install uv
	run: pipx install uv

- name: Create venv and install deps
	run: |
		uv python pin 3.11
		uv venv
		uv add --dev pytest
		uv lock
		uv sync

- name: Run tests
	run: uv run -- pytest -q
```

Notes:
- Because this repo previously used a checked-in `mlx-vlm` copy as a submodule, you may still have a `third_party/mlx-vlm` directory locally. If you prefer editing that copy during development, install it editable into the uv venv (see step 4).
- If you want me to remove the submodule entirely from git history and repository metadata, I can implement that (it requires git operations to fully unlink the submodule). For now the repo's workflow is switched to `uv`.

## Testing

The project includes a comprehensive test suite covering database operations, video processing, and web API endpoints.

### Running Tests

To run the full test suite:

```bash
# Install test dependencies
pip install pytest pytest-cov opencv-python-headless flask

# Run all tests
python3 -m pytest tests/ -v

# Run tests with coverage report
python3 -m pytest tests/ --cov=src/vlog --cov-report=term-missing

# Run a specific test file
python3 -m pytest tests/test_db.py -v
```

If using `uv`:

```bash
# Add test dependencies
uv add --dev pytest pytest-cov

# Run tests
uv run -- pytest tests/ -v

# Run with coverage
uv run -- pytest tests/ --cov=src/vlog --cov-report=html
```

### Test Coverage

Current test coverage:
- **db.py**: 93% coverage - Tests for database initialization, CRUD operations, and data retrieval
- **video.py**: 85% coverage - Tests for video metadata extraction and thumbnail generation
- **web.py**: 88% coverage - Tests for Flask API endpoints and request handling

The test suite includes:
- 14 tests for database operations (`tests/test_db.py`)
- 8 tests for video utilities (`tests/test_video.py`)
- 24 tests for web API endpoints (`tests/test_web.py`)

### Test Structure

- `tests/conftest.py` - Shared fixtures for database setup and cleanup
- `tests/test_db.py` - Database operation tests
- `tests/test_video.py` - Video processing tests  
- `tests/test_web.py` - Flask API endpoint tests

All tests use temporary databases and files to avoid affecting the development environment.

## VS Code setup (recommended)

If you use VS Code, point the editor to the uv-managed virtual environment so Pylance and the integrated terminal resolve dependencies installed by `uv`.

1. Create the uv venv (if you haven't already):

```bash
uv python pin 3.11
uv venv
uv sync
```

2. Select the interpreter in VS Code: Command Palette → `Python: Select Interpreter` → choose `${workspaceFolder}/.venv/bin/python`.

3. This repository includes a workspace settings file at `.vscode/settings.json` that sets the default interpreter and adds `src/` and `third_party/` to Pylance's `extraPaths` so imports like `from vlog.db import ...` resolve automatically.

4. If you keep an editable local copy of `mlx-vlm` in `third_party/mlx-vlm`, install it into the venv so the editor and runtime see the same package:

```bash
uv run -- python -m pip install -e third_party/mlx-vlm
```

5. Restart VS Code (Developer: Reload Window) after changing the interpreter so Pylance reloads the environment.

Notes:
- The `.vscode/settings.json` file configures the integrated terminal's `PYTHONPATH` so quick ad-hoc runs in the terminal pick up `src/` without manual activation. You can edit or remove `third_party` from `extraPaths` if you prefer not to expose that directory to Pylance.
- Do not commit the `.venv` directory. The `.gitignore` should already exclude it.
