#!/usr/bin/env python3
"""
Stress Test Results Analyzer
Analyzes CSV results and extracts performance insights
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

def load_and_analyze_csv(csv_path):
    """Load CSV and perform comprehensive analysis"""
    print(f"📊 Analyzing: {csv_path}")
    
    # Load data
    df = pd.read_csv(csv_path)
    print(f"✅ Loaded {len(df)} test results")
    
    # Basic statistics
    print("\n" + "="*60)
    print("📈 BASIC STATISTICS")
    print("="*60)
    
    print(f"Total tests: {len(df)}")
    print(f"Unique images: {df['image_file'].nunique()}")
    print(f"Unique resolutions: {df['resolution'].nunique()}")
    print(f"Audio durations: {sorted(df['audio_duration_seconds'].unique())}")
    
    # Performance metrics summary
    print(f"\n⏱️ Generation Time:")
    print(f"  Mean: {df['generation_time_seconds'].mean():.2f}s")
    print(f"  Median: {df['generation_time_seconds'].median():.2f}s")
    print(f"  Range: {df['generation_time_seconds'].min():.2f}s - {df['generation_time_seconds'].max():.2f}s")
    
    print(f"\n🎮 GPU Metrics:")
    print(f"  Memory (mean): {df['peak_gpu_memory_mb'].mean():.0f} MB")
    print(f"  Memory range: {df['peak_gpu_memory_mb'].min():.0f} - {df['peak_gpu_memory_mb'].max():.0f} MB")
    print(f"  Utilization (mean): {df['peak_gpu_utilization_percent'].mean():.1f}%")
    
    print(f"\n💾 System Memory:")
    print(f"  Mean: {df['peak_memory_mb'].mean():.0f} MB ({df['peak_memory_mb'].mean()/1024:.1f} GB)")
    print(f"  Range: {df['peak_memory_mb'].min():.0f} - {df['peak_memory_mb'].max():.0f} MB")
    
    print(f"\n🖥️ CPU Usage:")
    print(f"  Mean: {df['peak_cpu_percent'].mean():.1f}%")
    print(f"  Range: {df['peak_cpu_percent'].min():.1f}% - {df['peak_cpu_percent'].max():.1f}%")
    
    return df

def resolution_analysis(df):
    """Analyze performance by resolution"""
    print("\n" + "="*60)
    print("🖼️ RESOLUTION ANALYSIS")
    print("="*60)
    
    # Calculate pixel count for each test
    df['total_pixels'] = df['image_width'] * df['image_height']
    df['megapixels'] = df['total_pixels'] / 1000000
    
    # Group by resolution
    res_stats = df.groupby('resolution').agg({
        'generation_time_seconds': ['mean', 'min', 'max', 'count'],
        'total_pixels': 'mean',
        'peak_gpu_memory_mb': 'mean',
        'peak_memory_mb': 'mean'
    }).round(2)
    
    print("\nPerformance by Resolution:")
    print("-" * 80)
    print(f"{'Resolution':<15} {'Count':<6} {'Avg Time':<10} {'Min Time':<10} {'Max Time':<10} {'Megapixels':<12}")
    print("-" * 80)
    
    for resolution in res_stats.index:
        count = int(res_stats.loc[resolution, ('generation_time_seconds', 'count')])
        avg_time = res_stats.loc[resolution, ('generation_time_seconds', 'mean')]
        min_time = res_stats.loc[resolution, ('generation_time_seconds', 'min')]
        max_time = res_stats.loc[resolution, ('generation_time_seconds', 'max')]
        megapixels = res_stats.loc[resolution, ('total_pixels', 'mean')] / 1000000
        
        print(f"{resolution:<15} {count:<6} {avg_time:<10.1f} {min_time:<10.1f} {max_time:<10.1f} {megapixels:<12.1f}")
    
    # Correlation analysis
    correlation = df['total_pixels'].corr(df['generation_time_seconds'])
    print(f"\n🔗 Pixel count vs Generation time correlation: {correlation:.3f}")
    
    if correlation > 0.7:
        print("   → Strong positive correlation: Higher resolution = Much longer time")
    elif correlation > 0.4:
        print("   → Moderate positive correlation: Higher resolution = Longer time")
    else:
        print("   → Weak correlation: Resolution has limited impact on time")
    
    return df

def audio_duration_analysis(df):
    """Analyze performance by audio duration"""
    print("\n" + "="*60)
    print("🎵 AUDIO DURATION ANALYSIS")
    print("="*60)
    
    audio_stats = df.groupby('audio_duration_seconds').agg({
        'generation_time_seconds': ['mean', 'min', 'max', 'count'],
        'peak_gpu_memory_mb': 'mean'
    }).round(2)
    
    print("\nPerformance by Audio Duration:")
    print("-" * 70)
    print(f"{'Duration':<10} {'Count':<6} {'Avg Time':<10} {'Min Time':<10} {'Max Time':<10} {'GPU Mem':<10}")
    print("-" * 70)
    
    for duration in sorted(audio_stats.index):
        count = int(audio_stats.loc[duration, ('generation_time_seconds', 'count')])
        avg_time = audio_stats.loc[duration, ('generation_time_seconds', 'mean')]
        min_time = audio_stats.loc[duration, ('generation_time_seconds', 'min')]
        max_time = audio_stats.loc[duration, ('generation_time_seconds', 'max')]
        gpu_mem = audio_stats.loc[duration, ('peak_gpu_memory_mb', 'mean')]
        
        print(f"{duration}s{'':<7} {count:<6} {avg_time:<10.1f} {min_time:<10.1f} {max_time:<10.1f} {gpu_mem:<10.0f}")
    
    # Check linear scaling
    audio_correlation = df['audio_duration_seconds'].corr(df['generation_time_seconds'])
    print(f"\n🔗 Audio duration vs Generation time correlation: {audio_correlation:.3f}")
    
    if audio_correlation > 0.7:
        print("   → Strong linear scaling: 2x audio = ~2x time")
    elif audio_correlation > 0.4:
        print("   → Moderate scaling: Longer audio = longer time")
    else:
        print("   → Weak scaling: Audio duration has limited impact")

def efficiency_analysis(df):
    """Analyze processing efficiency"""
    print("\n" + "="*60)
    print("⚡ EFFICIENCY ANALYSIS")
    print("="*60)
    
    # Calculate efficiency metrics
    df['pixels_per_second'] = df['total_pixels'] / df['generation_time_seconds']
    df['frames_estimated'] = df['audio_duration_seconds'] * 25  # Assuming 25 FPS
    df['frames_per_second'] = df['frames_estimated'] / df['generation_time_seconds']
    
    print(f"Processing Efficiency:")
    print(f"  Average pixels/second: {df['pixels_per_second'].mean():.0f}")
    print(f"  Average frames/second: {df['frames_per_second'].mean():.2f}")
    
    # Find most/least efficient tests
    most_efficient = df.loc[df['pixels_per_second'].idxmax()]
    least_efficient = df.loc[df['pixels_per_second'].idxmin()]
    
    print(f"\n🏎️ Most Efficient:")
    print(f"   {most_efficient['resolution']} + {most_efficient['audio_duration_seconds']}s = {most_efficient['generation_time_seconds']:.1f}s")
    print(f"   ({most_efficient['pixels_per_second']:.0f} pixels/sec)")
    
    print(f"\n🐌 Least Efficient:")
    print(f"   {least_efficient['resolution']} + {least_efficient['audio_duration_seconds']}s = {least_efficient['generation_time_seconds']:.1f}s")
    print(f"   ({least_efficient['pixels_per_second']:.0f} pixels/sec)")

def resource_analysis(df):
    """Analyze resource usage patterns"""
    print("\n" + "="*60)
    print("🔧 RESOURCE USAGE ANALYSIS")
    print("="*60)
    
    # GPU Analysis
    print(f"🎮 GPU Analysis:")
    print(f"  GPU utilization is consistently {df['peak_gpu_utilization_percent'].mean():.0f}% (GPU bound)")
    print(f"  GPU memory usage: {df['peak_gpu_memory_mb'].min():.0f} - {df['peak_gpu_memory_mb'].max():.0f} MB")
    print(f"  GPU memory variation: {df['peak_gpu_memory_mb'].std():.0f} MB (very stable)")
    
    # Memory Analysis  
    print(f"\n💾 System Memory:")
    memory_gb = df['peak_memory_mb'] / 1024
    print(f"  Range: {memory_gb.min():.1f} - {memory_gb.max():.1f} GB")
    print(f"  Average: {memory_gb.mean():.1f} GB")
    
    # Check if memory scales with resolution
    memory_resolution_corr = df['total_pixels'].corr(df['peak_memory_mb'])
    print(f"  Memory vs Resolution correlation: {memory_resolution_corr:.3f}")
    
    if memory_resolution_corr > 0.5:
        print("  → Memory usage increases with resolution")
    else:
        print("  → Memory usage relatively stable across resolutions")
    
    # CPU Analysis
    print(f"\n🖥️ CPU Usage:")
    print(f"  Average: {df['peak_cpu_percent'].mean():.1f}%")
    print(f"  Range: {df['peak_cpu_percent'].min():.1f}% - {df['peak_cpu_percent'].max():.1f}%")
    
    if df['peak_cpu_percent'].mean() < 50:
        print("  → CPU is not the bottleneck (GPU bound workload)")
    else:
        print("  → CPU usage is significant (mixed workload)")

def generate_recommendations(df):
    """Generate optimization recommendations"""
    print("\n" + "="*60)
    print("💡 OPTIMIZATION RECOMMENDATIONS")
    print("="*60)
    
    # Resolution impact
    resolution_impact = df['total_pixels'].corr(df['generation_time_seconds'])
    if resolution_impact > 0.7:
        print("1. 🖼️ Resolution Management:")
        print("   • Resolution has MAJOR impact on generation time")
        print("   • Consider resizing very large images before processing")
        print("   • Implement resolution-based pricing/SLA tiers")
    
    # Audio scaling
    audio_impact = df['audio_duration_seconds'].corr(df['generation_time_seconds'])
    if audio_impact > 0.5:
        print("\n2. 🎵 Audio Optimization:")
        print("   • Audio duration scales with generation time")
        print("   • Consider chunking very long audio files")
        print("   • Implement duration-based timeouts")
    
    # Resource optimization
    gpu_util_mean = df['peak_gpu_utilization_percent'].mean()
    if gpu_util_mean > 95:
        print(f"\n3. 🎮 GPU Optimization:")
        print("   • GPU utilization is maxed out (good!)")
        print("   • Consider batch processing for efficiency")
        print("   • GPU is the primary bottleneck")
    
    cpu_util_mean = df['peak_cpu_percent'].mean()
    if cpu_util_mean < 30:
        print(f"\n4. 🖥️ CPU Underutilization:")
        print("   • CPU usage is low - could handle more parallel tasks")
        print("   • Consider concurrent request processing")
        print("   • Realtime optimizations are working well")
    
    # Memory efficiency
    memory_gb_max = df['peak_memory_mb'].max() / 1024
    if memory_gb_max > 60:
        print(f"\n5. 💾 Memory Usage:")
        print(f"   • Peak memory usage: {memory_gb_max:.1f}GB")
        print("   • High memory usage - monitor for memory leaks")
        print("   • Consider memory cleanup optimizations")
    
    print(f"\n6. 📊 Performance Benchmarks:")
    fastest_time = df['generation_time_seconds'].min()
    slowest_time = df['generation_time_seconds'].max()
    print(f"   • Best case: {fastest_time:.1f}s")
    print(f"   • Worst case: {slowest_time:.1f}s") 
    print(f"   • Performance ratio: {slowest_time/fastest_time:.1f}x difference")

def main():
    """Main analysis function"""
    csv_path = "/workspace/ai-video-generation/MuseTalk/stress_test/outputs_trial/stress_test_final_20250822_133203.csv"
    
    if not Path(csv_path).exists():
        print(f"❌ CSV file not found: {csv_path}")
        return
    
    print("🔬 MuseTalk Stress Test Analysis")
    print("="*60)
    
    # Load and analyze
    df = load_and_analyze_csv(csv_path)
    df = resolution_analysis(df)
    audio_duration_analysis(df)
    efficiency_analysis(df)
    resource_analysis(df)
    generate_recommendations(df)
    
    print("\n✅ Analysis completed!")

if __name__ == "__main__":
    main()