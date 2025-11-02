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

# Import all required functions from the dedicated database module
from vlog.db import get_all_metadata, get_thumbnail_by_filename, \
               update_keep_status, update_cut_duration

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# --- Flask App Initialization ---
app = Flask(__name__)
# Use environment variable for secret key, or generate a random one for development
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())
DATABASE = 'video_results.db'
STATIC_DIR = PROJECT_ROOT / 'static'

# Configure logging only if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default ML model for auto-ingest
DEFAULT_AUTOINGEST_MODEL = 'mlx-community/Qwen3-VL-8B-Instruct-4bit'

# Import auto-ingest service
try:
    from vlog.auto_ingest import AutoIngestService
    AUTO_INGEST_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Auto-ingest not available: {e}")
    AUTO_INGEST_AVAILABLE = False
    AutoIngestService = None

# --- Script Executor (for launcher functionality) ---

class ScriptExecutor:
    """Executes shell scripts in a separate thread and captures output."""
    
    def __init__(self):
        self.current_process = None
        self.output_queue = queue.Queue()
        self.is_running = False
        self.current_script = None
        self.working_directory = os.getcwd()
        
    def run_script(self, script_name, args=None, working_dir=None):
        """Run a script in a separate thread and capture output."""
        if self.is_running:
            return False, "A script is already running"
        
        # Validate script name to prevent path traversal
        if not script_name or '/' in script_name or '\\' in script_name or '..' in script_name:
            return False, "Invalid script name"
        
        # Construct script path and ensure it's within the scripts directory
        script_path = (PROJECT_ROOT / "scripts" / script_name).resolve()
        scripts_dir = (PROJECT_ROOT / "scripts").resolve()
        
        # Verify the resolved path is actually within the scripts directory
        try:
            script_path.relative_to(scripts_dir)
        except ValueError:
            return False, "Invalid script path"
        
        if not script_path.exists() or not script_path.is_file():
            return False, f"Script {script_name} not found"
        
        # Validate working directory to prevent path traversal
        if working_dir:
            working_dir = os.path.abspath(working_dir)
            if not os.path.isdir(working_dir):
                return False, "Invalid working directory"
            self.working_directory = working_dir
        
        self.current_script = script_name
        self.is_running = True
        self.output_queue = queue.Queue()  # Clear queue
        
        def run_process():
            try:
                env = os.environ.copy()
                env['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
                
                cmd = [str(script_path)]
                if args:
                    cmd.extend(args)
                
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=self.working_directory,
                    env=env
                )
                
                for line in iter(self.current_process.stdout.readline, ''):
                    if line:
                        self.output_queue.put({
                            'type': 'output',
                            'data': line.rstrip(),
                            'timestamp': time.time()
                        })
                
                self.current_process.wait()
                exit_code = self.current_process.returncode
                
                self.output_queue.put({
                    'type': 'complete',
                    'exit_code': exit_code,
                    'timestamp': time.time()
                })
                
            except Exception as e:
                logger.error(f"Error running script {script_name}: {str(e)}")
                self.output_queue.put({
                    'type': 'error',
                    'data': str(e),
                    'timestamp': time.time()
                })
            finally:
                self.is_running = False
                self.current_process = None
        
        thread = threading.Thread(target=run_process, daemon=True)
        thread.start()
        
        return True, f"Started {script_name}"
    
    def stop_script(self):
        """Stop the currently running script."""
        if self.current_process:
            self.current_process.terminate()
            self.is_running = False
            return True, "Script stopped"
        return False, "No script is running"
    
    def get_output(self, since_timestamp=0):
        """Get output messages since a given timestamp."""
        messages = []
        temp_queue = queue.Queue()
        
        while not self.output_queue.empty():
            try:
                msg = self.output_queue.get_nowait()
                if msg['timestamp'] > since_timestamp:
                    messages.append(msg)
                temp_queue.put(msg)
            except queue.Empty:
                break
        
        # Put messages back in queue
        while not temp_queue.empty():
            try:
                self.output_queue.put(temp_queue.get_nowait())
            except queue.Empty:
                break
        
        return messages
    
    def get_status(self):
        """Get current execution status."""
        return {
            'is_running': self.is_running,
            'current_script': self.current_script,
            'working_directory': self.working_directory
        }


# Global executor instance
executor = ScriptExecutor()

# Global auto-ingest service instance
auto_ingest_service: Optional[AutoIngestService] = None


# --- Database Connection Helper ---

def get_db_connection():
    """Initializes and returns a new database connection, stored in Flask's 'g'."""
    db = getattr(g, '_database', None)
    if db is None:
        # Open the database file relative to the executor's working directory
        # so that the launcher can switch which DB is active by changing
        # ScriptExecutor.working_directory.
        try:
            db_path = (Path(executor.working_directory) / DATABASE).resolve()
        except Exception:
            # Fallback to the configured DATABASE name in case of any error.
            db_path = Path(DATABASE).resolve()

        db = g._database = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection when the app context is torn down."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

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
        base_dir = Path(executor.working_directory).resolve()
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

@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    """
    Returns ALL classification data EXCEPT the large base64 thumbnail.
    """
    conn = get_db_connection()
    try:
        metadata = get_all_metadata(conn) 
        return jsonify(metadata)
    except sqlite3.Error as e:
        logger.error(f"Database error in get_metadata: {str(e)}")
        return jsonify({"success": False, "message": "Database error occurred"}), 500
    
@app.route('/api/thumbnail/<filename>', methods=['GET'])
def get_thumbnail(filename):
    """
    Returns only the base64 thumbnail for a specific filename.
    """
    conn = get_db_connection()
    try:
        raw_base64 = get_thumbnail_by_filename(conn, filename)
        
        if raw_base64:
            return jsonify({'video_thumbnail_base64': raw_base64})
        
        return jsonify({'video_thumbnail_base64': None}), 404
        
    except sqlite3.Error as e:
        logger.error(f"Database error in get_thumbnail: {str(e)}")
        return jsonify({"success": False, "message": "Database error occurred"}), 500


# --- Routes: Data Modification ---

@app.route('/api/update_keep', methods=['POST'])
def handle_update_keep_status():
    """Updates the 'keep' status for a given filename."""
    data = request.json
    filename = data.get('filename')
    keep_status = data.get('keep')
    
    if filename is None or keep_status is None:
        return jsonify({"success": False, "message": "Missing filename or keep status"}), 400

    conn = get_db_connection()
    try:
        update_keep_status(conn, filename, keep_status)
        return jsonify({"success": True, "message": f"Keep status updated for {filename} to {keep_status}"})
    except sqlite3.Error as e:
        logger.error(f"Database error in update_keep_status: {str(e)}")
        return jsonify({"success": False, "message": "Database error occurred"}), 500

@app.route('/api/update_duration', methods=['POST'])
def handle_update_cut_duration():
    """Updates the 'clip_cut_duration' for a given filename."""
    data = request.json
    filename = data.get('filename')
    duration = data.get('duration')

    if filename is None:
        return jsonify({"success": False, "message": "Missing filename"}), 400
    
    conn = get_db_connection()
    try:
        update_cut_duration(conn, filename, duration)
        return jsonify({"success": True, "message": f"Cut duration updated for {filename} to {duration}"})
    except sqlite3.Error as e:
        logger.error(f"Database error in update_cut_duration: {str(e)}")
        return jsonify({"success": False, "message": "Database error occurred"}), 500


# --- Routes: Launcher API ---

@app.route('/api/launcher/status', methods=['GET'])
def get_launcher_status():
    """Get current launcher status."""
    return jsonify(executor.get_status())


@app.route('/api/launcher/run', methods=['POST'])
def run_script():
    """Run a script."""
    data = request.json
    script_name = data.get('script')
    args = data.get('args', [])
    working_dir = data.get('working_dir')
    
    if not script_name:
        return jsonify({'success': False, 'message': 'Script name is required'}), 400
    
    success, message = executor.run_script(script_name, args, working_dir)
    return jsonify({'success': success, 'message': message})


@app.route('/api/launcher/stop', methods=['POST'])
def stop_script():
    """Stop the currently running script."""
    success, message = executor.stop_script()
    return jsonify({'success': success, 'message': message})


@app.route('/api/launcher/output', methods=['GET'])
def get_launcher_output():
    """Get script output since a given timestamp."""
    since = float(request.args.get('since', 0))
    messages = executor.get_output(since)
    return jsonify({'messages': messages})


@app.route('/api/launcher/set-working-dir', methods=['POST'])
def set_working_dir():
    """Set the working directory."""
    data = request.json
    working_dir = data.get('working_dir')
    
    if not working_dir:
        return jsonify({'success': False, 'message': 'Working directory is required'}), 400
    
    # Validate and normalize the path
    working_dir = os.path.abspath(working_dir)
    
    if not os.path.isdir(working_dir):
        return jsonify({'success': False, 'message': 'Directory does not exist'}), 400
    
    executor.working_directory = working_dir
    return jsonify({'success': True, 'message': f'Working directory set to {working_dir}'})


@app.route('/api/launcher/scripts', methods=['GET'])
def list_scripts():
    """List available scripts."""
    scripts_dir = PROJECT_ROOT / 'scripts'
    scripts = []
    
    for script_file in scripts_dir.glob('*.sh'):
        scripts.append({
            'name': script_file.name,
            'path': str(script_file),
            'description': get_script_description(script_file)
        })
    
    return jsonify({'scripts': scripts})


@app.route('/api/project-info', methods=['GET'])
def get_project_info():
    """
    Return project information for DaVinci Resolve integration.
    This endpoint allows davinci_clip_importer.py to discover the project path.
    """
    return jsonify({
        'project_path': str(PROJECT_ROOT),
        'database_file': DATABASE,
        'working_directory': executor.working_directory if executor else os.getcwd(),
        'version': '0.1.0'
    })


# --- Routes: Auto-Ingest API ---

@app.route('/api/auto-ingest/status', methods=['GET'])
def get_auto_ingest_status():
    """Get the status of the auto-ingest service."""
    if not AUTO_INGEST_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Auto-ingest feature not available (missing dependencies)'
        }), 503
    
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
    
    if not AUTO_INGEST_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Auto-ingest feature not available (missing dependencies)'
        }), 503
    
    data = request.json or {}
    watch_dir = data.get('watch_directory') or executor.working_directory
    model_name = data.get('model_name', DEFAULT_AUTOINGEST_MODEL)
    
    # Validate directory
    if not os.path.isdir(watch_dir):
        return jsonify({
            'success': False,
            'message': f'Directory does not exist: {watch_dir}'
        }), 400
    
    # Check if service is already running
    if auto_ingest_service is not None and auto_ingest_service.is_running:
        return jsonify({
            'success': False,
            'message': 'Auto-ingest is already running'
        }), 400
    
    # Create new service (or recreate if parameters changed)
    auto_ingest_service = AutoIngestService(watch_dir, model_name)
    
    success = auto_ingest_service.start()
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Auto-ingest started, monitoring: {watch_dir}'
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
    
    if not AUTO_INGEST_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Auto-ingest feature not available'
        }), 503
    
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


def get_script_description(script_path):
    """Extract description from script comments."""
    try:
        with open(script_path, 'r') as f:
            lines = f.readlines()
            for line in lines[:10]:  # Check first 10 lines
                if line.startswith('#') and not line.startswith('#!'):
                    return line[1:].strip()
    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
        logger.error(f"Error reading script description from {script_path}: {str(e)}")
    return ''


# --- Server Start ---
if __name__ == '__main__':
    # Debug mode should be disabled in production
    # Use environment variable to control debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5432)
