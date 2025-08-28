#!/usr/bin/env python3
"""
Test client for video-to-video generation
"""

import os
import sys
import requests
import json
import time
import argparse
from pathlib import Path

# API endpoint
API_BASE_URL = "http://localhost:8000"

def test_video_to_video(video_path: str, audio_path: str, user_id: str = "test_user"):
    """
    Test video-to-video generation
    
    Args:
        video_path: Path to input video file
        audio_path: Path to audio file
        user_id: User identifier
    """
    
    print("=" * 60)
    print("VIDEO-TO-VIDEO GENERATION TEST")
    print("=" * 60)
    
    # Check if files exist
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return
    
    if not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return
    
    print(f"📹 Input video: {video_path}")
    print(f"🔊 Input audio: {audio_path}")
    print(f"👤 User ID: {user_id}")
    
    # Prepare request
    generation_request = {
        "image": video_path,  # Using 'image' field for backward compatibility
        "audio": audio_path,
        "user_id": user_id,
        "input_type": "video",  # Explicitly set to video
        "batch_size": 4,  # Use smaller batch for video
        "video_start_time": 0,  # Process from beginning
        "video_end_time": 10  # Process first 10 seconds (for testing)
    }
    
    print("\n📤 Sending generation request...")
    print(f"   Processing first 10 seconds of video")
    print(f"   Using batch size: 4 (optimized for video)")
    
    try:
        # Send generation request
        response = requests.post(
            f"{API_BASE_URL}/generate",
            json=generation_request,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        result = response.json()
        task_id = result.get("task_id")
        
        print(f"✅ Request accepted!")
        print(f"   Task ID: {task_id}")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        
        # Poll for status
        print("\n⏳ Waiting for processing to complete...")
        print("   (This may take several minutes for video processing)")
        
        start_time = time.time()
        last_status = None
        
        while True:
            time.sleep(5)  # Check every 5 seconds
            
            # Get status
            status_response = requests.get(f"{API_BASE_URL}/status/{task_id}")
            if status_response.status_code != 200:
                print(f"❌ Failed to get status: {status_response.status_code}")
                break
            
            status_data = status_response.json()
            current_status = status_data.get("status")
            
            # Print status update if changed
            if current_status != last_status:
                elapsed_time = time.time() - start_time
                print(f"   [{elapsed_time:.1f}s] Status: {current_status}", end="")
                
                if status_data.get("queue_position"):
                    print(f" (Queue position: {status_data['queue_position']})", end="")
                print()
                
                last_status = current_status
            
            # Check if completed
            if current_status == "completed":
                print(f"\n✅ Video generation completed!")
                print(f"   Total time: {time.time() - start_time:.1f} seconds")
                
                if status_data.get("output_path"):
                    print(f"   Output path: {status_data['output_path']}")
                
                if status_data.get("gcs_path"):
                    print(f"   GCS path: {status_data['gcs_path']}")
                
                # Try to download the video
                print("\n📥 Attempting to download generated video...")
                download_response = requests.get(f"{API_BASE_URL}/video/{task_id}")
                
                if download_response.status_code == 200:
                    output_filename = f"output_video_{task_id}.mp4"
                    with open(output_filename, "wb") as f:
                        f.write(download_response.content)
                    print(f"✅ Video saved to: {output_filename}")
                else:
                    print(f"⚠️ Could not download video: {download_response.status_code}")
                    if download_response.status_code == 410:
                        print("   Video has been moved to cloud storage")
                
                break
            
            elif current_status == "failed":
                print(f"\n❌ Video generation failed!")
                print(f"   Error: {status_data.get('error_message', 'Unknown error')}")
                break
            
            # Timeout after 10 minutes
            if time.time() - start_time > 600:
                print(f"\n⏱️ Timeout: Processing took too long (>10 minutes)")
                break
        
    except requests.exceptions.Timeout:
        print("❌ Request timeout")
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is it running?")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

def test_with_sample_data():
    """Test with sample video and audio files"""
    
    # Look for sample files
    sample_video_paths = [
        "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/sample_video.mp4",
        "/workspace/ai-video-generation/MuseTalk/examples/video/sample.mp4",
        "./sample_video.mp4"
    ]
    
    sample_audio_paths = [
        "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/sample_audio.mp3",
        "/workspace/ai-video-generation/MuseTalk/examples/audio/sample.mp3",
        "./sample_audio.mp3"
    ]
    
    video_path = None
    audio_path = None
    
    for path in sample_video_paths:
        if os.path.exists(path):
            video_path = path
            break
    
    for path in sample_audio_paths:
        if os.path.exists(path):
            audio_path = path
            break
    
    if not video_path or not audio_path:
        print("❌ Sample files not found")
        print("\nTo test video-to-video generation, you need:")
        print("1. A video file (mp4, avi, mov, etc.)")
        print("2. An audio file (mp3, wav, etc.)")
        print("\nUsage: python test_video_to_video.py <video_path> <audio_path>")
        return
    
    test_video_to_video(video_path, audio_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test video-to-video generation")
    parser.add_argument("video", nargs="?", help="Path to input video file")
    parser.add_argument("audio", nargs="?", help="Path to audio file")
    parser.add_argument("--user-id", default="test_user", help="User ID")
    parser.add_argument("--start-time", type=float, default=0, help="Start time in seconds")
    parser.add_argument("--end-time", type=float, default=10, help="End time in seconds")
    
    args = parser.parse_args()
    
    if args.video and args.audio:
        # Use provided files
        test_video_to_video(args.video, args.audio, args.user_id)
    else:
        # Try to use sample files
        print("No files provided, looking for sample data...")
        test_with_sample_data()