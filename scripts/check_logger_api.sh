#!/usr/bin/env bash
# Check if the Snakemake logger API is running and accessible

set -e

LOGGER_HOST="${1:-127.0.0.1}"
LOGGER_PORT="${2:-5556}"

echo "Checking Snakemake logger API..."
echo "Host: $LOGGER_HOST"
echo "Port: $LOGGER_PORT"
echo ""

# Check if something is listening on the port
echo "1. Checking if port $LOGGER_PORT is in use..."
if command -v lsof &> /dev/null; then
    lsof -i :$LOGGER_PORT || echo "   Port $LOGGER_PORT is not in use"
elif command -v netstat &> /dev/null; then
    netstat -an | grep $LOGGER_PORT || echo "   Port $LOGGER_PORT is not in use"
else
    echo "   (lsof/netstat not available, skipping port check)"
fi
echo ""

# Try to connect to the health endpoint
echo "2. Testing logger API health endpoint..."
if command -v curl &> /dev/null; then
    if curl -s -m 2 "http://${LOGGER_HOST}:${LOGGER_PORT}/health" 2>/dev/null; then
        echo ""
        echo "✓ Logger API is responding!"
    else
        echo "✗ Logger API is not responding"
        echo ""
        echo "This is normal if Snakemake is not currently running."
        echo "The logger API starts automatically when Snakemake runs with --logger vlog"
    fi
else
    echo "   (curl not available, skipping health check)"
fi
echo ""

# Try to get status
echo "3. Testing logger API status endpoint..."
if command -v curl &> /dev/null; then
    echo "GET http://${LOGGER_HOST}:${LOGGER_PORT}/status"
    curl -s -m 2 "http://${LOGGER_HOST}:${LOGGER_PORT}/status" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "✗ Logger API is not responding or returned invalid JSON"
else
    echo "   (curl not available, skipping status check)"
fi
echo ""

echo "Summary:"
echo "- The logger API starts automatically when Snakemake runs with: --logger vlog --logger-vlog-port $LOGGER_PORT"
echo "- If auto-ingest is running, check the Snakemake process is using these flags"
echo "- The API will be unavailable when no Snakemake workflow is active"
