#!/usr/bin/env python3
"""
Integration test for the status logger plugin with a real Snakemake workflow.

This test creates a minimal Snakefile and runs it with the status logger to verify
the integration works end-to-end.
"""

import sys
import tempfile
import shutil
from pathlib import Path
import time
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def create_test_snakefile(temp_dir: Path) -> Path:
    """Create a minimal test Snakefile."""
    snakefile = temp_dir / "Snakefile"
    snakefile.write_text("""
# Minimal test workflow
rule all:
    input:
        "output/file1.txt",
        "output/file2.txt",
        "output/file3.txt"

rule create_file:
    output:
        "output/{name}.txt"
    shell:
        '''
        mkdir -p output
        echo "Test content for {wildcards.name}" > {output}
        sleep 1
        '''
""")
    return snakefile


def test_logger_integration():
    """Test the logger plugin with a real Snakemake workflow."""
    print("=" * 70)
    print("Integration Test: Status Logger Plugin with Snakemake")
    print("=" * 70)
    
    # Create temporary directory for test
    temp_dir = Path(tempfile.mkdtemp())
    print(f"\nTest directory: {temp_dir}")
    
    try:
        # Create test Snakefile
        snakefile = create_test_snakefile(temp_dir)
        print(f"Created test Snakefile: {snakefile}")
        
        # Import dependencies
        from vlog.snakemake_logger_plugin.logger import (
            StatusLogHandler,
            StatusLogHandlerSettings,
            get_workflow_status,
            reset_workflow_status,
        )
        from vlog.snakemake_logger_plugin.api_server import start_api_server
        import logging
        
        # Reset status tracker
        reset_workflow_status()
        
        # Start API server
        print("\nStarting API server on port 5559...")
        server_thread = start_api_server(host="127.0.0.1", port=5559)
        time.sleep(2)  # Give server time to start
        
        # Create mock output settings
        class MockOutputSettings:
            printshellcmds = True
            nocolor = False
            quiet = None
            debug_dag = False
            verbose = False
            show_failed_logs = True
            stdout = False
            dryrun = False
        
        # Create logger handler
        settings = StatusLogHandlerSettings(port=5559, host="127.0.0.1")
        # Disable __post_init__ since we already started the server
        StatusLogHandler.__post_init__ = lambda self: None
        
        handler = StatusLogHandler(
            common_settings=MockOutputSettings(),
            settings=settings
        )
        
        # Add handler to snakemake logger
        snakemake_logger = logging.getLogger("snakemake")
        snakemake_logger.addHandler(handler)
        
        print("Running Snakemake workflow...")
        
        # Import and run snakemake
        from snakemake import snakemake
        
        # Run workflow
        success = snakemake(
            snakefile=str(snakefile),
            workdir=str(temp_dir),
            cores=1,
            printshellcmds=False,
            quiet=["all"],
        )
        
        print(f"\nWorkflow completed: {'SUCCESS' if success else 'FAILED'}")
        
        # Query status via API
        print("\nQuerying status via API...")
        time.sleep(1)
        
        try:
            response = requests.get("http://127.0.0.1:5559/status", timeout=5)
            status = response.json()
            
            print("\nFinal Status from API:")
            print(f"  Total jobs: {status['total_jobs']}")
            print(f"  Completed: {status['completed_jobs']}")
            print(f"  Failed: {status['failed_jobs']}")
            print(f"  Rules tracked: {list(status['rules'].keys())}")
            
            for rule_name, rule_status in status['rules'].items():
                print(f"\n  {rule_name}:")
                print(f"    Total: {rule_status['total']}")
                print(f"    Completed: {rule_status['completed']}")
                print(f"    Failed: {rule_status['failed']}")
            
            # Verify results
            assert success, "Workflow should have succeeded"
            assert status['total_jobs'] > 0, "Should have tracked some jobs"
            assert status['completed_jobs'] > 0, "Should have completed some jobs"
            
            print("\n" + "=" * 70)
            print("Integration Test PASSED!")
            print("=" * 70)
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error querying API: {e}")
            return False
    
    finally:
        # Cleanup
        print(f"\nCleaning up test directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = test_logger_integration()
    sys.exit(0 if success else 1)
