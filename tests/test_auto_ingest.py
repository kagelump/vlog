"""Tests for auto-ingest functionality."""
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestVideoFileHandler:
    """Test the VideoFileHandler class."""
    
    def test_is_video_file_detection(self):
        """Test that video file extensions are correctly defined."""
        # Import locally to check if module is available
        try:
            from vlog.auto_ingest import VIDEO_EXTENSIONS
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        # These should be recognized as video files
        assert '.mp4' in VIDEO_EXTENSIONS
        assert '.mov' in VIDEO_EXTENSIONS
        assert '.avi' in VIDEO_EXTENSIONS
        assert '.mkv' in VIDEO_EXTENSIONS
        
        # Case sensitivity check
        assert '.MP4' in VIDEO_EXTENSIONS


class TestAutoIngestService:
    """Test the AutoIngestService class (without ML dependencies)."""
    
    def test_service_can_be_imported_if_dependencies_available(self):
        """Test that AutoIngestService can be imported when dependencies are available."""
        try:
            from vlog.auto_ingest import AutoIngestService
            # If we get here, import succeeded
            assert AutoIngestService is not None
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
    
    @pytest.mark.skip(reason="Requires ML dependencies not available in test environment")
    def test_service_initialization(self):
        """Test that AutoIngestService can be initialized."""
        pass
    
    @pytest.mark.skip(reason="Requires ML dependencies not available in test environment")
    def test_service_status(self):
        """Test get_status returns correct information."""
        pass
    
    @pytest.mark.skip(reason="Requires ML dependencies not available in test environment")
    def test_service_start_requires_valid_directory(self):
        """Test that start fails with invalid directory."""
        pass
    
    @pytest.mark.skip(reason="Requires ML dependencies not available in test environment")
    def test_process_video_file_skips_existing(self):
        """Test that _process_video_file skips already-processed files."""
        pass


class TestBatchProcessing:
    """Test batch processing functionality."""
    
    def test_batch_queue_initialization(self):
        """Test that batch queue is properly initialized."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AutoIngestService(tmpdir, batch_size=10, batch_timeout=30.0)
            assert service.batch_size == 10
            assert service.batch_timeout == 30.0
            assert service._batch_queue == []
            assert service._processing_batch is False
    
    def test_batch_size_minimum_validation(self):
        """Test that batch size has a minimum value of 1."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with 0 - should be clamped to 1
            service = AutoIngestService(tmpdir, batch_size=0)
            assert service.batch_size == 1
            
            # Test with negative - should be clamped to 1
            service = AutoIngestService(tmpdir, batch_size=-5)
            assert service.batch_size == 1
    
    def test_batch_timeout_minimum_validation(self):
        """Test that batch timeout has a minimum value of 1.0."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with 0 - should be clamped to 1.0
            service = AutoIngestService(tmpdir, batch_timeout=0.0)
            assert service.batch_timeout == 1.0
            
            # Test with negative - should be clamped to 1.0
            service = AutoIngestService(tmpdir, batch_timeout=-10.0)
            assert service.batch_timeout == 1.0
    
    def test_get_status_includes_batch_info(self):
        """Test that get_status returns batch-related information."""
        try:
            from vlog.auto_ingest import AutoIngestService
        except ImportError:
            pytest.skip("auto_ingest module not available (missing dependencies)")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AutoIngestService(tmpdir, batch_size=5, batch_timeout=60.0)
            status = service.get_status()
            
            assert 'batch_size' in status
            assert status['batch_size'] == 5
            assert 'batch_timeout' in status
            assert status['batch_timeout'] == 60.0
            assert 'queued_files' in status
            assert status['queued_files'] == 0
            assert 'processing_batch' in status
            assert status['processing_batch'] is False


class TestWebAPIEndpoints:
    """Test the auto-ingest API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a Flask test client."""
        from vlog.web import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_auto_ingest_status_endpoint_exists(self, client):
        """Test that the auto-ingest status endpoint is accessible."""
        response = client.get('/api/auto-ingest/status')
        assert response.status_code in [200, 503]  # 503 if dependencies not available
    
    def test_auto_ingest_start_endpoint_exists(self, client):
        """Test that the auto-ingest start endpoint is accessible."""
        response = client.post('/api/auto-ingest/start', 
                              json={'watch_directory': '/tmp'})
        assert response.status_code in [200, 400, 503]
    
    def test_auto_ingest_stop_endpoint_exists(self, client):
        """Test that the auto-ingest stop endpoint is accessible."""
        response = client.post('/api/auto-ingest/stop')
        assert response.status_code in [200, 400, 503]
    
    def test_auto_ingest_start_with_batch_params(self, client):
        """Test that the auto-ingest start endpoint accepts batch parameters."""
        response = client.post('/api/auto-ingest/start', 
                              json={
                                  'watch_directory': '/tmp',
                                  'batch_size': 10,
                                  'batch_timeout': 120.0
                              })
        # Should get 200 (started) or 503 (dependencies unavailable)
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
    
    def test_auto_ingest_start_validates_batch_size(self, client):
        """Test that invalid batch_size is validated."""
        response = client.post('/api/auto-ingest/start', 
                              json={
                                  'watch_directory': '/tmp',
                                  'batch_size': 'invalid'
                              })
        # Should get 400 (validation error) or 503 (dependencies unavailable)
        assert response.status_code in [400, 503]
    
    def test_auto_ingest_start_validates_batch_timeout(self, client):
        """Test that invalid batch_timeout is validated."""
        response = client.post('/api/auto-ingest/start', 
                              json={
                                  'watch_directory': '/tmp',
                                  'batch_timeout': 'invalid'
                              })
        # Should get 400 (validation error) or 503 (dependencies unavailable)
        assert response.status_code in [400, 503]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
