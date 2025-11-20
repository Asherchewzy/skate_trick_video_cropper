import requests
import time
import sys
import os

BASE_URL = "http://localhost:8000"
VIDEO_FILE = "test_vid_withskater.mp4"

def test_flow():
    if not os.path.exists(VIDEO_FILE):
        print(f"Error: {VIDEO_FILE} not found.")
        sys.exit(1)

    print(f"Uploading {VIDEO_FILE}...")
    with open(VIDEO_FILE, "rb") as f:
        files = {"file": f}
        response = requests.post(f"{BASE_URL}/api/upload", files=files)
    
    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        sys.exit(1)
        
    job_id = response.json()["job_id"]
    print(f"Job ID: {job_id}")
    
    print("Polling status...")
    while True:
        response = requests.get(f"{BASE_URL}/api/status/{job_id}")
        status = response.json()
        print(f"Status: {status['status']} - {status.get('message', '')}")
        
        if status["status"] == "completed":
            break
        elif status["status"] == "failed":
            print("Processing failed!")
            sys.exit(1)
            
        time.sleep(2)
        
    print("Downloading result...")
    download_url = status["download_url"]
    response = requests.get(f"{BASE_URL}{download_url}")
    
    if response.status_code == 200:
        with open("result_highlight_real.mp4", "wb") as f:
            f.write(response.content)
        print("Download successful: result_highlight_real.mp4")
    else:
        print(f"Download failed: {response.status_code}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_flow()
    except requests.exceptions.ConnectionError:
        print("Could not connect to server. Make sure it is running on port 8000.")
