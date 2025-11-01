From scratch

1. Install homebrew
2. brew install --cask miniconda
3. brew install python
4. pip install -U mlx-vlm
5. pip install torch torchvision
6. pip install flask

Try out mlx-vlm first

Using [this model](https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-8bit)

```
mlx_vlm.video_generate --model mlx-community/Qwen3-VL-4B-Instruct-8bit --max-tokens 100 --prompt "Describe this video" --video path/to/video.mp4 --max-pixels 224 224 --fps 1.0
```

## Project Structure

The project follows modern Python project organization conventions:

```
vlog/
├── src/vlog/          # Main Python package
│   ├── db.py          # Database operations
│   ├── video.py       # Video processing utilities
│   ├── describe.py    # Video description using ML models
│   ├── web.py         # Flask web server
│   └── ...            # Other modules
├── scripts/           # Executable shell scripts
│   ├── ingest.sh      # Main ingestion pipeline
│   └── transcribe.sh  # Video transcription
├── static/            # Web assets
│   └── index.html     # Web UI
├── third_party/       # External dependencies
└── README.md
```

## Usage

To run the ingestion pipeline:

```bash
cd /path/to/video/directory
/path/to/vlog/scripts/ingest.sh
```

To start the web server:

```bash
cd /path/to/vlog
PYTHONPATH=src python3 src/vlog/web.py
```

## Third-party submodules

This repository includes an external dependency checked in as a git submodule at `third_party/mlx-vlm`.

If you clone this repository for the first time, initialize submodules with:

```bash
git submodule update --init --recursive
```

To update the submodule to the latest commit from its tracked remote:

```bash
git submodule update --remote --merge --recursive
```
