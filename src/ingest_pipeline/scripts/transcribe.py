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
import subprocess
import sys
import argparse
from pathlib import Path


def run_transcribe(model: str, input_path: str, stem: str, output_dir: str) -> int:
    """Invoke mlx_whisper to transcribe a single preview file.

    Returns the subprocess exit code.
    """
    cmd = [
        "mlx_whisper",
        "--model",
        model,
        "-f",
        "srt",
        "--task",
        "transcribe",
        input_path,
        "--output-name",
        stem,
        "--output-dir",
        output_dir,
    ]

    logging.info("Running command: %s", " ".join(cmd))
    try:
        # Stream output directly to the console
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        logging.error("mlx_whisper binary not found. Ensure mlx_whisper is installed and on PATH.")
        return 2
    except Exception as e:
        logging.exception("Error running mlx_whisper: %s", e)
        return 3


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
        model = snakemake.params.model
        input_path = str(snakemake.input[0])
        stem = str(snakemake.wildcards.stem)
        output_dir = str(snakemake.params.get('output_dir', snakemake.params.get('preview_folder', '.')))
    except NameError:
        raise RuntimeError("This script expects to be run under Snakemake or as a CLI script")

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    exit_code = run_transcribe(model, input_path, stem, output_dir)
    if exit_code != 0:
        raise SystemExit(exit_code)
