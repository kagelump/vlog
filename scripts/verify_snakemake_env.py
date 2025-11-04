#!/usr/bin/env python3
"""
Verify that the Snakemake workflow environment is properly configured.

This script checks that all required dependencies and tools are available
before running the Snakemake video ingestion workflow.
"""

import subprocess
import sys
from pathlib import Path


def check_command(command: str, package_hint: str = None) -> bool:
    """Check if a command is available."""
    try:
        subprocess.run(
            [command, "--version"],
            capture_output=True,
            check=True
        )
        print(f"✅ {command} is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"❌ {command} is NOT installed")
        if package_hint:
            print(f"   Install with: {package_hint}")
        return False


def check_python_module(module: str, package_hint: str = None) -> bool:
    """Check if a Python module can be imported."""
    try:
        __import__(module)
        print(f"✅ Python module '{module}' is available")
        return True
    except ImportError:
        print(f"❌ Python module '{module}' is NOT available")
        if package_hint:
            print(f"   Install with: {package_hint}")
        return False


def check_file_exists(filepath: Path, description: str) -> bool:
    """Check if a file exists."""
    if filepath.exists():
        print(f"✅ {description} exists: {filepath}")
        return True
    else:
        print(f"❌ {description} NOT found: {filepath}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("Snakemake Workflow Environment Verification")
    print("=" * 60)
    print()
    
    all_ok = True
    
    # Check project structure
    print("Checking project structure...")
    project_root = Path(__file__).parent.parent
    
    all_ok &= check_file_exists(project_root / "Snakefile", "Snakefile")
    all_ok &= check_file_exists(project_root / "config.yaml", "config.yaml")
    all_ok &= check_file_exists(project_root / "scripts" / "discover_videos.py", "discover_videos.py")
    all_ok &= check_file_exists(project_root / "scripts" / "create_preview.py", "create_preview.py")
    all_ok &= check_file_exists(project_root / "scripts" / "describe_to_json.py", "describe_to_json.py")
    print()
    
    # Check system commands
    print("Checking system commands...")
    all_ok &= check_command("snakemake", "pip install snakemake")
    all_ok &= check_command("ffmpeg", "brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)")
    all_ok &= check_command("mlx_whisper", "pip install mlx-whisper")
    print()
    
    # Check Python modules
    print("Checking Python modules...")
    all_ok &= check_python_module("yaml", "pip install pyyaml")
    all_ok &= check_python_module("mlx_vlm", "pip install mlx-vlm")
    print()
    
    # Check vlog modules (optional, may fail if not in PYTHONPATH)
    print("Checking vlog modules (optional)...")
    sys.path.insert(0, str(project_root / "src"))
    all_ok &= check_python_module("vlog.describe_lib", "Ensure PYTHONPATH includes src/")
    all_ok &= check_python_module("vlog.video", "Ensure PYTHONPATH includes src/")
    all_ok &= check_python_module("vlog.srt_cleaner", "Ensure PYTHONPATH includes src/")
    print()
    
    # Summary
    print("=" * 60)
    if all_ok:
        print("✅ All checks passed! You're ready to run the workflow.")
        print()
        print("Next steps:")
        print("  1. Edit config.yaml to set your SD card path")
        print("  2. Run: snakemake --cores 1 --configfile config.yaml --dry-run")
        print("  3. Run: snakemake --cores 1 --configfile config.yaml")
        print()
        print("Or use the convenience script:")
        print("  ./scripts/run_snakemake.sh --dry-run")
        return 0
    else:
        print("❌ Some checks failed. Please install missing dependencies.")
        print()
        print("See docs/SNAKEMAKE_WORKFLOW.md for detailed setup instructions.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
