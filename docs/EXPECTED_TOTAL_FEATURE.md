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

The `/status` endpoint now returns `expected_total` and `already_satisfied` for each rule (when available):

```json
{
  "total_jobs": 50,
  "completed_jobs": 30,
  "failed_jobs": 0,
  "running_jobs": 20,
  "pending_jobs": 0,
  "rules": {
    "transcribe": {
      "total": 50,
      "pending": 0,
      "running": 20,
      "completed": 30,
      "failed": 0,
      "expected_total": 300,
      "already_satisfied": 250
    }
  }
}
```

### Field Definitions

- **`total`**: Number of jobs Snakemake created/will create for this rule
- **`expected_total`**: Total number of input files discovered (e.g., all video stems)
- **`already_satisfied`**: Number of outputs that already exist and don't need to be processed
  - Calculated as: `already_satisfied = expected_total - total`
  - Only appears when `expected_total` is set and `already_satisfied > 0`

### Calculating Overall Progress

To show complete progress including already-done work:

```python
# Get status from API
rule_status = status["rules"]["transcribe"]

# Calculate total completed (including pre-existing outputs)
total_done = rule_status["completed"] + rule_status.get("already_satisfied", 0)
expected = rule_status["expected_total"]

# Calculate percentage
percentage = (total_done / expected) * 100

print(f"Progress: {total_done}/{expected} ({percentage:.1f}%)")
# Example output: "Progress: 280/300 (93.3%)"
```

## Implementation Details

### How It Works

1. **Discovery Phase**: Snakemake workflow files call `set_expected_total()` after discovering input files
2. **Direct Storage**: The helper directly accesses the global `_workflow_status` object to store expected totals (works at parse time before logging is initialized)
3. **Logging Fallback**: If direct access fails, it falls back to emitting a log event
4. **API Response**: The `/status` endpoint includes `expected_total` for all rules (even those without jobs yet)

### Parse-Time vs Runtime

The key improvement is that `set_expected_total()` works at **parse time** (when Snakemake reads the workflow files), not just at runtime:

- **Parse time**: Discovery functions run and call `set_expected_total()`
- **Direct access**: Helper directly updates `_workflow_status._expected_totals`
- **Immediate visibility**: Expected totals appear in API immediately, even before any jobs are created
- **Job creation**: As Snakemake creates jobs, they're tracked alongside the expected totals

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

- `expected_total` appears in the API response even before jobs are created for that rule
- Multiple calls to `set_expected_total()` for the same rule will update the value
- The expected total is reset when the status tracker is reset
- Jobs may be created lazily, so `total` may be less than `expected_total` initially

## Troubleshooting

**Problem**: `expected_total` not showing up in the API

**Solution**: Make sure:
1. The workflow file imports and calls `set_expected_total()` in the discovery function
2. The discovery function is actually being called (it should run at parse time)
3. The logger plugin is enabled with `--logger-plugin-settings vlog`
4. Check stderr for debug messages: `[set_expected_total] rule_name: count`

**Verify it's working**:
```bash
# You should see debug output when Snakemake parses the workflow
snakemake ... 2>&1 | grep set_expected_total

# Expected totals should appear in API even with 0 jobs
curl http://127.0.0.1:5556/status | jq '.rules'
```

