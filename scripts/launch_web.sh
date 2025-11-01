#!/usr/bin/env bash
set -euo pipefail

# Launch the integrated web UI using the project's uv-managed venv.
# Usage: ./scripts/launch_web.sh [--port PORT] [--detached]
# Examples:
#   ./scripts/launch_web.sh --port 5432
#   ./scripts/launch_web.sh --detached

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PORT=5432
DETACHED=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"; shift 2;;
    --detached)
      DETACHED=1; shift;;
    -h|--help)
      echo "Usage: $0 [--port PORT] [--detached]"; exit 0;;
    *)
      echo "Unknown arg: $1"; exit 1;;
  esac
done

CMD=(uv run -- python -m vlog.web_integrated)

if [ -n "$PORT" ]; then
  CMD+=(-- --port "$PORT")
fi

if [ "$DETACHED" -eq 1 ]; then
  echo "Starting web UI on port $PORT (detached). Logs -> web_ui.log"
  nohup "${CMD[@]}" > web_ui.log 2>&1 &
  disown
  exit 0
else
  echo "Starting web UI on port $PORT"
  exec "${CMD[@]}"
fi
