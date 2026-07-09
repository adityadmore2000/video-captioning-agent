# Video Captioning Agent -- Specification Document

## 1. Problem Statement

Build an AI-powered Video Captioning Agent that accepts one or more
video-captioning tasks, understands the visual content of each video,
and generates captions in one or more requested writing styles.

The system must generalize to previously unseen videos spanning multiple
domains (urban, nature, sports, food, people, weather, animals,
technology, etc.) while maintaining factual accuracy and adhering to the
requested writing style.

The core problem is decomposed into two responsibilities:

1.  **Video Understanding** -- derive an accurate semantic understanding
    of the video.
2.  **Caption Generation** -- express that understanding in the
    requested style without changing the underlying facts.

------------------------------------------------------------------------

## 2. Functional Requirements

### Input Processing

-   Read `/input/tasks.json` on startup.
-   Support multiple tasks in a single execution.
-   For each task, read:
    -   `task_id`
    -   `video_url`
    -   requested `styles`

### Video Processing

-   Download the video from the provided URL.
-   Analyze the visual content.
-   Build a factual semantic understanding of:
    -   primary subjects
    -   scene/environment
    -   important objects
    -   actions/events
    -   temporal progression
    -   relationships between entities
    -   overall context

### Caption Generation

Generate one caption for every requested style: - formal - sarcastic -
humorous_tech - humorous_non_tech

Requirements: - Preserve factual correctness. - Adapt only tone/style. -
Produce independent captions for each requested style.

### Output

Write `/output/results.json` in the required format before exiting.

------------------------------------------------------------------------

## 3. Constraints

### Hackathon Constraints

-   Runtime ≤ 10 minutes.
-   Docker image ≤ 10 GB compressed.
-   Exit code 0 on success.
-   Valid JSON output is mandatory.
-   Missing captions receive zero score.
-   Hidden evaluation videos range from 30 seconds to 2 minutes.
-   Generalization to unseen videos is required.

### Working Assumptions

-   Captions are concise (approximately 1--2 sentences).
-   English output.
-   Style modifies wording only---not factual content.
-   Video understanding is performed once and reused across style
    generation.
-   Primary focus is visual understanding; audio is optional unless
    intentionally supported.

------------------------------------------------------------------------

## 4. Edge Cases

### Input

-   Empty task list.
-   Malformed JSON.
-   Duplicate task IDs.
-   Unsupported style.
-   Missing fields.

### Video

-   Invalid URL.
-   Download timeout.
-   Corrupted video.
-   Empty video.
-   Extremely dark or blurry scenes.
-   Multiple scene transitions.
-   Multiple equally important subjects.
-   Rapid motion.
-   Low frame quality.

### Captioning

-   Ambiguous actions.
-   Occluded objects.
-   Dense scenes with many entities.
-   Videos with little activity.
-   Humor that risks changing facts.
-   Style conflict with factual accuracy.

### Output

-   Missing caption for requested style.
-   Invalid JSON.
-   Partial task failure.

------------------------------------------------------------------------

## 5. Acceptance Criteria

The solution is accepted when:

### Functional

-   Reads all tasks from `/input/tasks.json`.
-   Processes every task.
-   Produces captions for every requested style.
-   Writes valid `/output/results.json`.
-   Exits successfully.

### Quality

-   Captions accurately describe the video.
-   Requested style is clearly reflected.
-   Facts remain consistent across styles.
-   No hallucinated major events or objects.

### Robustness

-   Generalizes to unseen videos.
-   Handles varied domains.
-   Produces deterministic, valid output.
-   Completes within runtime and image-size constraints.

------------------------------------------------------------------------

## Conceptual Pipeline

``` text
Read Tasks
    ↓
Download Video
    ↓
Video Understanding
    ↓
Canonical Semantic Representation
    ↓
Style-specific Caption Generation
    ↓
Generate results.json
```

## Design Principles

-   Separate **video understanding** from **language generation**.
-   Optimize for factual accuracy first, style second.
-   Reuse a single semantic understanding for all requested styles.
-   Design for generalization rather than memorizing sample videos.
