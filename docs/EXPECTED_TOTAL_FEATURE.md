# Expected Total Feature for Snakemake Logger Plugin

## Overview

The Snakemake logger plugin API now tracks the **expected total number of input files/stems** discovered at each stage, in addition to job counts. This allows monitoring tools to show both:
- How many jobs are planned (expected_total)
- How many jobs have actually been created/processed (total, pending, running, completed, failed)

## Usage in Snakemake Workflows

### Import the Helper

Add this import at the top of your `.smk` file:

```python
from vlog.snakemake_logger_plugin.helpers import set_expected_total
```

The helper includes a fallback, so it won't break if the plugin is not available.

### Call After Discovery

After discovering your input files/stems, call `set_expected_total()`:

```python
def discover_preview_videos():
    """Discover preview video files in the preview folder."""
    preview_pattern = f"{PREVIEW_FOLDER}/*.{PREVIEW_EXT}"
    video_files = glob.glob(preview_pattern)
    stems = [Path(f).stem for f in video_files]
    
    # Report expected total to status logger
    set_expected_total("transcribe", len(stems))
    set_expected_total("clean_subtitles", len(stems))
    
    return stems

VIDEO_STEMS = discover_preview_videos()
```

### Parameters

- `rule_name` (str): Name of the rule (e.g., "transcribe", "describe")
- `expected_total` (int): Total number of inputs discovered for this rule

## API Response Format

The `/status` endpoint now returns `expected_total` for each rule (when available):

```json
{
  "total_jobs": 10,
  "completed_jobs": 3,
  "failed_jobs": 0,
  "running_jobs": 2,
  "pending_jobs": 5,
  "rules": {
    "transcribe": {
      "total": 10,
      "pending": 5,
      "running": 2,
      "completed": 3,
      "failed": 0,
      "expected_total": 300
    },
    "describe": {
      "total": 5,
      "pending": 3,
      "running": 1,
      "completed": 1,
      "failed": 0,
      "expected_total": 250
    }
  }
}
```

## Implementation Details

### How It Works

1. **Discovery Phase**: Snakemake workflow files call `set_expected_total()` after discovering input files
2. **Logging**: The helper emits a custom log event with `event="SET_EXPECTED_TOTAL"`
3. **Capture**: The logger plugin's `emit()` method captures this event
4. **Storage**: Expected totals are stored in the `WorkflowStatus` tracker
5. **API**: The `/status` endpoint includes `expected_total` in the response

### Custom Log Event

The helper emits a log record with these extra fields:

```python
logger.info(
    f"Setting expected total for {rule_name}: {expected_total}",
    extra={
        "event": "SET_EXPECTED_TOTAL",
        "rule": rule_name,
        "expected_total": expected_total
    }
)
```

### Modified Files

**Logger Plugin:**
- `src/vlog/snakemake_logger_plugin/logger.py` - Added expected_total tracking
- `src/vlog/snakemake_logger_plugin/helpers.py` - New helper function
- `tests/test_status_logger.py` - Added tests for new feature

**Workflow Files:**
- `src/vlog/workflows/snakefiles/copy.smk` - Reports expected totals for copy_main and copy_or_create_preview
- `src/vlog/workflows/snakefiles/subtitles.smk` - Reports expected totals for transcribe and clean_subtitles
- `src/vlog/workflows/snakefiles/describe.smk` - Reports expected total for describe

## Benefits

1. **Progress Visibility**: Shows total work planned vs. work completed
2. **Debugging**: Helps identify if discovery is working correctly
3. **Monitoring**: Enables progress bars and percentage calculations
4. **Planning**: Shows scope of work before jobs even start

## Example Use Cases

### Progress Calculation

```python
# In monitoring UI
progress = completed_jobs / expected_total * 100
print(f"Progress: {progress}%")
```

### Detecting Issues

```python
# If total jobs created doesn't match expected
if rules["transcribe"]["total"] < rules["transcribe"]["expected_total"]:
    print("Warning: Not all expected jobs were created!")
```

### Per-Rule Status

```python
# Show detailed status per rule
for rule_name, rule_status in status["rules"].items():
    expected = rule_status.get("expected_total", "?")
    completed = rule_status["completed"]
    print(f"{rule_name}: {completed}/{expected} completed")
```

## Notes

- `expected_total` is optional and only appears if set by the workflow
- Multiple calls to `set_expected_total()` for the same rule will update the value
- The expected total is reset when the status tracker is reset
- Jobs may be created lazily, so `total` may be less than `expected_total` initially
