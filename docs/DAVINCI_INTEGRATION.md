# DaVinci Resolve Integration

This document explains how to use the `davinci_clip_importer.py` script to import vlog-classified video clips into DaVinci Resolve.

## Overview

The `davinci_clip_importer.py` script allows you to:
- Import video clips from your vlog project into DaVinci Resolve
- Automatically set in/out points based on vlog classifications
- Apply clip names based on the short descriptions from vlog
- Create a timeline with all clips in sorted order

## Setup

### Option 1: Using the Setup Script (Recommended)

Run the provided setup script to configure the integration:

```bash
./scripts/setup_davinci_config.sh
```

This creates a configuration file at `~/.vlog/config` with your project path.

### Option 2: Manual Environment Variable

Set the `VLOG_PROJECT_PATH` environment variable to point to your vlog project directory:

```bash
export VLOG_PROJECT_PATH=/path/to/your/vlog/project
```

For permanent configuration, add this to your shell profile (e.g., `~/.bashrc` or `~/.zshrc`).

### Option 3: Manual Config File

Create a config file at `~/.vlog/config` or `~/.config/vlog/config` with the following content:

```
PROJECT_PATH=/path/to/your/vlog/project
```

## Usage

### Step 1: Classify Your Videos

First, run the vlog classification on your videos as usual:

```bash
cd /path/to/your/video/directory
/path/to/vlog/scripts/ingest.sh
```

This creates a `video_results.db` database with classification data.

### Step 2: Copy the Importer Script to DaVinci Resolve

Copy the importer script to DaVinci Resolve's script directory:

**macOS:**
```bash
cp src/vlog/davinci_clip_importer.py "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/"
```

**Linux:**
```bash
cp src/vlog/davinci_clip_importer.py "$HOME/.local/share/DaVinciResolve/Fusion/Scripts/"
```

**Windows:**
```cmd
copy src\vlog\davinci_clip_importer.py "%APPDATA%\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\"
```

### Step 3: Run from DaVinci Resolve

1. Open DaVinci Resolve
2. Open the Console window: Workspace → Console
3. In the console, navigate to the script:
   ```python
   exec(open("/path/to/davinci_clip_importer.py").read())
   ```

Or use DaVinci Resolve's Script menu if available.

## Configuration Options

The script supports several environment variables for configuration:

- **VLOG_PROJECT_PATH** (required): Path to your vlog project directory
- **VLOG_DB_FILE** (optional): Database filename (default: `video_results.db`)
- **VLOG_JSON_FILE** (optional): JSON output filename (default: `extracted_clips.json`)
- **VLOG_AUTO_EXTRACT** (optional): Set to `1` to automatically extract clip data from database (default: `0`)

### Auto-Extract Mode

By default, the script looks for a pre-generated `extracted_clips.json` file. If you want the script to automatically generate this file from the database, set:

```bash
export VLOG_AUTO_EXTRACT=1
```

This is useful if you want to re-import clips after making changes in vlog's web UI.

## Workflow Example

Complete workflow from classification to DaVinci import:

```bash
# 1. Setup configuration (one-time)
cd /path/to/vlog
./scripts/setup_davinci_config.sh

# 2. Classify your videos
cd /path/to/your/videos
/path/to/vlog/scripts/ingest.sh

# 3. Review and edit classifications in vlog web UI
cd /path/to/vlog
./scripts/launch_web.sh
# Open http://localhost:5432 and review/edit clips

# 4. Extract clip data (optional if using auto-extract)
cd /path/to/your/videos
python /path/to/vlog/src/vlog/db_extract_v2.py

# 5. Copy importer to DaVinci (one-time)
cp /path/to/vlog/src/vlog/davinci_clip_importer.py \
   "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/"

# 6. Run in DaVinci Resolve
# Open DaVinci → Console → exec(open("davinci_clip_importer.py").read())
```

## Troubleshooting

### "VLOG_PROJECT_PATH not set" Error

Make sure you've either:
- Run `./scripts/setup_davinci_config.sh`, OR
- Set the `VLOG_PROJECT_PATH` environment variable, OR
- Created a config file at `~/.vlog/config`

### "Could not import vlog.db_extract_v2" Error

This usually means the vlog project path is incorrect or the project structure has changed. Verify:
- The path in your config points to the vlog project root
- The `src/vlog` directory exists in that path
- The `db_extract_v2.py` file exists in `src/vlog/`

### "JSON file not found" Error

Either:
- Run `python src/vlog/db_extract_v2.py` in your video directory to generate the JSON, OR
- Set `VLOG_AUTO_EXTRACT=1` to have the script generate it automatically

### "Database file not found" Error

Make sure:
- You're in the correct video directory
- You've run the vlog classification (ingest.sh)
- The `video_results.db` file exists

## Advanced Usage

### Custom Project FPS

Edit the `PROJECT_FPS` variable in `davinci_clip_importer.py` to match your project's frame rate:

```python
PROJECT_FPS = 24.0  # or 25.0, 29.97, 30.0, 60.0, etc.
```

### Custom Project Name

Edit the `PROJECT_NAME` variable:

```python
PROJECT_NAME = "My Video Project"
```

### Using Different Databases

If you have multiple video directories with different databases:

```bash
# Set the database file name
export VLOG_DB_FILE=my_custom_db.db

# Or specify full path to JSON
export VLOG_JSON_FILE=/full/path/to/clips.json
```

## Notes

- The script imports clips based on the `keep` flag in the database. Clips marked as "discard" are included.
- Clip in/out points are set based on the `in_timestamp` and `out_timestamp` fields from vlog.
- Clips are added to the timeline in sorted order by filename.
- The script uses the current DaVinci Resolve project; make sure you have a project open before running.
