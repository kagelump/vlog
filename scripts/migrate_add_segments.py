#!/usr/bin/env python3
"""
Migration script to add 'segments' column to existing vlog databases.

This script adds the new 'segments' column to the results table if it doesn't exist.
The column stores a JSON array of segment objects for supporting multiple in/out points.

Usage:
    python scripts/migrate_add_segments.py [database_path]

If no database path is provided, it will use 'video_results.db' in the current directory.
"""

import sqlite3
import sys
import os


def migrate_database(db_path):
    """Add segments column to database if it doesn't exist."""
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if segments column already exists
        cursor.execute("PRAGMA table_info(results)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'segments' in columns:
            print(f"Database already has 'segments' column: {db_path}")
            conn.close()
            return True
        
        # Add segments column
        print(f"Adding 'segments' column to database: {db_path}")
        cursor.execute("ALTER TABLE results ADD COLUMN segments TEXT")
        conn.commit()
        
        print("Migration complete!")
        print("The 'segments' column has been added to the results table.")
        print("Existing records will have NULL for this column (backwards compatible).")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "video_results.db"
    
    print("=" * 60)
    print("vlog Database Migration: Add 'segments' Column")
    print("=" * 60)
    print(f"Target database: {os.path.abspath(db_path)}")
    print()
    
    success = migrate_database(db_path)
    
    if success:
        print("\nMigration successful!")
        return 0
    else:
        print("\nMigration failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
