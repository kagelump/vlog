import os
import re
import mlx.core as mx
from mlx_lm import load, generate

TARGET_DIRECTORY = "." 
OUTPUT_SUFFIX = "_cleaned.srt"

import re
from collections import Counter
from typing import List


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

def parse_srt(filepath):
    """
    Reads an SRT file, separates it into subtitle blocks, and returns the segments 
    list (for index/time preservation) and a single string of all subtitle text 
    content joined by a delimiter (for full context LLM processing).
    """
    print(f"Reading {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find each block: index, timestamps, and text.
    srt_blocks = re.findall(
        r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n\d+|$)',
        content,
        re.DOTALL
    )

    subtitles = []
    for index, time, text in srt_blocks:
        text_only = text.strip()
        subtitles.append({
            # NOTE: We store the original index, but it will be overwritten during reassembly
            'index': int(index),
            'time': time.strip(),
            'text': text_only
        })

    return subtitles

def reassemble_srt(subtitles):
    """
    Takes the list of subtitle dictionaries and formats it back into a valid SRT string.
    Crucially, it re-indexes the output sequentially and skips segments with empty text.
    """
    output = []
    new_index = 1
    for sub in subtitles:
        # Only include non-empty text segments in the output file
        if sub['text']:
            # Use the new sequential index for the final output
            output.append(f"{new_index}")
            output.append(sub['time'])
            output.append(sub['text'])
            output.append("") # Empty line separator
            new_index += 1
    
    # Join all parts with newlines, ensuring no trailing newline at the very end
    return "\n".join(output).strip()

def clean_subtitles(subtitles):
    """Cleans subtitle file text using the LLM in a single full-context pass."""
    pass1 = []
    removed = set()
    for sub in subtitles:
        last_sub_text = pass1[-1]['text'] if pass1 else ""
        if (sub['text'].strip() == last_sub_text.strip() 
            or is_hallucination_by_repetition(sub['text'])):
            # Skip duplicate subtitle text
            print(f"Skipping duplicate subtitle text: {sub['time']} {sub['text']}")
            removed.add(sub['text'])
            continue
        print(f"OK subtitle text: {sub['time']} {sub['text']}")
        pass1.append(sub)
    
    result = []
    for sub in pass1:
        if sub['text'] in removed:
            print(f"Removing subtitle text found in removed set: {sub['time']} {sub['text']}")
            continue
        result.append(sub)
    
    if (len(result) == 1):
        return []
    return result


def process_srt_file(filename):    
    """
    Process a single SRT file: parse, clean, and reassemble.
    """
    subtitles = parse_srt(filename)
    output = clean_subtitles(subtitles)
    return reassemble_srt(output)

if __name__ == "__main__":
    process_srt_files()
