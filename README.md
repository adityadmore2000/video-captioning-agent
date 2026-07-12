# Video Captioning Agent

A prototype pipeline that produces styled video captions from one internal Canonical Video Report (CVR) per video. Vision understanding is performed exactly once per video; each requested caption style is then generated from the CVR alone, isolating factuality from stylistic phrasing.

Supported caption styles (exhaustive): `Formal`, `Sarcastic`, `Humorous-Tech`, `Humorous-Non-Tech`.

For the full design see [`DESIGN.md`](DESIGN.md), [`video_captioning_agent_spec.md`](video_captioning_agent_spec.md), and [`TASKS.md`](TASKS.md).

---

## How it works

For each task in `/input/tasks.json`, the agent:

1. Reads and structurally validates the task entry (`task_id`, `video_url`, `styles`).
2. Filters requested styles down to the supported set.
3. Downloads the video into a per-run temporary directory (failure-isolated per task).
4. Inspects the downloaded media with OpenCV (readability check + metadata).
5. Samples up to 16 chronological frames at a 768px max dimension, with a 1 fps sequential fallback when frame-count metadata is unavailable.
6. Calls Fireworks `Qwen2.5-VL 32B Instruct` (vision mode, `temperature=0.1`) exactly once to produce a CVR.
7. Parses and validates the CVR against a strict five-field schema (`scene`, `primary_subjects`, `important_objects`, `timeline`, `overall_summary`).
8. For each supported requested style, calls the same model in text-only mode (`temperature=0.2`) sending only the serialized CVR.
9. Validates captions (non-empty, requested style) and logs a warning if a caption exceeds ~100 words.
10. Writes `/output/results.json` atomically as a top-level JSON array.

Task-level failures do not terminate the batch: failed tasks yield empty strings for each of their requested styles, and the pipeline always exits with code `0` after writing a valid `results.json`.

---

## Input / output contract

### Input: `/input/tasks.json`

```json
[
  {
    "task_id": "v1",
    "video_url": "https://example.com/clip.mp4",
    "styles": ["Formal", "Sarcastic", "Humorous-Tech", "Humorous-Non-Tech"]
  }
]
```

- `task_id`: non-empty string. Duplicate IDs cause all tasks with that ID to be skipped.
- `video_url`: non-empty string. Invalid URLs and timeouts are treated as per-task failures.
- `styles`: list of non-empty strings. Unsupported styles are defensively ignored (not expected in valid input).

### Output: `/output/results.json`

```json
[
  {
    "task_id": "v1",
    "captions": {
      "formal": "...",
      "sarcastic": "...",
      "humorous_tech": "...",
      "humorous_non_tech": "..."
    }
  }
]
```

Each result object contains only the styles the task requested, using lowercase/snake_case keys. A missing or failed caption is represented by an empty string, never a missing key. The `/output` directory is created if it does not exist.

---

## Prerequisites

- Python 3.10+ (Python 3.12 in the Docker image)
- A Fireworks account with access to `Qwen2.5-VL 32B Instruct`
- `FIREWORKS_API_KEY` set in the environment

Python dependencies (see [`requirements.txt`](requirements.txt)):

```
requests>=2.31,<3
opencv-python-headless>=4.10,<5
Pillow>=10,<12
```

Optional local dev dependencies: `pytest` for the test suite.

---

## Running locally

### 1. Set up the environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest   # only for running the test suite
export FIREWORKS_API_KEY=...
```

### 2. Run the pipeline with default `/input` and `/output`

The entrypoint expects the POSIX paths `/input/tasks.json` and `/output/results.json`. The simplest way to provide them is to mount bind paths in Docker (see below) or, inside a Linux environment where those paths are writable:

```bash
PYTHONPATH=src python -m video_captioning_agent.pipeline
```

To run with custom paths from Python (e.g. for ad-hoc local runs), call `run_pipeline()`:

```python
from pathlib import Path
from video_captioning_agent.pipeline import run_pipeline

run_pipeline(
    input_path=Path("./my_tasks.json"),
    output_path=Path("./my_results.json"),
)
```

### 3. Verify Fireworks access (optional sanity checks)

`fireworks_test_deployment.py` provides two lightweight health checks against the deployed VLM:

```bash
# Verify Fireworks authentication and deployment health.
python fireworks_test_deployment.py --mode image-sanity

# Test frame sampling + video understanding against a local clip.
python fireworks_test_deployment.py --mode video --video-path /path/to/clip.mp4 --num-frames 8
```

---

## Running in Docker

The [`Dockerfile`](Dockerfile) builds a slim Python 3.12 image that copies only the runtime sources under `src/` and installs `requirements.txt`. The entrypoint is:

```
ENTRYPOINT ["python", "-m", "video_captioning_agent.pipeline"]
```

Build and run with mounted `/input` / `/output` volumes:

```bash
docker build -t video-captioning-agent .

mkdir -p ./input ./output
cp my_tasks.json ./input/tasks.json

docker run --rm \
  -e FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  -v "$(pwd)/input:/input:ro" \
  -v "$(pwd)/output:/output" \
  video-captioning-agent
```

Results are written to `./output/results.json`. The container always exits with code `0` as long as `results.json` can be written. The image is well under the 10 GB compressed-image cap described in the spec.

---

## Running the tests

The test suite (pytest, mocked network/model calls + small fixture media) lives under [`tests/`](tests/). From the repo root:

```bash
PYTHONPATH=src pytest -q
```

No real `FIREWORKS_API_KEY` or large dataset is required. Each test file corresponds to a single pipeline stage (e.g. `test_cvr_client.py`, `test_frame_sampler.py`, `test_pipeline.py`); `test_pipeline.py` exercises the full mocked end-to-end flow including per-task failure isolation.

---

## Project layout

```
.
├── src/video_captioning_agent/
│   ├── contracts.py          # VideoTask, CVR, FrameSample, VideoMetadata, TaskResult
│   ├── input_loader.py       # /input/tasks.json parsing + structural validation
│   ├── styles.py             # Supported style set + task eligibility
│   ├── downloader.py         # Bounded, per-task failure-isolated downloads
│   ├── video_inspection.py   # OpenCV readability + metadata extraction
│   ├── frame_sampler.py      # Uniform sampling + sequential 1 fps fallback
│   ├── cvr_client.py         # CVR prompt construction + Fireworks VLM client
│   ├── cvr_parser.py         # Strict JSON/CVR validation, no fact fabrication
│   ├── style_generator.py    # CVR-only text requests for each requested style
│   ├── caption_validation.py # Non-empty + concision (warn-only) validation
│   ├── result_writer.py      # Atomic /output/results.json serialization
│   └── pipeline.py           # Sequential orchestration with failure isolation
├── tests/                    # pytest suite, one file per stage
├── Dockerfile                # Runtime container image
├── requirements.txt          # Runtime dependencies only
├── fireworks_test_deployment.py  # Optional manual Fireworks sanity script
└── AGENTS.md / DESIGN.md / video_captioning_agent_spec.md / TASKS.md
```

---

## Notes and limitations

- **Audio is out of scope**; captioning is visual-only.
- **No programmatic caption factuality verifier** in this pass — the primary safeguard is CVR-only input isolation at the style-generation stage (see `TASKS.md` → Future Scope).
- **Frame padding is intentionally disabled**: short or degraded videos return only the unique frames that could actually be read.
- Never commit `.env`, `FIREWORKS_API_KEY`, signed upload URLs, model weights, or large dataset files. The Fireworks API key is read from the environment, never hardcoded.