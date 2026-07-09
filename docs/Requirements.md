
# Video Captioning Agent  

**What you are building**

An AI agent that watches a video clip and generates a caption in a requested style. Build your

pipeline to handle a wide variety of video content: different scenes, settings, subjects, and visual

**Styles:**
Styles your agent must support

| Style             | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| formal            | Professional, objective, factual tone                             |
| sarcastic         | Dry, ironic, lightly mocking                                      |
| humorous_tech     | Funny, with technology or programming<br><br>  <br><br>references |
| humorous_non_tech | Funny, everyday humour with no technical<br><br>  <br><br>jargon  |


**What to submit**

A Docker image pushed to a public registry.

Your container must:

1. Read tasks from /input/tasks.json on startup


```
[

{

"task_id": "v1",

"video_url": "https://storage.example.com/clips/clip1.mp4",

"styles": ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]

}

]
```


2. Write results to /output/results.json before exiting

  
```
[

{

"task_id": "v1",

"captions": {

"formal": "...",

"sarcastic": "...",

"humorous_tech": "...",

"humorous_non_tech": "..."

}

}

]

```
  

No inference log is required for Track 2.

Check out the Image Architecture requirement at the bottom of this document

**Environment variables**

No API key or model restriction is injected. You may call any model, API, or framework: 

use your own credentials inside the container.

**Example clips**

Use these to develop and test your agent. Evaluation uses a hidden set your agent has never

seen, ensure your pipeline generalises beyond these examples.


| Clip | URL                                                                                                         | Content                                                                        |
| ---- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| v1   | https://storage.google<br><br>apis.com/amd-hackathon<br><br>-clips/1860079-uhd_256<br><br>0_1440_25fps.mp4  | Urban autumn boulevard with<br><br>golden trees and city traffic               |
| v2   | https://storage.google<br><br>apis.com/amd-hackathon<br><br>-clips/13825391-uhd_38<br><br>40_2160_30fps.mp4 | Orange kitten among green<br><br>foliage in a garden                           |
| v3   | https://storage.google<br><br>apis.com/amd-hackathon<br><br>-clips/3044693-uhd_384<br><br>0_2160_24fps.mp4  | Office worker at a desktop<br><br>computer in a modern<br><br>open-plan office |

**Rules**

- Exit code 0 on success, non-zero on failure

- Maximum runtime: 10 minutes
	
- No model restriction: any model, framework, or API is permitted

- Video clips in the hidden evaluation set are 30 seconds to 2 minutes in length

- Output must include a caption for every requested style for every clip, missing styles

**score zero for that clip**

- /output/results.json must be valid JSON, malformed output scores zero

- Image compressed size must not exceed 10GB — larger images are rejected before pulling

- Submissions are rate-limited to 10 per hour per team

**Scoring**

Each caption is scored on two dimensions by an LLM-Judge:

1. Caption accuracy (0–1): how faithfully the caption reflects the video content

2. Style match (0–1): how well the caption matches the requested tone

  

Final score = weighted average across all clips and all four styles. Evaluation uses a hidden set of ~12 clips spanning varied content (nature, urban, animals, people, sports, food, weather technology). Agents that only work on the three example clips above will score poorly.

  
**