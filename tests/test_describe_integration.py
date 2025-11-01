import json

import pytest

from vlog import describe


class FakeProcessor:
    def __init__(self):
        self._applied = None

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        # return a simple text representation
        return "PROMPT_TEXT"

    def __call__(self, text=None, images=None, videos=None, padding=True, return_tensors=None, video_metadata=None):
        # Return the minimal dict the code expects
        return {
            "input_ids": [1, 2, 3],
            "attention_mask": [1, 1, 1],
            "video_grid_thw": [1, 2, 3],
            # Provide pixel_values_videos so the code picks it up
            "pixel_values_videos": [[[[0]]]]
        }


class DummyVideoInput:
    def __init__(self, frames=3):
        # shape[0] will be used by the code
        self.shape = (frames,)


def test_describe_video_integration_monkeypatched(monkeypatch, tmp_path):
    # Prepare a fake model response that matches our DescribeOutput schema
    fake_response = {
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

    class FakeResponse:
        def __init__(self, text):
            self.text = text

    # Monkeypatch the heavy functions in the module
    monkeypatch.setattr(describe, "process_vision_info", lambda messages: ([], [DummyVideoInput(3)]))

    def fake_generate(*args, **kwargs):
        return FakeResponse(json.dumps(fake_response))

    monkeypatch.setattr(describe, "generate", fake_generate)

    # Monkeypatch mx.array to be identity to avoid dependency on MX runtime
    monkeypatch.setattr(describe.mx, "array", lambda x: x)

    processor = FakeProcessor()
    model = object()
    config = {}

    # Call describe_video; it should return validated dict
    out = describe.describe_video(model, processor, config, str(tmp_path / "video.mp4"), prompt=None, fps=1.0, subtitle="sub")

    assert isinstance(out, dict)
    assert out["short_name"] == "a_short_name"
    assert out["tags"] == ["static", "closeup"]