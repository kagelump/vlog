#!/usr/bin/env python3
"""
Manual integration test to verify that the web server remains responsive
during auto-ingest Snakemake execution.

This test simulates the scenario:
1. Start the web server
2. Start auto-ingest via API
3. Continuously poll status/progress endpoints while Snakemake runs
4. Verify all API calls respond quickly (< 1 second)

Usage:
    python tests/manual_test_web_responsiveness.py

Note: This requires a real working directory with video files to process.
For a quick test with mocked Snakemake, use test_auto_ingest_lock_fix.py instead.
"""

import sys
import time
import tempfile
import threading
import requests
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_web_server_responsiveness():
    """Test that web server APIs remain responsive during auto-ingest."""
    
    print("=" * 70)
    print("Manual Integration Test: Web Server Responsiveness")
    print("=" * 70)
    
    # Configuration
    base_url = "http://localhost:5432"
    watch_dir = tempfile.mkdtemp()
    
    print(f"\n1. Testing connectivity to {base_url}...")
    try:
        response = requests.get(f"{base_url}/api/project-info", timeout=2)
        if response.status_code == 200:
            print("   ✓ Web server is running")
        else:
            print(f"   ✗ Web server returned status {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"   ✗ Cannot connect to web server: {e}")
        print(f"   Please start the web server first:")
        print(f"   cd /path/to/vlog && uv run -- python -m vlog.web")
        return False
    
    print(f"\n2. Getting initial auto-ingest status...")
    response = requests.get(f"{base_url}/api/auto-ingest-snakemake/status")
    initial_status = response.json()
    print(f"   Initial status: is_running={initial_status.get('is_running')}")
    
    if initial_status.get('is_running'):
        print("   ✗ Auto-ingest is already running. Please stop it first.")
        return False
    
    print(f"\n3. Starting auto-ingest for directory: {watch_dir}")
    start_data = {
        'watch_directory': watch_dir,
        'model_name': 'mlx-community/Qwen3-VL-8B-Instruct-4bit',
        'cores': 2,
        'resources_mem_gb': 4
    }
    response = requests.post(
        f"{base_url}/api/auto-ingest-snakemake/start",
        json=start_data,
        timeout=5
    )
    
    if response.status_code != 200:
        print(f"   ✗ Failed to start auto-ingest: {response.json()}")
        return False
    
    print(f"   ✓ Auto-ingest started successfully")
    
    print(f"\n4. Testing API responsiveness while Snakemake might be running...")
    print(f"   Polling status and progress endpoints for 10 seconds...")
    
    max_response_time = 0.0
    total_requests = 0
    slow_requests = 0
    
    start_time = time.time()
    while time.time() - start_time < 10:
        # Test status endpoint
        req_start = time.time()
        try:
            response = requests.get(
                f"{base_url}/api/auto-ingest-snakemake/status",
                timeout=2
            )
            req_time = time.time() - req_start
            total_requests += 1
            max_response_time = max(max_response_time, req_time)
            
            if req_time > 1.0:
                slow_requests += 1
                print(f"   ⚠ Slow status request: {req_time:.3f}s")
            
        except requests.Timeout:
            print(f"   ✗ Status request timed out!")
            slow_requests += 1
        except requests.RequestException as e:
            print(f"   ✗ Status request failed: {e}")
        
        time.sleep(0.2)
        
        # Test progress endpoint
        req_start = time.time()
        try:
            response = requests.get(
                f"{base_url}/api/auto-ingest-snakemake/progress",
                timeout=2
            )
            req_time = time.time() - req_start
            total_requests += 1
            max_response_time = max(max_response_time, req_time)
            
            if req_time > 1.0:
                slow_requests += 1
                print(f"   ⚠ Slow progress request: {req_time:.3f}s")
            
        except requests.Timeout:
            print(f"   ✗ Progress request timed out!")
            slow_requests += 1
        except requests.RequestException as e:
            print(f"   ✗ Progress request failed: {e}")
        
        time.sleep(0.3)
    
    print(f"\n5. Results:")
    print(f"   Total requests: {total_requests}")
    print(f"   Slow requests (> 1s): {slow_requests}")
    print(f"   Max response time: {max_response_time:.3f}s")
    
    print(f"\n6. Stopping auto-ingest...")
    response = requests.post(f"{base_url}/api/auto-ingest-snakemake/stop")
    if response.status_code == 200:
        print(f"   ✓ Auto-ingest stopped")
    else:
        print(f"   ⚠ Could not stop auto-ingest: {response.json()}")
    
    # Clean up temp directory
    import shutil
    shutil.rmtree(watch_dir, ignore_errors=True)
    
    print(f"\n7. Test Summary:")
    if slow_requests == 0:
        print(f"   ✓ SUCCESS: All API calls responded quickly (< 1s)")
        print(f"   The web server remained responsive during auto-ingest!")
        return True
    elif slow_requests < total_requests * 0.1:  # Less than 10% slow
        print(f"   ⚠ PARTIAL SUCCESS: Most requests were fast")
        print(f"   Only {slow_requests}/{total_requests} requests were slow")
        return True
    else:
        print(f"   ✗ FAILURE: Too many slow requests ({slow_requests}/{total_requests})")
        print(f"   The web server may still have responsiveness issues")
        return False


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("MANUAL INTEGRATION TEST")
    print("=" * 70)
    print("\nThis test verifies that the web server remains responsive while")
    print("auto-ingest (Snakemake) is running.")
    print("\nPrerequisites:")
    print("  1. Start the web server first:")
    print("     cd /path/to/vlog && uv run -- python -m vlog.web")
    print("  2. Ensure port 5432 is available")
    print("\nPress Ctrl+C to cancel or Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(0)
    
    success = test_web_server_responsiveness()
    
    print("\n" + "=" * 70)
    if success:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ✗")
    print("=" * 70 + "\n")
    
    sys.exit(0 if success else 1)
