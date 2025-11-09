#!/usr/bin/env python3
"""
Test what events Snakemake emits, especially for already-satisfied outputs.
"""

import tempfile
import os
import subprocess
from pathlib import Path

# Create a temporary directory with a simple Snakefile
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)
    
    # Create a simple Snakefile
    snakefile = tmpdir / "Snakefile"
    snakefile.write_text("""
rule all:
    input:
        "output1.txt",
        "output2.txt",
        "output3.txt"

rule make_file:
    output:
        "{name}.txt"
    shell:
        "echo 'Hello from {wildcards.name}' > {output}"
""")
    
    # Create config
    config = tmpdir / "config.yaml"
    config.write_text("# empty config\n")
    
    # First run - should create all files
    print("=" * 60)
    print("FIRST RUN - Creating all output files")
    print("=" * 60)
    result = subprocess.run(
        [
            "snakemake",
            "--snakefile", str(snakefile),
            "--cores", "1",
            "--logger-plugin", "vlog",
            "--logger-plugin-settings", "vlog", "debug=True"
        ],
        cwd=tmpdir,
        capture_output=True,
        text=True
    )
    print(result.stderr)
    print(result.stdout)
    
    # Second run - all outputs satisfied
    print("\n" + "=" * 60)
    print("SECOND RUN - All outputs already satisfied")
    print("=" * 60)
    result = subprocess.run(
        [
            "snakemake",
            "--snakefile", str(snakefile),
            "--cores", "1",
            "--logger-plugin", "vlog",
            "--logger-plugin-settings", "vlog", "debug=True"
        ],
        cwd=tmpdir,
        capture_output=True,
        text=True
    )
    print(result.stderr)
    print(result.stdout)
    
    # Third run - delete one file, one needs to be remade
    print("\n" + "=" * 60)
    print("THIRD RUN - One file deleted, needs to be remade")
    print("=" * 60)
    (tmpdir / "output2.txt").unlink()
    result = subprocess.run(
        [
            "snakemake",
            "--snakefile", str(snakefile),
            "--cores", "1",
            "--logger-plugin", "vlog",
            "--logger-plugin-settings", "vlog", "debug=True"
        ],
        cwd=tmpdir,
        capture_output=True,
        text=True
    )
    print(result.stderr)
    print(result.stdout)
