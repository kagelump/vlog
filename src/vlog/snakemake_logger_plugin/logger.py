"""
Snakemake logger plugin that tracks job completion status and exposes REST API.

This plugin captures job events from Snakemake workflow execution and maintains
a status tracker that can be queried via REST API to show progress at each stage.
"""

from dataclasses import dataclass, field
from logging import LogRecord
from typing import Optional, Dict, Set
from threading import Lock
from snakemake_interface_logger_plugins.base import LogHandlerBase
from snakemake_interface_logger_plugins.settings import (
    LogHandlerSettingsBase,
    OutputSettingsLoggerInterface,
)
from snakemake_interface_logger_plugins.common import LogEvent


@dataclass
class StatusLogHandlerSettings(LogHandlerSettingsBase):
    """Settings for the status logger plugin."""
    
    # Port for the REST API server
    port: int = 5556
    # Host for the REST API server
    host: str = "127.0.0.1"


class WorkflowStatus:
    """Thread-safe tracker for workflow job status."""
    
    def __init__(self):
        self._lock = Lock()
        # Track jobs by rule name and their status
        self._jobs: Dict[str, Dict[str, Set[str]]] = {}
        # job_id -> (rule_name, status)
        self._job_map: Dict[int, tuple[str, str]] = {}
        # Total counts
        self._total_jobs = 0
        self._completed_jobs = 0
        self._failed_jobs = 0
    
    def add_job(self, job_id: int, rule: str):
        """Register a new job."""
        with self._lock:
            if rule not in self._jobs:
                self._jobs[rule] = {
                    "pending": set(),
                    "running": set(),
                    "completed": set(),
                    "failed": set()
                }
            self._jobs[rule]["pending"].add(str(job_id))
            self._job_map[job_id] = (rule, "pending")
            self._total_jobs += 1
    
    def start_job(self, job_id: int):
        """Mark a job as started."""
        with self._lock:
            if job_id in self._job_map:
                rule, old_status = self._job_map[job_id]
                if rule in self._jobs and old_status in self._jobs[rule]:
                    self._jobs[rule][old_status].discard(str(job_id))
                    self._jobs[rule]["running"].add(str(job_id))
                    self._job_map[job_id] = (rule, "running")
    
    def complete_job(self, job_id: int):
        """Mark a job as completed."""
        with self._lock:
            if job_id in self._job_map:
                rule, old_status = self._job_map[job_id]
                if rule in self._jobs and old_status in self._jobs[rule]:
                    self._jobs[rule][old_status].discard(str(job_id))
                    self._jobs[rule]["completed"].add(str(job_id))
                    self._job_map[job_id] = (rule, "completed")
                    self._completed_jobs += 1
    
    def fail_job(self, job_id: int):
        """Mark a job as failed."""
        with self._lock:
            if job_id in self._job_map:
                rule, old_status = self._job_map[job_id]
                if rule in self._jobs and old_status in self._jobs[rule]:
                    self._jobs[rule][old_status].discard(str(job_id))
                    self._jobs[rule]["failed"].add(str(job_id))
                    self._job_map[job_id] = (rule, "failed")
                    self._failed_jobs += 1
    
    def get_status(self) -> dict:
        """Get current workflow status."""
        with self._lock:
            status = {
                "total_jobs": self._total_jobs,
                "completed_jobs": self._completed_jobs,
                "failed_jobs": self._failed_jobs,
                "running_jobs": sum(len(jobs["running"]) for jobs in self._jobs.values()),
                "pending_jobs": sum(len(jobs["pending"]) for jobs in self._jobs.values()),
                "rules": {}
            }
            
            for rule, jobs in self._jobs.items():
                total = len(jobs["pending"]) + len(jobs["running"]) + len(jobs["completed"]) + len(jobs["failed"])
                status["rules"][rule] = {
                    "total": total,
                    "pending": len(jobs["pending"]),
                    "running": len(jobs["running"]),
                    "completed": len(jobs["completed"]),
                    "failed": len(jobs["failed"])
                }
            
            return status
    
    def reset(self):
        """Reset all tracking."""
        with self._lock:
            self._jobs.clear()
            self._job_map.clear()
            self._total_jobs = 0
            self._completed_jobs = 0
            self._failed_jobs = 0


# Global status tracker instance
_workflow_status = WorkflowStatus()


def get_workflow_status() -> dict:
    """Get the current workflow status (accessible from REST API)."""
    return _workflow_status.get_status()


def reset_workflow_status():
    """Reset the workflow status tracker."""
    _workflow_status.reset()


class StatusLogHandler(LogHandlerBase):
    """
    Logger plugin that tracks job completion status.
    
    This handler captures job lifecycle events (info, started, finished, error)
    and maintains a running count of jobs at each stage. The status can be
    queried via REST API.
    """
    
    def __init__(
        self,
        common_settings: OutputSettingsLoggerInterface,
        settings: Optional[StatusLogHandlerSettings] = None,
    ):
        """Initialize the status log handler."""
        self._settings = settings or StatusLogHandlerSettings()
        super().__init__(common_settings, self._settings)
        self._api_server = None
    
    def __post_init__(self):
        """Post-initialization to start REST API server."""
        # Import here to avoid circular dependencies
        from .api_server import start_api_server
        
        # Start the REST API server in a background thread
        self._api_server = start_api_server(
            host=self._settings.host,
            port=self._settings.port
        )
    
    def emit(self, record: LogRecord) -> None:
        """
        Process log records and update workflow status.
        
        Captures job lifecycle events and updates the status tracker.
        """
        event = record.__dict__.get("event", None)
        
        if event == LogEvent.JOB_INFO:
            # New job registered
            job_id = record.__dict__.get("jobid")
            rule = record.__dict__.get("rule", "unknown")
            if job_id is not None:
                _workflow_status.add_job(job_id, rule)
        
        elif event == LogEvent.JOB_STARTED:
            # Job started execution
            job_id = record.__dict__.get("jobid")
            if job_id is not None:
                _workflow_status.start_job(job_id)
        
        elif event == LogEvent.JOB_FINISHED:
            # Job completed successfully
            job_id = record.__dict__.get("jobid")
            if job_id is not None:
                _workflow_status.complete_job(job_id)
        
        elif event == LogEvent.JOB_ERROR:
            # Job failed
            job_id = record.__dict__.get("jobid")
            if job_id is not None:
                _workflow_status.fail_job(job_id)
    
    @property
    def writes_to_stream(self) -> bool:
        """This plugin does not write to stdout/stderr."""
        return False
    
    @property
    def writes_to_file(self) -> bool:
        """This plugin does not write to a file."""
        return False
    
    @property
    def has_filter(self) -> bool:
        """This plugin does not attach a filter."""
        return False
    
    @property
    def has_formatter(self) -> bool:
        """This plugin does not attach a formatter."""
        return False
    
    @property
    def needs_rulegraph(self) -> bool:
        """This plugin does not need the DAG rulegraph."""
        return False
