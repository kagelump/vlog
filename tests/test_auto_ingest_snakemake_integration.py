"""Tests for Snakemake-based auto-ingest service."""
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAutoIngestSnakemakeService:
    """Test the AutoIngestSnakemakeService class."""
    
    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(
                temp_dir,
                model_name="test-model",
                cores=4,
                resources_mem_gb=8
            )
            
            assert service.watch_directory == os.path.abspath(temp_dir)
            assert service.model_name == "test-model"
            assert service.cores == 4
            assert service.resources_mem_gb == 8
            assert service.is_running is False
    
    def test_service_with_preview_folder(self):
        """Test service initialization with separate preview folder."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            preview_dir = os.path.join(temp_dir, "preview")
            os.makedirs(preview_dir)
            
            service = AutoIngestSnakemakeService(
                temp_dir,
                preview_folder=preview_dir
            )
            
            assert service.watch_directory == os.path.abspath(temp_dir)
            assert service.preview_folder == os.path.abspath(preview_dir)
    
    def test_get_status(self):
        """Test the get_status method."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(temp_dir)
            status = service.get_status()
            
            assert 'is_running' in status
            assert 'watch_directory' in status
            assert 'preview_folder' in status
            assert 'model_name' in status
            assert 'cores' in status
            assert 'resources_mem_gb' in status
            assert 'is_processing' in status
            
            assert status['is_running'] is False
    
    def test_create_snakemake_config(self):
        """Test that Snakemake config is created correctly."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(
                temp_dir,
                model_name="custom-model"
            )
            
            config = service._create_snakemake_config()
            
            assert config['sd_card_path'] == service.watch_directory
            assert config['main_folder'] == service.watch_directory
            assert config['preview_folder'] == service.preview_folder
            assert config['describe']['model'] == "custom-model"
            assert 'transcribe' in config
            assert 'preview_settings' in config
    
    @patch('vlog.auto_ingest_snakemake.Observer')
    def test_start_service(self, mock_observer):
        """Test starting the service."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock observer instance
            mock_observer_instance = MagicMock()
            mock_observer.return_value = mock_observer_instance
            
            service = AutoIngestSnakemakeService(temp_dir)
            success = service.start()
            
            assert success is True
            assert service.is_running is True
            mock_observer_instance.schedule.assert_called_once()
            mock_observer_instance.start.assert_called_once()
    
    @patch('vlog.auto_ingest_snakemake.Observer')
    def test_stop_service(self, mock_observer):
        """Test stopping the service."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_observer_instance = MagicMock()
            mock_observer.return_value = mock_observer_instance
            
            service = AutoIngestSnakemakeService(temp_dir)
            service.start()
            
            success = service.stop()
            
            assert success is True
            assert service.is_running is False
            mock_observer_instance.stop.assert_called_once()
    
    @patch('vlog.auto_ingest_snakemake.requests.get')
    def test_get_progress_success(self, mock_get):
        """Test getting progress from logger plugin."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'total_jobs': 10,
            'completed_jobs': 5,
            'rules': {'transcribe': {'total': 5, 'completed': 2}}
        }
        mock_get.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(temp_dir, logger_port=5556)
            progress = service.get_progress()
            
            assert 'total_jobs' in progress
            assert progress['total_jobs'] == 10
            assert 'rules' in progress
    
    @patch('vlog.auto_ingest_snakemake.requests.get')
    def test_get_progress_failure(self, mock_get):
        """Test getting progress when logger API is unavailable."""
        try:
            from vlog.auto_ingest_snakemake import AutoIngestSnakemakeService
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AutoIngestSnakemakeService(temp_dir)
            progress = service.get_progress()
            
            assert 'error' in progress
            assert progress['available'] is False


class TestVideoFileHandler:
    """Test the VideoFileHandler class."""
    
    def test_is_video_file(self):
        """Test video file detection."""
        try:
            from vlog.auto_ingest_snakemake import VideoFileHandler
        except ImportError:
            pytest.skip("auto_ingest_snakemake module not available")
        
        handler = VideoFileHandler(callback=lambda x: None)
        
        assert handler._is_video_file("/path/to/video.mp4") is True
        assert handler._is_video_file("/path/to/video.MP4") is True
        assert handler._is_video_file("/path/to/video.mov") is True
        assert handler._is_video_file("/path/to/video.avi") is True
        assert handler._is_video_file("/path/to/video.mkv") is True
        assert handler._is_video_file("/path/to/file.txt") is False
        assert handler._is_video_file("/path/to/file.jpg") is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
