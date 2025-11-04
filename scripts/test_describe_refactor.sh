#!/bin/bash
# Quick test script for the new describe architecture

set -e

echo "=== Testing Video Description Architecture ==="
echo

# Test 1: Check imports
echo "1. Testing library imports..."
python3 -c "
from vlog.describe_lib import (
    describe_video, load_model, load_prompt_template,
    calculate_adaptive_fps, Segment, DescribeOutput
)
print('✅ Library imports successful')
"

# Test 2: Check daemon module
echo
echo "2. Testing daemon module..."
python3 -m vlog.describe_daemon --help > /dev/null
echo "✅ Daemon module OK"

# Test 3: Check client module
echo
echo "3. Testing client module..."
python3 -m vlog.describe_client --help > /dev/null
echo "✅ Client module OK"

# Test 4: Check backward compatibility
echo
echo "4. Testing backward compatibility..."
python3 -c "
from vlog.describe import describe_and_insert_video, describe_videos_in_dir
print('✅ Backward compatibility OK')
"

# Test 5: Check adaptive FPS calculation
echo
echo "5. Testing adaptive FPS calculation..."
python3 -c "
from vlog.describe_lib import calculate_adaptive_fps
assert calculate_adaptive_fps(60, 1.0) == 1.0, 'Short video FPS incorrect'
assert calculate_adaptive_fps(150, 1.0) == 0.5, 'Medium video FPS incorrect'
assert calculate_adaptive_fps(350, 1.0) == 0.25, 'Long video FPS incorrect'
print('✅ Adaptive FPS calculation correct')
"

# Test 6: Check prompt template loading
echo
echo "6. Testing prompt template loading..."
python3 -c "
from vlog.describe_lib import load_prompt_template
import os
template = load_prompt_template('prompts/describe_v1.md')
if os.path.exists('prompts/describe_v1.md'):
    assert len(template) > 0, 'Template should not be empty'
    print('✅ Prompt template loading OK')
else:
    # Fallback behavior
    assert template == 'Describe this video.', 'Fallback template incorrect'
    print('✅ Prompt template fallback OK')
"

echo
echo "=== All Tests Passed! ==="
echo
echo "To test with a real video:"
echo "  python3 -m vlog.describe_client /path/to/video.mp4"
echo
echo "To start the daemon:"
echo "  python3 -m vlog.describe_daemon"
echo
echo "For more info, see:"
echo "  docs/DESCRIBE_ARCHITECTURE.md"
echo "  docs/DESCRIBE_REFACTORING.md"
