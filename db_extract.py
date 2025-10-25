import sqlite3
import json
import csv
import os
import time
from pathlib import Path

# Define the database file path
DB_FILE = 'video_results.db'
# Define the output JSON and CSV file paths
JSON_FILE = 'extracted_clips.json'
CSV_FILE = 'extracted_clips.csv'


def extract_and_write_json(db_file, json_file):
    """Extracts data from the SQLite table and writes it to a JSON file."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Query the required fields (including new primary_shot_type and tags)
        cursor.execute('''
            SELECT filename, video_description_short, in_timestamp, out_timestamp,
                   video_description_long, video_length_seconds, primary_shot_type, tags
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

            # Parse tags (stored as JSON string in DB) into a Python list
            tags_raw = row_dict.get('tags')
            tags_list = []
            if tags_raw:
                try:
                    tags_list = json.loads(tags_raw)
                except Exception:
                    # Fallback: if it's a plain string, put it in a single-element list
                    tags_list = [str(tags_raw)]

            # Construct the final output object (include primary_shot_type and tags)
            output_object = {
                'full_filepath': full_filepath,
                'video_description_short': row_dict['video_description_short'],
                'in_timestamp': row_dict['in_timestamp'],
                'out_timestamp': row_dict['out_timestamp'],
                'video_description_long': row_dict['video_description_long'],
                'video_length_seconds': row_dict['video_length_seconds'],
                'primary_shot_type': row_dict.get('primary_shot_type'),
                'tags': tags_list
            }
            
            extracted_data.append(output_object)

        conn.close()

        # Write the list of dictionaries to a JSON file
        with open(json_file, 'w') as f:
            json.dump(extracted_data, f, indent=4)

        # Also write a CSV file alongside the JSON output. Tags are written as a JSON string in the CSV.
        csv_fieldnames = [
            'full_filepath', 'video_description_short', 'video_description_long',
            'in_timestamp', 'out_timestamp', 'video_length_seconds',
            'primary_shot_type', 'tags'
        ]
        try:
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvf:
                writer = csv.DictWriter(csvf, fieldnames=csv_fieldnames)
                writer.writeheader()
                for item in extracted_data:
                    row_out = {
                        'full_filepath': item.get('full_filepath'),
                        'video_description_short': item.get('video_description_short'),
                        'video_description_long': item.get('video_description_long'),
                        'in_timestamp': item.get('in_timestamp'),
                        'out_timestamp': item.get('out_timestamp'),
                        'video_length_seconds': item.get('video_length_seconds'),
                        'primary_shot_type': item.get('primary_shot_type'),
                        # store tags as a JSON string so commas are preserved
                        'tags': json.dumps(item.get('tags', []), ensure_ascii=False)
                    }
                    writer.writerow(row_out)
        except IOError as e:
            print(f"Failed to write CSV file {CSV_FILE}: {e}")

        print(f"\nSuccessfully extracted {len(extracted_data)} records to {json_file} and {CSV_FILE}")
        
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
