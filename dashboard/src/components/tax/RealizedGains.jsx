import { fmt } from "../../utils";

export function RealizedGains({ realized }) {
  const r = realized;
  if (!r || r.sell_count === 0) return null;

  const gainCls = (n) => (Number(n) >= 0 ? "positive" : "negative");

  const kpis = [
    { label: "Total Gain", value: fmt(r.total_gain) + " €", cls: gainCls(r.total_gain) },
    { label: "TFS Exempt", value: `-${fmt(r.tfs_exempt)} €`, cls: "positive" },
    { label: "Taxable", value: fmt(r.taxable) + " €", cls: "" },
    { label: "Est. Tax", value: fmt(r.total_tax) + " €", cls: "negative" },
    { label: "Net Gain", value: fmt(r.net_gain) + " €", cls: gainCls(r.net_gain) },
  ];

  return (
    <div class="card" style="margin-bottom:28px">
      <h2>Realized Gains ({r.year})</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px">
        {kpis.map((k, i) => (
          <div key={i} class="kpi" style="padding:16px">
            <div class="label">{k.label}</div>
            <div class={`value ${k.cls}`} style="font-size:18px">{k.value}</div>
          </div>
        ))}
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Ticker</th>
              <th class="num">Qty</th><th class="num">Sell Price&nbsp;€</th>
              <th class="num">Realized Gain&nbsp;€</th><th class="num">TFS%</th>
              <th class="num">Taxable&nbsp;€</th>
            </tr>
          </thead>
          <tbody>
            {r.sells.map((s, i) => {
              const taxable = s.realized_gain > 0 ? s.realized_gain * (1 - s.tfs_rate) : s.realized_gain;
              return (
                <tr key={i}>
                  <td style="color:var(--text3);font-size:13px">{s.date}</td>
                  <td style="font-weight:600">{s.ticker}</td>
                  <td class="num">{fmt(s.quantity, 4)}</td>
                  <td class="num">{fmt(s.price, 4)}</td>
                  <td class={`num ${gainCls(s.realized_gain)}`}>{fmt(s.realized_gain)}</td>
                  <td class="num">{s.tfs_rate > 0 ? <span class="tfs-badge">{(s.tfs_rate * 100).toFixed(0)}%</span> : "—"}</td>
                  <td class={`num ${gainCls(taxable)}`}>{fmt(taxable)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
