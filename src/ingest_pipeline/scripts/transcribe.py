#!/usr/bin/env python3
"""Transcribe a single preview video to JSON using mlx_whisper with Silero VAD.

This script uses Voice Activity Detection (VAD) to identify speech segments
before transcription, reducing hallucinations from silence/noise.

The output is in JSON format (_whisper.json) which preserves word-level
timestamps and metadata for downstream processing.

This script is intended to be run via Snakemake's `script:` directive where
the `snakemake` object is available, or run standalone from the CLI.

When run by Snakemake, it will read parameters from `snakemake.params` and
`snakemake.input`/`snakemake.wildcards`.

CLI usage:
    python transcribe.py --model <model> --input <path> --stem <stem> --output-dir <dir> [--use-vad]

Author: automated migration with VAD integration
"""
from __future__ import annotations

import logging
import sys
import argparse
import json
from pathlib import Path
from mlx_whisper import transcribe
from mlx_whisper.cli import get_writer
from vad_utils import get_speech_segments, load_vad_model

sm = snakemake # type: ignore


def merge_transcription_segments(
    vad_segments: list[dict],
    transcription_results: list[dict]
) -> dict:
    """
    Merge multiple transcription results from VAD segments into a single result.
    
    Args:
        vad_segments: List of VAD segments with 'start' and 'end' times
        transcription_results: List of transcription results (one per VAD segment)
        
    Returns:
        Merged transcription result dict
    """
    merged = {
        "text": "",
        "segments": [],
        "language": transcription_results[0].get("language", "en") if transcription_results else "en"
    }
    
    for vad_seg, trans_result in zip(vad_segments, transcription_results):
        offset = vad_seg['start']
        
        # Add text with space separator
        if merged["text"]:
            merged["text"] += " "
        merged["text"] += trans_result.get("text", "")
        
        # Adjust segment timestamps and add to merged result
        for segment in trans_result.get("segments", []):
            adjusted_segment = segment.copy()
            adjusted_segment['start'] += offset
            adjusted_segment['end'] += offset
            
            # Adjust word timestamps if present
            if 'words' in adjusted_segment:
                adjusted_words = []
                for word in adjusted_segment['words']:
                    adjusted_word = word.copy()
                    adjusted_word['start'] += offset
                    adjusted_word['end'] += offset
                    adjusted_words.append(adjusted_word)
                adjusted_segment['words'] = adjusted_words
            
            merged["segments"].append(adjusted_segment)
    
    return merged


def run_transcribe(
    model: str,
    input_path: str,
    stem: str,
    output_dir: str,
    use_vad: bool = True
) -> int:
    """Transcribe a single preview file using mlx_whisper Python API with optional VAD.

    Args:
        model: Model ID for mlx_whisper
        input_path: Path to input video/audio file
        stem: Output filename stem (without extension)
        output_dir: Directory to write output JSON
        use_vad: Whether to use Silero VAD for speech detection (default: True)

    Returns:
        0 on success, non-zero on failure.
    """
    logging.info("Transcribing %s with model %s (VAD: %s)", input_path, model, use_vad)
    
    try:
        # Load VAD model if enabled
        vad_model = None
        vad_utils = None
        speech_segments = []
        
        if use_vad:
            logging.info("Loading Silero VAD model...")
            vad_model, vad_utils = load_vad_model()
            
            # Detect speech segments
            logging.info("Detecting speech segments...")
            speech_segments = get_speech_segments(
                input_path,
                vad_model=vad_model,
                vad_utils=vad_utils
            )
            logging.info(f"Detected {len(speech_segments)} speech segments")
        
        # Transcribe based on VAD results
        if speech_segments:
            # Transcribe each speech segment separately
            logging.info("Transcribing %d speech segments...", len(speech_segments))
            transcription_results = []
            
            for i, segment in enumerate(speech_segments, 1):
                logging.info(f"Transcribing segment {i}/{len(speech_segments)}: "
                           f"{segment['start']:.2f}s - {segment['end']:.2f}s")
                
                # Transcribe segment with word timestamps enabled
                result = transcribe(
                    audio=input_path,
                    path_or_hf_repo=model,
                    verbose=None,
                    word_timestamps=True,  # Enable for richer metadata
                    clip_timestamps=[segment['start'], segment['end']]
                )
                transcription_results.append(result)
            
            # Merge results from all segments
            final_result = merge_transcription_segments(speech_segments, transcription_results)
        else:
            # Transcribe entire file without VAD
            logging.info("Transcribing full audio (no VAD segments detected or VAD disabled)...")
            final_result = transcribe(
                audio=input_path,
                path_or_hf_repo=model,
                verbose=None,
                word_timestamps=True,  # Enable for richer metadata
            )
        
        # Write output in JSON format
        output_file = Path(output_dir) / f"{stem}_whisper.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        
        logging.info("Transcription completed: %s", output_file)
        logging.info(f"  Total segments: {len(final_result.get('segments', []))}")
        logging.info(f"  Detected language: {final_result.get('language', 'unknown')}")
        return 0
        
    except Exception as e:
        logging.exception("Error during transcription: %s", e)
        return 2


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe a single preview video to JSON using mlx_whisper with VAD"
    )
    parser.add_argument("--model", required=True, help="Model id for mlx_whisper")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--stem", required=True, help="Output stem/name (no extension)")
    parser.add_argument("--output-dir", required=True, help="Directory to write output JSON")
    parser.add_argument(
        "--use-vad",
        action="store_true",
        default=True,
        help="Use Silero VAD for speech detection (default: True)"
    )
    parser.add_argument(
        "--no-vad",
        dest="use_vad",
        action="store_false",
        help="Disable VAD and transcribe full audio"
    )

    args = parser.parse_args(argv)
    return run_transcribe(
        args.model, args.input, args.stem, args.output_dir, args.use_vad
    )


# Support being invoked as a Snakemake script: the runtime will provide a
# `snakemake` object with `.params`, `.input`, `.wildcards`, etc.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # If called directly, act as CLI
    rc = main_cli()
    sys.exit(rc)
else:
    # Running under Snakemake's `script:` directive
    try:
        # `snakemake` is injected by Snakemake when using `script:`
        model = sm.params.model
        input_path = str(sm.input[0])
        stem = str(sm.wildcards.stem)
        output_dir = str(sm.params.get('output_dir', sm.params.get('preview_folder', '.')))
        use_vad = sm.params.get('use_vad', True)  # Default to True
    except NameError:
        raise RuntimeError("This script expects to be run under Snakemake or as a CLI script")

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    exit_code = run_transcribe(model, input_path, stem, output_dir, use_vad)
    if exit_code != 0:
        raise SystemExit(exit_code)
