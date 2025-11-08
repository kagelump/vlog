#!/usr/bin/env bash
# Stop the describe daemon
#
# Usage: stop_daemon.sh <pid_file> <signal_file> <host> <port>
#
# Arguments:
#   pid_file: Path to daemon PID file
#   signal_file: Path to signal file indicating daemon is running
#   host: Host the daemon is bound to
#   port: Port the daemon is bound to

set -euo pipefail

PID_FILE="$1"
SIGNAL_FILE="$2"
HOST="$3"
PORT="$4"

echo "Stopping describe daemon..."

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found: $PID_FILE"
    echo "Daemon may not be running"
    # Clean up signal file anyway
    rm -f "$SIGNAL_FILE"
    exit 0
fi

# Read PID
DAEMON_PID=$(cat "$PID_FILE")
echo "Daemon PID: $DAEMON_PID"

# Check if process is running
if ! ps -p "$DAEMON_PID" > /dev/null 2>&1; then
    echo "Daemon process not running (stale PID file)"
    rm -f "$PID_FILE" "$SIGNAL_FILE"
    exit 0
fi

# Try graceful shutdown first (SIGTERM)
echo "Sending SIGTERM to daemon..."
kill "$DAEMON_PID" 2>/dev/null || true

# Wait for process to exit
MAX_WAIT=10
WAIT_COUNT=0
while ps -p "$DAEMON_PID" > /dev/null 2>&1; do
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo "Daemon did not exit gracefully, sending SIGKILL..."
        kill -9 "$DAEMON_PID" 2>/dev/null || true
        sleep 1
        break
    fi
    echo "Waiting for daemon to exit... ($WAIT_COUNT/$MAX_WAIT)"
    sleep 1
done

# Verify process is stopped
if ps -p "$DAEMON_PID" > /dev/null 2>&1; then
    echo "ERROR: Failed to stop daemon"
    exit 1
fi

# Clean up files
echo "Cleaning up PID and signal files..."
rm -f "$PID_FILE" "$SIGNAL_FILE"

echo "Daemon stopped successfully"
