# Video Captioning Agent — Implementation Tasks

Source requirements: `video_captioning_agent_spec.md`, `DESIGN.md`, and `AGENTS.md`. The order below follows implementation dependencies. Reusable Python code belongs under `src/`; focused tests belong under `tests/` and use pytest with mocked network/model calls and small fixture media.

> **Local testing note:** A real sample clip is available on the developer's machine for manual/integration verification (not part of the automated pytest suite, since CI/agents don't have filesystem access to it):
> `/home/aditya/dev-work/video-captioning-agent/Data/Charades_v1_480/Charades_v1_480/001YG.mp4`
> Use this path when manually running `fireworks_test_deployment.py --mode video --video-path <path> --num-frames N` locally (Tasks 6, 15) or when validating the container end-to-end (Task 14). Any automated test fixtures committed to the repo should still use small, checked-in sample media — not this path.

## Decisions (resolved — supersede prior Open Questions)

- **Supported styles are fixed and exhaustive:** `Formal`, `Sarcastic`, `Humorous-Tech`, `Humorous-Non-Tech`. Input tasks are only ever expected to request from this set. The "ignore unsupported styles" rule from DESIGN.md §6 remains in code as a defensive fallback but is not expected to be exercised in practice.
- **Style-generation temperature is lowered to `0.2`** (from DESIGN.md's original `0.7`) to satisfy the spec's determinism requirement while retaining some stylistic flexibility. Revisit down to `0` if strict reproducibility is later required.
- **results.json schema (final):**
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
  A top-level JSON array, one object per input task, with a `captions` dict keyed by lowercase/snake_case style name.
- **Duplicate task IDs:** Not expected from valid input. If encountered anyway, treat the same as other invalid/malformed input (do not crash) — log and skip the offending task(s) rather than guessing which one is authoritative.
- **Text-generation model:** Use `Qwen2.5-VL 32B Instruct` (same model as vision understanding, called in text-only mode) for style generation — no separate model needed.
- **Fireworks API endpoint:** `FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"`.
- **Audio:** Out of scope. Visual-only captioning.
- **Output folder handling:** The pipeline must create `/output` if it does not already exist before writing `results.json`.
- **Runtime benchmark:** Spec's hard cap is 10 minutes total. Use DESIGN.md §7's own estimate (~25s/task, ~4-5 min for a 10-task batch) as the representative smoke-test workload for Task 15.
- **Caption factuality enforcement:** Deferred — see "Future Scope" at the end of this document. No programmatic verifier will be built in this implementation pass; captions will rely on prompt design + CVR-only input isolation (Task 10) as the primary safeguard.

## 1. Define the task, frame, CVR, and result data contracts
**Depends on:** none

Create typed, serializable representations for an input task, sampled frame, video metadata, the Canonical Video Report (CVR), and a task result. Make the CVR contract include `scene`, `primary_subjects`, `important_objects`, `timeline`, and `overall_summary`.

**Acceptance criteria (from the specification):**
- The CVR captures scene, primary subjects, important objects, key actions, a timeline of major events, and an overall factual summary. Key actions are represented by timestamped `timeline` entries; the DESIGN.md §4.2 five-field schema intentionally has no separate `key_actions` field.
- The CVR is an internal artifact and is not included in the final submission.

**Independent verification:** Add pytest unit tests for valid serialization and rejection of malformed CVR data.

## 2. Implement input loading and structural validation
**Depends on:** task 1

Read `/input/tasks.json`, parse multiple tasks, and validate the presence and types of `task_id`, `video_url`, and requested styles before processing.

**Acceptance criteria (from the specification):**
- Reads every task from `/input/tasks.json`.
- Supports multiple tasks within a single execution.
- Handles an empty task list, malformed JSON, duplicate task IDs, and missing fields.

**Independent verification:** Add pytest cases for valid multi-task input, empty lists, malformed JSON, duplicates, and each missing field.

## 3. Define supported-style filtering and task eligibility
**Depends on:** tasks 1–2

Implement the supported style set: Formal, Sarcastic, Humorous-Tech, and Humorous-Non-Tech. This is the complete, exhaustive set of styles input tasks are expected to request (see Decisions). Validate/filter requested styles defensively and define a task-level processing outcome for tasks with no supported styles after filtering, even though this path is not expected to trigger given valid upstream input.

**Acceptance criteria (from the specification):**
- Generates one caption for every requested style.
- Handles unsupported styles.
- Supports Formal, Sarcastic, Humorous-Tech, and Humorous-Non-Tech captions.

**Independent verification:** Add pytest cases for every supported style, mixed supported/unsupported requests, and a request with no supported style.

## 4. Implement bounded video download
**Depends on:** task 1

Download each task's video URL to a per-run temporary location using a configurable timeout. Return a structured per-task download failure rather than terminating the run.

**Acceptance criteria (from the specification):**
- Downloads every video.
- Handles invalid URLs and download timeouts.

**Independent verification:** Add pytest tests with mocked HTTP responses for a successful download, invalid URL, timeout, and per-task failure isolation.

## 5. Implement video inspection and readability checks
**Depends on:** task 4

Open downloaded media with OpenCV, collect available metadata, and reject unreadable or empty videos before visual analysis.

**Acceptance criteria (from the specification):**
- Validates that the video is readable.
- Handles corrupted and empty videos.

**Independent verification:** Add pytest tests using a tiny valid fixture video and mocked OpenCV failures for corrupted and empty media.

## 6. Implement uniform frame sampling with metadata fallback
**Depends on:** task 5

Uniformly sample chronological frames across the entire timeline. Use the design configuration of 16 target frames and a 768px maximum dimension; convert frames to RGB and produce JPEG base64 data URLs with timestamps. Fall back to sequential 1 fps reading when frame-count metadata is unusable.

**Acceptance criteria (from the specification):**
- Analyzes the entire video, not only the most salient frame or event.
- Captions summarize the entire video, not isolated moments.
- Handles rapid camera motion, multiple scene transitions, and long videos containing several independent events.

**Independent verification:** Add pytest tests confirming chronological, timeline-wide indices; 768px resizing; RGB/base64 output; timestamps; and the metadata-failure fallback. Run the closest integration check when credentials and a sample clip are available:
```
python fireworks_test_deployment.py --mode video --video-path /home/aditya/dev-work/video-captioning-agent/Data/Charades_v1_480/Charades_v1_480/001YG.mp4 --num-frames 8
```

## 7. Build the CVR request and vision-model client
**Depends on:** tasks 1 and 6

Construct the CVR system and user prompts from DESIGN.md, including ordered timestamps and the strict JSON schema. Call the configured Fireworks Qwen VLM with low-temperature factual generation (`temperature=0.1`, `max_tokens=1024`) and obtain exactly one CVR response per video.

**Acceptance criteria (from the specification):**
- Produces one Canonical Video Report internally for every video.
- Video understanding is performed exactly once per video.
- Visual understanding is the primary source of information.

**Independent verification:** Add pytest tests that mock the API and assert the request includes ordered frame data, timestamps, metadata, required prompt constraints, and one call per video. With `FIREWORKS_API_KEY` configured, run `python fireworks_test_deployment.py --mode image-sanity`.

## 8. Parse and validate CVR responses conservatively
**Depends on:** tasks 1 and 7

Parse the VLM response as JSON and validate it against the CVR contract. Reject non-JSON, additional prose, missing required fields, and invalid field types as a per-task CVR failure; do not fabricate recovery facts.

**Acceptance criteria (from the specification):**
- The CVR contains only observable facts.
- The CVR does not contain humor, speculation, inferred emotions, intentions, or unsupported events.
- When uncertainty exists, the system prefers conservative factual descriptions over hallucinated details.

**Independent verification:** Add pytest tests for valid JSON, markdown or prose-wrapped JSON, malformed JSON, and invalid/missing CVR fields.

## 9. Add CVR factual-boundary and timeline prompt tests
**Depends on:** tasks 7–8

Test the CVR-prompt construction to ensure it directs the model to describe observable facts only, preserve chronology, prioritize important events, and omit unclear entities. Keep this validation at the prompt/contract boundary; model-output quality evaluation is a separate concern.

**Acceptance criteria (from the specification):**
- The understanding identifies primary subjects, important objects, scene/environment, actions, interactions, temporal progression, state changes, and overall context.
- The CVR prioritizes semantically important information over exhaustive scene description.

**Independent verification:** Add pytest assertions for the generated CVR prompt directives and schema, including chronological timestamps.

## 10. Implement CVR-only style-generation requests
**Depends on:** tasks 1, 3, and 8

For each supported requested style, send only the serialized CVR and target style to a text-generation client (Qwen2.5-VL 32B Instruct in text-only mode, per Decisions). Do not expose frame data, video URLs, or video metadata to this stage. Use `temperature=0.2` (lowered from DESIGN.md's original `0.7`) to satisfy the spec's determinism requirement.

**Acceptance criteria (from the specification):**
- Generates one caption for every requested style using the Canonical Video Report as the only source of factual information.
- The Canonical Video Report is reused for generating every caption style.
- The system treats video understanding and language generation as independent stages.

**Independent verification:** Add pytest tests that mock the text model and assert one request per requested supported style, all using the same CVR, with no visual input in any style request.

## 11. Validate generated captions against output requirements
**Depends on:** task 10

Validate that each requested caption is non-empty, concise, and associated with its requested style. Add deterministic request construction and response validation; record model failures per caption without ending unrelated work.

**Acceptance criteria (from the specification):**
- Captions preserve facts contained in the CVR.
- Humor may introduce creative phrasing but must not introduce new factual claims.
- Captions clearly express the requested writing style.
- Captions remain concise and readable (approximately one to two sentences).
- Handles missing requested styles and style conflicts with factual accuracy.

**Independent verification:** Add pytest tests for empty responses, missing style results, deterministic request parameters, and caption length/sentence validation. The exact fact-preservation verifier is an open question below.

## 12. Serialize results atomically and validate JSON
**Depends on:** tasks 1, 3, and 11

Serialize completed task captions to `/output/results.json` as a JSON array of `{"task_id": ..., "captions": {"formal": ..., "sarcastic": ..., "humorous_tech": ..., "humorous_non_tech": ...}}` objects (see Decisions for the finalized schema). Create the `/output` directory if it does not exist, then write atomically. Validate the serialized document before the process completes.

**Acceptance criteria (from the specification):**
- Writes valid `/output/results.json` before exiting.
- Contains one caption for every requested style.
- Handles invalid JSON, missing captions, and partial task failures.

**Independent verification:** Add pytest tests for valid JSON output, requested-style coverage, an empty task list, and output when one task fails.

## 13. Orchestrate per-task processing with failure isolation
**Depends on:** tasks 2–12

Create the executable pipeline that processes all tasks sequentially as: input → download → inspection/sampling → one CVR → requested captions → results. Catch expected task-level failures, preserve successful tasks, always write results, and return exit code 0 according to the agreed failure-output policy.

**Acceptance criteria (from the specification):**
- Reads every task, downloads every video, produces one internal CVR per video, generates every requested caption, writes valid results, and exits successfully.
- Handles partial task failures.
- Video understanding is performed exactly once per video.

**Independent verification:** Add a mocked end-to-end pytest test covering two successful tasks and one failed task; assert a single vision call per successfully understood video, requested-style output, valid JSON, and exit code 0.

## 14. Add container entrypoint and dependency definition
**Depends on:** task 13

Add the deployment files required to run the pipeline in the hackathon environment, install only runtime dependencies, and invoke the application using the `/input` and `/output` paths.

**Acceptance criteria (from the specification):**
- Runtime is at most 10 minutes.
- The compressed Docker image is at most 10 GB.
- Exit code 0 on success.
- Valid JSON output is mandatory.

**Independent verification:** Build the image and run it with a mounted fixture `tasks.json`; inspect `/output/results.json` and the container exit code. Keep routine media tests small or mocked, as required by AGENTS.md. For a real-world spot check, the local Charades clip (see note at top) can be used as one of the mounted inputs.

## 15. Measure the representative runtime and document operation
**Depends on:** task 14

Run a representative multi-task smoke test, record elapsed time and image size, and document required environment variables (especially `FIREWORKS_API_KEY`), external tools, and the validation commands in the project documentation.

**Acceptance criteria (from the specification):**
- Generalizes to previously unseen videos and handles diverse domains.
- Completes within the runtime and Docker constraints.
- Produces deterministic outputs.

**Independent verification:** Run the container with representative unseen clips within the stated 30-second to 2-minute range, record the duration and compressed image size, and repeat deterministic mock tests. For API health, run `python fireworks_test_deployment.py --mode image-sanity`.

## Remaining Minor Open Items

Everything major has been resolved (see Decisions above). Two small items are still loosely defined and can be settled just-in-time when their tasks are reached, without blocking earlier work:

- **Frame-sampling behavior for very short or metadata-corrupt videos:** The 1 fps fallback (DESIGN.md §3.1) is defined, but duplicate-frame handling and behavior when duration/FPS are both unavailable aren't spelled out. Resolve when implementing Task 6.
- **`target_frames` as constant vs. config:** DESIGN.md §5 notes frame count could go from 16 to 24 if testing reveals temporal gaps. Decide whether this is a hardcoded constant or an exposed config value when implementing Task 6.

## Future Scope

- **Caption factuality enforcement:** No programmatic verifier will be built in this pass. The CVR-only input isolation in Task 10 (style generator never sees raw video/frames) is the primary safeguard against fabricated facts. A dedicated fact-consistency check (e.g., comparing caption content against CVR fields, or a secondary LLM-as-judge pass) is deferred to a future iteration.
