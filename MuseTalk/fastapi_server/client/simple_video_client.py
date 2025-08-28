#!/usr/bin/env python3
import requests
import time
import os


# ========== CHANGE THESE ==========
AUDIO_PATH = "https://storage.googleapis.com/talking-head-upload-simulation/user_id_1/request_id_2/test_audio1-female.mp3"
VIDEO_PATH = "https://storage.googleapis.com/talking-head-upload-simulation/test_videos/1061613004-preview.mp4"  # Change to your video URL or local path
USER_ID = "user123"
# ==================================

API_BASE_URL = "http://localhost:8000/api/v1"

def main():
    # Submit video-to-video request
    print("Submitting video-to-video request...")
    print(f"Video: {VIDEO_PATH}")
    print(f"Audio: {AUDIO_PATH}")
    print(f"User: {USER_ID}")

    response = requests.post(
        f"{API_BASE_URL}/generate",
        json={
            "image": VIDEO_PATH,  # Using 'image' field for backward compatibility
            "audio": AUDIO_PATH,
            "user_id": USER_ID,
            "input_type": "video",  # Explicitly specify video input
            "batch_size": 4,  # Smaller batch size for video processing
            "video_start_time": 0,  # Start from beginning
            "video_end_time": 10  # Process first 10 seconds
        },
    )

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    result = response.json()
    task_id = result["task_id"]
    print(f"Task ID: {task_id}")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    # Wait for completion
    print("\nWaiting for completion...")
    start_time = time.time()

    while True:
        status_resp = requests.get(f"{API_BASE_URL}/status/{task_id}")
        if status_resp.status_code != 200:
            print(f"Error checking status: {status_resp.text}")
            return

        status_data = status_resp.json()
        status = status_data["status"]
        elapsed = time.time() - start_time

        print(f"[{elapsed:.1f}s] Status: {status}", end="")

        if status_data.get("queue_position"):
            print(f" (Queue: {status_data['queue_position']})", end="")
        print()

        if status == "completed":
            print(f"\n✅ Video generation completed!")
            print(f"Total time: {elapsed:.1f} seconds")

            # Show additional info for video processing
            if status_data.get("frames_with_faces"):
                print(f"Frames with faces: {status_data.get('frames_with_faces')}")
            if status_data.get("total_frames"):
                print(f"Total frames: {status_data.get('total_frames')}")

            break
        elif status == "failed":
            print(f"\n❌ Generation failed!")
            print(f"Error: {status_data.get('error_message', 'Unknown error')}")
            return

        time.sleep(5)

    # Download video
    print("\n📥 Downloading generated video...")
    video_resp = requests.get(f"{API_BASE_URL}/video/{task_id}")

    if video_resp.status_code == 200:
        filename = f"video_to_video_{task_id}.mp4"
        with open(filename, "wb") as f:
            f.write(video_resp.content)
        print(f"✅ Downloaded: {filename}")
    elif video_resp.status_code == 410:
        print("⚠️ Video has been moved to cloud storage")
        # Try to get GCS path from status
        if status_data.get("gcs_path"):
            print(f"Cloud location: {status_data['gcs_path']}")
    else:
        print(f"❌ Download failed: {video_resp.status_code}")
        print(f"Response: {video_resp.text}")


if __name__ == "__main__":
    main()