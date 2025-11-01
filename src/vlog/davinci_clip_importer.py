# resolve_clip_importer.py
#
# INSTRUCTIONS:
# 1. Copy this file to DaVinci Resolve's script directory
# 2. Set the VLOG_PROJECT_PATH environment variable to point to your vlog project directory
#    Example: export VLOG_PROJECT_PATH=/path/to/vlog/project
# 3. IMPORTANT: Run this script from the DaVinci Resolve application's built-in Python console,
#    or from an external Python environment configured to access the Resolve API.
#
# CONFIGURATION OPTIONS:
# - VLOG_PROJECT_PATH: Environment variable pointing to vlog project directory (required)
# - VLOG_DB_FILE: Optional override for database filename (default: video_results.db)
# - VLOG_JSON_FILE: Optional override for JSON output filename (default: extracted_clips.json)
# - VLOG_AUTO_EXTRACT: Set to "1" to auto-generate JSON from database (default: 0)

import json
import os
import re
import sys

# --- Configuration ---
# Try to find vlog project path from environment variable
VLOG_PROJECT_PATH = os.environ.get("VLOG_PROJECT_PATH")

# Configuration defaults (can be overridden by environment variables)
DB_FILE = os.environ.get("VLOG_DB_FILE", "video_results.db")
JSON_FILE = os.environ.get("VLOG_JSON_FILE", "extracted_clips.json")
AUTO_EXTRACT = os.environ.get("VLOG_AUTO_EXTRACT", "0") == "1"

PROJECT_NAME = "Automated Timeline Setup"
PROJECT_FPS = 60.0  # Set this to your project's frame rate (e.g., 24.0, 25.0, 29.97, 30.0)
# ---------------------

def setup_vlog_imports():
    """
    Setup Python path to import vlog modules.
    Looks for VLOG_PROJECT_PATH environment variable or attempts to find via config.
    Returns the project path if successful, None otherwise.
    """
    # Read from environment variable at runtime
    project_path = os.environ.get("VLOG_PROJECT_PATH")
    
    # Try to read from config file if environment variable not set
    if not project_path:
        config_locations = [
            os.path.expanduser("~/.vlog/config"),
            os.path.expanduser("~/.config/vlog/config"),
        ]
        for config_file in config_locations:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        for line in f:
                            if line.startswith("PROJECT_PATH="):
                                project_path = line.split("=", 1)[1].strip()
                                break
                    if project_path:
                        break
                except Exception as e:
                    print(f"Warning: Could not read config file {config_file}: {e}")
    
    if not project_path:
        print("ERROR: VLOG_PROJECT_PATH not set!")
        print("Please set the VLOG_PROJECT_PATH environment variable to your vlog project directory.")
        print("Example: export VLOG_PROJECT_PATH=/path/to/vlog/project")
        print("")
        print("Alternatively, create a config file at ~/.vlog/config with:")
        print("PROJECT_PATH=/path/to/vlog/project")
        return None
    
    if not os.path.isdir(project_path):
        print(f"ERROR: VLOG_PROJECT_PATH directory does not exist: {project_path}")
        return None
    
    # Add vlog src directory to Python path
    src_path = os.path.join(project_path, "src")
    if not os.path.isdir(src_path):
        print(f"ERROR: Could not find src directory in project path: {src_path}")
        return None
    
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        print(f"Added to Python path: {src_path}")
    
    return project_path

def get_json_path(project_path):
    """Get the full path to the JSON file."""
    json_file = os.environ.get("VLOG_JSON_FILE", "extracted_clips.json")
    if os.path.isabs(json_file):
        return json_file
    return os.path.join(project_path, json_file)

def ensure_json_file(project_path):
    """
    Ensure the JSON file exists by extracting from database if needed.
    Returns the path to the JSON file, or None on error.
    """
    json_path = get_json_path(project_path)
    db_file = os.environ.get("VLOG_DB_FILE", "video_results.db")
    db_path = os.path.join(project_path, db_file)
    auto_extract = os.environ.get("VLOG_AUTO_EXTRACT", "0") == "1"
    
    # Check if we should auto-extract
    if auto_extract or not os.path.exists(json_path):
        if not os.path.exists(db_path):
            print(f"ERROR: Database file not found: {db_path}")
            return None
        
        print(f"Extracting clip data from database: {db_path}")
        try:
            # Import vlog module
            from vlog import db_extract_v2
            
            # Extract data to JSON
            db_extract_v2.extract_and_write_json(
                db_file=db_path,
                json_file=json_path,
                csv_file=os.path.join(project_path, "extracted_clips.csv"),
                rename_files=False
            )
            print(f"Successfully extracted clip data to: {json_path}")
        except ImportError as e:
            print(f"ERROR: Could not import vlog.db_extract_v2: {e}")
            print("Make sure the vlog project is properly set up.")
            return None
        except Exception as e:
            print(f"ERROR: Failed to extract clip data: {e}")
            return None
    
    if not os.path.exists(json_path):
        print(f"ERROR: JSON file not found: {json_path}")
        print("Set VLOG_AUTO_EXTRACT=1 environment variable to auto-generate from database.")
        return None
    
    return json_path

def timestamp_to_frames(timestamp_str, fps):
    """
    Converts a HH:MM:SS.sss timestamp string to a frame number based on FPS.
    """
    try:
        # Regex to parse HH:MM:SS.sss format
        match = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})', timestamp_str)
        if match:
            H, M, S, ms = map(int, match.groups())
            total_seconds = H * 3600 + M * 60 + S + ms / 1000.0
        else:
            match = re.match(r'(\d{2}):(\d{2}):(\d{2})', timestamp_str)
            H, M, S  = map(int, match.groups())
            total_seconds = H * 3600 + M * 60 + S
            if not match:
                print(f"Error: Invalid timestamp format for '{timestamp_str}'. Expected HH:MM:SS.sss or HH:MM:SS")
                return -1

        
        # Round the result to the nearest whole frame for accuracy
        return int(round(total_seconds * fps))

    except Exception as e:
        print(f"Error converting timestamp '{timestamp_str}': {e}")
        return -1

def run_resolve_script():
    """
    The main function to execute the Resolve API workflow.
    """
    # 1. Setup vlog imports and get project path
    print("=" * 60)
    print("DaVinci Resolve Clip Importer - vlog Integration")
    print("=" * 60)
    
    project_path = setup_vlog_imports()
    if not project_path:
        print("\nFATAL ERROR: Could not setup vlog project integration.")
        print("Please configure VLOG_PROJECT_PATH before running this script.")
        return
    
    print(f"Using vlog project at: {project_path}")
    
    # 2. Ensure JSON file exists (extract from DB if needed)
    json_path = ensure_json_file(project_path)
    if not json_path:
        print("\nFATAL ERROR: Could not locate or generate clip data JSON file.")
        return
    
    # 3. Access the DaVinci Resolve application object
    try:
        # This is the standard way to access the Resolve object in the scripting environment
        resolve = app.GetResolve()
    except Exception as e:
        print(f"Error: Could not access DaVinci Resolve application. Check your environment setup.")
        print(f"Details: {e}")
        return

    if not resolve:
        print("Error: DaVinci Resolve object is null.")
        return

    # 4. Load the clip data from JSON
    print(f"\nLoading data from: {os.path.abspath(json_path)}")
    if not os.path.exists(json_path):
        print(f"FATAL ERROR: JSON file not found at '{json_path}'. Please ensure it exists.")
        return

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"FATAL ERROR: Could not decode JSON from '{json_path}'. Check file syntax.")
        return
    except Exception as e:
        print(f"FATAL ERROR reading JSON file: {e}")
        return


    project_manager = resolve.GetProjectManager()
    if not project_manager:
        print("Error: Could not get Project Manager.")
        return

    project = project_manager.GetCurrentProject()
            
    # Set the desired project frame rate for accurate frame calculation
    project.SetSetting("timelineFrameRate", str(PROJECT_FPS))
    print(f"Project '{PROJECT_NAME}' opened/created and project frame rate set to {PROJECT_FPS} FPS.")

    # 4. Access the Media Pool and prepare file list
    media_pool = project.GetMediaPool()
    if not media_pool:
        print("Error: Could not get Media Pool.")
        project_manager.CloseProject(project)
        return

    # Separate existing files from missing files
    file_paths_to_import = []
    clip_map = {} # Map full path to clip data for later processing

    for clip in data:
        full_path = clip["full_filepath"]
        if os.path.exists(full_path):
            file_paths_to_import.append(full_path)
            clip_map[full_path] = clip
        else:
            print(f"WARNING: File not found: {full_path}. Skipping import.")

    if not file_paths_to_import:
        print("Error: No existing files found to import after checking paths. Exiting.")
        project_manager.CloseProject(project)
        return

    # 5. Import the clips
    print(f"Attempting to import {len(file_paths_to_import)} existing files...")
    imported_items = media_pool.ImportMedia(file_paths_to_import)

    if not imported_items:
        print("FATAL ERROR: Resolve failed to import media files.")
        project_manager.CloseProject(project)
        return
    
    print(f"Successfully imported {len(imported_items)} items:")

    # Map imported Media Pool Item objects to their full file path for easy lookup
    item_map = dict()
    for item in imported_items:
        full_path = item.GetClipProperty("File Path")
        clip_data = clip_map[full_path]
        item_map[full_path] = (item, clip_data)

    print("Create empty timeline")
    media_pool.CreateEmptyTimeline("timeline")

    print("Applying metadata (Clip In/Out, Short Name) to imported clips...")
    
    processed_count = 0
    sorted_clips = []
    for full_path in sorted(item_map):
        media_pool_item, clip_data = item_map[full_path]

        sorted_clips.append(media_pool_item)
        print('media path: ', full_path)
        print('media_pool_item: ', media_pool_item)
        in_ts = clip_data["in_timestamp"]
        out_ts = clip_data["out_timestamp"]
        short_name = clip_data["video_description_short"]

        # Convert timestamps to frames
        in_frame = timestamp_to_frames(in_ts, PROJECT_FPS)
        out_frame = timestamp_to_frames(out_ts, PROJECT_FPS)

        if in_frame == -1 or out_frame == -1:
            print(f"Skipping '{short_name}' due to timestamp conversion error.")
            continue

        # Set Clip Properties (Resolve requires frame numbers as strings)
        print(media_pool_item.GetName())
        print(media_pool_item.GetMarkInOut())
        print(media_pool_item.GetClipProperty())
        media_pool_item.SetClipProperty("Clip Name", short_name)
        media_pool_item.SetMarkInOut(in_frame, out_frame, type=all)
        print('Appending to timeline: ', media_pool.AppendToTimeline(media_pool_item))
        processed_count += 1

        print(f"-> Set: '{short_name}' | In: {in_ts} | Out: {out_ts}")


    print(f"\n--- Script Complete ---")
    print(f"Total Clips Processed: {processed_count}")
    print(f"Project '{PROJECT_NAME}' is ready in DaVinci Resolve.")

if __name__ == "__main__":
    run_resolve_script()
