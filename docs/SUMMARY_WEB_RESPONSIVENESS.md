# Summary: Web Server Unresponsiveness Fix

## Issue
After starting auto-ingest (Snakemake) via the web interface, the web server became completely unresponsive. API requests would hang indefinitely in "pending" state, as if the entire web server process was locked up.

## Investigation
The problem was a **lock contention issue** in `AutoIngestSnakemakeService._run_snakemake_workflow()`:

- The `_snakemake_lock` was held for the **entire duration** of Snakemake execution
- This included blocking I/O operations (streaming stdout line-by-line)
- Could block for minutes to hours depending on the video processing workload
- Any API call trying to check status/progress would block waiting for this lock

**NOT a GIL issue**: Python's GIL is released during I/O operations. This was an application-level lock (`threading.Lock`) being held too long.

## Solution
Refactored lock usage to only protect critical sections:

### Before (Problematic)
```python
with self._snakemake_lock:
    self._snakemake_process = subprocess.Popen(...)
    # Entire execution happens while holding lock!
    for line in self._snakemake_process.stdout:
        logger.info(line)
    returncode = self._snakemake_process.wait()
    self._snakemake_process = None
```

### After (Fixed)
```python
# Only hold lock when setting process
with self._snakemake_lock:
    self._snakemake_process = subprocess.Popen(...)
    process = self._snakemake_process

# Stream and wait OUTSIDE the lock - allows other threads to check status
for line in process.stdout:
    logger.info(line)
returncode = process.wait()

# Hold lock again only to clear process
with self._snakemake_lock:
    self._snakemake_process = None
```

## Changes
1. **src/vlog/auto_ingest_snakemake.py**: Fixed lock scope in `_run_snakemake_workflow()`
2. **src/vlog/web.py**: Added explicit `threaded=True` and CLI argument parser
3. **tests/test_auto_ingest_lock_fix.py**: New tests verifying lock behavior
4. **tests/manual_test_web_responsiveness.py**: Manual integration test
5. **docs/FIX_WEB_RESPONSIVENESS.md**: Comprehensive documentation

## Verification

### Automated Tests
```bash
uv run -- pytest tests/test_auto_ingest_lock_fix.py -v
# Result: 3/3 tests pass ✓
```

All new tests pass, verifying:
- Lock is not held during execution
- Status/progress APIs work while Snakemake runs
- All operations complete quickly (< 0.5s)

### Security Scan
```bash
codeql_checker
# Result: 0 security issues found ✓
```

### Pre-existing Test Failures
2 pre-existing tests fail in `test_auto_ingest_snakemake_integration.py`:
- `test_get_progress_success` 
- `test_get_progress_failure`

These fail because they don't properly mock a running Snakemake process. These failures existed before this fix and are unrelated to the changes made.

## Impact
- ✅ Web server remains responsive during auto-ingest
- ✅ Status and progress APIs work in real-time
- ✅ Users can monitor workflow progress without freezing
- ✅ No breaking changes to API
- ✅ No security vulnerabilities introduced

## Testing Recommendations
1. **Automated**: Run `pytest tests/test_auto_ingest_lock_fix.py`
2. **Manual**: Run `tests/manual_test_web_responsiveness.py` against live server
3. **Integration**: Start auto-ingest via web UI and verify UI remains responsive

## Files Modified
- `src/vlog/auto_ingest_snakemake.py` (lock fix)
- `src/vlog/web.py` (threading + CLI args)

## Files Added
- `tests/test_auto_ingest_lock_fix.py` (automated tests)
- `tests/manual_test_web_responsiveness.py` (manual test)
- `docs/FIX_WEB_RESPONSIVENESS.md` (detailed documentation)
- `docs/SUMMARY_WEB_RESPONSIVENESS.md` (this summary)
