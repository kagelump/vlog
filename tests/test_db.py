"""Tests for vlog.db module."""
import sqlite3
import json
from pathlib import Path
import pytest
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.db import (
    get_conn,
    initialize_db,
    get_all_metadata,
    get_thumbnail_by_filename,
    update_keep_status,
    update_cut_duration,
    check_if_file_exists,
    insert_result,
)


class TestGetConn:
    """Tests for get_conn function."""
    
    def test_get_conn_creates_connection(self, temp_db_path):
        """Test that get_conn returns a valid connection."""
        conn = get_conn(temp_db_path)
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row
        conn.close()


class TestInitializeDb:
    """Tests for initialize_db function."""
    
    def test_initialize_db_creates_table(self, temp_db_path):
        """Test that initialize_db creates the results table."""
        initialize_db(temp_db_path)
        
        conn = get_conn(temp_db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='results'
        """)
        result = cursor.fetchone()
        
        assert result is not None
        assert result['name'] == 'results'
        conn.close()
    
    def test_initialize_db_creates_correct_schema(self, temp_db_path):
        """Test that the table has all expected columns."""
        initialize_db(temp_db_path)
        
        conn = get_conn(temp_db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(results)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        expected_columns = {
            'filename', 'video_description_long', 'video_description_short',
            'primary_shot_type', 'tags', 'last_updated', 'classification_time_seconds',
            'classification_model', 'video_length_seconds', 'video_timestamp',
            'video_thumbnail_base64', 'clip_cut_duration', 'keep',
            'in_timestamp', 'out_timestamp', 'rating'
        }
        
        assert columns == expected_columns
        conn.close()


class TestGetAllMetadata:
    """Tests for get_all_metadata function."""
    
    def test_get_all_metadata_empty_db(self, use_temp_db):
        """Test getting metadata from empty database."""
        conn = get_conn(use_temp_db)
        metadata = get_all_metadata(conn)
        
        assert isinstance(metadata, list)
        assert len(metadata) == 0
        conn.close()
    
    def test_get_all_metadata_with_data(self, use_temp_db):
        """Test getting metadata with data in database."""
        # Insert test data
        insert_result(
            filename="test_video.mp4",
            video_description_long="A test video description",
            video_description_short="test_video",
            primary_shot_type="insert",
            tags=["static", "closeup"],
            classification_time_seconds=1.5,
            classification_model="test-model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="base64string",
            in_timestamp="00:00:00.000",
            out_timestamp="00:00:10.000",
            rating=0.8
        )
    
        conn = get_conn(use_temp_db)
        metadata = get_all_metadata(conn)
        
        assert len(metadata) == 1
        assert metadata[0]['filename'] == 'test_video.mp4'
        assert metadata[0]['video_description_long'] == 'A test video description'
        assert metadata[0]['tags'] == ["static", "closeup"]
        assert metadata[0]['rating'] == 0.8
        # Ensure thumbnail is not included in metadata
        assert 'video_thumbnail_base64' not in metadata[0]
        conn.close()
    
    def test_get_all_metadata_tags_parsing(self, use_temp_db):
        """Test that tags are properly parsed from JSON."""
        insert_result(
            filename="test.mp4",
            video_description_long="desc",
            video_description_short="short",
            primary_shot_type="pov",
            tags=["tag1", "tag2", "tag3"],
            classification_time_seconds=1.0,
            classification_model="model",
            video_length_seconds=5.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="thumb",
            in_timestamp="00:00:00",
            out_timestamp="00:00:05",
            rating=0.5
        )
        
        conn = get_conn(use_temp_db)
        metadata = get_all_metadata(conn)
        
        assert isinstance(metadata[0]['tags'], list)
        assert metadata[0]['tags'] == ["tag1", "tag2", "tag3"]
        conn.close()


class TestGetThumbnailByFilename:
    """Tests for get_thumbnail_by_filename function."""
    
    def test_get_thumbnail_nonexistent_file(self, use_temp_db):
        """Test getting thumbnail for non-existent file."""
        conn = get_conn(use_temp_db)
        result = get_thumbnail_by_filename(conn, "nonexistent.mp4")
        
        assert result is None
        conn.close()
    
    def test_get_thumbnail_existing_file(self, use_temp_db):
        """Test getting thumbnail for existing file."""
        expected_thumbnail = "base64_encoded_thumbnail_data"
        insert_result(
            filename="video.mp4",
            video_description_long="desc",
            video_description_short="short",
            primary_shot_type="insert",
            tags=[],
            classification_time_seconds=1.0,
            classification_model="model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64=expected_thumbnail,
            in_timestamp="00:00:00",
            out_timestamp="00:00:10",
            rating=0.7
        )
        
        conn = get_conn(use_temp_db)
        result = get_thumbnail_by_filename(conn, "video.mp4")
        
        assert result == expected_thumbnail
        conn.close()


class TestUpdateKeepStatus:
    """Tests for update_keep_status function."""
    
    def test_update_keep_status(self, use_temp_db):
        """Test updating keep status."""
        insert_result(
            filename="video.mp4",
            video_description_long="desc",
            video_description_short="short",
            primary_shot_type="insert",
            tags=[],
            classification_time_seconds=1.0,
            classification_model="model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="thumb",
            in_timestamp="00:00:00",
            out_timestamp="00:00:10",
            rating=0.5
        )
        
        conn = get_conn(use_temp_db)
        
        # Update to discard (0)
        update_keep_status(conn, "video.mp4", 0)
        
        # Verify update
        cursor = conn.cursor()
        cursor.execute("SELECT keep, last_updated FROM results WHERE filename = ?", ("video.mp4",))
        result = cursor.fetchone()
        
        assert result['keep'] == 0
        assert result['last_updated'] is not None
        conn.close()


class TestUpdateCutDuration:
    """Tests for update_cut_duration function."""
    
    def test_update_cut_duration(self, use_temp_db):
        """Test updating cut duration."""
        insert_result(
            filename="video.mp4",
            video_description_long="desc",
            video_description_short="short",
            primary_shot_type="insert",
            tags=[],
            classification_time_seconds=1.0,
            classification_model="model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="thumb",
            in_timestamp="00:00:00",
            out_timestamp="00:00:10",
            rating=0.5
        )
        
        conn = get_conn(use_temp_db)
        
        # Update duration
        update_cut_duration(conn, "video.mp4", 5.5)
        
        # Verify update
        cursor = conn.cursor()
        cursor.execute("SELECT clip_cut_duration FROM results WHERE filename = ?", ("video.mp4",))
        result = cursor.fetchone()
        
        assert result['clip_cut_duration'] == 5.5
        conn.close()


class TestCheckIfFileExists:
    """Tests for check_if_file_exists function."""
    
    def test_check_if_file_exists_false(self, use_temp_db):
        """Test checking for non-existent file."""
        result = check_if_file_exists("nonexistent.mp4")
        assert result is False
    
    def test_check_if_file_exists_true(self, use_temp_db):
        """Test checking for existing file."""
        insert_result(
            filename="exists.mp4",
            video_description_long="desc",
            video_description_short="short",
            primary_shot_type="insert",
            tags=[],
            classification_time_seconds=1.0,
            classification_model="model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="thumb",
            in_timestamp="00:00:00",
            out_timestamp="00:00:10",
            rating=0.5
        )
        
        result = check_if_file_exists("exists.mp4")
        assert result is True


class TestInsertResult:
    """Tests for insert_result function."""
    
    def test_insert_result_basic(self, use_temp_db):
        """Test basic insertion of a result."""
        insert_result(
            filename="new_video.mp4",
            video_description_long="A long description",
            video_description_short="short_name",
            primary_shot_type="establishing",
            tags=["dynamic", "wide"],
            classification_time_seconds=2.5,
            classification_model="test-model-v1",
            video_length_seconds=15.0,
            video_timestamp="2024-01-15T12:00:00",
            video_thumbnail_base64="thumbnail_data",
            in_timestamp="00:00:01.000",
            out_timestamp="00:00:14.000",
            rating=0.9
        )
        
        # Verify insertion
        conn = get_conn(use_temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE filename = ?", ("new_video.mp4",))
        result = cursor.fetchone()
        
        assert result is not None
        assert result['filename'] == "new_video.mp4"
        assert result['video_description_long'] == "A long description"
        assert result['rating'] == 0.9
        
        # Verify tags are stored as JSON
        tags = json.loads(result['tags'])
        assert tags == ["dynamic", "wide"]
        
        conn.close()
    
    def test_insert_result_default_keep_value(self, use_temp_db):
        """Test that default keep value is 1."""
        insert_result(
            filename="default_keep.mp4",
            video_description_long="desc",
            video_description_short="short",
            primary_shot_type="insert",
            tags=[],
            classification_time_seconds=1.0,
            classification_model="model",
            video_length_seconds=10.0,
            video_timestamp="2024-01-01T00:00:00",
            video_thumbnail_base64="thumb",
            in_timestamp="00:00:00",
            out_timestamp="00:00:10",
            rating=0.5
        )
        
        conn = get_conn(use_temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT keep FROM results WHERE filename = ?", ("default_keep.mp4",))
        result = cursor.fetchone()
        
        assert result['keep'] == 1
        
        conn.close()
