import { fmt } from "../../utils";

export function FsaBar({ tax, freistellungsauftrag }) {
  const used = Number(tax.freistellungsauftrag_used);
  const total = Number(freistellungsauftrag) || 1000;
  const pct = Math.min((used / total) * 100, 100);
  const color = pct < 70 ? "var(--green)" : pct < 95 ? "var(--amber)" : "var(--red)";

  return (
    <div>
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:10px;align-items:baseline">
        <span style="color:var(--text2)">
          Used: <strong class="mono" style="color:var(--text);font-size:15px">{fmt(used)} €</strong>
        </span>
        <span style="color:var(--text3);font-size:12px">of {fmt(total)} €</span>
      </div>
      <div class="fsa-bar-wrap" style="position:relative">
        <div class="fsa-bar-fill" style={{ width: pct + "%", background: color }}>
          {pct > 20 && <span class="fsa-pct-label">{pct.toFixed(0)}%</span>}
        </div>
      </div>
      <div style="font-size:12px;color:var(--text3);margin-top:8px" class="mono">
        {fmt(total - used)} € remaining
      </div>
    </div>
  );
}
