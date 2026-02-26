import { fmt } from "../../utils";

export function TaxSummary({ tax, freistellungsauftrag }) {
  const t = tax;
  const netCls = Number(t.net_gain) >= 0 ? "positive" : "negative";
  const fsaTotal = freistellungsauftrag || 1000;
  const fsaUsedVP = (t.vp_entries || []).reduce((s, v) => s + Number(v.fsa_used), 0);
  const fsaRemaining = fsaTotal - fsaUsedVP;

  const rows = [
    { label: "Unrealized Gain", sublabel: "(hypothetical)", value: fmt(t.gross_gain) + " €" },
  ];

  if (Number(t.tfs_exempt) > 0) {
    rows.push({
      label: `Teilfreistellung ~${fmt(t.tfs_rate_pct, 1)}%`,
      sublabel: "(partial exemption)",
      value: `-${fmt(t.tfs_exempt)} €`,
      valueCls: "positive",
    });
  }

  for (const vp of t.vp_entries || []) {
    rows.push({
      label: `Vorabpauschale ${vp.year}`,
      sublabel: "(prepayment tax)",
      value: `−${fmt(vp.fsa_used)} € FSA`,
      valueStyle: { color: "var(--amber)" },
    });
  }

  rows.push(
    {
      label: "Freistellungsauftrag",
      sublabel: "(tax-free allowance)",
      value: `-${fmt(fsaRemaining > 0 ? Math.min(Number(t.taxable_gain), fsaRemaining) : 0)} €`,
      valueCls: "positive",
    },
    { label: "Taxable Gain", value: fmt(t.taxable_gain) + " €" },
    {
      label: "Abgeltungssteuer 25%",
      sublabel: "(flat capital gains tax)",
      value: fmt(t.abgeltungssteuer) + " €",
    },
    {
      label: "Solidaritätszuschlag 5.5%",
      sublabel: "(solidarity surcharge)",
      value: fmt(t.soli) + " €",
    },
    { label: "Total Tax", value: fmt(t.total_tax) + " €", valueCls: "negative" },
  );

  return (
    <div class="tax-grid">
      {rows.map((r, i) => (
        <div key={i} class="tax-item">
          <span class="tl">
            {r.label}
            {r.sublabel && <span style="opacity:0.4;font-size:11px"> {r.sublabel}</span>}
          </span>
          <span class={`tv${r.valueCls ? " " + r.valueCls : ""}`} style={r.valueStyle}>
            {r.value}
          </span>
        </div>
      ))}
      <div class="tax-item highlight">
        <span class="tl">Net Gain after Tax</span>
        <span class={`tv ${netCls}`}>{fmt(t.net_gain)} €</span>
      </div>
    </div>
  );
}
