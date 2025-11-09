#!/usr/bin/env bash
# Batch create 720p H.264 proxies under a single "Proxies" folder,
# preserving the source directory tree and keeping the same filenames
# (this makes relinking in DaVinci Resolve straightforward).
#
# Requirements: ffmpeg, ffprobe (e.g. `brew install ffmpeg`)
# Usage: place in the root of your media tree and run: ./make_proxies.sh
set -euo pipefail

OUTROOT="Proxies"
CRF=28                 # 24-28 recommended for small proxies; lower = higher quality/larger files
PRESET="slower"        # slower -> better compression; change to "fast" if you need speed
AUDIO_BPS="64k"        # small audio
SHOULD_OVERWRITE=false # set to true to re-encode existing proxies

mkdir -p "$OUTROOT"

# Find all .mp4 files (case-insensitive), skip files already inside the OUTROOT
IFS=$'\n'
for src in $(find . -type f -iname '*.mp4' -not -path "./$OUTROOT/*"); do
  # Normalize path (remove leading ./)
  rel="${src#./}"
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

  # Run ffmpeg encode
  ffmpeg -y -hide_banner -loglevel error -i "$src" \
    -map_metadata 0 \
    -c:v libx264 -preset "$PRESET" -crf "$CRF" -profile:v high -level 4.1 -pix_fmt yuv420p \
    -vf "scale=-2:720" \
    $( [ -n "$fps" ] && printf -- "-r %s -vsync cfr" "$fps" ) \
    -c:a aac -b:a "$AUDIO_BPS" -ac 1 \
    -movflags +faststart \
    "$out"

  echo "Done: $out"
done

echo "All finished. Proxies root: $OUTROOT"