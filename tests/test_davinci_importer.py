"""
Tests for davinci_clip_importer module.
Tests the setup and configuration functions, not the actual DaVinci Resolve integration.
"""

import os
import sys
import tempfile
import json
import pytest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vlog import davinci_clip_importer


class TestSetupVlogImports:
    """Test the setup_vlog_imports function."""
    
    def test_setup_with_env_variable(self, tmp_path):
        """Test setup when VLOG_PROJECT_PATH environment variable is set."""
        # Create a mock vlog project structure
        project_dir = tmp_path / "vlog_project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        
        # Set environment variable
        old_path = os.environ.get('VLOG_PROJECT_PATH')
        os.environ['VLOG_PROJECT_PATH'] = str(project_dir)
        
        try:
            result = davinci_clip_importer.setup_vlog_imports()
            assert result == str(project_dir)
            assert str(src_dir) in sys.path
        finally:
            # Clean up
            if old_path:
                os.environ['VLOG_PROJECT_PATH'] = old_path
            else:
                os.environ.pop('VLOG_PROJECT_PATH', None)
            if str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))
    
    def test_setup_with_config_file(self, tmp_path, monkeypatch):
        """Test setup when config file exists."""
        # Create a mock vlog project structure
        project_dir = tmp_path / "vlog_project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        
        # Create config file
        config_dir = tmp_path / ".vlog"
        config_dir.mkdir()
        config_file = config_dir / "config"
        config_file.write_text(f"PROJECT_PATH={project_dir}\n")
        
        # Mock expanduser to point to our temp directory
        def mock_expanduser(path):
            if path.startswith("~/.vlog"):
                return str(tmp_path / ".vlog" / path[8:])
            return path
        
        monkeypatch.setattr(os.path, 'expanduser', mock_expanduser)
        
        # Clear environment variable
        old_path = os.environ.get('VLOG_PROJECT_PATH')
        os.environ.pop('VLOG_PROJECT_PATH', None)
        
        try:
            result = davinci_clip_importer.setup_vlog_imports()
            assert result == str(project_dir)
            assert str(src_dir) in sys.path
        finally:
            # Clean up
            if old_path:
                os.environ['VLOG_PROJECT_PATH'] = old_path
            if str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))
    
    def test_setup_without_configuration(self, monkeypatch):
        """Test setup when no configuration is provided."""
        # Clear environment variable
        old_path = os.environ.get('VLOG_PROJECT_PATH')
        os.environ.pop('VLOG_PROJECT_PATH', None)
        
        # Mock expanduser to return non-existent paths
        def mock_expanduser(path):
            return "/nonexistent" + path[1:]
        
        monkeypatch.setattr(os.path, 'expanduser', mock_expanduser)
        
        try:
            result = davinci_clip_importer.setup_vlog_imports()
            assert result is None
        finally:
            if old_path:
                os.environ['VLOG_PROJECT_PATH'] = old_path
    
    def test_setup_with_invalid_path(self):
        """Test setup when VLOG_PROJECT_PATH points to non-existent directory."""
        old_path = os.environ.get('VLOG_PROJECT_PATH')
        os.environ['VLOG_PROJECT_PATH'] = "/nonexistent/path"
        
        try:
            result = davinci_clip_importer.setup_vlog_imports()
            assert result is None
        finally:
            if old_path:
                os.environ['VLOG_PROJECT_PATH'] = old_path
            else:
                os.environ.pop('VLOG_PROJECT_PATH', None)


class TestGetJsonPath:
    """Test the get_json_path function."""
    
    def test_get_json_path_relative(self, tmp_path, monkeypatch):
        """Test getting JSON path with relative path."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        
        monkeypatch.setenv("VLOG_JSON_FILE", "clips.json")
        
        result = davinci_clip_importer.get_json_path(str(project_dir))
        assert result == str(project_dir / "clips.json")
    
    def test_get_json_path_absolute(self, tmp_path, monkeypatch):
        """Test getting JSON path with absolute path."""
        project_dir = tmp_path / "project"
        json_path = tmp_path / "other" / "clips.json"
        
        monkeypatch.setenv("VLOG_JSON_FILE", str(json_path))
        
        result = davinci_clip_importer.get_json_path(str(project_dir))
        assert result == str(json_path)


class TestEnsureJsonFile:
    """Test the ensure_json_file function."""
    
    def test_ensure_json_file_exists(self, tmp_path, monkeypatch):
        """Test when JSON file already exists."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        json_file = project_dir / "clips.json"
        json_file.write_text('[]')
        
        monkeypatch.setenv("VLOG_JSON_FILE", "clips.json")
        monkeypatch.setenv("VLOG_AUTO_EXTRACT", "0")
        
        result = davinci_clip_importer.ensure_json_file(str(project_dir))
        assert result == str(json_file)
        assert json_file.exists()
    
    def test_ensure_json_file_missing_no_auto_extract(self, tmp_path, monkeypatch):
        """Test when JSON file doesn't exist and auto-extract is disabled."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        
        monkeypatch.setenv("VLOG_JSON_FILE", "clips.json")
        monkeypatch.setenv("VLOG_AUTO_EXTRACT", "0")
        
        result = davinci_clip_importer.ensure_json_file(str(project_dir))
        assert result is None
    
    def test_ensure_json_file_missing_db(self, tmp_path, monkeypatch):
        """Test when database file doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        
        monkeypatch.setenv("VLOG_JSON_FILE", "clips.json")
        monkeypatch.setenv("VLOG_DB_FILE", "video_results.db")
        monkeypatch.setenv("VLOG_AUTO_EXTRACT", "1")
        
        result = davinci_clip_importer.ensure_json_file(str(project_dir))
        assert result is None


class TestTimestampToFrames:
    """Test the timestamp_to_frames function."""
    
    def test_timestamp_with_milliseconds(self):
        """Test timestamp conversion with milliseconds."""
        result = davinci_clip_importer.timestamp_to_frames("00:00:01.000", 30.0)
        assert result == 30
    
    def test_timestamp_without_milliseconds(self):
        """Test timestamp conversion without milliseconds."""
        result = davinci_clip_importer.timestamp_to_frames("00:00:01", 30.0)
        assert result == 30
    
    def test_timestamp_complex(self):
        """Test complex timestamp conversion."""
        # 1 hour, 2 minutes, 3 seconds, 500 ms at 60 fps
        # = 3600 + 120 + 3 + 0.5 = 3723.5 seconds
        # = 3723.5 * 60 = 223410 frames
        result = davinci_clip_importer.timestamp_to_frames("01:02:03.500", 60.0)
        assert result == 223410
    
    def test_timestamp_invalid_format(self):
        """Test invalid timestamp format."""
        result = davinci_clip_importer.timestamp_to_frames("invalid", 30.0)
        assert result == -1
    
    def test_timestamp_different_fps(self):
        """Test timestamp conversion with different FPS values."""
        # 1 second at different frame rates
        assert davinci_clip_importer.timestamp_to_frames("00:00:01.000", 24.0) == 24
        assert davinci_clip_importer.timestamp_to_frames("00:00:01.000", 25.0) == 25
        assert davinci_clip_importer.timestamp_to_frames("00:00:01.000", 30.0) == 30
        assert davinci_clip_importer.timestamp_to_frames("00:00:01.000", 60.0) == 60
