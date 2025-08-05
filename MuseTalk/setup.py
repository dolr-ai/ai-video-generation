#!/usr/bin/env python3
"""
Setup script for MuseTalk with Flask API service
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "MuseTalk: Real-Time High-Fidelity Video Dubbing via Spatio-Temporal Sampling"

# Read requirements
def read_requirements(filename):
    req_path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

# Base requirements from MuseTalk
base_requirements = read_requirements('requirements.txt')

# Service-specific requirements
service_requirements = read_requirements('service/requirements.txt')

# Combine all requirements
all_requirements = base_requirements + service_requirements

setup(
    name="musetalk",
    version="1.5.0",
    description="Real-Time High-Fidelity Video Dubbing via Spatio-Temporal Sampling",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Lyra Lab, Tencent Music Entertainment",
    url="https://github.com/TMElyralab/MuseTalk",
    
    # Package discovery
    packages=find_packages(include=['musetalk*', 'service*']),
    
    # Include package data
    include_package_data=True,
    package_data={
        'musetalk': ['**/*.py', '**/*.json', '**/*.yaml', '**/*.yml'],
        'service': ['**/*.py', '**/*.json', '**/*.yaml', '**/*.yml'],
    },
    
    # Dependencies
    install_requires=all_requirements,
    
    # Extra dependencies
    extras_require={
        'api': service_requirements,
        'dev': [
            'pytest>=6.0',
            'pytest-cov>=2.0',
            'black>=21.0',
            'flake8>=3.8',
        ],
    },
    
    # Entry points for command-line scripts
    entry_points={
        'console_scripts': [
            'musetalk-api=service.app:main',
            'musetalk-inference=scripts.inference:main',
            'musetalk-realtime=scripts.realtime_inference:main',
        ],
    },
    
    # Python version requirement
    python_requires='>=3.8',
    
    # Classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Multimedia :: Video',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    
    # Keywords for PyPI
    keywords='talking-head, video-generation, lip-sync, deepfake, ai, computer-vision, flask-api',
    
    # Project URLs
    project_urls={
        'Bug Reports': 'https://github.com/TMElyralab/MuseTalk/issues',
        'Source': 'https://github.com/TMElyralab/MuseTalk',
        'Documentation': 'https://github.com/TMElyralab/MuseTalk/blob/main/README.md',
    },
)