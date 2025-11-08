#!/usr/bin/env python3
"""Transcribe a single preview video to SRT using mlx_whisper.

This script is intended to be run via Snakemake's `script:` directive where
the `snakemake` object is available, or run standalone from the CLI.

When run by Snakemake, it will read parameters from `snakemake.params` and
`snakemake.input`/`snakemake.wildcards`.

CLI usage:
    python transcribe_preview.py --model <model> --input <path> --stem <stem> --output-dir <dir>

Author: automated migration
"""
from __future__ import annotations

import logging
import sys
import argparse
from pathlib import Path
from mlx_whisper import transcribe
from mlx_whisper.cli import get_writer

sm = snakemake # type: ignore


def run_transcribe(model: str, input_path: str, stem: str, output_dir: str) -> int:
    """Transcribe a single preview file using mlx_whisper Python API.

    Returns 0 on success, non-zero on failure.
    """
    logging.info("Transcribing %s with model %s", input_path, model)
    
    try:
        # Call mlx_whisper.transcribe() directly
        result = transcribe(
            audio=input_path,
            path_or_hf_repo=model,
            verbose=None,  # Don't print progress to avoid cluttering logs
        )
        
        # Write output in SRT format
        writer = get_writer("srt", output_dir)
        
        # Create output file with the specified stem
        output_file = Path(output_dir) / f"{stem}.srt"
        with open(output_file, "w", encoding="utf-8") as f:
            writer(result, f, {"max_line_width": None, "max_line_count": None, "highlight_words": False})
        
        logging.info("Transcription completed: %s", output_file)
        return 0
        
    except Exception as e:
        logging.exception("Error during transcription: %s", e)
        return 2


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe a single preview video to SRT using mlx_whisper")
    parser.add_argument("--model", required=True, help="Model id for mlx_whisper")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--stem", required=True, help="Output stem/name (no extension)")
    parser.add_argument("--output-dir", required=True, help="Directory to write output SRT")

    args = parser.parse_args(argv)
    return run_transcribe(args.model, args.input, args.stem, args.output_dir)


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
    except NameError:
        raise RuntimeError("This script expects to be run under Snakemake or as a CLI script")

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    exit_code = run_transcribe(model, input_path, stem, output_dir)
    if exit_code != 0:
        raise SystemExit(exit_code)
