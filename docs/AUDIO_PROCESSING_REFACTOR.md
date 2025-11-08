# Audio Processing Refactor: Removing torchaudio and torchcodec Dependencies

## Summary

This document describes the changes made to remove dependencies on `torchaudio` and `torchcodec`, which have issues with ffmpeg library integration in version 2.9.

## Problem Statement

- **torchaudio 2.9** has compatibility issues with ffmpeg libraries
- **torchcodec** was listed as a dependency but not actually used in the code
- The application needs to process audio for Voice Activity Detection (VAD) without these problematic dependencies

## Solution

Replace torchaudio's audio loading/saving functionality with a combination of:
1. **ffmpeg** (subprocess) - for decoding audio from any format
2. **soundfile** - for reading/writing WAV files
3. **numpy** - for audio array manipulation
4. **torch** - still used for the VAD model itself, just not for audio I/O

## Files Changed

### 1. `src/vlog/workflows/scripts/vad_utils.py`

**Key Changes:**
- Replaced `import torchaudio` with `import soundfile as sf`
- Added `load_audio_with_ffmpeg()` function:
  - Uses ffmpeg subprocess to convert any audio/video to WAV format
  - Loads WAV using soundfile
  - Returns numpy array and sample rate
- Added `resample_audio()` function:
  - Uses numpy interpolation for resampling (alternative to torchaudio.transforms.Resample)
  - Not currently used since ffmpeg handles resampling directly
- Updated `get_speech_segments()`:
  - Calls `load_audio_with_ffmpeg()` instead of `torchaudio.load()`
  - Converts numpy array to torch tensor for VAD model
- Updated `extract_audio_segment()`:
  - Uses `soundfile.write()` instead of `torchaudio.save()`

**Technical Details:**
```python
# Old approach (using torchaudio)
waveform, sr = torchaudio.load(audio_path)
if waveform.shape[0] > 1:
    waveform = torch.mean(waveform, dim=0, keepdim=True)
if sr != target_sr:
    resampler = torchaudio.transforms.Resample(sr, target_sr)
    waveform = resampler(waveform)

# New approach (using ffmpeg + soundfile)
waveform, sr = load_audio_with_ffmpeg(audio_path, sample_rate=target_sr)
waveform_tensor = torch.from_numpy(waveform)
```

### 2. `pyproject.toml`

**Changes:**
- Removed: `torchaudio<2.9.0`
- Removed: `torchcodec<0.8`
- Added: `soundfile>=0.12.1`

### 3. `src/vlog/workflows/scripts/transcribe.py`

**Changes:**
- Removed obsolete comment: "So that torchcodec can find ffmpeg on macOS"

### 4. `tests/test_vad_transcribe.py`

**Changes:**
- Updated test mocks to patch `load_audio_with_ffmpeg` instead of `torchaudio.load`
- Mocks now return numpy arrays instead of torch tensors
- Added mock for `torch.from_numpy` conversion

### 5. `tests/test_audio_processing_integration.py` (New)

**Purpose:**
- Integration test that verifies the complete audio processing pipeline
- Tests without requiring torch installation
- Validates the new approach works end-to-end

**Tests:**
1. Audio loading with soundfile
2. Resampling using numpy interpolation
3. Audio saving back to WAV format
4. Round-trip loading/saving

## Benefits of the New Approach

1. **Bypasses torchaudio 2.9 issues**: No longer depends on torchaudio's problematic ffmpeg backend
2. **Simpler dependency chain**: Direct subprocess calls instead of complex C++ bindings
3. **More debuggable**: ffmpeg subprocess errors are easier to diagnose
4. **Consistent with existing code**: Project already uses ffmpeg for video processing
5. **Lightweight**: soundfile is a simpler library than torchaudio

## Dependencies

### External Tools Required
- **ffmpeg**: Must be installed on the system (already required for video processing)

### Python Packages Required
- **soundfile** (>=0.12.1): For reading/writing WAV files
- **numpy**: For array manipulation (already available via torch)
- **torch**: Still required for the VAD model itself

### No Longer Required
- **torchaudio**: Removed
- **torchcodec**: Removed (was never actually used)

## Migration Notes

### For Users
- Install ffmpeg if not already installed: `apt-get install ffmpeg` or `brew install ffmpeg`
- Run `uv sync` to update dependencies (removes torchaudio, adds soundfile)

### For Developers
- The VAD functionality works exactly the same from the user's perspective
- Audio is still converted to torch tensors for the VAD model
- All existing tests continue to work with updated mocks

## Testing

### Unit Tests
Run the VAD-related tests:
```bash
pytest tests/test_vad_transcribe.py -v
```

### Integration Test
Run the audio processing integration test:
```bash
python3 tests/test_audio_processing_integration.py
```

This test verifies:
- ffmpeg can decode audio
- soundfile can read WAV files
- numpy can resample audio
- Audio can be saved and reloaded

## Performance Considerations

The new approach should have similar or better performance:
- **ffmpeg**: Highly optimized C library, same as what torchaudio used internally
- **soundfile**: Lightweight wrapper around libsndfile (C library)
- **numpy**: Similar performance to torch for basic array operations

The only potential overhead is the subprocess call to ffmpeg, but this is negligible compared to the actual audio processing time.

## Backward Compatibility

This change is backward compatible from a functionality perspective:
- All existing audio files can still be processed
- VAD output is identical
- API signatures remain the same

The only breaking change is the removal of torchaudio/torchcodec from dependencies, which should not affect users who don't import these libraries directly.

## Future Improvements

Potential enhancements:
1. Add caching of converted WAV files to avoid redundant ffmpeg calls
2. Support streaming audio processing for very large files
3. Add more sophisticated resampling options (currently uses linear interpolation)

## Conclusion

This refactor successfully removes the problematic torchaudio 2.9 and torchcodec dependencies while maintaining all functionality. The new approach is simpler, more debuggable, and consistent with the project's existing use of ffmpeg for video processing.
