#!/bin/bash
# Setup configuration for DaVinci Resolve integration
# This script creates a config file that the davinci_clip_importer.py script can use

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

CONFIG_DIR="$HOME/.vlog"
CONFIG_FILE="$CONFIG_DIR/config"

echo "Setting up vlog configuration for DaVinci Resolve integration..."
echo ""

# Create config directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Creating config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
fi

# Write project path to config file
echo "Writing project path to: $CONFIG_FILE"
echo "PROJECT_PATH=$PROJECT_DIR" > "$CONFIG_FILE"

echo ""
echo "Configuration complete!"
echo ""
echo "Project path set to: $PROJECT_DIR"
echo ""
echo "You can now use davinci_clip_importer.py from DaVinci Resolve."
echo ""
echo "To copy the importer script to DaVinci Resolve's script directory:"
echo "  cp $PROJECT_DIR/src/vlog/davinci_clip_importer.py /path/to/davinci/resolve/scripts/"
echo ""
echo "Alternatively, you can set the VLOG_PROJECT_PATH environment variable:"
echo "  export VLOG_PROJECT_PATH=$PROJECT_DIR"
echo ""
