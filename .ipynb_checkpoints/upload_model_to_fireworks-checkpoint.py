import os
import time
import requests

# --- Configuration ---
API_KEY = os.environ["FIREWORKS_API_KEY"]
ACCOUNT_ID = "adityadmore2000-x698"
MODEL_ID = "InternVL3-78B"
MODEL_PATH = "/home/aditya/dev-work/InternVL3-78B/"  # folder of Hugging Face files: config.json, *.safetensors, tokenizer, ...

BASE_URL = "https://api.fireworks.ai/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

files = [f for f in os.listdir(MODEL_PATH) if os.path.isfile(os.path.join(MODEL_PATH, f))]
file_sizes = {f: os.path.getsize(os.path.join(MODEL_PATH, f)) for f in files}

# --- Step 1: Create the model ---
requests.post(
    f"{BASE_URL}/accounts/{ACCOUNT_ID}/models",
    headers=HEADERS,
    json={
        "modelId": MODEL_ID,
        "model": {
            "kind": "HF_BASE_MODEL",
            "huggingFaceUrl": "https://huggingface.co/<ORG>/<MODEL>",
            "baseModelDetails": {
                "checkpointFormat": "HUGGINGFACE",
                "worldSize": 1,
                "huggingfaceFiles": files,
            },
        },
    },
).raise_for_status()
print(f"Created model {MODEL_ID}")

# --- Step 2: Get a signed upload URL for each file ---
resp = requests.post(
    f"{BASE_URL}/accounts/{ACCOUNT_ID}/models/{MODEL_ID}:getUploadEndpoint",
    headers=HEADERS,
    json={"filenameToSize": file_sizes, "enableResumableUpload": False},
)
resp.raise_for_status()
upload_urls = resp.json()["filenameToSignedUrls"]

# --- Step 3: Upload each file to its signed URL ---
for filename, url in upload_urls.items():
    size = file_sizes[filename]
    with open(os.path.join(MODEL_PATH, filename), "rb") as f:
        requests.put(
            url,
            data=f,
            headers={
                "Content-Type": "application/octet-stream",
                "x-goog-content-length-range": f"{size},{size}",
            },
        ).raise_for_status()
    print(f"Uploaded {filename}")

# --- Step 4: Validate — poll until the model is READY ---
validate_url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/models/{MODEL_ID}:validateUpload"
while True:
    resp = requests.get(validate_url, headers=HEADERS)
    if resp.status_code == 200:
        print("Model validated and ready to deploy!")
        break
    if "FAILED_PRECONDITION" in resp.text:  # files still landing
        print("Files still finalizing, retrying in 30s...")
        time.sleep(30)
        continue
    resp.raise_for_status()  # any other error is fatal