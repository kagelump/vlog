#!/bin/bash
# Script to run Snakemake with the status logger plugin enabled

# Default values
CONFIG_FILE="config.yaml"
SNAKEFILE="src/vlog/workflows/Snakefile"
CORES=1
LOGGER_PORT=5556
LOGGER_HOST="127.0.0.1"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --snakefile)
            SNAKEFILE="$2"
            shift 2
            ;;
        --cores)
            CORES="$2"
            shift 2
            ;;
        --logger-port)
            LOGGER_PORT="$2"
            shift 2
            ;;
        --logger-host)
            LOGGER_HOST="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options] [snakemake_args...]"
            echo ""
            echo "Options:"
            echo "  --config FILE         Config file (default: config.yaml)"
            echo "  --snakefile FILE      Snakefile (default: src/vlog/workflows/Snakefile)"
            echo "  --cores N             Number of cores (default: 1)"
            echo "  --logger-port PORT    Logger API port (default: 5556)"
            echo "  --logger-host HOST    Logger API host (default: 127.0.0.1)"
            echo "  --help                Show this help"
            echo ""
            echo "Any additional arguments are passed directly to snakemake."
            echo ""
            echo "Examples:"
            echo "  $0"
            echo "  $0 --cores 4"
            echo "  $0 stage2 --cores 2"
            echo "  $0 --snakefile src/vlog/workflows/snakefiles/subtitles.smk"
            exit 0
            ;;
        *)
            # Pass remaining args to snakemake
            break
            ;;
    esac
done

# Check if snakefile exists
if [ ! -f "$SNAKEFILE" ]; then
    echo "Error: Snakefile not found: $SNAKEFILE"
    exit 1
fi

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Set PYTHONPATH to include src directory
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

echo "Running Snakemake with status logger plugin..."
echo "  Snakefile: $SNAKEFILE"
echo "  Config: $CONFIG_FILE"
echo "  Cores: $CORES"
echo "  Logger API: http://${LOGGER_HOST}:${LOGGER_PORT}/status"
echo ""
echo "To query status in another terminal:"
echo "  python3 scripts/snakemake_status.py"
echo "  python3 scripts/snakemake_status.py --watch 2  # refresh every 2 seconds"
echo ""

# Run snakemake with the logger plugin
# Note: This requires the plugin to be installed as a proper entry point
# For now, we'll use a custom logger that we instantiate programmatically
python3 -c "
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from vlog.snakemake_logger_plugin.logger import StatusLogHandler, StatusLogHandlerSettings
from vlog.snakemake_logger_plugin.api_server import start_api_server

# Start the API server
print('Starting status API server...')
start_api_server('$LOGGER_HOST', $LOGGER_PORT)

# Import and run snakemake
from snakemake import snakemake
from snakemake.settings import OutputSettings

# Create custom logger handler
settings = StatusLogHandlerSettings(port=$LOGGER_PORT, host='$LOGGER_HOST')

# This is a workaround since we're not installing as a proper plugin
# The handler will be attached via the logging system
handler = StatusLogHandler(
    common_settings=None,  # Will be set by snakemake
    settings=settings
)

# Get root logger and add our handler
root_logger = logging.getLogger('snakemake')
# root_logger.addHandler(handler)

# Run snakemake
success = snakemake(
    snakefile='$SNAKEFILE',
    configfiles=['$CONFIG_FILE'],
    cores=$CORES,
    printshellcmds=True,
    $@
)

sys.exit(0 if success else 1)
" "$@"
