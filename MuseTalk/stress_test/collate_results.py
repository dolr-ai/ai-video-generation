#!/usr/bin/env python3
"""
Stress Test Results Collator
Collates all partial stress test result files into a single comprehensive report.
"""
import json
import os
import glob
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import statistics
import csv

def load_json_files(directory):
    """Load all JSON result files from directory"""
    json_files = glob.glob(os.path.join(directory, "stress_test_results_*.json"))
    json_files.sort()  # Sort by filename (timestamp)
    
    all_data = []
    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                all_data.append({
                    'file': os.path.basename(file_path),
                    'data': data
                })
                print(f"✅ Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"❌ Error loading {file_path}: {str(e)}")
    
    return all_data

def merge_results(all_data):
    """Merge all results into a single consolidated dataset"""
    print(f"\n📊 Merging {len(all_data)} result files...")
    
    # Use metadata from the most recent file
    latest_metadata = all_data[-1]['data']['test_metadata']
    
    # Collect all unique results (deduplicate by task_id)
    all_results = {}
    total_results = 0
    
    for file_data in all_data:
        results = file_data['data'].get('results', [])
        for result in results:
            task_id = result.get('task_id')
            if task_id and task_id not in all_results:
                all_results[task_id] = result
                total_results += 1
    
    print(f"📈 Found {total_results} unique test results")
    
    # Create consolidated metadata
    consolidated_metadata = {
        "collation_timestamp": datetime.now().isoformat(),
        "source_files_count": len(all_data),
        "source_files": [f['file'] for f in all_data],
        "original_test_start": all_data[0]['data']['test_metadata']['timestamp'],
        "original_test_end": all_data[-1]['data']['test_metadata']['timestamp'],
        "api_base_url": latest_metadata['api_base_url'],
        "total_unique_results": total_results,
        "videos_saved": latest_metadata.get('videos_saved', False),
        "video_directory": latest_metadata.get('video_directory')
    }
    
    return consolidated_metadata, list(all_results.values())

def analyze_results(results):
    """Generate analytics from the results"""
    print(f"\n📊 Analyzing {len(results)} results...")
    
    if not results:
        return {}
    
    # Filter completed results
    completed = [r for r in results if r.get('status') == 'completed']
    failed = [r for r in results if r.get('status') == 'failed']
    timeout = [r for r in results if r.get('status') == 'timeout']
    
    analytics = {
        "summary": {
            "total_tests": len(results),
            "completed": len(completed),
            "failed": len(failed),
            "timeouts": len(timeout),
            "success_rate": round(len(completed) / len(results) * 100, 1) if results else 0
        }
    }
    
    if not completed:
        return analytics
    
    # Performance metrics
    generation_times = [r['generation_time_seconds'] for r in completed]
    gpu_memory = [r.get('peak_gpu_memory_mb', 0) for r in completed]
    gpu_utilization = [r.get('peak_gpu_utilization_percent', 0) for r in completed]
    cpu_usage = [r.get('peak_cpu_percent', 0) for r in completed]
    
    analytics.update({
        "performance": {
            "generation_time": {
                "mean": round(statistics.mean(generation_times), 2),
                "median": round(statistics.median(generation_times), 2),
                "min": round(min(generation_times), 2),
                "max": round(max(generation_times), 2),
                "std_dev": round(statistics.stdev(generation_times) if len(generation_times) > 1 else 0, 2)
            },
            "gpu_memory_mb": {
                "mean": round(statistics.mean(gpu_memory), 2),
                "median": round(statistics.median(gpu_memory), 2),
                "min": round(min(gpu_memory), 2),
                "max": round(max(gpu_memory), 2)
            },
            "gpu_utilization_percent": {
                "mean": round(statistics.mean(gpu_utilization), 2),
                "median": round(statistics.median(gpu_utilization), 2),
                "min": round(min(gpu_utilization), 2),
                "max": round(max(gpu_utilization), 2)
            },
            "cpu_percent": {
                "mean": round(statistics.mean(cpu_usage), 2),
                "median": round(statistics.median(cpu_usage), 2),
                "min": round(min(cpu_usage), 2),
                "max": round(max(cpu_usage), 2)
            }
        }
    })
    
    # Resolution analysis
    resolution_stats = defaultdict(list)
    for result in completed:
        resolution = result.get('resolution', 'unknown')
        resolution_stats[resolution].append(result['generation_time_seconds'])
    
    resolution_analysis = {}
    for resolution, times in resolution_stats.items():
        if times:
            resolution_analysis[resolution] = {
                "count": len(times),
                "mean_time": round(statistics.mean(times), 2),
                "median_time": round(statistics.median(times), 2),
                "min_time": round(min(times), 2),
                "max_time": round(max(times), 2)
            }
    
    analytics["resolution_analysis"] = resolution_analysis
    
    # Audio duration analysis
    audio_stats = defaultdict(list)
    for result in completed:
        duration = result.get('audio_duration_seconds', 0)
        audio_stats[duration].append(result['generation_time_seconds'])
    
    audio_analysis = {}
    for duration, times in audio_stats.items():
        if times:
            audio_analysis[f"{duration}s"] = {
                "count": len(times),
                "mean_time": round(statistics.mean(times), 2),
                "median_time": round(statistics.median(times), 2),
                "min_time": round(min(times), 2),
                "max_time": round(max(times), 2)
            }
    
    analytics["audio_duration_analysis"] = audio_analysis
    
    # Find best and worst performers
    fastest = min(completed, key=lambda x: x['generation_time_seconds'])
    slowest = max(completed, key=lambda x: x['generation_time_seconds'])
    
    analytics["extremes"] = {
        "fastest": {
            "resolution": fastest.get('resolution'),
            "audio_duration": f"{fastest.get('audio_duration_seconds')}s",
            "time": fastest['generation_time_seconds'],
            "image_file": fastest.get('image_file'),
            "audio_file": fastest.get('audio_file')
        },
        "slowest": {
            "resolution": slowest.get('resolution'),
            "audio_duration": f"{slowest.get('audio_duration_seconds')}s", 
            "time": slowest['generation_time_seconds'],
            "image_file": slowest.get('image_file'),
            "audio_file": slowest.get('audio_file')
        }
    }
    
    return analytics

def save_csv_report(results, output_path):
    """Save results as CSV for analysis"""
    completed = [r for r in results if r.get('status') == 'completed']
    
    if not completed:
        print("⚠️ No completed results to save as CSV")
        return
    
    fieldnames = [
        "image_file", "audio_file", "resolution", "image_width", "image_height",
        "audio_duration_seconds", "generation_time_seconds", "status",
        "peak_cpu_percent", "peak_memory_mb", "peak_gpu_memory_mb", 
        "peak_gpu_utilization_percent", "task_id", "video_saved"
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in completed:
            writer.writerow({k: result.get(k, '') for k in fieldnames})
    
    print(f"📄 CSV saved: {output_path}")

def print_summary(analytics):
    """Print a summary of the analysis"""
    print("\n" + "="*60)
    print("📊 STRESS TEST ANALYSIS SUMMARY")
    print("="*60)
    
    summary = analytics.get('summary', {})
    print(f"Total tests: {summary.get('total_tests', 0)}")
    print(f"Completed: {summary.get('completed', 0)}")
    print(f"Failed: {summary.get('failed', 0)}")
    print(f"Timeouts: {summary.get('timeouts', 0)}")
    print(f"Success rate: {summary.get('success_rate', 0)}%")
    
    if 'performance' in analytics:
        perf = analytics['performance']
        gen_time = perf.get('generation_time', {})
        print(f"\n⏱️ Generation Time:")
        print(f"  Mean: {gen_time.get('mean', 0)}s")
        print(f"  Range: {gen_time.get('min', 0)}s - {gen_time.get('max', 0)}s")
        
        gpu_mem = perf.get('gpu_memory_mb', {})
        print(f"\n🎮 GPU Memory:")
        print(f"  Mean: {gpu_mem.get('mean', 0)} MB")
        print(f"  Range: {gpu_mem.get('min', 0)} - {gpu_mem.get('max', 0)} MB")
        
        if 'extremes' in analytics:
            extremes = analytics['extremes']
            fastest = extremes.get('fastest', {})
            slowest = extremes.get('slowest', {})
            print(f"\n🏎️ Fastest: {fastest.get('resolution')} + {fastest.get('audio_duration')} = {fastest.get('time')}s")
            print(f"🐌 Slowest: {slowest.get('resolution')} + {slowest.get('audio_duration')} = {slowest.get('time')}s")

def main():
    """Main function"""
    print("🔄 Starting stress test results collation...")
    
    # Define paths
    outputs_dir = "/workspace/ai-video-generation/MuseTalk/stress_test/outputs"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Check if outputs directory exists
    if not os.path.exists(outputs_dir):
        print(f"❌ Outputs directory not found: {outputs_dir}")
        return
    
    # Load all JSON files
    all_data = load_json_files(outputs_dir)
    
    if not all_data:
        print("❌ No valid JSON files found to collate")
        return
    
    # Merge results
    metadata, results = merge_results(all_data)
    
    # Analyze results
    analytics = analyze_results(results)
    
    # Create final consolidated report
    final_report = {
        "collation_metadata": metadata,
        "analytics": analytics,
        "raw_results": results
    }
    
    # Save consolidated JSON
    json_output = f"{outputs_dir}/collated_stress_test_{timestamp}.json"
    with open(json_output, 'w') as f:
        json.dump(final_report, f, indent=2)
    print(f"📄 Consolidated JSON saved: {json_output}")
    
    # Save CSV for analysis
    csv_output = f"{outputs_dir}/collated_stress_test_{timestamp}.csv"
    save_csv_report(results, csv_output)
    
    # Print summary
    print_summary(analytics)
    
    print(f"\n✅ Collation completed successfully!")
    print(f"📁 Output files saved in: {outputs_dir}")

if __name__ == "__main__":
    main()