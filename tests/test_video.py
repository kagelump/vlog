"""Tests for vlog.video module."""
import os
import tempfile
import datetime
from pathlib import Path
import pytest
import sys
import cv2
import numpy as np
import base64

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vlog.video import (
    get_video_length_and_timestamp,
    get_video_thumbnail,
    BLACK_PIXEL_BASE64,
)


@pytest.fixture
def sample_video():
    """Create a temporary sample video file for testing."""
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix='.mp4')
    os.close(fd)
    
    # Create a simple video with OpenCV
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30.0
    frame_size = (640, 480)
    
    out = cv2.VideoWriter(path, fourcc, fps, frame_size)
    
    # Create 90 frames (3 seconds at 30 fps)
    for i in range(90):
        # Create a frame with varying colors
        frame = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
        # Add some variation to each frame
        frame[:, :] = [i % 255, (i * 2) % 255, (i * 3) % 255]
        out.write(frame)
    
    out.release()
    
    yield path
    
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def nonexistent_video():
    """Provide a path to a non-existent video file."""
    return "/tmp/nonexistent_video_file_12345.mp4"


class TestGetVideoLengthAndTimestamp:
    """Tests for get_video_length_and_timestamp function."""
    
    def test_get_video_length_and_timestamp_valid_video(self, sample_video):
        """Test getting length and timestamp from a valid video."""
        length, timestamp = get_video_length_and_timestamp(sample_video)
        
        # Check that length is approximately 3 seconds (90 frames at 30 fps)
        assert isinstance(length, float)
        assert 2.5 < length < 3.5  # Allow some tolerance
        
        # Check timestamp format (ISO format)
        assert isinstance(timestamp, str)
        # Should be parseable as datetime
        parsed_time = datetime.datetime.fromisoformat(timestamp)
        assert isinstance(parsed_time, datetime.datetime)
    
    def test_get_video_length_and_timestamp_nonexistent_file(self, nonexistent_video):
        """Test behavior with non-existent file."""
        length, timestamp = get_video_length_and_timestamp(nonexistent_video)
        
        # Length should be 0.0 for non-existent file
        assert length == 0.0
        
        # Timestamp should still be a valid ISO format string (current time)
        assert isinstance(timestamp, str)
        parsed_time = datetime.datetime.fromisoformat(timestamp)
        assert isinstance(parsed_time, datetime.datetime)
    
    def test_get_video_length_and_timestamp_uses_file_mtime(self, sample_video):
        """Test that timestamp matches file modification time."""
        length, timestamp = get_video_length_and_timestamp(sample_video)
        
        # Get the file's actual modification time
        mtime = os.path.getmtime(sample_video)
        expected_timestamp = datetime.datetime.fromtimestamp(mtime).isoformat()
        
        # The timestamps should match
        assert timestamp == expected_timestamp


class TestGetVideoThumbnail:
    """Tests for get_video_thumbnail function."""
    
    def test_get_video_thumbnail_valid_video(self, sample_video):
        """Test extracting a thumbnail from a valid video."""
        thumbnail_frame = 1  # Request frame 1 (safer for 3-second video at 30fps)
        thumbnail_base64 = get_video_thumbnail(sample_video, thumbnail_frame, thumbnail_frame_fps=1.0)
        
        # Should return a base64 string
        assert isinstance(thumbnail_base64, str)
        # Should not be the black pixel (video exists and is readable)
        assert thumbnail_base64 != BLACK_PIXEL_BASE64
        
        # Verify it's valid base64
        try:
            decoded = base64.b64decode(thumbnail_base64)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Returned thumbnail is not valid base64: {e}")
    
    def test_get_video_thumbnail_nonexistent_file(self, nonexistent_video):
        """Test behavior with non-existent video file."""
        thumbnail_base64 = get_video_thumbnail(nonexistent_video, 0, thumbnail_frame_fps=1.0)
        
        # Should return the black pixel fallback
        assert thumbnail_base64 == BLACK_PIXEL_BASE64
    
    def test_get_video_thumbnail_different_frame(self, sample_video):
        """Test extracting thumbnails from different frames."""
        thumbnail1 = get_video_thumbnail(sample_video, 5, thumbnail_frame_fps=1.0)
        thumbnail2 = get_video_thumbnail(sample_video, 50, thumbnail_frame_fps=1.0)
        
        # Both should be valid base64
        assert isinstance(thumbnail1, str)
        assert isinstance(thumbnail2, str)
        
        # They might be different (depending on video content)
        # At minimum, both should decode successfully
        decoded1 = base64.b64decode(thumbnail1)
        decoded2 = base64.b64decode(thumbnail2)
        assert len(decoded1) > 0
        assert len(decoded2) > 0
    
    def test_get_video_thumbnail_frame_zero(self, sample_video):
        """Test extracting the first frame."""
        thumbnail_base64 = get_video_thumbnail(sample_video, 0, thumbnail_frame_fps=1.0)
        
        assert isinstance(thumbnail_base64, str)
        assert thumbnail_base64 != BLACK_PIXEL_BASE64
        
        # Should be valid base64
        decoded = base64.b64decode(thumbnail_base64)
        assert len(decoded) > 0
    
    def test_get_video_thumbnail_different_fps(self, sample_video):
        """Test thumbnail extraction with different FPS settings."""
        # Extract at different FPS values
        thumbnail_fps1 = get_video_thumbnail(sample_video, 1, thumbnail_frame_fps=1.0)
        thumbnail_fps2 = get_video_thumbnail(sample_video, 1, thumbnail_frame_fps=2.0)
        
        # Both should be valid
        assert isinstance(thumbnail_fps1, str)
        assert isinstance(thumbnail_fps2, str)
        assert thumbnail_fps1 != BLACK_PIXEL_BASE64
        assert thumbnail_fps2 != BLACK_PIXEL_BASE64


class TestBlackPixelBase64:
    """Tests for BLACK_PIXEL_BASE64 constant."""
    
    def test_black_pixel_is_valid_base64(self):
        """Test that BLACK_PIXEL_BASE64 is valid base64."""
        try:
            decoded = base64.b64decode(BLACK_PIXEL_BASE64)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"BLACK_PIXEL_BASE64 is not valid base64: {e}")
    
    def test_black_pixel_constant_exists(self):
        """Test that the constant is defined and accessible."""
        assert BLACK_PIXEL_BASE64 is not None
        assert isinstance(BLACK_PIXEL_BASE64, str)
        assert len(BLACK_PIXEL_BASE64) > 0
