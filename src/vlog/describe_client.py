"""
CLI client for the video description daemon.

This script handles:
- Starting the daemon if not running
- Sending video files for description
- Saving results as JSON files next to the videos
- Cleaning up the daemon when done
"""
import os
import sys
import json
import time
import signal
import subprocess
import argparse
from pathlib import Path
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 5555
DAEMON_STARTUP_TIMEOUT = 60  # seconds to wait for daemon startup


class DaemonManager:
    """Manages the lifecycle of the describe daemon."""
    
    def __init__(self, host: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT,
                 model: Optional[str] = None):
        self.host = host
        self.port = port
        self.model = model
        self.base_url = f"http://{host}:{port}"
        self.process: Optional[subprocess.Popen] = None
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        return session
    
    def is_daemon_running(self) -> bool:
        """Check if the daemon is already running.
        
        Returns:
            bool: True if daemon is reachable (even if busy), False if not running
        """
        try:
            # Try status endpoint first (gives more info)
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                if status.get("is_busy"):
                    print(f"Note: Daemon is currently processing {status.get('current_file', 'a file')}")
                    if status.get("processing_time_seconds"):
                        print(f"      Processing for {status['processing_time_seconds']}s")
                return True
        except requests.exceptions.Timeout:
            # Timeout likely means daemon is busy, not dead
            # Fall back to health check
            pass
        except requests.exceptions.ConnectionError:
            # Connection refused/failed - daemon is definitely not running
            return False
        except requests.exceptions.RequestException:
            # Other errors - try health check as fallback
            pass
        
        # Fallback to health endpoint (simpler, faster)
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.Timeout:
            # Timeout - check if we can at least connect to the port
            import socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((self.host, self.port))
                sock.close()
                if result == 0:
                    print("Note: Daemon is responding slowly (likely busy processing)")
                    return True
                return False
            except Exception:
                return False
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.RequestException:
            return False
    
    def start_daemon(self) -> bool:
        """Start the daemon process.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.is_daemon_running():
            print(f"Daemon already running at {self.base_url}")
            return True
        
        print(f"Starting daemon at {self.base_url}...")
        
        # Build command to start daemon
        cmd = [
            sys.executable, "-m", "vlog.describe_daemon",
            "--host", self.host,
            "--port", str(self.port),
        ]
        
        if self.model:
            cmd.extend(["--model", self.model])
        
        # Start the daemon as a subprocess
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            print(f"Failed to start daemon: {e}")
            return False
        
        # Wait for daemon to be ready
        start_time = time.time()
        while time.time() - start_time < DAEMON_STARTUP_TIMEOUT:
            if self.is_daemon_running():
                print("Daemon started successfully")
                return True
            time.sleep(1)
        
        print(f"Daemon failed to start within {DAEMON_STARTUP_TIMEOUT} seconds")
        self.stop_daemon()
        return False
    
    def stop_daemon(self):
        """Stop the daemon process."""
        if self.process:
            print("Stopping daemon...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Daemon did not stop gracefully, killing...")
                self.process.kill()
            self.process = None
        
        self.session.close()
    
    def describe_video(self, video_path: str, fps: float = 1.0,
                      max_pixels: int = 224 * 224, max_tokens: int = 10000,
                      temperature: float = 0.7) -> Optional[dict]:
        """Send a video to the daemon for description.
        
        Args:
            video_path: Path to the video file
            fps: Frames per second to sample
            max_pixels: Maximum pixel size for frames
            max_tokens: Maximum generation tokens
            temperature: Temperature for generation
        
        Returns:
            dict: The description response, or None on error
        """
        if not os.path.isfile(video_path):
            print(f"Error: File not found: {video_path}")
            return None
        
        # Prepare request
        request_data = {
            "filename": os.path.abspath(video_path),
            "fps": fps,
            "max_pixels": max_pixels,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        print(f"Describing {os.path.basename(video_path)}...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/describe",
                json=request_data,
                timeout=600,  # 10 minute timeout for long videos
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 503:
                # Daemon is busy
                try:
                    error_detail = e.response.json()
                    print(f"Error: {error_detail.get('detail', 'Daemon is busy')}")
                    print("Wait for the current job to complete and try again")
                except Exception:
                    print("Error: Daemon is busy processing another request")
                    print("Wait for the current job to complete and try again")
            else:
                print(f"HTTP Error {e.response.status_code}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.json()
                        print(f"Error details: {error_detail}")
                    except Exception:
                        print(f"Error response: {e.response.text}")
            return None
        except requests.exceptions.Timeout as e:
            print(f"Error: Request timed out after 600 seconds")
            print("The daemon may still be processing - check daemon logs")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"Error: Cannot connect to daemon at {self.base_url}")
            print("The daemon may have crashed or been stopped")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error describing video: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"Error details: {error_detail}")
                except Exception:
                    print(f"Error response: {e.response.text}")
            return None


def save_description_json(video_path: str, description: dict, output_dir: Optional[str] = None):
    """Save the description as a JSON file next to the video.
    
    Args:
        video_path: Path to the video file
        description: Description dictionary to save
        output_dir: Optional output directory (default: same as video)
    """
    video_path_obj = Path(video_path)
    
    if output_dir:
        output_path_obj = Path(output_dir) / f"{video_path_obj.stem}.json"
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path_obj = video_path_obj.with_suffix('.json')
    
    with open(output_path_obj, 'w', encoding='utf-8') as f:
        json.dump(description, f, indent=2, ensure_ascii=False)
    
    print(f"Saved description to {output_path_obj}")


def process_videos(video_paths: list[str], daemon_manager: DaemonManager,
                   output_dir: Optional[str] = None, fps: float = 1.0,
                   max_pixels: int = 224 * 224, max_tokens: int = 10000,
                   temperature: float = 0.7):
    """Process multiple video files.
    
    Args:
        video_paths: List of video file paths
        daemon_manager: The daemon manager instance
        output_dir: Optional output directory for JSON files
        fps: Frames per second to sample
        max_pixels: Maximum pixel size for frames
        max_tokens: Maximum generation tokens
        temperature: Temperature for generation
    """
    successful = 0
    failed = 0
    
    for video_path in video_paths:
        description = daemon_manager.describe_video(
            video_path,
            fps=fps,
            max_pixels=max_pixels,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        if description:
            save_description_json(video_path, description, output_dir)
            successful += 1
        else:
            failed += 1
    
    print(f"\nProcessed {successful + failed} videos: {successful} successful, {failed} failed")


def main():
    """Main entry point for the CLI client."""
    parser = argparse.ArgumentParser(
        description="Describe videos using the MLX-VLM daemon"
    )
    parser.add_argument(
        "videos",
        nargs="+",
        help="Video file(s) to describe"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_DAEMON_HOST,
        help="Daemon host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DAEMON_PORT,
        help="Daemon port (default: 5555)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name to use (if starting daemon)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for JSON files (default: same as video)"
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=1.0,
        help="Frames per second to sample (default: 1.0)"
    )
    parser.add_argument(
        "--max-pixels",
        type=int,
        default=224 * 224,
        help="Maximum pixel size for frames (default: 50176)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=10000,
        help="Maximum generation tokens (default: 10000)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for generation (default: 0.7)"
    )
    parser.add_argument(
        "--keep-daemon",
        action="store_true",
        help="Keep daemon running after processing (don't cleanup)"
    )
    parser.add_argument(
        "--use-existing",
        action="store_true",
        help="Use existing daemon without starting a new one"
    )
    
    args = parser.parse_args()
    
    # Create daemon manager
    daemon_manager = DaemonManager(
        host=args.host,
        port=args.port,
        model=args.model,
    )
    
    # Track if we started the daemon (for cleanup)
    started_daemon = False
    
    try:
        # Start daemon if needed
        if not args.use_existing:
            if not daemon_manager.start_daemon():
                print("Failed to start daemon")
                sys.exit(1)
            started_daemon = True
        elif not daemon_manager.is_daemon_running():
            print(f"Error: Daemon not running at {daemon_manager.base_url}")
            print("Possible reasons:")
            print("  - Daemon is not started")
            print("  - Daemon is starting up (wait a moment and try again)")
            print("  - Wrong host/port specified")
            print("\nEither start a daemon separately or remove --use-existing flag")
            sys.exit(1)
        else:
            print(f"Using existing daemon at {daemon_manager.base_url}")
        
        # Process videos
        process_videos(
            args.videos,
            daemon_manager,
            output_dir=args.output_dir,
            fps=args.fps,
            max_pixels=args.max_pixels,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Cleanup daemon if we started it and user didn't request to keep it
        if started_daemon and not args.keep_daemon:
            daemon_manager.stop_daemon()
        elif started_daemon and args.keep_daemon:
            print(f"\nDaemon still running at {daemon_manager.base_url}")
            print("Stop it manually when done")


if __name__ == "__main__":
    main()
