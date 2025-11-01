#!/usr/bin/env bash
set -euo pipefail

# Helper script to provision a uv environment for this project and install mlx-vlm
# Usage: ./scripts/setup_uv.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "Ensure 'uv' is installed (https://docs.astral.sh/uv)."

echo "Pinning Python to 3.11 (you can change this)"
uv python pin 3.11

echo "Creating project venv"
uv venv

echo "Adding runtime dependencies (example: flask)"
uv add flask

echo "Installing mlx-vlm from GitHub into the uv env (editable/local option shown below)"
# Install from github
uv run -- python -m pip install git+https://github.com/Blaizzy/mlx-vlm.git

# If you have a local copy in third_party/mlx-vlm and prefer editable install, uncomment:
# uv run -- python -m pip install -e third_party/mlx-vlm

echo "Locking and syncing the environment"
uv lock || true
uv sync || true

echo "Done. Use 'uv run -- python web.py' or 'uv run -- python src/vlog/describe.py' to run scripts."
