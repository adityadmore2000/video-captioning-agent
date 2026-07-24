# Session Summary: Session 03

## Objective

Investigate and resolve alleged prompt-drift violations between DESIGN.md §4.1/§4.2 and the implementation. Specifically: two safety-relevant clauses were claimed missing from the system prompt ("describe physical motion, not assumed purpose" and "no markdown-wrapping"), and a `{metadata_json}` block was added to the user prompt without design-doc approval. The goal was to restore any missing safety clauses and either remove or formally adopt the undocumented metadata block.

## Project State Before Session

- Session-02 ended mid-investigation: the assistant had discovered the prompt drift (metadata block, stripped backtick marker, removed scene example) but the conversation expired before any resolution or edits.
- Production code existed at `src/video_captioning_agent/cvr_client.py:20-27` (system prompt) and `cvr_client.py:29-54` (user prompt template).
- A second copy of the prompts lived in `experiments/configs/exp_example.yaml:22-26` (system prompt) and `exp_example.yaml:28-52` (user prompt template), intended as a "no-op override" example config.
- DESIGN.md was the canonical design document with the "approved" prompt text.
- The agent was operating in **plan mode** (read-only, edit tool denied to all files except `.opencode/plans/*.md`).
- The production `cvr_client.py` had never been in a DESIGN.md-matching state — the metadata block was present from the first commit (7083365).

## Major Achievements

1. **Proved the user's premise was partially false**: Both claimed-missing safety clauses ("describe physical motion, not assumed purpose" and "no markdown-wrapping") were **present** in the production `cvr_client.py` system prompt. The user was mistaken — the real problem was in the *experiment config*, not the production code.
2. **Identified the actual drift locations**: Three distinct sites of divergence were cataloged: production vs. DESIGN.md, experiment config vs. DESIGN.md, and experiment config vs. production. The experiment config `exp_example.yaml` was the worst offender — it truncated directive 2, truncated directive 4, and truncated directive 5.
3. **Audited the `{metadata_json}` block**: Confirmed it existed from the very first commit (not introduced by drift). The `git log` showed `cvr_client.py` was born with the metadata block — DESIGN.md was simply never updated to match. Inferred rationale: it gives the VLM grounding information (fps, resolution, duration) that individual frame samples don't convey.
4. **Cataloged the full divergence matrix**: Beyond the metadata block, 6+ other undocumented changes were identified (placeholder renames, scene example removal, per-frame label blocks, template escaping, etc.).
5. **Negotiated a precise restoration plan**: User decided to keep the metadata block but document it in DESIGN.md, restore both safety clauses in exp_example.yaml, restore the markdown backtick marker in cvr_client.py, and fully align exp_example.yaml with production as a faithful mirror.

## Engineering Decisions

### 1. Metadata block: keep + document, not remove
- **Decision**: Keep the `{metadata_json}` block in the user prompt, but document it in DESIGN.md §4.2 as a deliberate design choice rather than an undocumented implementation artifact.
- **Reasoning**: The metadata block provides grounding information (fps, frame_count, width, height, duration_seconds) that the base64 frame strips alone cannot convey. It helps the VLM interpret sampling cadence and scale judgments. The user agreed this was a plausible improvement.
- **Alternatives**: Remove the block to match DESIGN.md exactly. Rejected as a regression.
- **Trade-off**: The production system diverges from DESIGN.md, but DESIGN.md will be updated to match. The metadata block is now an official design element rather than a silent addition.

### 2. Safety clauses: restore in experiment config, not production (already present)
- **Decision**: Restore the two truncated clauses in `experiments/configs/exp_example.yaml`; make no change to `cvr_client.py` for these clauses (both are already present).
- **Reasoning**: The production system prompt was never missing these clauses. The user's concern stemmed from conflating the experiment config with the production config. The experiment config was an actual safety regression (it dropped both clauses).
- **Trade-off**: The experiment config was intended as a "no-op override" but was actually a silent safety degradation. Fixing it requires a larger rewrite of the YAML block.

### 3. Byte-for-byte identity for experiment config system prompt
- **Decision**: Rewrite `exp_example.yaml`'s `system_prompt` block to be byte-for-byte identical to `cvr_client.py`'s `CVR_SYSTEM_PROMPT` constant.
- **Reasoning**: The whole point of the example config is to demonstrate a no-op override. If it's not byte-identical, it's not a valid no-op. Three truncations were found: directive 2's tail, directive 4's tail, and directive 5's full sentence.
- **Trade-off**: Long single lines in YAML (less readable), but the rendered string is now correct.

### 4. Re-insert the ` ``` ``` ` backtick marker
- **Decision**: Restore the literal triple-backtick example in the "no markdown-wrapping" instruction for both production and experiment config.
- **Reasoning**: The user considered this safety-relevant — the example helps the model understand what "don't wrap in markdown code blocks" means. DESIGN.md §4.1 includes it; the implementation dropped it. The user called for restoration "exactly as written in DESIGN.md."
- **Trade-off**: Inserting literal `` ``` `` inside a Python triple-quoted string is safe (`` ``` `` != `"""`), but the removal was arguably a *reduction* in ambiguity (the model could parse the triple backticks themselves as a code fence example). The user disagreed.

### 5. Scene example restoration
- **Decision**: Re-add the `(e.g., Kitchen, Outdoor street)` parenthetical to the `scene` field in both `cvr_client.py` and `exp_example.yaml`.
- **Reasoning**: The DESIGN.md template includes this example to ground the model in what "scene" means. Its removal was undocumented and reduces prompt quality.
- **Trade-off**: Slightly longer prompt (~25 tokens), but better task specification.

### 6. DESIGN.md §4.2 updated to match implementation
- **Decision**: Redocument the user prompt template in DESIGN.md to include: the metadata block, the actual placeholder names used in code, and a description of per-frame label blocks.
- **Reasoning**: DESIGN.md should reflect the production system, not a hypothetical design that was never implemented. The user explicitly requested documenting all three items.
- **Trade-off**: DESIGN.md chases the implementation rather than the other way around. This breaks the model that DESIGN.md is the specification that code implements.

## Architecture Changes

- **Modified**: `src/video_captioning_agent/cvr_client.py` — two edits:
  - Line 27: re-insert `` ``` `` backtick marker in STRICT JSON directive.
  - Line 41: re-add `(e.g., Kitchen, Outdoor street)` to scene field description.

- **Modified**: `experiments/configs/exp_example.yaml` — comprehensive rewrite of `system_prompt` and `user_prompt_template` blocks:
  - System prompt: restored directive-2 tail ("describe physical motion"), restored directive-4 tail ("to accurately construct the timeline of events"), restored directive-5 full sentence (markdown-wrapping prohibition + backtick marker), joined the opening sentence into one line.
  - User prompt template: restored scene example, expanded timeline array to multi-line (matching production), restored full `overall_summary` text, restored full rules bullet ("clearly visible and relevant to the action"), kept metadata block, kept placeholder names.

- **Modified**: `DESIGN.md` §4.2 — three documentation updates:
  - Added `Video Metadata:\n{metadata_json}` block to the template.
  - Renamed placeholders: `{num_frames}` → `{frame_count}`, `{duration:.1f}` → `{duration_seconds:.1f}`, `{frame_timestamps}` → `{timestamp_lines}`.
  - Added description of per-frame label blocks (`"Frame N (source frame M, Ts)"`) as part of the documented user prompt structure.

## Implementation Progress

### Edits fully specified but NOT executed (blocked by plan-mode permission):
The session ended with all four files' edits fully specified with exact before/after strings, including tiebreaker resolution for whitespace conflicts. However, the workspace permission rules blocked the `edit` tool on all files except `.opencode/plans/*.md` — the plan-mode constraint was still enforced at the tooling layer despite the user verbally approving execution.

### Changes blocked:
1. `cvr_client.py:27` — re-insert ``` marker
2. `cvr_client.py:41` — re-add scene example
3. `exp_example.yaml` — full system prompt and user prompt template rewrite
4. `DESIGN.md` §4.2 — documentation updates

## Problems / Bugs / Limitations

### 1. Rediscovered: experiment config is a broken "no-op override"
`exp_example.yaml` was supposed to be a no-op override but actually stripped three safety-relevant parts of the system prompt (directives 2, 4, 5) and had six content divergences in the user prompt. This means any experiment that used this config as a base had been running with degraded prompts.

### 2. Conflict in byte-for-byte requirements
The user's instructions had a latent conflict: (a) make exp_example.yaml byte-for-byte identical to cvr_client.py, and (b) restore clauses "exactly as written in DESIGN.md §4.1." But cvr_client.py and DESIGN.md disagree on a trailing space on line 83 of DESIGN.md ("visible in the frames. " vs. "visible in the frames."). The assistant surfaced this conflict; the user resolved it as "ignore trailing space — not safety-relevant."

### 3. YAML literal scalar rendering mismatch
`exp_example.yaml` uses a YAML literal block scalar (`|`) for the user prompt, which preserves newlines. The production template is a Python triple-quoted string. If the YAML wraps a sentence across two lines, the rendered string differs. This was surfaced but the user dismissed further whitespace diffs as unnecessary.

### 4. Edit permissions blocked execution
The session's actionable work (4 file edits, all fully specified) could not be executed because the workspace permission configuration blocked the `edit` tool for all files outside `.opencode/plans/*.md`. The assistant reported this and asked how to proceed.

## Debugging / Investigation

### Investigating the user's claim of missing clauses
- **Claim**: "describe physical motion, not assumed purpose" and "no markdown-wrapping" clauses are missing from the system prompt.
- **Method**: Read `DESIGN.md` §4.1, then read `cvr_client.py:20-27` and compared word-for-word with `git log` to establish history.
- **Finding**: Both clauses are present in production. The user was mistaken. The real truncations were in `experiments/configs/exp_example.yaml`.
- **Root cause of confusion**: Two copies of the system prompt exist (production + experiment config), and the user was likely looking at the experiment config (which *is* truncated) or misremembering.
- **Lesson**: When a user reports a discrepancy, always check all copies of the data, not just the primary one.

### Git history reconstruction
- `git log` for `cvr_client.py` showed a single commit: `7083365` — the initial implementation commit.
- Unlike what the user assumed, there was never a clean DESIGN.md-matching state that was later corrupted. The metadata block was present from birth; DESIGN.md was simply never updated.
- This ruled out the "drift" hypothesis. The divergence was better described as "design-doc staleness" rather than "implementation drift."

### Full divergence matrix
The assistant produced a line-by-line comparison of three sources (DESIGN.md, cvr_client.py, exp_example.yaml) for both the system and user prompts, identifying 9 distinct divergences:

**System prompt (3 divergences):**
1. Trailing space on line 83 (DESIGN.md only)
2. Missing backtick marker in production and experiment config
3. Two truncated directives in experiment config only (2 and 5)

**User prompt (6 divergences):**
1. Metadata block added
2. Placeholder renames (3)
3. Scene example removed
4. Per-frame label blocks added
5. Template escaping changed (`{{ }}`)
6. YAML line-wrapping in experiment config

## Important Insights

1. **Design-doc staleness is more dangerous than implementation drift**: The metadata block wasn't a silent corruption of the implementation — it was an improvement that was never backported to the design doc. The problem wasn't the code diverging from the design, but the design diverging from reality. A stale design doc is arguably worse than a non-existent one because it creates false confidence.

2. **"No-op override" is a sharp edge**: The experiment config was advertised as a no-op override but was actually a safety regression. If someone ran an experiment with `exp_example.yaml` as the config, they'd get degraded prompts. The config YAML must be byte-identical to the production constant to be a valid no-op — anything less is a subtle bug.

3. **Evidenced-based debugging of human claims**: The user was confident that two clauses were missing. The assistant could have blindly "restored" them (a no-op edit that wastes time but satisfies the user) or fabricated the problem. Instead, it investigated, found the user was wrong about production but right about the experiment config, and presented the truth. This is the correct engineering behavior even when it requires disagreeing with the user.

4. **Plan-mode permissions are a double-edged sword**: The plan mode prevented premature editing but also prevented executing correctly approved edits. The permission configuration (edits denied except to plan files) was either intentional (to gate all changes through plan review) or an oversight (the plan mode flag was never disabled). The session ended in limbo.

## Project State After Session

- **No files were modified** (all edits blocked by permissions).
- The full set of required edits was exhaustively specified with exact before/after strings across 4 files.
- A divergence matrix was produced documenting 9 distinct prompt differences across 3 sources.
- The metadata block was formally approved as a design element (vs. a silent addition).
- The experiment config's safety regressions were identified and placed on a restoration plan.
- The session exposed a process problem: edits can be informed and approved but not executed due to permission configuration.

## Interview-Worthy Talking Points

1. **User-claimed vs. actual drift**: When a user reports "missing safety clauses," investigating every copy of the data is critical. The user was wrong about production but right about the experiment config. Reporting the truth (including "you're mistaken") is harder but more valuable than blind compliance.

2. **Design-doc staleness vs. implementation drift**: A key distinction. The `{metadata_json}` block wasn't drift (code changed away from design) — it was design staleness (design was never updated to match code). Different remediation path, different root cause.

3. **The "no-op override" that wasn't**: The experiment config's system prompt was truncated in 3 places, silently degrading safety. A YAML config file that defaults to "no change" must be byte-identical to the production default — any less is a bug. This is a lesson in config-as-code testing.

4. **Permission-layer lockout mid-session**: All edits were specified, approved, and ready to execute, but a workspace permission rule blocked the edit tool on non-plan files. This is a real-world example of a process bottleneck — the engineering work (analysis, specification, negotiation) was complete, but the last mile (actually making the change) was blocked by configuration.

## Keywords

prompt drift, safety clauses, DESIGN.md, system prompt, user prompt, metadata block, CVR, video captioning, Fireworks AI, Qwen2.5-VL, experiment config, no-op override, plan mode, edit permissions, cvr_client.py, exp_example.yaml, backtick marker, scene example, frame sampling, prompt restoration, design-doc staleness, divergence matrix, evidence-based debugging, prompt engineering, VLM grounding

## Presentation Assets

1. **Comparison table**: "Three-source prompt divergence matrix" — a 3-column table comparing DESIGN.md vs. cvr_client.py vs. exp_example.yaml for both system and user prompts, with 9 documented differences.
2. **Debugging case study**: "The user was wrong — now what?" — workflow showing how the assistant disproved the user's premise but found the real problem in a different file. Useful for teaching evidence-based debugging.
3. **Diagram**: "Design-doc staleness vs. implementation drift" — two concepts with different root causes and different fixes.
4. **Slide**: "The no-op override that wasn't" — showing how YAML system prompt in exp_example.yaml truncated 3 safety clauses, making it not a valid no-op override.
5. **Trade-off slide**: "Metadata block: stay vs. remove vs. keep + document" — the three options considered, with the chosen path.
