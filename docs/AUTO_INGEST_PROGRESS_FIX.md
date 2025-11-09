# Auto-Ingest Progress Fix

## Problem
After starting auto-ingest via the web interface, the progress endpoint returned:
```json
{
    "available": false,
    "error": "Failed to connect to logger API: ... Connection refused"
}
```

## Root Causes

### 1. Missing Logger Configuration
The `AutoIngestSnakemakeService` was calling Snakemake with `--logger vlog` but **not passing the port configuration**. Without the explicit `--logger-vlog-port` flag, Snakemake couldn't properly initialize the logger plugin settings, and the API server never started.

### 2. No Initial Workflow Trigger
When auto-ingest started, it only watched for new files but didn't trigger an initial Snakemake run to process existing files. This meant:
- Snakemake would never start unless a new file was added
- The logger API (which only runs during Snakemake execution) was never available
- Progress monitoring appeared broken even though auto-ingest was "running"

### 3. Poor Error Communication
- The web API always returned 200 OK even for error states
- The UI silently failed when progress wasn't available
- No distinction between "no workflow running" (normal) and "error" (problem)

## Solutions Implemented

### 1. Added Logger Plugin Configuration
**File:** `src/vlog/auto_ingest_snakemake.py`

```python
cmd = [
    'snakemake',
    '--snakefile', str(snakefile),
    '--configfile', temp_config,
    '--config', f'preview_folder={self.preview_folder}',
    '--logger', 'vlog',
    '--logger-vlog-port', str(self.logger_port),  # ← Added
    '--logger-vlog-host', '127.0.0.1',            # ← Added
    '--cores={self.cores}',
    '--resources', f'mem_gb={self.resources_mem_gb}'
]
```

### 2. Trigger Initial Workflow on Start
**File:** `src/vlog/auto_ingest_snakemake.py`

```python
def start(self) -> bool:
    # ... observer setup ...
    
    self.is_running = True
    logger.info("Triggering initial Snakemake run to discover and process existing files...")
    
    # Trigger initial Snakemake run to process any existing files
    self._maybe_start_processing()  # ← Added
    
    return True
```

Now when auto-ingest starts, it immediately runs Snakemake to:
- Discover existing files in the watch directory
- Start processing them
- Make the logger API available for progress monitoring

### 3. Improved Progress Response
**File:** `src/vlog/auto_ingest_snakemake.py`

Enhanced `get_progress()` to provide better state information:

```python
def get_progress(self) -> Dict[str, Any]:
    # Check if Snakemake is actually running
    with self._snakemake_lock:
        is_processing = self._snakemake_process is not None and self._snakemake_process.poll() is None
    
    if not is_processing:
        return {
            'available': False,
            'message': 'No workflow currently running. Snakemake will start when new files are detected.',
            'is_processing': False
        }
    
    # ... try to fetch from logger API ...
    
    # If API fails while Snakemake is running, indicate configuration issue
    except requests.RequestException as e:
        return {
            'error': f'Failed to connect to logger API: {e}',
            'available': False,
            'is_processing': True,
            'message': 'Snakemake is running but logger API is not responding.'
        }
```

### 4. Proper HTTP Status Codes
**File:** `src/vlog/web.py`

```python
@app.route('/api/auto-ingest-snakemake/progress', methods=['GET'])
def get_auto_ingest_snakemake_progress():
    progress = auto_ingest_snakemake_service.get_progress()
    
    # Return appropriate status codes
    if progress.get('available'):
        return jsonify(progress), 200  # OK - progress data available
    elif progress.get('is_processing') == False:
        return jsonify(progress), 200  # OK - no workflow (normal state)
    elif 'error' in progress:
        http_status = progress.get('http_status', 503)
        return jsonify(progress), http_status  # 503 - Service error
    else:
        return jsonify(progress), 200  # OK - unknown state
```

### 5. Enhanced UI Error Display
**File:** `static/launcher/launcher.html`

Added functions to display different states:

```javascript
async function fetchSnakemakeProgress() {
    const response = await fetch('/api/auto-ingest-snakemake/progress');
    const progress = await response.json();
    
    if (!response.ok) {
        showProgressError(progress.error || `Server error: ${response.status}`);
        return;
    }
    
    if (progress.available === false) {
        if (progress.error) {
            showProgressError(progress.error);  // Show error with red banner
        } else if (progress.message) {
            showProgressMessage(progress.message, 'info');  // Show info with blue banner
        }
        return;
    }
    
    updateProgressDisplay(progress);  // Show normal progress
}

function showProgressError(message) {
    // Red error banner with icon
}

function showProgressMessage(message, type = 'info') {
    // Blue/yellow/green info banner with icon
}
```

## How It Works Now

1. **Start auto-ingest** via web UI or API
2. **Service initializes** and starts watching directory
3. **Immediately triggers Snakemake** to process existing files
4. **Snakemake starts** with logger plugin configured on port 5556
5. **Logger API becomes available** for progress monitoring
6. **UI polls progress** every few seconds and displays:
   - Active progress bars when Snakemake is running
   - Info message when no workflow is running (normal)
   - Error message when there's a configuration problem
7. **When Snakemake completes**, logger API shuts down
8. **New files detected** → Snakemake restarts → cycle repeats

## Testing the Fix

### 1. Check if logger API is running
```bash
./scripts/check_logger_api.sh
```

### 2. Test the complete fix
```bash
./scripts/test_auto_ingest_fix.sh
```

### 3. Start auto-ingest and monitor
```bash
# In terminal 1: Start web server
uv run -- python src/vlog/web.py

# In terminal 2: Start auto-ingest (via API or web UI)
curl -X POST http://localhost:5432/api/auto-ingest-snakemake/start \
     -H 'Content-Type: application/json' \
     -d '{"watch_directory":"/path/to/videos"}'

# In terminal 3: Monitor progress
watch -n 2 'curl -s http://localhost:5432/api/auto-ingest-snakemake/progress | python3 -m json.tool'
```

### 4. Verify via web UI
1. Open http://localhost:5432
2. Click "Start Auto-Ingest"
3. Progress should immediately show:
   - If files exist: Progress bars for each stage
   - If no files: Info message "No workflow currently running"
   - If error: Red error banner with details

## Expected Responses

### Normal - Workflow Running
```json
{
  "available": true,
  "is_processing": true,
  "total": 15,
  "completed": 10,
  "running": 2,
  "failed": 0,
  "rules": {
    "transcribe": {
      "total": 15,
      "completed": 10,
      "running": 2,
      "failed": 0
    }
  }
}
```
**HTTP Status:** 200 OK

### Normal - No Workflow Running  
```json
{
  "available": false,
  "is_processing": false,
  "message": "No workflow currently running. Snakemake will start when new files are detected or when manually triggered."
}
```
**HTTP Status:** 200 OK

### Error - Logger API Not Responding
```json
{
  "available": false,
  "is_processing": true,
  "error": "Failed to connect to logger API: Connection refused",
  "message": "Snakemake is running but logger API is not responding. This may indicate a configuration issue."
}
```
**HTTP Status:** 503 Service Unavailable

## Important Notes

1. **Logger API lifecycle**: The API server only runs while Snakemake is actively processing. This is by design.

2. **Initial trigger**: Auto-ingest now immediately runs Snakemake on start, ensuring:
   - Existing files are discovered and processed
   - Logger API becomes available right away
   - Progress monitoring works from the start

3. **Status code semantics**:
   - `200 OK` = Normal operation (with or without data)
   - `503 Service Unavailable` = Error condition (Snakemake running but logger not responding)

4. **UI behavior**:
   - Shows progress bars when workflow is active
   - Shows blue info banner when idle (normal)
   - Shows red error banner when there's a problem
   - No silent failures

## Troubleshooting

### Progress shows "No workflow currently running"
- **This is normal** if no files are in the watch directory
- Add a video file to trigger Snakemake
- Or check if files are being filtered out by extensions

### Progress shows error "Failed to connect to logger API"
- Check if `--logger-vlog-port` is in the Snakemake command
- Verify port 5556 is not in use by another service
- Check Snakemake logs for logger plugin initialization errors

### Auto-ingest starts but never processes files
- Check watch directory path is correct
- Verify files have valid extensions (mp4, mov, avi, mkv)
- Check Snakemake logs for discovery issues
- Look for file permission problems

## Related Files
- `src/vlog/auto_ingest_snakemake.py` - Auto-ingest service (FIXED)
- `src/vlog/web.py` - Web API endpoints (UPDATED)
- `static/launcher/launcher.html` - UI error display (UPDATED)
- `src/vlog/snakemake_logger_plugin/logger.py` - Logger plugin
- `src/vlog/snakemake_logger_plugin/api_server.py` - REST API server
- `scripts/check_logger_api.sh` - Diagnostic script
- `scripts/test_auto_ingest_fix.sh` - Integration test script
