from db import VideoDBManager
from flask import Flask, render_template_string, jsonify, request, send_from_directory


import os
import time

# Initialize Flask application
app = Flask(__name__)
# Initialize the database manager
db_manager = VideoDBManager()

# Simulate a delay to demonstrate the auto-update feature 
# (Remove this in a real high-performance app)
@app.before_request
def simulate_work():
    """Simulate some processing time if needed, especially when testing auto-updates."""
    # time.sleep(0.1) # Uncomment if you want to test loading indicators

@app.route('/')
def index():
    """
    Serves the main HTML page.
    Note: In a real Flask app, you'd use render_template('index.html'), 
    but here we serve the content directly for a single-file environment.
    """
    # Determine the absolute path to the index.html file to ensure it's found
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, 'index.html')
    
    with open(html_path, 'r') as f:
        html_content = f.read()
    return html_content

@app.route('/video/<filename>', methods=['GET'])
def stream_video(filename):
    """
    Streams the requested video file from the VIDEO_DIR (current working directory).
    The browser handles the 'Accept-Ranges' and 'Range' headers 
    for seeking, which Flask's send_from_directory handles automatically.
    """
    if not filename:
        return "Video filename missing", 400
    
    # Securely serve the file from the specified directory
    try:
        # Use os.getcwd() as the path to serve from
        return send_from_directory(
            os.getcwd(), 
            filename, 
            as_attachment=False, 
            mimetype='video/mp4' # Best guess, adjust if using other formats
        )
    except FileNotFoundError:
        return f"Video file '{filename}' not found on server.", 404

@app.route('/api/results', methods=['GET'])
def get_results():
    """
    API endpoint to retrieve all classification results from the database.
    Returns data as JSON, which is consumed by the frontend.
    """
    try:
        results = db_manager.fetch_all_results_for_api()
        for result in results:
            result['video_filename'] = result['filename']
        # jsonify handles converting the list of dictionaries into a JSON response
        return jsonify(results)
    except Exception as e:
        print(f"Error fetching results for API: {e}")
        return jsonify({"error": "Could not retrieve data."}), 500

# To run the server: python app.py
if __name__ == '__main__':
    app.run(debug=True, port=5432)
