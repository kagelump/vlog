#!/usr/bin/env python3
"""
Test the already_satisfied calculation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler,
    StatusLogHandlerSettings,
    get_workflow_status,
    reset_workflow_status,
)
from vlog.snakemake_logger_plugin.helpers import set_expected_total
from snakemake_interface_logger_plugins.common import LogEvent
import logging


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


def test_already_satisfied():
    """Test the already_satisfied calculation."""
    print("Testing already_satisfied calculation...\n")
    
    # Reset status
    reset_workflow_status()
    
    # Create handler without starting API server
    StatusLogHandler.__post_init__ = lambda self: None
    common_settings = MockOutputSettings()
    settings = StatusLogHandlerSettings(port=5558, debug=False)
    
    handler = StatusLogHandler(
        common_settings=common_settings,
        settings=settings
    )
    
    # Attach the handler
    logger = logging.getLogger("snakemake")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Scenario: We discovered 300 input files
    print("1. Set expected_total = 300 for transcribe rule")
    set_expected_total("transcribe", 300)
    
    status = get_workflow_status()
    print(f"   Status: {status['rules']['transcribe']}\n")
    
    # Scenario: Snakemake only creates 50 jobs (because 250 outputs already exist)
    print("2. Snakemake creates only 50 jobs (250 already satisfied)")
    for i in range(50):
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job info", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_INFO
        record.jobid = i
        record.rule = "transcribe"
        handler.emit(record)
    
    status = get_workflow_status()
    transcribe = status['rules']['transcribe']
    print(f"   Status: {transcribe}")
    print(f"   → Total jobs created: {transcribe['total']}")
    print(f"   → Expected total: {transcribe['expected_total']}")
    print(f"   → Already satisfied: {transcribe.get('already_satisfied', 0)}\n")
    
    # Verify calculation
    assert transcribe['already_satisfied'] == 250, f"Expected 250, got {transcribe['already_satisfied']}"
    
    # Scenario: Complete 30 jobs
    print("3. Complete 30 jobs")
    for i in range(30):
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job finished", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_FINISHED
        record.jobid = i
        handler.emit(record)
    
    status = get_workflow_status()
    transcribe = status['rules']['transcribe']
    print(f"   Status: {transcribe}")
    print(f"   → Completed: {transcribe['completed']}/300 total files")
    print(f"   → Running: {transcribe['running']}")
    print(f"   → Already satisfied: {transcribe.get('already_satisfied', 0)}")
    print(f"   → Total progress: {transcribe['completed'] + transcribe.get('already_satisfied', 0)}/300")
    
    total_done = transcribe['completed'] + transcribe.get('already_satisfied', 0)
    percentage = (total_done / 300) * 100
    print(f"   → Percentage: {percentage:.1f}%\n")
    
    print("✅ All tests passed!")
    print("\nThis shows how to calculate overall progress:")
    print("  total_done = completed + already_satisfied")
    print("  percentage = (total_done / expected_total) * 100")


if __name__ == "__main__":
    test_already_satisfied()
