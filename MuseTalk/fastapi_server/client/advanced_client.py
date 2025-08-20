#!/usr/bin/env python3
"""
Advanced client to demonstrate queue management with concurrent requests.
This client shows how multiple requests are queued and processed sequentially.
"""
import requests
import time
import threading
import json
from datetime import datetime
from typing import List, Dict
import argparse

# ========== CONFIGURATION ==========
API_BASE_URL = "http://localhost:8000/api/v1"

# Test files - these should exist on the server
TEST_FILES = {
    "audio1": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/8e22464e-b67b-46b7-9042-29c73d22add6/test_audio1-female.mp3",
    "audio2": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/d46f640a-bdde-434d-8135-b79f45c85c81/test_audio1-female.mp3",
    "image1": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/8e22464e-b67b-46b7-9042-29c73d22add6/test_image1-female.png",
    "image2": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/d46f640a-bdde-434d-8135-b79f45c85c81/test_image2-female.jpg",
    "image3": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp/4ef79625-6430-4fc0-b140-568a15a85e57/test_image3-female.jpeg"
}

# Request configurations
TEST_REQUESTS = [
    {"name": "Request-1", "image": "image1", "audio": "audio1", "user_id": "user_001"},
    {"name": "Request-2", "image": "image2", "audio": "audio1", "user_id": "user_002"}, 
    {"name": "Request-3", "image": "image3", "audio": "audio2", "user_id": "user_003"},
    {"name": "Request-4", "image": "image1", "audio": "audio2", "user_id": "user_004"},
]

class RequestTracker:
    def __init__(self):
        self.results: List[Dict] = []
        self.lock = threading.Lock()
        
    def log_event(self, request_name: str, event: str, details: Dict = None):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self.lock:
            log_entry = {
                "timestamp": timestamp,
                "request": request_name,
                "event": event,
                "details": details or {}
            }
            self.results.append(log_entry)
            print(f"[{timestamp}] {request_name}: {event} {json.dumps(details or {}, indent=None)}")

def submit_request(config: Dict, tracker: RequestTracker) -> str:
    """Submit a single request and return task_id"""
    request_name = config["name"]
    
    try:
        # Prepare request payload
        payload = {
            "image": TEST_FILES[config["image"]],
            "audio": TEST_FILES[config["audio"]],
            "user_id": config["user_id"],
            "fps": 25,
            "batch_size": 4  # Smaller batch for faster testing
        }
        
        tracker.log_event(request_name, "SUBMITTING", {"user_id": config["user_id"]})
        
        # Submit request
        response = requests.post(f"{API_BASE_URL}/generate", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            task_id = result["task_id"]
            tracker.log_event(request_name, "ACCEPTED", {
                "task_id": task_id,
                "status": result["status"],
                "message": result["message"]
            })
            return task_id
        else:
            tracker.log_event(request_name, "FAILED", {
                "status_code": response.status_code,
                "error": response.text
            })
            return None
            
    except Exception as e:
        tracker.log_event(request_name, "ERROR", {"error": str(e)})
        return None

def monitor_task(task_id: str, request_name: str, tracker: RequestTracker):
    """Monitor a task until completion"""
    if not task_id:
        return
        
    last_status = None
    last_queue_position = None
    
    while True:
        try:
            response = requests.get(f"{API_BASE_URL}/status/{task_id}")
            if response.status_code == 200:
                status_data = response.json()
                current_status = status_data["status"]
                queue_position = status_data.get("queue_position")
                
                # Log status changes
                if current_status != last_status or queue_position != last_queue_position:
                    details = {"status": current_status}
                    if queue_position:
                        details["queue_position"] = queue_position
                    tracker.log_event(request_name, "STATUS_UPDATE", details)
                    last_status = current_status
                    last_queue_position = queue_position
                
                # Check if completed or failed
                if current_status in ["completed", "failed"]:
                    final_details = {
                        "status": current_status,
                        "task_id": task_id
                    }
                    if current_status == "completed":
                        final_details["output_path"] = status_data.get("output_path")
                    else:
                        final_details["error"] = status_data.get("error_message")
                    
                    tracker.log_event(request_name, "FINISHED", final_details)
                    break
                    
            else:
                tracker.log_event(request_name, "STATUS_ERROR", {
                    "status_code": response.status_code,
                    "error": response.text
                })
                break
                
        except Exception as e:
            tracker.log_event(request_name, "MONITOR_ERROR", {"error": str(e)})
            break
            
        time.sleep(2)  # Check every 2 seconds

def run_concurrent_demo(num_requests: int = None):
    """Run the concurrent request demonstration"""
    tracker = RequestTracker()
    
    # Use specified number of requests or all configured requests
    requests_to_run = TEST_REQUESTS[:num_requests] if num_requests else TEST_REQUESTS
    
    print("=" * 80)
    print(f"🚀 QUEUE DEMONSTRATION: Submitting {len(requests_to_run)} concurrent requests")
    print(f"⏰ Start time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Check server health first
    try:
        health_response = requests.get(f"{API_BASE_URL}/health")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ Handler server: {health_data['status']}")
            if health_data.get('model_server'):
                print(f"✅ Model server: {health_data['model_server']['status']}")
            print(f"📊 Queue size: {health_data.get('queue_size', 'unknown')}")
            print(f"📋 Total tasks: {health_data.get('tasks_count', 'unknown')}")
        else:
            print("❌ Server health check failed")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return
    
    print("\n" + "=" * 80)
    print("📤 PHASE 1: Submitting all requests simultaneously")
    print("=" * 80)
    
    # Submit all requests simultaneously
    threads = []
    task_ids = {}
    
    for config in requests_to_run:
        def submit_and_monitor(cfg=config):
            task_id = submit_request(cfg, tracker)
            if task_id:
                task_ids[cfg["name"]] = task_id
                monitor_task(task_id, cfg["name"], tracker)
        
        thread = threading.Thread(target=submit_and_monitor)
        thread.daemon = True
        threads.append(thread)
        thread.start()
        
        # Small delay between submissions to see queue building up
        time.sleep(0.5)
    
    print(f"\n📋 Submitted {len(requests_to_run)} requests, monitoring progress...")
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    print("\n" + "=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    
    # Print summary
    completed = 0
    failed = 0
    
    for result in tracker.results:
        if result["event"] == "FINISHED":
            if result["details"]["status"] == "completed":
                completed += 1
            else:
                failed += 1
    
    print(f"✅ Completed: {completed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Total processing time: {datetime.now().strftime('%H:%M:%S')}")
    
    # Show queue behavior analysis
    print(f"\n📈 QUEUE BEHAVIOR ANALYSIS:")
    queue_events = [r for r in tracker.results if "queue_position" in r.get("details", {})]
    if queue_events:
        print(f"   • Maximum queue position observed: {max(r['details']['queue_position'] for r in queue_events)}")
        print(f"   • Queue events logged: {len(queue_events)}")
        print("   • This demonstrates sequential processing with proper queuing")
    else:
        print("   • No explicit queue positions observed (requests may have processed immediately)")
    
    print(f"\n💡 KEY OBSERVATIONS:")
    print(f"   • All requests submitted nearly simultaneously")
    print(f"   • Only 1 request processes at a time (MAX_CONCURRENT_MODEL_REQUESTS=1)")
    print(f"   • Remaining requests wait in queue with position tracking")
    print(f"   • No GPU memory conflicts due to proper queue management")

def main():
    parser = argparse.ArgumentParser(description="Advanced MuseTalk Queue Demonstration Client")
    parser.add_argument("-n", "--num-requests", type=int, 
                       help="Number of requests to submit (default: all configured)")
    parser.add_argument("-u", "--url", default="http://localhost:8000/api/v1",
                       help="API base URL")
    
    args = parser.parse_args()
    
    global API_BASE_URL
    API_BASE_URL = args.url
    
    run_concurrent_demo(args.num_requests)

if __name__ == "__main__":
    main()