import { fmt, fmtPct } from "../utils";

export function KpiGrid({ summary }) {
  const pnlVal = Number(summary.total_pnl);
  const pnlCls = pnlVal >= 0 ? "positive" : "negative";
  const pnlBg = pnlVal >= 0 ? "kpi-pnl-positive" : "kpi-pnl-negative";
  const glow = pnlVal >= 0 ? "var(--green)" : "var(--red)";

  return (
    <div class="kpi-grid">
      <div class="kpi kpi-hero animate-in" style="--delay:50ms">
        <div class="hero-glow" style={{ background: glow }} />
        <div class="label">Portfolio Value</div>
        <div class="value">{fmt(summary.total_value)}&nbsp;€</div>
        <div class="sub">holdings {fmt(summary.holdings_value)} + cash {fmt(summary.cash_balance)}</div>
      </div>
      <div class="kpi animate-in" style="--delay:100ms">
        <div class="label">Total Invested</div>
        <div class="value">{fmt(summary.total_cost)}&nbsp;€</div>
      </div>
      <div class={`kpi ${pnlBg} animate-in`} style="--delay:150ms">
        <div class="label">Unrealized P&amp;L</div>
        <div class={`value ${pnlCls}`}>{fmt(summary.total_pnl)}&nbsp;€</div>
        <div class={`sub ${pnlCls}`}>{fmtPct(summary.pnl_pct)}</div>
      </div>
      <div class="kpi animate-in" style="--delay:200ms">
        <div class="label">Cash Balance</div>
        <div class="value">{fmt(summary.cash_balance)}&nbsp;€</div>
      </div>
    </div>
  );
}
