"""
FastAPI daemon for video description service.

This daemon loads the MLX-VLM model once at startup and provides a REST API
for describing videos. It uses protobuf messages for the API contract.
"""
import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from vlog.describe_lib import (
    describe_video,
    load_model,
    load_subtitle_file,
    calculate_adaptive_fps,
)
from vlog.video import get_video_length_and_timestamp, save_video_thumbnail_to_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Request/Response models (simplified from protobuf for JSON API)
class DescribeRequest(BaseModel):
    """Request to describe a video file."""
    filename: str  # Full path to video file
    fps: float = 1.0
    max_pixels: int = 224 * 224
    max_tokens: int = 10000
    temperature: float = 0.7


class SegmentResponse(BaseModel):
    """Video segment with timestamps."""
    in_timestamp: str
    out_timestamp: str


class DescribeResponse(BaseModel):
    """Response containing video description."""
    filename: str
    video_description_long: str
    video_description_short: str
    primary_shot_type: str
    tags: list[str]
    classification_time_seconds: float
    classification_model: str
    video_length_seconds: float
    video_timestamp: str
    video_thumbnail_base64: str  # DEPRECATED: Use thumbnail JPG file instead
    in_timestamp: str
    out_timestamp: str
    rating: float
    segments: list[SegmentResponse] | None = None
    camera_movement: str | None = None
    thumbnail_frame: int | None = None


# Global model state
MODEL_STATE: dict = {
    "model": None,
    "processor": None,
    "config": None,
    "model_name": None,
}

# Processing state
PROCESSING_STATE: dict = {
    "is_busy": False,
    "current_file": None,
    "start_time": None,
    "total_processed": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage model lifecycle - load on startup, cleanup on shutdown."""
    # Startup: Load model
    model_name = os.environ.get(
        "DESCRIBE_MODEL",
        "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    )
    logger.info(f"Loading model: {model_name}")
    try:
        model, processor, config = load_model(model_name)
        MODEL_STATE["model"] = model
        MODEL_STATE["processor"] = processor
        MODEL_STATE["config"] = config
        MODEL_STATE["model_name"] = model_name
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise
    
    yield
    
    # Shutdown: Cleanup
    logger.info("Shutting down daemon")
    MODEL_STATE.clear()


app = FastAPI(
    title="Video Description Daemon",
    description="MLX-VLM based video description service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint - always responds quickly even if busy."""
    return {
        "status": "healthy",
        "model_loaded": MODEL_STATE["model"] is not None,
        "model_name": MODEL_STATE.get("model_name"),
    }


@app.get("/status")
async def status_check():
    """
    Status endpoint with processing information.
    
    Returns information about whether daemon is busy and what it's processing.
    """
    status = {
        "status": "healthy",
        "model_loaded": MODEL_STATE["model"] is not None,
        "model_name": MODEL_STATE.get("model_name"),
        "is_busy": PROCESSING_STATE["is_busy"],
        "total_processed": PROCESSING_STATE["total_processed"],
    }
    
    if PROCESSING_STATE["is_busy"] and PROCESSING_STATE["current_file"]:
        status["current_file"] = os.path.basename(PROCESSING_STATE["current_file"])
        if PROCESSING_STATE["start_time"]:
            elapsed = time.time() - PROCESSING_STATE["start_time"]
            status["processing_time_seconds"] = round(elapsed, 1)
    
    return status


@app.post("/describe", response_model=DescribeResponse)
async def describe_video_endpoint(request: DescribeRequest):
    """
    Describe a video file.

    Args:
        request: DescribeRequest containing the filename and parameters

    Returns:
        DescribeResponse with video description and metadata

    Raises:
        HTTPException: If file not found or processing fails
    """
    # Validate model is loaded
    if MODEL_STATE["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Check if already busy (optional - remove this if you want to queue)
    if PROCESSING_STATE["is_busy"]:
        raise HTTPException(
            status_code=503,
            detail=f"Daemon is busy processing {os.path.basename(PROCESSING_STATE['current_file'])}"
        )
    
    # Mark as busy
    PROCESSING_STATE["is_busy"] = True
    PROCESSING_STATE["current_file"] = request.filename
    PROCESSING_STATE["start_time"] = time.time()
    
    try:
        # Validate file exists
        if not os.path.isfile(request.filename):
            raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")
        
        # Extract base filename
        base_filename = os.path.basename(request.filename)
        
        # Load subtitle if present
        subtitle_file = os.path.splitext(request.filename)[0] + '.srt'
        subtitle_text = load_subtitle_file(subtitle_file)
        
        # Get video metadata
        try:
            video_length, video_timestamp = get_video_length_and_timestamp(request.filename)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read video metadata: {e}")
        
        # Calculate adaptive FPS
        fps = calculate_adaptive_fps(video_length, request.fps)
        
        # Describe the video
        start_time = time.time()
        try:
            desc = describe_video(
                MODEL_STATE["model"],
                MODEL_STATE["processor"],
                MODEL_STATE["config"],
                request.filename,
                prompt=None,  # Use default prompt
                fps=fps,
                subtitle=subtitle_text,
                max_pixels=request.max_pixels,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except Exception as e:
            logger.error(f"Failed to describe video {base_filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to describe video: {e}")
        
        elapsed_time = time.time() - start_time
        
        # Save thumbnail to file
        try:
            thumbnail_frame = int(desc.get('thumbnail_frame', 0))
        except (ValueError, TypeError):
            thumbnail_frame = 0
        
        try:
            save_video_thumbnail_to_file(request.filename, thumbnail_frame, fps)
        except Exception as e:
            logger.warning(f"Failed to save thumbnail: {e}")
        
        # Convert segments to response format
        segments_response = None
        if desc.get('segments'):
            segments_response = [
                SegmentResponse(
                    in_timestamp=seg.get('in_timestamp', ''),
                    out_timestamp=seg.get('out_timestamp', '')
                )
                for seg in desc['segments']
            ]
        
        # Build response (video_thumbnail_base64 is deprecated but kept for API compatibility)
        response = DescribeResponse(
            filename=base_filename,
            video_description_long=desc.get('description', ''),
            video_description_short=desc.get('short_name', ''),
            primary_shot_type=desc.get('primary_shot_type', ''),
            tags=desc.get('tags', []),
            classification_time_seconds=elapsed_time,
            classification_model=MODEL_STATE["model_name"] or "unknown",
            video_length_seconds=video_length,
            video_timestamp=video_timestamp,
            video_thumbnail_base64="",  # DEPRECATED: Now saved as JPG file
            in_timestamp=desc.get('in_timestamp', ''),
            out_timestamp=desc.get('out_timestamp', ''),
            rating=desc.get('rating', 0.0),
            segments=segments_response,
            camera_movement=desc.get('camera_movement'),
            thumbnail_frame=thumbnail_frame,
        )
        
        # Increment processed count
        PROCESSING_STATE["total_processed"] += 1
        
        return response
        
    finally:
        # Always mark as not busy when done (success or failure)
        PROCESSING_STATE["is_busy"] = False
        PROCESSING_STATE["current_file"] = None
        PROCESSING_STATE["start_time"] = None


def main(host: str = "127.0.0.1", port: int = 5555):
    """Run the daemon server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the video description daemon")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5555, help="Port to bind to")
    parser.add_argument("--model", type=str, help="Model name (overrides DESCRIBE_MODEL env var)")
    
    args = parser.parse_args()
    
    # Set model environment variable if provided
    if args.model:
        os.environ["DESCRIBE_MODEL"] = args.model
    
    main(host=args.host, port=args.port)