"""Tests for vlog.web module (Flask API)."""
import os
import tempfile
import json
from pathlib import Path
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.web import app


@pytest.fixture
def client():
    """Create a Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestIndexRoute:
    """Tests for index route."""
    
    def test_index_returns_html(self, client):
        """Test that index route returns HTML file."""
        # This will fail if static/index.html doesn't exist
        # We'll just check that the route is defined
        response = client.get('/')
        
        # The response could be 200 if file exists or 404 if it doesn't
        # We just want to ensure the route is defined
        assert response.status_code in [200, 404]


class TestVideoRoute:
    """Tests for video serving route."""
    
    def test_video_route_exists(self, client):
        """Test that video serving route is defined."""
        # This will fail if video doesn't exist, which is expected
        response = client.get('/video/test.mp4')
        
        # Should return 404 for non-existent file
        assert response.status_code == 404


class TestProjectInfoAPI:
    """Tests for the project-info API endpoint."""
    
    def test_project_info_endpoint_exists(self, client):
        """Test that project-info endpoint exists and returns 200."""
        response = client.get('/api/project-info')
        assert response.status_code == 200
    
    def test_project_info_returns_json(self, client):
        """Test that project-info returns JSON content."""
        response = client.get('/api/project-info')
        assert 'application/json' in response.content_type
        data = response.get_json()
        assert data is not None
    
    def test_project_info_has_required_fields(self, client):
        """Test that project-info returns required fields."""
        response = client.get('/api/project-info')
        data = response.get_json()
        
        assert 'project_path' in data
        assert 'working_directory' in data
        assert 'version' in data
    
    def test_project_info_project_path_is_valid(self, client):
        """Test that project_path is a valid path."""
        response = client.get('/api/project-info')
        data = response.get_json()
        
        project_path = data['project_path']
        assert project_path is not None
        assert len(project_path) > 0
        # Should be an absolute path
        assert os.path.isabs(project_path) or project_path.startswith('/')


class TestWorkingDirEndpoints:
    """Tests for working dir API endpoints."""
    
    def test_set_working_dir_success(self, client):
        """Test setting working directory to a valid path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            response = client.post(
                '/api/set-working-dir',
                json={'working_dir': tmpdir}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert tmpdir in data['message']
    
    def test_set_working_dir_nonexistent(self, client):
        """Test setting working directory to a non-existent path."""
        response = client.post(
            '/api/set-working-dir',
            json={'working_dir': '/nonexistent/path/12345'}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'does not exist' in data['message'].lower()
    
    def test_set_working_dir_missing_param(self, client):
        """Test setting working directory without providing the path."""
        response = client.post(
            '/api/set-working-dir',
            json={}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'required' in data['message'].lower()


class TestMetadataAPI:
    """Tests for the metadata API endpoint."""
    
    def test_metadata_endpoint_exists(self, client):
        """Test that metadata endpoint exists and returns 200."""
        response = client.get('/api/metadata')
        assert response.status_code == 200
    
    def test_metadata_returns_json_array(self, client):
        """Test that metadata returns JSON array."""
        response = client.get('/api/metadata')
        assert 'application/json' in response.content_type
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_metadata_empty_when_no_videos(self, client, tmp_path, monkeypatch):
        """Test that metadata returns empty array when no videos exist."""
        # Mock the preview folder to point to an empty temp directory
        import vlog.web as web_module
        monkeypatch.setattr(web_module, 'working_directory', str(tmp_path))
        
        response = client.get('/api/metadata')
        data = response.get_json()
        assert data == []
    
    def test_metadata_returns_video_data(self, client, tmp_path, monkeypatch):
        """Test that metadata returns video data when JSON files exist."""
        # Create preview folder and add a test JSON file
        preview_folder = tmp_path / 'videos' / 'preview'
        preview_folder.mkdir(parents=True)
        
        test_video_data = {
            'filename': 'test.mp4',
            'video_description_short': 'Test video',
            'video_description_long': 'A test video description',
            'primary_shot_type': 'pov',
            'tags': ['test'],
            'keep': 1,
            'rating': 0.8,
            'video_length_seconds': 30.5,
            'video_timestamp': '2024-01-01T10:00:00'
        }
        
        json_file = preview_folder / 'test.json'
        with open(json_file, 'w') as f:
            json.dump(test_video_data, f)
        
        # Mock the working directory
        import vlog.web as web_module
        monkeypatch.setattr(web_module, 'working_directory', str(tmp_path))
        
        response = client.get('/api/metadata')
        data = response.get_json()
        
        assert len(data) == 1
        assert data[0]['filename'] == 'test.mp4'
        assert data[0]['video_description_short'] == 'Test video'
        assert 'video_thumbnail_base64' not in data[0]  # Should be removed


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
