# Describe.py Refactoring - Quick Reference

## Files Created

### Core Modules
1. **`src/vlog/describe_lib.py`** - Pure business logic library
2. **`src/vlog/describe_daemon.py`** - FastAPI REST API service  
3. **`src/vlog/describe_client.py`** - CLI client with daemon management

### Documentation
4. **`docs/DESCRIBE_ARCHITECTURE.md`** - Comprehensive architecture guide
5. **`docs/DESCRIBE_REFACTORING.md`** - Refactoring summary and migration guide

### Testing
6. **`scripts/test_describe_refactor.sh`** - Validation test script

### Modified
7. **`src/vlog/describe.py`** - Refactored to use library (maintains backward compatibility)
8. **`pyproject.toml`** - Added fastapi, uvicorn, requests dependencies

## Quick Commands

### Process Videos
```bash
# Single video
python -m vlog.describe_client video.mp4

# Multiple videos
python -m vlog.describe_client video1.mp4 video2.mp4 video3.mp4

# Custom output directory
python -m vlog.describe_client video.mp4 --output-dir ./results
```

### Run Daemon
```bash
# Start daemon (default: localhost:5555)
python -m vlog.describe_daemon

# Custom host/port
python -m vlog.describe_daemon --host 0.0.0.0 --port 8000

# With specific model
python -m vlog.describe_daemon --model mlx-community/Qwen3-VL-8B-Instruct-4bit
```

### API Usage
```bash
# Health check
curl http://localhost:5555/health

# Describe video
curl -X POST http://localhost:5555/describe \
  -H "Content-Type: application/json" \
  -d '{"filename": "/path/to/video.mp4", "fps": 1.0}'
```

### Validation
```bash
# Run all tests
./scripts/test_describe_refactor.sh

# Test imports
python3 -c "from vlog.describe_lib import describe_video; print('OK')"
```

## Architecture Summary

```
describe.py (original)
    ↓
┌───────────────────────────────────────────────────┐
│  describe_lib.py (Core Business Logic)           │
│  - describe_video()                               │
│  - load_model()                                   │
│  - validate_model_output()                        │
│  - Pydantic models                                │
└───────────────────────────────────────────────────┘
         ↑                    ↑                ↑
         │                    │                │
    ┌────┴────┐      ┌────────┴────────┐  ┌──┴───────┐
    │describe │      │describe_daemon  │  │describe_ │
    │.py      │      │.py              │  │client.py │
    │(legacy) │      │(FastAPI)        │  │(CLI)     │
    └─────────┘      └─────────────────┘  └──────────┘
                              ↑                 │
                              └─────HTTP────────┘
```

## Key Features

### describe_lib.py
- ✅ Pure functions (no side effects)
- ✅ Pydantic validation
- ✅ Adaptive FPS calculation
- ✅ Prompt template support
- ✅ Subtitle integration

### describe_daemon.py
- ✅ FastAPI REST API
- ✅ Model loaded once at startup
- ✅ Health check endpoint
- ✅ Automatic thumbnail extraction
- ✅ JSON response format

### describe_client.py
- ✅ Daemon lifecycle management
- ✅ Batch processing support
- ✅ JSON output next to videos
- ✅ Keep-alive option
- ✅ Retry logic with backoff

## Dependencies Added

```toml
"fastapi>=0.100.0"
"uvicorn>=0.23.0"
"requests>=2.31.0"
```

Install with:
```bash
pip install -e .
# or
uv pip install -e .
```

## Next Steps

1. ✅ **Install dependencies**: `pip install -e .`
2. ✅ **Run tests**: `./scripts/test_describe_refactor.sh`
3. ✅ **Try client**: `python -m vlog.describe_client --help`
4. 📖 **Read docs**: `docs/DESCRIBE_ARCHITECTURE.md`
5. 🚀 **Process videos**: Use client for batch jobs

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Modularity** | Monolithic | 3 focused modules |
| **Reusability** | Limited | Library can be imported anywhere |
| **Performance** | Load model per video | Load once, reuse |
| **Testing** | Hard to mock | Pure functions easy to test |
| **API** | None | REST API available |
| **Deployment** | Script only | Daemon as microservice |

## Backward Compatibility

✅ All existing code continues to work  
✅ No breaking changes to `describe.py` API  
✅ Old scripts don't need modification  
✅ New features available optionally  

---

For detailed documentation, see:
- `docs/DESCRIBE_ARCHITECTURE.md` - Full architecture guide
- `docs/DESCRIBE_REFACTORING.md` - Migration and usage guide
