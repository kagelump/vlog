"""
Auto-ingest service for monitoring directories and automatically processing new video files.

This module provides a file system watcher that monitors a directory for new video files
and automatically runs the ingestion pipeline via Snakemake workflow.
"""

import os
import time
import logging
import subprocess
import threading
import tempfile
import yaml
import json
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from vlog.db import check_if_file_exists, initialize_db

logger = logging.getLogger(__name__)

# Supported video file extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.MP4', '.MOV', '.AVI', '.MKV'}

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


class VideoFileHandler(FileSystemEventHandler):
    """Handles file system events for video files."""
    
    def __init__(self, callback: Callable[[str], None]):
        """
        Initialize the handler.
        
        Args:
            callback: Function to call when a new video file is detected.
                     Takes the file path as argument.
        """
        super().__init__()
        self.callback = callback
        self._processing = set()  # Track files currently being processed
        self._lock = threading.Lock()
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Called when a file or directory is created."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if self._is_video_file(file_path):
            # Wait a bit to ensure file is fully written
            time.sleep(2)
            
            with self._lock:
                if file_path not in self._processing:
                    self._processing.add(file_path)
                    try:
                        self.callback(file_path)
                    finally:
                        self._processing.discard(file_path)
    
    def _is_video_file(self, file_path: str) -> bool:
        """Check if the file is a supported video file."""
        return Path(file_path).suffix in VIDEO_EXTENSIONS


class AutoIngestService:
    """Service for automatically ingesting new video files using Snakemake pipeline."""
    
    def __init__(self, watch_directory: str, model_name: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit"):
        """
        Initialize the auto-ingest service.
        
        Args:
            watch_directory: Directory to monitor for new video files.
            model_name: ML model to use for video description.
        """
        self.watch_directory = os.path.abspath(watch_directory)
        self.model_name = model_name
        self.observer: Optional[Observer] = None
        self.is_running = False
        
        # Ensure database is initialized
        initialize_db()
        
        logger.info(f"AutoIngestService initialized for directory: {self.watch_directory}")
    
    def start(self) -> bool:
        """
        Start monitoring the directory.
        
        Returns:
            True if started successfully, False otherwise.
        """
        if self.is_running:
            logger.warning("Auto-ingest service is already running")
            return False
        
        if not os.path.isdir(self.watch_directory):
            logger.error(f"Watch directory does not exist: {self.watch_directory}")
            return False
        
        try:
            # Create file handler with callback
            event_handler = VideoFileHandler(callback=self._process_video_file)
            
            # Create and start observer
            self.observer = Observer()
            self.observer.schedule(event_handler, self.watch_directory, recursive=False)
            self.observer.start()
            
            self.is_running = True
            logger.info(f"Auto-ingest service started, monitoring: {self.watch_directory}")
            
            # Process any existing unprocessed files
            self._process_existing_files()
            
            return True
        except Exception as e:
            logger.error(f"Failed to start auto-ingest service: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop monitoring the directory.
        
        Returns:
            True if stopped successfully, False otherwise.
        """
        if not self.is_running:
            logger.warning("Auto-ingest service is not running")
            return False
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
            
            self.is_running = False
            logger.info("Auto-ingest service stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop auto-ingest service: {e}")
            return False
    
    def get_status(self) -> dict:
        """
        Get the current status of the auto-ingest service.
        
        Returns:
            Dictionary with status information.
        """
        return {
            'is_running': self.is_running,
            'watch_directory': self.watch_directory,
            'model_name': self.model_name
        }
    
    def _process_existing_files(self) -> None:
        """Process any existing video files in the watch directory that haven't been processed."""
        logger.info("Scanning for existing unprocessed video files...")
        
        try:
            watch_dir_obj = Path(self.watch_directory).resolve()
            
            for filename in os.listdir(self.watch_directory):
                # Validate filename doesn't contain path separators
                if os.path.sep in filename or filename.startswith('.'):
                    continue
                
                file_path = os.path.join(self.watch_directory, filename)
                file_path_obj = Path(file_path).resolve()
                
                # Ensure file is within watch directory
                try:
                    file_path_obj.relative_to(watch_dir_obj)
                except ValueError:
                    logger.warning(f"Skipping file outside watch directory: {filename}")
                    continue
                
                if not os.path.isfile(file_path):
                    continue
                
                if Path(file_path).suffix not in VIDEO_EXTENSIONS:
                    continue
                
                # Check if already processed (idempotency)
                if check_if_file_exists(filename):
                    logger.info(f"Skipping already processed file: {filename}")
                    continue
                
                # Process the file
                logger.info(f"Found unprocessed file: {filename}")
                self._process_video_file(file_path)
        except Exception as e:
            logger.error(f"Error scanning existing files: {e}")
    
    def _process_video_file(self, file_path: str) -> None:
        """
        Process a single video file through the Snakemake pipeline.
        
        This method is idempotent - it will skip files that have already been processed.
        
        Args:
            file_path: Path to the video file to process.
        """
        filename = os.path.basename(file_path)
        
        try:
            # Idempotency check - skip if already processed
            if check_if_file_exists(filename):
                logger.info(f"File already processed, skipping: {filename}")
                return
            
            logger.info(f"Processing new video file: {filename}")
            
            # Run Snakemake pipeline for this file
            success, json_path = self._run_snakemake_pipeline(file_path)
            
            if not success:
                logger.error(f"Snakemake pipeline failed for: {filename}")
                return
            
            # Import JSON results to database
            self._import_json_to_database(json_path)
            
            logger.info(f"Successfully processed: {filename}")
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}", exc_info=True)
    
    def _run_snakemake_pipeline(self, video_path: str) -> tuple[bool, str]:
        """
        Run Snakemake pipeline for a single video file.
        
        Args:
            video_path: Path to the video file.
            
        Returns:
            Tuple of (success: bool, json_output_path: str).
            On failure, returns (False, "") with an empty string for the JSON path.
        """
        try:
            video_path_obj = Path(video_path).resolve()
            video_dir = video_path_obj.parent
            stem = video_path_obj.stem
            extension = video_path_obj.suffix[1:] if video_path_obj.suffix else 'mp4'  # Default to mp4 if no extension
            
            # Create a temporary config file for this run
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                config = {
                    'sd_card_path': str(video_dir),
                    'main_folder': str(video_dir),
                    'preview_folder': str(video_dir),
                    'video_extensions': [extension],
                    'preview_suffix': '_preview',
                    'preview_extension': extension,
                    'preview_settings': {
                        'width': 1280,
                        'crf': 23,
                        'preset': 'medium'
                    },
                    'transcribe': {
                        'model': 'mlx-community/whisper-large-v3-turbo'
                    },
                    'describe': {
                        'model': self.model_name,
                        'max_pixels': 224
                    }
                }
                yaml.dump(config, f)
                temp_config = f.name
            
            try:
                # Path to Snakefile
                snakefile = PROJECT_ROOT / 'Snakefile'
                
                if not snakefile.exists():
                    logger.error(f"Snakefile not found at {snakefile}")
                    return False, ""
                
                # Target: the final JSON file
                json_target = str(video_dir / f"{stem}.json")
                
                # Run Snakemake
                cmd = [
                    'snakemake',
                    '--snakefile', str(snakefile),
                    '--configfile', temp_config,
                    '--cores', '1',
                    '--quiet',
                    json_target
                ]
                
                logger.info(f"Running Snakemake pipeline for: {video_path_obj.name}")
                result = subprocess.run(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=1800  # 30 minute timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"Snakemake pipeline failed: {result.stderr}")
                    if result.stdout:
                        logger.error(f"Snakemake stdout: {result.stdout}")
                    return False, ""
                
                logger.info(f"Snakemake pipeline completed for: {video_path_obj.name}")
                return True, json_target
                
            finally:
                # Clean up temporary config
                try:
                    os.unlink(temp_config)
                except OSError as e:
                    logger.warning(f"Failed to cleanup temp config: {e}")
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Snakemake pipeline timeout for: {video_path}")
            return False, ""
        except Exception as e:
            logger.error(f"Snakemake pipeline error: {e}")
            return False, ""
    
    def _import_json_to_database(self, json_path: str) -> None:
        """
        Import JSON results into the database.
        
        Args:
            json_path: Path to the JSON file with results.
        """
        try:
            if not os.path.exists(json_path):
                logger.error(f"JSON file not found: {json_path}")
                return
            
            logger.info(f"Importing results from: {json_path}")
            
            # Load JSON data
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Import required function
            from vlog.db import insert_result
            
            # Insert into database
            insert_result(
                filename=data['filename'],
                video_description_long=data.get('video_description_long', ''),
                video_description_short=data.get('video_description_short', ''),
                primary_shot_type=data.get('primary_shot_type', ''),
                tags=data.get('tags', []),
                classification_time_seconds=data.get('classification_time_seconds', 0.0),
                classification_model=data.get('classification_model', ''),
                video_length_seconds=data.get('video_length_seconds', 0.0),
                video_timestamp=data.get('video_timestamp', ''),
                video_thumbnail_base64=data.get('video_thumbnail_base64', ''),
                in_timestamp=data.get('in_timestamp'),
                out_timestamp=data.get('out_timestamp'),
                rating=data.get('rating', 0.0),
                segments=data.get('segments')
            )
            
            logger.info(f"Successfully imported to database: {data['filename']}")
            
        except Exception as e:
            logger.error(f"Error importing JSON to database: {e}", exc_info=True)
            raise
