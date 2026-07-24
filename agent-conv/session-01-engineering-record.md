# Session Summary: Session 01

## Objective

Create `AGENTS.md` — a compact instruction file enabling future AI coding sessions (OpenCode) to ramp up quickly in this repository without re-discovering project conventions, commands, architecture, and constraints.

## Project State Before Session

- Repository was a very early-stage hackathon project with a single `initial commit` in git history.
- Python 3.12.3 virtual environment at `.venv/`.
- A small set of root-level Python scripts existed: `fireworks_test_deployment.py`, `upload_model_to_fireworks.py`, `remove_out_of_bound_video_clips.py`, `find_extensions.py`.
- Core design documents existed: `DESIGN.md`, `video_captioning_agent_spec.md`.
- A `Data/` directory (gitignored) held Charades dataset material.
- `docs/` directory contained research notes about Fireworks setup, InternVL3 vs Qwen2.5-VL decisions, and datasets.
- A `.env` file held `FIREWORKS_API_KEY` (gitignored).
- No formal build system — no `pyproject.toml`, `setup.py`, lint config, formatter config, or CI pipeline.
- No test suite, no `src/` package structure, no `tests/` directory.
- No `Dockerfile` or container configuration yet.
- The initial design specified a pipeline: download video → sample frames → VLM understanding (CVR) → style generation → results output.
- The spec described a two-stage architecture strictly separating **visual understanding** (CVR = Canonical Video Report) from **language generation** (4 writing styles).
- Target model was Qwen2.5-VL 32B Instruct hosted on Fireworks AI, with InternVL3-8B as an earlier candidate that was abandoned due to context window limitations (16k vs 128k).
- Hackathon constraints mandated ≤10 min runtime, ≤10 GB Docker image, and valid JSON output.

## Major Achievements

- Authored `AGENTS.md` (~44 lines of actionable content) capturing the repository's non-obvious conventions, commands, and architecture for future AI sessions.
- Established permanent conventions for: project structure, Python style, testing, commits, file operations, and security.

## Engineering Decisions

- **Decision**: Write AGENTS.md as a new file rather than embedding instructions in opencode.json.
  - **Reasoning**: AGENTS.md is a universally recognized agent-instruction filename, readable by any AI tool, not tied to a specific editor or agent framework.
  - **Alternatives considered**: opencode.json `instructions` field, `.cursor/rules/`, `.github/copilot-instructions.md`.
  - **Trade-off**: AGENTS.md is portable but lacks the structured rule format that opencode.json or Cursor rules provide.

- **Decision**: Include only repo-specific, hard-earned knowledge; omit generic Python advice.
  - **Reasoning**: Every line should answer "Would an agent likely miss this without help?" Prevents the file from becoming noise the agent learns to ignore.
  - **Alternatives considered**: Comprehensive style guide.
  - **Trade-off**: Concise files may omit edge cases that occasionally trip agents, but the signal-to-noise ratio is high.

- **Decision**: Source truth from executable artifacts (scripts, config files, directory structure) over prose documentation.
  - **Reasoning**: Prose can go stale; scripts and config are the actual system behavior. The `fireworks_test_deployment.py` script, for example, defined the actual test procedure better than any doc.
  - **Trade-off**: Requires agent to re-read source files occasionally; but protects against stale docs.

- **Decision**: Prescribe `if __name__ == "__main__":` guard for all new executable files.
  - **Reasoning**: Scripts were being written without the guard, making them unsafe to import from tests or other modules.
  - **Alternatives considered**: Single-entry-point CLI pattern (e.g., `click` or `argparse` in `main()`).
  - **Trade-off**: The `if __name__` guard is a minimal convention that doesn't prescribe a CLI framework, but doesn't enforce consistent CLI interface design.

- **Decision**: Recommend `pytest` for future tests with file naming `tests/test_*.py`.
  - **Reasoning**: No test framework existed; the hacking/testing pattern was to run scripts ad-hoc. Establishing a convention early avoids later migration pain.
  - **Alternatives considered**: `unittest`, doctests.
  - **Trade-off**: pytest is the de facto standard for Python; the recommendation is lightweight and imposes no mandatory test fixtures.

- **Decision**: Prescribe `pathlib.Path` for filesystem work and environment variables for credentials.
  - **Reasoning**: Consistent with the existing `fireworks_test_deployment.py` code style and Python 3.10+ best practices.
  - **Trade-off**: Minor; aligns with modern Python conventions.

- **Decision**: Document `firectl` (Fireworks CLI binary) as a tool even though it was just a binary in the repo root.
  - **Reasoning**: Non-obvious tooling that agents wouldn't know to look for — it's a binary, not a Python package, so `pip list` won't reveal it.
  - **Trade-off**: Tool path may change; CLI interface is undocumented.

## Architecture Changes

None. This was a documentation/instruction session, not an architecture session.

## Implementation Progress

- **File created**: `AGENTS.md` at repo root, consisting of 6 sections:
  - **Project Structure & Module Organization**: Documents root-level scripts, `docs/`, `Data/`, and the convention to place future packages under `src/` and tests under `tests/`.
  - **Build, Test, and Development Commands**: Exact commands for `fireworks_test_deployment.py` (image-sanity and video modes), `remove_out_of_bound_video_clips.py`, `find_extensions.py`. Covers the Fireworks auth verification workflow.
  - **Coding Style & Naming Conventions**: 4-space indentation, `pathlib.Path`, env vars for credentials, uppercase constants, `if __name__ == "__main__":` guard.
  - **Testing Guidelines**: pytest convention, small/mocked media, no large datasets.
  - **Commit & Pull Request Guidelines**: Imperative commit messages, PR content structure.
  - **File Operations**: Prohibition on file deletion without explicit permission (pre-emptively addresses a common agent failure mode).
  - **Security & Configuration Tips**: `.env` secrecy, `ffprobe` documentation requirement.

## Problems / Bugs / Limitations

- **No formal build system**: No `pyproject.toml`, `setup.py`, or `setup.cfg`. Dependencies were documented only in `requirements.txt` (which may have existed or was inferred from install commands). No version pinning.
- **No test suite**: All testing was ad-hoc via `fireworks_test_deployment.py`.
- **No CI/CD**: No automated checks for regressions.
- **No Dockerfile yet**: Containerization was planned but not implemented; the spec's `/input` → `/output` contract existed only on paper.
- **Fireworks API dependency**: The entire pipeline depended on a single external API; no fallback or offline mode existed.
- **FIREWORKS_API_KEY required at runtime**: No mechanism was yet designed for provisioning or key rotation in production.

## Debugging / Investigation

- The assistant read all ~15 key files in the repo (README, spec, design doc, all Python scripts, docs, .env, .gitignore, Dockerfile if any) to construct the AGENTS.md from first principles.
- Discovered that no test framework, build system, or lint/typecheck command existed — documented this absence explicitly so future agents don't waste time looking for them.

## Important Insights

- **Project maturity level was clearly "early prototype"**: Single `initial commit`, ad-hoc scripts, no package structure. AGENTS.md needed to communicate this honestly so agents don't assume more infrastructure exists than actually does.
- **The architecture already had a clear separation of concerns**: VLM (vision) → CVR → Text LLM (style) — this two-stage decomposition was the project's defining design choice and was worth calling out explicitly in AGENTS.md.
- **Hackathon constraints shaped everything**: 10-min runtime bound, 10 GB Docker image cap, and the Fireworks API dependency drove every implementation decision. These constraints were more important than standard engineering concerns like test coverage or CI.
- **Frames-as-images approach (not native video upload)**: The Fireworks API didn't support native video; the frame-sampling approach was a workaround that became a core architectural constraint.

## Project State After Session

- Repository gained `AGENTS.md` — a portable agent-instruction file.
- No code, architecture, or infrastructure changed.
- Future agents would be able to ramp up faster by reading AGENTS.md instead of re-scanning the entire repo.

## Interview-Worthy Talking Points

1. **Agent-to-Agent instruction design**: Creating AGENTS.md is a meta-engineering task — designing instructions for future AI agents requires a different mindset than writing for human developers. The constraint "every line should answer 'Would an agent likely miss this?'" is a useful filtering heuristic.
2. **Source-of-truth hierarchy**: The decision to trust executable artifacts over prose documentation reflects a real engineering problem — stale docs vs. live code. The trade-off (more reading at startup vs. higher correctness) is worth discussing.
3. **Hackathon vs. production engineering**: The project prioritized rapid prototyping (no tests, no CI, ad-hoc scripts) over engineering rigor, driven by a 10-min runtime constraint and a demo deadline. When is this trade-off justified, and when is it technical debt?
4. **Early project scaffolding**: What information should be captured when a project has only a single `initial commit`? The AGENTS.md documented directory conventions before they were enforced, anticipating growth rather than reacting to it.

## Keywords

AGENTS.md, agent instructions, OpenCode, video captioning, Fireworks AI, Qwen2.5-VL, Canonical Video Report, CVR, hackathon project, frame sampling, VLM, two-stage architecture, Python project template, repository conventions, developer onboarding, project scaffolding, agent-to-agent communication, prompt engineering, video understanding
