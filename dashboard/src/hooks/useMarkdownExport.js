import { useCallback } from "preact/hooks";
import { fmt } from "../utils";

export function useMarkdownExport(data) {
  const generateMarkdown = useCallback(() => {
    const D = data;
    const s = D.summary;
    const t = D.tax;
    const r = D.realized;
    const dateStr = new Date(D.generated_at).toLocaleDateString("de-DE", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
    const fmtN = (n, d = 2) => Number(n).toFixed(d);
    const sign = (n) => (Number(n) >= 0 ? "+" : "");
    const lines = [];

    lines.push(`# Portfolio: ${D.portfolio_name}`);
    lines.push(`Generated: ${dateStr}\n`);

    lines.push("## Summary\n");
    lines.push("| Metric | Value |");
    lines.push("|--------|-------|");
    lines.push(`| Total Value | €${fmtN(s.total_value)} |`);
    lines.push(`| Holdings Value | €${fmtN(s.holdings_value)} |`);
    lines.push(`| Cash Balance | €${fmtN(s.cash_balance)} |`);
    lines.push(`| Total Invested | €${fmtN(s.total_cost)} |`);
    lines.push(`| Unrealized P&L | €${fmtN(s.total_pnl)} (${sign(s.pnl_pct)}${fmtN(s.pnl_pct)}%) |`);
    lines.push(`| Dividends Received | €${fmtN(s.total_dividends)} |`);
    lines.push(`| Holdings Count | ${s.holdings_count} |`);
    lines.push("");

    lines.push("## Holdings\n");
    lines.push("| Ticker | Name | Type | TFS% | Shares | Cost € | Price € | Value € | P&L € | P&L % | Weight |");
    lines.push("|--------|------|------|------|-------:|-------:|--------:|--------:|------:|------:|-------:|");
    for (const h of D.holdings) {
      const tfs = h.tfs_rate > 0 ? (h.tfs_rate * 100).toFixed(0) + "%" : "—";
      const price = h.current_price ? fmtN(h.current_price, 4) : "—";
      lines.push(`| ${h.ticker || "—"} | ${h.name || h.isin} | ${h.asset_type} | ${tfs} | ${fmtN(h.shares, 4)} | ${fmtN(h.cost_basis)} | ${price} | ${fmtN(h.current_value)} | ${sign(h.pnl)}${fmtN(h.pnl)} | ${sign(h.pnl_pct)}${fmtN(h.pnl_pct)}% | ${fmtN(h.weight, 1)}% |`);
    }
    lines.push("");

    lines.push("## Tax Estimate (Germany, hypothetical)\n");
    lines.push("| Item | Amount |");
    lines.push("|------|-------:|");
    lines.push(`| Unrealized Gain | €${fmtN(t.gross_gain)} |`);
    if (Number(t.tfs_exempt) > 0) {
      lines.push(`| Teilfreistellung ~${fmtN(t.tfs_rate_pct, 1)}% (partial exemption) | −€${fmtN(t.tfs_exempt)} |`);
    }
    lines.push(`| Freistellungsauftrag used | −€${fmtN(t.freistellungsauftrag_used)} |`);
    lines.push(`| Taxable Gain | €${fmtN(t.taxable_gain)} |`);
    lines.push(`| Abgeltungssteuer 25% | €${fmtN(t.abgeltungssteuer)} |`);
    lines.push(`| Solidaritätszuschlag 5.5% | €${fmtN(t.soli)} |`);
    lines.push(`| **Total Tax** | **€${fmtN(t.total_tax)}** |`);
    lines.push(`| **Net Gain after Tax** | **€${fmtN(t.net_gain)}** |`);
    lines.push("");

    const devs = D.deviations.filter((d) => Number(d.target) > 0 || Number(d.current) > 0);
    if (devs.length) {
      lines.push("## Target vs Actual Allocation\n");
      lines.push("| Asset | Current | Target | Deviation | Status |");
      lines.push("|-------|--------:|-------:|----------:|--------|");
      for (const d of devs) {
        const dev = Number(d.deviation);
        const status = !d.needs_rebalance ? "✅ OK" : dev > 0 ? "🔴 Overweight" : "🔵 Underweight";
        const devStr = (dev > 0 ? "+" : "") + fmtN(d.deviation, 1) + "%";
        lines.push(`| ${d.name} | ${fmtN(d.current, 1)}% | ${fmtN(d.target, 1)}% | ${devStr} | ${status} |`);
      }
      lines.push("");
    }

    if (r.sell_count > 0) {
      lines.push(`## Realized Gains (${r.year})\n`);
      lines.push("| Item | Amount |");
      lines.push("|------|-------:|");
      lines.push(`| Total Realized Gain | €${fmtN(r.total_gain)} |`);
      lines.push(`| TFS Exempt | −€${fmtN(r.tfs_exempt)} |`);
      lines.push(`| Taxable | €${fmtN(r.taxable)} |`);
      lines.push(`| Freistellungsauftrag used | −€${fmtN(r.fsa_used)} |`);
      lines.push(`| Est. Total Tax | €${fmtN(r.total_tax)} |`);
      lines.push(`| **Net Gain** | **€${fmtN(r.net_gain)}** |`);
      lines.push("");
      lines.push("| Date | Ticker | Qty | Sell Price € | Realized Gain € | TFS% | Taxable € |");
      lines.push("|------|--------|----:|-------------:|----------------:|-----:|----------:|");
      for (const sell of r.sells) {
        const taxable = sell.realized_gain > 0 ? sell.realized_gain * (1 - sell.tfs_rate) : sell.realized_gain;
        const tfs = sell.tfs_rate > 0 ? (sell.tfs_rate * 100).toFixed(0) + "%" : "—";
        lines.push(`| ${sell.date} | ${sell.ticker} | ${fmtN(sell.quantity, 4)} | ${fmtN(sell.price, 4)} | ${sign(sell.realized_gain)}${fmtN(sell.realized_gain)} | ${tfs} | ${sign(taxable)}${fmtN(taxable)} |`);
      }
      lines.push("");
    }

    return lines.join("\n");
  }, [data]);

  const copyMarkdown = useCallback(() => {
    const md = generateMarkdown();
    navigator.clipboard.writeText(md).catch(() => {});
  }, [generateMarkdown]);

  return { generateMarkdown, copyMarkdown };
}
