"""Tests for localStorage integration in launcher UI."""
import re
from pathlib import Path


def test_launcher_html_has_localstorage_key():
    """Test that launcher.html defines a localStorage key constant."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Check for localStorage key constant
    assert "WORKING_DIR_STORAGE_KEY" in content
    assert "'vlog_working_directory'" in content or '"vlog_working_directory"' in content


def test_launcher_html_has_save_function():
    """Test that launcher.html has a function to save working directory to localStorage."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Check for save function
    assert "saveWorkingDirToStorage" in content
    assert "localStorage.setItem" in content


def test_launcher_html_has_load_function():
    """Test that launcher.html has a function to load working directory from localStorage."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Check for load function
    assert "loadWorkingDirFromStorage" in content
    assert "localStorage.getItem" in content


def test_launcher_html_calls_save_on_set_directory():
    """Test that saveWorkingDirToStorage is called when setting directory."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Look for the pattern where saveWorkingDirToStorage is called after successful set
    # This is a simpler and more reliable check
    pattern = r'async function setWorkingDirectory\(\).*?saveWorkingDirToStorage'
    
    assert re.search(pattern, content, re.DOTALL), \
        "saveWorkingDirToStorage should be called in setWorkingDirectory function"


def test_launcher_html_calls_save_on_select_directory():
    """Test that saveWorkingDirToStorage is called when selecting directory from browser."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Look for the pattern where saveWorkingDirToStorage is called after successful select
    pattern = r'async function selectCurrentDirectory\(\).*?saveWorkingDirToStorage'
    
    assert re.search(pattern, content, re.DOTALL), \
        "saveWorkingDirToStorage should be called in selectCurrentDirectory function"


def test_launcher_html_loads_from_storage_on_init():
    """Test that working directory is loaded from localStorage on initialization."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Find the init function
    init_match = re.search(
        r'async function init\(\).*?^\s*}',
        content,
        re.MULTILINE | re.DOTALL
    )
    
    assert init_match, "init function not found"
    init_content = init_match.group(0)
    
    # Should call loadWorkingDirFromStorage on initialization
    assert "loadWorkingDirFromStorage" in init_content


def test_launcher_html_has_error_handling():
    """Test that localStorage operations have error handling."""
    launcher_html = Path(__file__).parent.parent / "static" / "launcher" / "launcher.html"
    content = launcher_html.read_text()
    
    # Check for error handling in save function
    save_pattern = r'function saveWorkingDirToStorage.*?try.*?catch'
    assert re.search(save_pattern, content, re.DOTALL), \
        "saveWorkingDirToStorage should have try-catch error handling"
    
    # Check for error handling in load function
    load_pattern = r'function loadWorkingDirFromStorage.*?try.*?catch'
    assert re.search(load_pattern, content, re.DOTALL), \
        "loadWorkingDirFromStorage should have try-catch error handling"
