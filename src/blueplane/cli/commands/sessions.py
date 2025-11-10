"""
Sessions command for CLI.
"""

import click
import httpx
from rich.console import Console
from rich.table import Table

from ...config import config

console = Console()


@click.command("sessions")
@click.option("--platform", "-p", help="Filter by platform")
@click.option("--limit", "-l", type=int, default=10, help="Maximum number of sessions")
def sessions_command(platform: str, limit: int):
    """
    List all telemetry sessions.
    """
    try:
        # Call API
        url = f"http://{config.server_host}:{config.server_port}{config.api_prefix}/sessions"
        params = {"limit": limit}
        if platform:
            params["platform"] = platform
        
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=5.0)
            response.raise_for_status()
            sessions = response.json()
        
        if not sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return
        
        # Display as table
        table = Table(title="Telemetry Sessions", show_header=True, header_style="bold magenta")
        table.add_column("Session ID", style="cyan")
        table.add_column("Platform", style="green")
        table.add_column("Conversations", style="yellow")
        table.add_column("Acceptance Rate", style="blue")
        
        for session in sessions:
            table.add_row(
                session.get("session_id", ""),
                session.get("platform", ""),
                str(session.get("interaction_count", 0)),
                f"{session.get('acceptance_rate', 0) * 100:.1f}%" if session.get("acceptance_rate") else "N/A",
            )
        
        console.print(table)
        
    except httpx.ConnectError:
        console.print(
            f"[red]Error: Could not connect to API server[/red]\n"
            f"Make sure the server is running on {config.server_host}:{config.server_port}"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


import sys

