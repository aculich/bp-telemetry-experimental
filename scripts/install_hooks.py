#!/usr/bin/env python3
"""
Install Layer 1 hooks for Claude Code and Cursor.
"""

import sys
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def install_claude_hooks():
    """Install Claude Code hooks to ~/.claude/hooks/telemetry/"""
    hooks_dir = Path.home() / ".claude" / "hooks" / "telemetry"
    source_dir = Path(__file__).parent.parent / "hooks" / "claude"
    
    print(f"Installing Claude Code hooks to {hooks_dir}...")
    
    # Create directory
    hooks_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy hook scripts
    hooks = ["SessionStart", "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "PreCompact"]
    for hook in hooks:
        source = source_dir / hook
        if source.exists():
            dest = hooks_dir / hook
            shutil.copy2(source, dest)
            dest.chmod(0o755)  # Make executable
            print(f"  ✅ Installed {hook}")
        else:
            print(f"  ⚠️  {hook} not found")
    
    print(f"\n✅ Claude Code hooks installed to {hooks_dir}")
    print("   Hooks will be called automatically by Claude Code.")


def install_cursor_hooks(project_root: str = None):
    """
    Install Cursor hooks to .cursor/hooks/telemetry/ in current or specified project.
    
    Args:
        project_root: Project root directory (defaults to current directory)
    """
    if project_root:
        project_dir = Path(project_root)
    else:
        project_dir = Path.cwd()
    
    hooks_dir = project_dir / ".cursor" / "hooks" / "telemetry"
    source_dir = Path(__file__).parent.parent / "hooks" / "cursor"
    
    print(f"Installing Cursor hooks to {hooks_dir}...")
    
    # Create directory
    hooks_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy hook scripts
    hooks = [
        "beforeSubmitPrompt",
        "afterAgentResponse",
        "beforeMCPExecution",
        "afterMCPExecution",
        "afterFileEdit",
        "stop",
    ]
    for hook in hooks:
        source = source_dir / hook
        if source.exists():
            dest = hooks_dir / hook
            shutil.copy2(source, dest)
            dest.chmod(0o755)  # Make executable
            print(f"  ✅ Installed {hook}")
        else:
            print(f"  ⚠️  {hook} not found")
    
    print(f"\n✅ Cursor hooks installed to {hooks_dir}")
    print("   Note: Cursor extension is required for session management.")


def main():
    """Main installation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Install Blueplane Telemetry hooks")
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Install Claude Code hooks",
    )
    parser.add_argument(
        "--cursor",
        action="store_true",
        help="Install Cursor hooks",
    )
    parser.add_argument(
        "--cursor-project",
        type=str,
        help="Project root for Cursor hooks (defaults to current directory)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Install all hooks",
    )
    
    args = parser.parse_args()
    
    if args.all or args.claude:
        install_claude_hooks()
    
    if args.all or args.cursor:
        install_cursor_hooks(args.cursor_project)
    
    if not (args.all or args.claude or args.cursor):
        print("No hooks specified. Use --claude, --cursor, or --all")
        print("\nExamples:")
        print("  python scripts/install_hooks.py --all")
        print("  python scripts/install_hooks.py --claude")
        print("  python scripts/install_hooks.py --cursor --cursor-project /path/to/project")


if __name__ == "__main__":
    main()

