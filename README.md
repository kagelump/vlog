From scratch

1. Install homebrew
2. brew install --cask miniconda
3. brew install python
4. pip install -U mlx-vlm
5. pip install torch torchvision
6. pip install flask

Try out mlx-vlm first

Using [this model](https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-8bit)

```
mlx_vlm.video_generate --model mlx-community/Qwen3-VL-4B-Instruct-8bit --max-tokens 100 --prompt "Describe this video" --video path/to/video.mp4 --max-pixels 224 224 --fps 1.0
```

## Project Structure

The project follows modern Python project organization conventions:

```
vlog/
├── src/vlog/          # Main Python package
│   ├── db.py          # Database operations
│   ├── video.py       # Video processing utilities
│   ├── describe.py    # Video description using ML models
│   ├── web.py         # Flask web server
│   └── ...            # Other modules
├── scripts/           # Executable shell scripts
│   ├── ingest.sh      # Main ingestion pipeline
│   └── transcribe.sh  # Video transcription
├── static/            # Web assets
│   └── index.html     # Web UI
├── third_party/       # External dependencies
└── README.md
```

## Usage

### UI Launcher (Recommended)

The easiest way to use vlog is through the integrated web UI launcher:

```bash
cd /path/to/vlog
PYTHONPATH=src python3 src/vlog/web_integrated.py
```

Then open your browser to http://localhost:5432

The launcher provides:
- Point-and-click script execution
- Real-time progress tracking and console output
- Working directory configuration
- Model and FPS settings
- Easy navigation to classification results

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
