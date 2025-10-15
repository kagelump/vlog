import os
import json
import time
from db import VideoDBManager
from mlx_vlm import load
from mlx_vlm.video_generate import generate  # or the appropriate import
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
from mlx_vlm.video_generate import process_vision_info
import mlx.core as mx
from video import get_video_length_and_timestamp, get_video_thumbnail

DEAFULT_PROMPT = """
Describe this video clip using 1-2 sentences. 
Then give it a short name to use as a filename.  Use snake_case.
Classify the clip as a talking, transit, establishing, action shot, etc, or other (explain) type of clip?

    * talking - There is a main subject who is talking to the camera.
    * transit - Transiting from one place to another.
    * establishing - Setting the environment, usually ambiance
    * food - Showcasing food or subjects eating
    * action - Subjects in the shot are doing an activity
    * closeup - Tight focus on a small object, texture, or specific detail

Find the most best frame to use as a video thumbnail.
The thumbnail should have good visual quality, focused subject, and/or representativeness.

Give a rating of the quality of the clip from 0.0 for poor quality to 1.0 for great quality.

Use JSON as output, using the following keys:

    * 'description' (str)
    * 'short_name' (str)
    * 'clip_type' (str)
    * 'thumbnail_frame' (int)
    * 'rating' (float)
"""

def describe_video(model, processor, config, video_path, prompt="Describe this video", fps=1.0, max_pixels=224*224, **generate_kwargs):
    """
    Describe a single video using mlx-vlm.
    """
    # create message format (this is inferred from how video inference is done in mlx-vlm)  
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": video_path,
                    "fps": fps,
                    "max_pixels": max_pixels,
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]

    # format prompt
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    # process vision info (videos etc) — convert to model-ready inputs
    
    image_inputs, video_inputs, fps = process_vision_info(messages, return_video_kwargs=True)

    inputs = processor(
        text=[text],
        images=image_inputs,  # often empty for pure video
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    

    input_ids = mx.array(inputs["input_ids"])
    pixel_values = mx.array(inputs["pixel_values_videos"])
    mask = mx.array(inputs["attention_mask"])
    video_grid_thw = mx.array(inputs["video_grid_thw"])

    # include kwargs for video layout grid info
    extra = {"video_grid_thw": video_grid_thw}

    response = generate(
        model=model,
        processor=processor,
        prompt=text,
        input_ids=input_ids,
        pixel_values=pixel_values,
        mask=mask,
        **extra,
        **generate_kwargs,
    )

    try:
        return json.loads(response.text)
    except Exception:
        raise Exception('Could not deserialize {response.text}')

def describe_videos_in_dir(directory, model_name, prompt="Describe this video", fps=1.0, **generate_kwargs):
    """
    Iterate through video files in `directory` and generate descriptions.
    Returns a dict mapping filename → description.
    """
    # load model & processor & config
    model, processor = load(model_name)
    config = load_config(model_name)
    db = VideoDBManager()

    results = {}
    for fname in sorted(os.listdir(directory)):
        f = db.check_if_file_exists(fname)
        if f:
            print('Already processed', f)
            continue
        full = os.path.join(directory, fname)
        if not os.path.isfile(full):
            continue
        video_length, video_timestamp = get_video_length_and_timestamp(full)
        if video_length > 150:
            fps = fps / 2.0
        if video_length > 300:
            fps = fps / 2.0
        # filter by extension (e.g. .mp4, .mov, .avi). adjust as needed
        ext = os.path.splitext(fname)[1].lower()
        start_time = time.time()
        if ext not in (".mp4", ".mov", ".avi", ".mkv"):
            continue
        try:
            desc = describe_video(model, processor, config, full, prompt=prompt, fps=fps, **generate_kwargs)
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        desc['timing_sec'] = time.time() - start_time
        print(fname, desc)
        results[fname] = desc
        thumbnail_frame = int(desc['thumbnail_frame'])
        thumbnail_base64 = get_video_thumbnail(full, thumbnail_frame, fps)
        db.insert_result(
            fname, desc['description'], desc['short_name'],  
            desc.get('clip_type'), time.time() - start_time, model_name, video_length,
            video_timestamp, thumbnail_base64)
    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Describe all videos in a directory.")
    parser.add_argument("directory", type=str, help="Path to the directory containing videos")
    parser.add_argument("--model", type=str, default="mlx-community/Qwen3-VL-8B-Instruct-4bit",
                        help="The model path to use in mlx-vlm")
    parser.add_argument("--prompt", type=str, default=DEAFULT_PROMPT,
                        help="Prompt to pass to the model for describing videos")
    parser.add_argument("--fps", type=float, default=1.0, help="Frames per second to sample from video")
    parser.add_argument("--max_pixels", type=int, default=224*224, help="Max pixel size for frames")
    parser.add_argument("--max_tokens", type=int, default=200, help="Max generation tokens")
    args = parser.parse_args()

    descs = describe_videos_in_dir(
        args.directory,
        args.model,
        prompt=args.prompt,
        fps=args.fps,
        max_pixels=args.max_pixels,
        max_tokens=args.max_tokens,
        temperature=0.7,
    )
    for fname, desc in descs.items():
        print(f"--- {fname} ---")
        print(desc)
        print()
