# Daemon Management in Snakemake Workflow

## Overview

The video description workflow uses a daemon process to efficiently process multiple videos. Instead of loading the MLX-VLM model for each video (which is slow), the daemon loads the model once at startup and keeps it in memory to serve multiple description requests.

## Architecture

The daemon management is split into several components:

### 1. daemon.smk (Snakemake Rules)
Located at: `src/ingest_pipeline/snakefiles/daemon.smk`

Defines Snakemake rules for:
- `start_daemon`: Starts the describe daemon and creates a signal file
- `stop_daemon`: Stops the daemon and cleans up

### 2. Start Script
Located at: `src/ingest_pipeline/start_daemon.sh`

Bash script that:
- Starts the daemon process in the background using `nohup`
- Saves the daemon PID to a file for later management
- Waits for the daemon to initialize
- Checks the `/health` endpoint to ensure daemon is ready
- Creates a signal file (`status/daemon_running.signal`) when ready

### 3. Stop Script
Located at: `src/ingest_pipeline/stop_daemon.sh`

Bash script that:
- Reads the daemon PID from the PID file
- Sends SIGTERM for graceful shutdown
- Falls back to SIGKILL if needed
- Cleans up PID and signal files

### 4. Daemon Service
Located at: `src/vlog/describe_daemon.py`

FastAPI service that:
- Loads the MLX-VLM model at startup
- Provides a `/describe` endpoint for video description
- Provides a `/health` endpoint for health checks
- Keeps the model in memory across requests

## Workflow Integration

### Automatic Daemon Management

When running the full pipeline or stage 3, the daemon is automatically managed:

```bash
# This will automatically start the daemon before stage 3
snakemake --snakefile src/ingest_pipeline/snakefiles/Snakefile --cores 1 --configfile config.yaml stage3
```

The workflow ensures:
1. The daemon starts after stage 2 completes (subtitles ready)
2. The `status/daemon_running.signal` file is created when daemon is ready
3. All `describe` rules depend on the signal file (won't run until daemon is ready)
4. The signal file is marked as `temp()` so Snakemake can clean it up

### Dependency Chain

```
Stage 2 (subtitles) → start_daemon → daemon_running.signal → describe rules
```

Each `describe` rule has the daemon signal as an input:

```python
rule describe:
    input:
        video=f"{PREVIEW_FOLDER}/{{stem}}.mp4",
        subtitle=f"{PREVIEW_FOLDER}/{{stem}}_cleaned.srt",
        daemon_signal="status/daemon_running.signal"  # Won't run until daemon is ready
    output:
        f"{PREVIEW_FOLDER}/{{stem}}.json"
```

## Manual Daemon Management

You can also manage the daemon manually for testing or debugging:

### Start Daemon
```bash
snakemake --snakefile src/ingest_pipeline/snakefiles/daemon.smk --cores 1 --configfile config.yaml start_daemon
```

### Stop Daemon
```bash
snakemake --snakefile src/ingest_pipeline/snakefiles/daemon.smk --cores 1 --configfile config.yaml stop_daemon
```

### Check if Daemon is Running
```bash
# Check signal file
ls -la status/daemon_running.signal

# Check PID file
cat status/daemon.pid
2. The configured signal file (default: `status/daemon_running.signal`) is created when daemon is ready
# Check process
3. All `describe` rules depend on the configured signal file (won't run until daemon is ready)
ps -p $(cat status/daemon.pid)

# Check health endpoint
curl http://127.0.0.1:5555/health
```

## Configuration
      daemon_signal=config.get("daemon_signal_file", "status/daemon_running.signal")
Daemon settings are configured in `config.yaml`:

```yaml
# Daemon settings
daemon_host: "127.0.0.1"
daemon_port: 5555

# Describe settings (used by daemon)
 - Configurable signal file (default: `status/daemon_running.signal`): Signal file indicating daemon is ready (temp file, cleaned by Snakemake)
 - Configurable PID file (default: `status/daemon.pid`): Process ID of the daemon
 - Configurable daemon log (default: `logs/daemon.log`): Daemon stdout/stderr output

## Files Created

The daemon management creates several files:
 # Check signal file (default path: `status/daemon_running.signal`)
 ls -la $(python -c "import yaml,sys;print(yaml.safe_load(open('config.yaml')).get('daemon_signal_file','status/daemon_running.signal'))")
- `status/daemon_running.signal`: Signal file indicating daemon is ready (temp file, cleaned by Snakemake)
- `status/daemon.pid`: Process ID of the daemon
- `logs/daemon.log`: Daemon stdout/stderr output
- `logs/daemon_start.log`: Start script output
- `logs/daemon_stop.log`: Stop script output

rm -f $(python -c "import yaml,sys;c=yaml.safe_load(open('config.yaml'));print(c.get('daemon_pid_file','status/daemon.pid'))") $(python -c "import yaml,sys;c=yaml.safe_load(open('config.yaml'));print(c.get('daemon_signal_file','status/daemon_running.signal'))")

### Daemon won't start

1. Check the start log:
   ```bash
   cat logs/daemon_start.log
   ```

2. Check the daemon log:
   ```bash
   cat logs/daemon.log
   ```

3. Make sure no other process is using the port:
   ```bash
   lsof -i :5555
   ```

### Daemon is running but health check fails

1. Try hitting the health endpoint manually:
   ```bash
   curl -v http://127.0.0.1:5555/health
   ```

2. Check if model loaded successfully:
   ```bash
   tail -f logs/daemon.log
   ```

### Stale PID file

If the daemon crashes and leaves a stale PID file:
```bash
rm -f status/daemon.pid status/daemon_running.signal
```

### Port already in use

Change the port in `config.yaml`:
```yaml
daemon_port: 5556  # or any other available port
```

## Design Decisions

1. **Why use a daemon instead of running the model directly?**
   - Loading the MLX-VLM model is expensive (takes several seconds)
   - By loading once and reusing, we save significant time across multiple videos
   - The daemon can also be reused across multiple Snakemake runs

2. **Why use shell scripts instead of Python?**
   - Shell scripts are simpler for process management (background jobs, PID files, signals)
   - Easier to use `nohup` and standard Unix tools
   - Snakemake already has good shell script support

3. **Why use a signal file?**
   - Snakemake needs concrete files for dependency tracking
   - The signal file allows rules to depend on "daemon is ready" state
   - Marking it as `temp()` allows Snakemake to clean it up automatically

4. **Why check the health endpoint?**
   - Just because the process started doesn't mean the model loaded
   - Health check ensures the service is actually ready to handle requests
   - Prevents describe jobs from failing due to daemon not being ready
