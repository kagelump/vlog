"""
FastAPI server for exposing workflow status via REST API.

This module provides a simple REST API endpoint that returns the current
status of the Snakemake workflow, including job counts per rule and stage.
"""

import threading
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn


# FastAPI app instance
app = FastAPI(title="Snakemake Workflow Status API")


@app.get("/status")
async def get_status():
    """
    Get current workflow status.
    
    Returns:
        JSON object with workflow status including:
        - total_jobs: Total number of jobs
        - completed_jobs: Number of completed jobs
        - failed_jobs: Number of failed jobs
        - running_jobs: Number of currently running jobs
        - pending_jobs: Number of pending jobs
        - rules: Per-rule breakdown of job counts
    """
    from .logger import get_workflow_status
    
    status = get_workflow_status()
    return JSONResponse(content=status)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/reset")
async def reset_status():
    """Reset the workflow status tracker."""
    from .logger import reset_workflow_status
    
    reset_workflow_status()
    return {"status": "reset"}


def start_api_server(host: str = "127.0.0.1", port: int = 5556) -> threading.Thread:
    """
    Start the FastAPI server in a background thread.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    
    Returns:
        Thread object running the server
    """
    def run_server():
        uvicorn.run(app, host=host, port=port, log_level="error")
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
