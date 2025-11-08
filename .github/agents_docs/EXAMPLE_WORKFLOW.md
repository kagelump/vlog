# Complete Example: Processing Videos from SD Card

This document walks through a complete real-world example of using the Snakemake workflow to process videos from an SD card.

## Scenario

You've just finished filming with your camera and have a microSD card with the following files:

```
/Volumes/SDCARD/
├── CLIP001.MP4           (4K main file, 500MB)
├── CLIP001_preview.MP4   (HD preview file, 150MB)
├── CLIP002.MP4           (4K main file, 300MB)
└── CLIP003.mov           (4K main file, 450MB)
```

Note:
- CLIP001 has a preview file created by the camera
- CLIP002 and CLIP003 do not have preview files (we'll create them)

## Step 1: Setup

1. **Mount the SD card** and verify it's accessible:
   ```bash
   ls /Volumes/SDCARD
   # Should show: CLIP001.MP4  CLIP001_preview.MP4  CLIP002.MP4  CLIP003.mov
   ```

2. **Verify your environment**:
   ```bash
   cd /path/to/vlog
   ./scripts/verify_snakemake_env.py
   ```
   
   Expected output:
   ```
   ✅ Snakefile exists
   ✅ config.yaml exists
   ✅ snakemake is installed
   ✅ ffmpeg is installed
   ✅ mlx_whisper is installed
   ...
   ```

3. **Configure the workflow**:
   ```bash
   # Edit config.yaml
   nano config.yaml
   ```
   
   Update the SD card path:
   ```yaml
   sd_card_path: "/Volumes/SDCARD"
   main_folder: "videos/main"
   preview_folder: "videos/preview"
   ```

## Step 2: Preview the Workflow

Before running, let's see what will happen:

```bash
./scripts/run_snakemake.sh --dry-run
```

Expected output:
```
=== Snakemake Video Ingestion Workflow ===
Project root: /path/to/vlog
Cores: 1
Mode: DRY RUN (preview only)
===========================================

Building DAG of jobs...
Job stats:
job                       count
----------------------  -------
all                           1
clean_subtitles               3
copy_main                     3
copy_or_create_preview        3
describe                      3
transcribe                    3
total                        16

[Thu Nov 04 13:45:00 2024]
rule copy_main:
    input: /Volumes/SDCARD/CLIP001.MP4
    output: videos/main/CLIP001.mp4
    
[Thu Nov 04 13:45:00 2024]
rule copy_main:
    input: /Volumes/SDCARD/CLIP002.MP4
    output: videos/main/CLIP002.mp4
    
[Thu Nov 04 13:45:00 2024]
rule copy_main:
    input: /Volumes/SDCARD/CLIP003.mov
    output: videos/main/CLIP003.mp4
    
... (and so on for each rule)
```

This shows:
- ✅ 3 videos will be processed
- ✅ 16 total jobs will run (3 videos × 5 steps + 1 "all" rule)
- ✅ Each step and its inputs/outputs

## Step 3: Run the Workflow

Now let's process the videos:

```bash
./scripts/run_snakemake.sh
```

The workflow will execute the following steps for each video:

### For CLIP001 (has preview):

```
[1/16] Copying main file...
  Copy: /Volumes/SDCARD/CLIP001.MP4 → videos/main/CLIP001.mp4
  
[2/16] Copying preview file (already exists)...
  Copy: /Volumes/SDCARD/CLIP001_preview.MP4 → videos/preview/CLIP001.mp4
  
[3/16] Transcribing preview file...
  Running: mlx_whisper --model mlx-community/whisper-large-v3-turbo -f srt --task transcribe videos/preview/CLIP001.mp4
  Output: videos/preview/CLIP001.srt
  
[4/16] Cleaning subtitles...
  Processing: videos/preview/CLIP001.srt
  Removed 5 duplicate entries
  Removed 2 hallucinations
  Output: videos/preview/CLIP001_cleaned.srt
  
[5/16] Describing video...
  Loading model: mlx-community/Qwen3-VL-8B-Instruct-4bit
  Processing: videos/preview/CLIP001.mp4 with subtitles
  Using adaptive FPS: 1.0 for 45s video
  Classification time: 142.3s
  Output: videos/preview/CLIP001.json
```

### For CLIP002 (no preview - will create):

```
[6/16] Copying main file...
  Copy: /Volumes/SDCARD/CLIP002.MP4 → videos/main/CLIP002.mp4
  
[7/16] Creating preview file (doesn't exist on SD card)...
  Creating preview from: videos/main/CLIP002.mp4
  Running ffmpeg with: scale=1280:-1, crf=23, preset=medium
  Output: videos/preview/CLIP002.mp4
  
[8/16] Transcribing preview file...
  ...
```

### For CLIP003 (different extension):

```
[11/16] Copying main file...
  Copy: /Volumes/SDCARD/CLIP003.mov → videos/main/CLIP003.mp4
  
[12/16] Creating preview file...
  ...
```

## Step 4: Review Results

After ~15-20 minutes (depending on video length and hardware), the workflow completes:

```
Workflow complete!

Results are in:
  Main videos:    videos/main/
  Preview videos: videos/preview/
  JSON results:   videos/preview/*.json
```

### File Structure

Your workspace now looks like:

```
vlog/
├── videos/
│   ├── main/
│   │   ├── CLIP001.mp4           # Full-res main file (500MB)
│   │   ├── CLIP002.mp4           # Full-res main file (300MB)
│   │   └── CLIP003.mp4           # Full-res main file (450MB)
│   └── preview/
│       ├── CLIP001.mp4           # HD preview (150MB, copied)
│       ├── CLIP001.srt           # Original subtitles
│       ├── CLIP001_cleaned.srt   # Cleaned subtitles
│       ├── CLIP001.json          # ⭐ Description results
│       ├── CLIP002.mp4           # HD preview (90MB, created)
│       ├── CLIP002.srt
│       ├── CLIP002_cleaned.srt
│       ├── CLIP002.json          # ⭐ Description results
│       ├── CLIP003.mp4           # HD preview (135MB, created)
│       ├── CLIP003.srt
│       ├── CLIP003_cleaned.srt
│       └── CLIP003.json          # ⭐ Description results
```

### Examining Results

View a description result:

```bash
cat videos/preview/CLIP001.json | python3 -m json.tool
```

Output:
```json
{
  "filename": "CLIP001.mp4",
  "video_description_long": "A first-person perspective shot of mountain biking down a forest trail. The camera shows the handlebar view as the rider navigates through trees and over small jumps. Sunlight filters through the canopy creating dynamic lighting conditions.",
  "video_description_short": "Mountain biking through forest trail, POV from handlebar",
  "primary_shot_type": "pov",
  "tags": ["dynamic", "medium", "outdoor"],
  "classification_time_seconds": 142.3,
  "classification_model": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
  "video_length_seconds": 45.2,
  "video_timestamp": "2024-11-03T14:23:45",
  "video_thumbnail_base64": "iVBORw0KGgoAAAANS...",
  "rating": 0.85,
  "segments": [
    {
      "in_timestamp": "00:00:05.500",
      "out_timestamp": "00:00:25.200",
      "description": "Best action segment with jump sequence"
    },
    {
      "in_timestamp": "00:00:32.100",
      "out_timestamp": "00:00:42.800",
      "description": "Smooth trail riding through trees"
    }
  ]
}
```

## Step 5: What's Next?

### Import to Database (Optional)

If you want to use the web UI or DaVinci integration:

```python
import json
from vlog.db import insert_result, initialize_db

initialize_db()

# Import all JSON results
import glob
for json_file in glob.glob("videos/preview/*.json"):
    with open(json_file) as f:
        data = json.load(f)
        insert_result(data)
        print(f"Imported: {data['filename']}")
```

### Use with DaVinci Resolve

The JSON files can be used with the DaVinci Resolve importer to automatically bring your clips into your timeline with proper in/out points.

### Process More Videos

Next time you insert an SD card:

1. Update `config.yaml` if needed (or use `--sd-card` option)
2. Run `./scripts/run_snakemake.sh`
3. Only new videos will be processed (Snakemake tracks dependencies)

### Reprocess Specific Videos

If you want to rerun the describe step for better results:

```bash
# Rerun describe for CLIP001 only
snakemake --cores 1 --forcerun describe videos/preview/CLIP001.json

# Or rerun everything for CLIP002
snakemake --cores 1 --forceall videos/preview/CLIP002.json
```

## Summary

This complete example showed:

1. ✅ **Setup**: Verified environment and configured workflow
2. ✅ **Preview**: Used dry-run to see what would happen
3. ✅ **Execute**: Ran the complete pipeline on 3 videos
4. ✅ **Results**: Generated organized outputs with JSON descriptions
5. ✅ **Next Steps**: Options for using the results

The Snakemake workflow automatically:
- Copied existing preview files when available
- Created new preview files when needed
- Transcribed and cleaned subtitles
- Generated comprehensive video descriptions
- Organized all outputs systematically

All of this from a single command! 🎉
