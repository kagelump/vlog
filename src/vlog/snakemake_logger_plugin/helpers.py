"""
Helper functions for Snakemake workflows to communicate with the status logger plugin.

This module provides utility functions that can be called from within Snakemake
workflow files (*.smk) to send information to the status logger plugin.
"""

import logging
import sys


def set_expected_total(rule_name: str, expected_total: int):
    """
    Report the expected total number of inputs for a rule to the status logger.
    
    This should be called after discovering input files (e.g., video stems) but
    before Snakemake starts executing jobs. The status logger plugin will capture
    this information and include it in the /status API response.
    
    Args:
        rule_name: Name of the rule (e.g., "transcribe", "describe")
        expected_total: Total number of inputs discovered for this rule
    
    Example:
        from vlog.snakemake_logger_plugin.helpers import set_expected_total
        
        # After discovering stems
        stems = discover_preview_videos()
        set_expected_total("transcribe", len(stems))
    """
    # First, try to set it directly on the global workflow status
    # This works even during parse time before logging is initialized
    try:
        from vlog.snakemake_logger_plugin.logger import _workflow_status
        _workflow_status.set_expected_total(rule_name, expected_total)
        # Debug output to stderr so we can verify it's being called
        print(f"[set_expected_total] {rule_name}: {expected_total}", file=sys.stderr, flush=True)
    except Exception as e:
        # Fallback: try logging (for when logger is initialized)
        print(f"[set_expected_total] Direct call failed ({e}), trying logger", file=sys.stderr, flush=True)
        logger = logging.getLogger("snakemake")
        logger.info(
            f"Setting expected total for {rule_name}: {expected_total}",
            extra={
                "event": "SET_EXPECTED_TOTAL",
                "rule": rule_name,
                "expected_total": expected_total
            }
        )

