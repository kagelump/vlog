import sqlite3
import datetime
import time

class VideoDBManager:
    """Manages SQLite operations for video classification results."""

    def __init__(self, db_file="video_results.db"):
        """Initializes the database connection and ensures the table exists."""
        self.db_file = db_file
        self._initialize_db()

    def _initialize_db(self):
        """Creates the results table if it does not already exist."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                # Renamed 'video_thumbnail_url' to 'video_thumbnail_base64'
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS results (
                        filename TEXT PRIMARY KEY,
                        video_description_long TEXT,
                        video_description_short TEXT,
                        clip_type TEXT,  -- Now holds the primary clip classification (e.g., 'Main', 'B-Roll', 'Tutorial')
                        last_updated TEXT,
                        classification_time_seconds REAL,
                        classification_model TEXT,
                        video_length_seconds REAL, 
                        video_timestamp TEXT,
                        video_thumbnail_base64 TEXT -- Now stores the Base64 image string
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"Database initialization error: {e}")

    def insert_result(self, filename: str, long_desc: str, short_desc: str, 
                      clip_type: str, classification_time: float, classification_model: str,
                      video_length: float, video_timestamp: str, thumbnail_base64: str):
        """
        Inserts a new classification result or updates an existing one based on filename.
        
        Note: thumbnail_base64 must be a raw Base64 string of the image.
        """
        now = datetime.datetime.now().isoformat()
        
        # SQL now requires 10 placeholders
        sql = """
            INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        data = (
            filename,
            long_desc,
            short_desc,
            clip_type,
            now,
            classification_time,
            classification_model,
            video_length,
            video_timestamp,
            thumbnail_base64, # Updated field
        )
        
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(sql, data)
                conn.commit()
        except sqlite3.Error as e:
            print(f"Error inserting result for {filename}: {e}")

    def check_if_file_exists(self, filename: str) -> tuple | None:
        """
        Checks if a filename exists and returns the full database row (tuple) if found.
        Returns None if not found.
        """
        sql = "SELECT * FROM results WHERE filename = ?"
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row  # Ensure rows can be accessed by name
                cursor = conn.execute(sql, (filename,))
                return cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error checking file existence for {filename}: {e}")
            return None

    def fetch_all_results_for_api(self) -> list[dict]:
        """Fetches all classification results, sorted by filename, as a list of dictionaries."""
        sql = "SELECT * FROM results ORDER BY filename ASC"
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Use sqlite3.Row factory to allow fetching results as dictionaries
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql)
                # Convert list of Row objects to list of dicts for JSON serialization
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching all results: {e}")
            return []

if __name__ == '__main__':
    # NOTE: If you run this file after a previous version, you may need to manually
    # delete the 'video_results.db' file to apply the new schema changes correctly.
    db_manager = VideoDBManager()
    print("\nDatabase ready for API use.")
