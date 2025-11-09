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
    port: int = field(default=5556, metadata={"help": "Port for the REST API server"})
    # Host for the REST API server
    host: str = field(default="127.0.0.1", metadata={"help": "Host for the REST API server"})
    # Enable debug logging of incoming LogRecord attributes (useful for
    # diagnosing missing lifecycle events). Defaults to False.
    debug: bool = field(
        default=False, metadata={"help": "Log incoming record attributes for debugging"}
    )


class WorkflowStatus:
    """Thread-safe tracker for workflow job status."""
    
    def __init__(self):
        self._lock = Lock()
        # Track jobs by rule name and their status
        self._jobs: Dict[str, Dict[str, Set[str]]] = {}
        # job_id -> (rule_name, status)
        self._job_map: Dict[int, tuple[str, str]] = {}
        # Expected total inputs per rule (e.g., number of stems discovered)
        self._expected_totals: Dict[str, int] = {}
        # Total counts
        self._total_jobs = 0
        self._completed_jobs = 0
        self._failed_jobs = 0

    def _normalize_job_id(self, job_id):
        """Normalize job id to an int when possible for consistent lookups."""
        try:
            return int(job_id)
        except Exception:
            return job_id
    
    def set_expected_total(self, rule: str, expected_total: int):
        """Set the expected total number of inputs for a rule."""
        with self._lock:
            self._expected_totals[rule] = expected_total
    
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
            nid = self._normalize_job_id(job_id)
            self._jobs[rule]["pending"].add(str(nid))
            self._job_map[nid] = (rule, "pending")
            self._total_jobs += 1
    
    def start_job(self, job_id: int):
        """Mark a job as started."""
        with self._lock:
            nid = self._normalize_job_id(job_id)
            if nid in self._job_map:
                rule, old_status = self._job_map[nid]
                if rule in self._jobs and old_status in self._jobs[rule]:
                    self._jobs[rule][old_status].discard(str(nid))
                    self._jobs[rule]["running"].add(str(nid))
                    self._job_map[nid] = (rule, "running")
            else:
                # Job not registered yet - this can happen if JOB_STARTED/SHELLCMD
                # fires before JOB_INFO. Add it as running with unknown rule.
                rule = "unknown"
                if rule not in self._jobs:
                    self._jobs[rule] = {
                        "pending": set(),
                        "running": set(),
                        "completed": set(),
                        "failed": set()
                    }
                self._jobs[rule]["running"].add(str(nid))
                self._job_map[nid] = (rule, "running")
                self._total_jobs += 1
    
    def complete_job(self, job_id: int):
        """Mark a job as completed."""
        with self._lock:
            nid = self._normalize_job_id(job_id)
            if nid in self._job_map:
                rule, old_status = self._job_map[nid]
                if rule in self._jobs and old_status in self._jobs[rule]:
                    self._jobs[rule][old_status].discard(str(nid))
                    self._jobs[rule]["completed"].add(str(nid))
                    self._job_map[nid] = (rule, "completed")
                    self._completed_jobs += 1
    
    def fail_job(self, job_id: int):
        """Mark a job as failed."""
        with self._lock:
            nid = self._normalize_job_id(job_id)
            if nid in self._job_map:
                rule, old_status = self._job_map[nid]
                if rule in self._jobs and old_status in self._jobs[rule]:
                    self._jobs[rule][old_status].discard(str(nid))
                    self._jobs[rule]["failed"].add(str(nid))
                    self._job_map[nid] = (rule, "failed")
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
                rule_status = {
                    "total": total,
                    "pending": len(jobs["pending"]),
                    "running": len(jobs["running"]),
                    "completed": len(jobs["completed"]),
                    "failed": len(jobs["failed"])
                }
                # Add expected_total if available for this rule
                if rule in self._expected_totals:
                    rule_status["expected_total"] = self._expected_totals[rule]
                status["rules"][rule] = rule_status
            
            return status
    
    def reset(self):
        """Reset all tracking."""
        with self._lock:
            self._jobs.clear()
            self._job_map.clear()
            self._expected_totals.clear()
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
        # Start the API server so endpoints are available when the handler
        # is attached. __post_init__ may not be invoked in this context,
        # so start the server here to ensure availability.
        self._api_server = None
        self._debug = bool(getattr(self._settings, "debug", False))
        try:
            # Import here to avoid circular dependencies and only when needed
            from .api_server import start_api_server
            # Start the API server by default (since we removed start_server field).
            # Tests and some programmatic uses can avoid starting the server by
            # passing settings=StatusLogHandlerSettings() to prevent port binding.
            self._api_server = start_api_server(
                host=self._settings.host, port=self._settings.port
            )
        except Exception as e:
            # Don't let API startup failures crash Snakemake; handler should
            # still operate (status tracking in-memory). The error can be
            # observed in logs if needed.
            import sys
            print(f"[status-logger] Failed to start API server: {e}", file=sys.stderr, flush=True)
            self._api_server = None
    
    # Note: API server startup is done in __init__ to ensure it runs when
    # Snakemake instantiates the handler. Leaving no-op here for clarity.
    
    def emit(self, record: LogRecord) -> None:
        """
        Process log records and update workflow status.
        
        Captures job lifecycle events and updates the status tracker.
        """
        event = record.__dict__.get("event", None)

        # If debug is enabled, emit a compact view of the incoming record so
        # users can diagnose what fields Snakemake provides during a real run.
        if getattr(self, "_debug", False):
            try:
                import sys

                info = {
                    "event": event,
                    "jobid": record.__dict__.get("jobid"),
                    "job_id": record.__dict__.get("job_id"),
                    "job_ids": record.__dict__.get("job_ids"),
                    "rule_name": record.__dict__.get("rule_name"),
                    "rule": record.__dict__.get("rule"),
                    "msg": record.__dict__.get("msg", "")[:100],  # First 100 chars of message
                }
                print("[status-logger-debug]", info, file=sys.stderr, flush=True)
            except Exception:
                pass
        
        # Handle custom event for setting expected totals
        # Stages can emit this by logging with extra={'event': 'SET_EXPECTED_TOTAL', 'rule': 'rule_name', 'expected_total': count}
        if event == "SET_EXPECTED_TOTAL":
            rule = record.__dict__.get("rule")
            expected_total = record.__dict__.get("expected_total")
            if rule and expected_total is not None:
                _workflow_status.set_expected_total(rule, int(expected_total))
                if self._debug:
                    import sys
                    print(f"[status-logger] SET_EXPECTED_TOTAL: rule={rule}, expected_total={expected_total}", file=sys.stderr, flush=True)
            return
        
        if event == LogEvent.JOB_INFO:
            # New job registered and selected for execution
            # In Snakemake, JOB_INFO means the job is about to run, so we mark it
            # as running immediately rather than pending.
            job_id = record.__dict__.get("jobid")
            # Snakemake's LogRecord may provide the rule name under different
            # keys depending on version/format. Prefer `rule_name` (used by
            # Snakemake), fall back to `rule`, `rule_msg`, or finally
            # "unknown" to avoid losing the information.
            rule = (
                record.__dict__.get("rule_name")
                or record.__dict__.get("rule")
                or record.__dict__.get("rule_msg")
                or "unknown"
            )
            if job_id is not None:
                # Add job and immediately mark as running since JOB_INFO means
                # the job has been selected for execution
                _workflow_status.add_job(job_id, rule)
                _workflow_status.start_job(job_id)
                if self._debug:
                    import sys
                    print(f"[status-logger] JOB_INFO: job_id={job_id}, rule={rule} -> marking as RUNNING", file=sys.stderr, flush=True)
        
        elif event == LogEvent.JOB_STARTED:
            # Job started execution
            # Snakemake may provide a list of started job ids under 'job_ids',
            # or a single id under 'jobid' / 'job_id'. Handle all cases.
            job_ids = record.__dict__.get("job_ids")
            if job_ids:
                for jid in job_ids:
                    _workflow_status.start_job(jid)
                    if self._debug:
                        import sys
                        print(f"[status-logger] JOB_STARTED: job_id={jid} (from job_ids list)", file=sys.stderr, flush=True)
            else:
                job_id = record.__dict__.get("jobid") or record.__dict__.get("job_id")
                if job_id is not None:
                    _workflow_status.start_job(job_id)
                    if self._debug:
                        import sys
                        print(f"[status-logger] JOB_STARTED: job_id={job_id}", file=sys.stderr, flush=True)
        
        elif event == LogEvent.SHELLCMD:
            # Shell command executing (job is actually running now)
            # This is a more reliable indicator that a job is running than JOB_STARTED
            job_id = record.__dict__.get("jobid") or record.__dict__.get("job_id")
            if job_id is not None:
                _workflow_status.start_job(job_id)
                if self._debug:
                    import sys
                    print(f"[status-logger] SHELLCMD: job_id={job_id}", file=sys.stderr, flush=True)
        
        elif event == LogEvent.JOB_FINISHED:
            # Job completed successfully
            # Snakemake may use 'job_id' or 'jobid' for finished jobs.
            job_id = record.__dict__.get("job_id") or record.__dict__.get("jobid")
            if job_id is not None:
                _workflow_status.complete_job(job_id)
                if self._debug:
                    import sys
                    print(f"[status-logger] JOB_FINISHED: job_id={job_id}", file=sys.stderr, flush=True)
        
        elif event == LogEvent.JOB_ERROR:
            # Job failed
            # Accept 'jobid' or 'job_id'
            job_id = record.__dict__.get("jobid") or record.__dict__.get("job_id")
            if job_id is not None:
                _workflow_status.fail_job(job_id)
                if self._debug:
                    import sys
                    print(f"[status-logger] JOB_ERROR: job_id={job_id}", file=sys.stderr, flush=True)
    
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
