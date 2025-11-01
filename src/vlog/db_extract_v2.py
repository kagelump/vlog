import sqlite3
import json
import csv
import os
import re
import time
from pathlib import Path

# New, safer extractor with optional rename behavior.
DB_FILE = 'video_results.db'
JSON_FILE = 'extracted_clips.json'
CSV_FILE = 'extracted_clips.csv'


def sanitize_for_filename(s: str) -> str:
    if not s:
        return ''
    s = str(s).strip()
    s = s.replace(' ', '_')
    return re.sub(r'[^A-Za-z0-9._-]', '_', s)


def extract_and_write_json(db_file, json_file, csv_file=CSV_FILE, rename_files=False):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT filename, video_description_short, in_timestamp, out_timestamp,
                   video_description_long, video_length_seconds, primary_shot_type, tags
            FROM results
        ''')

        rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description]

        cwd = Path.cwd()
        extracted = []

        for row in rows:
            rd = dict(zip(col_names, row))
            orig_fn = rd['filename']
            full_path = cwd / orig_fn

            tags_raw = rd.get('tags')
            tags = []
            if tags_raw:
                try:
                    tags = json.loads(tags_raw)
                except Exception:
                    tags = [str(tags_raw)]

            primary = rd.get('primary_shot_type')

            out = {
                'full_filepath': str(full_path),
                'video_description_short': rd.get('video_description_short'),
                'in_timestamp': rd.get('in_timestamp'),
                'out_timestamp': rd.get('out_timestamp'),
                'video_description_long': rd.get('video_description_long'),
                'video_length_seconds': rd.get('video_length_seconds'),
                'primary_shot_type': primary,
                'tags': tags,
            }

            if rename_files and full_path.exists():
                primary_safe = sanitize_for_filename(primary) if primary else ''
                tags_safe = '_'.join([sanitize_for_filename(t) for t in tags if t])
                parts = [full_path.stem]
                if primary_safe:
                    parts.append(primary_safe)
                if tags_safe:
                    parts.append(tags_safe)
                new_name = '_'.join([p for p in parts if p]) + full_path.suffix
                new_path = full_path.with_name(new_name)

                counter = 1
                candidate = new_path
                while candidate.exists():
                    candidate = new_path.with_name(new_path.stem + f"_{counter}" + new_path.suffix)
                    counter += 1
                new_path = candidate

                try:
                    os.rename(full_path, new_path)
                    out['full_filepath'] = str(new_path)
                    print(f"Renamed: {full_path.name} -> {new_path.name}")
                except Exception as e:
                    print(f"Failed to rename {full_path}: {e}")

            extracted.append(out)

        # write json
        with open(json_file, 'w', encoding='utf-8') as jf:
            json.dump(extracted, jf, indent=2, ensure_ascii=False)

        # write csv
        fieldnames = [
            'full_filepath', 'video_description_short', 'video_description_long',
            'in_timestamp', 'out_timestamp', 'video_length_seconds', 'primary_shot_type', 'tags'
        ]
        with open(csv_file, 'w', newline='', encoding='utf-8') as cf:
            writer = csv.DictWriter(cf, fieldnames=fieldnames)
            writer.writeheader()
            for item in extracted:
                writer.writerow({
                    'full_filepath': item.get('full_filepath'),
                    'video_description_short': item.get('video_description_short'),
                    'video_description_long': item.get('video_description_long'),
                    'in_timestamp': item.get('in_timestamp'),
                    'out_timestamp': item.get('out_timestamp'),
                    'video_length_seconds': item.get('video_length_seconds'),
                    'primary_shot_type': item.get('primary_shot_type'),
                    'tags': json.dumps(item.get('tags', []), ensure_ascii=False),
                })

        print(f"\nWrote {len(extracted)} records to {json_file} and {csv_file}")

    except sqlite3.Error as e:
        print(f"DB error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=DB_FILE)
    parser.add_argument('--json', default=JSON_FILE)
    parser.add_argument('--csv', default=CSV_FILE)
    parser.add_argument('--rename', action='store_true')
    args = parser.parse_args()

    extract_and_write_json(args.db, args.json, csv_file=args.csv, rename_files=args.rename)
