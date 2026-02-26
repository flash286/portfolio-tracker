import { useState, useCallback } from "preact/hooks";
import { useMarkdownExport } from "../hooks/useMarkdownExport";

export function Header({ data }) {
  const { copyMarkdown } = useMarkdownExport(data);
  const [copyState, setCopyState] = useState(null);

  const handleCopy = useCallback(() => {
    copyMarkdown();
    setCopyState("copied");
    setTimeout(() => setCopyState(null), 2000);
  }, [copyMarkdown]);

  const dateStr = new Date(data.generated_at).toLocaleDateString("de-DE", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });

  // Stale prices warning
  let staleEl = null;
  if (data.prices_oldest_at) {
    const hoursAgo = (Date.now() - new Date(data.prices_oldest_at).getTime()) / 3600000;
    if (hoursAgo > 24) {
      const days = Math.floor(hoursAgo / 24);
      const label = days === 1 ? "1 day ago" : days + " days ago";
      staleEl = (
        <span class="stale-warn">
          ⚠ Prices {label} — run <code style="font-family:'JetBrains Mono',monospace;font-size:11px">pt prices fetch {data.portfolio_id}</code>
        </span>
      );
    }
  } else if (data.summary.holdings_count > 0) {
    staleEl = (
      <span class="stale-warn">
        ⚠ No prices — run <code style="font-family:'JetBrains Mono',monospace;font-size:11px">pt prices fetch {data.portfolio_id}</code>
      </span>
    );
  }

  return (
    <div class="header animate-in" style="--delay:0ms">
      <h1>{data.portfolio_name}</h1>
      <div class="header-right">
        {staleEl}
        <span class="date">{dateStr}</span>
        <button
          class="btn-ghost"
          onClick={handleCopy}
          style={copyState ? { color: "var(--green)", borderColor: "rgba(52,211,153,0.3)" } : {}}
        >
          {copyState ? "✓ Copied!" : "⌘ Copy as Markdown"}
        </button>
      </div>
    </div>
  );
}
