"""
Auto-ingest service using Snakemake workflow with status monitoring.

This module provides an auto-ingest service that monitors a directory for new video files
and automatically runs the complete Snakemake ingestion pipeline with real-time progress tracking.
"""

import os
import time
import logging
import subprocess
import threading
import tempfile
import yaml
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)

# Supported video file extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.MP4', '.MOV', '.AVI', '.MKV'}

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


class VideoFileHandler(FileSystemEventHandler):
    """Handles file system events for video files."""
    
    def __init__(self, callback):
        """
        Initialize the handler.
        
        Args:
            callback: Function to call when a new video file is detected.
        """
        super().__init__()
        self.callback = callback
        self._processing = set()
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


class AutoIngestSnakemakeService:
    """Service for automatically ingesting new video files using full Snakemake pipeline."""
    
    def __init__(
        self,
        watch_directory: str,
        preview_folder: Optional[str] = None,
        model_name: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit",
        cores: int = 8,
        resources_mem_gb: int = 12,
        logger_port: int = 5556
    ):
        """
        Initialize the auto-ingest Snakemake service.
        
        Args:
            watch_directory: Directory to monitor for new video files (also used as main_folder).
            preview_folder: Optional separate preview folder. If None, uses watch_directory.
            model_name: ML model to use for video description.
            cores: Number of cores for Snakemake to use.
            resources_mem_gb: Memory limit in GB.
            logger_port: Port for the Snakemake logger plugin API.
        """
        self.watch_directory = os.path.abspath(watch_directory)
        self.preview_folder = os.path.abspath(preview_folder) if preview_folder else self.watch_directory
        self.model_name = model_name
        self.cores = cores
        self.resources_mem_gb = resources_mem_gb
        self.logger_port = logger_port
        self.observer: Optional[Observer] = None
        self.is_running = False
        
        # Snakemake process management
        self._snakemake_process: Optional[subprocess.Popen] = None
        self._snakemake_lock = threading.Lock()
        self._queued_files = []
        self._queue_lock = threading.Lock()
        
        logger.info(f"AutoIngestSnakemakeService initialized")
        logger.info(f"  Watch directory: {self.watch_directory}")
        logger.info(f"  Preview folder: {self.preview_folder}")
        logger.info(f"  Model: {self.model_name}")
        logger.info(f"  Cores: {self.cores}, Memory: {self.resources_mem_gb}GB")
    
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
            event_handler = VideoFileHandler(callback=self._queue_video_file)
            
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
            # Stop the observer
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
            
            # Stop any running Snakemake process
            with self._snakemake_lock:
                if self._snakemake_process:
                    logger.info("Stopping Snakemake process...")
                    self._snakemake_process.terminate()
                    try:
                        self._snakemake_process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        logger.warning("Snakemake did not stop gracefully, killing...")
                        self._snakemake_process.kill()
                    self._snakemake_process = None
            
            self.is_running = False
            logger.info("Auto-ingest service stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop auto-ingest service: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the auto-ingest service.
        
        Returns:
            Dictionary with status information.
        """
        with self._queue_lock:
            queued_count = len(self._queued_files)
        
        with self._snakemake_lock:
            is_processing = self._snakemake_process is not None and self._snakemake_process.poll() is None
        
        return {
            'is_running': self.is_running,
            'watch_directory': self.watch_directory,
            'preview_folder': self.preview_folder,
            'model_name': self.model_name,
            'cores': self.cores,
            'resources_mem_gb': self.resources_mem_gb,
            'queued_files': queued_count,
            'is_processing': is_processing,
            'logger_port': self.logger_port
        }
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get the current progress from the Snakemake logger plugin.
        
        Returns:
            Dictionary with progress information from the logger plugin.
        """
        try:
            response = requests.get(f"http://127.0.0.1:{self.logger_port}/status", timeout=2)
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'error': f'Logger API returned status {response.status_code}',
                    'available': False
                }
        except requests.RequestException as e:
            return {
                'error': f'Failed to connect to logger API: {e}',
                'available': False
            }
    
    def _process_existing_files(self) -> None:
        """Process any existing video files in the watch directory."""
        logger.info("Scanning for existing unprocessed video files...")
        
        try:
            watch_dir_obj = Path(self.watch_directory).resolve()
            
            for filename in os.listdir(self.watch_directory):
                # Validate filename
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
                
                # Queue the file
                logger.info(f"Found unprocessed file: {filename}")
                self._queue_video_file(file_path)
        except Exception as e:
            logger.error(f"Error scanning existing files: {e}")
    
    def _queue_video_file(self, file_path: str) -> None:
        """
        Add a video file to the processing queue.
        
        Args:
            file_path: Path to the video file.
        """
        filename = os.path.basename(file_path)
        logger.info(f"Queuing video file: {filename}")
        
        with self._queue_lock:
            if file_path not in self._queued_files:
                self._queued_files.append(file_path)
                logger.info(f"File queued. Queue size: {len(self._queued_files)}")
        
        # Start processing if not already running
        self._maybe_start_processing()
    
    def _maybe_start_processing(self) -> None:
        """Start Snakemake processing if not already running and files are queued."""
        with self._snakemake_lock:
            # Check if already processing
            if self._snakemake_process and self._snakemake_process.poll() is None:
                logger.debug("Snakemake is already running")
                return
            
            # Check if there are files to process
            with self._queue_lock:
                if not self._queued_files:
                    logger.debug("No files queued for processing")
                    return
        
        # Start processing in a background thread
        thread = threading.Thread(target=self._run_snakemake_workflow, daemon=False)
        thread.start()
    
    def _run_snakemake_workflow(self) -> None:
        """Run the Snakemake workflow for queued files."""
        try:
            # Get files to process
            with self._queue_lock:
                if not self._queued_files:
                    return
                files_to_process = self._queued_files.copy()
                self._queued_files.clear()
            
            logger.info(f"Starting Snakemake workflow for {len(files_to_process)} files")
            
            # Create temporary config file
            config = self._create_snakemake_config()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config, f)
                temp_config = f.name
            
            try:
                # Build Snakemake command
                snakefile = PROJECT_ROOT / 'src' / 'ingest_pipeline' / 'Snakefile'
                
                cmd = [
                    'snakemake',
                    '--snakefile', str(snakefile),
                    '--configfile', temp_config,
                    f'--config',
                    f'preview_folder={self.preview_folder}',
                    '--logger', 'vlog',
                    f'--cores={self.cores}',
                    f'--resources', f'mem_gb={self.resources_mem_gb}'
                ]
                
                logger.info(f"Running Snakemake command: {' '.join(cmd)}")
                
                # Run Snakemake
                with self._snakemake_lock:
                    self._snakemake_process = subprocess.Popen(
                        cmd,
                        cwd=str(PROJECT_ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    
                    # Stream output
                    if self._snakemake_process.stdout:
                        for line in self._snakemake_process.stdout:
                            logger.info(f"Snakemake: {line.rstrip()}")
                    
                    # Wait for completion
                    returncode = self._snakemake_process.wait()
                    
                    if returncode == 0:
                        logger.info("Snakemake workflow completed successfully")
                    else:
                        logger.error(f"Snakemake workflow failed with exit code {returncode}")
                    
                    self._snakemake_process = None
                
            finally:
                # Clean up temp config
                try:
                    os.unlink(temp_config)
                except OSError as e:
                    logger.warning(f"Failed to cleanup temp config: {e}")
            
            # Check if more files were queued during processing
            self._maybe_start_processing()
            
        except Exception as e:
            logger.error(f"Error running Snakemake workflow: {e}", exc_info=True)
            with self._snakemake_lock:
                self._snakemake_process = None
    
    def _create_snakemake_config(self) -> Dict[str, Any]:
        """
        Create Snakemake configuration dictionary.
        
        Returns:
            Configuration dictionary for Snakemake.
        """
        return {
            'sd_card_path': self.watch_directory,
            'main_folder': self.watch_directory,
            'preview_folder': self.preview_folder,
            'video_extensions': ['mp4', 'MP4', 'mov', 'MOV', 'avi', 'AVI', 'mkv', 'MKV'],
            'preview_suffix': '_preview',
            'preview_extension': 'mp4',
            'preview_settings': {
                'width': 1280,
                'crf': 23,
                'preset': 'medium'
            },
            'transcribe': {
                'model': 'mlx-community/whisper-large-v3-turbo',
                'format': 'srt',
                'task': 'transcribe'
            },
            'describe': {
                'model': self.model_name,
                'max_pixels': 224,
                'fps': 1.0
            },
            'daemon_host': '127.0.0.1',
            'daemon_port': 5555,
            'daemon_signal_file': 'status/daemon_running.signal',
            'daemon_pid_file': 'status/daemon.pid',
            'daemon_log_file': 'logs/daemon.log'
        }
