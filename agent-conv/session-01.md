# Updating AGENTS.md for repo instructions

**Session ID:** ses_0af4ff7f5ffeahkd2tBrHmAeWW
**Created:** 7/11/2026, 3:49:01 PM
**Updated:** 7/11/2026, 3:49:36 PM

---

## User

Create or update `AGENTS.md` for this repository.

The goal is a compact instruction file that helps future OpenCode sessions avoid mistakes and ramp up quickly. Every line should answer: "Would an agent likely miss this without help?" If not, leave it out.

User-provided focus or constraints (honor these):


## How to investigate

Read the highest-value sources first:
- `README*`, root manifests, workspace config, lockfiles
- build, test, lint, formatter, typecheck, and codegen config
- CI workflows and pre-commit / task runner config
- existing instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`)
- repo-local OpenCode config such as `opencode.json`

If architecture is still unclear after reading config and docs, inspect a small number of representative code files to find the real entrypoints, package boundaries, and execution flow. Prefer reading the files that explain how the system is wired together over random leaf files.

Prefer executable sources of truth over prose. If docs conflict with config or scripts, trust the executable source and only keep what you can verify.

## What to extract

Look for the highest-signal facts for an agent working in this repo:
- exact developer commands, especially non-obvious ones
- how to run a single test, a single package, or a focused verification step
- required command order when it matters, such as `lint -> typecheck -> test`
- monorepo or multi-package boundaries, ownership of major directories, and the real app/library entrypoints
- framework or toolchain quirks: generated code, migrations, codegen, build artifacts, special env loading, dev servers, infra deploy flow
- repo-specific style or workflow conventions that differ from defaults
- testing quirks: fixtures, integration test prerequisites, snapshot workflows, required services, flaky or expensive suites
- important constraints from existing instruction files worth preserving

Good `AGENTS.md` content is usually hard-earned context that took reading multiple files to infer.

## Questions

Only ask the user questions if the repo cannot answer something important. Use the `question` tool for one short batch at most.

Good questions:
- undocumented team conventions
- branch / PR / release expectations
- missing setup or test prerequisites that are known but not written down

Do not ask about anything the repo already makes clear.

## Writing rules

Include only high-signal, repo-specific guidance such as:
- exact commands and shortcuts the agent would otherwise guess wrong
- architecture notes that are not obvious from filenames
- conventions that differ from language or framework defaults
- setup requirements, environment quirks, and operational gotchas
- references to existing instruction sources that matter

Exclude:
- generic software advice
- long tutorials or exhaustive file trees
- obvious language conventions
- speculative claims or anything you could not verify
- content better stored in another file referenced via `opencode.json` `instructions`

When in doubt, omit.

Prefer short sections and bullets. If the repo is simple, keep the file simple. If the repo is large, summarize the few structural facts that actually change how an agent should work.

If `AGENTS.md` already exists at `/home/aditya/dev-work/video-captioning-agent`, improve it in place rather than rewriting blindly. Preserve verified useful guidance, delete fluff or stale claims, and reconcile it with the current codebase.

---

## Assistant

_Thinking:_

Let me start by reading the existing AGENTS.md and then exploring the repo structure to gather the information needed.

**Tool: read**

**Tool: read**

---

## Assistant

_Thinking:_

No existing AGENTS.md. Let me read the key files to understand the repo.

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

_Thinking:_

Let me also read the docs files for more context.

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

**Tool: glob**

---

## Assistant

_Thinking:_

Now I have a good picture of the repo. Let me also check for the `.env` file and git log to understand the state.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

Now I have a comprehensive understanding of the repo. Let me write the AGENTS.md.

Key facts:
- Python project, no package manager config (no pyproject.toml, requirements.txt, package.json, Dockerfile)
- Virtual env at `.venv/` (Python 3.12.3)
- Data directory contains Charades dataset (gitignored)
- No build/test/lint commands configured
- Uses Fireworks AI API (InternVL3 model) for video understanding
- Reads `.env` for FIREWORKS_API_KEY
- Hackathon project: Docker image ≤10GB, runtime ≤10min


- Reads from `/input/tasks.json` and outputs to `/output/results.json` with video understanding and caption generation pipeline
- Key dependencies: opencv-python, requests, python-dotenv, pandas, matplotlib- `firectl` is a Fireworks CLI binary and `fireworks_test_deployment.py` handles testing the model deployment
- Spec is in `video_captioning_agent_spec.md` with research notes in `docs/`

Now I'm pulling together the essentials for AGENTS.md: this is a hackathon project for video captioning with no formal build system, Python 3.12.3, Docker deployment, and a pipeline that processes videos through frame sampling and the InternVL3 model before generating styled captions.

**Tool: write**

---

## Assistant

_Thinking:_

The file is written. Let me verify it looks good.

Created `AGENTS.md`. It covers the high-signal facts an agent would need: constraints, environment setup, how to test the API, pipeline architecture, data characteristics, and the absence of formal tooling. Kept it to ~60 lines of actionable content.

---

