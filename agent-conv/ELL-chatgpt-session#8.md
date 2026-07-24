# Engineering Learning Log (ELL)

## Session Title

**Designing an Evaluation Strategy for Video VLMs**

---

## Goal

Determine how to systematically evaluate and select a Video Vision-Language Model (Video VLM) for the Video Captioning Agent, while minimizing guesswork through structured experimentation and LLMOps.

---

## Starting Point

The session began with the assumption that model selection would primarily involve comparing a handful of large Video VLMs, such as InternVL3-78B and Qwen2.5-VL-72B, using benchmark leaderboards like MVBench. There was also uncertainty about whether an 8B model would be sufficient, whether larger models were necessary, and whether quantized variants should be preferred.

Another open question was how experienced AI engineers handle the simultaneous challenges of selecting models and designing effective system prompts without relying on intuition alone.

---

## Investigation

The discussion first shifted from comparing raw benchmark scores to identifying what the project actually requires from a Video VLM.

Rather than treating the model as a caption generator, the system architecture was re-examined through the concept of the Canonical Video Report (CVR). This made it clear that the model's primary responsibility is **structured video understanding**, while caption generation is a separate downstream task.

This naturally led to identifying the capabilities that actually matter for the project, such as temporal reasoning, multi-event understanding, factual consistency, and whole-video summarization, instead of simply maximizing benchmark performance.

The investigation then moved toward prompt engineering, model size, quantization, and ultimately evolved into a discussion about experimentation methodology and evaluation infrastructure.

Finally, attention shifted to building an evaluation dataset that resembles the hidden hackathon distribution, leading to an analysis of existing datasets such as Charades and the role of synthetic data.

---

# Key Discoveries

## The Project Evaluates Video Understanding, Not Caption Generation

A major realization was that the project should not optimize for "better captions."

Instead, the Video VLM is responsible for producing a **Canonical Video Report (CVR)**, which serves as the factual representation of the video.

This changes how models should be evaluated.

The quality of the CVR becomes significantly more important than the stylistic quality of the final caption because every downstream caption depends entirely on the information contained within the CVR.

---

## Prompt Engineering Is an Independent Optimization Problem

Initially, model size appeared to be the primary factor influencing performance.

However, the discussion revealed that a well-designed system prompt can substantially improve whole-video understanding without changing the underlying model.

The project's objective is not creative writing but structured information extraction.

Therefore, prompt engineering should focus on instructing the model to:

* watch the complete video,
* preserve chronological order,
* avoid speculation,
* produce structured factual output.

This reinforced the idea that prompt engineering deserves its own optimization cycle before drawing conclusions about model capability.

---

## Controlled Experimentation Is More Valuable Than Guessing

Perhaps the most important engineering insight from the session was recognizing that model selection and prompt engineering should not be optimized simultaneously.

Instead, experiments should isolate one variable at a time.

The proposed workflow became:

1. Select one baseline model.
2. Iterate on system prompts until a strong prompt is obtained.
3. Freeze the prompt.
4. Compare multiple models using the exact same prompt.
5. Only after selecting a model, investigate deployment optimizations such as quantization.

This transforms model selection from subjective opinion into measurable experimentation.

---

## LLMOps Is the Core of the Evaluation Strategy

Rather than searching for the "best model" through benchmarks alone, the project should rely on an experimentation framework.

Every experiment should record:

* model version,
* prompt version,
* generated CVR,
* generated captions,
* inference characteristics,
* manual evaluation.

The emphasis shifted from choosing models to building an environment where models can be compared fairly and repeatedly.

The experiment log itself becomes one of the project's most valuable engineering artifacts.

---

## Manual Evaluation Is Appropriate for This Project

Because the project optimizes for factual understanding rather than benchmark accuracy, manual inspection was recognized as both acceptable and desirable.

The CVR provides an intermediate artifact that makes debugging significantly easier.

If a caption is incorrect, it becomes possible to determine whether the problem originated during video understanding or during stylistic rewriting.

This reinforces the architectural benefit of separating understanding from generation.

---

## Quantization Is a Deployment Optimization, Not a Capability Improvement

The discussion clarified an important misconception.

Quantization does **not** increase model capability.

Instead, it makes larger models easier to deploy by reducing computational requirements.

A quantized InternVL3-78B remains fundamentally a 78B model.

However, because inference will be performed through Fireworks AI, quantization becomes a secondary concern unless Fireworks explicitly supports deploying different quantized checkpoints.

Consequently, deployment optimization should only occur after determining which model actually satisfies the project's quality requirements.

---

## Benchmark Selection Should Reflect the Hidden Evaluation

The session explored several possible data sources for evaluation.

The most important realization was that no single dataset sufficiently represents the hidden hackathon distribution.

Charades emerged as a valuable benchmark because its videos contain multiple sequential indoor activities, making it well suited for evaluating temporal reasoning and CVR generation.

However, it lacks environmental diversity.

This led to the conclusion that evaluation should combine:

* controlled datasets (e.g., Charades),
* real-world videos from diverse sources,
* targeted synthetic videos for unit testing specific reasoning capabilities.

---

## Synthetic Videos Have a Different Role Than Real Videos

Synthetic datasets were initially considered as a possible evaluation source.

The discussion concluded that synthetic videos are excellent for validating specific reasoning abilities because their expected outputs are known precisely.

However, they should not replace real-world videos.

Instead, synthetic videos are best viewed as unit tests for the video understanding stage, while real-world videos evaluate generalization and robustness.

---

## Engineering Implications

This session fundamentally changed the project's evaluation philosophy.

Rather than selecting the largest available Video VLM based on benchmark rankings, the project should rely on a structured experimentation framework driven by LLMOps.

The Canonical Video Report becomes the primary evaluation artifact, making prompt engineering and model comparison significantly more transparent.

Prompt engineering should precede large-scale model comparison, ensuring that observed improvements are attributable to model capability rather than better instructions.

Model selection should be performed through controlled experiments, with prompt versions, model versions, generated CVRs, and manual quality assessments logged for every run.

Evaluation should use a diverse benchmark combining datasets like Charades with real-world videos and synthetic unit tests, better approximating the hidden evaluation while still allowing targeted debugging.

Overall, the engineering focus shifted away from finding the "best model" toward building a reproducible evaluation system capable of identifying the most appropriate model empirically.

---

## Key Takeaways

* The project evaluates structured video understanding, not caption generation.
* The Canonical Video Report is the most important artifact for evaluating model quality.
* Prompt engineering should be optimized before comparing different models.
* Change only one experimental variable at a time to obtain meaningful conclusions.
* LLMOps and experiment tracking are central to the project's engineering workflow.
* Manual evaluation is appropriate because factual correctness is the primary objective.
* Quantization is a deployment optimization rather than a capability improvement.
* Charades is valuable for temporal reasoning but should be complemented with more diverse real-world videos.
* Synthetic videos are best treated as unit tests rather than primary evaluation data.

---

## Open Questions

* Which Video VLM produces the most accurate CVRs under the same optimized prompt?
* How much quality difference exists between 8B, 38B, and 78B models for whole-video summarization?
* Does prompt quality transfer equally well across different Video VLM families, or should prompts be adapted per model?
* Which prompt structure consistently maximizes factual completeness while minimizing hallucinations?
* How closely should the project's benchmark dataset resemble the unknown hackathon evaluation distribution?
