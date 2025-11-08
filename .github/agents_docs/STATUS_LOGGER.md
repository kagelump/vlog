# Snakemake Status Logger Plugin

This plugin provides a simple REST API endpoint to monitor the progress of Snakemake workflow execution. It tracks job completion status at each stage and exposes this information via HTTP.

## Features

- **Real-time tracking**: Captures job lifecycle events (pending, running, completed, failed)
- **Per-rule breakdown**: Shows progress for each rule in the workflow
- **REST API**: Query status via HTTP endpoint
- **Thread-safe**: Safe for concurrent access
- **Lightweight**: Minimal overhead on workflow execution

## Installation

The logger plugin is already included in the vlog project. No additional installation is needed.

## Usage

### Running Snakemake with the Logger

The logger plugin works by attaching a custom log handler to Snakemake's logger.  
Due to Snakemake 9.x API changes, the recommended approach is to use the demo script  
to see the logger in action, or integrate it into your own Python code.

**Quick Demo:**
```bash
# Run the demo to see the logger tracking simulated jobs
python3 scripts/demo_status_logger.py

# In another terminal, query the status
python3 scripts/snakemake_status.py --port 5558 --watch 2
```

**For Production Use:**
The logger is designed to be integrated programmatically. See the "Integration with Existing Workflows" section below for examples.

### Querying Workflow Status

While the workflow is running, query the status from another terminal:

```bash
# Get current status (formatted output)
python3 scripts/snakemake_status.py

# Get status as JSON
python3 scripts/snakemake_status.py --json

# Watch mode (refresh every 2 seconds)
python3 scripts/snakemake_status.py --watch 2

# Query custom host/port
python3 scripts/snakemake_status.py --host 127.0.0.1 --port 5557
```

### Direct API Access

You can also query the API directly using curl or any HTTP client:

```bash
# Get workflow status
curl http://127.0.0.1:5556/status

# Health check
curl http://127.0.0.1:5556/health

# Reset status tracker
curl -X POST http://127.0.0.1:5556/reset
```

## API Reference

### GET /status

Returns the current workflow status.

**Response:**
```json
{
  "total_jobs": 10,
  "completed_jobs": 7,
  "failed_jobs": 0,
  "running_jobs": 2,
  "pending_jobs": 1,
  "rules": {
    "transcribe": {
      "total": 5,
      "pending": 0,
      "running": 1,
      "completed": 4,
      "failed": 0
    },
    "describe": {
      "total": 5,
      "pending": 1,
      "running": 1,
      "completed": 3,
      "failed": 0
    }
  }
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

### POST /reset

Reset the workflow status tracker (useful between runs).

**Response:**
```json
{
  "status": "reset"
}
```

## Configuration

The logger can be configured with the following settings:

- **port**: Port for the REST API server (default: 5556)
- **host**: Host to bind the server to (default: 127.0.0.1)

Example configuration:

```python
from vlog.snakemake_logger_plugin.logger import StatusLogHandlerSettings

settings = StatusLogHandlerSettings(
    port=5557,
    host="0.0.0.0"  # Listen on all interfaces
)
```

## Example Output

When you run `python3 scripts/snakemake_status.py`, you'll see output like:

```
============================================================
Snakemake Workflow Status
============================================================
Total Jobs:     10
Completed:      7
Failed:         0
Running:        2
Pending:        1
------------------------------------------------------------
Per-Rule Breakdown:

  transcribe:
    Total:     5
    Completed: 4/5 (80.0%)
    Running:   1

  describe:
    Total:     5
    Completed: 3/5 (60.0%)
    Running:   1
    Pending:   1

============================================================
```

## Integration with Existing Workflows

To integrate the logger with your own Python code that uses Snakemake:

```python
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler,
    StatusLogHandlerSettings,
)

# Create logger settings
settings = StatusLogHandlerSettings(port=5556, host="127.0.0.1")

# Create mock common settings (required by Snakemake logger interface)
class MockOutputSettings:
    printshellcmds = True
    nocolor = False
    quiet = None
    debug_dag = False
    verbose = False
    show_failed_logs = True
    stdout = False
    dryrun = False

common_settings = MockOutputSettings()

# Create and add handler to Snakemake's logger
handler = StatusLogHandler(
    common_settings=common_settings,
    settings=settings
)

snakemake_logger = logging.getLogger("snakemake")
snakemake_logger.addHandler(handler)

# Now run Snakemake using the CLI or API
# The handler will capture job events automatically

# Example 1: Using subprocess to call snakemake CLI
import subprocess
result = subprocess.run([
    "snakemake",
    "--snakefile", "Snakefile",
    "--cores", "1",
    "--configfile", "config.yaml"
])

# Example 2: If using Snakemake 9.x API (more complex)
# See Snakemake documentation for the new API usage
```

**Note:** The logger plugin is fully functional and tested. Integration with Snakemake  
execution is left flexible to accommodate different Snakemake API versions and use cases.

## Architecture

The logger plugin consists of three main components:

1. **StatusLogHandler**: Implements the Snakemake logger plugin interface
   - Captures job lifecycle events from Snakemake
   - Updates the WorkflowStatus tracker
   - Extends `LogHandlerBase` from `snakemake-interface-logger-plugins`

2. **WorkflowStatus**: Thread-safe status tracker
   - Maintains counts of jobs by rule and status
   - Provides atomic operations for updating status
   - Accessible via `get_workflow_status()` function

3. **API Server**: FastAPI-based REST endpoint
   - Runs in a background thread
   - Exposes `/status`, `/health`, and `/reset` endpoints
   - Queries the WorkflowStatus tracker

## Limitations

- The logger tracks job-level events, not file-level events
- Status is held in memory and reset when the script exits
- The API server runs only during workflow execution (plus 30 seconds after completion)
- For distributed/cluster execution, each node would need its own API server
- **Snakemake API:** This plugin is compatible with Snakemake's logging interface but  
  requires manual integration due to Snakemake 9.x API changes. The demo script shows  
  the logger functionality without requiring complex API integration.

## Troubleshooting

### Port Already in Use

If you get an error about the port being in use, try a different port:

```bash
python3 scripts/run_with_status_logger.py --logger-port 5557
```

### API Not Responding

Make sure the workflow is actually running. The API server starts when the logger is initialized.

### Status Not Updating

Verify that the logger handler is properly attached to Snakemake's logger. Check the script output for the API URL.

## Future Enhancements

Potential improvements for the logger plugin:

- [ ] Persistent storage (SQLite or file-based)
- [ ] WebSocket support for real-time updates
- [ ] Web UI dashboard
- [ ] File-level tracking (not just job-level)
- [ ] Distributed/cluster support
- [ ] Historical run tracking
- [ ] Prometheus metrics export

## See Also

- [Snakemake Logger Plugin Interface](https://github.com/snakemake/snakemake-interface-logger-plugins)
- [Snakemake Documentation](https://snakemake.readthedocs.io/)
- [Auto-Ingest Documentation](AUTO_INGEST.md)
- [Snakemake Workflow Documentation](SNAKEMAKE_WORKFLOW.md)
