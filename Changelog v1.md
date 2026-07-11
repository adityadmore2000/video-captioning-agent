## Changelog 

## v1 

## Added 

- Introduced the **Canonical Video Report (CVR)** as an explicit intermediate artifact between video understanding and caption generation. 

- Defined the CVR as the **single source of truth** for all generated captions. 

- Added a dedicated **Canonical Video Report** section describing its purpose, expected contents, and guiding principles. 

- Added an example CVR structure illustrating scene, subjects, objects, timeline, and overall summary. 

- Added explicit guidance that the system should summarize the **entire video** , not only the most salient event. 

- Added the requirement that humor may change wording and tone but **must not introduce new facts** . 

- Added a design principle prioritizing **semantically important events over exhaustive scene description** . 

- Added an edge-case guideline encouraging conservative descriptions when the model is uncertain to reduce hallucinations. 

## Changed 

- Refined the problem decomposition from: 

   - **Video Understanding** 

   - **Caption Generation** 

to explicitly separate: 

   - **Video Understanding** 

   - **Style-specific Caption Generation** 

- Updated the conceptual pipeline to include the **Canonical Video Report** as an explicit processing stage. 

- Clarified that video understanding is performed **exactly once per video** and reused for generating all requested styles. 

- Updated the functional requirements to emphasize understanding the **entire video** rather than isolated frames or events. 

- Expanded caption generation requirements to explicitly require: 

   - factual consistency across styles, 

   - concise video-level summaries, 

   - style adaptation without factual modification. 

- Expanded the quality acceptance criteria to include: 

   - summarization of the complete video, 

   - consistency across all generated styles, 

   - readability in addition to factual accuracy. 

## Clarified 

- Distinguished **video understanding** from **language generation** as independent responsibilities. 

- **internal artifact** and is 

- Clarified that the CVR is an **not part of the final submission** . 

- Clarified that only **observable facts** should appear in the CVR. 

- Clarified that emotions, intentions, speculation, and unsupported inferences should not be included in the factual representation. 

- Clarified that visual understanding remains the primary information source, while audio understanding is optional and can be incorporated in future iterations without affecting the overall architecture. 

