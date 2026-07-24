# Session 04 – Evaluating the Charades Dataset

## Goal

The goal of this session was to determine whether the **Charades_v1_480** dataset is suitable for the Video Captioning Agent, which targets videos approximately **30–120 seconds** long.

Rather than deciding based on intuition, the objective was to evaluate the dataset using measurable evidence.

---

## Dataset Analysis

A Python script was developed to analyze every video in the dataset. The script recursively scanned all video files, extracted durations using `ffprobe`, stored the metadata in a pandas DataFrame, generated descriptive statistics, identified the shortest and longest videos, plotted a duration histogram, and measured execution time. The script was intentionally read-only and never modified the dataset.

The analysis processed **9,848 videos**.

Key statistics:

* Mean duration: **29.74 s**
* Median duration: **30.65 s**
* Maximum duration: **194.40 s**

The dataset appeared to be strongly centered around videos of roughly 30 seconds, with a long right tail containing a smaller number of longer clips.

---

## Choosing the Right Metric

Initially, descriptive statistics such as quartiles were used to judge whether the dataset matched the application's requirements.

During the discussion, it became clear that this approach answered the wrong question.

Quartiles describe how the dataset is distributed, but they cannot determine how many videos satisfy a custom duration requirement.

To answer the engineering question—

> "Is this dataset suitable for my application?"

—the dataset was filtered using the application's constraints:

**30 seconds ≤ duration ≤ 120 seconds**

This produced the result that mattered most:

* Valid videos: **6,089**
* Retention: **61.83%**

This became the primary metric for evaluating dataset suitability.

---

## Understanding Quartiles vs. Filtering

One important realization was that descriptive statistics and filtering serve different purposes.

Quartiles explain how the data is distributed, including its spread, median, and central range.

Filtering answers an application-specific question by measuring how many samples satisfy defined constraints.

These analyses complement each other rather than replacing one another.

---

## Interpreting the Histogram Correctly

At first glance, the histogram appeared to suggest that almost every video was exactly 30 seconds long.

This interpretation was incorrect.

Because the histogram used 50 bins across a duration range of approximately 2–194 seconds, each bin represented a range of roughly 3.8 seconds.

The large peak therefore represented videos concentrated around approximately **29–33 seconds**, rather than videos with an identical duration.

To verify this interpretation, the most common rounded durations were examined, confirming a strong concentration around **30–32 seconds** instead of a single fixed value.

---

## Environment Issue

The analysis script successfully processed every video but failed while importing Matplotlib.

The issue was traced to a version mismatch between system-installed Matplotlib (compiled against NumPy 1.x) and a locally installed NumPy 2.x package.

The problem was resolved by creating a dedicated Python virtual environment and installing compatible versions of NumPy, Pandas, and Matplotlib.

This isolated the scientific Python environment and eliminated the compatibility issue.

---

## Key Takeaways

* Dataset suitability should be evaluated using application-specific constraints rather than descriptive statistics alone.
* Quartiles, histograms, and filtering each answer different questions and should be interpreted together.
* Histogram peaks represent ranges of values, not exact values.
* The Charades dataset is strongly centered around videos of approximately 30 seconds, with most accepted videos falling between roughly 30 and 32 seconds.
* Approximately **61.8%** of the dataset satisfies the target duration requirement of **30–120 seconds**, making it a viable candidate for further evaluation.

---

## Open Questions

* How does Charades compare with the other candidate datasets using the same duration-based evaluation process?
* Should duration retention be combined with additional quality metrics such as annotation quality, scene diversity, and action coverage before making the final dataset selection?
