#!/usr/bin/env python3
"""
Run Snakemake with the status logger plugin enabled.

This script demonstrates how to integrate the custom logger plugin
with Snakemake workflow execution.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.snakemake_logger_plugin.logger import StatusLogHandler, StatusLogHandlerSettings
from vlog.snakemake_logger_plugin.api_server import start_api_server


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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Snakemake with status logger plugin"
    )
    parser.add_argument(
        "--snakefile",
        default="src/ingest_pipeline/Snakefile",
        help="Snakefile to run (default: src/ingest_pipeline/Snakefile)"
    )
    parser.add_argument(
        "--configfile",
        default="config.yaml",
        help="Configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=1,
        help="Number of cores to use (default: 1)"
    )
    parser.add_argument(
        "--logger-port",
        type=int,
        default=5556,
        help="Port for status API server (default: 5556)"
    )
    parser.add_argument(
        "--logger-host",
        default="127.0.0.1",
        help="Host for status API server (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Perform a dry run"
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Target rules to execute (default: all)"
    )
    
    args = parser.parse_args()
    
    # Verify files exist
    if not Path(args.snakefile).exists():
        print(f"Error: Snakefile not found: {args.snakefile}", file=sys.stderr)
        sys.exit(1)
    
    if not Path(args.configfile).exists():
        print(f"Error: Config file not found: {args.configfile}", file=sys.stderr)
        sys.exit(1)
    
    # Create logger handler settings
    logger_settings = StatusLogHandlerSettings(
        port=args.logger_port,
        host=args.logger_host
    )
    
    # Create mock common settings
    common_settings = MockOutputSettings()
    common_settings.dryrun = args.dryrun
    
    # Create and configure the status logger handler
    status_handler = StatusLogHandler(
        common_settings=common_settings,
        settings=logger_settings
    )
    
    print("=" * 70)
    print("Snakemake with Status Logger Plugin")
    print("=" * 70)
    print(f"Snakefile:   {args.snakefile}")
    print(f"Config:      {args.configfile}")
    print(f"Cores:       {args.cores}")
    print(f"Dry run:     {args.dryrun}")
    print(f"Status API:  http://{args.logger_host}:{args.logger_port}/status")
    print("-" * 70)
    print("To query status in another terminal:")
    print(f"  python3 scripts/snakemake_status.py --port {args.logger_port}")
    print(f"  python3 scripts/snakemake_status.py --port {args.logger_port} --watch 2")
    print("=" * 70)
    print()
    
    # Add our custom handler to snakemake's logger
    snakemake_logger = logging.getLogger("snakemake")
    snakemake_logger.addHandler(status_handler)
    
    # Import snakemake here after setting up logging
    from snakemake import snakemake
    
    # Run snakemake
    success = snakemake(
        snakefile=args.snakefile,
        configfiles=[args.configfile],
        cores=args.cores,
        printshellcmds=True,
        dryrun=args.dryrun,
        targets=args.targets if args.targets else None,
        quiet=[]
    )
    
    print()
    print("=" * 70)
    if success:
        print("Workflow completed successfully!")
    else:
        print("Workflow failed!")
    print("=" * 70)
    
    # Keep the API server running for a bit so status can be queried
    if not args.dryrun:
        print()
        print("Status API will remain available for 30 seconds...")
        print(f"Query at: http://{args.logger_host}:{args.logger_port}/status")
        import time
        time.sleep(30)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
