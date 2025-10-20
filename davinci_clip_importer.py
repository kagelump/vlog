# resolve_clip_importer.py
#
# INSTRUCTIONS:
# 1. Place this file and 'clip_data.json' in the same directory.
# 2. IMPORTANT: Run this script from the DaVinci Resolve application's built-in Python console,
#    or from an external Python environment configured to access the Resolve API.

import json
import os
import re

# --- Configuration ---
JSON_FILE_PATH = "/Users/ryantseng/Desktop/2025 Yakushima/Pocket/clip_data.json"
PROJECT_NAME = "Automated Timeline Setup"
PROJECT_FPS = 60.0  # Set this to your project's frame rate (e.g., 24.0, 25.0, 29.97, 30.0)
# ---------------------

def timestamp_to_frames(timestamp_str, fps):
    """
    Converts a HH:MM:SS.sss timestamp string to a frame number based on FPS.
    """
    try:
        # Regex to parse HH:MM:SS.sss format
        match = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})', timestamp_str)
        if not match:
            print(f"Error: Invalid timestamp format for '{timestamp_str}'. Expected HH:MM:SS.sss")
            return -1

        H, M, S, ms = map(int, match.groups())

        total_seconds = H * 3600 + M * 60 + S + ms / 1000.0
        # Round the result to the nearest whole frame for accuracy
        return int(round(total_seconds * fps))

    except Exception as e:
        print(f"Error converting timestamp '{timestamp_str}': {e}")
        return -1

def run_resolve_script():
    """
    The main function to execute the Resolve API workflow.
    """
    # 1. Access the DaVinci Resolve application object
    try:
        # This is the standard way to access the Resolve object in the scripting environment
        resolve = __import__("DaVinciResolveScript").scriptapp("Resolve")
    except Exception as e:
        print(f"Error: Could not access DaVinci Resolve application. Check your environment setup.")
        print(f"Details: {e}")
        return

    if not resolve:
        print("Error: DaVinci Resolve object is null.")
        return

    # 2. Load the clip data from JSON
    print(f"Loading data from: {os.path.abspath(JSON_FILE_PATH)}")
    if not os.path.exists(JSON_FILE_PATH):
        print(f"FATAL ERROR: JSON file not found at '{JSON_FILE_PATH}'. Please ensure it exists.")
        return

    try:
        with open(JSON_FILE_PATH, 'r') as f:
            data = json.load(f)
            clips_to_process = data.get("clips", [])
    except json.JSONDecodeError:
        print(f"FATAL ERROR: Could not decode JSON from '{JSON_FILE_PATH}'. Check file syntax.")
        return
    except Exception as e:
        print(f"FATAL ERROR reading JSON file: {e}")
        return

    if not clips_to_process:
        print("Warning: 'clips' list is empty or missing in the JSON file. Exiting.")
        return

    # 3. Create and open a new project
    project_manager = resolve.GetProjectManager()
    if not project_manager:
        print("Error: Could not get Project Manager.")
        return

    # Create a new project
    project = project_manager.CreateProject(PROJECT_NAME)
    if not project:
        # If creation fails (e.g., project already exists), try opening it
        project = project_manager.OpenProject(PROJECT_NAME)
        if not project:
            print(f"FATAL ERROR: Could not create or open project '{PROJECT_NAME}'.")
            return
            
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

    for clip in clips_to_process:
        full_path = clip["filename"]
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
    
    print(f"Successfully imported {len(imported_items)} items.")

    # Map imported Media Pool Item objects to their full file path for easy lookup
    item_map = {item.GetClipProperty("File Path"): item for item in imported_items}

    # 6. Process clips: Set in/out points and rename
    print("Applying metadata (Clip In/Out, Short Name) to imported clips...")
    
    processed_count = 0
    for full_path, clip_data in clip_map.items():
        media_pool_item = item_map.get(full_path)

        if media_pool_item:
            in_ts = clip_data["in_timestamp"]
            out_ts = clip_data["out_timestamp"]
            short_name = clip_data["short_name"]

            # Convert timestamps to frames
            in_frame = timestamp_to_frames(in_ts, PROJECT_FPS)
            out_frame = timestamp_to_frames(out_ts, PROJECT_FPS)

            if in_frame == -1 or out_frame == -1:
                print(f"Skipping '{short_name}' due to timestamp conversion error.")
                continue

            # Set Clip Properties (Resolve requires frame numbers as strings)
            media_pool_item.SetClipProperty("ClipIn", str(in_frame))
            media_pool_item.SetClipProperty("ClipOut", str(out_frame))
            media_pool_item.SetClipProperty("ClipName", short_name)
            processed_count += 1

            print(f"-> Set: '{short_name}' | In: {in_ts} | Out: {out_ts}")
        else:
            print(f"Warning: Imported item for path '{full_path}' could not be found in the Media Pool map. Skipping properties set.")

    print(f"\n--- Script Complete ---")
    print(f"Total Clips Processed: {processed_count}")
    print(f"Project '{PROJECT_NAME}' is ready in DaVinci Resolve.")

if __name__ == "__main__":
    run_resolve_script()
