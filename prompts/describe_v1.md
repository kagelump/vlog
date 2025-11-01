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

Identify the best segment(s) of the clip to keep. For each segment, provide the in and out timestamps.
Try to cut out any unneeded parts at the start (eg reframing) or end.
If the clip is very long or has multiple distinct good segments, you can specify multiple segments.
Each segment should be a continuous portion worth keeping.

Use JSON as output, using the following keys:

    * 'description' (str)
    * 'short_name' (str)
    * 'primary_shot_type' (str)
    * 'tags' (list of str)
    * 'thumbnail_frame' (int)
    * 'rating' (float)
    * 'camera_movement' (str)
    * 'segments' (list of objects with 'in_timestamp' (str "HH:MM:SS.sss") and 'out_timestamp' (str "HH:MM:SS.sss"))

For backwards compatibility, also include these (they should match the first segment):
    * 'in_timestamp' (str "HH:MM:SS.sss") - same as segments[0].in_timestamp
    * 'out_timestamp' (str "HH:MM:SS.sss") - same as segments[0].out_timestamp
