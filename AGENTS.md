# Repository Guidelines

## Project Structure & Module Organization

This repository is an early-stage video captioning agent prototype. Core design and requirements live in `DESIGN.md` and `video_captioning_agent_spec.md`; keep implementation decisions aligned with these documents. Utility scripts currently live at the repository root:

- `fireworks_test_deployment.py` tests Fireworks VLM access and frame-sampled video understanding.
- `upload_model_to_fireworks.py` uploads a local Hugging Face model snapshot to Fireworks.
- `remove_out_of_bound_video_clips.py` and `find_extensions.py` support dataset inspection.
- `docs/` stores dated notes and supporting research.
- `Data/` is local dataset material and should not be treated as source code.

If the agent grows beyond scripts, place reusable Python modules under `src/` and tests under `tests/`.

## Build, Test, and Development Commands

Use Python 3.10+ in the existing virtual environment or create one locally.

- `python fireworks_test_deployment.py --mode image-sanity` verifies Fireworks authentication and deployment health.
- `python fireworks_test_deployment.py --mode video --video-path /path/to/clip.mp4 --num-frames 8` tests frame sampling plus video understanding.
- `python remove_out_of_bound_video_clips.py` inspects local video durations with `ffprobe`.
- `python find_extensions.py` lists file extensions in a configured dataset directory.

Install missing dependencies as needed, for example `pip install python-dotenv requests opencv-python pandas matplotlib`.

## Coding Style & Naming Conventions

Write Python with 4-space indentation, clear function names, and small, single-purpose helpers. Prefer `pathlib.Path` for filesystem work and environment variables for credentials. Use uppercase names for constants such as `MODEL_ID`, `FIREWORKS_URL`, and `ROOT_DIR`. Keep script entry points behind `if __name__ == "__main__":` when adding new executable files.

## Testing Guidelines

There is no formal test suite yet. For now, validate changes with the closest runnable script, especially `fireworks_test_deployment.py` for model/API behavior. When adding tests, use `pytest`, name files `tests/test_*.py`, and keep sample media small or mocked. Do not require large local datasets for routine tests.

## Commit & Pull Request Guidelines

Git history currently contains only `initial commit`, so use concise imperative commit messages going forward, for example `Add frame sampler fallback` or `Document Fireworks setup`. Pull requests should include a short summary, commands run, required environment variables, linked issue or task context, and any dataset/model assumptions. Include screenshots or sample JSON only when output format or visual behavior changes.

## Security & Configuration Tips

Never commit `.env`, API keys, signed upload URLs, model weights, or large dataset files. Read `FIREWORKS_API_KEY` from the environment. Keep hardcoded local paths limited to throwaway analysis scripts, and document any required external tools such as `ffprobe`.
