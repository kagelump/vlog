#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Add src to PYTHONPATH so vlog package can be imported
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"

"$SCRIPT_DIR/transcribe.sh"
python3 "${PROJECT_ROOT}/src/vlog/srt_cleaner.py"
python3 "${PROJECT_ROOT}/src/vlog/describe.py" "$@"