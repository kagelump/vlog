# Copilot Instructions for vlog

## Project Overview
This is a video logging and analysis application that uses machine learning (MLX-VLM) to automatically classify and describe video clips. The system includes:
- Video analysis using MLX-VLM (Vision Language Model)
- SQLite database for storing metadata
- Flask web server for UI and API
- HTML/JavaScript frontend for video review and editing

## Technology Stack
- **Python 3.x**: Primary programming language
- **Flask**: Web framework for API and serving frontend
- **MLX-VLM**: Vision language model for video analysis
- **OpenCV (cv2)**: Video processing and thumbnail extraction
- **SQLite3**: Database for storing video metadata
- **HTML/CSS/JavaScript**: Frontend interface

## Coding Style & Conventions

### Python Code
- Follow PEP 8 style guidelines
- Use type hints where appropriate (e.g., `-> tuple[float, str]`)
- Use descriptive variable names (snake_case for variables and functions)
- Add docstrings to all functions explaining purpose, parameters, and return values
- Keep functions focused and single-purpose
- Use context managers for resource management (database connections, video captures)

### Error Handling
- Always use try/except blocks when working with external resources (files, database, video)
- Provide informative error messages
- Log errors with descriptive context
- Release resources (video captures, database connections) in finally blocks

### Database Operations
- Use the centralized `db.py` module for all database operations
- Always use parameterized queries to prevent SQL injection
- Set `row_factory = sqlite3.Row` for dictionary-like row access
- Handle `sqlite3.Error` exceptions appropriately

## Security Guidelines

### General Security
- Never hardcode secrets, API keys, or passwords in source code
- Use environment variables for sensitive configuration
- Validate all user input before processing
- Use parameterized SQL queries to prevent SQL injection
- Set secure Flask configuration (SECRET_KEY should be random and not committed)

### Flask Security
- Set httpOnly, secure, and sameSite attributes for cookies if used
- Validate file paths to prevent directory traversal attacks
- Sanitize user input in API endpoints
- Use appropriate HTTP status codes for errors

## Dependencies & Libraries

### Required Libraries
- Use `mlx-vlm` for video analysis tasks
- Use `cv2` (OpenCV) for video processing
- Use `flask` for web server functionality
- Use `sqlite3` (built-in) for database operations
- Use `base64` for encoding thumbnails

### Adding New Dependencies
- Only add new dependencies if absolutely necessary
- Document why the dependency is needed
- Add to requirements.txt or setup.py if created
- Check for security vulnerabilities before adding

## Project-Specific Guidelines

### Video Processing
- Always release video captures with `cap.release()` after use
- Handle cases where video files cannot be opened
- Provide fallback values (e.g., BLACK_PIXEL_BASE64 for failed thumbnails)
- Use appropriate frame rate calculations for thumbnail extraction

### Database Schema
The main table (`results`) stores the following fields (in schema order):
- `filename`: Video filename (PRIMARY KEY)
- `video_description_long`: AI-generated long description
- `video_description_short`: AI-generated short description
- `primary_shot_type`: pov, insert, or establishing
- `tags`: JSON-encoded list (static, dynamic, closeup, medium, wide)
- `last_updated`: ISO format timestamp of last modification
- `classification_time_seconds`: Time taken for AI classification
- `classification_model`: Name of the model used
- `video_length_seconds`: Duration in seconds
- `video_timestamp`: ISO format timestamp of video file
- `video_thumbnail_base64`: Base64-encoded JPEG thumbnail
- `clip_cut_duration`: Optional duration for trimming
- `keep`: Boolean flag for user selection (1=keep, 0=discard, default: 1)
- `in_timestamp`: Start timestamp for clip trimming (format: "HH:MM:SS.sss")
- `out_timestamp`: End timestamp for clip trimming (format: "HH:MM:SS.sss")
- `rating`: Quality rating (0.0 to 1.0)

Note: Tags are stored as JSON strings in the database but returned as Python lists in API responses.

### API Endpoints
- Follow RESTful conventions
- Use `/api/` prefix for all API routes
- Return JSON responses with appropriate status codes
- Include error messages in JSON format: `{"success": false, "message": "..."}`
- Separate data retrieval (GET) from modification (POST)

### MLX-VLM Integration
- Use the default prompt defined in `DEAFULT_PROMPT` for consistency (note: this variable has a typo in describe.py)
- Parse JSON responses from the model
- Handle cases where model output is malformed
- Use the `third_party/mlx-vlm` submodule for model code

## Testing Requirements
- Test database operations with various inputs
- Test API endpoints for both success and error cases
- Test video processing with different video formats
- Verify error handling for missing files and invalid data
- Test Flask routes return correct status codes

## Documentation Standards
- Add clear docstrings to all functions
- Include parameter types and return types in docstrings
- Document any assumptions or limitations
- Keep README.md updated with setup instructions
- Document the database schema if modified

## File Organization
- `db.py`: All database operations (create, read, update)
- `video.py`: Video processing utilities (length, timestamp, thumbnail)
- `describe.py`: ML model integration and video analysis
- `web.py`: Flask application and API endpoints
- `index.html`: Frontend UI
- Database modules should be imported and used, not duplicated

## Common Patterns

### Database Connection in Flask
```python
def get_db_connection():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db
```

### Video Capture Pattern
```python
cap = cv2.VideoCapture(file_path)
if cap.isOpened():
    try:
        # Process video
        pass
    except Exception as e:
        # Handle error
        pass
    finally:
        cap.release()
```

### API Response Pattern
```python
try:
    # Perform operation
    return jsonify({"success": True, "message": "..."}), 200
except Exception as e:
    return jsonify({"success": False, "message": str(e)}), 500
```
