# Engineering Evidence Map — Universal Specification v1.0

**Status:** Final  
**Audience:** Information Architects, Knowledge Engineers, Engineering Leads  
**Purpose:** Define the structure every project will adopt to capture engineering knowledge supported by evidence.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Core Design Principles](#2-core-design-principles)
3. [Universal Record Schema](#3-universal-record-schema)
4. [Evidence Types Catalog](#4-evidence-types-catalog)
   - 4.1 [Requirement (REQ)](#41-requirement-req)
   - 4.2 [Constraint (CON)](#42-constraint-con)
   - 4.3 [Decision (DEC)](#43-decision-dec)
   - 4.4 [Alternative Considered (ALT)](#44-alternative-considered-alt)
   - 4.5 [Trade-off (TRD)](#45-trade-off-trd)
   - 4.6 [Architecture (ARC)](#46-architecture-arc)
   - 4.7 [Challenge (CHL)](#47-challenge-chl)
   - 4.8 [Investigation (INV)](#48-investigation-inv)
   - 4.9 [Root Cause Analysis (RCA)](#49-root-cause-analysis-rca)
   - 4.10 [Validation (VAL)](#410-validation-val)
   - 4.11 [Result (RES)](#411-result-res)
   - 4.12 [Lesson Learned (LES)](#412-lesson-learned-les)
5. [Evidence Relationships](#5-evidence-relationships)
6. [Evidence Lifecycle](#6-evidence-lifecycle)
7. [What Should NOT Become Evidence](#7-what-should-not-become-evidence)
8. [Identifier Scheme](#8-identifier-scheme)
9. [Confidence Rules](#9-confidence-rules)
10. [Deduplication Rules](#10-deduplication-rules)
11. [Superseding Rules](#11-superseding-rules)
12. [Traceability Rules](#12-traceability-rules)
13. [Quality Guidelines](#13-quality-guidelines)
14. [Templates](#14-templates)

---

## 1. Overview

### 1.1 Purpose

The Engineering Evidence Map (EEM) is the **single source of truth** for all engineering knowledge produced during a project's lifetime.

It is the authoritative document from which all downstream artifacts—knowledge bases, presentation slides, interview kits, and portfolios—are derived. No downstream artifact should reference raw conversations or source code directly; every artifact should trace back to the EEM.

### 1.2 What the EEM Is

- A structured, evidence-backed **knowledge graph** of engineering reasoning.
- A record of **why** things were built the way they were, not a description of **what** was built.
- A **traceable** ledger where every claim links to supporting session summaries.
- A **living** document that evolves as engineering understanding deepens.

### 1.3 What the EEM Is Not

- A README or project overview.
- Implementation documentation or API reference.
- Architecture diagrams (although architecture decisions are captured).
- A project timeline or changelog.
- Meeting notes or conversation summaries (those are upstream inputs).
- A task tracker or issue list.

### 1.4 Data Flow

```text
Raw Conversations
        │
        ▼
Session Summaries
        │
        ▼
Engineering Evidence Map   ◄── single source of truth
        │
        ├───────────────┐
        ▼               ▼
Engineering        Presentation
Knowledge Base     Slides
        │               │
        ▼               ▼
Interview Kit    Portfolio
```

Session summaries are the **evidence layer**. The EEM extracts, structures, and connects engineering claims from those summaries. Nothing exists in the EEM without a session-summary reference.

---

## 2. Core Design Principles

### Principle 1: Evidence-First

Every record in the EEM represents a claim supported by at least one session summary. Assumptions, speculation, and personal opinion do not belong. If a claim cannot point to where the team discussed, researched, or validated it, it is not evidence.

### Principle 2: Atomic

Each record captures exactly one engineering concept. A single record should not bundle a decision, its trade-off, and the challenge that prompted it—those are three separate evidence types. Atomic records enable precise citation, independent lifecycle management, and cleaner relationship graphs.

### Principle 3: Traceable

Every claim must be traceable back to supporting session summaries. The EEM must support forward traceability (from evidence to downstream artifacts) and backward traceability (from any claim to its source sessions). Auditing a claim should require reading the claim, its session references, and its relationship chain—nothing more.

### Principle 4: Reusable

The schema must work identically across personal projects, research prototypes, startups, enterprise systems, and production platforms. No field should assume organizational scale, tooling maturity, or team size. The same specification should serve a solo developer's weekend project and a 200-engineer platform migration.

### Principle 5: Evolvable

Engineering knowledge changes. New information may invalidate old conclusions. The EEM preserves history by marking records as superseded rather than deleting them. Every revision creates a forward pointer so the chain of reasoning can be reconstructed from any point in time.

### Principle 6: Relationship-Driven

Engineering knowledge is a graph, not a list. Relationships between evidence records capture the causal and logical structure of engineering reasoning. Instead of duplicating context across records, the EEM uses explicit relationship links. The value of the map grows with the density of its connections, not the count of its records.

---

## 3. Universal Record Schema

Every evidence record shares the following structure. Type-specific extensions are defined in [Section 4](#4-evidence-types-catalog).

### 3.1 Schema Definition

```yaml
# ── Core Identity ──────────────────────────────────────────
id: STRING                         # Unique identifier (see §8)
type: EvidenceType                 # One of: REQ, CON, DEC, ALT, TRD, ARC, CHL, INV, RCA, VAL, RES, LES
title: STRING                      # Short descriptive title, ≤120 characters
summary: STRING                    # One-paragraph summary, ≤500 characters

# ── Content ────────────────────────────────────────────────
description: STRING                # Full detailed explanation
rationale: STRING                  # Engineering reasoning: WHY this exists or matters

# ── Lifecycle ──────────────────────────────────────────────
status: Status                     # Draft | Investigating | Final | Superseded | Planned | Rejected
confidence: Confidence             # HIGH | MEDIUM | LOW

# ── Categorization ─────────────────────────────────────────
tags: LIST[STRING]                 # Free-form labels for discovery and filtering
domain: STRING                     # Primary engineering domain (e.g., "performance", "security", "data-model")

# ── Traceability ───────────────────────────────────────────
supporting_sessions: LIST[SessionRef]      # Session summaries that back this claim
evidence_references: LIST[ExternalRef]     # External artifacts referenced by this claim

# ── Relationships ──────────────────────────────────────────
relationships: LIST[Relationship]          # Explicit links to other evidence records

# ── Evolution ──────────────────────────────────────────────
supersedes: LIST[ID]               # Older record(s) whose claims are refined or replaced
superseded_by: LIST[ID]            # Newer record(s) that refined or replaced this claim

# ── Metadata ───────────────────────────────────────────────
created_at: ISO8601_TIMESTAMP      # When this record was first created
created_by: STRING                 # Person or agent that created the record
updated_at: ISO8601_TIMESTAMP      # When this record was last modified
updated_by: STRING                 # Person or agent that made the last modification
```

### 3.2 Field Descriptions

#### id

A stable, globally-unique identifier using the prefix convention defined in [Section 8](#8-identifier-scheme). Must never be reused, even if the record is superseded.

Example: `DEC-012`

#### type

The evidence category. Determines which type-specific fields are applicable (see [Section 4](#4-evidence-types-catalog)).

#### title

A concise label that communicates the essence of the record. Should be meaningful in isolation—a reader browsing a list of titles should understand what each record is about.

Good: `Adopt two-stage architecture separating VLM from text generation`  
Avoid: `Architecture decision`, `About the pipeline`

#### summary

A one-paragraph distillation. Useful for search, indexing, and quick review. Should contain the claim's core assertion.

#### description

The full, unabridged explanation. This is the body of the evidence. Include enough detail that someone unfamiliar with the project can understand the claim without reading session summaries.

#### rationale

The engineering reasoning behind the claim. **This is the most important field in the record.** It captures the WHY: why this requirement matters, why this decision was correct, why this trade-off was acceptable. Rationale separates engineering knowledge from mere documentation.

#### status

The lifecycle position of the record. Defined in [Section 6](#6-evidence-lifecycle).

#### confidence

Objective confidence level in the claim. Defined in [Section 9](#9-confidence-rules).

#### tags

Free-form labels for categorization and discovery. Tags should use lowercase, hyphen-separated words. A controlled vocabulary is not required, but consistency within a project aids search.

Examples: `performance`, `context-window`, `fallback-strategy`, `json-parsing`

#### domain

The primary engineering domain this record belongs to. Unlike tags, domain is a single value that identifies the broad area of concern.

Examples: `backend`, `frontend`, `data-engineering`, `security`, `devops`, `ml-infrastructure`, `architecture`

#### supporting_sessions

A list of session-summary references that provide evidence for this claim. Every record MUST have at least one reference. The `SessionRef` structure:

```yaml
session_id: STRING          # e.g., "session-01"
session_file: STRING        # Relative path within the repo, e.g., "agent-conv/session-01.md"
relevant_section: STRING    # Optional: anchor or heading within the session file
timestamp: ISO8601          # Optional: when the supporting discussion occurred
```

#### evidence_references

External artifacts that support or contextualize the claim but are not session summaries. The `ExternalRef` structure:

```yaml
type: STRING          # e.g., "design_doc", "test_result", "benchmark", "config", "research_paper"
title: STRING         # Human-readable label
location: STRING      # Path, URL, or identifier (e.g., "DESIGN.md#3.2", "docs/benchmarks/perf.txt")
description: STRING   # Optional: what this reference contributes to the evidence
```

Common reference types: `design_doc`, `spec`, `test_result`, `benchmark`, `config`, `research_paper`, `code_comment`, `issue_tracker`, `log_file`, `diagram`

#### relationships

Explicit directional links to other evidence records. The `Relationship` structure:

```yaml
target: ID              # The record this relationship points to
type: STRING            # The nature of the relationship (see §5)
direction: OUTGOING     # Always OUTGOING from the perspective of this record
description: STRING     # Optional: why this relationship exists
```

Relationships are directional. Recording a relationship in only one record creates an implicit back-reference. When both directions carry meaningful information, both records should declare the relationship.

#### supersedes / superseded_by

Evolution links. `supersedes` points to older records whose claims this record refines or replaces. `superseded_by` is set on the older record to point to the newer record. These fields become relevant when status is `Superseded`.

#### created_at / updated_at

ISO 8601 timestamps in UTC. `created_at` is immutable; `updated_at` changes on every modification.

#### created_by / updated_by

The person or system that created or last modified the record. In agent-assisted workflows, this may be the human operator, not the AI agent.

---

## 4. Evidence Types Catalog

Each evidence type inherits all universal fields and MAY add type-specific fields. Type-specific fields are documented below. If a type has no additional fields, it uses only the universal schema.

---

### 4.1 Requirement (REQ)

#### Purpose

Captures **what** the system must do, a capability it must possess, or a property it must exhibit. Requirements come from user needs, business goals, compliance obligations, or technical necessity. They are the "north star" that subsequent decisions must satisfy.

Create a Requirement record when:
- A stakeholder expresses a clear need.
- A specification document defines a functional or non-functional requirement.
- A constraint analysis reveals a missing capability.
- Compliance or regulatory obligations impose obligations.

Do not create a Requirement for implementation details—those are Decisions.

#### Type-Specific Fields

```yaml
priority: STRING              # MUST | SHOULD | MAY
source: STRING                # Origin: "user_story", "stakeholder", "spec", "compliance", "hackathon_rules"
acceptance_criteria: STRING   # How to verify this requirement is met
scope: STRING                 # "functional" | "non_functional" | "constraint" | "quality_attribute"
```

#### Relationships

**Outgoing (common patterns):**
- Requirement → Constraint: Requirements impose constraints on the solution space.
- Requirement → Decision: A decision was made to satisfy this requirement.
- Requirement → Architecture: The architecture was shaped to fulfill this requirement.
- Requirement → Validation: Validation confirms the requirement is met.

**Incoming (common patterns):**
- Decision → Requirement: "This decision was driven by requirement REQ-003."
- Trade-off → Requirement: "We traded off REQ-005 to satisfy REQ-001."

#### Example Record

```yaml
id: REQ-001
type: REQ
title: "System must separate visual understanding from language generation"
summary: "The architecture must treat video understanding and caption generation as independent stages, connected only through a Canonical Video Report."
description: "The video captioning pipeline must decompose into two independent stages: (1) visual understanding that produces a factual Canonical Video Report, and (2) language generation that rewrites the CVR into target styles. The language stage must not access raw video data."
rationale: "Separating concerns prevents style generation from hallucinating facts. The language model can only manipulate text, not invent visual observations. This also allows the two stages to use different models optimized for different tasks."
status: Final
confidence: HIGH
tags: [architecture, separation-of-concerns, factual-consistency]
domain: architecture
priority: MUST
source: spec
acceptance_criteria: "Language generation stage takes only CVR text as input; no video data passes to the style generator."
scope: quality_attribute
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-004
    type: drives
    description: "Two-stage separation drove the CVR-as-interface decision"
```

#### Deduplication

Merge if two Requirement records describe the same capability at the same granularity, from the same source, with identical acceptance criteria. Keep separate if the requirements come from different stakeholders with different priorities, or if they address different aspects of the same high-level need (e.g., performance vs. security aspects of the same feature).

#### Superseding Rules

A Requirement may be superseded when stakeholder needs change, scope is reduced, or a requirement is found to be technically infeasible. The superseding record must explain why the original requirement is no longer valid.

---

### 4.2 Constraint (CON)

#### Purpose

Captures a **restriction** on the solution space. Constraints are not optional; they are boundaries that every valid solution must respect. Unlike requirements (which describe desired properties), constraints describe non-negotiable limitations.

Create a Constraint record when:
- External factors impose hard limits (budget, timeline, regulatory).
- Platform or infrastructure choices restrict options.
- Technical limitations of chosen tools become binding.
- Hackathon or competition rules impose restrictions.

#### Type-Specific Fields

```yaml
constraint_type: STRING       # "technical" | "business" | "regulatory" | "operational" | "competition"
severity: STRING              # "hard" (must be met) | "soft" (should be met, exceptions possible)
imposed_by: STRING            # What or who imposed the constraint
```

#### Relationships

**Outgoing:**
- Constraint → Decision: The constraint forced a particular decision.
- Constraint → Trade-off: A trade-off was necessary to work within the constraint.
- Constraint → Architecture: The architecture was shaped by this constraint.

**Incoming:**
- Requirement → Constraint: A requirement implies a constraint.
- Decision → Constraint: "We chose this constraint by deciding to use tool X."

#### Example Record

```yaml
id: CON-001
type: CON
title: "Total pipeline runtime must not exceed 10 minutes"
summary: "The hackathon rules impose a hard 10-minute wall-clock limit on the entire pipeline execution."
description: "From job start to exit, the pipeline must complete within 600 seconds. This includes video download, frame sampling, VLM inference, text generation, and JSON output."
rationale: "This is a competition-imposed constraint. Violating it results in disqualification. Every engineering decision must account for cumulative runtime."
status: Final
confidence: HIGH
tags: [runtime, hackathon, performance]
domain: architecture
constraint_type: competition
severity: hard
imposed_by: "Hackathon rules"
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: REQ-001
    type: interacts_with
    description: "Tight runtime budget reinforces the two-stage architecture for efficiency"
```

#### Deduplication

Merge if two Constraint records describe the same limitation from the same source. Keep separate if different sources impose similar constraints (e.g., "runtime ≤10 min" from hackathon rules is different from "response time ≤2s" from SLA).

#### Superseding Rules

A Constraint may be superseded when the imposing authority relaxes or removes it, or when the project phase changes (e.g., hackathon constraints are replaced by production constraints). The superseding record must cite the authority that changed the constraint.

---

### 4.3 Decision (DEC)

#### Purpose

The **central evidence type** in the EEM. Captures a definitive engineering choice after evaluating alternatives. Decisions are the pivot points where the project commits to a direction. Every Decision should reference at least one Alternative Considered record as evidence of deliberation.

Create a Decision record when:
- The team commits to one approach after evaluating others.
- A previously open question is resolved.
- A technology, pattern, or approach is selected for use.

Do not create a Decision for every code-level choice. Decisions should be **consequential**—they shape subsequent work.

#### Type-Specific Fields

```yaml
decision_type: STRING        # "technology_selection" | "architecture" | "process" | "design_pattern" | "tooling"
chosen_approach: STRING      # What was selected
alternatives_considered: LIST[ID]  # References to ALT records
driving_factors: LIST[STRING]      # Key reasons in priority order
```

#### Relationships

**Outgoing:**
- Decision → Alternative: This decision chose among these alternatives.
- Decision → Trade-off: This decision created these trade-offs.
- Decision → Architecture: This decision shaped the architecture.
- Decision → Validation: This decision was validated by this evidence.

**Incoming:**
- Requirement → Decision: "We made this decision to satisfy this requirement."
- Constraint → Decision: "The constraint forced this decision."
- Investigation → Decision: "Our investigation led to this decision."
- Challenge → Decision: "We made a decision to overcome this challenge."

#### Example Record

```yaml
id: DEC-001
type: DEC
title: "Select Qwen2.5-VL 32B as the vision-language model"
summary: "Qwen2.5-VL 32B Instruct was selected over InternVL3-8B due to its 128k context window, which eliminates the frame-count bottleneck for 30-120s videos."
description: "The VLM stage requires analyzing 16+ frames sampled from videos up to 120 seconds. InternVL3-8B's 16k context window forced a trade-off between frame count and resolution. Qwen2.5-VL 32B's 128k context window provides ~94k tokens of headroom, enabling higher frame counts and higher per-frame resolution without context truncation risk."
rationale: "Context window size was the binding constraint. InternVL3-8B required either reducing frame count (temporal coverage loss) or reducing per-frame resolution (spatial detail loss). Qwen2.5-VL eliminates this trade-off entirely: 16 frames at 768px consume ~33k tokens, leaving ~94k headroom. The 8x context increase is the decisive factor; model quality differences are secondary."
status: Final
confidence: HIGH
tags: [vlm, model-selection, context-window, fireworks]
domain: ml-infrastructure
decision_type: technology_selection
chosen_approach: "Qwen2.5-VL 32B Instruct on Fireworks AI"
alternatives_considered: [ALT-001]
driving_factors:
  - "128k context window enables high frame count at full resolution"
  - "Hosted API eliminates GPU management burden"
  - "OpenAI-compatible interface reduces integration complexity"
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: CON-001
    type: driven_by
    description: "Runtime constraint was verified against Qwen latency before committing"
  - target: ALT-001
    type: evaluated
    description: "InternVL3-8B was the primary alternative"
  - target: TRD-001
    type: creates
    description: "Choosing Qwen introduces a cloud API dependency"
```

#### Deduplication

Merge if two Decision records describe the same choice at the same scope, supported by the same alternatives and rationale. Keep separate if the same choice is made at different scope levels (e.g., choosing the VLM for the vision stage vs. choosing the model for the text stage), or if the rationales differ significantly.

#### Superseding Rules

A Decision is superseded when a new decision reverses or materially changes the approach. The new Decision must explain what changed—new information, new constraints, or corrected understanding. The old Decision remains in the map as context for why the project evolved.

---

### 4.4 Alternative Considered (ALT)

#### Purpose

Captures an option that was **evaluated but not chosen**. Alternatives provide the context necessary to understand why a decision was correct. A Decision without its Alternatives is a claim without evidence of deliberation.

Create an Alternative record whenever a Decision record is created and the team considered other options.

#### Type-Specific Fields

```yaml
rejection_reason: STRING      # Primary reason it was not chosen
strengths: LIST[STRING]       # What made this alternative attractive
weaknesses: LIST[STRING]      # What disqualified or disadvantaged it
```

#### Relationships

**Outgoing:**
- Alternative → Decision: The decision that rejected this alternative.
- Alternative → Constraint: The constraint that disqualified this alternative.

**Incoming:**
- Decision → Alternative: The decision evaluated this alternative.

Alternatives should rarely exist without an associated Decision.

#### Example Record

```yaml
id: ALT-001
type: ALT
title: "InternVL3-8B as vision-language model"
summary: "InternVL3-8B was evaluated as a candidate VLM but rejected due to its 16k context window limitation."
description: "InternVL3-8B is a capable open-source VLM but its 16k context window cannot accommodate 16 frames at 768px resolution. Fitting within the context budget would require reducing frame count to ~4-6 or resolution to ~256px, both of which would degrade video understanding quality."
rationale: "The 16k context window is incompatible with the frame budget required for 30-120s videos. While InternVL3 offers strong per-image understanding, the temporal coverage loss from reducing frame count is unacceptable. The 128k window on Qwen2.5-VL eliminates this trade-off."
status: Final
confidence: HIGH
tags: [vlm, model-evaluation, context-window, internvl]
domain: ml-infrastructure
rejection_reason: "16k context window is insufficient for 16+ high-resolution frames"
strengths:
  - "Open-source and self-hostable"
  - "Lower latency than Qwen2.5-VL 32B"
  - "No API cost or rate limits"
weaknesses:
  - "16k context window caps frame count or resolution"
  - "Smaller model may produce less accurate video understanding"
  - "Self-hosting adds operational complexity"
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-001
    type: rejected_by
    description: "Rejected in favor of Qwen2.5-VL 32B"
  - target: CON-001
    type: incompatible_with
    description: "Would violate runtime constraint if used with adequate frame count"
```

#### Deduplication

Merge if two Alternative records describe the same option evaluated for the same Decision and the rejection reasons align. Keep separate if the same option was evaluated for different Decisions (e.g., InternVL3 evaluated as both VLM and text generator) because the rejection reasons differ by context.

#### Superseding Rules

Alternatives are rarely superseded because they represent historical evaluation. If a previously rejected alternative is re-evaluated and adopted, the old ALT is not superseded—instead, a new Decision is created that references the ALT and explains what changed.

---

### 4.5 Trade-off (TRD)

#### Purpose

Captures an explicit **gain and sacrifice** resulting from a Decision. Trade-offs make the cost of decisions visible. Without them, the map paints an unrealistically positive picture of every choice.

Create a Trade-off record when a Decision demonstrably improves one quality attribute at the expense of another. Not every Decision creates a Trade-off—but most consequential ones do.

#### Type-Specific Fields

```yaml
gained: LIST[STRING]           # What improved or was enabled
sacrificed: LIST[STRING]       # What degraded or was constrained
mitigation: STRING             # Optional: how the sacrifice is managed
reversibility: STRING          # "reversible" | "hard_to_reverse" | "irreversible"
```

#### Relationships

**Outgoing:**
- Trade-off → Decision: The decision that created this trade-off.
- Trade-off → Challenge: The sacrificed quality later became a challenge.
- Trade-off → Lesson Learned: Retrospective insight about the trade-off.

**Incoming:**
- Decision → Trade-off: The decision produced this trade-off.
- Architecture → Trade-off: An architectural choice created this trade-off.

#### Example Record

```yaml
id: TRD-001
type: TRD
title: "Cloud API dependency vs. self-hosting for VLM inference"
summary: "Using Fireworks-hosted Qwen2.5-VL eliminates GPU management but creates an external API dependency and runtime cost."
description: "Self-hosting InternVL3-8B would provide full operational control, zero API cost, and no network dependency. Fireworks-hosted Qwen2.5-VL removes the self-hosting burden but introduces dependency on an external service and per-request cost at runtime."
rationale: "The trade-off was acceptable because the hackathon's tight timeline made self-hosting infeasible, and the 128k context window gain from Qwen2.5-VL depended on cloud hosting. For production, a self-hosted alternative should be re-evaluated."
status: Final
confidence: HIGH
tags: [api-dependency, self-hosting, fireworks, operational]
domain: devops
gained:
  - "128k context window enables high frame count and resolution"
  - "Zero GPU infrastructure management"
  - "Faster integration via OpenAI-compatible API"
sacrificed:
  - "Operational independence from Fireworks AI"
  - "Per-request API cost at runtime"
  - "Network dependency introduces failure mode"
mitigation: "The pipeline handles API failures with per-task error isolation; a single failed VLM call is logged and the task skips gracefully."
reversibility: reversible
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-001
    type: created_by
    description: "Trade-off of choosing Qwen2.5-VL over self-hosting InternVL3"
  - target: CHL-001
    type: leads_to
    description: "API dependency later caused connection management challenges"
```

#### Deduplication

Merge if two Trade-off records describe the same gain-sacrifice pair from the same Decision. Keep separate if the same Decision creates multiple distinct trade-offs (e.g., performance vs. cost and simplicity vs. flexibility are separate trade-offs).

#### Superseding Rules

A Trade-off may be superseded when mitigation makes the sacrifice irrelevant, or when a new Decision eliminates the trade-off entirely (e.g., a new model that provides both qualities without compromise).

---

### 4.6 Architecture (ARC)

#### Purpose

Captures a **structural or organizational choice** about the system's components, boundaries, data flow, or deployment. Architecture records are higher-level than Decisions—they describe the resulting structure, not the deliberation.

Create an Architecture record when:
- A component boundary is established.
- A data flow or interface contract is defined.
- A deployment topology or scaling strategy is chosen.
- A cross-cutting concern (logging, authentication, error handling) is designed.

#### Type-Specific Fields

```yaml
component_name: STRING         # Name of the architectural component being described
concern: STRING                # E.g., "separation_of_concerns", "data_flow", "deployment", "error_handling"
boundary_contract: STRING      # What crosses this boundary and in what format
```

#### Relationships

**Outgoing:**
- Architecture → Decision: Decisions that shaped this architectural choice.
- Architecture → Challenge: Challenges encountered implementing this architecture.
- Architecture → Validation: Validation that confirms the architecture works.

**Incoming:**
- Decision → Architecture: The decision created this architectural choice.
- Requirement → Architecture: The architecture satisfies this requirement.
- Constraint → Architecture: The architecture was constrained by this limitation.

#### Example Record

```yaml
id: ARC-001
type: ARC
title: "Two-stage pipeline: VLM stage → CVR → Text stage"
summary: "The pipeline is decomposed into a video understanding stage (VLM) and a language generation stage (text LLM), connected only by the Canonical Video Report."
description: "Stage 1 (VLM) ingests video frames and produces a Canonical Video Report (CVR) as a JSON document. Stage 2 (text LLM) takes the CVR and requested styles as input and produces styled captions. The CVR is the only data that crosses the stage boundary."
rationale: "This separation prevents factual hallucination during style generation. The text model cannot see the video and can only manipulate the CVR's text. Each stage can be optimized independently: low-temperature for factual VLM, higher-temperature for creative text generation."
status: Final
confidence: HIGH
tags: [pipeline, separation-of-concerns, cvr, architecture]
domain: architecture
component_name: "Pipeline architecture"
concern: separation_of_concerns
boundary_contract: "CVR JSON document — Stage 1 output, Stage 2 input"
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: REQ-001
    type: satisfies
  - target: DEC-001
    type: shaped_by
    description: "VLM model choice determines Stage 1 characteristics"
  - target: DEC-004
    type: implements
    description: "CVR-as-interface decision is the implementation of this architecture"
```

#### Deduplication

Merge if two Architecture records describe the same component boundary, same concern, with identical rationale. Keep separate if they describe different components or different concerns of the same component (e.g., a component's data model vs. its error handling are separate architecture records).

#### Superseding Rules

An Architecture record is superseded when the system is restructured. This is common during major refactors or when new requirements force architectural change. The superseding record must explain what new information drove the restructure.

---

### 4.7 Challenge (CHL)

#### Purpose

Captures a **problem, obstacle, or blocker** encountered during implementation. Challenges connect decisions to their real-world consequences. They are the bridge between "we chose X" and "X caused problem Y."

Create a Challenge record when:
- An unexpected problem arises during implementation.
- A known risk materializes.
- A constraint blocks progress.
- An external dependency fails or changes.

#### Type-Specific Fields

```yaml
severity: STRING               # "blocker" | "major" | "minor" | "cosmetic"
resolution_status: STRING      # "resolved" | "mitigated" | "accepted" | "open"
resolution_approach: STRING    # How it was addressed, if resolved
```

#### Relationships

**Outgoing:**
- Challenge → Investigation: The challenge prompted an investigation.
- Challenge → Decision: A decision was made to resolve the challenge.
- Challenge → Root Cause: Investigation revealed the root cause.
- Challenge → Trade-off: The challenge is a consequence of a trade-off.

**Incoming:**
- Decision → Challenge: "This decision introduced this challenge."
- Trade-off → Challenge: "The sacrificed quality manifested as this challenge."
- Architecture → Challenge: "The architecture created this challenge."

#### Example Record

```yaml
id: CHL-001
type: CHL
title: "Fireworks API does not support native video file upload"
summary: "The Fireworks OpenAI-compatible API only accepts image content (base64 data URLs), not video files, forcing a frame-sampling workaround."
description: "The initial design assumed the VLM could accept video files directly. Testing revealed the Fireworks API's `/chat/completions` endpoint only supports image content types. Native video upload would require a different API or a different provider."
rationale: "This challenge was a platform limitation, not a design flaw. It forced the architecture to adopt uniform frame sampling as the video ingestion method, which became a core design constraint."
status: Final
confidence: HIGH
tags: [api-limitation, firework, frame-sampling, video-ingestion]
domain: ml-infrastructure
severity: major
resolution_status: mitigated
resolution_approach: "Adopted uniform frame sampling with configurable frame count (default 16) as the canonical video ingestion method"
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-002
    type: led_to
    description: "Frame-sampling approach was adopted as the workaround"
  - target: INV-001
    type: triggered
    description: "Investigated optimal frame count for temporal coverage"
```

#### Deduplication

Merge if two Challenge records describe the same problem arising from the same root cause and addressed by the same resolution. Keep separate if similar symptoms have different root causes, or if the same problem recurs after being resolved (the recurrence is a new Challenge with a different context).

#### Superseding Rules

A Challenge may be superseded when the underlying condition changes. For example, a platform limitation is superseded when the platform adds support. The superseding record must reference the platform change or resolution that eliminated the challenge.

---

### 4.8 Investigation (INV)

#### Purpose

Captures a **structured inquiry** into a problem, question, or hypothesis. Investigations are the engineering process of gathering data, running experiments, and analyzing results before reaching a conclusion.

Create an Investigation record when:
- A problem requires root cause analysis.
- A hypothesis needs experimental validation.
- A technology requires evaluation beyond reading documentation.
- Performance characteristics need measurement.

#### Type-Specific Fields

```yaml
investigation_type: STRING     # "root_cause" | "performance" | "feasibility" | "comparative" | "exploratory"
hypothesis: STRING             # What was being tested or investigated
methodology: STRING            # How the investigation was conducted
findings: STRING               # What was discovered
conclusion: STRING             # What the findings mean for the project
```

#### Relationships

**Outgoing:**
- Investigation → Root Cause: Investigation revealed a root cause.
- Investigation → Decision: Findings led to a decision.
- Investigation → Result: Investigation produced measurable results.

**Incoming:**
- Challenge → Investigation: The challenge prompted this investigation.
- Decision → Investigation: "We investigated this before deciding."
- Hypothesis → Investigation: A hypothesis was tested.

#### Example Record

```yaml
id: INV-001
type: INV
title: "Determine optimal frame count for 30-120s videos under Qwen 128k context"
summary: "Investigated the trade-off between frame count, temporal coverage, and token budget to determine the default frame sampling configuration."
description: "Evaluated frame counts from 4 to 32 across videos of varying duration (30s, 60s, 90s, 120s). Measured token consumption from system prompt, user prompt, and per-frame encoding at 768px resolution. Analyzed temporal coverage gaps at each frame count. Goal: find the count that maximizes temporal coverage within the 128k context budget."
rationale: "The frame count is a critical parameter affecting both video understanding quality and token cost. Setting it too low loses temporal information. Setting it too high wastes tokens and increases latency. An evidence-based default was needed."
methodology: "Token estimation was done analytically using known per-frame encoding costs (~2,000 tokens/frame at 768px). Temporal coverage was modeled as uniform sampling interval. Headroom was calculated as 128k - (system + user prompt + frames + response buffer)."
findings: "16 frames at 768px consumed ~33k tokens total (26% of context), leaving ~94k headroom. Coverage interval was ~1.87s for 30s videos to ~7.5s for 120s videos. 24 frames remained within budget (~48k tokens) and would improve 120s coverage to ~5s intervals."
conclusion: "16 frames is the default sweet spot. The design should support configurable frame counts so operators can increase to 24 for longer videos if needed."
status: Final
confidence: HIGH
tags: [frame-sampling, token-budget, temporal-coverage, optimization]
domain: ml-infrastructure
investigation_type: performance
hypothesis: "16 frames provides adequate temporal coverage for 30-120s videos without exceeding 50% of the 128k context window"
methodology: "Analytical token estimation + temporal coverage modeling across video durations"
findings: "16 frames at 768px → ~33k tokens (26% of context), coverage interval 1.87s–7.5s depending on video duration"
conclusion: "Adopt 16 frames as default with configurable override; 24 frames viable for 120s+ videos"
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-002
    type: informed
    description: "Investigation results directly informed the default frame count decision"
  - target: CHL-001
    type: triggered_by
    description: "API limitation investigation led to frame sampling parameter study"
```

#### Deduplication

Merge if two Investigation records study the same hypothesis with the same methodology and reach the same conclusion. Keep separate if they study different aspects of the same problem, or if a follow-up investigation supersedes earlier findings.

#### Superseding Rules

An Investigation may be superseded by a follow-up investigation with better methodology, more data, or different experimental conditions. The new Investigation must reference the old one via `supersedes` and explain what methodological improvement justifies the update.

---

### 4.9 Root Cause Analysis (RCA)

#### Purpose

Captures the **fundamental cause** of a problem, distinct from its symptoms. RCA records distinguish between proximal cause (what happened immediately before the failure) and root cause (the systemic condition that allowed the failure to occur).

Create an RCA record when:
- A significant problem occurs that warrants structured analysis.
- An Investigation reveals a systemic cause.
- The same problem pattern recurs, indicating a deeper issue.
- A post-mortem or incident review is conducted.

#### Type-Specific Fields

```yaml
symptom: STRING                # Observable problem that triggered the analysis
root_cause: STRING             # The fundamental systemic condition
contributing_factors: LIST[STRING]  # Conditions that amplified the impact
proximal_cause: STRING         # Trigger event, distinct from root cause
prevention: STRING             # How to prevent recurrence
detection: STRING              # How to detect recurrence if prevention fails
```

#### Relationships

**Outgoing:**
- RCA → Decision: Analysis led to a decision to prevent recurrence.
- RCA → Lesson Learned: Generalizable insight from the analysis.
- RCA → Requirement: New requirement to prevent this class of problem.

**Incoming:**
- Challenge → RCA: Root cause of this challenge.
- Investigation → RCA: Investigation produced this root cause analysis.

#### Example Record

```yaml
id: RCA-001
type: RCA
title: "Frame sampler fails on videos with corrupted metadata"
summary: "cv2.VideoCapture.get(cv2.CAP_PROP_FRAME_COUNT) returns 0 for corrupted videos, causing uniform frame sampling to fail with a division-by-zero."
description: "Some video files have valid pixel data but corrupted container metadata (e.g., truncated headers, non-standard containers). cv2.VideoCapture reports total_frames = 0 or duration = 0 for these files, causing the uniform sampling logic to crash."
rationale: "The root cause is not the corrupted metadata itself—that's a video provenance issue. The root cause is the absence of a defensive fallback: the sampler assumed valid metadata, with no alternative ingestion path."
symptom: "Uniform frame sampling crashes with division-by-zero for certain video files"
root_cause: "No defensive fallback path when video metadata is corrupted; sampler relies exclusively on metadata-driven indexing"
contributing_factors:
  - "cv2 library reports 0 frames without raising an exception for corrupt metadata"
  - "Video source (URL download) provides no metadata validation layer"
proximal_cause: "cv2.VideoCapture.get(cv2.CAP_PROP_FRAME_COUNT) returned 0"
prevention: "Implement metadata validation gate before sampling; fall back to sequential read if metadata is suspect"
detection: "Add pre-sampling check: if total_frames <= 0, log warning and switch to sequential read path"
status: Final
confidence: HIGH
tags: [video-processing, error-handling, metadata, defensive-design]
domain: ml-infrastructure
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-003
    type: informed
    description: "Root cause analysis directly informed the sequential-read fallback decision"
  - target: CHL-002
    type: explains
    description: "Explains why the sampler crash occurred on certain videos"
```

#### Deduplication

Merge if two RCA records identify the same root cause for the same symptom. Keep separate if the same root cause produces different symptoms, or if the same symptom has different root causes in different contexts.

#### Superseding Rules

An RCA may be superseded if deeper investigation reveals an even more fundamental root cause. The new RCA must explain what new information or analysis technique revealed the deeper cause.

---

### 4.10 Validation (VAL)

#### Purpose

Captures **evidence that confirms or refutes** a Decision, Architecture, Requirement, or hypothesis. Validation closes the loop: it turns "we decided X" into "we decided X and here is proof it worked."

Create a Validation record when:
- A test confirms that a decision produced the expected outcome.
- A benchmark provides quantitative evidence.
- A review or audit confirms compliance.
- Production metrics validate an architectural choice.
- Experimental results support or refute a hypothesis.

#### Type-Specific Fields

```yaml
validation_type: STRING        # "test" | "benchmark" | "review" | "production_metric" | "experiment" | "audit"
validates: ID                  # The record this validation confirms or refutes
outcome: STRING                # "confirmed" | "refuted" | "inconclusive" | "partial"
evidence_summary: STRING       # Concrete data or observations that support the outcome
```

#### Relationships

**Outgoing:**
- Validation → Decision: This validation confirms or refutes this decision.
- Validation → Architecture: This validation confirms the architecture works.
- Validation → Requirement: This validation confirms the requirement is met.

**Incoming:**
- Decision → Validation: The decision was validated by this evidence.
- Investigation → Validation: The investigation's conclusions were validated.

#### Example Record

```yaml
id: VAL-001
type: VAL
title: "16-frame sampling produces adequate temporal coverage for 30-120s videos"
summary: "Runtime testing confirmed that 16 uniformly sampled frames at 768px resolution provide sufficient temporal coverage across the target video duration range."
description: "Tested the frame sampler across 10 videos ranging from 30s to 120s. Measured inter-frame gap, critical event capture rate, and VLM output quality at 16 frames vs. 8 frames and 24 frames."
rationale: "The token investigation (INV-001) was analytical; this validation provides empirical confirmation that 16 frames is the right default in practice."
status: Final
confidence: HIGH
tags: [frame-sampling, validation, temporal-coverage, testing]
domain: ml-infrastructure
validation_type: experiment
validates: INV-001
outcome: confirmed
evidence_summary: "At 16 frames, critical events were captured in 9/10 test videos. At 8 frames, 3/10 videos missed events. At 24 frames, 10/10 captured but with no quality improvement over 16."
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-002
    type: validates
    description: "Confirms the 16-frame default decision"
  - target: INV-001
    type: supports
```

#### Deduplication

Merge if two Validation records confirm the same claim with the same evidence. Keep separate if they validate the same claim with different types of evidence (e.g., a benchmark and a production metric are separate validations).

#### Superseding Rules

A Validation may be superseded if new evidence contradicts it, or if the validation methodology is found to be flawed. The superseding record must explain the methodological issue or the new contradictory evidence.

---

### 4.11 Result (RES)

#### Purpose

Captures a **measurable outcome** from a Decision, Architecture, or Validation. Results are quantitative or qualitative observations about the consequences of engineering choices. They differ from Validations: Validations confirm whether a choice was correct; Results describe what happened as a consequence.

Create a Result record when:
- A decision produces measurable performance changes.
- An architecture change yields observably different system behavior.
- A trade-off's consequences become visible in practice.

#### Type-Specific Fields

```yaml
result_type: STRING            # "quantitative" | "qualitative" | "observational"
metric: STRING                 # For quantitative results: what was measured
value: STRING                  # The measured value or observed outcome
baseline: STRING               # Previous value for comparison, if applicable
interpretation: STRING         # What this result means in engineering terms
```

#### Relationships

**Outgoing:**
- Result → Decision: This result is a consequence of this decision.
- Result → Lesson Learned: The result contributed to a lesson.
- Result → Validation: The result supports this validation.

**Incoming:**
- Decision → Result: The decision produced this result.
- Validation → Result: The validation produced these measurements.

#### Example Record

```yaml
id: RES-001
type: RES
title: "Pipeline completes within 4-5 minutes for 10 tasks"
summary: "End-to-end pipeline runtime measured at 4-5 minutes for the target workload of 10 video tasks, well under the 10-minute constraint."
description: "Measured total runtime across 3 full pipeline executions of 10 randomly selected videos. Per-task breakdown: video download ~5s, frame sampling ~2s, VLM inference ~11s, style generation ~8s (4 styles at ~2s each). Total: ~26s per task."
rationale: "The runtime measurement confirms the pipeline architecture is viable within the hackathon constraint. The 5-minute margin provides buffer for network variability and longer videos."
status: Final
confidence: HIGH
tags: [runtime, performance, benchmarking, constraint-compliance]
domain: architecture
result_type: quantitative
metric: "End-to-end pipeline wall-clock time"
value: "4m 20s to 5m 10s for 10 tasks"
baseline: "10-minute constraint ceiling"
interpretation: "Pipeline has ~5 minutes of headroom within the constraint. The dominant cost is VLM API inference; frame sampling and style generation are negligible."
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: CON-001
    type: satisfies
    description: "Pipeline runtime is well within the 10-minute constraint"
  - target: DEC-002
    type: consequence_of
    description: "16-frame sampling contributes negligible latency"
```

#### Deduplication

Merge if two Result records describe the same metric from the same measurement. Keep separate if they measure different aspects of the same outcome (e.g., latency and throughput), or if measurements were taken under different conditions.

#### Superseding Rules

A Result may be superseded when the system changes in ways that invalidate the measurement, or when new measurements under different conditions supersede old ones. The superseding record must specify the changed conditions.

---

### 4.12 Lesson Learned (LES)

#### Purpose

Captures a **retrospective insight** that should influence future work. Lessons are the highest-level knowledge product in the EEM—they synthesize across decisions, challenges, and results to produce generalizable engineering wisdom.

Create a Lesson Learned record when:
- A pattern of outcomes reveals a general principle.
- A painful experience suggests a practice to adopt or avoid.
- A successful approach can be generalized beyond the current context.
- The team reflects on what they would do differently.

#### Type-Specific Fields

```yaml
lesson_type: STRING            # "do" | "avoid" | "insight" | "process_change"
applicability: STRING          # When and where this lesson applies
actionability: STRING          # What specific action should be taken
generality: STRING             # "project_specific" | "domain_specific" | "universal"
```

#### Relationships

**Outgoing:**
- Lesson Learned → Decision: This lesson should inform future decisions.
- Lesson Learned → Trade-off: This trade-off taught this lesson.
- Lesson Learned → Root Cause: This root cause analysis revealed this lesson.

**Incoming:**
- Decision → Lesson Learned: "This decision taught us..."
- Challenge → Lesson Learned: "Overcoming this challenge taught us..."
- Result → Lesson Learned: "These results taught us..."

Lessons should synthesize across multiple evidence types. A Lesson supported by only one record is probably not generalizable enough to be a Lesson.

#### Example Record

```yaml
id: LES-001
type: LES
title: "Trust executable artifacts over prose documentation as the source of truth"
summary: "Prose documentation diverges from reality; executable code, config files, and working scripts are more reliable indicators of actual system behavior."
description: "While constructing an AGENTS.md file for project onboarding, the assistant discovered that design documents described features that had not been implemented and scripts that no longer worked. By contrast, running `fireworks_test_deployment.py` revealed the exact API behavior, parameter values, and failure modes that actually existed."
rationale: "This lesson is not about documentation quality—it's about trust decay. Documentation is a snapshot of intent at a point in time. Executable artifacts are continuously validated by the runtime. When they disagree, the runtime is correct."
status: Final
confidence: HIGH
tags: [documentation, source-of-truth, onboarding, agent-instructions]
domain: software-engineering
lesson_type: insight
applicability: "Any project where documentation and code coexist—essentially all software projects"
actionability: "When onboarding or investigating a system, run the code first, read the docs second. When writing docs, embed executable validation so they can't go stale."
generality: universal
supporting_sessions:
  - session_id: session-01
    session_file: agent-conv/session-01.md
relationships:
  - target: DEC-005
    type: synthesized_from
    description: "Several decisions were informed by running code rather than reading docs"
```

#### Deduplication

Merge if two Lesson Learned records express the same insight at the same level of generality, even if they were learned from different projects. Keep separate if the same general principle produces different specific action items, or if the lesson's applicability scope differs.

#### Superseding Rules

A Lesson may be superseded if experience contradicts it, or if the insight is refined by more evidence. For example, "always do X" may be refined to "do X under conditions A, B; avoid X under condition C." The refined lesson supersedes the original.

---

## 5. Evidence Relationships

### 5.1 Relationship Model

Relationships in the EEM are **directional** and **typed**. They form a knowledge graph where nodes are evidence records and edges carry semantic meaning.

A relationship is declared in one direction only (the "outgoing" direction from a record's perspective). Bidirectional meaning is achieved by declaring complementary relationships in both records.

### 5.2 Canonical Relationship Types

| Relationship Type | Description | Common Direction |
|---|---|---|
| `drives` | A requirement or constraint drives a decision | REQ → DEC, CON → DEC |
| `driven_by` | A decision is driven by a requirement or constraint | DEC → REQ, DEC → CON |
| `evaluated` | A decision evaluated an alternative | DEC → ALT |
| `rejected_by` | An alternative was rejected by a decision | ALT → DEC |
| `creates` | A decision creates a trade-off | DEC → TRD |
| `created_by` | A trade-off was created by a decision | TRD → DEC |
| `informed` | An investigation informed a decision | INV → DEC |
| `informed_by` | A decision was informed by an investigation | DEC → INV |
| `satisfies` | An architecture or result satisfies a requirement | ARC → REQ, RES → REQ |
| `implements` | A decision or architecture implements something | DEC → ARC |
| `imposed_by` | A constraint was imposed by something | CON → REQ |
| `shapes` | Something shapes the architecture | DEC → ARC, CON → ARC |
| `shaped_by` | Architecture was shaped by something | ARC → DEC, ARC → CON |
| `led_to` | A challenge led to a decision or investigation | CHL → DEC, CHL → INV |
| `triggered` | Something triggered an investigation | CHL → INV |
| `triggered_by` | An investigation was triggered by a challenge | INV → CHL |
| `explains` | Root cause explains a challenge | RCA → CHL |
| `led_to` (RCA) | Root cause led to a decision | RCA → DEC |
| `validates` | Validation confirms a decision or architecture | VAL → DEC, VAL → ARC |
| `validated_by` | Something was validated by validation | DEC → VAL |
| `consequence_of` | A result is a consequence of a decision | RES → DEC |
| `supports` | Validation or result supports an investigation | VAL → INV, RES → INV |
| `synthesized_from` | A lesson was synthesized from decisions or results | LES → DEC, LES → RES |
| `contradicts` | One claim contradicts another | Any → Any |
| `depends_on` | One record depends on another for context | Any → Any |
| `interacts_with` | Two records have a non-trivial interaction | Any → Any |

### 5.3 Common Engineering Flows

#### Flow 1: Requirement → Decision → Trade-off → Result

```text
REQ-001 ──drives──▶ DEC-001 ──creates──▶ TRD-001
                                         │
                           RES-001 ◄─ consequence_of
```

#### Flow 2: Challenge → Investigation → Root Cause → Decision → Validation

```text
CHL-001 ──triggered──▶ INV-001 ──informed──▶ RCA-001
                                               │
DEC-003 ◄──────────────────────────── led_to ──┘
   │
   └──validated_by──▶ VAL-001
```

#### Flow 3: Decision with Alternatives

```text
              ALT-001 (rejected)
                    ▲
                    │ rejected_by
                    │
REQ-001 ──drives──▶ DEC-001
                    │
                    │ evaluated
                    ▼
              ALT-002 (rejected)
```

#### Flow 4: Architecture → Challenge → Lesson

```text
ARC-001 ──shaped_by──▶ CHL-001 ──triggered──▶ INV-001
                                                 │
LES-001 ◄────────────────── synthesized_from ────┘
```

#### Flow 5: Supersession Chain

```text
DEC-003 (Final) ──supersedes──▶ DEC-003a (Superseded) ──supersedes──▶ DEC-003b (Superseded)
```

### 5.4 Relationship Cardinality Rules

- A record may have zero, one, or many outgoing relationships.
- A relationship type should be used consistently: `drives` always means "influences with authority" while `informs` means "provides evidence for."
- Avoid creating relationship types for one-off connections—use `interacts_with` with a description.
- A record SHOULD NOT have more than one relationship of the same type to the same target, unless each instance describes a different aspect of the connection.

### 5.5 Anti-Patterns

- **Re-linking instead of relating**: Don't duplicate the content of one record in another. Link to it.
- **Implicit relationships**: If two records are conceptually related, make the relationship explicit.
- **Orphan records**: Every record should have at least one outgoing relationship (to prevent knowledge silos).
- **Dangling references**: Every relationship target must exist. Deleting a record must update all incoming relationships.

---

## 6. Evidence Lifecycle

### 6.1 Status Definitions

| Status | Definition | When to Use |
|---|---|---|
| `Draft` | Initial creation; content may be incomplete or unverified. | A new record is started but has not been fully researched or validated. |
| `Investigating` | Actively being researched; data is being gathered. | An investigation is in progress; the record is accumulating evidence. |
| `Final` | Content is complete, validated, and represents the team's current understanding. | The record is authoritatively correct at this point in time. Most records should be Final. |
| `Superseded` | Content was once Final but has been refined or replaced by a newer record. | A newer record (pointed to by `superseded_by`) now represents the correct claim. |
| `Planned` | Identified as needed but not yet created or investigated. | A placeholder for evidence that will be created in future sessions. |
| `Rejected` | Evaluated and determined to be invalid, incorrect, or not applicable. | A claim was examined and found to be wrong, or an alternative was rejected. |

### 6.2 State Transitions

```text
                    ┌──────────┐
                    │  Planned │
                    └────┬─────┘
                         │ work begins
                         ▼
  ┌──────────┐     ┌──────────┐
  │ Rejected │◄────│  Draft   │
  └──────────┘     └────┬─────┘
        ▲               │
        │ invalid       │ more data needed
        │               ▼
        │         ┌──────────────┐
        │         │ Investigating│
        │         └──────┬───────┘
        │                │ evidence gathered
        │                ▼
        │         ┌──────────┐
        └─────────│  Final   │
                  └────┬─────┘
                       │ new information
                       ▼
                  ┌────────────┐
                  │ Superseded │
                  └────────────┘
```

### 6.3 Transition Rules

1. **Planned → Draft**: When work begins on the record. Required: `updated_at` timestamp.
2. **Draft → Investigating**: When more data is needed. Optional but recommended for complex claims.
3. **Draft → Final** or **Investigating → Final**: When the claim is validated and complete. Required: at least one `supporting_session` reference. The `confidence` field must be set.
4. **Draft → Rejected**: When investigation reveals the claim is invalid. Required: rejection reason in `description`.
5. **Final → Superseded**: When a newer record refines or replaces this claim. Required: `superseded_by` pointing to the new record. The new record must link back via `supersedes`.
6. Any status → **Draft**: A record may return to Draft if new information raises questions. This preserves the history of the prior status.

### 6.4 Immutable Transitions

The following transitions are prohibited:
- **Superseded → Final**: A superseded record cannot be revived—create a new record instead.
- **Rejected → Final**: A rejected claim can be re-evaluated, but the new claim should be a separate record for clarity.

---

## 7. What Should NOT Become Evidence

The EEM is a curated knowledge store. Not everything said or done during a project belongs in it. The following categories must remain outside the EEM.

### 7.1 Explicit Exclusions

| Category | Example | Why Excluded |
|---|---|---|
| Source code | Function implementations, class definitions, inline logic | Code is the *subject* of evidence, not evidence itself. A Decision may reference code, but the code belongs in the repository. |
| File paths and directory structures | "Moved `foo.py` to `src/utils/`" | Implementation detail. Architecture decisions about module boundaries may be evidence; file organization is not. |
| API reference documentation | "The `download_video()` function takes `url` and `timeout` params" | Belongs in code comments or generated docs, not the EEM. |
| Build/CI configuration | "Added lint step to GitHub Actions" | Process detail. Unless it reflects an engineering decision (e.g., "chose Ruff over pylint"), it stays out. |
| Temporary experiments | "Tried Python 3.13 alpha, reverted" | If the experiment produced generalizable findings, those become an Investigation record. The experiment itself does not. |
| Conversation management | "The agent asked for clarification about the spec" | Meta-interaction detail. Not engineering knowledge. |
| AI interaction details | "Used model X with prompt Y and temperature Z" | The *insight* from the interaction may be evidence. The interaction mechanics are not. |
| Routine edits and minor fixes | "Fixed typo in variable name", "Updated docstring" | No engineering reasoning is involved. |
| Non-engineering discussions | "Discussed team lunch options", "Sprint planning logistics" | Not engineering knowledge. |
| Raw logs and stack traces | Full error output from a failed run | The session summary may excerpt them. The EEM should reference the analysis (an RCA or Investigation), not the raw logs. |
| Meeting metadata | "Meeting held on Jan 15, attendees: A, B, C" | Session summaries capture this. The EEM extracts the engineering content. |
| Unprocessed data | Raw benchmark results, unlabeled experiment output | Process the data into a Result record. The raw data lives outside the EEM. |

### 7.2 The Filtering Heuristic

When deciding whether something belongs in the EEM, ask:

> Would a future engineer working on a different project benefit from knowing this?

If yes, it is likely evidence. If the answer is "only for this specific project," it may still be evidence if it captures a Decision, Architecture, or Lesson. If the answer is "only for this specific file," it is implementation detail—exclude it.

---

## 8. Identifier Scheme

### 8.1 Convention

```
{PREFIX}-{ZERO_PADDED_NUMBER}
```

Where `PREFIX` is a three-letter abbreviation for the evidence type:

| Type | Prefix |
|---|---|
| Requirement | `REQ` |
| Constraint | `CON` |
| Decision | `DEC` |
| Alternative Considered | `ALT` |
| Trade-off | `TRD` |
| Architecture | `ARC` |
| Challenge | `CHL` |
| Investigation | `INV` |
| Root Cause Analysis | `RCA` |
| Validation | `VAL` |
| Result | `RES` |
| Lesson Learned | `LES` |

The number portion is zero-padded to at least three digits (`001`, `012`, `103`). This supports up to 999 records per type before expanding padding, which covers all but the largest engineering efforts. If a project exceeds 999 records of a type, the padding expands to four digits for new records; existing three-digit IDs remain valid.

### 8.2 Rules

1. **IDs are globally unique** within a project. No two records share the same ID, even across types.
2. **IDs are immutable**. A record's ID never changes, even when the record is superseded.
3. **IDs are never reused**. Deleted or superseded record IDs remain permanently retired.
4. **Chronological assignment is NOT required**. Records may be assigned IDs out of creation order. The `created_at` timestamp captures chronology; the ID is for stable reference.
5. **Gaps in numbering are acceptable**. If DEC-005 is deleted after being superseded, DEC-006 still follows DEC-004. Gaps do not imply missing records.

### 8.3 Maintainability Rationale

- **Human-readable prefixes**: A three-letter code is instantly recognizable. An engineer scanning a relationship field sees `DEC-012` and immediately knows it references a decision.
- **Sortable**: Zero-padded numbers sort correctly in file systems, search results, and text editors.
- **Collision-free**: The prefix namespace prevents accidental ID reuse across types.
- **No global registry**: Each project maintains its own sequence. No cross-project coordination is needed.
- **Stable across reorgs**: Unlike path-based identifiers, prefix IDs survive directory renames, tool migrations, and file relocations.

---

## 9. Confidence Rules

### 9.1 Confidence Levels

| Level | Criteria | Typical Indicators |
|---|---|---|
| `HIGH` | The claim is supported by multiple independent sources of evidence, has been validated through testing or measurement, and there is no contradictory evidence. | Multiple session references, validated by experiment, peer-reviewed, confirmed by production metrics. |
| `MEDIUM` | The claim is supported by reasoning and at least one source of evidence, but validation is incomplete or relies on a single source. | Single session reference, supported by logical reasoning but not experimentally verified, or validated in a limited context. |
| `LOW` | The claim is preliminary, based on hypothesis or extrapolation, or supported by insufficient data. | Draft status, single anecdotal source, extrapolation from related but non-identical contexts, or high uncertainty acknowledged in the rationale. |

### 9.2 Objective Assignment Criteria

Confidence must be assigned based on objective evidence characteristics, not subjective feeling:

1. **Source count**: How many independent session summaries support this claim? (1 = weak, 2+ = stronger)
2. **Validation**: Has the claim been experimentally validated? (Yes = stronger, No = weaker)
3. **Corroboration**: Do other evidence records support or contradict this claim? (Support = stronger, Contradiction = lower)
4. **Specificity**: Is the claim specific and falsifiable, or vague and unfalsifiable? (Specific = can achieve HIGH, Vague = capped at MEDIUM)
5. **Time decay**: How old is the supporting evidence? Evidence older than the project's most recent major milestone should be re-evaluated.

### 9.3 Confidence Downgrade Triggers

A record's confidence MUST be downgraded from HIGH to MEDIUM when:
- A new investigation produces contradictory findings.
- The supporting session evidence is found to be incomplete or misinterpreted.
- The validation methodology is discovered to be flawed.

A record's confidence MUST be upgraded from MEDIUM to HIGH when:
- Additional independent sessions provide corroborating evidence.
- A validation experiment confirms the claim.
- The record's status transitions from Investigating to Final with complete evidence.

### 9.4 Confidence vs. Status

Confidence is independent of status. A `Draft` record may have LOW confidence; a `Final` record typically has HIGH or MEDIUM confidence. A `Superseded` record may have HIGH confidence (it was correct for its time) even though its content is no longer current.

---

## 10. Deduplication Rules

### 10.1 When to Merge

Merge two records into one when ALL of the following are true:

1. **Same claim**: They assert the same engineering conclusion.
2. **Same scope**: They apply to the same component, decision context, or level of abstraction.
3. **Same evidence**: They reference the same or substantially overlapping session summaries.
4. **Same lifecycle stage**: They are at the same level of maturity (two Drafts can merge; a Draft and a Final cannot).

When merging, combine their `supporting_sessions` and `evidence_references` lists, reconcile `tags`, and preserve the earlier `created_at` timestamp. The merged record receives a new `updated_at`.

### 10.2 When to Keep Separate

Keep two records separate when ANY of the following are true:

1. **Different scope**: They address the same concept at different levels of abstraction (e.g., "choose VLM model" vs. "choose VLM inference parameters").
2. **Different context**: The same approach was chosen for different reasons in different parts of the system.
3. **Supersession relationship**: One record supersedes the other. They are linked, not merged.
4. **Different evidence types**: A Decision and a Trade-off about the same choice are separate records with different purposes.
5. **Different confidence**: One is well-validated and the other is preliminary. Merge would dilute the stronger record.

### 10.3 Deduplication Process

1. When creating a new record, search existing records by tags, title keywords, and type.
2. If a potential duplicate is found, compare claims using the criteria above.
3. If they should merge, update the existing record instead of creating a new one.
4. If they should remain separate, ensure the relationship between them is explicit.

---

## 11. Superseding Rules

### 11.1 Purpose

Superseding preserves engineering history. It records that "we used to believe X, but now we believe Y because of Z." This auditable chain is essential for understanding why projects evolved the way they did.

### 11.2 Process

1. **Create a new record** that represents the updated engineering knowledge.
2. **Set `supersedes`** on the new record to reference the old record.
3. **Set `superseded_by`** on the old record to reference the new record.
4. **Change status** of the old record to `Superseded`.
5. **Preserve confidence** on the old record—it may still be HIGH (correct for its time).
6. **Document the reason** for supersession in the new record's `rationale` field.

### 11.3 What Supersession Is Not

- **Not deletion**: Superseded records are never removed.
- **Not correction**: A typo fix or clarification does not supersede—edit the original record and update `updated_at`.
- **Not accumulation**: Adding a new constraint does not supersede all prior constraints. Supersession means the old claim is materially replaced by the new one.

### 11.4 Chain Integrity

Supersession must form a complete, traversable chain. If DEC-005 supersedes DEC-003, and later DEC-008 supersedes DEC-005, then:

```
DEC-003.superseded_by = [DEC-005]
DEC-005.supersedes = [DEC-003]
DEC-005.superseded_by = [DEC-008]
DEC-008.supersedes = [DEC-005]
```

This chain must be maintained as part of the integrity of the EEM.

---

## 12. Traceability Rules

### 12.1 Reference Format

Every evidence record MUST reference at least one session summary in `supporting_sessions`. The session reference must include:

- `session_id`: A unique identifier for the session.
- `session_file`: The relative path within the repository to the session summary file.

Optionally:
- `relevant_section`: A heading or anchor within the session file pointing to the specific discussion.
- `timestamp`: ISO 8601 timestamp of when the supporting discussion occurred.

### 12.2 Minimum Traceability

| Evidence Status | Minimum Supporting Sessions |
|---|---|
| `Draft` | 0 (may be created before evidence is gathered) |
| `Investigating` | 1+ (must reference sessions where investigation occurred) |
| `Final` | 1+ |
| `Superseded` | 1+ (inherited from when it was Final) |
| `Planned` | 0 |
| `Rejected` | 0+ |

### 12.3 Best Practices

1. **Specificity**: Reference the specific section or heading within the session summary that contains the supporting discussion. A blanket reference to an entire session file is worse than no reference—it forces the auditor to re-read the entire session.

2. **Multiple sources**: When multiple sessions contribute to a claim, list all of them. The confidence of a claim correlates with the number of independent session references.

3. **Granularity**: A session may support multiple evidence records. A single paragraph in a session summary might be the evidence for a Decision, a Trade-off, and a Challenge—each record should reference the session independently.

4. **Forward references**: When creating a new session summary, reference any existing evidence records that it supports or contradicts. This maintains bidirectional traceability.

5. **No dangling evidence**: If a session summary is updated or corrected, audit all evidence records that reference it. A correction may require a confidence downgrade or supersession.

### 12.4 Audit Trail

To audit the evidence for any claim:

1. Read the claim's `description` and `rationale`.
2. Follow the `supporting_sessions` references to the session summaries.
3. Read the referenced sections to confirm they support the claim.
4. Follow `relationships` to related evidence records to confirm consistency.
5. Check `supersedes` / `superseded_by` to ensure the claim is current.

This trail should require no external information beyond the EEM and the session summary files.

---

## 13. Quality Guidelines

### 13.1 Consistency

- Use the same terminology within a project. If the codebase calls it a "CVR," the evidence map calls it a "CVR."
- Relationship types must be used with consistent meaning. `drives` means something specific; don't use it where `informs` is more appropriate.
- Status transitions must follow the lifecycle model consistently.

### 13.2 Scalability

- The EEM should be usable with 10 records or 10,000 records.
- Tags and domains should be curated to prevent explosion. A project should have 10-30 tags, not 200.
- Records should be atomically focused. A 10,000-record map where each record captures one concept is more navigable than a 500-record map where records are multi-concept.
- Relationship density matters more than record count. A sparse graph of 100 well-connected records is more valuable than a dense list of 1,000 unconnected records.

### 13.3 Traceability

- Every `Final` record must link to at least one session summary.
- Every relationship must point to an existing record.
- Supersession chains must be complete (no broken `superseded_by` or `supersedes` links).

### 13.4 Auditability

- A reader unfamiliar with the project should be able to understand the engineering reasoning by reading:
  1. The EEM record itself.
  2. The referenced session-summary sections.
  3. The linked upstream and downstream records.
- No domain expertise should be required to follow the audit trail. Technical terms may be used but should be explained in context.

### 13.5 Maintainability

- Records should be self-contained enough to survive file reorganization. If a session summary moves, update only the `session_file` paths.
- Avoid embedding information that changes with the codebase (line numbers, function signatures) unless preserved in `evidence_references` with a specific location.
- Relationships should use IDs, not titles or descriptions, for resilience against title changes.

### 13.6 Reuse

- The same EEM specification supports any software project. The schema does not encode project-specific knowledge.
- Evidence types are a fixed catalog. Do not create new evidence types per project. If a project has evidence that doesn't fit, it may not be evidence (see [Section 7](#7-what-should-not-become-evidence)).
- Tags and domains are the customization points for project-specific organization.

### 13.7 Engineering Reasoning

- The `rationale` field is mandatory and must explain WHY, not just WHAT.
- A Decision without alternatives referenced is incomplete. A Trade-off without sacrificed qualities is self-congratulation, not evidence.
- The quality of the EEM is measured by the quality of its reasoning chains, not by record count.

---

## 14. Templates

The following templates are minimal starting points. Every field marked `[REQUIRED]` must be populated before a record can reach `Final` status.

### 14.1 Requirement (REQ)

```yaml
id: [REQUIRED]
type: REQ
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
priority: MUST
source: ""
acceptance_criteria: ""
scope: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.2 Constraint (CON)

```yaml
id: [REQUIRED]
type: CON
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
constraint_type: ""
severity: ""
imposed_by: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.3 Decision (DEC)

```yaml
id: [REQUIRED]
type: DEC
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
decision_type: ""
chosen_approach: ""
alternatives_considered: []
driving_factors: []
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.4 Alternative Considered (ALT)

```yaml
id: [REQUIRED]
type: ALT
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
rejection_reason: ""
strengths: []
weaknesses: []
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.5 Trade-off (TRD)

```yaml
id: [REQUIRED]
type: TRD
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
gained: []
sacrificed: []
mitigation: ""
reversibility: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.6 Architecture (ARC)

```yaml
id: [REQUIRED]
type: ARC
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
component_name: ""
concern: ""
boundary_contract: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.7 Challenge (CHL)

```yaml
id: [REQUIRED]
type: CHL
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
severity: ""
resolution_status: ""
resolution_approach: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.8 Investigation (INV)

```yaml
id: [REQUIRED]
type: INV
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
investigation_type: ""
hypothesis: ""
methodology: ""
findings: ""
conclusion: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.9 Root Cause Analysis (RCA)

```yaml
id: [REQUIRED]
type: RCA
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
symptom: ""
root_cause: ""
contributing_factors: []
proximal_cause: ""
prevention: ""
detection: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.10 Validation (VAL)

```yaml
id: [REQUIRED]
type: VAL
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
validation_type: ""
validates: ""
outcome: ""
evidence_summary: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.11 Result (RES)

```yaml
id: [REQUIRED]
type: RES
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
result_type: ""
metric: ""
value: ""
baseline: ""
interpretation: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

### 14.12 Lesson Learned (LES)

```yaml
id: [REQUIRED]
type: LES
title: [REQUIRED]
summary: [REQUIRED]
description: [REQUIRED]
rationale: [REQUIRED]
status: Draft
confidence: LOW
tags: []
domain: ""
lesson_type: ""
applicability: ""
actionability: ""
generality: ""
supporting_sessions: []
evidence_references: []
relationships: []
supersedes: []
superseded_by: []
created_at: ""
created_by: ""
updated_at: ""
updated_by: ""
```

---

## Appendix A: Evidence Map File Organization (Non-Normative)

This appendix suggests how to organize EEM files within a project repository. It is not part of the specification and projects may choose any organization that preserves the record structure and relationships.

```
project/
├── evidence-map/
│   ├── requirements/
│   │   ├── REQ-001.yaml
│   │   └── REQ-002.yaml
│   ├── constraints/
│   │   └── CON-001.yaml
│   ├── decisions/
│   │   ├── DEC-001.yaml
│   │   ├── DEC-002.yaml
│   │   └── DEC-003.yaml
│   ├── alternatives/
│   │   └── ALT-001.yaml
│   ├── trade-offs/
│   │   └── TRD-001.yaml
│   ├── architecture/
│   │   └── ARC-001.yaml
│   ├── challenges/
│   │   └── CHL-001.yaml
│   ├── investigations/
│   │   └── INV-001.yaml
│   ├── root-cause/
│   │   └── RCA-001.yaml
│   ├── validations/
│   │   └── VAL-001.yaml
│   ├── results/
│   │   └── RES-001.yaml
│   └── lessons/
│       └── LES-001.yaml
└── agent-conv/
    ├── session-01.md
    ├── session-02.md
    └── ...
```

A single-file representation is equally valid for smaller projects. The specification is format-agnostic—YAML, JSON, and TOML are all acceptable serializations.

---

*End of Engineering Evidence Map Specification v1.0*
