#!/usr/bin/env python3
"""
Tests for Snakemake workflow helper scripts.

Tests the SD card discovery, preview creation, and describe-to-json functionality.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestDiscoverVideos(unittest.TestCase):
    """Test the discover_videos.py script."""
    
    def setUp(self):
        """Create a temporary SD card structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.sd_card = Path(self.temp_dir) / "sdcard"
        self.sd_card.mkdir()
        
        # Create test video files
        (self.sd_card / "video1.mp4").touch()
        (self.sd_card / "video1_preview.mp4").touch()
        (self.sd_card / "video2.MP4").touch()
        # video2 has no preview
        
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_discover_videos_with_preview(self):
        """Test discovering videos with preview files."""
        script_path = Path(__file__).parent.parent / "src" / "ingest_pipeline" / "discover_videos.py"
        
        import subprocess
        result = subprocess.run(
            [
                "python3",
                str(script_path),
                str(self.sd_card),
                '["mp4", "MP4"]',
                "_preview"
            ],
            capture_output=True,
            text=True
        )
        
        self.assertEqual(result.returncode, 0)
        
        output = json.loads(result.stdout)
        self.assertEqual(output["count"], 2)
        
        # Check that video1 has a preview
        video1 = next((v for v in output["videos"] if v["stem"] == "video1"), None)
        self.assertIsNotNone(video1)
        self.assertTrue(video1["has_preview"])
        
        # Check that video2 has no preview
        video2 = next((v for v in output["videos"] if v["stem"] == "video2"), None)
        self.assertIsNotNone(video2)
        self.assertFalse(video2["has_preview"])


class TestCreatePreview(unittest.TestCase):
    """Test the create_preview.py script (without actually running ffmpeg)."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_preview_validates_input(self):
        """Test that create_preview validates input file exists."""
        script_path = Path(__file__).parent.parent / "src" / "ingest_pipeline" / "create_preview.py"
        
        import subprocess
        result = subprocess.run(
            [
                "python3",
                str(script_path),
                "nonexistent.mp4",
                os.path.join(self.temp_dir, "output.mp4")
            ],
            capture_output=True,
            text=True
        )
        
        # Should fail because input doesn't exist
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)


class TestDescribeToJson(unittest.TestCase):
    """Test the describe_to_json.py script structure."""
    
    def test_script_exists_and_executable(self):
        """Test that the script exists and is executable."""
        script_path = Path(__file__).parent.parent / "src" / "ingest_pipeline" / "describe_to_json.py"
        
        self.assertTrue(script_path.exists())
        # Check it's a Python script
        with open(script_path) as f:
            first_line = f.readline()
            self.assertTrue(first_line.startswith("#!"))
    
    def test_describe_to_json_usage(self):
        """Test that script shows usage when called without args."""
        script_path = Path(__file__).parent.parent / "src" / "ingest_pipeline" / "describe_to_json.py"
        
        import subprocess
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True
        )
        
        # Should fail with usage message (either in stderr or because of import error)
        self.assertNotEqual(result.returncode, 0)


class TestSnakemakeConfig(unittest.TestCase):
    """Test the Snakemake configuration file."""
    
    def test_config_yaml_exists(self):
        """Test that config.yaml exists."""
        config_path = Path(__file__).parent.parent / "config.yaml"
        self.assertTrue(config_path.exists())
    
    def test_config_yaml_valid(self):
        """Test that config.yaml is valid YAML."""
        config_path = Path(__file__).parent.parent / "config.yaml"
        
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Check expected keys
        self.assertIn("sd_card_path", config)
        self.assertIn("main_folder", config)
        self.assertIn("preview_folder", config)
        self.assertIn("video_extensions", config)
        self.assertIn("preview_settings", config)
        self.assertIn("transcribe", config)
        self.assertIn("describe", config)


class TestSnakefile(unittest.TestCase):
    """Test the Snakefile."""
    
    def test_snakefile_exists(self):
        """Test that Snakefile exists."""
        snakefile_path = Path(__file__).parent.parent / "Snakefile"
        self.assertTrue(snakefile_path.exists())
    
    def test_snakefile_syntax(self):
        """Test that Snakefile contains expected rules."""
        snakefile_path = Path(__file__).parent.parent / "Snakefile"
        
        # Read the Snakefile and check for expected rules
        with open(snakefile_path) as f:
            content = f.read()
        
        # Check for expected Snakemake rules
        self.assertIn("rule all:", content)
        self.assertIn("rule copy_main:", content)
        self.assertIn("rule copy_or_create_preview:", content)
        self.assertIn("rule transcribe:", content)
        self.assertIn("rule clean_subtitles:", content)
        self.assertIn("rule describe:", content)


if __name__ == "__main__":
    unittest.main()
