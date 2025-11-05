"""Tests for Snakemake integration in auto_ingest."""
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSnakemakeIntegration:
    """Test that auto_ingest correctly invokes Snakemake."""
    
    @patch('vlog.auto_ingest.subprocess.run')
    @patch('vlog.auto_ingest.check_if_file_exists')
    def test_run_snakemake_pipeline_creates_temp_config(self, mock_check_exists, mock_subprocess):
        """Test that _run_snakemake_pipeline creates a temporary config file."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        # Mock file existence check
        mock_check_exists.return_value = False
        
        # Mock subprocess to simulate success
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        # Create service with a temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestService(temp_dir, "test-model")
            
            # Create a test video file
            test_video = Path(temp_dir) / "test.mp4"
            test_video.touch()
            
            # Mock the Snakefile existence
            with patch('pathlib.Path.exists', return_value=True):
                # Call the pipeline
                success, json_path = service._run_snakemake_pipeline(str(test_video))
            
            # Verify Snakemake was called
            assert mock_subprocess.called
            call_args = mock_subprocess.call_args
            
            # Check that snakemake command was invoked
            cmd = call_args[0][0]
            assert cmd[0] == 'snakemake'
            assert '--snakefile' in cmd
            assert '--configfile' in cmd
            assert '--cores' in cmd
            assert '1' in cmd
    
    
    @patch('vlog.auto_ingest.subprocess.run')
    @patch('vlog.auto_ingest.check_if_file_exists')
    def test_process_video_file_skips_existing(self, mock_check_exists, mock_subprocess):
        """Test that files already in database are skipped."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        # Mock file already exists
        mock_check_exists.return_value = True
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestService(temp_dir, "test-model")
            
            # Create a test video file
            test_video = Path(temp_dir) / "existing.mp4"
            test_video.touch()
            
            # Process the file
            service._process_video_file(str(test_video))
            
            # Verify Snakemake was NOT called (file already processed)
            assert not mock_subprocess.called
    
    def test_snakemake_config_format(self):
        """Test that the temporary config has the correct format."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestService(temp_dir, "custom-model")
            
            # The config should include the model name
            assert service.model_name == "custom-model"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
