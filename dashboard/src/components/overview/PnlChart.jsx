import { fmtPct } from "../../utils";

export function PnlChart({ holdings }) {
  const items = [...holdings].sort((a, b) => Number(b.pnl_pct) - Number(a.pnl_pct));
  const maxAbs = Math.max(...items.map((h) => Math.abs(Number(h.pnl_pct))), 0.01);
  const hasPos = items.some((h) => Number(h.pnl_pct) >= 0);
  const hasNeg = items.some((h) => Number(h.pnl_pct) < 0);
  const bidir = hasPos && hasNeg;

  return (
    <div>
      {items.map((h) => {
        const pct = Number(h.pnl_pct);
        const w = (Math.abs(pct) / maxAbs) * 100;
        const valCls = pct >= 0 ? "positive" : "negative";
        const ticker = h.ticker || h.isin?.slice(0, 6) || "?";

        if (!bidir) {
          const gradient = pct >= 0
            ? "linear-gradient(90deg, var(--green), rgba(52,211,153,0.4))"
            : "linear-gradient(90deg, var(--red), rgba(248,113,113,0.4))";
          return (
            <div key={h.id} class="pnl-row">
              <div class="pnl-label">{ticker}</div>
              <div class="pnl-bar-bg">
                <div style={{ width: w + "%", height: "100%", background: gradient, borderRadius: "4px", transition: "width .5s cubic-bezier(.4,0,.2,1)" }} />
              </div>
              <div class={`pnl-val ${valCls}`}>{fmtPct(pct)}</div>
            </div>
          );
        }

        if (pct >= 0) {
          return (
            <div key={h.id} class="pnl-row">
              <div class="pnl-label">{ticker}</div>
              <div class="pnl-bar-center" style="background:var(--surface2);border-radius:4px;overflow:hidden">
                <div class="pnl-bar-left" style="background:transparent" />
                <div class="pnl-bar-divider" />
                <div class="pnl-bar-right"><div class="pnl-fill-pos" style={{ width: w + "%" }} /></div>
              </div>
              <div class={`pnl-val ${valCls}`}>{fmtPct(pct)}</div>
            </div>
          );
        }

        return (
          <div key={h.id} class="pnl-row">
            <div class="pnl-label">{ticker}</div>
            <div class="pnl-bar-center" style="background:var(--surface2);border-radius:4px;overflow:hidden">
              <div class="pnl-bar-left"><div class="pnl-fill-neg" style={{ width: w + "%" }} /></div>
              <div class="pnl-bar-divider" />
              <div class="pnl-bar-right" style="background:transparent" />
            </div>
            <div class={`pnl-val ${valCls}`}>{fmtPct(pct)}</div>
          </div>
        );
      })}
    </div>
  );
}
