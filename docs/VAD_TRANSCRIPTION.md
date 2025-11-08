# VAD-Enhanced Transcription

This document describes the VAD (Voice Activity Detection) enhancement to the transcription pipeline, which reduces hallucinations and improves accuracy.

## Overview

The transcription workflow has been enhanced with:

1. **Silero VAD Integration**: Detects speech segments before transcription
2. **JSON Intermediate Format**: Rich metadata preservation with word-level timestamps
3. **Improved Cleaning**: Access to more signals for hallucination detection

## Architecture

### Workflow

```
Video → VAD Detection → Transcription → JSON → Cleaning → SRT
```

### Components

1. **vad_utils.py** - Voice Activity Detection utilities
   - Loads Silero VAD model from torch.hub
   - Detects speech segments in audio
   - Returns timestamps of speech regions

2. **transcribe.py** - Enhanced transcription script
   - Runs VAD to identify speech segments
   - Transcribes only speech (skips silence/noise)
   - Outputs JSON with word timestamps (_whisper.json)

3. **srt_cleaner.py** - JSON to SRT converter
   - Reads Whisper JSON output
   - Accesses word-level timestamps and metadata
   - Removes duplicates and hallucinations
   - Outputs clean SRT file (_cleaned.srt)

## File Formats

### Input

Video/audio file (`.mp4`, `.mov`, etc.)

### Intermediate: Whisper JSON (_whisper.json)

```json
{
  "text": "Full transcribed text",
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello world.",
      "words": [
        {"start": 0.0, "end": 0.5, "word": "Hello"},
        {"start": 0.6, "end": 1.2, "word": "world"}
      ]
    }
  ],
  "language": "en"
}
```

### Output: Cleaned SRT (_cleaned.srt)

```srt
1
00:00:00,000 --> 00:00:02,500
Hello world.

2
00:00:02,500 --> 00:00:05,000
This is a test.
```

## Usage

### Via Snakemake (Recommended)

```bash
# Run the full subtitle pipeline (stage 2)
snakemake --snakefile src/vlog/workflows/subtitles.smk --cores 1 --configfile config.yaml
```

This will:
1. Transcribe preview videos to JSON with VAD
2. Clean and convert to SRT

### Manual Transcription

```bash
# With VAD (recommended)
python src/vlog/workflows/scripts/transcribe.py \
  --model mlx-community/whisper-large-v3-turbo \
  --input video.mp4 \
  --stem video \
  --output-dir output/

# Without VAD
python src/vlog/workflows/scripts/transcribe.py \
  --model mlx-community/whisper-large-v3-turbo \
  --input video.mp4 \
  --stem video \
  --output-dir output/ \
  --no-vad
```

### Manual Cleaning

```python
from srt_cleaner import process_json_to_srt

# Convert JSON to clean SRT
process_json_to_srt("video_whisper.json", "video_cleaned.srt")
```

## Configuration

In `config.yaml`:

```yaml
transcribe:
  model: "mlx-community/whisper-large-v3-turbo"
```

VAD is enabled by default in the Snakemake workflow. To disable:

```python
# In subtitles.smk
params:
    model=TRANSCRIBE_MODEL,
    use_vad=False  # Disable VAD
```

## VAD Parameters

The `vad_utils.py` module provides configurable parameters:

- `threshold`: Speech probability threshold (default: 0.5)
- `min_speech_duration_ms`: Minimum speech segment duration (default: 250ms)
- `min_silence_duration_ms`: Minimum silence between segments (default: 100ms)
- `padding_duration_ms`: Padding around speech segments (default: 30ms)

## Benefits

1. **Reduced Hallucination**: Only transcribes actual speech, avoiding noise/silence transcription
2. **Better Accuracy**: VAD pre-filtering improves transcription quality
3. **Rich Metadata**: Word-level timestamps enable better post-processing
4. **Better Cleaning**: Access to confidence scores and timing for hallucination detection

## Inspiration

This implementation is inspired by [WhisperX](https://github.com/m-bain/whisperX), which uses VAD for improved transcription accuracy. However, we omit diarization as it's not needed for our use case.

## Testing

Run the test suite:

```bash
pytest tests/test_vad_transcribe.py -v
```

Tests cover:
- VAD utility functions
- JSON parsing and conversion
- Hallucination detection
- Duplicate removal
- SRT formatting

## Dependencies

- `torch`: PyTorch for Silero VAD model
- `torchaudio`: Audio processing for VAD
- `mlx-whisper`: Transcription engine
- Silero VAD model is loaded from torch.hub (no separate installation needed)

## Troubleshooting

### VAD fails to load

If Silero VAD fails to load, transcription will fall back to processing the full audio without VAD. Check the logs for warnings:

```
WARNING: VAD utilities not available - will transcribe full audio
```

### No speech detected

If VAD detects no speech segments, the entire audio will be transcribed as a fallback.

### Output files

- `_whisper.json`: Intermediate JSON output from transcription
- `_cleaned.srt`: Final cleaned subtitle file

Both files are kept for debugging and potential future use of the rich JSON metadata.
