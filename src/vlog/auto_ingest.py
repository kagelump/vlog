"""
Auto-ingest service for monitoring directories and automatically processing new video files.

This module provides a file system watcher that monitors a directory for new video files
and automatically runs the ingestion pipeline (transcription, subtitle cleaning, and description).
"""

import os
import time
import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from vlog.db import check_if_file_exists, initialize_db
from vlog.describe import describe_video, load_subtitle_file
from vlog.video import get_video_length_and_timestamp, get_video_thumbnail
from vlog.db import insert_result
from vlog.srt_cleaner import parse_srt, clean_subtitles, reassemble_srt

logger = logging.getLogger(__name__)

# Supported video file extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.MP4', '.MOV', '.AVI', '.MKV'}

# Video length thresholds for FPS adjustment (in seconds)
VIDEO_LENGTH_THRESHOLD_1 = 120  # 2 minutes
VIDEO_LENGTH_THRESHOLD_2 = 300  # 5 minutes

# FPS scaling factors
FPS_SCALE_MEDIUM = 0.5  # For videos between threshold 1 and 2
FPS_SCALE_LONG = 0.25   # For videos longer than threshold 2

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
    """Service for automatically ingesting new video files."""
    
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
        self._model = None
        self._processor = None
        self._config = None
        self._lock = threading.Lock()
        
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
        Process a single video file through the complete ingestion pipeline.
        
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
            
            # Step 1: Transcribe (create subtitle file)
            srt_path = self._transcribe_video(file_path)
            
            # Step 2: Clean subtitles
            cleaned_srt_path = None
            if srt_path and os.path.exists(srt_path):
                cleaned_srt_path = self._clean_subtitles(srt_path)
            
            # Step 3: Describe video (using ML model)
            self._describe_and_save(file_path, cleaned_srt_path)
            
            logger.info(f"Successfully processed: {filename}")
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}", exc_info=True)
    
    def _transcribe_video(self, video_path: str) -> Optional[str]:
        """
        Transcribe video to subtitle file using mlx_whisper.
        
        Args:
            video_path: Path to the video file.
            
        Returns:
            Path to the generated SRT file, or None if transcription failed.
        """
        try:
            # Validate video path is within watch directory
            video_path_obj = Path(video_path).resolve()
            watch_dir_obj = Path(self.watch_directory).resolve()
            
            try:
                video_path_obj.relative_to(watch_dir_obj)
            except ValueError:
                logger.error(f"Video path is outside watch directory: {video_path}")
                return None
            
            model = "mlx-community/whisper-large-v3-turbo"
            
            # Run mlx_whisper command with validated path
            cmd = [
                "mlx_whisper",
                "--model", model,
                "-f", "srt",
                "--task", "transcribe",
                str(video_path_obj)  # Use resolved absolute path
            ]
            
            logger.info(f"Transcribing: {video_path}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(watch_dir_obj),  # Use watch directory as cwd
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Transcription failed: {result.stderr}")
                return None
            
            # SRT file should be created with same name as video
            srt_path = os.path.splitext(video_path)[0] + '.srt'
            
            if os.path.exists(srt_path):
                logger.info(f"Transcription complete: {srt_path}")
                return srt_path
            else:
                logger.warning(f"SRT file not found after transcription: {srt_path}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Transcription timeout for: {video_path}")
            return None
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def _clean_subtitles(self, srt_path: str) -> Optional[str]:
        """
        Clean subtitle file to remove duplicates and hallucinations.
        
        Args:
            srt_path: Path to the subtitle file.
            
        Returns:
            Path to the cleaned SRT file, or None if cleaning failed.
        """
        try:
            logger.info(f"Cleaning subtitles: {srt_path}")
            
            # Parse SRT file
            subtitles = parse_srt(srt_path)
            
            # Clean subtitles
            cleaned_subtitles = clean_subtitles(subtitles)
            
            # Save cleaned version
            cleaned_path = srt_path.replace('.srt', '_cleaned.srt')
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(reassemble_srt(cleaned_subtitles))
            
            logger.info(f"Subtitles cleaned: {cleaned_path}")
            return cleaned_path
            
        except Exception as e:
            logger.error(f"Subtitle cleaning error: {e}")
            return None
    
    def _load_model_lazy(self):
        """Lazy-load the ML model, processor and config."""
        with self._lock:
            if self._model is None:
                from mlx_vlm import load
                from mlx_vlm.utils import load_config
                
                logger.info(f"Loading model: {self.model_name}")
                self._model, self._processor = load(self.model_name)
                self._config = load_config(self.model_name)
                logger.info("Model loaded successfully")
    
    def _describe_and_save(self, video_path: str, subtitle_path: Optional[str] = None) -> None:
        """
        Generate video description using ML model and save to database.
        
        Args:
            video_path: Path to the video file.
            subtitle_path: Optional path to subtitle file.
        """
        try:
            # Load model if not already loaded
            self._load_model_lazy()
            
            # Load subtitle if available
            subtitle_text = None
            if subtitle_path and os.path.exists(subtitle_path):
                subtitle_text = load_subtitle_file(subtitle_path)
            
            # Get video metadata
            video_length, video_timestamp = get_video_length_and_timestamp(video_path)
            
            # Adjust FPS based on video length
            fps = 1.0
            if video_length > VIDEO_LENGTH_THRESHOLD_1:
                fps = fps * FPS_SCALE_MEDIUM
            if video_length > VIDEO_LENGTH_THRESHOLD_2:
                fps = fps * FPS_SCALE_LONG
            
            # Generate description
            logger.info(f"Generating description for: {os.path.basename(video_path)}")
            start_time = time.time()
            
            desc = describe_video(
                self._model,
                self._processor,
                self._config,
                video_path,
                prompt=None,  # Use default prompt
                fps=fps,
                subtitle=subtitle_text,
                max_tokens=10000,
                temperature=0.7
            )
            
            classification_time = time.time() - start_time
            
            # Get thumbnail
            thumbnail_frame = int(desc.get('thumbnail_frame', 0))
            thumbnail_base64 = get_video_thumbnail(video_path, thumbnail_frame, fps)
            
            # Save to database
            insert_result(
                filename=os.path.basename(video_path),
                video_description_long=desc['description'],
                video_description_short=desc['short_name'],
                primary_shot_type=desc.get('primary_shot_type'),
                tags=desc.get('tags', []),
                classification_time_seconds=classification_time,
                classification_model=self.model_name,
                video_length_seconds=video_length,
                video_timestamp=video_timestamp,
                video_thumbnail_base64=thumbnail_base64,
                in_timestamp=desc.get('in_timestamp'),
                out_timestamp=desc.get('out_timestamp'),
                rating=desc.get('rating', 0.0),
                segments=desc.get('segments')
            )
            
            logger.info(f"Description saved to database for: {os.path.basename(video_path)}")
            
        except Exception as e:
            logger.error(f"Description generation error: {e}", exc_info=True)
            raise
