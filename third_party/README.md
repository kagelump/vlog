# Third-party dependencies

This folder contains third-party code included as git submodules.

## mlx-vlm

The project includes `mlx-vlm` as a git submodule at `third_party/mlx-vlm`.

Cloning the repository (first time):

```bash
git clone --recurse-submodules <this-repo-url>
# or if already cloned:
git submodule update --init --recursive
```

Updating the submodule to the latest tracked remote:

```bash
git submodule update --remote --merge --recursive
# or enter the submodule and use git pull
cd third_party/mlx-vlm
git fetch origin
git checkout main
git pull
cd ../..
```

If you prefer not to use submodules, copy the upstream code into `third_party/mlx-vlm` or use `git subtree`.
