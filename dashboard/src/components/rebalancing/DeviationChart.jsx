import { fmt } from "../../utils";

export function DeviationChart({ deviations }) {
  const devs = deviations.filter((d) => Number(d.target) > 0 || Number(d.current) > 0);

  if (!devs.length) {
    return <p style="color:var(--text3);font-size:13px">No targets set.</p>;
  }

  const maxPct = Math.max(...devs.map((d) => Math.max(Number(d.current), Number(d.target))), 1);

  return (
    <div>
      {devs.map((d) => {
        const dev = Number(d.deviation);
        const badgeCls = !d.needs_rebalance ? "ok" : dev > 0 ? "warn" : "under";
        const badgeText = d.needs_rebalance ? (dev > 0 ? "+" : "") + fmt(d.deviation, 1) + "%" : "OK";

        return (
          <div key={d.key} class="dev-row">
            <div class="dev-label">{d.name}</div>
            <div class="dev-bars">
              <div class="dev-bar-wrap">
                <div class="dev-bar-fill" style={{ width: (Number(d.current) / maxPct) * 100 + "%", background: "var(--accent)" }} />
              </div>
              <div class="dev-bar-wrap">
                <div class="dev-bar-fill" style={{ width: (Number(d.target) / maxPct) * 100 + "%", background: "var(--purple)" }} />
              </div>
            </div>
            <div class="dev-pcts">
              {fmt(d.current, 1)}% / {fmt(d.target, 1)}%
              <span class={`dev-badge ${badgeCls}`}>{badgeText}</span>
            </div>
          </div>
        );
      })}
      <div style="margin-top:14px;font-size:12px;color:var(--text3);display:flex;gap:20px">
        <span style="display:flex;align-items:center;gap:6px">
          <span style="display:inline-block;width:12px;height:4px;background:var(--accent);border-radius:2px" />
          Current
        </span>
        <span style="display:flex;align-items:center;gap:6px">
          <span style="display:inline-block;width:12px;height:4px;background:var(--purple);border-radius:2px" />
          Target
        </span>
      </div>
    </div>
  );
}
