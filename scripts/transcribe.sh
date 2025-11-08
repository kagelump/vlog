#!/usr/bin/env bash
# Transcribe a single video file using mlx_whisper with Silero VAD
#
# Usage: transcribe.sh <video_file> [model]
#
# Arguments:
#   video_file: Path to input video/audio file
#   model: (optional) MLX Whisper model ID (default: mlx-community/whisper-large-v3-turbo)
#
# Example:
#   transcribe.sh ./foobar.mp4
#   transcribe.sh ./foobar.mp4 mlx-community/whisper-large-v3-turbo

set -e

# Check if input file is provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <video_file> [model]"
    echo ""
    echo "Arguments:"
    echo "  video_file: Path to input video/audio file"
    echo "  model: (optional) MLX Whisper model ID (default: mlx-community/whisper-large-v3-turbo)"
    echo ""
    echo "Example:"
    echo "  $0 ./foobar.mp4"
    echo "  $0 ./foobar.mp4 mlx-community/whisper-large-v3-turbo"
    exit 1
fi

# Get input file path
INPUT_FILE="$1"

# Get model (use default if not provided)
MODEL="${2:-mlx-community/whisper-large-v3-turbo}"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE"
    exit 1
fi

# Get absolute path to input file
INPUT_FILE=$(cd "$(dirname "$INPUT_FILE")" && pwd)/$(basename "$INPUT_FILE")

# Extract stem (filename without extension)
STEM=$(basename "$INPUT_FILE" | sed 's/\.[^.]*$//')

# Get output directory (same as input file)
OUTPUT_DIR=$(dirname "$INPUT_FILE")

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Run transcription
echo "Transcribing: $INPUT_FILE"
echo "Model: $MODEL"
echo "Output directory: $OUTPUT_DIR"
echo "Stem: $STEM"
echo ""

cd "$PROJECT_ROOT"
uv run -- python src/vlog/workflows/scripts/transcribe.py \
    --model "$MODEL" \
    --input "$INPUT_FILE" \
    --stem "$STEM" \
    --output-dir "$OUTPUT_DIR"

echo ""
echo "Transcription complete!"
echo "Output: ${OUTPUT_DIR}/${STEM}_whisper.json"
