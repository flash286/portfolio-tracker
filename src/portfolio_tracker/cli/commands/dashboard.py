"""Dashboard — generate an interactive web dashboard for a portfolio."""

import http.server
import json
import os
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
_DASHBOARD_DIR = Path(__file__).resolve().parents[4] / "dashboard"
_DIST_HTML = _DASHBOARD_DIR / "dist" / "index.html"

_LIVE_RELOAD_SCRIPT = (  # noqa: E501
    '<script>(function(){setInterval(function(){fetch("/poll")'
    ".then(function(r){return r.json()})"
    ".then(function(d){if(d.reload)location.reload()})"
    ".catch(function(){})},500)})()</script>"
)


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
    template_path = _DIST_HTML if _DIST_HTML.exists() else _TEMPLATE
    html = template_path.read_text(encoding="utf-8").replace("__DATA_PLACEHOLDER__", data_json)

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


@app.command("dev")
def dev_server(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    port: int = typer.Option(3000, "--port", "-p", help="Server port"),
    data_refresh: bool = typer.Option(False, "--data-refresh", help="Re-collect portfolio data on each reload"),
    vite: bool = typer.Option(False, "--vite", help="Start Vite HMR dev server (requires Node.js)"),
):
    """Start a development server with live reload for dashboard editing."""
    portfolios_repo = PortfoliosRepository()
    portfolio = portfolios_repo.get_by_id(portfolio_id)
    if not portfolio:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Collecting data for '{portfolio.name}'...[/cyan]")
    cached_data_json = json.dumps(_collect_data(portfolio_id), default=_decimal_default, ensure_ascii=False)

    if vite:
        _dev_vite(portfolio_id, port, cached_data_json, data_refresh)
    else:
        _dev_legacy(portfolio_id, port, cached_data_json, data_refresh)


def _dev_legacy(portfolio_id, port, cached_data_json, data_refresh):
    """Legacy dev server — watches dashboard.html with poll-based live reload."""
    last_mtime = os.stat(_TEMPLATE).st_mtime

    class _DevHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal cached_data_json, last_mtime

            if self.path == "/poll":
                current_mtime = os.stat(_TEMPLATE).st_mtime
                reload = current_mtime != last_mtime
                if reload:
                    last_mtime = current_mtime
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reload": reload}).encode())
                return

            if data_refresh:
                cached_data_json = json.dumps(
                    _collect_data(portfolio_id), default=_decimal_default, ensure_ascii=False
                )
            try:
                template = _TEMPLATE.read_text(encoding="utf-8")
            except FileNotFoundError:
                self.send_error(404)
                return
            html = template.replace("__DATA_PLACEHOLDER__", cached_data_json)
            html = html.replace("</body>", _LIVE_RELOAD_SCRIPT + "</body>")
            html_bytes = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html_bytes)

        def log_message(self, *args):
            pass

    url = f"http://127.0.0.1:{port}/"
    with socketserver.TCPServer(("127.0.0.1", port), _DevHandler) as httpd:
        webbrowser.open(url)
        console.print(f"[green]Dev server: {url}[/green]")
        console.print(f"[dim]Watching {_TEMPLATE.name} for changes (live reload)[/dim]")
        if data_refresh:
            console.print("[dim]Data refresh enabled — portfolio data re-collected on each reload[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[dim]Dev server stopped.[/dim]")


def _dev_vite(portfolio_id, port, cached_data_json, data_refresh):
    """Vite HMR dev server — Python API + Vite subprocess."""
    import shutil
    import subprocess
    import threading

    if not shutil.which("npx"):
        console.print("[red]Node.js not found. Install Node.js or use --no-vite for legacy mode.[/red]")
        raise typer.Exit(1)

    if not (_DASHBOARD_DIR / "node_modules").exists():
        console.print("[yellow]Installing dashboard dependencies...[/yellow]")
        subprocess.run(["npm", "install"], cwd=str(_DASHBOARD_DIR), check=True)

    api_port = port + 1

    class _ApiHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal cached_data_json
            if self.path == "/api/data":
                if data_refresh:
                    cached_data_json = json.dumps(
                        _collect_data(portfolio_id), default=_decimal_default, ensure_ascii=False
                    )
                data_bytes = cached_data_json.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data_bytes)))
                self.send_header("Access-Control-Allow-Origin", f"http://127.0.0.1:{port}")
                self.end_headers()
                self.wfile.write(data_bytes)
            else:
                self.send_error(404)

        def log_message(self, *args):
            pass

    # Start Python API server in background thread
    api_server = socketserver.TCPServer(("127.0.0.1", api_port), _ApiHandler)
    api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
    api_thread.start()
    console.print(f"[dim]API server on http://127.0.0.1:{api_port}/api/data[/dim]")

    # Start Vite dev server (pass API port so vite.config.js can proxy correctly)
    vite_env = {**os.environ, "VITE_API_PORT": str(api_port)}
    vite_proc = subprocess.Popen(
        ["npx", "vite", "--port", str(port), "--open"],
        cwd=str(_DASHBOARD_DIR),
        env=vite_env,
    )
    console.print(f"[green]Vite dev server: http://127.0.0.1:{port}/[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    try:
        vite_proc.wait()
    except KeyboardInterrupt:
        vite_proc.terminate()
        vite_proc.wait(timeout=5)
        api_server.shutdown()
        console.print("\n[dim]Dev server stopped.[/dim]")
