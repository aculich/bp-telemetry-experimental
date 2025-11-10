"""
Analyze command for CLI.
"""

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...config import config

console = Console()


@click.command("analyze")
@click.argument("session_id")
def analyze_command(session_id: str):
    """
    Analyze a telemetry session.
    
    Provides deep analysis and insights for a specific session.
    """
    try:
        # Call API
        url = f"http://{config.server_host}:{config.server_port}{config.api_prefix}/sessions/{session_id}/analysis"
        
        with httpx.Client() as client:
            response = client.get(url, timeout=5.0)
            response.raise_for_status()
            analysis = response.json()
        
        # Display analysis
        console.print(Panel(f"Session Analysis: {session_id}", style="bold magenta"))
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Conversations", str(analysis.get("total_conversations", 0)))
        table.add_row("Total Interactions", str(analysis.get("total_interactions", 0)))
        
        acceptance_rate = analysis.get("avg_acceptance_rate", 0)
        table.add_row("Average Acceptance Rate", f"{acceptance_rate * 100:.1f}%")
        
        console.print(table)
        
        # Show conversations
        conversations = analysis.get("conversations", [])
        if conversations:
            console.print("\n[bold]Conversations:[/bold]")
            conv_table = Table(show_header=True, header_style="bold")
            conv_table.add_column("ID", style="cyan")
            conv_table.add_column("Platform", style="green")
            conv_table.add_column("Interactions", style="yellow")
            conv_table.add_column("Acceptance Rate", style="blue")
            
            for conv in conversations:
                conv_table.add_row(
                    conv.get("id", "")[:8] + "...",
                    conv.get("platform", ""),
                    str(conv.get("interaction_count", 0)),
                    f"{conv.get('acceptance_rate', 0) * 100:.1f}%" if conv.get("acceptance_rate") else "N/A",
                )
            
            console.print(conv_table)
        
    except httpx.ConnectError:
        console.print(
            f"[red]Error: Could not connect to API server[/red]\n"
            f"Make sure the server is running on {config.server_host}:{config.server_port}"
        )
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]Session not found: {session_id}[/red]")
        else:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


import sys

