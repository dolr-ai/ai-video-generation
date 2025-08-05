#!/usr/bin/env python3
"""
Test script for MuseTalk Flask API
"""

import requests
import json
import os
import sys

# API base URL
BASE_URL = "http://localhost:5000/api/v1"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print("✓ Health check passed:", response.json())
    else:
        print("✗ Health check failed:", response.status_code)
    return response.status_code == 200

def test_generate_local_files():
    """Test generation with local files"""
    print("\nTesting generation with local files...")
    
    # Use sample files from MuseTalk (now service is inside MuseTalk)
    musetalk_dir = os.path.dirname(os.path.dirname(__file__))  # Go up one level from service
    image_path = os.path.join(musetalk_dir, 'data', 'video', 'yongen.mp4')
    audio_path = os.path.join(musetalk_dir, 'data', 'audio', 'yongen.wav')
    
    if not os.path.exists(image_path) or not os.path.exists(audio_path):
        print("✗ Sample files not found. Please ensure MuseTalk sample data exists.")
        return False
    
    data = {
        "image": image_path,
        "audio": audio_path,
        "local_dev": True,
        "bbox_shift": 0,
        "fps": 25
    }
    
    response = requests.post(f"{BASE_URL}/generate", json=data)
    if response.status_code == 200:
        result = response.json()
        print("✓ Generation successful:")
        print(f"  Task ID: {result.get('task_id')}")
        print(f"  Output: {result.get('output_path')}")
    else:
        print("✗ Generation failed:", response.status_code)
        print("  Response:", response.text)
    return response.status_code == 200

def test_generate_with_urls():
    """Test generation with URLs"""
    print("\nTesting generation with URLs...")
    
    # Example URLs (replace with actual URLs)
    data = {
        "image": "https://raw.githubusercontent.com/TMElyralab/MuseTalk/main/assets/demo/yongen/yongen.jpeg",
        "audio": "https://github.com/TMElyralab/MuseTalk/raw/main/data/audio/yongen.wav",
        "local_dev": True,
        "realtime": False
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=data, timeout=300)
        if response.status_code == 200:
            result = response.json()
            print("✓ URL generation successful:")
            print(f"  Task ID: {result.get('task_id')}")
            print(f"  Output: {result.get('output_path')}")
        else:
            print("✗ URL generation failed:", response.status_code)
            print("  Response:", response.text)
        return response.status_code == 200
    except requests.exceptions.Timeout:
        print("✗ Request timed out (this might be normal for first run when loading models)")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_file_upload():
    """Test file upload endpoint"""
    print("\nTesting file upload...")
    
    # Create a test file
    test_file_path = "/tmp/test_upload.txt"
    with open(test_file_path, 'w') as f:
        f.write("Test file content")
    
    try:
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.txt', f)}
            response = requests.post(f"{BASE_URL}/upload", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Upload successful:")
            print(f"  Upload ID: {result.get('upload_id')}")
            print(f"  File path: {result.get('file_path')}")
        else:
            print("✗ Upload failed:", response.status_code)
        
        # Clean up
        os.remove(test_file_path)
        return response.status_code == 200
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("MuseTalk Flask API Test Suite")
    print("=" * 50)
    
    # Check if API is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=2)
    except:
        print("✗ API is not running. Please start the Flask app first:")
        print("  cd service && python app.py")
        sys.exit(1)
    
    # Run tests
    tests = [
        test_health,
        test_file_upload,
        test_generate_local_files,
        # test_generate_with_urls,  # Uncomment to test URL functionality
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test error: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Tests completed: {passed} passed, {failed} failed")
    print("=" * 50)

if __name__ == "__main__":
    main()