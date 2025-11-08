#!/usr/bin/env python3
"""
Clean subtitle files generated from Whisper JSON output.

This script reads Whisper JSON output (_whisper.json) which contains
word-level timestamps and confidence scores, applies cleaning logic to
remove duplicates and hallucinations, and outputs a clean SRT file (_cleaned.srt).

The JSON format provides richer metadata than SRT for better hallucination detection.

Author: automated migration with JSON support
"""
import os
import re
import json
from snakemake.script import snakemake
from collections import Counter
from typing import List, Dict


TARGET_DIRECTORY = "." 
OUTPUT_SUFFIX = "_cleaned.srt"


def _get_ngrams(sequence: List[str], n: int) -> List[str]:
    """Helper to generate N-grams from a sequence of words or characters."""
    ngrams: List[str] = []
    # Ensure there are enough elements to form at least one n-gram
    if len(sequence) < n:
        return []
        
    for i in range(len(sequence) - n + 1):
        # Determine separator: space for word bigrams, empty string for character bigrams
        # Check if the sequence elements are words (len > 1) or characters (len == 1)
        is_word_sequence = len(sequence) > 0 and len(sequence[0]) > 1
        separator = ' ' if is_word_sequence else ''
        
        ngram = separator.join(sequence[i:i + n])
        ngrams.append(ngram)
    return ngrams


def is_hallucination_by_repetition(
    text: str, 
    word_repetition_threshold: float = 0.65, 
    cjk_repetition_threshold: float = 0.25, 
    min_tokens: int = 5
) -> bool:
    """
    Detects potential ASR hallucination in a text string based on excessive
    repetition of a single N-gram.

    It uses a separate, lower threshold for CJK-like text (which lacks spaces) 
    due to the statistical property that cyclic repetition splits the frequency 
    count across multiple character N-grams.

    Args:
        text (str): The transcribed text segment to analyze.
        word_repetition_threshold (float): Threshold for space-separated languages (word bigrams).
                                           Default is 0.65 (65%).
        cjk_repetition_threshold (float): Threshold for CJK-like languages (character bigrams).
                                          Default is 0.25 (25%).
        min_tokens (int): The minimum number of *meaningful tokens* required for
                          the check. Default is 5.

    Returns:
        bool: True if the text is flagged as a likely hallucination, False otherwise.
    """

    # 1. Preprocessing and Tokenization Attempt
    normalized_text = re.sub(r'[.,;!?]', '', text).lower().strip()
    words = normalized_text.split()
    
    tokens: List[str] = words
    n_size = 2 # Default N-gram size
    used_threshold = word_repetition_threshold
    
    # 2. CJK Fallback Check
    # If word splitting results in too few tokens for a long string, switch to character n-grams.
    if len(words) < min_tokens and len(normalized_text) >= min_tokens:
        tokens = list(normalized_text)
        n_size = 2 # Character Bigrams
        used_threshold = cjk_repetition_threshold
        
    # Early exit for too short segments
    if len(tokens) < n_size:
        return False

    # 3. Generate N-grams
    ngrams: List[str] = _get_ngrams(tokens, n_size)

    if not ngrams:
        return False

    # 4. Frequency Counting and Score Calculation
    ngram_counts = Counter(ngrams)

    if not ngram_counts:
        return False
        
    most_common_count = ngram_counts.most_common(1)[0][1]
    total_ngrams = len(ngrams)

    repetition_score: float = most_common_count / total_ngrams

    # 5. Threshold Check
    if repetition_score >= used_threshold:
        return True
    else:
        return False


def parse_whisper_json(filepath: str) -> List[Dict]:
    """
    Reads a Whisper JSON file and converts segments to subtitle format.
    
    Args:
        filepath: Path to the _whisper.json file
        
    Returns:
        List of subtitle dictionaries with 'start', 'end', and 'text' keys
    """
    print(f"Reading {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    subtitles = []
    for segment in data.get('segments', []):
        text = segment.get('text', '').strip()
        start = segment.get('start', 0.0)
        end = segment.get('end', 0.0)
        
        # Store segment with timing info
        # We'll also keep word-level data for potential future use
        subtitles.append({
            'start': start,
            'end': end,
            'text': text,
            'words': segment.get('words', [])  # Word-level timestamps for future enhancements
        })
    
    return subtitles


def format_srt_timestamp(seconds: float) -> str:
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def reassemble_srt(subtitles: List[Dict]) -> str:
    """
    Takes the list of subtitle dictionaries and formats it back into a valid SRT string.
    Crucially, it re-indexes the output sequentially and skips segments with empty text.
    
    Args:
        subtitles: List of subtitle dicts with 'start', 'end', and 'text' keys
        
    Returns:
        SRT formatted string
    """
    output = []
    new_index = 1
    for sub in subtitles:
        # Only include non-empty text segments in the output file
        if sub['text']:
            # Use the new sequential index for the final output
            output.append(f"{new_index}")
            
            # Format timestamps
            start_ts = format_srt_timestamp(sub['start'])
            end_ts = format_srt_timestamp(sub['end'])
            output.append(f"{start_ts} --> {end_ts}")
            
            output.append(sub['text'])
            output.append("") # Empty line separator
            new_index += 1
    
    # Join all parts with newlines, ensuring no trailing newline at the very end
    return "\n".join(output).strip()


def clean_subtitles(subtitles: List[Dict]) -> List[Dict]:
    """
    Cleans subtitle segments by removing duplicates and hallucinations.
    
    Args:
        subtitles: List of subtitle dicts
        
    Returns:
        Cleaned list of subtitle dicts
    """
    pass1 = []
    removed = set()
    for sub in subtitles:
        last_sub_text = pass1[-1]['text'] if pass1 else ""
        if (sub['text'].strip() == last_sub_text.strip() 
            or is_hallucination_by_repetition(sub['text'])):
            # Skip duplicate subtitle text
            print(f"Skipping duplicate/hallucination: {sub['start']:.2f}s {sub['text']}")
            removed.add(sub['text'])
            continue
        print(f"OK subtitle text: {sub['start']:.2f}s {sub['text']}")
        pass1.append(sub)
    
    result = []
    for sub in pass1:
        if sub['text'] in removed:
            print(f"Removing subtitle text found in removed set: {sub['start']:.2f}s {sub['text']}")
            continue
        result.append(sub)
    
    # If only one subtitle remains, return empty (likely all hallucination)
    if len(result) == 1:
        return []
    return result


def process_json_to_srt(json_file: str, srt_file: str):    
    """
    Process a Whisper JSON file: parse, clean, and output as SRT.
    
    Args:
        json_file: Input _whisper.json file path
        srt_file: Output _cleaned.srt file path
    """
    subtitles = parse_whisper_json(json_file)
    cleaned = clean_subtitles(subtitles)
    with open(srt_file, 'w', encoding='utf-8') as f:
        f.write(reassemble_srt(cleaned))


# Main entry point for Snakemake
process_json_to_srt(snakemake.input.json, snakemake.output.cleaned)