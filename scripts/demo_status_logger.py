#!/usr/bin/env python3
"""
Demo script showing the status logger plugin in action.

This script simulates a Snakemake workflow by creating fake job events
and demonstrating how the status tracker works.
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler,
    StatusLogHandlerSettings,
    get_workflow_status,
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


def print_status():
    """Print the current workflow status."""
    status = get_workflow_status()
    print("\n" + "=" * 60)
    print(f"Total Jobs: {status['total_jobs']} | " +
          f"Completed: {status['completed_jobs']} | " +
          f"Running: {status['running_jobs']} | " +
          f"Failed: {status['failed_jobs']}")
    print("-" * 60)
    
    for rule_name, rule_status in status['rules'].items():
        total = rule_status['total']
        completed = rule_status['completed']
        pct = (completed / total * 100) if total > 0 else 0
        print(f"  {rule_name}: {completed}/{total} ({pct:.0f}%) " +
              f"[R:{rule_status['running']} P:{rule_status['pending']} F:{rule_status['failed']}]")
    
    print("=" * 60)


def simulate_job(handler, job_id, rule_name, should_fail=False):
    """Simulate a job lifecycle."""
    # Job info
    record = logging.LogRecord(
        name="snakemake", level=logging.INFO,
        pathname="workflow.py", lineno=1,
        msg="Job info", args=(), exc_info=None
    )
    record.event = LogEvent.JOB_INFO
    record.jobid = job_id
    record.rule = rule_name
    handler.emit(record)
    
    # Job started
    time.sleep(0.1)
    record = logging.LogRecord(
        name="snakemake", level=logging.INFO,
        pathname="workflow.py", lineno=1,
        msg="Job started", args=(), exc_info=None
    )
    record.event = LogEvent.JOB_STARTED
    record.jobid = job_id
    handler.emit(record)
    
    # Job finished or failed
    time.sleep(0.2)
    if should_fail:
        record = logging.LogRecord(
            name="snakemake", level=logging.ERROR,
            pathname="workflow.py", lineno=1,
            msg="Job failed", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_ERROR
        record.jobid = job_id
        handler.emit(record)
    else:
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job finished", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_FINISHED
        record.jobid = job_id
        handler.emit(record)


def main():
    """Run the demo."""
    print("=" * 60)
    print("Snakemake Status Logger Plugin Demo")
    print("=" * 60)
    print()
    print("This demo simulates a Snakemake workflow with multiple jobs")
    print("and shows how the status tracker works.")
    print()
    print("API Server: http://127.0.0.1:5558/status")
    print()
    print("In another terminal, you can query the status with:")
    print("  python3 scripts/snakemake_status.py --port 5558")
    print("  python3 scripts/snakemake_status.py --port 5558 --watch 1")
    print()
    print("-" * 60)
    
    # Create logger handler
    settings = StatusLogHandlerSettings(port=5558, host="127.0.0.1")
    common_settings = MockOutputSettings()
    handler = StatusLogHandler(
        common_settings=common_settings,
        settings=settings
    )
    
    print("\nStarting simulated workflow...")
    time.sleep(2)
    
    # Simulate workflow with multiple jobs
    jobs = [
        (1, "copy_main", False),
        (2, "copy_main", False),
        (3, "copy_main", False),
        (4, "transcribe", False),
        (5, "transcribe", False),
        (6, "transcribe", False),
        (7, "clean_subtitles", False),
        (8, "clean_subtitles", False),
        (9, "clean_subtitles", False),
        (10, "describe", False),
        (11, "describe", True),  # This one will fail
        (12, "describe", False),
    ]
    
    print("\nSimulating jobs...")
    for i, (job_id, rule, should_fail) in enumerate(jobs):
        print(f"\n[{i+1}/{len(jobs)}] Processing job {job_id} ({rule})...")
        simulate_job(handler, job_id, rule, should_fail)
        print_status()
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("Workflow simulation complete!")
    print("=" * 60)
    print()
    print("Final Status:")
    print_status()
    print()
    print("The API server will remain running for 60 seconds.")
    print("You can still query it at: http://127.0.0.1:5558/status")
    print()
    
    # Keep the API server running
    time.sleep(60)
    
    print("\nDemo complete. API server shutting down...")


if __name__ == "__main__":
    main()
