#!/bin/bash
# Run Snakemake video ingestion workflow
#
# This script provides a convenient wrapper around the Snakemake workflow
# for ingesting videos from an SD card.
#
# Usage:
#   ./scripts/run_snakemake.sh [OPTIONS]
#
# Options:
#   --dry-run          Show what will be done without executing
#   --cores N          Use N CPU cores (default: 1)
#   --sd-card PATH     Override SD card path from config
#   --forceall         Force reprocessing of all files
#   --help             Show this help message

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Default values
CORES=1
SNAKEMAKE_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            SNAKEMAKE_ARGS+=("--dry-run")
            shift
            ;;
        --cores)
            CORES="$2"
            shift 2
            ;;
        --sd-card)
            SNAKEMAKE_ARGS+=("--config" "sd_card_path=$2")
            shift 2
            ;;
        --forceall)
            SNAKEMAKE_ARGS+=("--forceall")
            shift
            ;;
        --help)
            echo "Run Snakemake video ingestion workflow"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run          Show what will be done without executing"
            echo "  --cores N          Use N CPU cores (default: 1)"
            echo "  --sd-card PATH     Override SD card path from config"
            echo "  --forceall         Force reprocessing of all files"
            echo "  --help             Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Preview the workflow"
            echo "  $0 --dry-run"
            echo ""
            echo "  # Run with custom SD card path"
            echo "  $0 --sd-card /Volumes/MY_SDCARD"
            echo ""
            echo "  # Use 4 cores for parallel processing"
            echo "  $0 --cores 4"
            echo ""
            echo "  # Force reprocess all videos"
            echo "  $0 --forceall"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

# Check if Snakemake is installed
if ! command -v snakemake &> /dev/null; then
    echo "Error: Snakemake is not installed"
    echo "Please install it with: pip install snakemake"
    echo "Or with uv: uv add snakemake"
    exit 1
fi

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "Error: config.yaml not found in $PROJECT_ROOT"
    echo "Please create config.yaml or run from the project root directory"
    exit 1
fi

echo "=== Snakemake Video Ingestion Workflow ==="
echo "Project root: $PROJECT_ROOT"
echo "Cores: $CORES"
if [[ " ${SNAKEMAKE_ARGS[*]} " =~ " --dry-run " ]]; then
    echo "Mode: DRY RUN (preview only)"
else
    echo "Mode: EXECUTE"
fi
echo "=========================================="
echo ""

# Run Snakemake
snakemake \
    --cores "$CORES" \
    --configfile config.yaml \
    "${SNAKEMAKE_ARGS[@]}"

echo ""
echo "Workflow complete!"
if [[ ! " ${SNAKEMAKE_ARGS[*]} " =~ " --dry-run " ]]; then
    echo ""
    echo "Results are in:"
    echo "  Main videos:    videos/main/"
    echo "  Preview videos: videos/preview/"
    echo "  JSON results:   videos/preview/*.json"
fi
