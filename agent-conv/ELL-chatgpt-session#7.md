# Session 07 – Understanding How Modern Video VLMs Process Videos

## Goal

The goal of this session was to understand how modern Video Vision-Language Models (VLMs) actually process videos before designing the video captioning pipeline.

The objective was to validate architectural assumptions using official documentation rather than building the system based on intuition.

---

## Correcting the Initial Assumption

The session began with the assumption that models such as InternVL3 process videos as continuous video clips.

As the documentation was explored, this assumption proved to be incorrect.

Instead, InternVL3 treats a video as an **ordered sequence of images**. The video itself is not directly consumed by the model. Frame extraction happens beforehand, and the model reasons over the resulting sequence of frames.

This shifted the mental model from:

> Video → Video Encoder → Caption

to:

> Video → Frame Extraction → Vision Encoder → Language Model → Response

This became the foundation for future pipeline design.

---

## Understanding the Processing Pipeline

The discussion broke down the responsibilities inside InternVL3.

The model expects an ordered collection of frames as input. Each frame is resized, tiled into image patches, converted into visual embeddings by the vision encoder, and then passed to the language model, which jointly reasons over both the visual tokens and the text prompt.

One important realization was that the model itself is responsible for visual understanding and temporal reasoning—but **not** for decoding videos or selecting frames.

---

## Separating System Responsibilities from Model Responsibilities

A useful distinction emerged between what our system must do and what the model already provides.

Our pipeline is responsible for:

* downloading videos
* decoding MP4 files
* extracting frames
* deciding which frames to send to the model

InternVL3 is responsible for:

* image preprocessing
* visual encoding
* temporal reasoning across the ordered frames
* generating the final response

This clarified the boundary between application logic and model capabilities, preventing unnecessary assumptions about what the model does automatically.

---

## Frame Extraction vs. Frame Selection

One of the most important insights from this session was recognizing that frame extraction and frame selection are two separate problems.

Frame extraction is a deterministic preprocessing step that converts a video into individual frames.

Frame selection is an engineering decision that determines which of those frames should be provided to the model.

Several possible strategies were identified for future investigation, including uniform sampling, scene-change detection, motion-aware sampling, keyframe extraction, and hybrid approaches.

This established frame selection as one of the primary quality levers for the video captioning pipeline.

---

## Understanding Temporal Reasoning

Although InternVL3 does not process videos as continuous spatio-temporal tensors, it still understands temporal relationships.

Rather than relying on explicit motion representations, the model reasons over an ordered sequence of visual tokens. Motion is inferred by comparing changes across successive frames.

This clarified how image-based Video VLMs achieve temporal understanding without using traditional video architectures.

---

## Comparing Two Families of Video Models

The discussion distinguished between two fundamentally different categories of models.

The first category consists of image-based Video VLMs such as InternVL3 and Qwen2.5-VL. These models operate on ordered images and combine visual understanding with instruction-following language models.

The second category consists of native video models such as VideoMAE, ViViT, TimeSformer, and InternVideo2. These models directly process spatio-temporal video representations but are generally designed as feature extractors rather than conversational multimodal systems.

Understanding this distinction helped explain why InternVL3 remains an appropriate choice despite not being a traditional video transformer.

---

## Why InternVL3 Fits the Project

The session concluded that InternVL3 is well aligned with the project's requirements.

It combines visual understanding, temporal reasoning, and natural language generation within a single instruction-following model.

Using InternVL3 avoids the need to design a separate caption generation pipeline on top of a dedicated video encoder, simplifying the overall system architecture.

---

## Key Takeaways

* Modern Video VLMs such as InternVL3 process videos as ordered sequences of images rather than continuous video clips.
* Frame extraction is an external preprocessing responsibility rather than a built-in model capability.
* Frame selection is an important engineering decision that directly influences caption quality, latency, and context usage.
* Temporal understanding is achieved through reasoning over ordered visual tokens instead of explicit motion representations.
* Understanding the internal responsibilities of the model helps define clear boundaries between application logic and model capabilities.
* Image-based Video VLMs and native video transformers solve related problems using fundamentally different architectures.

---

## Open Questions

Several implementation questions remained unresolved and were identified for future investigation:

* What frame counts are appropriate for videos between 30 seconds and 2 minutes?
* Which frame extraction library should be used in production?
* Does Fireworks perform frame extraction automatically or expect preprocessed inputs?
* How do InternVL3, Qwen2.5-VL, and other modern Video VLMs differ internally?
* Which frame selection strategy offers the best balance between caption quality, latency, and context usage?
