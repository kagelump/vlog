"""Tests for directory browser API endpoint."""
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


@pytest.fixture
def temp_dir_structure():
    """Create a temporary directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some subdirectories
        os.makedirs(os.path.join(tmpdir, 'videos'))
        os.makedirs(os.path.join(tmpdir, 'subfolder'))
        os.makedirs(os.path.join(tmpdir, 'videos', 'nested'))
        
        # Create some files (should not be shown in directory browser)
        with open(os.path.join(tmpdir, 'test.txt'), 'w') as f:
            f.write('test')
        
        yield tmpdir


class TestDirectoryBrowser:
    """Tests for /api/launcher/browse-directory endpoint."""
    
    def test_browse_home_directory(self, client):
        """Test browsing the home directory."""
        response = client.get('/api/launcher/browse-directory')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'current_path' in data
        assert 'items' in data
        assert isinstance(data['items'], list)
    
    def test_browse_specific_directory(self, client, temp_dir_structure):
        """Test browsing a specific directory."""
        response = client.get(f'/api/launcher/browse-directory?path={temp_dir_structure}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['current_path'] == temp_dir_structure
        
        # Should have the subdirectories we created
        item_names = [item['name'] for item in data['items']]
        assert 'videos' in item_names
        assert 'subfolder' in item_names
        
        # All items should be directories
        for item in data['items']:
            assert item['is_directory'] is True
    
    def test_browse_nonexistent_directory(self, client):
        """Test browsing a nonexistent directory."""
        response = client.get('/api/launcher/browse-directory?path=/nonexistent/path/12345')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'does not exist' in data['message'].lower()
    
    def test_browse_file_instead_of_directory(self, client, temp_dir_structure):
        """Test browsing a file path instead of directory."""
        file_path = os.path.join(temp_dir_structure, 'test.txt')
        response = client.get(f'/api/launcher/browse-directory?path={file_path}')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not a directory' in data['message'].lower()
    
    def test_parent_path_included(self, client, temp_dir_structure):
        """Test that parent path is included in response."""
        subfolder = os.path.join(temp_dir_structure, 'videos')
        response = client.get(f'/api/launcher/browse-directory?path={subfolder}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['parent_path'] == temp_dir_structure
    
    def test_hidden_files_excluded(self, client, temp_dir_structure):
        """Test that hidden files starting with . are excluded."""
        # Create a hidden directory
        hidden_dir = os.path.join(temp_dir_structure, '.hidden')
        os.makedirs(hidden_dir)
        
        response = client.get(f'/api/launcher/browse-directory?path={temp_dir_structure}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Hidden directory should not be in the list
        item_names = [item['name'] for item in data['items']]
        assert '.hidden' not in item_names
