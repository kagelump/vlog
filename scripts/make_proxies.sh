#!/usr/bin/env bash
# Batch create 720p H.264 proxies under a single "Proxies" folder,
# preserving the source directory tree and keeping the same filenames
# (this makes relinking in DaVinci Resolve straightforward).
#
# Requirements: ffmpeg, ffprobe (e.g. `brew install ffmpeg`)
# Usage: ./make_proxies.sh <input_dir> <output_dir>
set -euo pipefail

# Check arguments
if [ $# -ne 2 ]; then
  echo "Usage: $0 <input_dir> <output_dir>"
  echo "  input_dir:  Directory containing source videos"
  echo "  output_dir: Directory where proxies will be created"
  exit 1
fi

INROOT="$1"
OUTROOT="$2"

# Validate input directory
if [ ! -d "$INROOT" ]; then
  echo "Error: Input directory does not exist: $INROOT"
  exit 1
fi

BITRATE="2M"           # Target bitrate for proxies
AUDIO_BPS="64k"        # small audio
SHOULD_OVERWRITE=false # set to true to re-encode existing proxies

mkdir -p "$OUTROOT"

# Find all .mp4 files (case-insensitive) in the input directory
IFS=$'\n'
for src in $(find "$INROOT" -type f -iname '*.mp4'); do
  # Get relative path from input root
  rel="${src#$INROOT/}"
  dest_dir="$OUTROOT/$(dirname "$rel")"
  mkdir -p "$dest_dir"
  out="$dest_dir/$(basename "$src")"  # same filename (no suffix) to help Resolve relink

  if [ -f "$out" ] && [ "$SHOULD_OVERWRITE" = "false" ]; then
    echo "Skipping (exists): $out"
    continue
  fi

  # Get source frame rate as reported by ffprobe (e.g. 30000/1001 or 24)
  fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate \
    -of default=noprint_wrappers=1:nokey=1 "$src" || echo "")

  echo "Encoding: $src -> $out (fps=$fps)"

  # Build ffmpeg command with optional fps arguments
  fps_args=()
  if [ -n "$fps" ]; then
    fps_args=(-r "$fps" -vsync cfr)
  fi

  # Run ffmpeg encode
  ffmpeg -y -hide_banner -stats -hwaccel videotoolbox -i "$src" \
    -map_metadata 0 \
    -c:v h264_videotoolbox -b:v "$BITRATE" -profile:v high -level 4.1 -pix_fmt yuv420p \
    -vf "scale=-2:720" \
    "${fps_args[@]}" \
    -c:a aac -b:a "$AUDIO_BPS" -ac 1 \
    -movflags +faststart \
    "$out"

  echo "Done: $out"
done

echo "All finished. Proxies root: $OUTROOT"