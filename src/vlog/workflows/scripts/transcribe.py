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

import logging
import sys
import argparse
import json
import math
from pathlib import Path
from typing import List, Dict

import os
os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = "/opt/homebrew/lib"

from mlx_whisper import transcribe
from vad_utils import get_speech_segments, load_vad_model
from opencc import OpenCC


def merge_transcription_segments(
    vad_segments: List[Dict],
    transcription_results: List[Dict]
) -> Dict:
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
    }
    languages = set()
    
    # Check if any transcription contains Chinese - if so, initialize OpenCC for s2tw conversion
    has_chinese = any(trans_result.get('language') == 'zh' for trans_result in transcription_results)
    cc = OpenCC('s2tw') if has_chinese else None
    
    for vad_seg, trans_result in zip(vad_segments, transcription_results):
        offset = vad_seg['start']
        print(trans_result)
        result_ok = False
        
        # Adjust segment timestamps and add to merged result
        for segment in trans_result.get("segments", []):
            # Skip segments with NaN avg_logprob
            avg_logprob = segment.get('avg_logprob')
            if avg_logprob is not None:
                if math.isnan(avg_logprob):
                    continue
                if avg_logprob < -1.0:  # Arbitrary threshold to filter low-confidence segments
                    continue
            result_ok = True
            if segment.get('compression_ratio', 100) > 3.0:
                print('Discarding high compression ratio segment: %s', segment)
                continue
            
            adjusted_segment = segment.copy()
            adjusted_segment['start'] += offset
            adjusted_segment['end'] += offset
            
            # Convert Chinese text if OpenCC is initialized
            if cc and 'text' in adjusted_segment:
                adjusted_segment['text'] = cc.convert(adjusted_segment['text'])
            
            # Adjust word timestamps if present
            if 'words' in adjusted_segment:
                adjusted_words = []
                for word in adjusted_segment['words']:
                    adjusted_word = word.copy()
                    adjusted_word['start'] += offset
                    adjusted_word['end'] += offset
                    # Convert Chinese word text if OpenCC is initialized
                    if cc and 'word' in adjusted_word:
                        adjusted_word['word'] = cc.convert(adjusted_word['word'])
                    adjusted_words.append(adjusted_word)
                adjusted_segment['words'] = adjusted_words
            
            merged["segments"].append(adjusted_segment)
        
        if result_ok:
            # Add text with space separator
            if merged["text"]:
                merged["text"] += " "
            text_to_add = trans_result.get("text", "")
            # Convert Chinese text if OpenCC is initialized
            if cc:
                text_to_add = cc.convert(text_to_add)
            merged["text"] += text_to_add
            languages.add(trans_result.get("language", 'en'))
        
    merged["language"] = list(languages)
    
    return merged


def run_transcribe(
    model: str,
    input_path: str,
    stem: str,
    output_dir: str,
) -> int:
    """Transcribe a single preview file using mlx_whisper Python API with optional VAD.

    Args:
        model: Model ID for mlx_whisper
        input_path: Path to input video/audio file
        stem: Output filename stem (without extension)
        output_dir: Directory to write output JSON

    Returns:
        0 on success, non-zero on failure.
    """
    logging.info("Transcribing %s with model %s", input_path, model)
    
    try:
        # Load VAD model if enabled
        vad_model = None
        vad_utils = None
        speech_segments = []
        
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
                    clip_timestamps=[segment['start'], segment['end']],
                    temperature=(0.0, 0.2, 0.4, 0.5)
                )
                transcription_results.append(result)
            
            # Merge results from all segments
            final_result = merge_transcription_segments(speech_segments, transcription_results)
        else:
            # No speech segments detected (or we are assuming silence for this run).
            # Instead of calling the model, return an empty transcription result
            # so downstream steps get a valid JSON with zero segments.
            logging.info(
                "No speech segments detected — writing empty transcription result instead of calling model"
            )
            final_result = {
                "text": "",
                "segments": [],
                "language": "unknown",
            }
        
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


def main_cli(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe a single preview video to JSON using mlx_whisper with VAD"
    )
    parser.add_argument("--model", required=True, help="Model id for mlx_whisper")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--stem", required=True, help="Output stem/name (no extension)")
    parser.add_argument("--output-dir", required=True, help="Directory to write output JSON")

    args = parser.parse_args(argv)
    return run_transcribe(
        args.model, args.input, args.stem, args.output_dir
    )


# Main execution logic
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Check if running under Snakemake by looking for the 'snakemake' object
    try:
        sm = snakemake  # type: ignore # noqa: F821
        # Running under Snakemake's `script:` directive
        model = sm.params.model
        input_path = str(sm.input[0])
        stem = str(sm.wildcards.stem)
        output_dir = str(sm.params.get('output_dir', sm.params.get('preview_folder', '.')))
        
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        exit_code = run_transcribe(model, input_path, stem, output_dir)
        if exit_code != 0:
            raise SystemExit(exit_code)
    except NameError:
        # Not running under Snakemake, use CLI arguments
        rc = main_cli()
        sys.exit(rc)
