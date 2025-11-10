"""
Layer 3 CLI interface entry point.
"""

import click
import sys
from pathlib import Path

# Add src to path for development
if Path(__file__).parent.parent.parent.parent.exists():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .commands.metrics import metrics_command
from .commands.sessions import sessions_command
from .commands.analyze import analyze_command
from .commands.export import export_command
from ..config import config


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Blueplane Telemetry Core CLI
    
    Privacy-first, local-only telemetry and analytics for AI-assisted coding.
    """
    pass


# Register commands
cli.add_command(metrics_command)
cli.add_command(sessions_command)
cli.add_command(analyze_command)
cli.add_command(export_command)


def main():
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()

