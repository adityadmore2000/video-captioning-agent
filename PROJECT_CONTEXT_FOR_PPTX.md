# Video Captioning Agent — Project Context (for PowerPoint generation)

Hand this document to Claude. It is a factual summary of the project's current
state, architecture, and decisions. Structure it as a slide deck: one heading
level maps roughly to one slide.

---

## Slide 1 — Title

**Video Captioning Agent**
A multimodal pipeline that turns a single Canonical Video Report (CVR) into
four distinct writing styles per video.

- Status: working prototype (v1), hackathon-ready
- Repo: `/home/aditya/dev-work/video-captioning-agent` (Python 3.10+)
- Key docs on disk: `README.md`, `DESIGN.md`, `video_captioning_agent_spec.md`,
  `TASKS.md`, `EXPERIMENT_TRACKING.md`

## Slide 2 — The Problem

Generate concise captions for unseen videos (30s–2min) in four styles:
- Formal
- Sarcastic
- Humorous-Tech
- Humorous-Non-Tech

Hard constraints:
- Runtime ≤ 10 minutes
- Docker image ≤ 10 GB (compressed)
- Valid `results.json` output, exit code 0
- Missing captions score zero

Core design insight: **separate video understanding from language generation**.
Vision runs once; style is a text-only rewrite of one factual CVR.

## Slide 3 — Architecture (one diagram)

```
tasks.json
   ↓
Video Downloader
   ↓
Video Frame Sampler (OpenCV)
   ↓
Visual LLM: Qwen2.5-VL 32B Instruct
   ↓
Canonical Video Report (CVR)   ← single source of truth
   ↓
Text LLM: Style Rewriter
   ↓
results.json
```

The CVR is an internal artifact — not part of the final submission.
Style generation never sees frames, video, or metadata, only the CVR text.

## Slide 4 — Production Pipeline Stages

1. Load `/input/tasks.json` (validate `task_id`, `video_url`, `styles`)
2. Filter requested styles against the supported set
3. Download video (per-task timeout, failure-isolated)
4. Inspect with OpenCV (readability + metadata)
5. Sample up to 16 chronological frames, max 768px, with 1fps sequential fallback
6. Call Fireworks qwen2p5-vl-32b-instruct ONCE → CVR (temperature 0.1)
7. Parse/validate CVR against a strict schema
8. For all 4 supported styles, call gpt-oss-120b in text-only mode (temperature 0.2)
9. Validate captions (non-empty, ~100-word soft warning)
10. Write `/output/results.json` atomically; always exit 0

Concurrency model: vision stage is sequential per video; style generation for
task N runs as a background `Future` that overlaps task N+1's vision call.

## Slide 5 — Models

| Stage | Model | Provider | temperature | max_tokens |
|---|---|---|---|---|
| CVR (vision) | qwen2p5-vl-32b-instruct | Fireworks | 0.1 | 1024 |
| Style (text) | gpt-oss-120b | Fireworks | 0.2 | 2048 |

Production runs on serverless pay-per-token Fireworks endpoints.
Dedicated (on-demand) deployments are an open follow-up — see Slide 11.

## Slide 6 — Input / Output Contract

Input `/input/tasks.json`:
```json
[{"task_id":"v1","video_url":"https://.../clip.mp4","styles":["Formal","Sarcastic","Humorous-Tech","Humorous-Non-Tech"]}]
```

Output `/output/results.json`:
```json
[{"task_id":"v1","captions":{"formal":"...","sarcastic":"...","humorous_tech":"...","humorous_non_tech":"..."}}]
```

Rules:
- Top-level JSON array, one object per task
- `captions` contains ONLY styles that task requested
- Failed-but-requested caption → key present, value `""`
- Never-requested style → key absent

## Slide 7 — The Canonical Video Report (CVR)

Strict JSON schema:
- `scene` — location/environment
- `primary_subjects` — list
- `important_objects` — list
- `timeline` — chronological events
- `overall_summary` — one factual sentence

Rules: observable facts only, no speculation, no humor, no inferred emotions,
prefer conservative descriptions over hallucination.

## Slide 8 — Token / Context Budget

Switching from InternVL3-8B (16k context) to Qwen2.5-VL 32B (128k context)
removed the primary pipeline bottleneck:

| Component | Tokens |
|---|---|
| System prompt | ~300 |
| User prompt + schema | ~400 |
| 16 frames @ 768px | ~32,000 |
| Response buffer | 1,024 |
| **Total used** | **~33.7k** |
| Qwen context limit | 128,000 |
| Headroom | ~94k (room to grow to 24 frames) |

## Slide 9 — Engineering Quality

- Pytest suite, one file per pipeline stage, mocked network/models
- Failure isolation: bad tasks yield empty strings; batch always exits 0
- Atomic `results.json` write
- Docker image builds only `src/`, under 1 GB
- No large datasets or secrets in the repo; `FIREWORKS_API_KEY` from env

## Slide 10 — Experiment Tracking (dev-only)

A lightweight MLflow harness under `experiments/`:
- `experiments/run_experiment.py --config experiments/configs/exp_*.yaml`
- `experiments/run_all.py` — batch over every YAML config
- Tracks CVR prompts, frame-sampling params, model/temperature/max_tokens
- SQLite backend (`experiments/mlflow.db`), file artifacts (`experiments/mlruns`)
- NOT part of production Docker image; reuses real `src/` components
- MLflow Compare view used to diff configs side by side

## Slide 11 — Current State & Open Work

Built and working:
- Full `src/` production pipeline (Tasks 1–14 in TASKS.md complete)
- Test suite under `tests/` and `experiments/tests/`
- Docker entrypoint
- MLflow experiment harness

Open this session (in progress, not yet merged):
- **Dedicated Fireworks deployments**: `DEDICATED_DEPLOYMENT_SETUP.md`
  asks for a one-time setup script that provisions on-demand deployments
  for both models and writes their IDs into the experiment YAML.

API reality (discovered by probing live this session):
- `POST /v1/accounts/{account}/deployments` does NOT accept the
  `deploymentId` field the spec describes — Fireworks auto-generates it.
- It REQUIRES `acceleratorType` (and count) — contradicts the spec's
  "let Fireworks pick defaults".

Confirmed working per-model accelerator shapes (via `firectl list
deployment-shape-versions`):
- qwen2p5-vl-32b-instruct: 1× NVIDIA_H200_141GB (minimal) BF16, also 2×H200 throughput/fast
- gpt-oss-20b: 1× NVIDIA_H100_80GB FP4 throughput, 1× H200 FP4 fast/full

No deployment was created this session — billing is currently $0.
The setup script was discarded pending an accelerator decision.

## Slide 12 — Limitations & Future Scope

- Audio is out of scope; captioning is visual-only
- No programmatic caption factuality verifier in this pass
  (CVR-only input isolation is the primary safeguard)
- Frame padding intentionally disabled for short/degraded videos
- Caption factuality verifier (LLM-as-judge) deferred to a future iteration
- Deployment teardown is a separate future utility