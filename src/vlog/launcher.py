"""
UI Launcher for video ingestion workflow scripts.
Provides a web interface to run scripts, track progress, and configure settings.
"""

import os
import subprocess
import threading
import queue
import time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, g
from werkzeug.utils import secure_filename

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Global state for tracking script execution
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
        
        script_path = PROJECT_ROOT / "scripts" / script_name
        if not script_path.exists():
            return False, f"Script {script_name} not found"
        
        if working_dir:
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

def create_launcher_app():
    """Create and configure the launcher Flask app"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'launcher_secret_key_change_me'
    
    LAUNCHER_STATIC_DIR = PROJECT_ROOT / 'static' / 'launcher'
    
    @app.route('/')
    def index():
        """Serve the launcher UI"""
        return send_from_directory(LAUNCHER_STATIC_DIR, 'launcher.html')
    
    @app.route('/api/launcher/status', methods=['GET'])
    def get_status():
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
    def get_output():
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
    
    return app

if __name__ == '__main__':
    app = create_launcher_app()
    app.run(debug=True, port=5433)
