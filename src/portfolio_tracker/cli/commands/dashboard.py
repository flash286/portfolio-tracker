"""Dashboard — generate an interactive web dashboard for a portfolio."""

import http.server
import json
import socket
import socketserver
import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from ...data.repositories.portfolios_repo import PortfoliosRepository
from .dashboard_data import _collect_data, _decimal_default

app = typer.Typer(help="Web dashboard")
console = Console()

_TEMPLATE = Path(__file__).with_name("dashboard.html")


@app.command("open")
def open_dashboard(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    output: str = typer.Option("", "--output", "-o", help="Save HTML to this path (skips browser)"),
):
    """Generate and open a web dashboard for a portfolio."""
    portfolios_repo = PortfoliosRepository()
    portfolio = portfolios_repo.get_by_id(portfolio_id)
    if not portfolio:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    # Auto-snapshot: record today's state before collecting dashboard data
    try:
        from ...data.repositories.snapshots_repo import take_snapshot_for_portfolio
        snap = take_snapshot_for_portfolio(portfolio_id)
        if snap.holdings_value > 0:
            console.print(f"[dim]Snapshot recorded for {snap.date}[/dim]")
    except Exception:
        pass  # never let snapshot failure break the dashboard

    console.print(f"[cyan]Collecting data for '{portfolio.name}'...[/cyan]")
    portfolio_data = _collect_data(portfolio_id)

    data_json = json.dumps(portfolio_data, default=_decimal_default, ensure_ascii=False)
    html = _TEMPLATE.read_text(encoding="utf-8").replace("__DATA_PLACEHOLDER__", data_json)

    if output:
        Path(output).write_text(html, encoding="utf-8")
        console.print(f"[green]Dashboard saved to {output}[/green]")
        return

    # Serve via local HTTP so the browser can make API calls (file:// blocks cross-origin fetch)
    html_bytes = html.encode("utf-8")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)

        def log_message(self, *args):
            pass

    url = f"http://127.0.0.1:{port}/"
    with socketserver.TCPServer(("127.0.0.1", port), _Handler) as httpd:
        webbrowser.open(url)
        console.print(f"[green]Dashboard: {url}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[dim]Server stopped.[/dim]")
