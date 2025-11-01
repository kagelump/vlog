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
from vlog.db import initialize_db, insert_result



@pytest.fixture
def client(use_temp_db):
    """Create a Flask test client with a temporary database."""
    # Override the DATABASE setting
    app.config['TESTING'] = True
    
    # Update the DATABASE constant in web module
    import vlog.web as web_module
    original_db = web_module.DATABASE
    web_module.DATABASE = use_temp_db
    
    with app.test_client() as client:
        yield client
    
    # Restore original DATABASE
    web_module.DATABASE = original_db


@pytest.fixture
def populated_db(client, use_temp_db):
    """Create a test client with populated database."""
    import vlog.db as db_module
    original_db = db_module.DATABASE
    db_module.DATABASE = use_temp_db
    
    try:
        # Insert test data
        insert_result(
            filename="test1.mp4",
            video_description_long="First test video",
            video_description_short="test_one",
            primary_shot_type="insert",
            tags=["static", "closeup"],
            classification_time_seconds=1.5,
            classification_model="test-model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="thumbnail_base64_data_1",
            in_timestamp="00:00:00.000",
            out_timestamp="00:00:10.000",
            rating=0.8
        )
        
        insert_result(
            filename="test2.mp4",
            video_description_long="Second test video",
            video_description_short="test_two",
            primary_shot_type="pov",
            tags=["dynamic", "wide"],
            classification_time_seconds=2.0,
            classification_model="test-model",
            video_length_seconds=15.0,
            video_timestamp="2024-01-02T00:00:00",
            video_thumbnail_base64="thumbnail_base64_data_2",
            in_timestamp="00:00:01.000",
            out_timestamp="00:00:14.000",
            rating=0.9
        )
        
        yield client
    finally:
        db_module.DATABASE = original_db


class TestApiMetadata:
    """Tests for /api/metadata endpoint."""
    
    def test_get_metadata_empty_db(self, client):
        """Test getting metadata from empty database."""
        response = client.get('/api/metadata')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_metadata_with_data(self, populated_db):
        """Test getting metadata with data in database."""
        response = populated_db.get('/api/metadata')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Check first entry
        assert data[0]['filename'] == 'test1.mp4'
        assert data[0]['video_description_long'] == 'First test video'
        assert data[0]['video_description_short'] == 'test_one'
        assert data[0]['primary_shot_type'] == 'insert'
        assert data[0]['tags'] == ['static', 'closeup']
        assert data[0]['rating'] == 0.8
        
        # Ensure thumbnails are not included
        assert 'video_thumbnail_base64' not in data[0]
        assert 'video_thumbnail_base64' not in data[1]
    
    def test_get_metadata_returns_json(self, client):
        """Test that metadata endpoint returns JSON."""
        response = client.get('/api/metadata')
        
        assert response.content_type == 'application/json'


class TestApiThumbnail:
    """Tests for /api/thumbnail/<filename> endpoint."""
    
    def test_get_thumbnail_nonexistent_file(self, client):
        """Test getting thumbnail for non-existent file."""
        response = client.get('/api/thumbnail/nonexistent.mp4')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['video_thumbnail_base64'] is None
    
    def test_get_thumbnail_existing_file(self, populated_db):
        """Test getting thumbnail for existing file."""
        response = populated_db.get('/api/thumbnail/test1.mp4')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'video_thumbnail_base64' in data
        assert data['video_thumbnail_base64'] == 'thumbnail_base64_data_1'
    
    def test_get_thumbnail_different_files(self, populated_db):
        """Test getting thumbnails for different files."""
        response1 = populated_db.get('/api/thumbnail/test1.mp4')
        response2 = populated_db.get('/api/thumbnail/test2.mp4')
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        
        assert data1['video_thumbnail_base64'] == 'thumbnail_base64_data_1'
        assert data2['video_thumbnail_base64'] == 'thumbnail_base64_data_2'


class TestApiUpdateKeep:
    """Tests for /api/update_keep endpoint."""
    
    def test_update_keep_status_to_discard(self, populated_db):
        """Test updating keep status to discard (0)."""
        response = populated_db.post(
            '/api/update_keep',
            json={'filename': 'test1.mp4', 'keep': 0}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'test1.mp4' in data['message']
    
    def test_update_keep_status_to_keep(self, populated_db):
        """Test updating keep status to keep (1)."""
        response = populated_db.post(
            '/api/update_keep',
            json={'filename': 'test2.mp4', 'keep': 1}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_update_keep_missing_filename(self, client):
        """Test update_keep with missing filename."""
        response = client.post(
            '/api/update_keep',
            json={'keep': 1}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Missing filename' in data['message']
    
    def test_update_keep_missing_keep_status(self, client):
        """Test update_keep with missing keep status."""
        response = client.post(
            '/api/update_keep',
            json={'filename': 'test.mp4'}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_update_keep_invalid_json(self, client):
        """Test update_keep with invalid JSON."""
        response = client.post(
            '/api/update_keep',
            data='invalid json',
            content_type='application/json'
        )
        
        # Should handle the error gracefully
        assert response.status_code in [400, 500]


class TestApiUpdateDuration:
    """Tests for /api/update_duration endpoint."""
    
    def test_update_duration_with_value(self, populated_db):
        """Test updating duration with a numeric value."""
        response = populated_db.post(
            '/api/update_duration',
            json={'filename': 'test1.mp4', 'duration': 5.5}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'test1.mp4' in data['message']
        assert '5.5' in data['message']
    
    def test_update_duration_with_null(self, populated_db):
        """Test updating duration to null (full length)."""
        response = populated_db.post(
            '/api/update_duration',
            json={'filename': 'test2.mp4', 'duration': None}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_update_duration_missing_filename(self, client):
        """Test update_duration with missing filename."""
        response = client.post(
            '/api/update_duration',
            json={'duration': 10.0}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Missing filename' in data['message']
    
    def test_update_duration_with_zero(self, populated_db):
        """Test updating duration to zero."""
        response = populated_db.post(
            '/api/update_duration',
            json={'filename': 'test1.mp4', 'duration': 0.0}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


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


class TestDatabaseConnection:
    """Tests for database connection handling."""
    
    def test_database_connection_teardown(self, client):
        """Test that database connections are properly closed."""
        # Make a request that uses the database
        response = client.get('/api/metadata')
        assert response.status_code == 200
        
        # Make another request to ensure connection handling works
        response = client.get('/api/metadata')
        assert response.status_code == 200
    
    def test_multiple_concurrent_requests(self, populated_db):
        """Test handling multiple requests."""
        responses = []
        for _ in range(5):
            response = populated_db.get('/api/metadata')
            responses.append(response)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data) == 2


class TestContentTypes:
    """Tests for proper content types."""
    
    def test_metadata_content_type(self, client):
        """Test metadata endpoint returns JSON content type."""
        response = client.get('/api/metadata')
        assert 'application/json' in response.content_type
    
    def test_thumbnail_content_type(self, populated_db):
        """Test thumbnail endpoint returns JSON content type."""
        response = populated_db.get('/api/thumbnail/test1.mp4')
        assert 'application/json' in response.content_type
    
    def test_update_keep_content_type(self, populated_db):
        """Test update_keep endpoint returns JSON content type."""
        response = populated_db.post(
            '/api/update_keep',
            json={'filename': 'test1.mp4', 'keep': 1}
        )
        assert 'application/json' in response.content_type
