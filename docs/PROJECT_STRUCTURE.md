# Project Structure

This document describes the vlog project structure and organization.

## Overview

The vlog project follows modern Python package conventions with all package code organized under `src/vlog/`. This structure provides clear separation between different types of files and makes the project easier to understand and maintain.

## Directory Layout

```
vlog/
├── src/vlog/                    # Main Python package (installed code)
│   ├── workflows/               # Snakemake workflows for video ingestion
│   │   ├── Snakefile            # Master workflow orchestrator
│   │   ├── snakefiles/          # Individual stage workflows
│   │   │   ├── copy.smk         # Stage 1: Copy videos from SD card
│   │   │   ├── subtitles.smk    # Stage 2: Generate/clean subtitles
│   │   │   ├── describe.smk     # Stage 3: Describe videos
│   │   │   └── daemon.smk       # Daemon management
│   │   └── scripts/             # Workflow helper scripts
│   │       ├── discover_videos.py
│   │       ├── create_preview.py
│   │       ├── transcribe.py
│   │       ├── srt_cleaner.py
│   │       ├── describe_to_json.py
│   │       └── vad_utils.py
│   ├── static/                  # Web UI assets (served by Flask)
│   │   ├── index.html           # Results viewer UI
│   │   └── launcher/
│   │       └── launcher.html    # Launcher UI
│   ├── prompts/                 # AI model prompts (package data)
│   │   ├── describe_v1.md       # Markdown prompt template
│   │   └── describe_v1.yaml     # Prompt metadata/config
│   ├── snakemake_logger_plugin/ # Status logger plugin implementation
│   │   ├── __init__.py
│   │   ├── logger.py            # Logger handler
│   │   └── api_server.py        # REST API server
│   ├── web.py                   # Flask web server (launcher + results)
│   ├── video.py                 # Video processing utilities
│   ├── describe_lib.py          # ML model integration
│   ├── describe_daemon.py       # FastAPI service for descriptions
│   ├── describe_client.py       # Client for daemon communication
│   ├── auto_ingest_snakemake.py # Auto-ingest with Snakemake
│   ├── davinci_clip_importer.py # DaVinci Resolve integration
│   └── web_file_browser.py      # Directory browser utility
├── src/proto/                   # Protocol Buffers definitions
│   ├── describe.proto           # Schema definition
│   └── describe_pb2.py          # Generated Python code
├── src/snakemake_logger_plugin_vlog/  # Plugin discovery shim
│   └── __init__.py              # Re-exports from vlog.snakemake_logger_plugin
├── scripts/                     # User-facing executable scripts
│   ├── ingest.sh                # Manual ingestion pipeline
│   ├── launch_web.sh            # Start web UI
│   ├── transcribe.sh            # Transcribe videos
│   ├── run_snakemake.sh         # Run Snakemake workflow
│   ├── run_snakemake_with_logger.sh  # Run with status logger
│   ├── run_with_status_logger.py     # Python wrapper for logger
│   ├── snakemake_status.py      # Query workflow status
│   └── ...                      # Other utility scripts
├── examples/                    # Example configurations
│   └── config.yaml              # Example Snakemake config
├── tests/                       # Test suite (pytest)
│   ├── test_video.py
│   ├── test_web.py
│   ├── test_snakemake_workflow.py
│   └── ...
├── docs/                        # Documentation
│   ├── SNAKEMAKE_WORKFLOW.md
│   ├── AUTO_INGEST_SNAKEMAKE.md
│   ├── DAVINCI_INTEGRATION.md
│   └── ...
├── test_data/                   # Test fixtures
├── config.yaml                  # Working config (user-specific, not in git)
├── pyproject.toml               # Project metadata and dependencies
├── uv.lock                      # Locked dependency versions (UV)
├── Makefile                     # Common tasks
└── README.md                    # Main documentation
```

## Design Principles

### 1. Package Data Co-location

All data files that are part of the package (static assets, prompts, workflows) are located within `src/vlog/`. This ensures:
- Files are distributed with the package when installed
- Import paths are predictable and consistent
- No need for complex path resolution at runtime

### 2. Clear Separation of Concerns

**User Scripts** (`scripts/`): Shell scripts that users invoke directly from the command line.

**Workflow Scripts** (`src/vlog/workflows/scripts/`): Python scripts called by Snakemake rules, not meant to be run directly by users.

**Package Code** (`src/vlog/`): Importable Python modules that implement functionality.

### 3. Example vs. Working Files

**Example Config** (`examples/config.yaml`): A reference configuration showing all available options. Can be copied and customized.

**Working Config** (`config.yaml`): User's actual configuration. Should be in `.gitignore` to avoid committing local paths.

## Migration from Old Structure

The reorganization consolidated several scattered directories:

**Before:**
- `src/ingest_pipeline/` - Snakemake workflows
- `src/ingest_pipeline/scripts/` - Workflow helper scripts
- `static/` - Web UI at root level
- `prompts/` - Prompts at root level
- Duplicate `scripts/` locations

**After:**
- `src/vlog/workflows/` - All Snakemake workflows
- `src/vlog/workflows/scripts/` - All workflow scripts
- `src/vlog/static/` - Web UI in package
- `src/vlog/prompts/` - Prompts in package
- Single `scripts/` directory for user scripts

## Finding Files

### Common File Locations

| File Type | Location | Example |
|-----------|----------|---------|
| Snakemake workflows | `src/vlog/workflows/snakefiles/*.smk` | `copy.smk`, `subtitles.smk` |
| Workflow scripts | `src/vlog/workflows/scripts/*.py` | `discover_videos.py` |
| Web UI | `src/vlog/static/*.html` | `index.html`, `launcher.html` |
| AI prompts | `src/vlog/prompts/*.{md,yaml}` | `describe_v1.md` |
| User scripts | `scripts/*.sh` | `ingest.sh`, `launch_web.sh` |
| Python modules | `src/vlog/*.py` | `web.py`, `describe_lib.py` |
| Tests | `tests/test_*.py` | `test_web.py` |
| Documentation | `docs/*.md` | `SNAKEMAKE_WORKFLOW.md` |

### Path Resolution in Code

**Web Server** (`web.py`):
```python
PACKAGE_DIR = Path(__file__).parent  # src/vlog/
STATIC_DIR = PACKAGE_DIR / 'static'  # src/vlog/static/
```

**Description Library** (`describe_lib.py`):
```python
PACKAGE_DIR = os.path.dirname(__file__)  # src/vlog/
DEFAULT_PROMPT_PATH = os.path.join(PACKAGE_DIR, 'prompts', 'describe_v1.md')
```

**Snakemake Scripts** (workflow context):
```python
# Scripts are in src/vlog/workflows/scripts/
# Called via: uv run -- python src/vlog/workflows/scripts/script_name.py
```

## Benefits of This Structure

1. **Standard Convention**: Follows src-layout pattern used by most modern Python projects
2. **Clear Organization**: Easy to find files based on their purpose
3. **Package Distribution**: All package data is properly included
4. **No Path Confusion**: Single source of truth for each type of file
5. **Better IDE Support**: Standard structure works well with IDEs and linters
6. **Easier Testing**: Tests can import from package without path manipulation
7. **Scalability**: Structure can grow without becoming messy

## References

- [Python Packaging User Guide - src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [PyPA Sample Project](https://github.com/pypa/sampleproject)
- [Snakemake Best Practices](https://snakemake.readthedocs.io/en/stable/snakefiles/deployment.html)
