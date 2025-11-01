import sqlite3
from flask import Flask, jsonify, request, send_from_directory, g
# Import all required functions from the dedicated database module
from vlog.db import get_all_metadata, get_thumbnail_by_filename, \
               update_keep_status, update_cut_duration
import os
from pathlib import Path

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_secure_random_key_here'
DATABASE = 'video_results.db'
VIDEO_DIR = os.getcwd()
# Static directory path relative to this file's location
STATIC_DIR = Path(__file__).parent.parent.parent / 'static'

# --- Database Connection Helper (Required for Flask's context) ---

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

# --- Mock Video File Handling (for the UI video player) ---

@app.route('/video/<filename>')
def serve_video(filename):
    """Serves a video file from the mock_videos directory."""
    return send_from_directory(VIDEO_DIR, filename)

# --- API Endpoints for Data Retrieval ---

@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    """
    Returns ALL classification data EXCEPT the large base64 thumbnail.
    Delegates the data retrieval to the database library.
    """
    conn = get_db_connection()
    try:
        # Call the external database function
        metadata = get_all_metadata(conn) 
        return jsonify(metadata)
    except sqlite3.Error as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500
    
@app.route('/api/thumbnail/<filename>', methods=['GET'])
def get_thumbnail(filename):
    """
    Returns only the base64 thumbnail for a specific filename.
    Delegates the data retrieval to the database library.
    """
    conn = get_db_connection()
    try:
        # Call the external database function
        raw_base64 = get_thumbnail_by_filename(conn, filename)
        
        if raw_base64:
            return jsonify({'video_thumbnail_base64': raw_base64})
        
        return jsonify({'video_thumbnail_base64': None}), 404
        
    except sqlite3.Error as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

# --- API Endpoints for Data Modification ---

@app.route('/api/update_keep', methods=['POST'])
def handle_update_keep_status():
    """Updates the 'keep' status for a given filename by calling the DB library."""
    data = request.json
    filename = data.get('filename')
    keep_status = data.get('keep')
    
    if filename is None or keep_status is None:
        return jsonify({"success": False, "message": "Missing filename or keep status"}), 400

    conn = get_db_connection()
    try:
        # Call the external database function
        update_keep_status(conn, filename, keep_status)
        return jsonify({"success": True, "message": f"Keep status updated for {filename} to {keep_status}"})
    except sqlite3.Error as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/api/update_duration', methods=['POST'])
def handle_update_cut_duration():
    """Updates the 'clip_cut_duration' for a given filename by calling the DB library."""
    data = request.json
    filename = data.get('filename')
    duration = data.get('duration') # Can be a float or null

    if filename is None:
        return jsonify({"success": False, "message": "Missing filename"}), 400
    
    conn = get_db_connection()
    try:
        # Call the external database function
        update_cut_duration(conn, filename, duration)
        return jsonify({"success": True, "message": f"Cut duration updated for {filename} to {duration}"})
    except sqlite3.Error as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500


# --- Frontend Route ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return send_from_directory(STATIC_DIR, 'index.html')


# --- Server Start ---
if __name__ == '__main__':
    app.run(debug=True, port=5432)
