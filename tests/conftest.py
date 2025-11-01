"""Shared pytest fixtures and configuration."""
import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def use_temp_db(temp_db_path, monkeypatch):
    """Fixture that configures the application to use a temporary database."""
    import vlog.db as db_module
    
    # Initialize the temp database
    db_module.initialize_db(temp_db_path)
    
    # Monkey-patch the DATABASE variable
    monkeypatch.setattr(db_module, 'DATABASE', temp_db_path)
    
    # Monkey-patch get_conn to use temp_db_path as default
    original_get_conn = db_module.get_conn
    def patched_get_conn(db_path=None):
        if db_path is None:
            db_path = temp_db_path
        return original_get_conn(db_path)
    monkeypatch.setattr(db_module, 'get_conn', patched_get_conn)
    
    return temp_db_path
