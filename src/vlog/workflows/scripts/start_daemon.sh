#!/usr/bin/env bash
# Start the describe daemon for video description processing
#
# Usage: start_daemon.sh <model> <host> <port> <log_file> <pid_file> <signal_file>
#
# Arguments:
#   model: MLX model to use (e.g., mlx-community/Qwen3-VL-8B-Instruct-4bit)
#   host: Host to bind daemon to (e.g., 127.0.0.1)
#   port: Port to bind daemon to (e.g., 5555)
#   log_file: Path to daemon log file
#   pid_file: Path to store daemon PID
#   signal_file: Path to signal file indicating daemon is running

set -euo pipefail

MODEL="$1"
HOST="$2"
PORT="$3"
LOG_FILE="$4"
PID_FILE="$5"
SIGNAL_FILE="$6"

echo "Starting describe daemon..."
echo "Model: $MODEL"
echo "Host: $HOST"
echo "Port: $PORT"
echo "Log file: $LOG_FILE"
echo "PID file: $PID_FILE"
echo "Signal file: $SIGNAL_FILE"

# Create directories if needed
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$PID_FILE")"
mkdir -p "$(dirname "$SIGNAL_FILE")"

# Check if daemon is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Daemon already running with PID $OLD_PID"
        # Create signal file if it doesn't exist
        touch "$SIGNAL_FILE"
        exit 0
    else
        echo "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Start the daemon in the background
echo "Launching daemon process..."
nohup uv run -- python -m vlog.describe_daemon \
    --model "$MODEL" \
    --host "$HOST" \
    --port "$PORT" \
    >> "$LOG_FILE" 2>&1 &

DAEMON_PID=$!

# Save PID
echo "$DAEMON_PID" > "$PID_FILE"
echo "Daemon started with PID: $DAEMON_PID"

# Wait a moment for the daemon to initialize
echo "Waiting for daemon to initialize..."
sleep 2

# Check if daemon is still running
if ! ps -p "$DAEMON_PID" > /dev/null 2>&1; then
    echo "ERROR: Daemon failed to start. Check log file: $LOG_FILE"
    cat "$LOG_FILE" | tail -20
    exit 1
fi

# Wait for daemon to be ready (check health endpoint)
MAX_RETRIES=30
RETRY_COUNT=0
echo "Checking daemon health endpoint..."
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
        echo "Daemon is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "Waiting for daemon to respond (attempt $RETRY_COUNT/$MAX_RETRIES)..."
        sleep 1
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Daemon health check timed out after $MAX_RETRIES attempts"
    echo "Last 20 lines of log file:"
    cat "$LOG_FILE" | tail -20
    # Kill the daemon
    kill "$DAEMON_PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
fi

# Create signal file to indicate daemon is running
touch "$SIGNAL_FILE"
echo "Daemon is running and ready at http://${HOST}:${PORT}"
echo "Signal file created: $SIGNAL_FILE"
