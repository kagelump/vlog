import sqlite3
import base64
import random
import os
import datetime # Added for the new last_updated field

# The database file path is defined here
DATABASE = 'video_results.db'

# --- Utility Functions ---

def get_conn(db_path=DATABASE):
    """Returns a raw SQLite connection object with row factory set to sqlite3.Row."""
    conn = sqlite3.connect(db_path)
    # Set row factory to easily access columns by name (dict-like access)
    conn.row_factory = sqlite3.Row 
    return conn

# --- Initialization and Mock Data ---

def initialize_db(db_path=DATABASE):
    """Ensures the database and the table exist, using the updated schema."""
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        # Updated table name to 'results' and changed PK to 'filename'
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                filename TEXT PRIMARY KEY,
                video_description_long TEXT,
                video_description_short TEXT,
                clip_type TEXT,
                last_updated TEXT,
                classification_time_seconds REAL,
                classification_model TEXT,
                video_length_seconds REAL,
                video_timestamp TEXT,
                video_thumbnail_base64 TEXT,
                clip_cut_duration REAL,
                keep INTEGER DEFAULT 1,
                in_timestamp TEXT,
                out_timestamp TEXT,
                rating REAL
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

# --- Data Retrieval Operations (Called by app.py) ---

def get_all_metadata(conn):
    """
    Retrieves all classification data EXCEPT the large base64 thumbnail.
    :param conn: An open database connection object.
    :return: A list of dictionaries (metadata).
    """
    # Updated columns and table name 'results'
    columns = [
        "filename", "video_description_long", "video_description_short", 
        "clip_type", "last_updated", "classification_time_seconds", 
        "classification_model", "video_length_seconds", "video_timestamp", 
        "clip_cut_duration", "keep", "in_timestamp", "out_timestamp", "rating"
    ]
    query = f"SELECT {', '.join(columns)} FROM results"
    
    results = conn.execute(query).fetchall()
    
    return [dict(row) for row in results]

def get_thumbnail_by_filename(conn, filename):
    """
    Retrieves only the base64 thumbnail for a specific filename.
    :param conn: An open database connection object.
    :param filename: The filename to look up.
    :return: The base64 string or None.
    """
    # Updated table name to 'results'
    result = conn.execute(
        'SELECT video_thumbnail_base64 FROM results WHERE filename = ?',
        (filename,)
    ).fetchone()
    
    if result:
        return result[0]
    return None

# --- Data Modification Operations (Called by app.py) ---

def update_keep_status(conn, filename, keep_status):
    """
    Updates the 'keep' (1=Keep, 0=Discard) status and 'last_updated' timestamp.
    :param conn: An open database connection object.
    :param filename: The file to update.
    :param keep_status: The new status (0 or 1).
    """
    current_time = datetime.datetime.now().isoformat()
    # Updated table name to 'results' and included last_updated field
    conn.execute(
        'UPDATE results SET keep = ?, last_updated = ? WHERE filename = ?',
        (keep_status, current_time, filename)
    )
    conn.commit()

def update_cut_duration(conn, filename, duration):
    """
    Updates the 'clip_cut_duration' (seconds, or None for full length) and 'last_updated' timestamp.
    :param conn: An open database connection object.
    :param filename: The file to update.
    :param duration: The new duration (float or None).
    """
    current_time = datetime.datetime.now().isoformat()
    # Updated table name to 'results' and included last_updated field
    conn.execute(
        'UPDATE results SET clip_cut_duration = ?, last_updated = ? WHERE filename = ?',
        (duration, current_time, filename)
    )
    conn.commit()

def check_if_file_exists(filename: str) -> bool:
    """
    Checks if a file with the given filename already exists in the database.
    :param filename: The filename to check.
    :return: True if the file exists, False otherwise.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM results WHERE filename = ?", (filename,))
        return cursor.fetchone() is not None
    finally:
        if conn:
            conn.close()

def insert_result(filename, video_description_long, video_description_short, 
                  clip_type, classification_time_seconds, classification_model, 
                  video_length_seconds, video_timestamp, video_thumbnail_base64, 
                  in_timestamp, out_timestamp, rating):
    """
    Inserts a new result into the database.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        current_time = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO results (
                filename, video_description_long, video_description_short, clip_type, 
                last_updated, classification_time_seconds, classification_model, 
                video_length_seconds, video_timestamp, video_thumbnail_base64,
                in_timestamp, out_timestamp, rating
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename, video_description_long, video_description_short, clip_type, 
            current_time, classification_time_seconds, classification_model, 
            video_length_seconds, video_timestamp, video_thumbnail_base64,
            in_timestamp, out_timestamp, rating
        ))
        conn.commit()
    finally:
        if conn:
            conn.close()
