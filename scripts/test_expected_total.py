#!/usr/bin/env python3
"""
Simple test to verify the expected_total feature works with the helper function.
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.snakemake_logger_plugin.helpers import set_expected_total
from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler,
    StatusLogHandlerSettings,
    get_workflow_status,
    reset_workflow_status,
)
from snakemake_interface_logger_plugins.common import LogEvent


class MockOutputSettings:
    """Mock implementation of OutputSettingsLoggerInterface."""
    
    def __init__(self):
        self.printshellcmds = True
        self.nocolor = False
        self.quiet = None
        self.debug_dag = False
        self.verbose = False
        self.show_failed_logs = True
        self.stdout = False
        self.dryrun = False


def test_expected_total():
    """Test the expected_total feature end-to-end."""
    print("Testing expected_total feature...")
    
    # Reset status
    reset_workflow_status()
    
    # Create handler without starting API server
    StatusLogHandler.__post_init__ = lambda self: None
    common_settings = MockOutputSettings()
    settings = StatusLogHandlerSettings(port=5558, debug=True)
    
    handler = StatusLogHandler(
        common_settings=common_settings,
        settings=settings
    )
    
    # Attach the handler to the snakemake logger
    logger = logging.getLogger("snakemake")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    print("\n1. Setting expected totals...")
    # Simulate stage discovery setting expected totals
    set_expected_total("transcribe", 300)
    set_expected_total("describe", 300)
    set_expected_total("clean_subtitles", 300)
    
    # Check status (should not show rules yet since no jobs)
    status = get_workflow_status()
    print(f"   Status after setting expected totals (no jobs yet): {status}")
    
    print("\n2. Adding some jobs...")
    # Simulate Snakemake creating jobs
    for i in range(5):
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job info", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_INFO
        record.jobid = i
        record.rule = "transcribe"
        handler.emit(record)
    
    # Check status
    status = get_workflow_status()
    print(f"   Total jobs: {status['total_jobs']}")
    print(f"   Transcribe rule: {status['rules']['transcribe']}")
    
    # Verify expected_total is present
    assert "expected_total" in status["rules"]["transcribe"]
    assert status["rules"]["transcribe"]["expected_total"] == 300
    assert status["rules"]["transcribe"]["total"] == 5
    
    print("\n3. Completing some jobs...")
    # Complete 3 jobs
    for i in range(3):
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job finished", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_FINISHED
        record.jobid = i
        handler.emit(record)
    
    status = get_workflow_status()
    print(f"   Transcribe rule: {status['rules']['transcribe']}")
    print(f"   Progress: {status['rules']['transcribe']['completed']}/{status['rules']['transcribe']['expected_total']}")
    
    # Calculate percentage
    completed = status['rules']['transcribe']['completed']
    expected = status['rules']['transcribe']['expected_total']
    percentage = (completed / expected) * 100
    print(f"   Percentage complete: {percentage:.1f}%")
    
    print("\n✅ All tests passed!")
    print(f"\nFinal status:\n{status}")


if __name__ == "__main__":
    test_expected_total()
