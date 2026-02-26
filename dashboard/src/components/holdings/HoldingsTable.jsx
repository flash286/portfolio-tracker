import { useState, useMemo, useCallback } from "preact/hooks";
import { fmt, fmtPct } from "../../utils";

const COL_KEYS = [
  "ticker", "name", "asset_type", "tfs_rate", "shares",
  "cost_basis", "current_price", "current_value", "pnl", "pnl_pct", "weight",
];

export function HoldingsTable({ holdings }) {
  const [sort, setSort] = useState({ col: 7, asc: false });
  const [filter, setFilter] = useState("");

  const sorted = useMemo(() => {
    const key = COL_KEYS[sort.col];
    const isStr = sort.col <= 2;
    return [...holdings].sort((a, b) => {
      let va = a[key], vb = b[key];
      if (isStr) {
        va = String(va || "").toLowerCase();
        vb = String(vb || "").toLowerCase();
      } else {
        va = Number(va || 0);
        vb = Number(vb || 0);
      }
      return sort.asc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
  }, [holdings, sort]);

  const filtered = useMemo(() => {
    if (!filter) return sorted;
    const q = filter.toLowerCase();
    return sorted.filter(
      (h) =>
        (h.ticker || "").toLowerCase().includes(q) ||
        (h.name || h.isin || "").toLowerCase().includes(q),
    );
  }, [sorted, filter]);

  const handleSort = useCallback(
    (col) => {
      setSort((prev) => ({
        col,
        asc: prev.col === col ? !prev.asc : col <= 2,
      }));
    },
    [],
  );

  const arrow = (col) => {
    if (sort.col !== col) return "";
    return sort.asc ? "▲" : "▼";
  };

  const headers = [
    { label: "Ticker", type: "str" },
    { label: "Name", type: "str" },
    { label: "Type", type: "str" },
    { label: "TFS%", type: "num", cls: "num" },
    { label: "Shares", type: "num", cls: "num" },
    { label: "Cost\u00a0€", type: "num", cls: "num" },
    { label: "Price\u00a0€", type: "num", cls: "num" },
    { label: "Value\u00a0€", type: "num", cls: "num" },
    { label: "P&L\u00a0€", type: "num", cls: "num" },
    { label: "P&L\u00a0%", type: "num", cls: "num" },
    { label: "Weight", type: "num", cls: "num" },
  ];

  return (
    <div class="card" style="margin-bottom:28px">
      <h2>Holdings</h2>
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px">
        <input
          type="text"
          class="filter-input"
          placeholder="Filter by ticker or name…"
          value={filter}
          onInput={(e) => setFilter(e.target.value)}
        />
        <span style="color:var(--text3);font-size:12px;font-family:'JetBrains Mono',monospace">
          {filter ? `${filtered.length} of ${holdings.length} holdings` : `${holdings.length} holdings`}
        </span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i} class={`sortable-th${h.cls ? " " + h.cls : ""}`} onClick={() => handleSort(i)}>
                  {h.label} <span class="sort-arrow">{arrow(i)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((h) => {
              const pc = Number(h.pnl) >= 0 ? "positive" : "negative";
              const tfs = h.tfs_rate > 0 ? <span class="tfs-badge">{(h.tfs_rate * 100).toFixed(0)}%</span> : "—";
              return (
                <tr key={h.id}>
                  <td style="font-weight:600;color:var(--text)">{h.ticker || "—"}</td>
                  <td style="color:var(--text2);font-size:13px">{h.name || h.isin}</td>
                  <td><span style="color:var(--text3);font-size:12px;text-transform:uppercase;letter-spacing:0.3px">{h.asset_type}</span></td>
                  <td class="num">{tfs}</td>
                  <td class="num">{fmt(h.shares, 4)}</td>
                  <td class="num">{fmt(h.cost_basis)}</td>
                  <td class="num">{h.current_price ? fmt(h.current_price, 4) : "—"}</td>
                  <td class="num" style="font-weight:600;color:var(--text)">{fmt(h.current_value)}</td>
                  <td class={`num ${pc}`}>{fmt(h.pnl)}</td>
                  <td class={`num ${pc}`}>{fmtPct(h.pnl_pct)}</td>
                  <td class="num">{fmt(h.weight, 1)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
