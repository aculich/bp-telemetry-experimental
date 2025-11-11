#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Installation script for Cursor telemetry capture.

Copies hooks to project .cursor directory and sets up configuration.
"""

import sys
import os
import shutil
import json
import argparse
from pathlib import Path


def find_project_root() -> Path:
    """Find the project root directory."""
    current = Path(__file__).parent.parent
    return current


def install_hooks(workspace_path: Path, source_path: Path) -> bool:
    """
    Install hooks to workspace .cursor directory.

    Args:
        workspace_path: Target workspace directory
        source_path: Source directory containing hooks

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create .cursor/hooks/telemetry directory
        cursor_dir = workspace_path / ".cursor"
        hooks_dir = cursor_dir / "hooks" / "telemetry"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        # Copy hook scripts
        source_hooks = source_path / "src" / "capture" / "cursor" / "hooks"
        if not source_hooks.exists():
            print(f"❌ Source hooks directory not found: {source_hooks}")
            return False

        print(f"📦 Copying hooks from {source_hooks} to {hooks_dir}")

        # Copy all Python files
        for hook_file in source_hooks.glob("*.py"):
            if hook_file.name != "hook_base.py":
                dest = hooks_dir / hook_file.name
                shutil.copy2(hook_file, dest)
                # Make executable
                os.chmod(dest, 0o755)
                print(f"   ✅ {hook_file.name}")

        # Copy hook_base.py to parent directory
        hook_base = source_hooks.parent / "hook_base.py"
        if hook_base.exists():
            shutil.copy2(hook_base, hooks_dir.parent / "hook_base.py")
            print(f"   ✅ hook_base.py")

        # Copy shared modules
        shared_dir = source_path / "src" / "capture" / "shared"
        if shared_dir.exists():
            target_shared = hooks_dir.parent / "shared"
            if target_shared.exists():
                shutil.rmtree(target_shared)
            shutil.copytree(shared_dir, target_shared)
            print(f"   ✅ shared/ (modules)")

        # Copy hooks.json
        hooks_json_src = source_hooks / "hooks.json"
        if not hooks_json_src.exists():
            hooks_json_src = source_hooks.parent / "hooks.json"

        if hooks_json_src.exists():
            hooks_json_dest = cursor_dir / "hooks.json"
            shutil.copy2(hooks_json_src, hooks_json_dest)
            print(f"   ✅ hooks.json")
        else:
            print(f"   ⚠️  hooks.json not found, creating minimal version")
            create_minimal_hooks_json(cursor_dir)

        return True

    except Exception as e:
        print(f"❌ Failed to install hooks: {e}")
        return False


def create_minimal_hooks_json(cursor_dir: Path) -> None:
    """Create minimal hooks.json configuration."""
    hooks_config = {
        "version": 1,
        "description": "Blueplane Telemetry Hooks",
        "hooks": {
            "beforeSubmitPrompt": [{"command": "hooks/telemetry/before_submit_prompt.py", "enabled": True}],
            "afterAgentResponse": [{"command": "hooks/telemetry/after_agent_response.py", "enabled": True}],
            "afterFileEdit": [{"command": "hooks/telemetry/after_file_edit.py", "enabled": True}],
            "stop": [{"command": "hooks/telemetry/stop.py", "enabled": True}],
        }
    }

    hooks_json_path = cursor_dir / "hooks.json"
    with open(hooks_json_path, 'w') as f:
        json.dump(hooks_config, f, indent=2)


def install_config(workspace_path: Path, source_path: Path) -> bool:
    """
    Install configuration files.

    Args:
        workspace_path: Target workspace directory
        source_path: Source directory containing config

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create .blueplane directory in home
        blueplane_dir = Path.home() / ".blueplane"
        blueplane_dir.mkdir(exist_ok=True)

        # Copy config files
        config_source = source_path / "config"
        if config_source.exists():
            for config_file in config_source.glob("*.yaml"):
                dest = blueplane_dir / config_file.name
                if not dest.exists():  # Don't overwrite existing config
                    shutil.copy2(config_file, dest)
                    print(f"   ✅ {config_file.name}")
                else:
                    print(f"   ⏭️  {config_file.name} (already exists)")

        return True

    except Exception as e:
        print(f"❌ Failed to install config: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Install Cursor telemetry capture'
    )
    parser.add_argument(
        '--workspace',
        type=Path,
        default=Path.cwd(),
        help='Workspace directory (default: current directory)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without doing it'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Blueplane Telemetry - Cursor Installation")
    print("=" * 60)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")

    # Find source directory
    source_path = find_project_root()
    print(f"\n📂 Source: {source_path}")
    print(f"📂 Workspace: {args.workspace}\n")

    if args.dry_run:
        print("Would install:")
        print("  - Hooks to .cursor/hooks/telemetry/")
        print("  - Configuration to ~/.blueplane/")
        print("\nRun without --dry-run to proceed")
        return 0

    # Install hooks
    print("📦 Installing hooks...")
    if not install_hooks(args.workspace, source_path):
        return 1

    # Install configuration
    print("\n⚙️  Installing configuration...")
    if not install_config(args.workspace, source_path):
        return 1

    print("\n" + "=" * 60)
    print("✅ Installation completed successfully!")
    print("=" * 60)

    print("\n📋 Next steps:")
    print("  1. Install Python dependencies:")
    print("     pip install redis pyyaml")
    print("  2. Start Redis server:")
    print("     redis-server")
    print("  3. Initialize Redis streams:")
    print("     python scripts/init_redis.py")
    print("  4. (Optional) Install Cursor extension for database monitoring")
    print("\n💡 Verify installation:")
    print("     python scripts/verify_installation.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
