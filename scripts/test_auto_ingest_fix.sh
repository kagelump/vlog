#!/usr/bin/env bash
# Test script to verify auto-ingest progress monitoring fixes

set -e

echo "=========================================="
echo "Auto-Ingest Progress Monitoring Test"
echo "=========================================="
echo ""

# Check if web server is running
echo "1. Checking if web server is running..."
if curl -s -f http://localhost:5432/ > /dev/null 2>&1; then
    echo "   ✓ Web server is running on port 5432"
else
    echo "   ✗ Web server is NOT running"
    echo "   Start it with: uv run -- python src/vlog/web.py"
    exit 1
fi
echo ""

# Check auto-ingest status
echo "2. Checking auto-ingest status..."
STATUS=$(curl -s http://localhost:5432/api/auto-ingest-snakemake/status)
echo "   Response: $STATUS"
IS_RUNNING=$(echo "$STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('is_running', False))")
echo "   Is running: $IS_RUNNING"
echo ""

# Check progress endpoint
echo "3. Checking progress endpoint..."
PROGRESS_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" http://localhost:5432/api/auto-ingest-snakemake/progress)
PROGRESS_BODY=$(echo "$PROGRESS_RESPONSE" | sed -n '1,/HTTP_STATUS:/p' | sed '$d')
HTTP_STATUS=$(echo "$PROGRESS_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)

echo "   HTTP Status: $HTTP_STATUS"
echo "   Response body:"
echo "$PROGRESS_BODY" | python3 -m json.tool 2>/dev/null || echo "$PROGRESS_BODY"
echo ""

# Analyze the response
IS_AVAILABLE=$(echo "$PROGRESS_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('available', 'unknown'))" 2>/dev/null || echo "error")
HAS_ERROR=$(echo "$PROGRESS_BODY" | python3 -c "import sys, json; print('error' in json.load(sys.stdin))" 2>/dev/null || echo "unknown")
HAS_MESSAGE=$(echo "$PROGRESS_BODY" | python3 -c "import sys, json; print('message' in json.load(sys.stdin))" 2>/dev/null || echo "unknown")

echo "4. Analysis:"
echo "   Available: $IS_AVAILABLE"
echo "   Has error: $HAS_ERROR"
echo "   Has message: $HAS_MESSAGE"
echo ""

# Check if Snakemake is running
echo "5. Checking if Snakemake process is running..."
if ps aux | grep -i snakemake | grep -v grep > /dev/null 2>&1; then
    echo "   ✓ Snakemake process is running"
    ps aux | grep -i snakemake | grep -v grep
else
    echo "   ✗ Snakemake process is NOT running"
    echo "   This is expected if auto-ingest hasn't detected any new files"
fi
echo ""

# Check logger API directly
echo "6. Checking logger API directly on port 5556..."
if curl -s -f http://127.0.0.1:5556/health > /dev/null 2>&1; then
    echo "   ✓ Logger API is responding"
    curl -s http://127.0.0.1:5556/status | python3 -m json.tool
else
    echo "   ✗ Logger API is not responding (normal if Snakemake not running)"
fi
echo ""

echo "=========================================="
echo "Summary:"
echo "=========================================="
if [ "$IS_RUNNING" = "True" ] || [ "$IS_RUNNING" = "true" ]; then
    echo "✓ Auto-ingest is ACTIVE"
    echo ""
    echo "Expected behavior:"
    echo "- If no files to process: Progress shows message 'No workflow currently running'"
    echo "- If Snakemake is running: Progress shows job counts and stages"
    echo "- If error: Progress shows error message with 503 status"
else
    echo "✗ Auto-ingest is NOT active"
    echo ""
    echo "To test:"
    echo "1. Start auto-ingest via web UI (http://localhost:5432)"
    echo "2. Or via API:"
    echo "   curl -X POST http://localhost:5432/api/auto-ingest-snakemake/start \\"
    echo "        -H 'Content-Type: application/json' \\"
    echo "        -d '{\"watch_directory\":\"/path/to/videos\"}'"
fi
echo ""
