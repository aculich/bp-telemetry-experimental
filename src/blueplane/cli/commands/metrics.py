"""
Metrics command for CLI.
"""

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ...config import config

console = Console()


@click.command("metrics")
@click.option("--category", "-c", help="Metric category (realtime, session, tools)")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table")
def metrics_command(category: str, format: str):
    """
    Display current telemetry metrics.
    
    Shows real-time metrics, session metrics, and tool metrics.
    """
    try:
        # Call API
        url = f"http://{config.server_host}:{config.server_port}{config.api_prefix}/metrics"
        params = {}
        if category:
            params["category"] = category
        
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()
        
        if format == "json":
            console.print_json(data=data)
            return
        
        # Display as table
        table = Table(title="Telemetry Metrics", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Metric", style="green")
        table.add_column("Value", style="yellow")
        
        for cat_name, cat_data in data.items():
            if isinstance(cat_data, dict):
                for metric_name, metric_value in cat_data.items():
                    table.add_row(cat_name, metric_name, str(metric_value))
        
        console.print(table)
        
    except httpx.ConnectError:
        console.print(
            Panel(
                f"[red]Error: Could not connect to API server[/red]\n"
                f"Make sure the server is running on {config.server_host}:{config.server_port}\n"
                f"Run: python scripts/run_api_server.py",
                title="Connection Error",
            )
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


import sys

