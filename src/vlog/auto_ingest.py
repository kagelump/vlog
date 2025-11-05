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

from vlog.db import check_if_file_exists, initialize_db, insert_result
from vlog.describe_client import DaemonManager

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
    
    def __init__(self, watch_directory: str, model_name: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit",
                 batch_size: int = 5, batch_timeout: float = 60.0):
        """
        Initialize the auto-ingest service.
        
        Args:
            watch_directory: Directory to monitor for new video files.
            model_name: ML model to use for video description.
            batch_size: Number of files to accumulate before processing (default: 5).
            batch_timeout: Maximum seconds to wait before processing incomplete batch (default: 60).
        """
        self.watch_directory = os.path.abspath(watch_directory)
        self.model_name = model_name
        self.observer: Optional[Observer] = None
        self.is_running = False
        
        # Batch processing configuration
        self.batch_size = max(1, batch_size)
        self.batch_timeout = max(1.0, batch_timeout)
        self._batch_queue = []
        self._batch_lock = threading.Lock()
        self._batch_timer: Optional[threading.Timer] = None
        self._processing_batch = False
        self._batch_thread: Optional[threading.Thread] = None
        
        # Ensure database is initialized
        initialize_db()
        
        logger.info(f"AutoIngestService initialized for directory: {self.watch_directory}")
        logger.info(f"Batch processing: size={self.batch_size}, timeout={self.batch_timeout}s")
    
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
            # Stop the observer
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
            
            # Cancel any pending batch timer
            with self._batch_lock:
                if self._batch_timer:
                    self._batch_timer.cancel()
                    self._batch_timer = None

            # If a batch worker thread is running, wait for it to finish so we have exclusive shutdown ordering
            if self._batch_thread and self._batch_thread.is_alive():
                logger.info("Waiting for batch processing to complete...")
                self._batch_thread.join(timeout=60)  # Wait up to 60 seconds
                if self._batch_thread.is_alive():
                    logger.warning("Batch processing did not complete within timeout")

            # If any files remain in the queue after the worker finished, process them synchronously now
            remaining = []
            with self._batch_lock:
                if self._batch_queue:
                    remaining = self._batch_queue.copy()
                    self._batch_queue.clear()
                    self._processing_batch = True

            if remaining:
                logger.info(f"Processing {len(remaining)} remaining files before shutdown")
                # Process synchronously by calling worker directly (not in daemon thread)
                try:
                    self._process_batch_worker(remaining)
                finally:
                    self._processing_batch = False
            
            self.is_running = False
            self._processing_batch = False
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
        with self._batch_lock:
            batch_queue_size = len(self._batch_queue)
        
        return {
            'is_running': self.is_running,
            'watch_directory': self.watch_directory,
            'model_name': self.model_name,
            'batch_size': self.batch_size,
            'batch_timeout': self.batch_timeout,
            'queued_files': batch_queue_size,
            'processing_batch': self._processing_batch
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
        Add a video file to the batch queue for processing.
        
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
            
            logger.info(f"Adding video file to batch queue: {filename}")
            
            with self._batch_lock:
                # Add to batch queue
                self._batch_queue.append(file_path)
                
                # Cancel existing timer if present
                if self._batch_timer:
                    self._batch_timer.cancel()
                    self._batch_timer = None
                
                # Check if batch is full
                if len(self._batch_queue) >= self.batch_size:
                    logger.info(f"Batch size reached ({self.batch_size}), processing batch")
                    self._process_batch()
                else:
                    # Start timeout timer for incomplete batch
                    logger.info(f"Batch has {len(self._batch_queue)}/{self.batch_size} files, "
                              f"starting {self.batch_timeout}s timer")
                    self._batch_timer = threading.Timer(self.batch_timeout, self._on_batch_timeout)
                    self._batch_timer.start()
            
        except Exception as e:
            logger.error(f"Error queueing {filename}: {e}", exc_info=True)
    
    def _on_batch_timeout(self) -> None:
        """Called when the batch timeout expires."""
        with self._batch_lock:
            if self._batch_queue and not self._processing_batch:
                logger.info(f"Batch timeout reached, processing {len(self._batch_queue)} queued files")
                self._process_batch()
    
    def _process_batch(self) -> None:
        """
        Process a batch of video files through the pipeline.
        
        This method should be called while holding _batch_lock.
        It processes files in these stages:
        1. Run Snakemake for preprocessing (transcribe, clean_subtitles) with parallelism
        2. Start describe daemon
        3. Use daemon to describe all videos in batch (model loaded once)
        4. Import results to database
        """
        if not self._batch_queue:
            return
        
        # If already processing, another worker is running and will pick up queued items
        if self._processing_batch:
            logger.debug("Batch processor already running; queued files will be picked up by running worker")
            return

        # Mark as processing and extract initial batch
        self._processing_batch = True
        # Cancel timer if present and take a greedy snapshot of all currently queued files
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None

        initial_batch = self._batch_queue.copy()
        self._batch_queue.clear()

        # Start a single worker thread that will process batches greedily and sequentially
        self._batch_thread = threading.Thread(
            target=self._process_batches_loop,
            args=(initial_batch,),
            daemon=False,
            name="BatchProcessWorker"
        )
        self._batch_thread.start()

    def _process_batches_loop(self, initial_batch: list[str]) -> None:
        """
        Worker loop that processes the initial batch and then continues to drain the queue
        greedily until no more files remain. This ensures only one batch processor runs at a time
        and all queued files are handled synchronously in series.
        """
        try:
            # Process the first batch
            if initial_batch:
                self._process_batch_worker(initial_batch)

            # Keep draining any newly queued files until queue is empty
            while True:
                next_batch = []
                with self._batch_lock:
                    if self._batch_queue:
                        next_batch = self._batch_queue.copy()
                        self._batch_queue.clear()

                if not next_batch:
                    break

                logger.info(f"Greedy worker picked up {len(next_batch)} additional files")
                self._process_batch_worker(next_batch)

        finally:
            # Mark processing as finished and clear thread handle
            self._processing_batch = False
            self._batch_thread = None
    
    def _process_batch_worker(self, batch_files: list[str]) -> None:
        """
        Worker thread to process a batch of files.
        
        Args:
            batch_files: List of file paths to process.
        """
        try:
            logger.info(f"Processing batch of {len(batch_files)} files")
            
            # Step 1: Run Snakemake for preprocessing stages (up to cleaned subtitles)
            logger.info("Step 1: Running preprocessing (transcribe, clean_subtitles)")
            preprocessed_files = self._run_batch_preprocessing(batch_files)
            
            if not preprocessed_files:
                logger.error("Preprocessing failed for all files in batch")
                return
            
            # Step 2: Use describe daemon to process all videos
            logger.info(f"Step 2: Describing {len(preprocessed_files)} videos using daemon")
            described_files = self._run_batch_describe(preprocessed_files)
            
            # Step 3: Import results to database
            logger.info(f"Step 3: Importing {len(described_files)} results to database")
            for json_path in described_files:
                try:
                    self._import_json_to_database(json_path)
                except Exception as e:
                    logger.error(f"Failed to import {json_path}: {e}")
            
            logger.info(f"Batch processing complete: {len(described_files)}/{len(batch_files)} successful")
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}", exc_info=True)
        finally:
            # Do not flip _processing_batch here — the loop owner manages that flag
            pass
    
    def _run_batch_preprocessing(self, batch_files: list[str]) -> list[str]:
        """
        Run preprocessing stages (transcribe, clean_subtitles) for a batch of files.
        
        Args:
            batch_files: List of video file paths.
            
        Returns:
            List of successfully preprocessed file paths.
        """
        successful_files = []
        
        for video_path in batch_files:
            try:
                video_path_obj = Path(video_path).resolve()
                video_dir = video_path_obj.parent
                stem = video_path_obj.stem
                extension = video_path_obj.suffix[1:] if video_path_obj.suffix else 'mp4'
                
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
                        continue
                    
                    # Target: cleaned subtitle file (stops before describe step)
                    subtitle_target = str(video_dir / f"{stem}_cleaned.srt")
                    
                    # Run Snakemake for preprocessing only
                    cmd = [
                        'snakemake',
                        '--snakefile', str(snakefile),
                        '--configfile', temp_config,
                        '--cores', '1',
                        '--quiet', 'progress',
                        '--',
                        subtitle_target
                    ]
                    
                    logger.info(f"Preprocessing: {video_path_obj.name}")
                    result = subprocess.run(
                        cmd,
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=1800  # 30 minute timeout
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"Preprocessing failed for {video_path_obj.name}: {result.stderr}")
                        continue
                    
                    successful_files.append(video_path)
                    logger.info(f"Preprocessing complete: {video_path_obj.name}")
                    
                finally:
                    # Clean up temporary config
                    try:
                        os.unlink(temp_config)
                    except OSError as e:
                        logger.warning(f"Failed to cleanup temp config: {e}")
                        
            except subprocess.TimeoutExpired:
                logger.error(f"Preprocessing timeout for: {video_path}")
            except Exception as e:
                logger.error(f"Preprocessing error for {video_path}: {e}")
        
        return successful_files

    def _run_snakemake_pipeline(self, video_path: str) -> tuple[bool, str | None]:
        """
        Run Snakemake preprocessing for a single video and return (success, json_path).

        This helper creates a temporary config file and invokes snakemake with --configfile.
        Returns True and the expected JSON output path on success, otherwise False, None.
        """
        try:
            video_path_obj = Path(video_path).resolve()
            video_dir = video_path_obj.parent
            stem = video_path_obj.stem
            extension = video_path_obj.suffix[1:] if video_path_obj.suffix else 'mp4'

            # Create temporary config file
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
                    'transcribe': {'model': 'mlx-community/whisper-large-v3-turbo'},
                    'describe': {'model': self.model_name, 'max_pixels': 224}
                }
                yaml.dump(config, f)
                temp_config = f.name

            try:
                snakefile = PROJECT_ROOT / 'Snakefile'
                if not snakefile.exists():
                    logger.error(f"Snakefile not found at {snakefile}")
                    return False, None

                # Target: cleaned subtitle (pre-describe target)
                subtitle_target = str(video_dir / f"{stem}_cleaned.srt")

                cmd = [
                    'snakemake',
                    '--snakefile', str(snakefile),
                    '--configfile', temp_config,
                    '--cores', '1',
                    '--quiet', 'progress',
                    '--',
                    subtitle_target,
                ]

                logger.info(f"Running snakemake preprocessing for: {video_path_obj.name}")
                result = subprocess.run(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=1800,
                )

                if result.returncode != 0:
                    logger.error(f"Preprocessing failed for {video_path_obj.name}: {result.stderr}")
                    return False, None

                # Assume the describe output JSON will be next to the video with .json suffix
                json_path = str(video_path_obj.with_suffix('.json'))
                return True, json_path
            finally:
                try:
                    os.unlink(temp_config)
                except OSError:
                    pass

        except Exception as e:
            logger.error(f"Error running snakemake pipeline: {e}")
            return False, None
    
    def _run_batch_describe(self, video_paths: list[str]) -> list[str]:
        """
        Use describe daemon to process a batch of videos.
        
        Args:
            video_paths: List of preprocessed video file paths.
            
        Returns:
            List of JSON output file paths for successfully described videos.
        """
        json_files = []
        
        # Create daemon manager
        daemon_manager = DaemonManager(model=self.model_name)
        
        try:
            # Start daemon (loads model once)
            if not daemon_manager.start_daemon():
                logger.error("Failed to start describe daemon")
                return json_files
            
            # Process each video using the daemon
            for video_path in video_paths:
                try:
                    video_path_obj = Path(video_path)
                    
                    # Describe the video
                    description = daemon_manager.describe_video(
                        video_path,
                        fps=1.0,
                        max_pixels=224 * 224
                    )
                    
                    if not description:
                        logger.error(f"Failed to describe: {video_path_obj.name}")
                        continue
                    
                    # Save JSON output
                    json_path = video_path_obj.with_suffix('.json')
                    with open(json_path, 'w') as f:
                        json.dump(description, f, indent=2)
                    
                    json_files.append(str(json_path))
                    logger.info(f"Described: {video_path_obj.name}")
                    
                except Exception as e:
                    logger.error(f"Error describing {video_path}: {e}", exc_info=True)
            
        finally:
            # Stop the daemon
            daemon_manager.stop_daemon()
        
        return json_files
    
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
