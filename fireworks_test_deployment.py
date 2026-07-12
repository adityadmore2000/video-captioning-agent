"""
Test harness for the InternVL3-8B Fireworks deployment.

Usage:
    # Stage 1: sanity check the deployment with the single image example
    python test_deployment.py --mode image-sanity

    # Stage 2: test video understanding via frame sampling
    python test_deployment.py --mode video --video-path /path/to/clip.mp4 --num-frames 8
"""

import argparse
import base64
import json
import os
import sys
from dotenv import load_dotenv
import cv2
import requests
load_dotenv()  # load FIREWORKS_API_KEY from .env if present
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL_ID = "accounts/adityadmore2000-x698/deployments/dzcxfs49"

API_KEY = os.environ.get("FIREWORKS_API_KEY")
if not API_KEY:
    sys.exit(
        "ERROR: set your key first -> export FIREWORKS_API_KEY='fw_xxx'\n"
        "(don't hardcode it in this file)"
    )

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


def call_model(content_blocks, max_tokens=1024, temperature=0):
    payload = {
        "model": MODEL_ID,
        "max_tokens": max_tokens,
        "temperature": temperature,   # determinism matters for your acceptance criteria
        "top_k": 40,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "messages": [{"role": "user", "content": content_blocks}],
    }
    resp = requests.post(FIREWORKS_URL, headers=HEADERS, data=json.dumps(payload), timeout=120)
    if resp.status_code != 200:
        print(f"[HTTP {resp.status_code}] {resp.text[:2000]}")
        resp.raise_for_status()
    return resp.json()


def stage1_image_sanity():
    """Confirms auth + deployment work at all, before touching video logic."""
    content = [
        {"type": "text", "text": "Can you describe this image?"},
        {
            "type": "image_url",
            "image_url": {
                "url": (
                    "https://images.unsplash.com/photo-1582538885592-e70a5d7ab3d3"
                    "?ixlib=rb-4.0.3&auto=format&fit=crop&w=1770&q=80"
                )
            },
        },
    ]
    result = call_model(content, max_tokens=256)
    print("=== Stage 1: image sanity check ===")
    print(json.dumps(result, indent=2)[:3000])
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("\nModel output:\n", text)


def extract_frames_base64(video_path, num_frames):
    """Uniformly sample num_frames frames across the whole clip, return as base64 JPEGs."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    duration = total_frames / fps if fps else 0
    print(f"Video: {total_frames} frames, {fps:.1f} fps, ~{duration:.1f}s")

    if total_frames <= 0:
        raise RuntimeError("Video reports zero frames - possibly corrupted/empty")

    # evenly spaced frame indices, avoiding the very first/last edge frames
    indices = [
        int((i + 0.5) * total_frames / num_frames) for i in range(num_frames)
    ]

    frames_b64 = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            print(f"  warning: couldn't read frame {idx}, skipping")
            continue
        # downscale to keep payload/token cost sane - tune this
        h, w = frame.shape[:2]
        max_dim = 768
        scale = max_dim / max(h, w)
        if scale < 1:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            continue
        frames_b64.append(base64.b64encode(buf).decode("utf-8"))

    cap.release()
    print(f"Extracted {len(frames_b64)} frames")
    return frames_b64


def stage2_video_test(video_path, num_frames):
    frames_b64 = extract_frames_base64(video_path, num_frames)
    if not frames_b64:
        raise RuntimeError("No frames extracted - check the video file")

    # This prompt mirrors the CVR extraction task from your spec -
    # good early test of whether the model can hold the whole timeline, not just one frame.
    prompt_text = (
        "You are shown a sequence of frames sampled uniformly across a short video, "
        "in chronological order. Based ONLY on what is visible, describe:\n"
        "1. Scene/environment\n"
        "2. Primary subjects\n"
        "3. Important objects\n"
        "4. Key actions in chronological order\n"
        "5. A one-sentence overall factual summary\n"
        "Do not speculate about anything not visible in the frames."
    )

    content = [{"type": "text", "text": prompt_text}]
    for b64 in frames_b64:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )

    print("\n=== Stage 2: video (frame-sampled) test ===")
    result = call_model(content, max_tokens=1024)

    usage = result.get("usage", {})
    print(f"Token usage: {usage}")  # watch this against your 16k context budget

    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("\nModel output:\n", text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["image-sanity", "video"], required=True)
    parser.add_argument("--video-path", help="Path to local video file (required for --mode video)")
    parser.add_argument("--num-frames", type=int, default=8, help="How many frames to sample")
    args = parser.parse_args()

    if args.mode == "image-sanity":
        stage1_image_sanity()
    else:
        if not args.video_path:
            sys.exit("--video-path is required for --mode video")
        stage2_video_test(args.video_path, args.num_frames)


if __name__ == "__main__":
    main()