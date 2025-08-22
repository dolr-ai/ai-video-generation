#!/usr/bin/env python3
import requests
import time
import json
import psutil
import subprocess
import threading
import argparse
import random
from datetime import datetime
from pathlib import Path
from PIL import Image
import re

API_BASE_URL = "http://localhost:8000/api/v1"
RESOLUTION_TEST_DIR = Path(
    "/workspace/ai-video-generation/MuseTalk/stress-test-data/resolution-test"
)
AUDIO_SAMPLES_DIR = Path(
    "/workspace/ai-video-generation/MuseTalk/stress-test-data/audio-samples"
)
OUTPUT_DIR = Path("/workspace/ai-video-generation/MuseTalk/stress_test/outputs")

# Cache for uploaded files to avoid re-uploading
UPLOAD_CACHE = {}


class PerformanceMonitor:
    def __init__(self):
        self.monitoring = False
        self.peak_cpu_percent = 0
        self.peak_memory_mb = 0
        self.peak_gpu_memory_mb = 0
        self.peak_gpu_utilization = 0
        self.monitor_thread = None

    def start_monitoring(self):
        self.monitoring = True
        self.peak_cpu_percent = 0
        self.peak_memory_mb = 0
        self.peak_gpu_memory_mb = 0
        self.peak_gpu_utilization = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        return {
            "peak_cpu_percent": self.peak_cpu_percent,
            "peak_memory_mb": self.peak_memory_mb,
            "peak_gpu_memory_mb": self.peak_gpu_memory_mb,
            "peak_gpu_utilization_percent": self.peak_gpu_utilization,
        }

    def _monitor_loop(self):
        while self.monitoring:
            # CPU and Memory monitoring
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 * 1024)

            self.peak_cpu_percent = max(self.peak_cpu_percent, cpu_percent)
            self.peak_memory_mb = max(self.peak_memory_mb, memory_mb)

            # GPU monitoring using nvidia-smi
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=memory.used,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output:
                        parts = output.split(", ")
                        if len(parts) == 2:
                            gpu_memory_mb = float(parts[0])
                            gpu_utilization = float(parts[1])
                            self.peak_gpu_memory_mb = max(
                                self.peak_gpu_memory_mb, gpu_memory_mb
                            )
                            self.peak_gpu_utilization = max(
                                self.peak_gpu_utilization, gpu_utilization
                            )
            except (subprocess.TimeoutExpired, Exception):
                pass

            time.sleep(0.5)


def get_image_resolution(image_path):
    """Extract resolution from image file"""
    with Image.open(image_path) as img:
        return f"{img.width}x{img.height}"


def get_audio_duration(audio_file):
    """Extract duration from audio filename (e.g., audio_sample-10s.mp3 -> 10)"""
    match = re.search(r"-(\d+)s\.mp3$", audio_file)
    if match:
        return int(match.group(1))
    return None


def upload_file(file_path, api_base_url, use_cache=True):
    """Upload a file to the API and return the remote path"""
    # Check cache first
    file_key = str(file_path)
    if use_cache and file_key in UPLOAD_CACHE:
        print(f"    ✓ Using cached upload for {file_path.name}")
        return UPLOAD_CACHE[file_key]
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            response = requests.post(f"{api_base_url}/upload", files=files, timeout=30)
            
        if response.status_code == 200:
            result = response.json()
            remote_path = result.get('file_path')
            if use_cache and remote_path:
                UPLOAD_CACHE[file_key] = remote_path
            return remote_path
        else:
            print(f"    ⚠ Failed to upload {file_path.name}: {response.text}")
            return None
    except Exception as e:
        print(f"    ⚠ Error uploading {file_path.name}: {str(e)}")
        return None


def process_single_request(
    image_path, audio_path, monitor, save_videos=True, video_output_dir=None, cache_uploads=True
):
    """Process a single generation request and return metrics"""
    print(f"\n  Processing: {image_path.name} with {audio_path.name}")

    # Get image resolution
    resolution = get_image_resolution(image_path)
    audio_duration = get_audio_duration(audio_path.name)

    # Upload files to the API first
    print(f"    📤 Uploading image...")
    uploaded_image_path = upload_file(image_path, API_BASE_URL, use_cache=cache_uploads)
    if not uploaded_image_path:
        return {
            "image_file": image_path.name,
            "audio_file": audio_path.name,
            "resolution": resolution,
            "audio_duration_seconds": audio_duration,
            "status": "failed",
            "error": "Failed to upload image"
        }
    
    print(f"    📤 Uploading audio...")
    uploaded_audio_path = upload_file(audio_path, API_BASE_URL, use_cache=cache_uploads)
    if not uploaded_audio_path:
        return {
            "image_file": image_path.name,
            "audio_file": audio_path.name,
            "resolution": resolution,
            "audio_duration_seconds": audio_duration,
            "status": "failed",
            "error": "Failed to upload audio"
        }

    # Start monitoring
    monitor.start_monitoring()
    start_time = time.time()

    try:
        # Submit request with uploaded file paths
        response = requests.post(
            f"{API_BASE_URL}/generate",
            json={
                "image": uploaded_image_path,
                "audio": uploaded_audio_path,
                "user_id": "stress_test_user",
            },
            timeout=30,
        )

        if response.status_code != 200:
            print(f"    Error submitting request: {response.text}")
            return None

        task_id = response.json()["task_id"]
        print(f"    Task ID: {task_id}")

        # Poll for completion
        max_wait_time = 600  # 10 minutes max
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait_time:
            status_resp = requests.get(f"{API_BASE_URL}/status/{task_id}")
            status_data = status_resp.json()
            status = status_data["status"]

            if status == "completed":
                end_time = time.time()
                generation_time = end_time - start_time

                # Stop monitoring and get peak values
                metrics = monitor.stop_monitoring()

                print(f"    ✓ Completed in {generation_time:.2f}s")

                # Save video if requested
                video_filename = None
                if save_videos and video_output_dir:
                    # Create descriptive filename
                    image_base = image_path.stem
                    audio_duration_str = f"{audio_duration}s"
                    video_filename = (
                        f"{image_base}_{resolution}_{audio_duration_str}_{task_id}.mp4"
                    )
                    video_path = video_output_dir / video_filename

                    # Download video
                    video_resp = requests.get(f"{API_BASE_URL}/video/{task_id}")
                    if video_resp.status_code == 200:
                        with open(video_path, "wb") as f:
                            f.write(video_resp.content)
                        print(f"    → Saved video: {video_filename}")
                    else:
                        print(
                            f"    ⚠ Failed to download video: {video_resp.status_code}"
                        )
                        video_filename = None

                return {
                    "image_file": image_path.name,
                    "audio_file": audio_path.name,
                    "resolution": resolution,
                    "image_width": int(resolution.split("x")[0]),
                    "image_height": int(resolution.split("x")[1]),
                    "audio_duration_seconds": audio_duration,
                    "generation_time_seconds": round(generation_time, 2),
                    "task_id": task_id,
                    "status": "completed",
                    "video_saved": video_filename if save_videos else "not_saved",
                    **metrics,
                }

            elif status == "failed":
                monitor.stop_monitoring()
                error_msg = status_data.get("error_message", "Unknown error")
                print(f"    ✗ Failed: {error_msg}")
                return {
                    "image_file": image_path.name,
                    "audio_file": audio_path.name,
                    "resolution": resolution,
                    "audio_duration_seconds": audio_duration,
                    "status": "failed",
                    "error": error_msg,
                }

            time.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout
        monitor.stop_monitoring()
        print(f"    ✗ Timeout after {max_wait_time}s")
        return {
            "image_file": image_path.name,
            "audio_file": audio_path.name,
            "resolution": resolution,
            "audio_duration_seconds": audio_duration,
            "status": "timeout",
        }

    except Exception as e:
        monitor.stop_monitoring()
        print(f"    ✗ Exception: {str(e)}")
        return {
            "image_file": image_path.name,
            "audio_file": audio_path.name,
            "resolution": resolution,
            "audio_duration_seconds": audio_duration,
            "status": "error",
            "error": str(e),
        }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="MuseTalk API Stress Test - Resolution & Audio Duration"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Number of random combinations to test (default: test all combinations)",
    )
    parser.add_argument(
        "--save-videos",
        action="store_true",
        default=True,
        help="Save generated videos (default: True)",
    )
    parser.add_argument(
        "--no-save-videos",
        dest="save_videos",
        action="store_false",
        help="Do not save generated videos",
    )
    parser.add_argument(
        "--video-dir",
        type=str,
        default=None,
        help="Custom directory for saving videos (default: outputs/videos_TIMESTAMP)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000/api/v1",
        help="API base URL (default: http://localhost:8000/api/v1)",
    )
    parser.add_argument(
        "--cache-uploads",
        action="store_true",
        default=True,
        help="Cache uploaded files to avoid re-uploading (default: True)",
    )
    parser.add_argument(
        "--no-cache-uploads",
        dest="cache_uploads",
        action="store_false",
        help="Re-upload files for each test",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Update API URL if provided
    global API_BASE_URL
    API_BASE_URL = args.api_url

    print("=" * 60)
    print("MuseTalk API Stress Test - Resolution & Audio Duration")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Create video output directory if saving videos
    video_output_dir = None
    if args.save_videos:
        if args.video_dir:
            video_output_dir = Path(args.video_dir)
        else:
            video_output_dir = (
                OUTPUT_DIR / f"videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
        video_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Videos will be saved to: {video_output_dir}")

    # Check API health
    print("\nChecking API health...")
    try:
        health_resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if health_resp.status_code != 200:
            print("API is not healthy. Please ensure the server is running.")
            return
        print("✓ API is healthy")
    except Exception as e:
        print(f"Cannot connect to API: {e}")
        return

    # Get all test files
    image_files = sorted(list(RESOLUTION_TEST_DIR.glob("*.jpg")))
    audio_files = sorted(list(AUDIO_SAMPLES_DIR.glob("*.mp3")))

    print(f"\nFound {len(image_files)} images with varying resolutions")
    print(f"Found {len(audio_files)} audio samples with varying durations")

    # Create all combinations
    all_combinations = [(img, audio) for audio in audio_files for img in image_files]
    total_combinations = len(all_combinations)

    # Sample if requested
    if args.sample and args.sample < total_combinations:
        test_combinations = random.sample(all_combinations, args.sample)
        print(
            f"Sampling {args.sample} random combinations from {total_combinations} total"
        )
    else:
        test_combinations = all_combinations
        print(f"Testing all {total_combinations} combinations")

    # Results storage
    results = {
        "test_metadata": {
            "timestamp": datetime.now().isoformat(),
            "api_base_url": API_BASE_URL,
            "total_images": len(image_files),
            "total_audios": len(audio_files),
            "total_possible_combinations": total_combinations,
            "combinations_tested": len(test_combinations),
            "sampled": args.sample if args.sample else False,
            "videos_saved": args.save_videos,
            "video_directory": str(video_output_dir) if video_output_dir else None,
        },
        "results": [],
    }

    monitor = PerformanceMonitor()
    test_counter = 0

    # Process each combination
    for image_path, audio_path in test_combinations:
        test_counter += 1
        print(f"\n{'=' * 40}")
        print(f"Test {test_counter}/{len(test_combinations)}")
        print(f"Image: {image_path.name}")
        print(f"Audio: {audio_path.name}")
        print(f"{'=' * 40}")

        result = process_single_request(
            image_path,
            audio_path,
            monitor,
            save_videos=args.save_videos,
            video_output_dir=video_output_dir,
            cache_uploads=args.cache_uploads,
        )
        if result:
            results["results"].append(result)

            # Save intermediate results after each test
            output_file = (
                OUTPUT_DIR
                / f"stress_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)

        # Small delay between requests to avoid overwhelming the server
        time.sleep(2)

    # Final summary
    print("\n" + "=" * 60)
    print("STRESS TEST COMPLETED")
    print("=" * 60)

    completed = [r for r in results["results"] if r.get("status") == "completed"]
    failed = [r for r in results["results"] if r.get("status") == "failed"]
    timeout = [r for r in results["results"] if r.get("status") == "timeout"]

    print(f"Total tests: {len(results['results'])}")
    print(f"Completed: {len(completed)}")
    print(f"Failed: {len(failed)}")
    print(f"Timeouts: {len(timeout)}")

    if completed:
        avg_time = sum(r["generation_time_seconds"] for r in completed) / len(completed)
        print(f"\nAverage generation time: {avg_time:.2f}s")

        # Find fastest and slowest
        fastest = min(completed, key=lambda x: x["generation_time_seconds"])
        slowest = max(completed, key=lambda x: x["generation_time_seconds"])

        print(
            f"Fastest: {fastest['resolution']} with {fastest['audio_duration_seconds']}s audio - {fastest['generation_time_seconds']}s"
        )
        print(
            f"Slowest: {slowest['resolution']} with {slowest['audio_duration_seconds']}s audio - {slowest['generation_time_seconds']}s"
        )

        # Peak resource usage
        if any("peak_gpu_memory_mb" in r for r in completed):
            max_gpu_mem = max(r.get("peak_gpu_memory_mb", 0) for r in completed)
            max_gpu_util = max(
                r.get("peak_gpu_utilization_percent", 0) for r in completed
            )
            print(f"\nPeak GPU Memory: {max_gpu_mem:.0f} MB")
            print(f"Peak GPU Utilization: {max_gpu_util:.0f}%")

    # Save final results
    final_output = (
        OUTPUT_DIR
        / f"stress_test_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(final_output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {final_output}")

    # Also save a CSV for easier analysis
    if completed:
        csv_output = (
            OUTPUT_DIR
            / f"stress_test_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        import csv

        with open(csv_output, "w", newline="") as f:
            fieldnames = [
                "image_file",
                "resolution",
                "image_width",
                "image_height",
                "audio_duration_seconds",
                "generation_time_seconds",
                "peak_cpu_percent",
                "peak_memory_mb",
                "peak_gpu_memory_mb",
                "peak_gpu_utilization_percent",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for r in completed:
                writer.writerow({k: r.get(k, "") for k in fieldnames})

        print(f"CSV results saved to: {csv_output}")


if __name__ == "__main__":
    main()
