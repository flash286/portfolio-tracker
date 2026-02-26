import { fmt, fmtPct } from "../utils";

export function KpiRow2({ summary, twr, periodLabel }) {
  const hasTwr = twr !== null;
  const gridStyle = !hasTwr ? { gridTemplateColumns: "repeat(2, 1fr)" } : {};

  return (
    <div class="kpi-row2" style={gridStyle}>
      <div class="kpi kpi-accent animate-in" style="--delay:250ms;--kpi-color:var(--green)">
        <div class="label">Dividends</div>
        <div class="value">{fmt(summary.total_dividends)}&nbsp;€</div>
        <div class="sub">total received</div>
      </div>
      <div class="kpi kpi-accent animate-in" style="--delay:300ms;--kpi-color:var(--accent)">
        <div class="label">Holdings</div>
        <div class="value">{summary.holdings_count}</div>
        <div class="sub">positions</div>
      </div>
      {hasTwr && (
        <div class="kpi kpi-accent animate-in" style="--delay:350ms;--kpi-color:var(--purple)">
          <div class="label">TWR ({periodLabel})</div>
          <div class={`value ${twr >= 0 ? "positive" : "negative"}`}>{fmtPct(twr)}</div>
          <div class="sub">time-weighted return</div>
        </div>
      )}
    </div>
  );
}
