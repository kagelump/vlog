#!/usr/bin/env python3
"""
Run Snakemake workflow for a single video file in local mode.

This script is designed to be called by auto_ingest to process individual files
using the Snakemake pipeline. It creates a temporary config and runs Snakemake
targeting just the specific file.
"""

import sys
import os
import subprocess
import tempfile
import yaml
from pathlib import Path


def run_snakemake_for_file(
    video_file: str,
    model_name: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit",
) -> tuple[bool, str]:
    """
    Run Snakemake workflow for a single video file in local mode.
    
    In local mode:
    - The video file is already in place (not copied from SD card)
    - No preview file creation (works with the main file directly)
    - Outputs JSON file in the same directory as the video
    
    Args:
        video_file: Path to the video file to process
        model_name: ML model to use for description
        
    Returns:
        Tuple of (success: bool, json_path: str)
    """
    video_path = Path(video_file).resolve()
    
    if not video_path.exists():
        print(f"Error: Video file does not exist: {video_file}", file=sys.stderr)
        return False, ""
    
    # Get directory and stem
    video_dir = video_path.parent
    stem = video_path.stem
    extension = video_path.suffix[1:]  # Remove leading dot
    
    # Create a temporary config file for local mode processing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            # Local mode configuration
            'sd_card_path': str(video_dir),  # Use video directory as "source"
            'main_folder': str(video_dir),   # Keep everything in same directory
            'preview_folder': str(video_dir),
            'video_extensions': [extension],
            'preview_suffix': '_preview',
            'preview_extension': extension,
            'preview_settings': {
                'width': 1280,
                'crf': 23,
                'preset': 'medium'
            },
            'transcribe': {
                'model': 'mlx-community/whisper-large-v3-turbo'
            },
            'describe': {
                'model': model_name,
                'max_pixels': 224
            }
        }
        yaml.dump(config, f)
        temp_config = f.name
    
    try:
        # Get the project root (parent of scripts directory)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        snakefile = project_root / 'Snakefile'
        
        if not snakefile.exists():
            print(f"Error: Snakefile not found at {snakefile}", file=sys.stderr)
            return False, ""
        
        # Target: the final JSON file for this video
        json_target = f"{video_dir}/{stem}.json"
        
        # Run Snakemake with the specific target
        # Use explicit quiet-mode argument for Snakemake >=8 ('progress' is a
        # supported choice) so the json_target is not mistaken for the quiet
        # flag value.
        cmd = [
            'snakemake',
            '--snakefile', str(snakefile),
            '--configfile', temp_config,
            '--cores', '1',
            '--quiet', 'progress',  # Reduce output noise
            '--',
            json_target
        ]
        
        print(f"Running Snakemake for: {video_path.name}: {cmd}")
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Snakemake failed for {video_path.name}:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            return False, ""
        
        print(f"Successfully processed: {video_path.name}")
        return True, json_target
        
    finally:
        # Clean up temporary config file
        try:
            os.unlink(temp_config)
        except OSError:
            # Ignore cleanup errors - temp file will be cleaned by system eventually
            # Could log at debug level if needed
            pass


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: run_snakemake_single_file.py <video_file> [model_name]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Example: run_snakemake_single_file.py /path/to/video.mp4", file=sys.stderr)
        sys.exit(1)
    
    video_file = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    
    success, json_path = run_snakemake_for_file(video_file, model_name)
    if success:
        print(f"Output JSON: {json_path}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
