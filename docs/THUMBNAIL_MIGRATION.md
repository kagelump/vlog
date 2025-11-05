# Thumbnail Storage Migration Guide

## Overview

As of version 0.2.0, the vlog system has migrated from storing thumbnails as base64-encoded strings in the database to saving them as JPG files alongside video files.

## What Changed

### Before (v0.1.x)
- Thumbnails were extracted from videos and encoded as base64 strings
- Base64 thumbnails were stored in the `video_thumbnail_base64` field in the database
- The web UI fetched thumbnails via the `/api/thumbnail/<filename>` endpoint which returned base64 data

### After (v0.2.0+)
- Thumbnails are extracted from videos and saved as JPG files (e.g., `video_thumb.jpg`)
- The `video_thumbnail_base64` field in the database is deprecated (kept empty for backwards compatibility)
- The web UI fetches thumbnails via the `/api/thumbnail-file/<filename>` endpoint which serves JPG files directly

## Benefits of the New Approach

1. **Reduced Database Size**: Base64-encoded thumbnails significantly increased database size. JPG files are stored separately.
2. **Faster Database Queries**: Excluding large base64 fields from queries improves performance.
3. **Better Caching**: Browsers can cache JPG files more efficiently than base64 data.
4. **Easier Management**: Thumbnail files can be easily viewed, deleted, or regenerated independently of the database.

## Migration Steps

### For Existing Projects

If you have an existing vlog project with base64 thumbnails in the database, here's how to migrate:

1. **Update the Code**: Pull the latest changes from the repository.

2. **Regenerate Thumbnails**: Run the following script to extract thumbnails as JPG files for existing videos:

```bash
# Example script to regenerate thumbnails
python3 scripts/regenerate_thumbnails.py /path/to/videos
```

3. **Optional: Clean Database**: If you want to remove old base64 data from the database to save space:

```sql
-- Connect to your database
sqlite3 video_results.db

-- Clear the deprecated field
UPDATE results SET video_thumbnail_base64 = '';

-- Vacuum to reclaim space
VACUUM;
```

### For New Projects

New projects automatically use the JPG file approach. No migration needed.

## API Changes

### Deprecated Endpoints

- `/api/thumbnail/<filename>` - Still works but returns base64 from database (empty for new records)

### New Endpoints

- `/api/thumbnail-file/<filename>` - Returns JPG file directly from filesystem

### Updated Functions

**video.py:**
- `get_video_thumbnail()` - DEPRECATED: Use `save_video_thumbnail_to_file()` instead
- `save_video_thumbnail_to_file()` - NEW: Saves thumbnail as JPG file
- `get_thumbnail_path_for_video()` - NEW: Returns expected path for thumbnail file

**db.py:**
- `insert_result()` - `video_thumbnail_base64` parameter now defaults to empty string

## File Naming Convention

Thumbnails are saved with the following naming pattern:
```
<video_stem>_thumb.jpg
```

Examples:
- `video.mp4` → `video_thumb.jpg`
- `clip.mov` → `clip_thumb.jpg`
- `recording_001.MP4` → `recording_001_thumb.jpg`

## Backwards Compatibility

The system maintains backwards compatibility:

1. **Database Schema**: The `video_thumbnail_base64` field is retained in the database schema
2. **Old API**: The `/api/thumbnail/<filename>` endpoint still exists
3. **Old Function**: `get_video_thumbnail()` still works but is marked as deprecated

## Troubleshooting

### Thumbnails Not Showing in Web UI

1. Check if thumbnail JPG files exist alongside video files
2. Verify file permissions on thumbnail files
3. Check browser console for 404 errors from `/api/thumbnail-file/` endpoint

### Regenerating Individual Thumbnails

```python
from vlog.video import save_video_thumbnail_to_file

# Regenerate thumbnail for a video
success = save_video_thumbnail_to_file("path/to/video.mp4", thumbnail_frame=0)
```

### Finding Orphaned Thumbnail Files

```bash
# Find all thumbnail files
find . -name "*_thumb.jpg"

# Find thumbnails without corresponding videos
for thumb in *_thumb.jpg; do
    video="${thumb%_thumb.jpg}.mp4"
    if [ ! -f "$video" ]; then
        echo "Orphaned: $thumb"
    fi
done
```

## Technical Details

### Storage Comparison

| Metric | Base64 (Old) | JPG File (New) |
|--------|--------------|----------------|
| Typical Size | ~50-100 KB in database | ~5-10 KB on disk |
| Query Impact | Slows down all queries | No impact on queries |
| Browser Caching | Limited | Full HTTP caching |
| Management | Requires database tools | Standard file operations |

### Implementation Details

The thumbnail extraction uses OpenCV with the following settings:
- Format: JPEG
- Quality: 50%
- Naming: `{video_stem}_thumb.jpg`
- Location: Same directory as video file

## Future Considerations

- Consider implementing a thumbnail cleanup utility to remove orphaned files
- Add support for thumbnail regeneration via web UI
- Implement thumbnail preview size options (currently uses extraction frame size)
