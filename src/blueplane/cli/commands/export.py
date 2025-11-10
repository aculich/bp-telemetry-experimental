"""
Export command for CLI.
"""

import click
import httpx
from rich.console import Console
from pathlib import Path

from ...config import config

console = Console()


@click.command("export")
@click.option("--format", "-f", type=click.Choice(["json", "csv"]), default="json", help="Export format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--time-range", "-t", default="7d", help="Time range (e.g., 7d, 30d)")
def export_command(format: str, output: str, time_range: str):
    """
    Export telemetry data.
    
    Exports data in JSON or CSV format.
    """
    try:
        # Call API
        url = f"http://{config.server_host}:{config.server_port}{config.api_prefix}/export"
        params = {"format": format, "time_range": time_range}
        
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            result = response.json()
        
        data = result.get("data", [])
        
        # Write to file or stdout
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == "csv":
                output_path.write_text(data)
            else:
                import json
                output_path.write_text(json.dumps(data, indent=2))
            
            console.print(f"[green]✅ Exported {len(data)} records to {output_path}[/green]")
        else:
            # Print to stdout
            if format == "csv":
                console.print(data)
            else:
                import json
                console.print_json(data=data)
        
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

