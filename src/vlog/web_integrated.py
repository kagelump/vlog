"""
Integrated web application that combines the launcher and classification viewer.
"""

import sqlite3
import os
import subprocess
import threading
import queue
import time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, g
from vlog.db import get_all_metadata, get_thumbnail_by_filename, \
               update_keep_status, update_cut_duration

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# --- Flask App Initialization ---
app = Flask(__name__)
# Use environment variable for secret key, or generate a random one for development
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())
DATABASE = 'video_results.db'
VIDEO_DIR = os.getcwd()
STATIC_DIR = PROJECT_ROOT / 'static'

# --- Script Executor (for launcher functionality) ---

class ScriptExecutor:
    def __init__(self):
        self.current_process = None
        self.output_queue = queue.Queue()
        self.is_running = False
        self.current_script = None
        self.working_directory = os.getcwd()
        
    def run_script(self, script_name, args=None, working_dir=None):
        """Run a script in a separate thread and capture output"""
        if self.is_running:
            return False, "A script is already running"
        
        # Validate script name to prevent path traversal
        if not script_name or '/' in script_name or '\\' in script_name or '..' in script_name:
            return False, "Invalid script name"
        
        script_path = PROJECT_ROOT / "scripts" / script_name
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
        """Stop the currently running script"""
        if self.current_process:
            self.current_process.terminate()
            self.is_running = False
            return True, "Script stopped"
        return False, "No script is running"
    
    def get_output(self, since_timestamp=0):
        """Get output messages since a given timestamp"""
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
        """Get current execution status"""
        return {
            'is_running': self.is_running,
            'current_script': self.current_script,
            'working_directory': self.working_directory
        }

# Global executor instance
executor = ScriptExecutor()

# --- Database Connection Helper ---

def get_db_connection():
    """Initializes and returns a new database connection, stored in Flask's 'g'."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
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
    """Serves the launcher UI (new default page)"""
    return send_from_directory(STATIC_DIR / 'launcher', 'launcher.html')

@app.route('/results')
def results():
    """Serves the classification results viewer"""
    return send_from_directory(STATIC_DIR, 'index.html')

# --- Routes: Video Files ---

@app.route('/video/<filename>')
def serve_video(filename):
    """Serves a video file from the working directory."""
    return send_from_directory(VIDEO_DIR, filename)

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
        app.logger.error(f"Database error in get_metadata: {str(e)}")
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
        app.logger.error(f"Database error in get_thumbnail: {str(e)}")
        return jsonify({"success": False, "message": "Database error occurred"}), 500

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
        app.logger.error(f"Database error in update_keep_status: {str(e)}")
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
        app.logger.error(f"Database error in update_cut_duration: {str(e)}")
        return jsonify({"success": False, "message": "Database error occurred"}), 500

# --- Routes: Launcher API ---

@app.route('/api/launcher/status', methods=['GET'])
def get_launcher_status():
    """Get current launcher status"""
    return jsonify(executor.get_status())

@app.route('/api/launcher/run', methods=['POST'])
def run_script():
    """Run a script"""
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
    """Stop the currently running script"""
    success, message = executor.stop_script()
    return jsonify({'success': success, 'message': message})

@app.route('/api/launcher/output', methods=['GET'])
def get_launcher_output():
    """Get script output since a given timestamp"""
    since = float(request.args.get('since', 0))
    messages = executor.get_output(since)
    return jsonify({'messages': messages})

@app.route('/api/launcher/set-working-dir', methods=['POST'])
def set_working_dir():
    """Set the working directory"""
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
    """List available scripts"""
    scripts_dir = PROJECT_ROOT / 'scripts'
    scripts = []
    
    for script_file in scripts_dir.glob('*.sh'):
        scripts.append({
            'name': script_file.name,
            'path': str(script_file),
            'description': get_script_description(script_file)
        })
    
    return jsonify({'scripts': scripts})

def get_script_description(script_path):
    """Extract description from script comments"""
    try:
        with open(script_path, 'r') as f:
            lines = f.readlines()
            for line in lines[:10]:  # Check first 10 lines
                if line.startswith('#') and not line.startswith('#!'):
                    return line[1:].strip()
    except Exception:
        pass
    return ''

# --- Server Start ---
if __name__ == '__main__':
    # Debug mode should be disabled in production
    # Use environment variable to control debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5432)
