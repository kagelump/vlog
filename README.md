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
