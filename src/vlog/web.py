"""
Integrated web application that combines the launcher and classification viewer.
"""

import sqlite3
import os
import subprocess
import threading
import queue
import time
import logging
from pathlib import Path
from typing import Optional
from flask import Flask, jsonify, request, send_from_directory, g

from vlog.launcher_utils import browse_server_directory

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# --- Flask App Initialization ---
app = Flask(__name__)
# Use environment variable for secret key, or generate a random one for development
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())
STATIC_DIR = PROJECT_ROOT / 'static'

# Configure logging only if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default ML model for auto-ingest
DEFAULT_AUTOINGEST_MODEL = 'mlx-community/Qwen3-VL-8B-Instruct-4bit'

# Import auto-ingest service
from vlog.auto_ingest import AutoIngestService

# Global auto-ingest service instance
auto_ingest_service: Optional[AutoIngestService] = None

working_directory = os.getcwd()

# --- Routes: Main Pages ---

@app.route('/')
def index():
    """Serves the launcher UI (new default page)."""
    return send_from_directory(STATIC_DIR / 'launcher', 'launcher.html')


@app.route('/results')
def results():
    """Serves the classification results viewer."""
    return send_from_directory(STATIC_DIR, 'index.html')


# --- Routes: Video Files ---

@app.route('/video/<filename>')
def serve_video(filename):
    """Serves a video file from the working directory."""
    try:
        # Resolve and validate the requested file is inside the executor's working directory
        base_dir = Path(working_directory).resolve()
        requested_path = (base_dir / filename).resolve()

        try:
            requested_path.relative_to(base_dir)
        except ValueError:
            # Attempted path traversal or outside of working directory
            return jsonify({'success': False, 'message': 'Invalid file path'}), 400

        if not requested_path.exists() or not requested_path.is_file():
            return jsonify({'success': False, 'message': 'File not found'}), 404

        # Use send_from_directory to preserve correct headers and range requests
        return send_from_directory(str(base_dir), str(requested_path.relative_to(base_dir)))
    except Exception as e:
        logger.exception(f"Error serving video {filename}: {e}")
        return jsonify({'success': False, 'message': f'Error serving file: {str(e)}'}), 500


# --- Routes: Classification Results API ---

@app.route('/api/thumbnail-file/<filename>', methods=['GET'])
def get_thumbnail_file(filename):
    """
    Serves the thumbnail JPG file for a specific video filename.
    
    This is the preferred method for getting thumbnails (vs base64 from database).
    
    Security: This function implements defense-in-depth against path traversal:
    1. Validates filename doesn't contain path separators or '..'
    2. Uses Path.resolve() to get canonical absolute path
    3. Verifies resolved path is within the working directory
    4. Flask routing provides additional protection
    """
    try:
        # Validate filename to prevent path traversal
        # CodeQL may flag this, but we have multiple layers of protection
        if not filename or '/' in filename or '\\' in filename or '..' in filename:
            return jsonify({'success': False, 'message': 'Invalid filename'}), 400
        
        # Import here to avoid circular dependencies
        from vlog.video import get_thumbnail_path_for_video
        
        # Resolve and validate the requested file is inside the executor's working directory
        base_dir = Path(working_directory).resolve()
        
        # Construct the video path to derive the thumbnail path
        video_path = base_dir / filename
        thumbnail_path_str = get_thumbnail_path_for_video(str(video_path))
        thumbnail_path = Path(thumbnail_path_str).resolve()
        
        # Ensure the thumbnail path is within the working directory (defense in depth)
        try:
            thumbnail_path.relative_to(base_dir)
        except ValueError:
            # Attempted path traversal or outside of working directory
            logger.warning(f"Path traversal attempt blocked for filename: {filename}")
            return jsonify({'success': False, 'message': 'Invalid file path'}), 400
        
        # Check if thumbnail file exists
        if not thumbnail_path.exists() or not thumbnail_path.is_file():
            return jsonify({'success': False, 'message': 'Thumbnail not found'}), 404
        
        # Serve the thumbnail file
        return send_from_directory(str(thumbnail_path.parent), thumbnail_path.name, mimetype='image/jpeg')
        
    except Exception as e:
        logger.exception(f"Error serving thumbnail for {filename}")
        # Don't expose internal error details to the client
        return jsonify({'success': False, 'message': 'Error serving thumbnail'}), 500

# --- Routes: Launcher API ---

@app.route('/api/set-working-dir', methods=['POST'])
def set_working_dir():
    """Set the working directory."""
    # request.json can be None if the client sent no JSON body; use a safe default
    data = request.get_json() or {}
    working_dir = data.get('working_dir')
    
    if not working_dir:
        return jsonify({'success': False, 'message': 'Working directory is required'}), 400
    
    # Validate and normalize the path
    working_dir = os.path.abspath(working_dir)
    
    if not os.path.isdir(working_dir):
        return jsonify({'success': False, 'message': 'Directory does not exist'}), 400
    
    working_directory = working_dir
    return jsonify({'success': True, 'message': f'Working directory set to {working_dir}'})


@app.route('/api/browse-directory', methods=['GET'])
def browse_directory():
    """Browse directories on the server"""
    path = request.args.get('path')
    return browse_server_directory(path)


@app.route('/api/project-info', methods=['GET'])
def get_project_info():
    """
    Return project information for DaVinci Resolve integration.
    This endpoint allows davinci_clip_importer.py to discover the project path.
    """
    return jsonify({
        'project_path': str(PROJECT_ROOT),
        'database_file': DATABASE,
        'working_directory': working_directory,
        'version': '0.1.0'
    })


# --- Routes: Auto-Ingest API ---

@app.route('/api/auto-ingest/status', methods=['GET'])
def get_auto_ingest_status():
    """Get the status of the auto-ingest service."""
    if auto_ingest_service is None:
        return jsonify({
            'available': True,
            'is_running': False,
            'watch_directory': None,
            'model_name': None
        })
    
    status = auto_ingest_service.get_status()
    status['available'] = True
    return jsonify(status)


@app.route('/api/auto-ingest/start', methods=['POST'])
def start_auto_ingest():
    """Start the auto-ingest service."""
    global auto_ingest_service
    
    data = request.json or {}
    watch_dir = data.get('watch_directory') or working_directory
    model_name = data.get('model_name', DEFAULT_AUTOINGEST_MODEL)
    batch_size = data.get('batch_size', 5)
    batch_timeout = data.get('batch_timeout', 60.0)
    
    # Validate and normalize directory path
    try:
        watch_dir = os.path.abspath(watch_dir)
    except (TypeError, ValueError) as e:
        return jsonify({
            'success': False,
            'message': f'Invalid directory path: {e}'
        }), 400
    
    # Validate directory exists
    if not os.path.isdir(watch_dir):
        return jsonify({
            'success': False,
            'message': f'Directory does not exist: {watch_dir}'
        }), 400
    
    # Validate batch parameters
    try:
        batch_size = max(1, int(batch_size))
        batch_timeout = max(1.0, float(batch_timeout))
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'message': 'Invalid batch parameters: batch_size must be an integer and batch_timeout must be a number'
        }), 400
    
    # Check if service is already running
    if auto_ingest_service is not None and auto_ingest_service.is_running:
        return jsonify({
            'success': False,
            'message': 'Auto-ingest is already running'
        }), 400
    
    # Create new service (or recreate if parameters changed)
    auto_ingest_service = AutoIngestService(
        watch_dir, 
        model_name,
        batch_size=batch_size,
        batch_timeout=batch_timeout
    )
    
    success = auto_ingest_service.start()
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Auto-ingest started, monitoring: {watch_dir} (batch_size={batch_size}, timeout={batch_timeout}s)'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to start auto-ingest service'
        }), 500


@app.route('/api/auto-ingest/stop', methods=['POST'])
def stop_auto_ingest():
    """Stop the auto-ingest service."""
    global auto_ingest_service
    
    if auto_ingest_service is None or not auto_ingest_service.is_running:
        return jsonify({
            'success': False,
            'message': 'Auto-ingest is not running'
        }), 400
    
    success = auto_ingest_service.stop()
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Auto-ingest stopped'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to stop auto-ingest service'
        }), 500

# --- Server Start ---
if __name__ == '__main__':
    # Debug mode should be disabled in production
    # Use environment variable to control debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5432)
