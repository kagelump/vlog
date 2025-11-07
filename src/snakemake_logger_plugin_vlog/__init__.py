"""Shim module so Snakemake's logger plugin registry can discover the
status logger implemented in this repository.

Snakemake's LoggerPluginRegistry looks for importable modules whose name
starts with the module prefix defined by
`snakemake_interface_logger_plugins.common.logger_plugin_module_prefix`
(which is "snakemake_logger_plugin_").

This module provides the two symbols the registry expects:
- LogHandler (subclass of LogHandlerBase)
- LogHandlerSettings (optional; subclass of LogHandlerSettingsBase)

It simply re-exports the implementation from `vlog.snakemake_logger_plugin.logger`.

Notes:
- For discovery to work, the directory containing this module must be on
  Python's sys.path (for this repo that means adding the `src/` directory
  to PYTHONPATH or installing the project into the environment).
- If you want the plugin available system-wide (when invoking the
  system `snakemake`), package and install this project so the module
  is on site-packages.
"""

from vlog.snakemake_logger_plugin.logger import (
    StatusLogHandler as LogHandler,
    StatusLogHandlerSettings as LogHandlerSettings,
)

__all__ = ["LogHandler", "LogHandlerSettings"]
