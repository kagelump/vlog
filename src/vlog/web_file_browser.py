"""
Utility functions for the vlog launcher and web server.
"""

import os
from flask import jsonify


def browse_server_directory(path=None):
    """
    Browse directories on the server.
    
    Args:
        path: The directory path to browse. Defaults to user's home directory.
    
    Returns:
        A Flask JSON response with directory contents.
    """
    if path is None:
        path = os.path.expanduser('~')
    
    try:
        # Normalize and validate the path
        path = os.path.abspath(os.path.expanduser(path))
        
        # Security check: ensure path exists and is a directory
        if not os.path.exists(path):
            return jsonify({'success': False, 'message': 'Path does not exist'}), 400
        
        if not os.path.isdir(path):
            return jsonify({'success': False, 'message': 'Path is not a directory'}), 400
        
        # Get directory contents
        items = []
        try:
            for entry in sorted(os.listdir(path)):
                entry_path = os.path.join(path, entry)
                try:
                    is_dir = os.path.isdir(entry_path)
                    # Skip hidden files/directories starting with .
                    if entry.startswith('.'):
                        continue
                    
                    # Only include directories
                    if is_dir:
                        items.append({
                            'name': entry,
                            'path': entry_path,
                            'is_directory': is_dir
                        })
                except (PermissionError, OSError):
                    # Skip entries we can't access
                    continue
        except PermissionError:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Get parent directory
        parent = os.path.dirname(path) if path != os.path.dirname(path) else None
        
        return jsonify({
            'success': True,
            'current_path': path,
            'parent_path': parent,
            'items': items
        })
    except Exception as e:
        # Log the full error but don't expose internal details to users
        import logging
        logging.error(f"Error browsing directory {path}: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while browsing the directory'}), 500
