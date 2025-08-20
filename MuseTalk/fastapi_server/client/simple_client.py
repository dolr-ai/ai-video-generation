#!/usr/bin/env python3
import requests
import time
import os


# ========== CHANGE THESE ==========
AUDIO_PATH = "https://storage.googleapis.com/talking-head-upload-simulation/user_id_1/request_id_2/test_audio1-female.mp3"
IMAGE_PATH = "https://storage.googleapis.com/talking-head-upload-simulation/user_id_1/request_id_3/test_image3-female.jpeg"
USER_ID = "user123"
# ==================================

API_BASE_URL = "http://localhost:8000/api/v1"


def main():
    # Submit request
    print("Submitting request...")
    response = requests.post(
        f"{API_BASE_URL}/generate",
        json={
            "image": IMAGE_PATH,
            "audio": AUDIO_PATH,
            "user_id": USER_ID,
        },
    )

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    task_id = response.json()["task_id"]
    print(f"Task ID: {task_id}")

    # Wait for completion
    print("Waiting for completion...")
    while True:
        status_resp = requests.get(f"{API_BASE_URL}/status/{task_id}")
        status = status_resp.json()["status"]
        print(f"Status: {status}")

        if status == "completed":
            break
        elif status == "failed":
            print(f"Failed: {status_resp.json().get('error_message')}")
            return

        time.sleep(5)

    # Download video
    print("Downloading video...")
    video_resp = requests.get(f"{API_BASE_URL}/video/{task_id}")

    filename = f"video_{task_id}.mp4"
    with open(filename, "wb") as f:
        f.write(video_resp.content)

    print(f"Downloaded: {filename}")


if __name__ == "__main__":
    main()
