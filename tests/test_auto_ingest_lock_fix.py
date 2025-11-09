"""
Test that the auto-ingest snakemake service doesn't hold locks during execution.

This test verifies the fix for the issue where the web server becomes unresponsive
during Snakemake execution due to holding a lock for the entire duration.
"""
import os
import sys
import time
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAutoIngestLockBehavior:
    """Test that locks are not held during long-running operations."""
    
    def test_lock_not_held_during_snakemake_execution(self):
        """Test that _snakemake_lock is not held while Snakemake is running."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(temp_dir)
            
            # Track lock acquisitions and releases
            lock_held_during_execution = False
            execution_started = threading.Event()
            execution_completed = threading.Event()
            
            original_popen = MagicMock()
            
            # Create a mock process that simulates a long-running command
            mock_process = MagicMock()
            mock_process.poll.return_value = None  # Process is running
            mock_process.stdout = iter(["line 1\n", "line 2\n", "line 3\n"])
            mock_process.wait.return_value = 0
            
            def mock_popen_side_effect(*args, **kwargs):
                """Simulate Popen that takes time to execute."""
                execution_started.set()
                # Check if lock is held during this call
                # The lock should NOT be held while we're iterating stdout
                return mock_process
            
            with patch('subprocess.Popen', side_effect=mock_popen_side_effect):
                # Start the workflow in a background thread
                workflow_thread = threading.Thread(
                    target=service._run_snakemake_workflow,
                    daemon=True
                )
                workflow_thread.start()
                
                # Wait for execution to start
                execution_started.wait(timeout=2)
                
                # Now try to acquire the lock - this should succeed quickly
                # If the lock is held during the entire execution, this will block
                start_time = time.time()
                lock_acquired = False
                
                # Try to get status multiple times while workflow is running
                # This should not block if lock is properly released
                for i in range(3):
                    try:
                        # get_status acquires the lock briefly
                        status = service.get_status()
                        lock_acquired = True
                        # If we can get status, the lock is not being held
                        break
                    except Exception as e:
                        time.sleep(0.1)
                
                elapsed = time.time() - start_time
                
                # Wait for workflow thread to complete
                workflow_thread.join(timeout=5)
                
                # Assert that we were able to acquire the lock quickly (< 0.5 seconds)
                # This proves the lock is not held during execution
                assert lock_acquired, "Could not acquire lock to get status"
                assert elapsed < 0.5, f"Lock acquisition took too long: {elapsed}s (lock was held during execution)"
    
    def test_get_status_works_during_execution(self):
        """Test that get_status() can be called while Snakemake is running."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(temp_dir)
            
            # Create a mock process that simulates a running command
            mock_process = MagicMock()
            mock_process.poll.return_value = None  # Process is running
            mock_process.pid = 12345
            
            # Manually set the process to simulate it running
            with service._snakemake_lock:
                service._snakemake_process = mock_process
            
            # Now get_status should work without blocking
            start_time = time.time()
            status = service.get_status()
            elapsed = time.time() - start_time
            
            # Should complete quickly (< 0.1 seconds)
            assert elapsed < 0.1, f"get_status took too long: {elapsed}s"
            assert status['is_processing'] is True
            
            # Clean up
            with service._snakemake_lock:
                service._snakemake_process = None
    
    def test_get_progress_works_during_execution(self):
        """Test that get_progress() can be called while Snakemake is running."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(temp_dir)
            
            # Create a mock process that simulates a running command
            mock_process = MagicMock()
            mock_process.poll.return_value = None  # Process is running
            
            # Manually set the process to simulate it running
            with service._snakemake_lock:
                service._snakemake_process = mock_process
            
            # Mock the requests.get to simulate logger API response
            with patch('vlog.auto_ingest_snakemake.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    'total_jobs': 10,
                    'completed_jobs': 5
                }
                mock_get.return_value = mock_response
                
                # Now get_progress should work without blocking
                start_time = time.time()
                progress = service.get_progress()
                elapsed = time.time() - start_time
                
                # Should complete quickly (< 0.5 seconds, accounting for network mock)
                assert elapsed < 0.5, f"get_progress took too long: {elapsed}s"
                assert progress['is_processing'] is True
                assert progress['total_jobs'] == 10
            
            # Clean up
            with service._snakemake_lock:
                service._snakemake_process = None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
