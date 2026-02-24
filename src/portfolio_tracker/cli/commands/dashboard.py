"""Dashboard — generate an interactive web dashboard for a portfolio."""

import json
import tempfile
import webbrowser
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import typer
from rich.console import Console

from ...core.calculator import PortfolioCalculator
from ...core.models import Holding
from ...core.rebalancer import Rebalancer
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.prices_repo import PricesRepository
from ...data.repositories.targets_repo import TargetsRepository
from ...data.repositories.transactions_repo import TransactionsRepository

app = typer.Typer(help="Web dashboard")
console = Console()


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _get_cash_balance(portfolio_id: int) -> Decimal:
    """Get cash balance from the database."""
    cash_repo = CashRepository()
    return cash_repo.get_balance(portfolio_id)


def _collect_data(portfolio_id: int) -> dict:
    """Collect all portfolio data into a JSON-serializable dict."""
    portfolios_repo = PortfoliosRepository()
    holdings_repo = HoldingsRepository()
    prices_repo = PricesRepository()
    targets_repo = TargetsRepository()
    tx_repo = TransactionsRepository()

    portfolio = portfolios_repo.get_by_id(portfolio_id)
    if not portfolio:
        raise typer.Exit(1)

    holdings = holdings_repo.list_by_portfolio(portfolio_id)

    # Load latest prices
    for h in holdings:
        latest = prices_repo.get_latest(h.id)
        if latest:
            h.current_price = latest.price

    calc = PortfolioCalculator
    total_value = calc.total_value(holdings)
    total_cost = calc.total_cost_basis(holdings)
    total_pnl = calc.total_unrealized_pnl(holdings)
    pnl_pct = (total_pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")

    alloc_by_type = calc.allocation_by_type(holdings)
    alloc_by_isin = calc.allocation_by_isin(holdings)
    tax_info = calc.calculate_german_tax(total_pnl)

    # Targets & rebalancing
    targets = targets_repo.list_by_portfolio(portfolio_id)
    deviations = {}
    if targets:
        reb = Rebalancer(holdings, targets)
        deviations = reb.check_deviation()

    # Transactions summary & cash balance
    all_tx = tx_repo.list_by_portfolio(portfolio_id)
    # Dividends are stored with quantity=0, price=dividend_amount
    total_dividends = sum(
        (t.price for t in all_tx if t.transaction_type.value == "dividend"),
        Decimal("0"),
    )

    # Cash balance from the database
    cash_balance = _get_cash_balance(portfolio_id)

    # Holdings detail
    holdings_data = []
    for h in holdings:
        holdings_data.append({
            "id": h.id,
            "isin": h.isin,
            "name": h.name,
            "ticker": h.ticker,
            "asset_type": h.asset_type.value,
            "shares": h.shares,
            "cost_basis": h.cost_basis,
            "current_price": h.current_price,
            "current_value": h.current_value if h.current_price else Decimal("0"),
            "pnl": h.unrealized_pnl if h.current_price else Decimal("0"),
            "pnl_pct": h.unrealized_pnl_pct if h.current_price else Decimal("0"),
            "weight": alloc_by_isin.get(h.isin, Decimal("0")),
        })

    # Sort by value desc
    holdings_data.sort(key=lambda x: float(x["current_value"]), reverse=True)

    # Build ISIN → short name lookup (from holdings + well-known tickers)
    isin_names = {
        # Portfolio A targets
        "IE00BK5BQT80": "VWCE",
        "IE00BMC38736": "VVSM",
        "IE00BGV5VN51": "XAIX",
        "IE00BYZK4776": "HEAL",
        "IE00BG47KH54": "VAGF",
    }
    for h in holdings:
        isin_names[h.isin] = h.ticker or h.name or h.isin[:8]

    # Deviation data for chart
    deviation_data = []
    for key, info in deviations.items():
        name = isin_names.get(key, key[:8])
        deviation_data.append({
            "key": key,
            "name": name,
            "current": info["current"],
            "target": info["target"],
            "deviation": info["deviation"],
            "needs_rebalance": info["needs_rebalance"],
        })

    deviation_data.sort(key=lambda x: float(x["target"]), reverse=True)

    return {
        "portfolio_name": portfolio.name,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "holdings_value": total_value,
            "cash_balance": cash_balance,
            "total_value": total_value + cash_balance,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "pnl_pct": pnl_pct,
            "total_dividends": total_dividends,
            "holdings_count": len(holdings),
        },
        "tax": {
            "gross_gain": tax_info.gross_gain,
            "freistellungsauftrag_used": tax_info.freistellungsauftrag_used,
            "taxable_gain": tax_info.taxable_gain,
            "abgeltungssteuer": tax_info.abgeltungssteuer,
            "soli": tax_info.solidaritaetszuschlag,
            "total_tax": tax_info.total_tax,
            "net_gain": tax_info.net_gain,
        },
        "allocation_by_type": {k: v for k, v in alloc_by_type.items()},
        "holdings": holdings_data,
        "deviations": deviation_data,
    }


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portfolio Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #242836;
    --border: #2e3348; --text: #e4e6f0; --text2: #8b8fa3;
    --green: #22c55e; --red: #ef4444; --blue: #3b82f6;
    --purple: #a855f7; --amber: #f59e0b; --cyan: #06b6d4;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 32px; flex-wrap: wrap; gap: 12px; }
  .header h1 { font-size: 28px; font-weight: 700; }
  .header .date { color: var(--text2); font-size: 14px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .kpi .label { font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .kpi .value { font-size: 24px; font-weight: 700; }
  .kpi .sub { font-size: 13px; margin-top: 4px; }
  .positive { color: var(--green); }
  .negative { color: var(--red); }
  .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
  @media (max-width: 768px) { .charts-row { grid-template-columns: 1fr; } }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
  .card h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th { text-align: left; color: var(--text2); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; padding: 10px 12px; border-bottom: 1px solid var(--border); }
  td { padding: 12px; border-bottom: 1px solid var(--border); }
  tr:hover td { background: var(--surface2); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .chart-container { display: flex; align-items: center; gap: 24px; }
  .chart-container svg { flex-shrink: 0; }
  .legend { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
  .legend-item { display: flex; align-items: center; gap: 8px; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .dev-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); }
  .dev-row:last-child { border-bottom: none; }
  .dev-label { width: 56px; font-size: 12px; font-weight: 600; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dev-bars { flex: 1; display: flex; flex-direction: column; gap: 3px; }
  .dev-bar-wrap { height: 12px; width: 100%; background: var(--surface2); border-radius: 3px; overflow: hidden; }
  .dev-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
  .dev-pcts { width: 160px; font-size: 12px; text-align: right; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .dev-badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 4px; }
  .dev-badge.ok { background: rgba(34,197,94,0.15); color: var(--green); }
  .dev-badge.warn { background: rgba(239,68,68,0.15); color: var(--red); }
  .tax-grid { display: grid; grid-template-columns: 1fr; gap: 0; }
  .tax-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); }
  .tax-item:last-child { border-bottom: none; }
  .tax-item .tl { color: var(--text2); font-size: 13px; }
  .tax-item .tv { font-weight: 600; font-size: 14px; font-variant-numeric: tabular-nums; }
  .tax-item.highlight { padding: 12px 0; margin-top: 4px; border-top: 2px solid var(--border); border-bottom: none; }
  .tax-item.highlight .tl { color: var(--text); font-size: 15px; font-weight: 600; }
  .tax-item.highlight .tv { font-size: 20px; }
  .tooltip { position: absolute; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.15s; white-space: nowrap; z-index: 10; }
</style>
</head>
<body>
<div class="container" id="app"></div>
<script>
const D = window.__PORTFOLIO_DATA__ = __DATA_PLACEHOLDER__;
const COLORS = ['#3b82f6','#a855f7','#22c55e','#f59e0b','#06b6d4','#ef4444','#ec4899','#8b5cf6','#14b8a6','#f97316','#6366f1','#84cc16'];
const fmt = (n,d=2) => Number(n).toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct = n => (Number(n)>=0?'+':'') + fmt(n) + '%';

function donut(container, items, cx, cy, outerR, innerR) {
  const total = items.reduce((s,i) => s+i.value, 0);
  if (total === 0) return;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns,'svg');
  const size = (outerR+60)*2;
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
  const cxC = size/2, cyC = size/2;

  let startAngle = -Math.PI/2;
  const tooltip = document.createElement('div');
  tooltip.className = 'tooltip';
  container.style.position = 'relative';
  container.appendChild(tooltip);

  items.forEach((item, i) => {
    const pct = item.value/total;
    const angle = pct * Math.PI * 2;
    const endAngle = startAngle + angle;
    const gap = 0.02;
    const s = startAngle + gap/2;
    const e = endAngle - gap/2;
    if (e <= s) { startAngle = endAngle; return; }

    const x1 = cxC + outerR * Math.cos(s);
    const y1 = cyC + outerR * Math.sin(s);
    const x2 = cxC + outerR * Math.cos(e);
    const y2 = cyC + outerR * Math.sin(e);
    const x3 = cxC + innerR * Math.cos(e);
    const y3 = cyC + innerR * Math.sin(e);
    const x4 = cxC + innerR * Math.cos(s);
    const y4 = cyC + innerR * Math.sin(s);
    const large = angle > Math.PI ? 1 : 0;

    const path = document.createElementNS(ns,'path');
    path.setAttribute('d', `M${x1},${y1} A${outerR},${outerR} 0 ${large},1 ${x2},${y2} L${x3},${y3} A${innerR},${innerR} 0 ${large},0 ${x4},${y4} Z`);
    path.setAttribute('fill', COLORS[i % COLORS.length]);
    path.style.cursor = 'pointer';
    path.style.transition = 'opacity 0.15s';

    path.addEventListener('mouseenter', (ev) => {
      path.style.opacity = '0.8';
      tooltip.textContent = `${item.label}: ${item.value.toFixed(1)}%`;
      tooltip.style.opacity = '1';
    });
    path.addEventListener('mousemove', (ev) => {
      const rect = container.getBoundingClientRect();
      tooltip.style.left = (ev.clientX - rect.left + 12) + 'px';
      tooltip.style.top = (ev.clientY - rect.top - 30) + 'px';
    });
    path.addEventListener('mouseleave', () => {
      path.style.opacity = '1';
      tooltip.style.opacity = '0';
    });
    svg.appendChild(path);

    // Label
    const midAngle = (s + e) / 2;
    const labelR = outerR + 20;
    const lx = cxC + labelR * Math.cos(midAngle);
    const ly = cyC + labelR * Math.sin(midAngle);
    if (pct > 0.04) {
      const text = document.createElementNS(ns,'text');
      text.setAttribute('x', lx);
      text.setAttribute('y', ly);
      text.setAttribute('fill', '#e4e6f0');
      text.setAttribute('font-size', '11');
      text.setAttribute('font-weight', '600');
      text.setAttribute('text-anchor', Math.cos(midAngle) >= 0 ? 'start' : 'end');
      text.setAttribute('dominant-baseline', 'middle');
      text.textContent = `${item.name} ${item.value.toFixed(1)}%`;
      svg.appendChild(text);
    }

    startAngle = endAngle;
  });

  // Center text
  const centerText = document.createElementNS(ns,'text');
  centerText.setAttribute('x', cxC);
  centerText.setAttribute('y', cyC);
  centerText.setAttribute('fill', '#e4e6f0');
  centerText.setAttribute('font-size', '14');
  centerText.setAttribute('font-weight', '700');
  centerText.setAttribute('text-anchor', 'middle');
  centerText.setAttribute('dominant-baseline', 'middle');
  centerText.textContent = items.length + ' positions';
  svg.appendChild(centerText);

  container.insertBefore(svg, tooltip);
}

function render() {
  const app = document.getElementById('app');
  const s = D.summary;
  const pnlCls = Number(s.total_pnl) >= 0 ? 'positive' : 'negative';
  const dateStr = new Date(D.generated_at).toLocaleDateString('de-DE', {day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});

  app.innerHTML = `
    <div class="header">
      <h1>${D.portfolio_name}</h1>
      <span class="date">${dateStr}</span>
    </div>

    <div class="kpi-grid">
      <div class="kpi"><div class="label">Portfolio Value</div><div class="value">${fmt(s.total_value)}&nbsp;€</div><div class="sub" style="color:var(--text2)">holdings ${fmt(s.holdings_value)} + cash ${fmt(s.cash_balance)}</div></div>
      <div class="kpi"><div class="label">Total Invested</div><div class="value">${fmt(s.total_cost)}&nbsp;€</div></div>
      <div class="kpi"><div class="label">Unrealized P&amp;L</div><div class="value ${pnlCls}">${fmt(s.total_pnl)}&nbsp;€</div><div class="sub ${pnlCls}">${fmtPct(s.pnl_pct)}</div></div>
      <div class="kpi"><div class="label">Cash Balance</div><div class="value">${fmt(s.cash_balance)}&nbsp;€</div><div class="sub" style="color:var(--text2)">dividends − fees</div></div>
      <div class="kpi"><div class="label">Dividends</div><div class="value">${fmt(s.total_dividends)}&nbsp;€</div><div class="sub" style="color:var(--text2)">total received</div></div>
      <div class="kpi"><div class="label">Holdings</div><div class="value">${s.holdings_count}</div></div>
    </div>

    <div class="charts-row">
      <div class="card"><h2>Allocation by Holding</h2><div id="chart-holding" class="chart-container"></div></div>
      <div class="card"><h2>Allocation by Type</h2><div id="chart-type" class="chart-container"></div></div>
    </div>

    <div class="card" style="margin-bottom:32px">
      <h2>Holdings</h2>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Ticker</th><th>Name</th><th>Type</th>
            <th class="num">Shares</th><th class="num">Cost&nbsp;€</th>
            <th class="num">Price&nbsp;€</th><th class="num">Value&nbsp;€</th>
            <th class="num">P&amp;L&nbsp;€</th><th class="num">P&amp;L&nbsp;%</th>
            <th class="num">Weight</th>
          </tr></thead>
          <tbody>
            ${D.holdings.map(h => {
              const pc = Number(h.pnl) >= 0 ? 'positive' : 'negative';
              return `<tr>
                <td style="font-weight:600">${h.ticker||'—'}</td>
                <td style="color:var(--text2);font-size:13px">${h.name||h.isin}</td>
                <td>${h.asset_type}</td>
                <td class="num">${fmt(h.shares,4)}</td>
                <td class="num">${fmt(h.cost_basis)}</td>
                <td class="num">${h.current_price?fmt(h.current_price,4):'—'}</td>
                <td class="num" style="font-weight:600">${fmt(h.current_value)}</td>
                <td class="num ${pc}">${fmt(h.pnl)}</td>
                <td class="num ${pc}">${fmtPct(h.pnl_pct)}</td>
                <td class="num">${fmt(h.weight,1)}%</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div class="charts-row">
      <div class="card">
        <h2>Target vs Actual</h2>
        <div id="deviations"></div>
      </div>
      <div class="card">
        <h2>Tax Summary (Germany)</h2>
        <div id="tax"></div>
      </div>
    </div>

    <div style="text-align:center;padding:24px 0;color:var(--text2);font-size:12px">
      Portfolio Tracker Dashboard &bull; ${dateStr}
    </div>
  `;

  // Draw donut charts
  const holdingItems = D.holdings.filter(h => h.weight > 0).map(h => ({
    name: h.ticker || h.isin.slice(0,6), label: h.name || h.isin, value: Number(h.weight)
  }));
  donut(document.getElementById('chart-holding'), holdingItems, 0, 0, 100, 60);

  const typeItems = Object.entries(D.allocation_by_type).map(([k,v]) => ({
    name: k, label: k, value: Number(v)
  }));
  donut(document.getElementById('chart-type'), typeItems, 0, 0, 90, 55);

  // Deviations
  const devEl = document.getElementById('deviations');
  const devs = D.deviations.filter(d => Number(d.target) > 0 || Number(d.current) > 0);
  if (!devs.length) {
    devEl.innerHTML = '<p style="color:var(--text2)">No targets set.</p>';
  } else {
    const maxPct = Math.max(...devs.map(d => Math.max(Number(d.current), Number(d.target))), 1);
    devEl.innerHTML = devs.map(d => {
      const badgeCls = d.needs_rebalance ? 'warn' : 'ok';
      const badgeText = d.needs_rebalance
        ? (Number(d.deviation)>0?'+':'') + fmt(d.deviation,1) + '%'
        : 'OK';
      return `<div class="dev-row">
        <div class="dev-label">${d.name}</div>
        <div class="dev-bars">
          <div class="dev-bar-wrap"><div class="dev-bar-fill" style="width:${(Number(d.current)/maxPct*100)}%;background:var(--blue)"></div></div>
          <div class="dev-bar-wrap"><div class="dev-bar-fill" style="width:${(Number(d.target)/maxPct*100)}%;background:var(--purple)"></div></div>
        </div>
        <div class="dev-pcts">
          ${fmt(d.current,1)}% / ${fmt(d.target,1)}%
          <span class="dev-badge ${badgeCls}">${badgeText}</span>
        </div>
      </div>`;
    }).join('') + `<div style="margin-top:12px;font-size:12px;color:var(--text2)">
      <span style="display:inline-block;width:10px;height:10px;background:var(--blue);border-radius:2px;margin-right:4px;vertical-align:middle"></span>Current
      <span style="display:inline-block;width:10px;height:10px;background:var(--purple);border-radius:2px;margin-left:12px;margin-right:4px;vertical-align:middle"></span>Target
    </div>`;
  }

  // Tax
  const t = D.tax;
  const taxEl = document.getElementById('tax');
  const netCls = Number(t.net_gain) >= 0 ? 'positive' : 'negative';
  taxEl.innerHTML = `<div class="tax-grid">
    <div class="tax-item"><span class="tl">Unrealized Gain</span><span class="tv">${fmt(t.gross_gain)} €</span></div>
    <div class="tax-item"><span class="tl">Freistellungsauftrag <span style="opacity:0.5;font-size:11px">(tax-free allowance)</span></span><span class="tv positive">-${fmt(t.freistellungsauftrag_used)} €</span></div>
    <div class="tax-item"><span class="tl">Taxable Gain</span><span class="tv">${fmt(t.taxable_gain)} €</span></div>
    <div class="tax-item"><span class="tl">Abgeltungssteuer 25% <span style="opacity:0.5;font-size:11px">(flat capital gains tax)</span></span><span class="tv">${fmt(t.abgeltungssteuer)} €</span></div>
    <div class="tax-item"><span class="tl">Solidaritätszuschlag 5.5% <span style="opacity:0.5;font-size:11px">(solidarity surcharge)</span></span><span class="tv">${fmt(t.soli)} €</span></div>
    <div class="tax-item"><span class="tl">Total Tax</span><span class="tv negative">${fmt(t.total_tax)} €</span></div>
    <div class="tax-item highlight"><span class="tl">Net Gain after Tax</span><span class="tv ${netCls}">${fmt(t.net_gain)} €</span></div>
  </div>`;
}

render();
</script>
</body>
</html>"""


@app.command("open")
def open_dashboard(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    output: str = typer.Option("", "--output", "-o", help="Save HTML to this path instead of temp file"),
):
    """Generate and open a web dashboard for a portfolio."""
    portfolios_repo = PortfoliosRepository()
    portfolio = portfolios_repo.get_by_id(portfolio_id)
    if not portfolio:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Collecting data for '{portfolio.name}'...[/cyan]")
    portfolio_data = _collect_data(portfolio_id)

    data_json = json.dumps(portfolio_data, default=_decimal_default, ensure_ascii=False)
    html = DASHBOARD_HTML.replace("__DATA_PLACEHOLDER__", data_json)

    if output:
        out_path = Path(output)
    else:
        out_path = Path(tempfile.gettempdir()) / "portfolio-dashboard.html"

    out_path.write_text(html, encoding="utf-8")
    console.print(f"[green]Dashboard saved to {out_path}[/green]")

    webbrowser.open(f"file://{out_path.resolve()}")
    console.print("[green]Opened in browser![/green]")
