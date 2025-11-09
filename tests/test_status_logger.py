#!/usr/bin/env python3
"""
Tests for the Snakemake status logger plugin.
"""

import sys
import logging
import time
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler,
    StatusLogHandlerSettings,
    WorkflowStatus,
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


class TestWorkflowStatus(unittest.TestCase):
    """Test the WorkflowStatus tracker."""
    
    def setUp(self):
        """Set up test case."""
        self.status = WorkflowStatus()
    
    def tearDown(self):
        """Clean up."""
        self.status.reset()
    
    def test_add_job(self):
        """Test adding a job."""
        self.status.add_job(1, "transcribe")
        status = self.status.get_status()
        
        self.assertEqual(status["total_jobs"], 1)
        self.assertEqual(status["rules"]["transcribe"]["total"], 1)
        self.assertEqual(status["rules"]["transcribe"]["pending"], 1)
    
    def test_start_job(self):
        """Test starting a job."""
        self.status.add_job(1, "transcribe")
        self.status.start_job(1)
        status = self.status.get_status()
        
        self.assertEqual(status["rules"]["transcribe"]["pending"], 0)
        self.assertEqual(status["rules"]["transcribe"]["running"], 1)
        self.assertEqual(status["running_jobs"], 1)
    
    def test_complete_job(self):
        """Test completing a job."""
        self.status.add_job(1, "transcribe")
        self.status.start_job(1)
        self.status.complete_job(1)
        status = self.status.get_status()
        
        self.assertEqual(status["rules"]["transcribe"]["running"], 0)
        self.assertEqual(status["rules"]["transcribe"]["completed"], 1)
        self.assertEqual(status["completed_jobs"], 1)
    
    def test_fail_job(self):
        """Test failing a job."""
        self.status.add_job(1, "transcribe")
        self.status.start_job(1)
        self.status.fail_job(1)
        status = self.status.get_status()
        
        self.assertEqual(status["rules"]["transcribe"]["running"], 0)
        self.assertEqual(status["rules"]["transcribe"]["failed"], 1)
        self.assertEqual(status["failed_jobs"], 1)
    
    def test_multiple_rules(self):
        """Test tracking multiple rules."""
        self.status.add_job(1, "transcribe")
        self.status.add_job(2, "describe")
        self.status.add_job(3, "transcribe")
        
        status = self.status.get_status()
        
        self.assertEqual(status["total_jobs"], 3)
        self.assertEqual(status["rules"]["transcribe"]["total"], 2)
        self.assertEqual(status["rules"]["describe"]["total"], 1)
    
    def test_reset(self):
        """Test resetting the status."""
        self.status.add_job(1, "transcribe")
        self.status.reset()
        status = self.status.get_status()
        
        self.assertEqual(status["total_jobs"], 0)
        self.assertEqual(len(status["rules"]), 0)
    
    def test_set_expected_total(self):
        """Test setting expected total for a rule."""
        self.status.set_expected_total("transcribe", 100)
        self.status.add_job(1, "transcribe")
        
        status = self.status.get_status()
        
        self.assertEqual(status["rules"]["transcribe"]["expected_total"], 100)
        self.assertEqual(status["rules"]["transcribe"]["total"], 1)
    
    def test_expected_total_multiple_rules(self):
        """Test expected totals for multiple rules."""
        self.status.set_expected_total("transcribe", 50)
        self.status.set_expected_total("describe", 75)
        
        self.status.add_job(1, "transcribe")
        self.status.add_job(2, "describe")
        
        status = self.status.get_status()
        
        self.assertEqual(status["rules"]["transcribe"]["expected_total"], 50)
        self.assertEqual(status["rules"]["describe"]["expected_total"], 75)
    
    def test_expected_total_without_jobs(self):
        """Test that expected_total appears even without jobs yet."""
        self.status.set_expected_total("transcribe", 200)
        
        status = self.status.get_status()
        
        # Should appear in rules even if no jobs registered yet
        # This allows monitoring the expected workload before jobs are created
        self.assertIn("transcribe", status["rules"])
        self.assertEqual(status["rules"]["transcribe"]["expected_total"], 200)
        self.assertEqual(status["rules"]["transcribe"]["total"], 0)


class TestStatusLogHandler(unittest.TestCase):
    """Test the StatusLogHandler."""
    
    def setUp(self):
        """Set up test case."""
        # Reset global status before each test
        reset_workflow_status()
        # Use different port for tests to avoid conflicts
        self.settings = StatusLogHandlerSettings(port=5557)
        self.common_settings = MockOutputSettings()

        # Note: We won't actually start the API server in tests to avoid port conflicts
        # So we'll test the handler without __post_init__
    
    def test_handler_instantiation(self):
        """Test that handler can be instantiated."""
        # Temporarily disable API server startup
        import vlog.snakemake_logger_plugin.logger as logger_module
        original_post_init = StatusLogHandler.__post_init__
        StatusLogHandler.__post_init__ = lambda self: None
        
        try:
            handler = StatusLogHandler(
                common_settings=self.common_settings,
                settings=self.settings
            )
            
            self.assertIsInstance(handler, StatusLogHandler)
            self.assertFalse(handler.writes_to_stream)
            self.assertFalse(handler.writes_to_file)
            self.assertFalse(handler.has_filter)
            self.assertFalse(handler.has_formatter)
            self.assertFalse(handler.needs_rulegraph)
        finally:
            StatusLogHandler.__post_init__ = original_post_init
    
    def test_emit_job_info(self):
        """Test handling JOB_INFO event."""
        # Disable API server
        StatusLogHandler.__post_init__ = lambda self: None
        
        handler = StatusLogHandler(
            common_settings=self.common_settings,
            settings=self.settings
        )
        
        # Create a log record with JOB_INFO event
        record = logging.LogRecord(
            name="snakemake",
            level=logging.INFO,
            pathname="workflow.py",
            lineno=1,
            msg="Job info",
            args=(),
            exc_info=None
        )
        record.event = LogEvent.JOB_INFO
        record.jobid = 1
        record.rule = "transcribe"
        
        handler.emit(record)
        
        status = get_workflow_status()
        self.assertEqual(status["total_jobs"], 1)
        self.assertEqual(status["rules"]["transcribe"]["pending"], 1)
    
    def test_emit_job_lifecycle(self):
        """Test full job lifecycle events."""
        # Disable API server
        StatusLogHandler.__post_init__ = lambda self: None
        
        handler = StatusLogHandler(
            common_settings=self.common_settings,
            settings=self.settings
        )
        
        # Job info
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job info", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_INFO
        record.jobid = 1
        record.rule = "transcribe"
        handler.emit(record)
        
        # Job started
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job started", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_STARTED
        record.jobid = 1
        handler.emit(record)
        
        status = get_workflow_status()
        self.assertEqual(status["rules"]["transcribe"]["running"], 1)
        
        # Job finished
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job finished", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_FINISHED
        record.jobid = 1
        handler.emit(record)
        
        status = get_workflow_status()
        self.assertEqual(status["rules"]["transcribe"]["completed"], 1)
        self.assertEqual(status["completed_jobs"], 1)
    
    def test_emit_set_expected_total(self):
        """Test handling SET_EXPECTED_TOTAL custom event."""
        # Disable API server
        StatusLogHandler.__post_init__ = lambda self: None
        
        handler = StatusLogHandler(
            common_settings=self.common_settings,
            settings=self.settings
        )
        
        # Emit SET_EXPECTED_TOTAL event
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Setting expected total", args=(), exc_info=None
        )
        record.event = "SET_EXPECTED_TOTAL"
        record.rule = "transcribe"
        record.expected_total = 100
        handler.emit(record)
        
        # Add a job to see the expected_total in the status
        record = logging.LogRecord(
            name="snakemake", level=logging.INFO,
            pathname="workflow.py", lineno=1,
            msg="Job info", args=(), exc_info=None
        )
        record.event = LogEvent.JOB_INFO
        record.jobid = 1
        record.rule = "transcribe"
        handler.emit(record)
        
        status = get_workflow_status()
        self.assertEqual(status["rules"]["transcribe"]["expected_total"], 100)
        self.assertEqual(status["rules"]["transcribe"]["total"], 1)


class TestAPIServer(unittest.TestCase):
    """Test the API server (basic smoke tests only)."""
    
    def test_api_endpoints_exist(self):
        """Test that API endpoints are defined."""
        from vlog.snakemake_logger_plugin.api_server import app
        
        routes = [route.path for route in app.routes]
        self.assertIn("/status", routes)
        self.assertIn("/health", routes)
        self.assertIn("/reset", routes)


if __name__ == "__main__":
    unittest.main()
