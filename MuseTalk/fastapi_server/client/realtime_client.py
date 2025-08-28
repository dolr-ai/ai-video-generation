#!/usr/bin/env python3
"""
Realtime generation client for MuseTalk FastAPI server

This client demonstrates the two-phase realtime generation:
1. Prepare video once (slow, ~1-2 minutes)
2. Generate with any audio instantly (fast, <30 seconds)
"""

import os
import sys
import requests
import json
import time
import argparse
from typing import Optional

# API endpoint
API_BASE_URL = "http://localhost:8000"

def prepare_realtime_video(video_path: str, user_id: str = "realtime_user", 
                          bbox_shift: int = 0, prep_name: Optional[str] = None) -> Optional[str]:
    """
    Prepare video for realtime generation
    
    Args:
        video_path: Path to video file or URL
        user_id: User identifier
        bbox_shift: Bounding box shift parameter
        prep_name: Optional human-readable name
        
    Returns:
        Preparation ID if successful, None otherwise
    """
    print("=" * 70)
    print("🚀 REALTIME VIDEO PREPARATION")
    print("=" * 70)
    
    if not os.path.exists(video_path) and not video_path.startswith('http'):
        print(f"❌ Video file not found: {video_path}")
        return None
    
    print(f"📹 Video: {video_path}")
    print(f"👤 User: {user_id}")
    print(f"📦 Name: {prep_name or 'Unnamed'}")
    
    prep_request = {
        "video_path": video_path,
        "user_id": user_id,
        "bbox_shift": bbox_shift,
        "prep_name": prep_name
    }
    
    print("\n🔄 Starting preparation (this may take 1-2 minutes)...")
    print("   • Extracting frames")
    print("   • Detecting faces") 
    print("   • Pre-computing materials")
    print("   • Caching for instant reuse")
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/prepare_realtime",
            json=prep_request,
            timeout=300  # 5 minutes max
        )
        
        if response.status_code != 200:
            print(f"❌ Preparation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
        
        result = response.json()
        prep_time = time.time() - start_time
        
        if result["status"] == "success":
            prep_id = result["prep_id"]
            print(f"\n✅ Preparation completed in {prep_time:.1f} seconds!")
            print(f"   Prep ID: {prep_id}")
            print(f"   Frames: {result.get('valid_frames', '?')}/{result.get('num_frames', '?')} with faces")
            print(f"   Smoothing: {'Yes' if result.get('smoothing_enabled') else 'No'}")
            print(f"\n💡 Save this prep_id for ultra-fast generation: {prep_id}")
            return prep_id
        else:
            print(f"❌ Preparation failed: {result.get('message')}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Preparation timeout (>5 minutes)")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is it running?")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None


def generate_realtime_video(prep_id: str, audio_path: str, 
                           user_id: str = "realtime_user", fps: int = 25) -> bool:
    """
    Generate video using realtime preparation - should be very fast!
    
    Args:
        prep_id: Preparation ID from prepare_realtime_video
        audio_path: Path to audio file or URL
        user_id: User identifier
        fps: Output FPS
        
    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("⚡ REALTIME VIDEO GENERATION")
    print("=" * 70)
    
    if not os.path.exists(audio_path) and not audio_path.startswith('http'):
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    print(f"🎯 Prep ID: {prep_id}")
    print(f"🔊 Audio: {audio_path}")
    print(f"👤 User: {user_id}")
    print(f"🎬 FPS: {fps}")
    
    gen_request = {
        "prep_id": prep_id,
        "audio": audio_path,
        "user_id": user_id,
        "fps": fps
    }
    
    try:
        print("\n⚡ Starting realtime generation...")
        
        start_time = time.time()
        
        # Send generation request
        response = requests.post(
            f"{API_BASE_URL}/generate_realtime",
            json=gen_request,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        result = response.json()
        task_id = result.get("task_id")
        
        print(f"✅ Request accepted!")
        print(f"   Task ID: {task_id}")
        print(f"   Status: {result.get('status')}")
        
        # Poll for status (should be very fast)
        print("\n⏳ Processing (should be very fast)...")
        
        last_status = None
        while True:
            time.sleep(2)  # Check every 2 seconds
            
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
                print(f"   [{elapsed_time:.1f}s] Status: {current_status}")
                last_status = current_status
            
            # Check if completed
            if current_status == "completed":
                total_time = time.time() - start_time
                print(f"\n🚀 Realtime generation completed!")
                print(f"   Total time: {total_time:.1f} seconds")
                
                if status_data.get("output_path"):
                    print(f"   Output: {status_data['output_path']}")
                if status_data.get("gcs_path"):
                    print(f"   Cloud: {status_data['gcs_path']}")
                
                # Try to download
                print("\n📥 Downloading generated video...")
                download_response = requests.get(f"{API_BASE_URL}/video/{task_id}")
                
                if download_response.status_code == 200:
                    output_filename = f"realtime_output_{task_id}.mp4"
                    with open(output_filename, "wb") as f:
                        f.write(download_response.content)
                    print(f"✅ Video saved to: {output_filename}")
                else:
                    print(f"⚠️ Could not download video: {download_response.status_code}")
                
                print(f"\n🎉 Realtime generation successful! ({total_time:.1f}s total)")
                return True
            
            elif current_status == "failed":
                print(f"\n❌ Generation failed!")
                print(f"   Error: {status_data.get('error_message', 'Unknown error')}")
                return False
            
            # Timeout after 2 minutes (realtime should be much faster)
            if time.time() - start_time > 120:
                print(f"\n⏱️ Timeout: Realtime generation took too long (>2 minutes)")
                return False
        
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Request timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


def list_preparations():
    """List all available realtime preparations"""
    print("=" * 70)
    print("📋 AVAILABLE REALTIME PREPARATIONS")
    print("=" * 70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/realtime/preparations")
        
        if response.status_code != 200:
            print(f"❌ Failed to get preparations: {response.status_code}")
            return
        
        data = response.json()
        
        if data.get("status") == "disabled":
            print("❌ Realtime mode is disabled on the server")
            return
        
        preparations = data.get("preparations", [])
        stats = data.get("statistics", {})
        
        print(f"📊 Statistics:")
        print(f"   • Total preparations: {stats.get('num_preparations', 0)}")
        print(f"   • Total uses: {stats.get('total_uses', 0)}")
        print(f"   • Storage used: {stats.get('total_size_gb', 0)} GB")
        
        if not preparations:
            print(f"\n📭 No preparations found.")
            print(f"   Use --prepare to create one!")
            return
        
        print(f"\n📦 Preparations:")
        for prep in preparations:
            print(f"   🎯 {prep['prep_id']}")
            print(f"      📹 Video: {os.path.basename(prep.get('video_path', 'Unknown'))}")
            print(f"      🎬 Frames: {prep.get('valid_frames', '?')}/{prep.get('num_frames', '?')}")
            print(f"      📅 Created: {prep.get('created_at', 'Unknown')}")
            print(f"      🔄 Uses: {prep.get('uses', 0)}")
            print(f"      💾 Size: {prep.get('size_mb', 0)} MB")
            print()
        
        print(f"💡 Use any prep_id above for instant generation!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def delete_preparation(prep_id: str):
    """Delete a realtime preparation"""
    print(f"🗑️ Deleting preparation: {prep_id}")
    
    try:
        response = requests.delete(f"{API_BASE_URL}/realtime/preparations/{prep_id}")
        
        if response.status_code == 200:
            print(f"✅ Preparation {prep_id} deleted successfully")
        elif response.status_code == 404:
            print(f"❌ Preparation {prep_id} not found")
        else:
            print(f"❌ Failed to delete: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def demo_workflow(video_path: str, audio_path: str):
    """Demonstrate the complete realtime workflow"""
    print("=" * 70)
    print("🎬 REALTIME GENERATION DEMO")
    print("=" * 70)
    print("This demo shows the complete realtime workflow:")
    print("1. Prepare video once (slow)")
    print("2. Generate with audio instantly (fast)")
    print("3. Reuse preparation for more audio files")
    print()
    
    # Step 1: Prepare video
    prep_id = prepare_realtime_video(video_path, "demo_user", prep_name="Demo Video")
    if not prep_id:
        print("❌ Demo failed at preparation step")
        return
    
    # Step 2: Generate with audio
    success = generate_realtime_video(prep_id, audio_path, "demo_user")
    if not success:
        print("❌ Demo failed at generation step")
        return
    
    print("\n" + "=" * 70)
    print("🎉 DEMO COMPLETE!")
    print("=" * 70)
    print(f"✅ Video prepared: {prep_id}")
    print(f"✅ First generation completed")
    print(f"\n💡 Next steps:")
    print(f"   • Reuse prep_id '{prep_id}' with different audio")
    print(f"   • Each subsequent generation will be ultra-fast!")
    print(f"   • python realtime_client.py --generate {prep_id} another_audio.mp3")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MuseTalk Realtime Generation Client",
        epilog="Examples:\n"
               "  python realtime_client.py --prepare video.mp4\n"
               "  python realtime_client.py --generate prep_id audio.mp3\n"
               "  python realtime_client.py --demo video.mp4 audio.mp3\n"
               "  python realtime_client.py --list",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--prepare", metavar="VIDEO", help="Prepare video for realtime generation")
    parser.add_argument("--generate", metavar="PREP_ID", help="Generate using preparation ID")
    parser.add_argument("--audio", metavar="AUDIO", help="Audio file for generation")
    parser.add_argument("--demo", metavar="VIDEO", help="Run complete demo with video and audio")
    parser.add_argument("--demo-audio", metavar="AUDIO", help="Audio file for demo")
    parser.add_argument("--list", action="store_true", help="List available preparations")
    parser.add_argument("--delete", metavar="PREP_ID", help="Delete a preparation")
    parser.add_argument("--user-id", default="realtime_user", help="User ID")
    parser.add_argument("--fps", type=int, default=25, help="Output FPS")
    parser.add_argument("--bbox-shift", type=int, default=0, help="Bounding box shift")
    parser.add_argument("--name", help="Human-readable name for preparation")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.prepare, args.generate, args.demo, args.list, args.delete]):
        print("❌ Please specify an action: --prepare, --generate, --demo, --list, or --delete")
        parser.print_help()
        sys.exit(1)
    
    # Execute actions
    if args.list:
        list_preparations()
    
    elif args.delete:
        delete_preparation(args.delete)
    
    elif args.prepare:
        prep_id = prepare_realtime_video(
            args.prepare, 
            args.user_id, 
            args.bbox_shift,
            args.name
        )
        if prep_id:
            print(f"\n🎯 Use this prep_id for generation: {prep_id}")
    
    elif args.generate:
        if not args.audio:
            print("❌ --generate requires --audio parameter")
            sys.exit(1)
        generate_realtime_video(args.generate, args.audio, args.user_id, args.fps)
    
    elif args.demo:
        if not args.demo_audio:
            print("❌ --demo requires --demo-audio parameter")
            sys.exit(1)
        demo_workflow(args.demo, args.demo_audio)