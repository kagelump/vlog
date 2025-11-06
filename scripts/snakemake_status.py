#!/usr/bin/env python3
"""
Command-line client for querying Snakemake workflow status.

This script queries the REST API exposed by the logger plugin and displays
the current workflow status in a human-readable format.
"""

import argparse
import requests
import json
import sys
from typing import Optional


def get_workflow_status(host: str = "127.0.0.1", port: int = 5556) -> Optional[dict]:
    """
    Query the workflow status API.
    
    Args:
        host: API server host
        port: API server port
    
    Returns:
        Status dictionary or None if request fails
    """
    try:
        response = requests.get(f"http://{host}:{port}/status", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to status API: {e}", file=sys.stderr)
        return None


def format_status(status: dict) -> str:
    """
    Format workflow status as human-readable text.
    
    Args:
        status: Status dictionary from API
    
    Returns:
        Formatted status string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("Snakemake Workflow Status")
    lines.append("=" * 60)
    lines.append(f"Total Jobs:     {status['total_jobs']}")
    lines.append(f"Completed:      {status['completed_jobs']}")
    lines.append(f"Failed:         {status['failed_jobs']}")
    lines.append(f"Running:        {status['running_jobs']}")
    lines.append(f"Pending:        {status['pending_jobs']}")
    lines.append("-" * 60)
    
    if status['rules']:
        lines.append("Per-Rule Breakdown:")
        lines.append("")
        for rule_name, rule_status in status['rules'].items():
            total = rule_status['total']
            completed = rule_status['completed']
            failed = rule_status['failed']
            running = rule_status['running']
            pending = rule_status['pending']
            
            # Calculate percentage
            if total > 0:
                pct = (completed / total) * 100
            else:
                pct = 0
            
            lines.append(f"  {rule_name}:")
            lines.append(f"    Total:     {total}")
            lines.append(f"    Completed: {completed}/{total} ({pct:.1f}%)")
            if failed > 0:
                lines.append(f"    Failed:    {failed}")
            if running > 0:
                lines.append(f"    Running:   {running}")
            if pending > 0:
                lines.append(f"    Pending:   {pending}")
            lines.append("")
    else:
        lines.append("No rules tracked yet.")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Query Snakemake workflow status from logger plugin API"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5556,
        help="API server port (default: 5556)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text"
    )
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Watch mode: refresh status every N seconds"
    )
    
    args = parser.parse_args()
    
    if args.watch:
        import time
        import os
        try:
            while True:
                # Clear screen
                os.system('clear' if os.name == 'posix' else 'cls')
                
                status = get_workflow_status(args.host, args.port)
                if status is None:
                    print("Waiting for workflow status API...", file=sys.stderr)
                else:
                    if args.json:
                        print(json.dumps(status, indent=2))
                    else:
                        print(format_status(status))
                
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped watching.", file=sys.stderr)
            sys.exit(0)
    else:
        status = get_workflow_status(args.host, args.port)
        if status is None:
            sys.exit(1)
        
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(format_status(status))


if __name__ == "__main__":
    main()
