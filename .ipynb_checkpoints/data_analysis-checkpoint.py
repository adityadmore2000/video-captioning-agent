from pathlib import Path
import subprocess

import pandas as pd
ROOT_DIR = Path("/home/aditya/dev-work/video-captioning-agent/Data/Charades_v1_480/Charades_v1_480")
VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mov", ".mkv", ".webm",
    ".mpeg", ".mpg", ".m4v", ".wmv", ".flv", ".3gp"
}
def get_duration(video_path: Path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None

records = []

print("Scanning...")

from tqdm import tqdm

for video in tqdm(ROOT_DIR.rglob("*"), desc="Scanning videos"):
    if not video.is_file():
        continue

    if video.suffix.lower() not in VIDEO_EXTENSIONS:
        continue

    duration = get_duration(video)
    if duration is None:
        continue

    records.append({
        "class": video.parent.name,
        "filename": video.name,
        "duration_sec": duration,
        "path": str(video),
    })

df = pd.DataFrame(records)

print("\n===== Overall Statistics =====")
print(df["duration_sec"].describe())

print("\nShortest videos:")
print(df.nsmallest(10, "duration_sec")[["duration_sec", "path"]])

print("\nLongest videos:")
print(df.nlargest(10, "duration_sec")[["duration_sec", "path"]])

import matplotlib.pyplot as plt

df["duration_sec"].hist(bins=50)

plt.xlabel("Duration (seconds)")
plt.ylabel("Number of videos")
plt.title("Video Duration Distribution")
plt.show()

valid = df[
    (df["duration_sec"] >= 30) &
    (df["duration_sec"] <= 120)
]

print(len(valid))
print(f"{100 * len(valid) / len(df):.2f}%")

print(
    df["duration_sec"]
      .round(1)
      .value_counts()
      .head(20)
)

# Write paths of videos with duration in [30, 120] seconds to a text file
output_txt = Path("valid_videos_30_120s.txt")

valid = df[(df["duration_sec"] >= 30) & (df["duration_sec"] <= 120)].copy()
print(f"Found {len(valid)} videos in range [30, 120] seconds "
      f"({100 * len(valid) / len(df):.2f}% of {len(df)}).")

# Option 1: plain Python (newline-separated, sorted by filename for reproducibility)
valid_sorted = valid.sort_values("path")
with output_txt.open("w", encoding="utf-8") as f:
    for p in valid_sorted["path"]:
        f.write(p + "\n")

print(f"Wrote {len(valid_sorted)} paths to: {output_txt.resolve()}")

# Quick sanity check: read back and count lines
with output_txt.open("r", encoding="utf-8") as f:
    line_count = sum(1 for _ in f if _.strip())
print(f"Verified line count in file: {line_count}")