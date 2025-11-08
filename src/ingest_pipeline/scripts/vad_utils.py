#!/usr/bin/env python3
"""
Voice Activity Detection (VAD) utilities using Silero VAD.

This module provides functions to detect speech segments in audio files
before transcription, reducing hallucination by avoiding silent regions.

Inspired by WhisperX approach but without diarization.
"""
from __future__ import annotations

import logging
import torch
import torchaudio
from pathlib import Path
from typing import List, Dict


def load_vad_model():
    """Load Silero VAD model from torch.hub.
    
    Returns:
        tuple: (model, utils) where utils contains helper functions
    """
    try:
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        return model, utils
    except Exception as e:
        logging.error(f"Failed to load Silero VAD model: {e}")
        raise


def get_speech_segments(
    audio_path: str,
    vad_model=None,
    vad_utils=None,
    sample_rate: int = 16000,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 100,
    padding_duration_ms: int = 30,
) -> List[Dict[str, float]]:
    """
    Detect speech segments in an audio file using Silero VAD.
    
    Args:
        audio_path: Path to the audio file
        vad_model: Pre-loaded VAD model (optional, will load if None)
        vad_utils: VAD utilities (optional, will load if None)
        sample_rate: Target sample rate for VAD (16kHz recommended)
        threshold: Speech probability threshold (0.0-1.0)
        min_speech_duration_ms: Minimum speech segment duration in ms
        min_silence_duration_ms: Minimum silence duration between segments
        padding_duration_ms: Padding to add around speech segments
    
    Returns:
        List of dicts with 'start' and 'end' timestamps in seconds
        
    Example:
        >>> segments = get_speech_segments("audio.mp4")
        >>> print(segments)
        [{'start': 0.5, 'end': 5.2}, {'start': 6.0, 'end': 10.5}]
    """
    # Load VAD model if not provided
    if vad_model is None or vad_utils is None:
        vad_model, vad_utils = load_vad_model()
    
    get_speech_timestamps = vad_utils[0]
    
    # Load audio file
    try:
        # torchaudio.load returns (waveform, sample_rate)
        # waveform shape: (channels, samples)
        waveform, original_sr = torchaudio.load(audio_path)
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Resample to 16kHz if needed (VAD expects 16kHz)
        if original_sr != sample_rate:
            resampler = torchaudio.transforms.Resample(
                orig_freq=original_sr,
                new_freq=sample_rate
            )
            waveform = resampler(waveform)
        
        # Flatten to 1D tensor (VAD expects 1D)
        waveform = waveform.squeeze()
        
        # Get speech timestamps (returns sample indices)
        speech_timestamps = get_speech_timestamps(
            waveform,
            vad_model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            speech_pad_ms=padding_duration_ms,
        )
        
        # Convert from sample indices to seconds
        segments = []
        for timestamp in speech_timestamps:
            start_sec = timestamp['start'] / sample_rate
            end_sec = timestamp['end'] / sample_rate
            segments.append({
                'start': start_sec,
                'end': end_sec
            })
        
        logging.info(f"Detected {len(segments)} speech segments in {audio_path}")
        return segments
        
    except Exception as e:
        logging.error(f"Failed to detect speech segments in {audio_path}: {e}")
        # Return empty list on error - will transcribe entire file
        return []


def extract_audio_segment(
    audio_path: str,
    start_sec: float,
    end_sec: float,
    output_path: str | None = None,
    sample_rate: int = 16000
) -> str:
    """
    Extract a segment from an audio file.
    
    Args:
        audio_path: Path to source audio file
        start_sec: Start time in seconds
        end_sec: End time in seconds
        output_path: Path to save extracted segment (optional)
        sample_rate: Target sample rate
        
    Returns:
        Path to the extracted audio segment
    """
    try:
        # Load audio
        waveform, original_sr = torchaudio.load(audio_path)
        
        # Convert to mono
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Resample if needed
        if original_sr != sample_rate:
            resampler = torchaudio.transforms.Resample(
                orig_freq=original_sr,
                new_freq=sample_rate
            )
            waveform = resampler(waveform)
        
        # Calculate sample indices
        start_sample = int(start_sec * sample_rate)
        end_sample = int(end_sec * sample_rate)
        
        # Extract segment
        segment = waveform[:, start_sample:end_sample]
        
        # Save to file if output_path provided
        if output_path:
            torchaudio.save(output_path, segment, sample_rate)
            return output_path
        else:
            # Save to temp file
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.wav',
                prefix='vad_segment_'
            )
            torchaudio.save(temp_file.name, segment, sample_rate)
            return temp_file.name
            
    except Exception as e:
        logging.error(f"Failed to extract audio segment: {e}")
        raise


if __name__ == "__main__":
    # Test VAD functionality
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python vad_utils.py <audio_file>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    audio_file = sys.argv[1]
    segments = get_speech_segments(audio_file)
    
    print(f"\nDetected {len(segments)} speech segments:")
    for i, seg in enumerate(segments, 1):
        duration = seg['end'] - seg['start']
        print(f"  {i}. {seg['start']:.2f}s - {seg['end']:.2f}s (duration: {duration:.2f}s)")
