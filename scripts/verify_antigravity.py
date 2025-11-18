#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Verify Antigravity instrumentation.

Checks:
1. Extension installation
2. Database accessibility
3. Redis connection
4. Processing server configuration
"""

import sys
import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

# Add src to path
repo_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(repo_root))

from src.processing.antigravity.platform import get_antigravity_database_paths
from src.processing.antigravity.workspace_mapper import AntigravityWorkspaceMapper
from src.capture.shared.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_extension():
    """Check if extension is installed in Antigravity."""
    print("\n[1/4] Checking Extension Installation...")
    
    # Find CLI
    local_binary = repo_root / "binaries" / "Antigravity.app" / "Contents" / "Resources" / "app" / "bin" / "antigravity"
    system_binary = Path("/Applications/Antigravity.app/Contents/Resources/app/bin/antigravity")
    
    cli = None
    if local_binary.exists():
        cli = local_binary
    elif system_binary.exists():
        cli = system_binary
    else:
        cli = shutil.which("antigravity")
        
    if not cli:
        print("❌ Antigravity CLI not found")
        return False
        
    try:
        result = subprocess.run(
            [str(cli), "--list-extensions"], 
            capture_output=True, 
            text=True
        )
        extensions = result.stdout.splitlines()
        installed = any("blueplane-cursor-telemetry" in ext for ext in extensions)
        
        if installed:
            print("✅ Blueplane extension is installed")
            return True
        else:
            print("❌ Blueplane extension NOT found in 'antigravity --list-extensions'")
            return False
            
    except Exception as e:
        print(f"❌ Error checking extensions: {e}")
        return False

async def check_database():
    """Check if we can find and read Antigravity databases."""
    print("\n[2/4] Checking Database Access...")
    
    db_paths = get_antigravity_database_paths()
    found_dbs = 0
    
    for base_path in db_paths:
        if not base_path.exists():
            continue
            
        print(f"  Scanning {base_path}...")
        for workspace_dir in base_path.iterdir():
            if not workspace_dir.is_dir():
                continue
                
            db_file = workspace_dir / "state.vscdb"
            if db_file.exists():
                found_dbs += 1
                # Try to read it
                try:
                    import aiosqlite
                    async with aiosqlite.connect(str(db_file)) as conn:
                        await conn.execute("PRAGMA query_only=1")
                        cursor = await conn.execute("SELECT count(*) FROM ItemTable")
                        row = await cursor.fetchone()
                        print(f"  ✅ Found database for workspace {workspace_dir.name} ({row[0]} items)")
                        break # Just check one to verify access
                except Exception as e:
                    print(f"  ⚠️ Found database but could not read: {e}")
    
    if found_dbs > 0:
        print(f"✅ Found {found_dbs} Antigravity databases")
        return True
    else:
        print("❌ No Antigravity databases found (have you opened any workspaces?)")
        return False

def check_redis():
    """Check Redis connection."""
    print("\n[3/4] Checking Redis Connection...")
    try:
        import redis
        config = Config()
        r = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            socket_timeout=1.0
        )
        r.ping()
        print("✅ Redis is running and accessible")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("  Run 'redis-server' to start Redis")
        return False

def check_server_config():
    """Check if server code has Antigravity enabled."""
    print("\n[4/4] Checking Server Configuration...")
    
    server_path = repo_root / "src" / "processing" / "server.py"
    try:
        with open(server_path, 'r') as f:
            content = f.read()
            
        if "AntigravityDatabaseMonitor" in content and "_initialize_antigravity_monitor" in content:
            print("✅ Server is configured for Antigravity")
            return True
        else:
            print("❌ Server code missing Antigravity configuration")
            return False
    except Exception as e:
        print(f"❌ Error reading server code: {e}")
        return False

async def main():
    print("Blueplane Telemetry - Antigravity Verification")
    print("==============================================")
    
    results = [
        check_extension(),
        await check_database(),
        check_redis(),
        check_server_config()
    ]
    
    print("\nSummary")
    print("=======")
    if all(results):
        print("✅ All checks passed! System is ready.")
        print("\nNext steps:")
        print("1. Start the server: python scripts/start_server.py")
        print("2. Open Antigravity and use the 'Blueplane: Start New Session' command")
        print("3. Check logs/telemetry.db for events")
    else:
        print("❌ Some checks failed. Please review errors above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
