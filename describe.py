import os
import json
import time
from db import check_if_file_exists, insert_result, initialize_db
from mlx_vlm import load
from mlx_vlm.video_generate import generate  # or the appropriate import
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
from mlx_vlm.video_generate import process_vision_info
import mlx.core as mx
from video import get_video_length_and_timestamp, get_video_thumbnail

DEAFULT_PROMPT = """
You are an expert film editor and cinematographer. 
Analyze the provided video and classify its shot type according to my internal system, which is .
Describe this video clip using 1-2 sentences. 
Then give it a short name to use as a filename.  Use snake_case.

Determine the primary shot type - based on standard film and editing terminology — choose one of the following:

* pov: The camera represents the perspective of a character or subject.
* insert: A close-up or detailed shot of an object, text, or small action that provides specific information.
* establishing: A wide or introductory shot that sets the scene or location context.

Add descriptive tags that apply to the shot. Choose all that fit from the following list:

* static: The camera does not move.
* dynamic: The camera moves (pans, tilts, tracks, zooms, etc.).
* closeup: Tight framing around a person's face or an object.
* medium: Frames the subject roughly from the waist up.
* wide: Shows the subject and significant background context.

Find the most best frame to use as a video thumbnail.
The thumbnail should have good visual quality, focused subject, and/or representativeness.

Give a rating of the quality of the clip from 0.0 for poor quality to 1.0 for great quality.

Classify the camera movement as still, panning, moving forward, or random.
Provide the in and out timestamps for the best segment of the clip to keep.  
Try to cut out any unneeded parts at the start (eg reframing) or end.

Use JSON as output, using the following keys:

    * 'description' (str)
    * 'short_name' (str)
    * 'primary_shot_type' (str)
    * 'tags' (list of str)
    * 'thumbnail_frame' (int)
    * 'rating' (float)
    * 'camera_movement' (str)
    * 'in_timestamp' (str "HH:MM:SS.sss")
    * 'out_timestamp' (str "HH:MM:SS.sss")
"""

def describe_video(
        model, processor, config, video_path, prompt="Describe this video", 
        fps=1.0, subtitle=None, max_pixels=224*224, **generate_kwargs):
    """
    Describe a single video using mlx-vlm.
    """
    # create message format (this is inferred from how video inference is done in mlx-vlm)  
    if subtitle:
        prompt += f"\n\n# Transcript for this video:\n\n{subtitle}\n"
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
    
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text],
        images=image_inputs,  # often empty for pure video
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
        video_metadata={'fps': fps, 'total_num_frames': video_inputs[0].shape[0]}
    )

    

    input_ids = mx.array(inputs["input_ids"])
    mask = mx.array(inputs["attention_mask"])
    video_grid_thw = mx.array(inputs["video_grid_thw"])

    # include kwargs for video layout grid info
    extra = {"video_grid_thw": video_grid_thw}

    pixel_values = inputs.get(
            "pixel_values_videos", inputs.get("pixel_values", None)
        )
    if pixel_values is None:
        raise ValueError("Please provide a valid video or image input.")
    pixel_values = mx.array(pixel_values)

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
        raise Exception(f'Could not deserialize {response.text}')

def load_subtitle_file(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def describe_videos_in_dir(directory, model_name, prompt="Describe this video", fps=1.0, **generate_kwargs):
    """
    Iterate through video files in `directory` and generate descriptions.
    Returns a dict mapping filename → description.
    """
    # load model & processor & config
    model, processor = load(model_name)
    config = load_config(model_name)

    results = {}
    for fname in sorted(os.listdir(directory)):
        if not fname.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            print('Skipping non-video file:', fname)
            continue
        f = check_if_file_exists(fname)
        if f:
            print('Already processed', f)
            continue
        full = os.path.join(directory, fname)
        if not os.path.isfile(full):
            continue

        subtitle_file = os.path.splitext(full)[0] + '.srt'
        subtitle_text = load_subtitle_file(subtitle_file)

        video_length, video_timestamp = get_video_length_and_timestamp(full)
        if video_length > 120:
            fps = fps / 2.0
        if video_length > 300:
            fps = fps / 2.0
        # filter by extension (e.g. .mp4, .mov, .avi). adjust as needed
        ext = os.path.splitext(fname)[1].lower()

        start_time = time.time()
        if ext not in (".mp4", ".mov", ".avi", ".mkv"):
            continue
        try:
            desc = describe_video(
                model, processor, config, full, prompt=prompt, 
                fps=fps, subtitle=subtitle_text, **generate_kwargs)
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        desc['timing_sec'] = time.time() - start_time
        print(fname, desc)
        results[fname] = desc
        thumbnail_frame = int(desc['thumbnail_frame'])
        thumbnail_base64 = get_video_thumbnail(full, thumbnail_frame, fps)
        insert_result(
            fname, desc['description'], desc['short_name'],  
            desc.get('clip_type'), time.time() - start_time, model_name, video_length,
            video_timestamp, thumbnail_base64, desc.get('in_timestamp'), desc.get('out_timestamp'),
            desc.get('rating', 0.0))
    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Describe all videos in a directory.")
    parser.add_argument("directory", type=str, help="Path to the directory containing videos")
    # 8B is good enough, Thinking would be better but too slow.  30B would not run well in 24GB RAM.
    parser.add_argument("--model", type=str, default="mlx-community/Qwen3-VL-8B-Instruct-4bit",
                        help="The model path to use in mlx-vlm")
    parser.add_argument("--prompt", type=str, default=DEAFULT_PROMPT,
                        help="Prompt to pass to the model for describing videos")
    parser.add_argument("--fps", type=float, default=1.0, help="Frames per second to sample from video")
    parser.add_argument("--max_pixels", type=int, default=224*224, help="Max pixel size for frames")
    parser.add_argument("--max_tokens", type=int, default=10000, help="Max generation tokens")
    args = parser.parse_args()
    initialize_db()

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
