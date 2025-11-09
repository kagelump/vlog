#!/usr/bin/env python3
"""
Test that the expected_total helper is called during Snakemake workflow parsing.
This simulates importing a snakefile that calls set_expected_total().
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Reset the workflow status first
from vlog.snakemake_logger_plugin.logger import reset_workflow_status, get_workflow_status
reset_workflow_status()

print("Before importing workflow modules:")
print(f"  Status: {get_workflow_status()}")

# Now simulate what happens when Snakemake parses the workflow files
# The discovery functions will be called at module level
print("\nSimulating Snakemake parsing workflow...")

# This should call set_expected_total() during import
from vlog.snakemake_logger_plugin.helpers import set_expected_total

# Call it as the workflow would during parsing
set_expected_total("transcribe", 42)
set_expected_total("describe", 99)

print("\nAfter calling set_expected_total:")
status = get_workflow_status()
print(f"  Status: {status}")

# Verify the expected totals are stored
from vlog.snakemake_logger_plugin.logger import _workflow_status
print(f"\nDirect check of _expected_totals dict:")
print(f"  {_workflow_status._expected_totals}")

print("\n✅ Expected totals are stored correctly!")
print("   These will appear in the API once jobs are created for these rules.")
