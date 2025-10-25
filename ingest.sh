#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/transcribe.sh"
python3 "$SCRIPT_DIR/srt_cleaner.py"
python3 "$SCRIPT_DIR/describe.py" "$@"