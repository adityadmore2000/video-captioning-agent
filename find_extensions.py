from pathlib import Path

# Change this to your target directory
ROOT_DIR = r"/home/aditya/dev-work/video-captioning-agent/Moments_in_Time_Raw"

extensions = set()

for file in Path(ROOT_DIR).rglob("*"):
    if file.is_file():
        # Get extension (includes the leading '.')
        ext = file.suffix.lower()

        # Handle files with no extension
        if not ext:
            ext = "<no_extension>"

        extensions.add(ext)

# Convert to a sorted tuple
extensions = tuple(sorted(extensions))

print(f"Found {len(extensions)} unique extensions:\n")
print(extensions)