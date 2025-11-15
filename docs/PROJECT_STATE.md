# vlog Project State & Onboarding Guide

**Last Updated:** November 15, 2024  
**Version:** 0.1.0  
**Python Version:** 3.13 (pinned in `.python-version`)

## Table of Contents

- [Executive Summary](#executive-summary)
- [Quick Start for New Engineers](#quick-start-for-new-engineers)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Workflows & Processing Pipelines](#workflows--processing-pipelines)
- [Database Schema](#database-schema)
- [Recent Changes & Fixes](#recent-changes--fixes)
- [Testing Infrastructure](#testing-infrastructure)
- [Configuration Management](#configuration-management)
- [Known Issues & Technical Debt](#known-issues--technical-debt)
- [Improvement Opportunities](#improvement-opportunities)
- [Priority Action Items](#priority-action-items)
- [Development Workflow](#development-workflow)
- [Getting Help](#getting-help)
- [Conclusion](#conclusion)

## Executive Summary

vlog is a video logging and analysis application that uses machine learning (MLX-VLM) to automatically classify, transcribe, and describe video clips. The system combines multiple technologies into an integrated workflow for ingesting videos from cameras/SD cards, analyzing them with AI, and exporting them to video editing software (DaVinci Resolve).

**Current Status:** The project is in active development with a functional core pipeline. Recent work has focused on improving web UI responsiveness, auto-ingest reliability, and workflow monitoring capabilities.

## Quick Start for New Engineers

### Prerequisites
- macOS with Apple Silicon (for MLX support)
- Python 3.11+ (3.13 recommended, pinned in `.python-version`)
- uv package manager (recommended)
- FFmpeg (for video processing)
- Protocol Buffers compiler (optional, for schema changes)

### Getting Started
```bash
# Clone the repository
git clone https://github.com/kagelump/vlog.git
cd vlog

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up the environment
uv python pin 3.13
uv venv
uv sync

# Run tests to verify setup
make test  # or: uv run -- pytest

# Start the web UI
uv run -- python -m vlog.web
# Open http://localhost:5432 in browser
```

### Key Documentation to Read First
1. **README.md** - Overview and basic usage
2. **docs/PROJECT_STRUCTURE.md** - Code organization
3. **docs/SNAKEMAKE_QUICKSTART.md** - Workflow basics
4. **docs/AUTO_INGEST_SNAKEMAKE.md** - Auto-processing setup
5. **This document** - Current state and next steps

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                          │
├──────────────────┬──────────────────┬──────────────────────┤
│  Launcher UI     │  Results Viewer  │  DaVinci Resolve    │
│  (launcher.html) │  (index.html)    │  Integration        │
└────────┬─────────┴────────┬─────────┴──────────┬───────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌────────────────────────────────────────────────────────────┐
│                    Flask Web Server                         │
│                      (web.py)                               │
├────────────────┬─────────────────┬─────────────────────────┤
│  Launcher API  │  Results API    │  Auto-Ingest API        │
└────────┬───────┴────────┬────────┴──────────┬──────────────┘
         │                │                    │
         ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   Processing Layer                           │
├──────────────────┬──────────────────┬──────────────────────┤
│  Snakemake       │  Describe        │  Auto-Ingest         │
│  Workflows       │  Daemon          │  Service             │
│  (workflows/)    │  (FastAPI)       │  (watchdog)          │
└────────┬─────────┴────────┬─────────┴──────────┬───────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data & Storage                            │
├──────────────────┬──────────────────┬──────────────────────┤
│  SQLite Database │  Video Files     │  JSON Outputs        │
│  (video_results  │  (main/preview)  │  (workflow results)  │
│   .db)           │                  │                      │
└──────────────────┴──────────────────┴──────────────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   ML/Processing Layer                        │
├──────────────────┬──────────────────┬──────────────────────┤
│  MLX-VLM         │  MLX-Whisper     │  OpenCV              │
│  (video desc)    │  (transcription) │  (thumbnails)        │
└──────────────────┴──────────────────┴──────────────────────┘
```

### Technology Stack

**Languages & Frameworks:**
- Python 3.13 (core application)
- HTML/CSS/JavaScript (web UI)
- Snakemake (workflow orchestration)
- Protocol Buffers (data schema)

**Key Dependencies:**
- **Flask** - Web server for launcher and results viewer
- **FastAPI/Uvicorn** - Async API for description daemon
- **MLX-VLM** - Vision language model for video analysis
- **MLX-Whisper** - Audio transcription
- **Snakemake** - Workflow management
- **Watchdog** - File system monitoring (auto-ingest)
- **OpenCV (cv2)** - Video processing
- **SQLite3** - Database (built-in)

**Package Management:**
- **UV** - Modern Python package manager (recommended)
- All dependencies in `pyproject.toml` with locked versions in `uv.lock`

## Project Structure

```
vlog/
├── src/vlog/                      # Main package (all installable code)
│   ├── workflows/                 # Snakemake orchestration
│   │   ├── Snakefile              # Master workflow
│   │   ├── snakefiles/            # Stage-specific workflows
│   │   │   ├── copy.smk           # Stage 1: Copy from SD card
│   │   │   ├── subtitles.smk      # Stage 2: Transcribe & clean
│   │   │   ├── describe.smk       # Stage 3: AI description
│   │   │   └── daemon.smk         # Daemon lifecycle
│   │   └── scripts/               # Workflow helper scripts
│   ├── static/                    # Web UI assets
│   │   ├── index.html             # Results viewer dashboard
│   │   └── launcher/              # Launcher UI
│   ├── prompts/                   # AI model prompts
│   ├── snakemake_logger_plugin/   # Status logger plugin
│   ├── web.py                     # Flask application
│   ├── video.py                   # Video utilities
│   ├── describe_lib.py            # ML model integration
│   ├── describe_daemon.py         # FastAPI description service
│   ├── describe_client.py         # Daemon client
│   ├── auto_ingest_snakemake.py   # Auto-ingest service
│   └── davinci_clip_importer.py   # DaVinci integration
├── scripts/                       # User-facing executables
│   ├── ingest.sh                  # Manual ingestion
│   ├── launch_web.sh              # Start web server
│   └── ...                        # Other utilities
├── tests/                         # Test suite (pytest)
├── docs/                          # Documentation
├── examples/                      # Example configs
├── config.yaml                    # Working config (user-specific)
├── pyproject.toml                 # Dependencies & metadata
└── README.md                      # Main documentation
```

**Design Principles:**
1. **Src-layout:** All package code under `src/vlog/` following modern Python conventions
2. **Package data co-location:** Static files, prompts, workflows within package for portability
3. **Clear separation:** User scripts vs. workflow scripts vs. package modules
4. **Configuration-driven:** YAML config files for workflow settings

## Workflows & Processing Pipelines

### 1. Manual Ingestion (`scripts/ingest.sh`)
**Use Case:** Quick processing of local videos

**Steps:**
1. Transcribe audio → `.srt` files
2. Clean subtitles (remove duplicates/hallucinations)
3. Describe video using MLX-VLM
4. Save results to database

**When to Use:** Ad-hoc processing of individual videos or small batches

### 2. Snakemake Pipeline (Staged)
**Use Case:** Importing from SD cards with organized file structure

**Stages:**
1. **Copy** (`copy.smk`) - Copy main videos and create/copy preview files
2. **Subtitles** (`subtitles.smk`) - Transcribe and clean subtitle files
3. **Describe** (`describe.smk`) - Analyze videos and save to JSON

**Features:**
- Dependency tracking (only process changed files)
- Parallel processing support
- Configuration via `config.yaml`
- Status monitoring via logger plugin API

**When to Use:** Importing from cameras/SD cards, batch processing with previews

### 3. Auto-Ingest (Snakemake-based)
**Use Case:** Automated background processing of new files

**How it Works:**
1. Monitors directory with watchdog
2. Detects new video files
3. Triggers Snakemake pipeline for each file
4. Provides REST API for control (start/stop/status)
5. Reports progress via logger plugin

**Features:**
- Idempotent (skips already-processed files)
- Real-time progress tracking
- Configurable resource limits
- Web UI integration

**When to Use:** Continuous monitoring and automatic processing

### 4. Describe Daemon
**Use Case:** Long-running or distributed description workloads

**Architecture:**
- FastAPI service for async processing
- Client/server model
- Can run on different machines
- Managed by Snakemake or manually

**When to Use:** High-volume processing, distributed compute

## Database Schema

**Primary Table:** `video_results.db` → `results`

**Key Fields:**
- `filename` (PRIMARY KEY) - Video filename
- `video_description_long` - AI-generated long description
- `video_description_short` - AI-generated short description
- `primary_shot_type` - pov, insert, establishing, aerial, etc.
- `tags` - JSON array: [static, dynamic, closeup, medium, wide]
- `video_length_seconds` - Duration
- `video_timestamp` - File creation time
- `video_thumbnail_base64` - JPEG thumbnail (base64)
- `keep` - Boolean flag (1=keep, 0=discard, default: 1)
- `in_timestamp` - Clip start time (HH:MM:SS.sss)
- `out_timestamp` - Clip end time (HH:MM:SS.sss)
- `rating` - Quality rating (0.0 - 1.0)
- `segments` - JSON array of in/out timestamps (multiple segments per video)
- `classification_time_seconds` - Processing time
- `classification_model` - Model name used
- `last_updated` - ISO timestamp

**Schema Definition:** Also available in Protocol Buffers format (`src/proto/describe.proto`)

## Recent Changes & Fixes

### Web Server Responsiveness (Fixed)
**Problem:** Web server became unresponsive during auto-ingest  
**Cause:** Lock held for entire Snakemake execution (minutes to hours)  
**Solution:** Refactored lock scope to only protect critical sections  
**Impact:** Web UI now remains responsive during long-running workflows  
**Documentation:** `docs/FIX_WEB_RESPONSIVENESS.md`

### Auto-Ingest Progress Monitoring (Fixed)
**Problem:** Progress endpoint returned connection errors  
**Cause:** Logger plugin not configured with port, no initial workflow trigger  
**Solution:** Added logger port configuration, trigger initial Snakemake run on start  
**Impact:** Progress monitoring now works immediately after starting auto-ingest  
**Documentation:** `docs/AUTO_INGEST_PROGRESS_FIX.md`

### Expected Total Feature (Added)
**Problem:** No visibility into total work planned vs. completed  
**Solution:** Added `expected_total` tracking in logger plugin  
**Impact:** Progress bars now show complete picture including already-done work  
**Documentation:** `docs/EXPECTED_TOTAL_FEATURE.md`

### Dashboard Debugging (Added)
**Problem:** Empty state UX was confusing, hard to debug issues  
**Solution:** Added debugging info panel, improved empty state messaging  
**Impact:** Better visibility into what's happening when no videos are displayed  
**PR:** #34

## Testing Infrastructure

### Test Suite Overview
- **Framework:** pytest with pytest-cov
- **Total Tests:** 2,725 lines across 15 test files
- **Coverage:** ~85-93% for core modules
- **Run Command:** `make test` or `uv run -- pytest`

### Test Categories

**Unit Tests:**
- `test_video.py` - Video processing utilities (8 tests)
- `test_web.py` - Flask API endpoints (24 tests)
- `test_prompts.py` - Prompt loading and validation
- `test_directory_browser.py` - File browser utility

**Integration Tests:**
- `test_snakemake_workflow.py` - End-to-end workflow tests
- `test_auto_ingest_snakemake.py` - Auto-ingest functionality
- `test_logger_integration.py` - Logger plugin API
- `test_davinci_importer.py` - DaVinci Resolve integration
- `test_audio_processing_integration.py` - Audio processing pipeline
- `test_vad_transcribe.py` - Voice activity detection

**Manual Tests:**
- `manual_test_web_responsiveness.py` - Web server responsiveness verification

### Test Fixtures
- `tests/conftest.py` - Shared fixtures for database and file setup
- Temporary databases and files (no pollution of dev environment)

### Coverage Highlights
- **db.py:** 93% - Database operations
- **video.py:** 85% - Video processing
- **web.py:** 88% - Web API endpoints

## Configuration Management

### Main Config File: `config.yaml`
**Location:** Project root (user-specific, not in git)  
**Example:** `examples/config.yaml`

**Key Sections:**
```yaml
# SD card and output paths
sd_card_path: "/Volumes/SDCARD"
main_folder: "videos/main"
preview_folder: "videos/preview"

# Video processing
video_extensions: ["mp4", "MP4", "mov", "MOV"]
preview_settings:
  width: 1280
  crf: 23
  preset: "medium"

# ML models
transcribe:
  model: "mlx-community/whisper-large-v3-turbo"
describe:
  model: "mlx-community/Qwen3-VL-8B-Instruct-4bit"

# Daemon settings
daemon_host: "127.0.0.1"
daemon_port: 5555
```

### Prompt Configuration
**Location:** `src/vlog/prompts/`  
**Format:** YAML + Markdown (Jinja2 templates)  
**Primary Prompt:** `describe_v1.yaml` and `describe_v1.md`

## Known Issues & Technical Debt

### High Priority

#### 1. UV Not Installed in CI/CD
**Issue:** The `uv` package manager is not available in the environment  
**Impact:** Cannot run tests or verify setup in automated environments  
**Workaround:** Fall back to direct `python3` usage  
**Fix Needed:** Add `uv` installation to CI/CD setup or provide fallback scripts

#### 2. Static File Duplication
**Issue:** HTML files exist in both `static/` and `src/vlog/static/`  
**Impact:** Confusion about which is canonical, potential inconsistency  
**Root Cause:** Migration to src-layout not fully complete  
**Fix Needed:** Remove `static/` directory at root, update all references to use `src/vlog/static/`

#### 3. Database Migration Strategy
**Issue:** No formal database migration system  
**Impact:** Schema changes require manual database updates or recreation  
**Current Approach:** Drop and recreate database  
**Fix Needed:** Add Alembic or similar migration tool

#### 4. Error Handling in Workflows
**Issue:** Some workflow scripts lack comprehensive error handling  
**Impact:** Failures may be silent or produce unclear error messages  
**Fix Needed:** Add try/except blocks with proper logging throughout workflow scripts

### Medium Priority

#### 5. Test Coverage Gaps
**Areas Needing Tests:**
- SRT cleaner edge cases
- Daemon lifecycle management
- Error conditions in auto-ingest
- File browser security (path traversal)

#### 6. Documentation Inconsistencies
**Issues:**
- Some docs reference old file locations
- Missing API documentation for new endpoints
- No architecture diagrams (except timing diagram)

**Fix Needed:** 
- Update all docs for new structure
- Add OpenAPI/Swagger docs for APIs
- Create architecture diagrams

#### 7. Python Version Mismatch
**Issue:** `.python-version` says 3.13, but `pyproject.toml` requires >=3.11  
**Impact:** Minor confusion about required version  
**Fix Needed:** Align version requirements or document the strategy

#### 8. Hardcoded Paths and Constants
**Examples:**
- Logger plugin port (5556) hardcoded in multiple places
- Default directories scattered across modules
- Magic numbers in video processing

**Fix Needed:** Centralize configuration in a settings module

### Low Priority

#### 9. Code Organization
**Areas for Improvement:**
- Some modules are large (web.py is 23KB, 700+ lines)
- Could benefit from splitting into smaller modules
- Some utility functions could be shared better

#### 10. Dependency Version Pinning
**Issue:** Some dependencies use `>=` which could lead to breakage  
**Current:** Partially mitigated by `uv.lock`  
**Consideration:** Review if stricter pinning is needed for stability

#### 11. Legacy Code
**Files with "old" suffix:**
- `src/vlog/static/index_old.html`

**Fix Needed:** Remove once new version is confirmed stable

## Improvement Opportunities

### Usability Improvements

#### 1. **Better First-Run Experience**
**Current State:** User must manually create `config.yaml`, set paths  
**Improvement:** 
- Add setup wizard in web UI
- Auto-detect common SD card paths
- Provide interactive config builder
- Copy `examples/config.yaml` to `config.yaml` on first run

**Effort:** Medium | **Impact:** High

#### 2. **Progress Visibility Enhancements**
**Current State:** Progress available but could be clearer  
**Improvement:**
- Show estimated time remaining
- Add progress history/charts
- Notification system for completion
- Better error messages with actionable suggestions

**Effort:** Medium | **Impact:** Medium

#### 3. **Results Viewer Improvements**
**Current State:** View-only, functional but basic  
**Improvement:**
- Add bulk operations (mark multiple as keep/discard)
- Export to CSV/JSON for analysis
- Advanced filtering (date ranges, multiple tags)
- Video player with in/out point editing
- Side-by-side comparison view

**Effort:** High | **Impact:** High

#### 4. **Mobile/Tablet Support**
**Current State:** Web UI designed for desktop  
**Improvement:**
- Responsive design for smaller screens
- Touch-friendly controls
- Progressive Web App (PWA) capabilities

**Effort:** High | **Impact:** Medium

#### 5. **Better Documentation**
**Current State:** Good docs but could be more discoverable  
**Improvement:**
- In-app help and tutorials
- Video walkthroughs
- FAQ section
- Troubleshooting guide with common issues
- Interactive examples

**Effort:** Medium | **Impact:** Medium

#### 6. **Keyboard Shortcuts**
**Current State:** Limited keyboard navigation  
**Improvement:**
- Comprehensive keyboard shortcuts
- Shortcuts cheat sheet (? key)
- Vim-style navigation option
- Customizable shortcuts

**Effort:** Low | **Impact:** Low

### Maintainability Improvements

#### 1. **Automated Testing Enhancement**
**Current State:** Good coverage but gaps exist  
**Improvement:**
- Increase coverage to 95%+
- Add integration tests for all workflows
- Performance regression tests
- Visual regression tests for UI
- Mutation testing

**Effort:** High | **Impact:** High

#### 2. **CI/CD Pipeline**
**Current State:** No automated CI/CD visible  
**Improvement:**
- GitHub Actions for tests on PR
- Automated code quality checks (ruff, mypy)
- Automated dependency updates (Dependabot)
- Automated releases with changelog
- Docker images for easy deployment

**Effort:** Medium | **Impact:** High

#### 3. **Code Quality Tools**
**Current State:** No linting/formatting enforced  
**Improvement:**
- Add ruff for linting and formatting
- Add mypy for type checking
- Pre-commit hooks
- Automated code review (CodeRabbit, etc.)

**Effort:** Low | **Impact:** Medium

#### 4. **Logging & Monitoring**
**Current State:** Basic logging, no monitoring  
**Improvement:**
- Structured logging (JSON logs)
- Log aggregation (ELK stack or similar)
- Metrics collection (Prometheus)
- Health check endpoints
- Alerting for failures

**Effort:** High | **Impact:** Medium

#### 5. **Dependency Management**
**Current State:** UV-based, good but could be better documented  
**Improvement:**
- Document UV usage thoroughly
- Automated dependency vulnerability scanning
- Clear upgrade strategy
- Dependency graph visualization
- License compliance checking

**Effort:** Low | **Impact:** Low

#### 6. **Error Handling & Recovery**
**Current State:** Basic error handling  
**Improvement:**
- Graceful degradation strategies
- Automatic retry logic for transient failures
- Detailed error reporting with context
- Recovery procedures documentation
- Error aggregation and analysis

**Effort:** Medium | **Impact:** Medium

#### 7. **Performance Optimization**
**Current State:** Functional but not optimized  
**Improvement:**
- Profile and optimize hot paths
- Batch processing optimization
- Database query optimization
- Caching strategies
- Async processing where beneficial

**Effort:** High | **Impact:** Medium

#### 8. **Security Hardening**
**Current State:** Basic security, no formal audit  
**Improvement:**
- Security audit and penetration testing
- Input validation everywhere
- HTTPS support
- Authentication/authorization system
- Rate limiting
- CSRF protection
- Content Security Policy

**Effort:** High | **Impact:** High

#### 9. **Code Modularity**
**Current State:** Some large modules  
**Improvement:**
- Split large files into logical modules
- Extract common utilities
- Create plugin system for extensibility
- Better separation of concerns
- Interface definitions

**Effort:** Medium | **Impact:** Medium

#### 10. **Database Improvements**
**Current State:** SQLite, functional  
**Improvement:**
- Add migration system (Alembic)
- Database versioning
- Backup/restore utilities
- Optional PostgreSQL support for scale
- Query optimization
- Indexing strategy

**Effort:** Medium | **Impact:** Medium

## Priority Action Items

### Immediate (This Week)

1. **Fix Static File Duplication** (2 hours)
   - Remove root `static/` directory
   - Update all references
   - Verify web server serves correctly

2. **Document UV Installation** (1 hour)
   - Add troubleshooting section
   - Provide alternatives if UV unavailable

3. **Add Setup Wizard** (4 hours)
   - Auto-copy example config
   - Detect common paths
   - Guide through first-time setup

### Short Term (This Month)

4. **Enhance Test Coverage** (8 hours)
   - Add missing tests for workflow scripts
   - Test error conditions
   - Integration tests for auto-ingest

5. **Add CI/CD Pipeline** (6 hours)
   - GitHub Actions for tests
   - Code quality checks
   - Automated dependency updates

6. **Improve Error Messages** (4 hours)
   - Add context to errors
   - Suggest fixes
   - Better logging

7. **Database Migration System** (6 hours)
   - Add Alembic
   - Create initial migration
   - Document migration process

### Medium Term (Next Quarter)

8. **Results Viewer Enhancements** (16 hours)
   - Bulk operations
   - CSV/JSON export
   - Advanced filtering
   - Video player with editing

9. **Performance Optimization** (12 hours)
   - Profile hot paths
   - Optimize database queries
   - Implement caching

10. **Security Hardening** (12 hours)
    - Input validation audit
    - Add authentication
    - HTTPS support
    - Security testing

11. **Documentation Overhaul** (8 hours)
    - Update all docs for new structure
    - Add API documentation
    - Create architecture diagrams
    - Video tutorials

### Long Term (Next 6 Months)

12. **Mobile/Tablet Support** (24 hours)
    - Responsive design
    - PWA capabilities
    - Touch optimization

13. **Plugin System** (20 hours)
    - Define plugin interfaces
    - Create example plugins
    - Documentation

14. **Monitoring & Observability** (16 hours)
    - Metrics collection
    - Log aggregation
    - Alerting system
    - Dashboards

## Development Workflow

### Making Changes

1. **Create a branch** following naming convention:
   ```bash
   git checkout -b feature/description
   # or
   git checkout -b fix/bug-description
   ```

2. **Make minimal changes** following these principles:
   - Change as few lines as possible
   - Don't modify working code unless necessary
   - Preserve existing behavior
   - Add tests for new functionality

3. **Test thoroughly:**
   ```bash
   # Run full test suite
   make test
   
   # Run specific tests
   uv run -- pytest tests/test_web.py -v
   
   # Check coverage
   uv run -- pytest --cov=src/vlog --cov-report=html
   ```

4. **Lint and format** (when tools are set up):
   ```bash
   # Will be: ruff check src/
   # Will be: ruff format src/
   ```

5. **Update documentation** if needed

6. **Commit with clear messages:**
   ```bash
   git commit -m "Add feature X: description"
   ```

7. **Create PR** with:
   - Clear description of changes
   - Link to related issues
   - Screenshots for UI changes
   - Test results

### Running the Application

**Development mode:**
```bash
# Start web server
uv run -- python -m vlog.web

# Or with custom port
uv run -- python -m vlog.web --port 8080

# Start describe daemon
uv run -- python -m vlog.describe_daemon --port 5555
```

**Processing videos:**
```bash
# Manual ingestion
cd /path/to/videos
/path/to/vlog/scripts/ingest.sh

# Snakemake pipeline
cd /path/to/vlog
snakemake --cores 1 --configfile config.yaml

# With status logger
python scripts/run_with_status_logger.py
```

## Getting Help

### Resources
- **README.md** - Quick start and overview
- **docs/** - Detailed documentation
- **tests/** - Examples of usage
- **examples/** - Sample configurations

### Common Questions

**Q: How do I add a new model?**  
A: Update `config.yaml` with model name, ensure it's available via MLX

**Q: How do I change the prompt?**  
A: Edit `src/vlog/prompts/describe_v1.md` (Jinja2 template)

**Q: Why is my video not being processed?**  
A: Check file extension, path, and logs. Ensure database doesn't already have it.

**Q: How do I reset the database?**  
A: Delete `video_results.db` file. No migration system currently.

**Q: Can I run this on Windows/Linux?**  
A: MLX requires macOS with Apple Silicon. Other components could work elsewhere with modifications.

## Conclusion

The vlog project is a well-structured application with a solid foundation. Recent fixes have improved reliability and user experience. The main opportunities for improvement are:

1. **Usability:** Better onboarding, more intuitive UI, mobile support
2. **Maintainability:** CI/CD, testing, code quality tools, monitoring
3. **Documentation:** Keep up-to-date, add visual aids, in-app help
4. **Performance:** Optimization, caching, async processing
5. **Security:** Hardening, authentication, vulnerability scanning

The project is ready for both new feature development and systematic improvement of existing functionality. The modular architecture and good test coverage provide a strong foundation for future work.

---

**Next Steps for New Engineers:**
1. Set up development environment following Quick Start
2. Run tests to verify setup
3. Start web UI and explore the interface
4. Process a few test videos to understand the workflow
5. Pick an item from Priority Action Items and contribute!

**Questions?** Check documentation in `docs/` or create an issue on GitHub.
