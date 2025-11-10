#!/usr/bin/env python3
"""
Run the Blueplane Telemetry Core API server.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn
from blueplane.server.api import create_app
from blueplane.config import config

if __name__ == "__main__":
    app = create_app()
    
    print(f"Starting Blueplane Telemetry Core API server...")
    print(f"  Host: {config.server_host}")
    print(f"  Port: {config.server_port}")
    print(f"  API: http://{config.server_host}:{config.server_port}{config.api_prefix}")
    print()
    
    uvicorn.run(
        app,
        host=config.server_host,
        port=config.server_port,
        log_level="info",
    )

