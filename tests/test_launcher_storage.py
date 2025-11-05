"""Tests for localStorage integration in launcher UI."""
import re
from pathlib import Path
import pytest


# Constants
LAUNCHER_HTML_PATH = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"


@pytest.fixture
def launcher_html_content():
    """Fixture that provides the launcher HTML content."""
    return LAUNCHER_HTML_PATH.read_text()


def test_launcher_html_has_localstorage_key(launcher_html_content):
    """Test that launcher.html defines a localStorage key constant."""
    # Check for localStorage key constant
    assert "WORKING_DIR_STORAGE_KEY" in launcher_html_content
    assert "'vlog_working_directory'" in launcher_html_content or '"vlog_working_directory"' in launcher_html_content


def test_launcher_html_has_save_function(launcher_html_content):
    """Test that launcher.html has a function to save working directory to localStorage."""
    # Check for save function
    assert "saveWorkingDirToStorage" in launcher_html_content
    assert "localStorage.setItem" in launcher_html_content


def test_launcher_html_has_load_function(launcher_html_content):
    """Test that launcher.html has a function to load working directory from localStorage."""
    # Check for load function
    assert "loadWorkingDirFromStorage" in launcher_html_content
    assert "localStorage.getItem" in launcher_html_content


def test_launcher_html_calls_save_on_set_directory(launcher_html_content):
    """Test that saveWorkingDirToStorage is called when setting directory."""
    # Look for the pattern where saveWorkingDirToStorage is called after successful set
    # This is a simpler and more reliable check
    pattern = r'async function setWorkingDirectory\(\).*?saveWorkingDirToStorage'
    
    assert re.search(pattern, launcher_html_content, re.DOTALL), \
        "saveWorkingDirToStorage should be called in setWorkingDirectory function"


def test_launcher_html_calls_save_on_select_directory(launcher_html_content):
    """Test that saveWorkingDirToStorage is called when selecting directory from browser."""
    # Look for the pattern where saveWorkingDirToStorage is called after successful select
    pattern = r'async function selectCurrentDirectory\(\).*?saveWorkingDirToStorage'
    
    assert re.search(pattern, launcher_html_content, re.DOTALL), \
        "saveWorkingDirToStorage should be called in selectCurrentDirectory function"


def test_launcher_html_loads_from_storage_on_init(launcher_html_content):
    """Test that working directory is loaded from localStorage on initialization."""
    # Find the init function
    init_match = re.search(
        r'async function init\(\).*?^\s*}',
        launcher_html_content,
        re.MULTILINE | re.DOTALL
    )
    
    assert init_match, "init function not found"
    init_content = init_match.group(0)
    
    # Should call loadWorkingDirFromStorage on initialization
    assert "loadWorkingDirFromStorage" in init_content


def test_launcher_html_has_error_handling(launcher_html_content):
    """Test that localStorage operations have error handling."""
    # Check for error handling in save function
    save_pattern = r'function saveWorkingDirToStorage.*?try.*?catch'
    assert re.search(save_pattern, launcher_html_content, re.DOTALL), \
        "saveWorkingDirToStorage should have try-catch error handling"
    
    # Check for error handling in load function
    load_pattern = r'function loadWorkingDirFromStorage.*?try.*?catch'
    assert re.search(load_pattern, launcher_html_content, re.DOTALL), \
        "loadWorkingDirFromStorage should have try-catch error handling"

