import { useRef, useState, useEffect, useCallback } from "preact/hooks";
import { fmt } from "../../utils";

const PERIODS = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "6m", label: "6M", days: 180 },
  { key: "1y", label: "1Y", days: 365 },
  { key: "2y", label: "2Y", days: 730 },
  { key: "all", label: "All", days: null },
];

export function filterSnapsByPeriod(snaps, period) {
  const p = PERIODS.find((x) => x.key === period);
  if (!p || !p.days) return snaps;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - p.days);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  return snaps.filter((s) => s.date >= cutoffStr);
}

export function calcTwr(snaps, cashFlows) {
  if (snaps.length < 2) return null;
  const flows = cashFlows || [];
  let twr = 1;
  for (let i = 1; i < snaps.length; i++) {
    const d0 = snaps[i - 1].date, d1 = snaps[i].date;
    let net = 0;
    for (const f of flows) {
      if (f.date > d0 && f.date <= d1) net += Number(f.amount);
    }
    const denom = Number(snaps[i - 1].total_value) + net;
    if (denom <= 0) continue;
    twr *= Number(snaps[i].total_value) / denom;
  }
  return (twr - 1) * 100;
}

export function PerformanceChart({ data, period, onPeriodChange }) {
  const containerRef = useRef(null);
  const [tip, setTip] = useState(null);

  const snaps = filterSnapsByPeriod(data.snapshots || [], period);
  const twr = calcTwr(snaps, data.cash_flows);

  if (snaps.length < 2) {
    return (
      <div>
        <PeriodButtons period={period} onPeriodChange={onPeriodChange} />
        <p style="color:var(--text3);padding:32px 0;text-align:center;font-size:13px">
          No history yet — open the dashboard daily or run{" "}
          <code style="background:var(--surface2);padding:2px 8px;border-radius:6px;font-size:12px;font-family:'JetBrains Mono',monospace">
            pt snapshot take {data.portfolio_id}
          </code>{" "}
          to start tracking.
        </p>
      </div>
    );
  }

  const W = 600, H = 240;
  const PAD = { top: 16, right: 16, bottom: 36, left: 72 };
  const iW = W - PAD.left - PAD.right;
  const iH = H - PAD.top - PAD.bottom;

  const dates = snaps.map((s) => new Date(s.date).getTime());
  const minT = Math.min(...dates), maxT = Math.max(...dates);
  const allV = snaps.flatMap((s) => [Number(s.total_value), Number(s.holdings_value)]);
  const minV = Math.min(...allV) * 0.98, maxV = Math.max(...allV) * 1.02;
  const xS = (t) => ((t - minT) / (maxT - minT || 1)) * iW;
  const yS = (v) => iH - ((v - minV) / (maxV - minV || 1)) * iH;

  // Grid lines + labels
  const gridLines = [];
  for (let i = 0; i <= 4; i++) {
    const v = minV + ((maxV - minV) * i) / 4;
    const y = yS(v);
    gridLines.push({ y, label: "€" + fmt(v, 0), isAxis: i === 0 });
  }

  // Area fill points
  const areaPoints = `${xS(dates[0])},${iH} ` +
    snaps.map((s) => `${xS(new Date(s.date).getTime())},${yS(Number(s.total_value))}`).join(" ") +
    ` ${xS(dates[dates.length - 1])},${iH}`;

  // Line points
  const totalPts = snaps.map((s) => `${xS(new Date(s.date).getTime())},${yS(Number(s.total_value))}`).join(" ");
  const holdingsPts = snaps.map((s) => `${xS(new Date(s.date).getTime())},${yS(Number(s.holdings_value))}`).join(" ");

  // X axis labels
  const step = Math.max(1, Math.floor((snaps.length - 1) / 5));
  const xLabels = [];
  for (let i = 0; i < snaps.length; i += step) {
    xLabels.push({ x: xS(new Date(snaps[i].date).getTime()), label: snaps[i].date.slice(5) });
  }

  const handleDot = (e, s) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const clientX = e.clientX || e.touches?.[0]?.clientX || 0;
    const clientY = e.clientY || e.touches?.[0]?.clientY || 0;
    setTip({
      date: s.date,
      total: fmt(s.total_value),
      holdings: fmt(s.holdings_value),
      cash: fmt(s.cash_balance),
      x: clientX - rect.left + 14,
      y: clientY - rect.top - 64,
    });
  };

  return (
    <div ref={containerRef} style="position:relative">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h2 style="margin-bottom:0">Portfolio Value Over Time</h2>
        <PeriodButtons period={period} onPeriodChange={onPeriodChange} />
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} class="line-chart-svg">
        <defs>
          <linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.2" />
            <stop offset="100%" stop-color="var(--accent)" stop-opacity="0" />
          </linearGradient>
        </defs>
        <g transform={`translate(${PAD.left},${PAD.top})`}>
          {gridLines.map((g, i) => (
            <g key={i}>
              <line x1="0" x2={iW} y1={g.y} y2={g.y} class={g.isAxis ? "axis-line" : "grid-line"} />
              <text x={-8} y={g.y} class="axis-label" text-anchor="end" dominant-baseline="middle">{g.label}</text>
            </g>
          ))}
          <polygon points={areaPoints} fill="url(#area-grad)" />
          <polyline points={holdingsPts} class="line-holdings" />
          <polyline points={totalPts} class="line-total" />
          {snaps.map((s, i) => {
            const x = xS(new Date(s.date).getTime());
            const y = yS(Number(s.total_value));
            return (
              <circle
                key={i} cx={x} cy={y} r={3}
                fill="var(--accent)" stroke="var(--bg)" stroke-width="1.5"
                class="chart-dot"
                onMouseEnter={(e) => handleDot(e, s)}
                onMouseMove={(e) => handleDot(e, s)}
                onMouseLeave={() => setTip(null)}
                onClick={(e) => (tip ? setTip(null) : handleDot(e, s))}
              />
            );
          })}
          {xLabels.map((l, i) => (
            <text key={i} x={l.x} y={iH + 20} class="axis-label" text-anchor="middle">{l.label}</text>
          ))}
        </g>
      </svg>

      {tip && (
        <div class="tooltip" style={{ opacity: 1, left: tip.x + "px", top: tip.y + "px" }}>
          <strong>{tip.date}</strong><br />Total: €{tip.total}<br />Holdings: €{tip.holdings}<br />Cash: €{tip.cash}
        </div>
      )}

      <div style="display:flex;gap:16px;margin-top:12px;font-size:12px;align-items:center">
        <span style="display:flex;align-items:center;gap:4px">
          <span style="display:inline-block;width:16px;height:2px;background:var(--accent);border-radius:2px" />
          <span style="color:var(--text2)">Total</span>
        </span>
        <span style="display:flex;align-items:center;gap:4px">
          <span style="display:inline-block;width:16px;height:2px;background:var(--green);border-radius:2px;border-style:dashed" />
          <span style="color:var(--text2)">Holdings</span>
        </span>
        {twr !== null && (
          <span style={{
            marginLeft: "auto", fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
            color: `var(${twr >= 0 ? "--green" : "--red"})`,
          }}>
            TWR: {twr >= 0 ? "+" : ""}{twr.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}

function PeriodButtons({ period, onPeriodChange }) {
  return (
    <div class="period-ctrl">
      {PERIODS.map((p) => (
        <button
          key={p.key}
          class={`period-btn${p.key === period ? " active" : ""}`}
          onClick={() => onPeriodChange(p.key)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
