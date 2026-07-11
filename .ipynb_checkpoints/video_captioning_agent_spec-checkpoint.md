# Video Captioning Agent — Specification Document (v1)

## 1. Problem Statement

Build an AI-powered Video Captioning Agent that processes one or more video-captioning tasks and generates a concise caption or summary of each video in four distinct writing styles:

* Formal
* Sarcastic
* Humorous-Tech
* Humorous-Non-Tech

The system must accurately understand previously unseen videos spanning diverse domains (urban, nature, sports, food, people, weather, animals, technology, etc.) and preserve factual consistency across every generated style.

The problem is decomposed into two independent responsibilities:

1. **Video Understanding** — derive an accurate, factual understanding of the entire video.
2. **Style-specific Caption Generation** — rewrite that factual understanding into the requested writing style without altering the underlying facts.

The system treats **video understanding** and **language generation** as independent stages.

---

# 2. Functional Requirements

## Input Processing

On startup, the system shall:

* Read `/input/tasks.json`
* Support multiple tasks within a single execution

Each task contains:

* `task_id`
* `video_url`
* requested `styles`

---

## Video Processing

For every task, the system shall:

* Download the video.
* Validate that the video is readable.
* Analyze the visual content.
* Build a factual understanding of the **entire video**, not only the most salient frame or event.

The understanding process should identify:

* primary subjects
* important objects
* scene/environment
* actions
* interactions between entities
* temporal progression of events
* state changes
* overall context

---

## Canonical Video Report (CVR)

Before generating captions, the system shall produce a **Canonical Video Report (CVR)**.

The CVR is the single factual representation of the video and serves as the interface between video understanding and language generation.

The report should capture:

* Scene
* Primary subjects
* Important objects
* Key actions
* Timeline of major events
* Overall factual summary

The CVR:

* must contain only observable facts
* must not contain humor
* must not speculate
* must not infer emotions, intentions, or events not supported by the video
* should prioritize semantically important information over exhaustive scene description

Example structure:

```text
Scene:
Kitchen

Primary Subjects:
- Woman

Important Objects:
- Eggs
- Frying pan
- Refrigerator

Timeline:
1. Woman enters the kitchen.
2. Removes eggs from refrigerator.
3. Cracks eggs into pan.
4. Cooks eggs.
5. Serves eggs onto a plate.

Overall Summary:
A woman prepares scrambled eggs in a kitchen.
```

The CVR is an internal artifact and is not included in the final submission.

---

## Caption Generation

The system shall generate one caption for every requested style using the Canonical Video Report as the only source of factual information.

Supported styles:

* Formal
* Sarcastic
* Humorous-Tech
* Humorous-Non-Tech

Requirements:

* Every caption must preserve the facts contained in the CVR.
* Style may modify wording and tone only.
* Humor may introduce creative phrasing but must not introduce new factual claims.
* Captions should summarize the **entire video**, not isolated moments.
* Captions should remain concise (approximately one to two sentences).

---

## Output

Before exiting, the system shall write:

`/output/results.json`

containing one caption for every requested style.

---

# 3. Constraints

## Hackathon Constraints

* Runtime ≤ 10 minutes
* Docker image ≤ 10 GB (compressed)
* Exit code 0 on success
* Valid JSON output is mandatory
* Missing captions receive zero score
* Hidden evaluation videos range from approximately 30 seconds to 2 minutes
* Generalization to unseen videos is required

---

## Working Assumptions

* English output
* Captions summarize the entire video
* Captions are concise (approximately one to two sentences)
* Visual understanding is the primary source of information
* Audio understanding is optional unless explicitly added later
* Video understanding is performed exactly once per video
* The Canonical Video Report is reused for generating every caption style

---

# 4. Edge Cases

## Input

* Empty task list
* Malformed JSON
* Duplicate task IDs
* Missing fields
* Unsupported styles

---

## Video

* Invalid URL
* Download timeout
* Corrupted video
* Empty video
* Extremely dark scenes
* Low-quality or blurry footage
* Rapid camera motion
* Multiple scene transitions
* Multiple equally important subjects
* Dense scenes containing many entities
* Very little activity

---

## Understanding

* Ambiguous actions
* Occluded objects
* Partial visibility
* Uncertain object categories
* Similar-looking actions
* Long videos containing several independent events

When uncertainty exists, the system should prefer conservative factual descriptions over hallucinated details.

---

## Caption Generation

* Humor accidentally changing facts
* Excessive detail reducing readability
* Overly generic summaries
* Missing requested styles
* Style conflicting with factual accuracy

---

## Output

* Invalid JSON
* Missing captions
* Partial task failures

---

# 5. Acceptance Criteria

## Functional

The solution is accepted when it:

* Reads every task from `/input/tasks.json`
* Downloads every video
* Produces one Canonical Video Report internally for every video
* Generates every requested caption
* Writes valid `/output/results.json`
* Exits successfully

---

## Quality

The generated captions shall:

* accurately summarize the entire video
* preserve factual consistency across all styles
* clearly express the requested writing style
* avoid hallucinated major objects, events, or actions
* remain concise and readable

---

## Robustness

The solution shall:

* Generalize to previously unseen videos
* Handle diverse domains
* Produce deterministic outputs
* Complete within runtime and Docker constraints

---

# 6. Conceptual Pipeline

```text
Read Tasks
        ↓
Download Video
        ↓
Video Understanding
        ↓
Canonical Video Report (CVR)
        ↓
Style-specific Caption Generation
        ↓
results.json
```

---

# 7. Design Principles

* Separate **video understanding** from **language generation**.
* Treat the **Canonical Video Report** as the single source of truth.
* Optimize for factual correctness before stylistic quality.
* Generate multiple writing styles from a single semantic understanding.
* Prefer conservative factual descriptions over hallucinated details.
* Prioritize semantically important events rather than exhaustive scene descriptions.
* Design for robust generalization rather than memorization.
