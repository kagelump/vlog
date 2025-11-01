import sqlite3
import json
import csv
import os
import re
import time
from pathlib import Path
# Define the database file path
DB_FILE = 'video_results.db'
# Define the output JSON and CSV file paths
JSON_FILE = 'extracted_clips.json'
CSV_FILE = 'extracted_clips.csv'

def extract_and_write_json(db_file, json_file, rename_files=False):
    """Extracts data from the SQLite table and writes it to a JSON file.

    If rename_files is True, attempts to rename files in the current working
    directory by appending the primary shot type and tags to the filename.
    """
    conn = None
import sqlite3
import json
import csv
import os
import re
import time
from pathlib import Path
DB_FILE = 'video_results.db'
JSON_FILE = 'extracted_clips.json'
CSV_FILE = 'extracted_clips.csv'
import csv
import os
import re
import time
from pathlib import Path

# Define the database file path
DB_FILE = 'video_results.db'
# Define the output JSON and CSV file paths
JSON_FILE = 'extracted_clips.json'
CSV_FILE = 'extracted_clips.csv'


def extract_and_write_json(db_file, json_file, rename_files=False):
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

        def sanitize_for_filename(s: str) -> str:
            """Return a filesystem-safe string for use in filenames."""
            if not s:
                return ''
            # Lowercase, strip, replace spaces and invalid chars with underscore
            s = str(s).strip()
            s = s.replace(' ', '_')
            # Allow alphanumerics, dot, dash and underscore
            return re.sub(r'[^A-Za-z0-9._-]', '_', s)
        
        import sqlite3
        import json
        import csv
        import os
        import re
        import time
        from pathlib import Path

        # Define the database file path
        DB_FILE = 'video_results.db'
        # Define the output JSON and CSV file paths
        JSON_FILE = 'extracted_clips.json'
        CSV_FILE = 'extracted_clips.csv'


        def extract_and_write_json(db_file, json_file, rename_files=False):
            """Extracts data from the SQLite table and writes it to a JSON file.

            If rename_files is True, attempts to rename files in the current working
            directory by appending the primary shot type and tags to the filename.
            """
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

                def sanitize_for_filename(s: str) -> str:
                    """Return a filesystem-safe string for use in filenames."""
                    if not s:
                        return ''
                    s = str(s).strip()
                    s = s.replace(' ', '_')
                    # Allow alphanumerics, dot, dash and underscore
                    return re.sub(r'[^A-Za-z0-9._-]', '_', s)

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
                    primary = row_dict.get('primary_shot_type')
                    output_object = {
                        'full_filepath': full_filepath,
                        'video_description_short': row_dict['video_description_short'],
                        'in_timestamp': row_dict['in_timestamp'],
                        'out_timestamp': row_dict['out_timestamp'],
                        'video_description_long': row_dict['video_description_long'],
                        'video_length_seconds': row_dict['video_length_seconds'],
                        'primary_shot_type': primary,
                        'tags': tags_list
                    }

                    # Optionally rename the file to include primary shot type and tags
                    if rename_files:
                        try:
                            orig_path = Path(full_filepath)
                            if orig_path.exists():
                                stem = orig_path.stem  # filename without suffix
                                suffix = orig_path.suffix  # includes the dot

                                primary_safe = sanitize_for_filename(primary) if primary else ''
                                tags_safe = '_'.join([sanitize_for_filename(t) for t in tags_list if t])

                                parts = [stem]
                                if primary_safe:
                                    parts.append(primary_safe)
                                if tags_safe:
                                    parts.append(tags_safe)

                                new_name = '_'.join([p for p in parts if p]) + suffix
                                new_path = orig_path.with_name(new_name)

                                # If target exists, avoid clobbering: append a numeric suffix
                                counter = 1
                                candidate = new_path
                                while candidate.exists():
                                    candidate = new_path.with_name(new_path.stem + f"_{counter}" + new_path.suffix)
                                    counter += 1
                                new_path = candidate

                                os.rename(orig_path, new_path)
                                output_object['full_filepath'] = str(new_path)
                                print(f"Renamed: {orig_path.name} -> {new_path.name}")
                            else:
                                # File not found in cwd; leave full_filepath as-is
                                print(f"Warning: file not found, cannot rename: {full_filepath}")
                        except Exception as e:
                            print(f"Failed to rename {full_filepath}: {e}")

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
            import argparse

            parser = argparse.ArgumentParser(description='Extract results from SQLite DB to JSON/CSV')
            parser.add_argument('--db', type=str, default=DB_FILE, help='Path to sqlite DB file')
            parser.add_argument('--json', type=str, default=JSON_FILE, help='Output JSON file')
            parser.add_argument('--csv', type=str, default=CSV_FILE, help='Output CSV file (ignored if not writing)')
            parser.add_argument('--rename', action='store_true', help='Rename source video files to include primary_shot_type and tags')
            args = parser.parse_args()

            # Update global CSV_FILE constant if user provided custom CSV path
            CSV_FILE = args.csv

            extract_and_write_json(args.db, args.json, rename_files=args.rename)

