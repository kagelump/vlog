
SD_CARD_ROOTS = ["/Users/ryantseng/Desktop/2025 Tokyo High and Seek/Pocket"]
PREVIEW_FOLDER = "/Users/ryantseng/Movies/temp_preview"
FORMATS = ['mp4', 'mov', 'MP4', 'MOV']

from pathlib import Path
import os

def get_all_files(roots, formats):
    results = []
    for root in roots:
        p = Path(root)
        all_files = []
        for ext in formats:
            all_files.extend(p.rglob(f"*.{ext}"))
        results.extend([{
            "basename": f.stem,
            "fullpath": str(f),
            "ext": f.suffix.lstrip("."),
        } for f in all_files])
    print(f"Discovered {len(results)} files in {root}")
    return results

ALL_INPUTS = get_all_files(SD_CARD_ROOTS, FORMATS)

rule copy_all:
    input:
        expand(f"{PREVIEW_FOLDER}/{{stem}}_preview.mp4", stem=[f["basename"] for f in ALL_INPUTS])

rule copy_sd_to_preview:
    input:
        lambda wildcards: next(
            f["fullpath"] for f in ALL_INPUTS if f["basename"] == wildcards.stem
        )
    output:
        f"{PREVIEW_FOLDER}/{{stem}}_preview.{{ext}}"
    shell:
        """
        mkdir -p "{PREVIEW_FOLDER}"
        ffmpeg -i "{input}" -c:v libx264 -crf 23 -preset medium -vf "scale=1920:1080" -c:a aac -b:a 128k "{output}"
        """