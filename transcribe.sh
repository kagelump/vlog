#!/bin/bash
# transcribe_all.sh
# Transcribes all .mp4 files in the current directory to .srt using mlx_whisper

MODEL="mlx-community/whisper-large-v3-turbo"

for f in *.mp4 *.MP4; do
    echo "Transcribing: $f"
    mlx_whisper --model "$MODEL" -f srt --task transcribe "$f"
done

echo "All transcriptions complete."