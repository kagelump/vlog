import cv2
import os
import datetime
import base64
from typing import Optional

# Assuming BLACK_PIXEL_BASE64 is defined elsewhere (e.g., a 1x1 black pixel encoded)
# For this example, let's use a placeholder/mock value:
BLACK_PIXEL_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def get_video_length_and_timestamp(file_path: str) -> tuple[float, str]:
    """
    Opens the video file to extract length and system timestamp (last modified).

    Returns: (video_length_seconds, video_timestamp_iso)
    """
    video_length = 0.0
    video_timestamp = datetime.datetime.now().isoformat()  # Default to now()

    # --- 1. Get Video Length ---
    cap = cv2.VideoCapture(file_path)
    
    if cap.isOpened():
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            # Calculate length, safely handle zero values
            video_length = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
            print(f" -> Calculated video length: {video_length:.2f} seconds.")
        except Exception as e:
            print(f" -> Warning: Could not calculate video length for '{file_path}'. Error: {e}")
        finally:
            cap.release()
    else:
        print(f" -> Warning: Could not open video '{file_path}' to calculate length.")
    
    # --- 2. Get System Timestamp (Last Modified Time) ---
    try:
        # Get file modification time
        mod_time_sec = os.path.getmtime(file_path)
        # Convert Unix timestamp to datetime and then to ISO format
        video_timestamp = datetime.datetime.fromtimestamp(mod_time_sec).isoformat()
        print(f" -> Using file system modification time: {video_timestamp}")
    except FileNotFoundError:
        # Fallback if file path is unreachable
        print(" -> Warning: File not found for timestamp. Using current time.")
        video_timestamp = datetime.datetime.now().isoformat()
    except Exception as e:
        print(f" -> Warning: Could not get file system time. Error: {e}")

    return video_length, video_timestamp

# -----------------------------------------------------------------------------

def get_video_thumbnail(file_path: str, thumbnail_frame: int, thumbnail_frame_fps: float = 1.0) -> str:
    """
    Opens the video file to extract a thumbnail at a specific frame and returns it as a Base64 string.
    
    DEPRECATED: Use save_video_thumbnail_to_file() instead to save thumbnails as JPG files.
    
    Returns: thumbnail_base64
    """
    thumbnail_base64 = BLACK_PIXEL_BASE64
    cap = cv2.VideoCapture(file_path)
    
    if cap.isOpened():
        try:
            # Get video FPS to convert the requested 'thumbnail_frame' to the actual frame number
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                 # Handle case where FPS is not detected or zero, default to frame index being the requested frame
                 real_frame = thumbnail_frame
                 print(" -> Warning: FPS not detected, using thumbnail_frame as direct frame index.")
            else:
                # Calculate the actual frame number based on the desired frame at the specified FPS
                real_frame = thumbnail_frame * fps / thumbnail_frame_fps

            # Set the position to the desired frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, real_frame)
            ret, frame = cap.read()
            
            if ret and frame is not None:
                # Encode the frame to JPG format (bytes) with 50% quality
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                _, buffer = cv2.imencode('.jpg', frame, encode_param) 
                # Convert bytes to Base64 string
                thumbnail_base64 = base64.b64encode(buffer).decode('utf-8')
                print(f" -> Successfully extracted frame {real_frame} and encoded to Base64.")
            else:
                print(f" -> Warning: Could not read frame {real_frame} from video '{file_path}'.")
                
        except Exception as e:
            print(f" -> Error extracting thumbnail from '{file_path}': {e}")
        finally:
            # Release the resource immediately after extraction
            cap.release()
    else:
        print(f" -> Critical Warning: Could not open video '{file_path}' for thumbnail extraction. Returning black pixel.")
        
    return thumbnail_base64


def save_video_thumbnail_to_file(file_path: str, thumbnail_frame: int, thumbnail_frame_fps: float = 1.0, output_path: Optional[str] = None) -> bool:
    """
    Opens the video file to extract a thumbnail at a specific frame and saves it as a JPG file.
    
    Args:
        file_path: Path to the video file
        thumbnail_frame: Frame number to extract (in thumbnail_frame_fps units)
        thumbnail_frame_fps: FPS rate for the thumbnail_frame parameter
        output_path: Optional path for the output JPG. If None, saves as {video_path}_thumb.jpg
    
    Returns:
        True if thumbnail was saved successfully, False otherwise
    """
    from pathlib import Path
    
    # Determine output path
    if output_path is None:
        video_path = Path(file_path)
        output_path = str(video_path.parent / f"{video_path.stem}_thumb.jpg")
    
    cap = cv2.VideoCapture(file_path)
    
    if cap.isOpened():
        try:
            # Get video FPS to convert the requested 'thumbnail_frame' to the actual frame number
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                # Handle case where FPS is not detected or zero, default to frame index being the requested frame
                real_frame = thumbnail_frame
                print(" -> Warning: FPS not detected, using thumbnail_frame as direct frame index.")
            else:
                # Calculate the actual frame number based on the desired frame at the specified FPS
                real_frame = thumbnail_frame * fps / thumbnail_frame_fps

            # Set the position to the desired frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, real_frame)
            ret, frame = cap.read()
            
            if ret and frame is not None:
                # Save the frame as JPG with 50% quality
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                success = cv2.imwrite(output_path, frame, encode_param)
                
                if success:
                    print(f" -> Successfully saved thumbnail to: {output_path}")
                    return True
                else:
                    print(f" -> Error: Failed to save thumbnail to {output_path}")
                    return False
            else:
                print(f" -> Warning: Could not read frame {real_frame} from video '{file_path}'.")
                return False
                
        except Exception as e:
            print(f" -> Error extracting thumbnail from '{file_path}': {e}")
            return False
        finally:
            # Release the resource immediately after extraction
            cap.release()
    else:
        print(f" -> Critical Warning: Could not open video '{file_path}' for thumbnail extraction.")
        return False


def get_thumbnail_path_for_video(video_path: str) -> str:
    """
    Get the expected thumbnail path for a video file.
    
    Args:
        video_path: Path to the video file
    
    Returns:
        Expected path to the thumbnail JPG file
    """
    from pathlib import Path
    video_path_obj = Path(video_path)
    return str(video_path_obj.parent / f"{video_path_obj.stem}_thumb.jpg")