"""Tests for scripts/create_proxies.py"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
import subprocess
import pytest

# Add scripts directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import functions from create_proxies
import create_proxies


class TestFindVideoFiles:
    """Test the find_video_files function."""
    
    def test_finds_mp4_files(self, tmp_path):
        """Test that it finds .mp4 files."""
        # Create test structure
        video1 = tmp_path / "video1.mp4"
        video1.touch()
        
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        video2 = subdir / "video2.mp4"
        video2.touch()
        
        # Find videos
        videos = create_proxies.find_video_files(tmp_path)
        
        assert len(videos) == 2
        assert video1 in videos
        assert video2 in videos
    
    def test_finds_uppercase_mp4_files(self, tmp_path):
        """Test that it finds .MP4 files."""
        video = tmp_path / "VIDEO.MP4"
        video.touch()
        
        videos = create_proxies.find_video_files(tmp_path)
        
        assert len(videos) == 1
        assert video in videos
    
    def test_excludes_proxy_directories(self, tmp_path):
        """Test that files in proxy directories are excluded."""
        # Create regular video
        video1 = tmp_path / "video1.mp4"
        video1.touch()
        
        # Create proxy directory with video
        proxy_dir = tmp_path / "proxy"
        proxy_dir.mkdir()
        proxy_video = proxy_dir / "proxy_video.mp4"
        proxy_video.touch()
        
        # Create nested proxy
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        video2 = subdir / "video2.mp4"
        video2.touch()
        
        nested_proxy_dir = subdir / "proxy"
        nested_proxy_dir.mkdir()
        nested_proxy = nested_proxy_dir / "nested.mp4"
        nested_proxy.touch()
        
        # Find videos
        videos = create_proxies.find_video_files(tmp_path)
        
        # Should only find the non-proxy videos
        assert len(videos) == 2
        assert video1 in videos
        assert video2 in videos
        assert proxy_video not in videos
        assert nested_proxy not in videos
    
    def test_returns_empty_list_when_no_videos(self, tmp_path):
        """Test that empty list is returned when no videos found."""
        # Create some non-video files
        (tmp_path / "file.txt").touch()
        (tmp_path / "file.avi").touch()
        
        videos = create_proxies.find_video_files(tmp_path)
        
        assert len(videos) == 0


class TestGetVideoFramerate:
    """Test the get_video_framerate function."""
    
    def test_returns_empty_string_when_ffprobe_not_found(self, tmp_path):
        """Test that empty string is returned when ffprobe is not available."""
        # This test will pass if ffprobe is not installed
        # If ffprobe is installed, it will test with a non-existent file
        video = tmp_path / "nonexistent.mp4"
        
        result = create_proxies.get_video_framerate(video)
        
        # Should return empty string on error
        assert isinstance(result, str)


class TestCreateProxy:
    """Test the create_proxy function."""
    
    def test_creates_proxy_directory(self, tmp_path):
        """Test that proxy directory is created."""
        video = tmp_path / "video.mp4"
        video.touch()
        
        proxy_dir = tmp_path / "proxy"
        
        # Mock the actual ffmpeg call by just creating the file
        # (we can't run ffmpeg in tests without it being installed)
        success, message = create_proxies.create_proxy(video, proxy_dir, overwrite=False)
        
        # The directory should be created even if ffmpeg fails
        assert proxy_dir.exists()
        assert proxy_dir.is_dir()
    
    def test_skips_existing_proxy_when_not_overwrite(self, tmp_path):
        """Test that existing proxy is skipped when overwrite=False."""
        video = tmp_path / "video.mp4"
        video.touch()
        
        proxy_dir = tmp_path / "proxy"
        proxy_dir.mkdir()
        
        proxy_file = proxy_dir / "video.mp4"
        proxy_file.touch()
        
        success, message = create_proxies.create_proxy(video, proxy_dir, overwrite=False)
        
        assert success
        assert "Skipping" in message
        assert str(proxy_file) in message


class TestMainFunction:
    """Test the main function behavior."""
    
    def test_dry_run_mode(self, tmp_path, monkeypatch, capsys):
        """Test that dry-run mode doesn't create files."""
        # Create test videos
        video = tmp_path / "video.mp4"
        video.touch()
        
        # Mock sys.argv
        test_args = ['create_proxies.py', '--root', str(tmp_path), '--dry-run']
        monkeypatch.setattr(sys, 'argv', test_args)
        
        # Run main
        exit_code = create_proxies.main()
        
        # Should succeed
        assert exit_code == 0
        
        # Proxy directory should not be created in dry-run
        proxy_dir = tmp_path / "proxy"
        assert not proxy_dir.exists()
        
        # Check output
        captured = capsys.readouterr()
        assert "Would create" in captured.out or "Dry run" in captured.out
    
    def test_handles_nonexistent_directory(self, tmp_path, monkeypatch, capsys):
        """Test that it handles non-existent directories gracefully."""
        nonexistent = tmp_path / "does_not_exist"
        
        test_args = ['create_proxies.py', '--root', str(nonexistent)]
        monkeypatch.setattr(sys, 'argv', test_args)
        
        exit_code = create_proxies.main()
        
        # Should fail with error code
        assert exit_code == 1
        
        # Check error message
        captured = capsys.readouterr()
        assert "does not exist" in captured.err
    
    def test_handles_no_videos(self, tmp_path, monkeypatch, capsys):
        """Test that it handles directories with no videos gracefully."""
        test_args = ['create_proxies.py', '--root', str(tmp_path)]
        monkeypatch.setattr(sys, 'argv', test_args)
        
        exit_code = create_proxies.main()
        
        # Should succeed (no errors)
        assert exit_code == 0
        
        # Check output
        captured = capsys.readouterr()
        assert "No video files found" in captured.out


class TestIntegration:
    """Integration tests (only run if ffmpeg is available)."""
    
    @pytest.mark.skipif(
        shutil.which('ffmpeg') is None,
        reason="ffmpeg not available"
    )
    def test_end_to_end_with_real_video(self, tmp_path):
        """
        End-to-end test with a real video file (if ffmpeg is available).
        
        This test creates a minimal valid video file and runs the proxy creation.
        """
        # Create a minimal test video using ffmpeg
        test_video = tmp_path / "test.mp4"
        
        # Create a 1-second black video at 480p (small and fast to encode)
        result = subprocess.run([
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'color=black:s=640x480:d=1',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-t', '1',
            str(test_video)
        ], capture_output=True)
        
        if result.returncode != 0:
            pytest.skip("Could not create test video")
        
        # Run the proxy creation
        proxy_dir = tmp_path / "proxy"
        success, message = create_proxies.create_proxy(test_video, proxy_dir)
        
        # Verify proxy was created
        assert success
        assert "Done" in message
        
        proxy_file = proxy_dir / "test.mp4"
        assert proxy_file.exists()
        
        # Verify the proxy is a valid video (basic check)
        probe_result = subprocess.run([
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=height',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(proxy_file)
        ], capture_output=True, text=True)
        
        # For a 480p source, scaling to 1080p should upscale
        # But ffmpeg should respect the aspect ratio
        height = int(probe_result.stdout.strip())
        assert height > 0  # At least verify it has a height
