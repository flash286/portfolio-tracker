export const COLORS = [
  "#818cf8", "#34d399", "#fbbf24", "#f87171", "#60a5fa", "#a78bfa",
  "#22d3ee", "#ec4899", "#f97316", "#84cc16", "#6366f1", "#14b8a6",
];

export const fmt = (n, d = 2) =>
  Number(n).toLocaleString("de-DE", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });

export const fmtPct = (n) =>
  (Number(n) >= 0 ? "+" : "") + fmt(n) + "%";

export const fmtEur = (n, d = 2) => fmt(n, d) + "\u00a0\u20AC";

export const cls = (...args) => args.filter(Boolean).join(" ");
