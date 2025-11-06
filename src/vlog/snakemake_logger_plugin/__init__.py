"""Snakemake logger plugin with REST API for workflow status tracking."""

__version__ = "0.1.0"

from .logger import StatusLogHandler

__all__ = ["StatusLogHandler"]
