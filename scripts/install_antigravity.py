#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Install Blueplane Telemetry extension into Antigravity IDE.

Steps:
1. Builds the VS Code extension (npm install & compile)
2. Packages it into a .vsix file
3. Installs it using the Antigravity CLI
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    # Setup paths
    repo_root = Path(__file__).parent.parent.resolve()
    extension_dir = repo_root / "src" / "capture" / "cursor" / "extension"
    
    print(f"Blueplane Telemetry - Antigravity Installer")
    print(f"===========================================")
    
    # 1. Find Antigravity CLI
    print(f"\n[1/3] Locating Antigravity CLI...")
    
    # Check local binaries first (repo copy)
    local_binary = repo_root / "binaries" / "Antigravity.app" / "Contents" / "Resources" / "app" / "bin" / "antigravity"
    
    # Check system install
    system_binary = Path("/Applications/Antigravity.app/Contents/Resources/app/bin/antigravity")
    
    antigravity_cli = None
    if local_binary.exists():
        antigravity_cli = local_binary
        print(f"  Found local binary: {antigravity_cli}")
        # Ensure executable
        os.chmod(antigravity_cli, 0o755)
    elif system_binary.exists():
        antigravity_cli = system_binary
        print(f"  Found system binary: {antigravity_cli}")
    else:
        # Try PATH
        antigravity_cli = shutil.which("antigravity")
        if antigravity_cli:
            print(f"  Found in PATH: {antigravity_cli}")

    if not antigravity_cli:
        print("  Error: Antigravity CLI not found.")
        print("  Please ensure Antigravity is installed in /Applications or in the 'binaries' directory.")
        sys.exit(1)

    # 2. Build Extension
    print(f"\n[2/3] Building extension...")
    os.chdir(extension_dir)
    
    try:
        # Install dependencies
        print("  Running npm install...")
        subprocess.check_call(["npm", "install"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        # Compile
        print("  Compiling TypeScript...")
        subprocess.check_call(["npm", "run", "compile"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        # Package
        print("  Packaging VSIX...")
        # Using npx to run vsce without global install
        subprocess.check_call(["npx", "-y", "@vscode/vsce", "package"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
    except subprocess.CalledProcessError as e:
        print(f"  Error building extension: {e}")
        sys.exit(1)
    
    # Find the generated VSIX
    vsix_files = list(extension_dir.glob("*.vsix"))
    if not vsix_files:
        print("  Error: No VSIX file generated.")
        sys.exit(1)
        
    # Get the most recent one
    vsix_file = sorted(vsix_files, key=lambda p: p.stat().st_mtime)[-1]
    print(f"  Generated: {vsix_file.name}")

    # 3. Install Extension
    print(f"\n[3/3] Installing into Antigravity...")
    try:
        cmd = [str(antigravity_cli), "--install-extension", str(vsix_file)]
        subprocess.check_call(cmd)
        print("\nSuccess! Extension installed.")
        print("Please restart Antigravity to enable telemetry.")
        
    except subprocess.CalledProcessError as e:
        print(f"\nError installing extension: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
