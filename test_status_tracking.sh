#!/bin/bash
# Test script to monitor status API while Snakemake runs

# Start monitoring the status API in background
(
    sleep 2  # Give Snakemake time to start
    for i in {1..30}; do
        echo "=== Status at $(date +%H:%M:%S) ==="
        curl -s http://127.0.0.1:5556/status | jq .
        sleep 1
    done
) &
MONITOR_PID=$!

# Run a small subset of jobs with debug logging
echo "Starting Snakemake with logger plugin..."
uv run -- snakemake \
    --snakefile ./src/ingest_pipeline/snakefiles/describe.smk \
    --configfile config.yaml \
    --config preview_folder="/Users/ryantseng/Desktop/2025 Yakushima/Pocket" \
    --logger=vlog \
    --logger-vlog-debug \
    --cores=2 \
    --resources=mem_gb=12 \
    --until describe \
    --forcerun DJI_20250906122551_0046_D.json DJI_20250906123249_0047_D.json \
    2>&1 | tee /tmp/snakemake_test.log

# Wait for monitor to finish
wait $MONITOR_PID

echo ""
echo "=== Final status ==="
curl -s http://127.0.0.1:5556/status | jq .
