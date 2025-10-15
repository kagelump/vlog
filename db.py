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
                keep INTEGER DEFAULT 1
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

def insert_mock_data(db_path=DATABASE):
    """Inserts mock data into the results table if it doesn't already exist."""
    
    video_dir = 'mock_videos'
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)

    mock_thumbnail = base64.b64encode(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90\x77\x53\xDE\x00\x00\x00\x0cIDATx\xDAc`\x00\x00\x00\x02\x00\x01\xE2\x21\xBC\x33\x00\x00\x00\x00IEND\xAEB`\x82').decode('utf-8')
    current_iso_time = datetime.datetime.now().isoformat()

    mock_entries = [
        {
            "filename": f"clip_A_{i}.mp4",
            "timestamp": f"2024-10-15 10:{str(10 + i * 2).zfill(2)}:00",
            "length": 15.5 + random.random() * 5,
            "clip_type": random.choice(["Main Action", "B-Roll", "Scenic"]),
            "description_short": f"Mock event {i} at Location X",
            "description_long": f"Detailed description of mock event {i}. This clip contains the main action shot from a single camera angle.",
            "thumbnail": mock_thumbnail,
            "last_updated": current_iso_time,
        } for i in range(10)
    ]
    
    mock_entries.extend([
        {
            "filename": f"tutorial_B_{i}.mp4",
            "timestamp": f"2024-10-15 11:{str(50 + i).zfill(2)}:00",
            "length": 60.0,
            "clip_type": "Tutorial",
            "description_short": f"Software tutorial section {i}",
            "description_long": "Screen recording for a software tutorial. Needs precise cutting.",
            "thumbnail": mock_thumbnail,
            "keep": 0, # Discard by default
            "cut_duration": random.choice([4.2, 8.5]),
            "last_updated": current_iso_time,
        } for i in range(3)
    ])

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        
        for entry in mock_entries:
            # Create a dummy video file
            with open(os.path.join(video_dir, entry['filename']), 'w') as f:
                f.write(f"This is a placeholder for video file {entry['filename']}")
                
            # Updated to match the new schema and table name 'results'
            cursor.execute('''
                INSERT OR IGNORE INTO results 
                (filename, video_description_long, video_description_short, clip_type, 
                 last_updated, classification_time_seconds, classification_model, 
                 video_length_seconds, video_timestamp, video_thumbnail_base64, 
                 clip_cut_duration, keep)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry['filename'],
                entry['description_long'],
                entry['description_short'],
                entry['clip_type'],
                entry['last_updated'], # New field value
                round(entry['length'] / 10 + random.random() * 0.5, 3), 
                random.choice(["Model_V1.2", "Model_V2.1"]),
                entry['length'],
                entry['timestamp'],
                entry['thumbnail'],
                entry.get('cut_duration', None),
                entry.get('keep', 1)
            ))
        conn.commit()
    except sqlite3.IntegrityError:
        pass 
    except sqlite3.Error as e:
        print(f"Database error during mock data insertion: {e}")
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
        "clip_cut_duration", "keep"
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
