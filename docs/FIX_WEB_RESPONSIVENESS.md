# Fix: Web Server Unresponsiveness During Auto-Ingest

## Problem

After starting auto-ingest (Snakemake) on the web interface and confirming via server logs that Snakemake has started, the web server becomes unresponsive. API requests end up in "pending" state forever without returning, as if the entire web server process is locked up and cannot service requests while Snakemake is running.

## Root Cause Analysis

The issue was identified in `src/vlog/auto_ingest_snakemake.py` in the `_run_snakemake_workflow()` method:

### The Problem

```python
# BEFORE (PROBLEMATIC CODE):
with self._snakemake_lock:
    self._snakemake_process = subprocess.Popen(...)
    
    # Stream output - THIS BLOCKS FOR HOURS!
    if self._snakemake_process.stdout:
        for line in self._snakemake_process.stdout:
            logger.info(f"Snakemake: {line.rstrip()}")
    
    # Wait for completion - ALSO BLOCKS!
    returncode = self._snakemake_process.wait()
    
    self._snakemake_process = None
```

The `_snakemake_lock` was acquired and held for the **entire duration** of the Snakemake workflow execution, which could be:
- Minutes to hours for video processing
- Potentially indefinite if Snakemake encounters issues

### Why This Caused Unresponsiveness

1. **Lock Contention**: The lock was held while:
   - Streaming stdout line-by-line (blocking I/O)
   - Waiting for the subprocess to complete
   - This could take hours for large video batches

2. **Blocked API Calls**: Any other thread trying to:
   - Check status via `get_status()` 
   - Check progress via `get_progress()`
   - Start new processing via `_maybe_start_processing()`
   
   Would block waiting for the lock, which was held for the entire Snakemake run.

3. **Web Server Impact**: Even though Flask runs with threading enabled, the API endpoints would hang because they couldn't acquire the lock to check the service status.

### Not a GIL Issue

This was **not** a Python GIL (Global Interpreter Lock) issue. The GIL is released during I/O operations, so it wouldn't cause this problem. The issue was an application-level lock (`threading.Lock`) being held too long.

## Solution

### Lock Scope Fix

The fix refactors the lock usage to only protect the critical section (setting/clearing the process reference):

```python
# AFTER (FIXED CODE):
# Only hold lock when setting the process
with self._snakemake_lock:
    self._snakemake_process = subprocess.Popen(...)
    process = self._snakemake_process  # Keep reference for use outside lock

# Stream output and wait OUTSIDE the lock
# This allows other threads to check status while Snakemake runs
if process.stdout:
    for line in process.stdout:
        logger.info(f"Snakemake: {line.rstrip()}")

returncode = process.wait()

# Clear the process reference
with self._snakemake_lock:
    self._snakemake_process = None
```

### Flask Threading

Additionally, Flask's `app.run()` was updated to explicitly enable threading:

```python
app.run(
    host=args.host,
    port=args.port,
    debug=debug_mode,
    threaded=True  # Explicitly enable threading for concurrent request handling
)
```

While Flask 3.x enables threading by default, this makes it explicit and self-documenting.

## Changes Made

### 1. `src/vlog/auto_ingest_snakemake.py`

**Changed**: `_run_snakemake_workflow()` method

- Lock is acquired only when setting `self._snakemake_process`
- Lock is released before streaming output and waiting for completion
- Lock is acquired again only when clearing `self._snakemake_process`
- Added comments explaining the lock strategy

### 2. `src/vlog/web.py`

**Changed**: `if __name__ == '__main__'` block

- Added `argparse` for command-line arguments (`--port`, `--host`, `--debug`)
- Explicitly set `threaded=True` in `app.run()`
- Added documentation comments explaining threading requirement

### 3. `tests/test_auto_ingest_lock_fix.py` (NEW)

**Added**: Comprehensive tests for lock behavior

Tests verify:
- Lock is not held during Snakemake execution
- `get_status()` works while Snakemake is running
- `get_progress()` works while Snakemake is running
- All operations complete quickly (< 0.5s for status checks)

### 4. `tests/manual_test_web_responsiveness.py` (NEW)

**Added**: Manual integration test

- Can be run against a live web server
- Verifies API responsiveness during actual auto-ingest
- Provides clear pass/fail feedback

## Testing

### Automated Tests

```bash
# Run the lock behavior tests
cd /path/to/vlog
uv run -- pytest tests/test_auto_ingest_lock_fix.py -v

# All tests should pass:
# ✓ test_lock_not_held_during_snakemake_execution
# ✓ test_get_status_works_during_execution
# ✓ test_get_progress_works_during_execution
```

### Manual Integration Test

```bash
# Terminal 1: Start the web server
cd /path/to/vlog
uv run -- python -m vlog.web

# Terminal 2: Run the integration test
cd /path/to/vlog
uv run -- python tests/manual_test_web_responsiveness.py
```

Expected result: All API calls should respond in < 1 second, even while Snakemake is running.

## Verification

To verify the fix works:

1. **Start the web server**:
   ```bash
   uv run -- python -m vlog.web
   ```

2. **Start auto-ingest** via the web UI at http://localhost:5432

3. **While Snakemake is running**, check that the UI remains responsive:
   - Status updates continue to work
   - Progress bar updates in real-time
   - Other API calls don't hang

4. **Before the fix**: The web UI would freeze and all requests would hang

5. **After the fix**: The web UI remains responsive and shows live progress

## Impact

- ✅ Web server remains responsive during auto-ingest
- ✅ Status and progress APIs work correctly while Snakemake runs
- ✅ Users can monitor progress in real-time
- ✅ No breaking changes to the API
- ✅ No security issues introduced (verified with CodeQL)

## Related Files

- `src/vlog/auto_ingest_snakemake.py` - Core fix
- `src/vlog/web.py` - Flask threading configuration
- `tests/test_auto_ingest_lock_fix.py` - Automated tests
- `tests/manual_test_web_responsiveness.py` - Manual integration test
- `docs/FIX_WEB_RESPONSIVENESS.md` - This document

## Future Improvements

While this fix solves the immediate problem, potential future enhancements include:

1. **Async/Await**: Migrate to async processing with `asyncio` for better concurrency
2. **Task Queue**: Use Celery or similar for long-running background tasks
3. **WebSockets**: Provide real-time progress updates via WebSocket connection
4. **Production Server**: Deploy with Gunicorn/uWSGI instead of Flask dev server

However, these are not necessary for the current use case and would require significant refactoring.
