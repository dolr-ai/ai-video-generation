#!/usr/bin/env python3
"""
Direct Python runner for MuseTalk Flask API
Run this after installing the package with: pip install -e .
"""

import os
from service.app import create_app
from service.config.settings import Config

if __name__ == '__main__':
    # Create the Flask app
    app = create_app()
    
    # Get configuration
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"Starting MuseTalk Flask API on http://{host}:{port}")
    print(f"Health check: http://{host}:{port}/api/v1/health")
    
    # Run the app
    app.run(
        host=host,
        port=port,
        debug=Config.DEBUG,
        threaded=True
    )