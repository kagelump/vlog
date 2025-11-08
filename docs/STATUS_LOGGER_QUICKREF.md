# Snakemake Status Logger - Quick Reference

## Quick Start

```bash
# 1. Run the demo
python3 scripts/demo_status_logger.py

# 2. In another terminal, query status
python3 scripts/snakemake_status.py --port 5558
python3 scripts/snakemake_status.py --port 5558 --watch 2
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Get current workflow status with job counts |
| `/health` | GET | Health check |
| `/reset` | POST | Reset the status tracker |

## Status Response Format

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

## Command Line Tools

### Query Status
```bash
# Default (formatted output)
python3 scripts/snakemake_status.py

# JSON output
python3 scripts/snakemake_status.py --json

# Watch mode (refresh every 2 seconds)
python3 scripts/snakemake_status.py --watch 2

# Custom host/port
python3 scripts/snakemake_status.py --host 127.0.0.1 --port 5557
```

### Run Demo
```bash
# Run the demo workflow simulation
python3 scripts/demo_status_logger.py
```

## Configuration

```python
from vlog.snakemake_logger_plugin.logger import StatusLogHandlerSettings

settings = StatusLogHandlerSettings(
    port=5556,      # REST API port (default: 5556)
    host="127.0.0.1"  # REST API host (default: 127.0.0.1)
)
```

## Example cURL Commands

```bash
# Get status
curl http://127.0.0.1:5556/status

# Get status (pretty-printed)
curl http://127.0.0.1:5556/status | jq

# Health check
curl http://127.0.0.1:5556/health

# Reset tracker
curl -X POST http://127.0.0.1:5556/reset
```

## Integration Example

```python
import logging
from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler,
    StatusLogHandlerSettings,
)

# Setup
settings = StatusLogHandlerSettings(port=5556)
handler = StatusLogHandler(common_settings=..., settings=settings)

# Attach to Snakemake logger
snakemake_logger = logging.getLogger("snakemake")
snakemake_logger.addHandler(handler)

# Run your Snakemake workflow
# Handler will automatically capture job events
```

## Testing

```bash
# Run tests
python3 -m pytest tests/test_status_logger.py -v

# Run with coverage
python3 -m pytest tests/test_status_logger.py --cov=src/vlog/snakemake_logger_plugin
```

## Files

- `src/vlog/snakemake_logger_plugin/` - Plugin implementation
  - `logger.py` - Main logger handler and status tracker
  - `api_server.py` - FastAPI REST server
  - `__init__.py` - Package exports
- `scripts/snakemake_status.py` - CLI status query tool
- `scripts/demo_status_logger.py` - Demo simulation
- `tests/test_status_logger.py` - Test suite
- `docs/STATUS_LOGGER.md` - Full documentation

## See Also

- [Full Documentation](STATUS_LOGGER.md)
- [Snakemake Logger Plugin Interface](https://github.com/snakemake/snakemake-interface-logger-plugins)
