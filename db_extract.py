import sqlite3
import json
import os
import time
from pathlib import Path

# Define the database file path
DB_FILE = 'video_results.db'
# Define the output JSON file path
JSON_FILE = 'extracted_clips.json'


def extract_and_write_json(db_file, json_file):
    """Extracts data from the SQLite table and writes it to a JSON file."""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query the required fields
        cursor.execute('''
            SELECT filename, video_description_short, in_timestamp, out_timestamp,
                   video_description_long, video_length_seconds
            FROM results
        ''')
        
        # Fetch all results
        rows = cursor.fetchall()
        
        # Get column names for mapping
        col_names = [description[0] for description in cursor.description]
        
        # Determine the current working directory for path resolution
        current_dir = Path.cwd()
        
        extracted_data = []
        
        # Process each row
        for row in rows:
            # Create a dictionary from the row values and column names
            row_dict = dict(zip(col_names, row))
            
            # 1. Resolve filename to the full absolute path
            original_filename = row_dict['filename']
            full_filepath = str(current_dir / original_filename)
            
            # Construct the final output object
            output_object = {
                'full_filepath': full_filepath,
                'video_description_short': row_dict['video_description_short'],
                'in_timestamp': row_dict['in_timestamp'],
                'out_timestamp': row_dict['out_timestamp'],
                'video_description_long': row_dict['video_description_long'],
                'video_length_seconds': row_dict['video_length_seconds']
            }
            
            extracted_data.append(output_object)

        conn.close()

        # Write the list of dictionaries to a JSON file
        with open(json_file, 'w') as f:
            json.dump(extracted_data, f, indent=4)
        
        print(f"\nSuccessfully extracted {len(extracted_data)} records to {json_file}")
        
    except sqlite3.Error as e:
        print(f"Database error occurred: {e}")
    except IOError as e:
        print(f"File writing error occurred: {e}")
    finally:
        # Clean up the database connection if still open (optional, but good practice)
        if conn:
            conn.close()


if __name__ == '__main__':
    extract_and_write_json(DB_FILE, JSON_FILE)
