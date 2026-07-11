# Technical Design Document: Video Captioning Agent

**Version:** 1.0

**Project:** Video Captioning Hackathon

**Author:** Senior AI Engineering

**Status:** Approved for Implementation


## 1. System Overview:

- The Video Captioning Agent is a multimodal AI pipeline designed to process video tasks, generate a factual understanding of the video content, and rewrite that understanding into four distinct stylistic captions.
- The architecture strictly separates visual understanding from language generation. Visual understanding is executed exactly once per video to produce a Canonical Video Report (CVR). The CVR acts as the single source of truth, which is then passed to a text-generation stage to produce the four required styles.
---------------------------------------------------------
### 1.1 Architecture Diagram
```
flowchart TD
    A[Input: tasks.json] --> B[Video Downloader]
    B --> C[Video Frame Sampler]
    C --> D[Visual LLM: Qwen2.5-VL 32B]
    D --> E[Canonical Video Report CVR]
    E --> F[Text LLM: Style Rewriter]
    F --> G[Output: results.json]
```
---------------------------------------------------------
## 2. Technology Stack
1. **Vision-Language Model (VLM):** Qwen2.5-VL 32B Instruct (Hosted on Fireworks AI)
2. **Text LLM (for Style Generation):** Qwen2.5-VL 32B Instruct (text-only mode) or similar fast LLM
3. **Video Processing:** OpenCV (cv2)
4. **Data Serialization:** JSON
5. **Language:** Python 3.10+

----------------------------------------------------------
## 3. Component Design
### 3.1 Video Frame Sampler
Since the Fireworks OpenAI-compatible API does not reliably support native video file uploads, we use uniform frame sampling. This gives us deterministic control over the token budget and temporal coverage.

- **Input:** Local video file path.
- **Process:**
    1. Open video via cv2.VideoCapture.
    2. Calculate duration and total frames.
    3. Uniformly select N frame indices across the timeline.
    4. For each frame: convert to RGB, downscale max dimension to 768px, encode to JPEG base64.

- **Configuration:**
    - target_frames: 16 (Sweet spot for 30-120s videos within Qwen's 128k context).
    - max_resolution: 768px.
- **Output:** List of FrameSample objects (containing base64 data URLs and timestamps).
- **Edge Case Handling:** Includes a fallback to sequential reading (1 fps) if uniform indexing fails due to corrupted video metadata.


## 3.2 CVR Generator (Vision-Language Stage)

This component queries the VLM to extract observable facts from the sampled frames.

- **Model:** accounts/fireworks/models/qwen2p5-vl-32b-instruct
- **Input:** List of FrameSample objects + Video Metadata.
- **Generation Parameters:** temperature: 0.1 (low temperature for factual determinism), max_tokens: 1024.
- **Output:** Parsed JSON object representing the Canonical Video Report (CVR).

---------------------------------------------------------
## 3.3 Style Generator (Language Generation Stage)

This component takes the dry, factual CVR and rewrites it into the four requested styles. By isolating this stage, we ensure factual consistency—the style model is physically blocked from seeing the video and can only manipulate the text of the CVR.

- **Input:** CVR JSON string, Target Style (Formal, Sarcastic, Humorous-Tech, Humorous-Non-Tech).
- **Process:** Prompts a text LLM to rewrite the CVR summary into 1-2 sentences matching the style.
- **Generation Parameters:** temperature: 0.2 (higher temperature for creative phrasing).
- **Output:** 4 distinct caption strings per task.
------------------------------------------------------------
### 4. Prompt Engineering
Qwen2.5-VL responds exceptionally well to structured directives, explicit schema constraints, and strict negative constraints.

### 4.1 CVR System Prompt
Sets the global persona and strict factual boundaries.

```
You are a strict, objective video-understanding agent. Your sole purpose is to analyze sequences of video frames and generate a Canonical Video Report (CVR).

Core Directives:
1. OBSERVABLE FACTS ONLY: Describe only what is explicitly visible in the frames. 
2. NO SPECULATION: Do not infer emotions, intentions, or off-screen events. If an action is ambiguous, describe the physical motion, not the assumed purpose.
3. NO HUMOR OR STYLE: The CVR must be completely dry, factual, and objective.
4. TEMPORAL AWARENESS: Pay close attention to the chronological order of frames to accurately construct the timeline of events.
5. STRICT JSON: You must output ONLY valid JSON matching the requested schema. Do not wrap the output in markdown code blocks (```) and do not include any conversational text before or after the JSON.
```

------------------------------------------------------------

### 4.2 CVR User Prompt
Provides the specific task context, frame timestamps, and the expected JSON schema.

```
Below are {num_frames} frames sampled from a {duration:.1f}-second video, presented in chronological order.

Frame Timestamps:
{frame_timestamps}

Analyze these frames and generate the Canonical Video Report (CVR). 

Return a JSON object with EXACTLY this structure:
{
  "scene": "Brief description of the location or environment (e.g., Kitchen, Outdoor street)",
  "primary_subjects": ["Entity 1", "Entity 2"],
  "important_objects": ["Object 1", "Object 2"],
  "timeline": [
    "Event 1 at timestamp X",
    "Event 2 at timestamp Y"
  ],
  "overall_summary": "A single, concise sentence summarizing the factual progression of the entire video."
}

Rules:
- Prioritize semantically important events over exhaustive background details.
- Only include primary subjects and important objects that are clearly visible and relevant to the action.
- If you cannot see something clearly, do not include it.
```
------------------------------------------------------------
### 5. Token & Context Budget Analysis
Switching from InternVL3-8B (16k context) to Qwen2.5-VL 32B Instruct (128k context) removed the primary bottleneck of the pipeline. We now have ample headroom to pass 16 high-resolution frames without risking context truncation.

| Component                                | Estimated Tokens | Running Total |
|------------------------------------------|------------------|---------------|
|                                          |                  |               |
|                                          |                  |               |
| System Prompt                            | ~300             | 300           |
| User Prompt (Instructions + JSON Schema) | ~400             | 700           |
| 16 Frames @ 768px (~2,000 tokens each)   | ~32,000          | 32,700        |
| Response Buffer (max_tokens)             | 1,024            | 33,724        |
| **Total Context Used**                       | **~33,724**          |               |
| **Qwen2.5-VL Context Limit**                 | **128,000**          |               |
| **Remaining Headroom**                       | **~94,276**          |               |


** Note:** The generous headroom allows us to increase target_frames to 24 if testing reveals temporal gaps in 120-second videos.
------------------------------------------------------------
6. Edge Cases & Error Handling

| Component | Estimated Tokens               | Running Total                                                                                                            |
|-----------|--------------------------------|--------------------------------------------------------------------------------------------------------------------------|
|           |                                |                                                                                                                          |
|           |                                |                                                                                                                          |
| Category  | Edge Case                      | Mitigation Strategy                                                                                                      |
| Input     | Malformed tasks.json           | Use try/except on json.load(). Skip execution, write empty results.json, exit 0.                                         |
| Input     | Unsupported style requested    | Filter styles against a hardcoded list [Formal, Sarcastic, Humorous-Tech, Humorous-Non-Tech]. Ignore unsupported styles. |
| Video     | Invalid URL / Download timeout | Use requests with timeout=30. Catch exceptions, log failure, write empty caption for that task.                          |
| Video     | Corrupted video metadata       | VideoFrameSampler detects total_frames <= 0 and falls back to sequential cap.read() at 1 fps.                            |
|           |                                |                                                                                                                          |
|           |                                |                                                                                                                          |

------------------------------------------------------------
7. Hackathon Constraints Compliance

- Runtime ≤ 10 minutes: The pipeline processes videos sequentially. 16-frame sampling takes ~2s. VLM API call takes ~10-15s. Style generation takes ~2s per style. Total per task: ~25s. For 10 tasks, estimated runtime is ~4-5 minutes.
- Docker image ≤ 10 GB: Base Python image (~150MB) + OpenCV (~100MB) + Requests/NumPy (~50MB). Total image size will be well under 1 GB.
- Valid JSON output: The pipeline strictly enforces JSON schema validation before writing to /output/results.json.
- Exit code 0: The pipeline will use broad exception handling to ensure it never crashes mid-execution, always writing a valid (even if partially empty) results.json and exiting with code 0.