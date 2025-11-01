#!/usr/bin/env python3
"""
Demo script to test the DaVinci integration without DaVinci Resolve.
This simulates the workflow to ensure the import mechanism works correctly.
"""

import os
import sys
import tempfile
import sqlite3
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def create_test_database(db_path):
    """Create a test database with sample data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            filename TEXT PRIMARY KEY,
            video_description_long TEXT,
            video_description_short TEXT,
            primary_shot_type TEXT,
            tags TEXT,
            last_updated TEXT,
            classification_time_seconds REAL,
            classification_model TEXT,
            video_length_seconds REAL,
            video_timestamp TEXT,
            video_thumbnail_base64 TEXT,
            clip_cut_duration REAL,
            keep INTEGER DEFAULT 1,
            in_timestamp TEXT,
            out_timestamp TEXT,
            rating REAL
        )
    ''')
    
    # Insert sample data
    cursor.execute("""
        INSERT INTO results (
            filename, video_description_long, video_description_short,
            primary_shot_type, tags, last_updated, classification_time_seconds,
            classification_model, video_length_seconds, video_timestamp,
            video_thumbnail_base64, in_timestamp, out_timestamp, rating
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "test_video.mp4",
        "A long description of the test video",
        "Test video",
        "pov",
        '["dynamic", "medium"]',
        "2024-01-01T00:00:00",
        1.5,
        "test-model",
        10.0,
        "2024-01-01T00:00:00",
        "base64data",
        "00:00:01.000",
        "00:00:05.000",
        0.8
    ))
    
    conn.commit()
    conn.close()
    print(f"Created test database: {db_path}")

def test_davinci_integration():
    """Test the DaVinci integration setup."""
    print("=" * 60)
    print("Testing DaVinci Resolve Integration")
    print("=" * 60)
    
    # Create a temporary project directory
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir) / "vlog_test_project"
        project_dir.mkdir()
        
        # Create src/vlog structure
        src_dir = project_dir / "src"
        vlog_dir = src_dir / "vlog"
        vlog_dir.mkdir(parents=True)
        
        # Copy necessary files
        vlog_src = Path(__file__).parent.parent / "src" / "vlog"
        for file in ["__init__.py", "db_extract_v2.py"]:
            src_file = vlog_src / file
            if src_file.exists():
                dest_file = vlog_dir / file
                dest_file.write_text(src_file.read_text())
        
        # Create test database
        db_path = project_dir / "video_results.db"
        create_test_database(str(db_path))
        
        # Set environment variable
        os.environ['VLOG_PROJECT_PATH'] = str(project_dir)
        os.environ['VLOG_AUTO_EXTRACT'] = '1'
        
        print(f"\nProject directory: {project_dir}")
        print(f"Database: {db_path}")
        print(f"VLOG_PROJECT_PATH: {os.environ['VLOG_PROJECT_PATH']}")
        print(f"VLOG_AUTO_EXTRACT: {os.environ['VLOG_AUTO_EXTRACT']}")
        
        # Import and test the davinci_clip_importer
        from vlog import davinci_clip_importer
        
        # Test setup_vlog_imports
        print("\n" + "=" * 60)
        print("Testing setup_vlog_imports()")
        print("=" * 60)
        result_path = davinci_clip_importer.setup_vlog_imports()
        
        if result_path:
            print(f"✓ Successfully set up imports")
            print(f"  Project path: {result_path}")
            print(f"  Python path includes: {src_dir}")
        else:
            print("✗ Failed to set up imports")
            return False
        
        # Test ensure_json_file
        print("\n" + "=" * 60)
        print("Testing ensure_json_file()")
        print("=" * 60)
        json_path = davinci_clip_importer.ensure_json_file(result_path)
        
        if json_path:
            print(f"✓ Successfully ensured JSON file")
            print(f"  JSON path: {json_path}")
            
            # Verify JSON content
            with open(json_path, 'r') as f:
                data = json.load(f)
            print(f"  Number of clips: {len(data)}")
            if data:
                print(f"  Sample clip: {data[0]['video_description_short']}")
        else:
            print("✗ Failed to ensure JSON file")
            return False
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
        print("\nThe DaVinci integration is working correctly.")
        print("To use it in DaVinci Resolve:")
        print("1. Set VLOG_PROJECT_PATH environment variable")
        print("2. Copy davinci_clip_importer.py to DaVinci's script directory")
        print("3. Run the script from DaVinci's console")
        
        return True

if __name__ == "__main__":
    success = test_davinci_integration()
    sys.exit(0 if success else 1)
