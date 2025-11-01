import json
import os

from vlog.describe import (
    DEFAULT_PROMPT_PATH,
    load_prompt_template,
    render_prompt,
    validate_model_output,
)


def test_render_prompt_contains_subtitle():
    tpl = load_prompt_template(DEFAULT_PROMPT_PATH)
    out = render_prompt(tpl, "This is a subtitle")
    assert "This is a subtitle" in out


def test_validate_model_output_accepts_expected_shape():
    fake = {
        "description": "A short description",
        "short_name": "a_short_name",
        "primary_shot_type": "insert",
        "tags": ["static", "closeup"],
        "thumbnail_frame": 10,
        "rating": 0.8,
        "camera_movement": "still",
        "in_timestamp": "00:00:00.000",
        "out_timestamp": "00:00:02.500",
    }
    parsed = validate_model_output(fake)
    assert parsed["short_name"] == "a_short_name"
    assert isinstance(parsed["tags"], list)

