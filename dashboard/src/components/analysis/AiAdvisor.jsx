import { useState, useRef, useCallback } from "preact/hooks";
import { getStream } from "./AiStreaming";
import { Prose } from "./MarkdownRenderer";
import { useMarkdownExport } from "../../hooks/useMarkdownExport";

const AI_SCENARIOS = [
  {
    label: "Analyze Portfolio", desc: "health · risk · actions", color: "#818cf8",
    svg: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="1" y="8" width="3" height="7" rx="0.5"/><rect x="6.5" y="4" width="3" height="11" rx="0.5"/><rect x="12" y="1" width="3" height="14" rx="0.5"/></svg>',
    prompt: "Provide a comprehensive portfolio analysis: overall health assessment, performance highlights (best and worst performers with context), risk and diversification evaluation, and 3\u20135 specific actionable recommendations with euro amounts where relevant.",
  },
  {
    label: "Tax Optimization", desc: "FSA · TFS · harvesting", color: "#34d399",
    svg: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1v14"/><path d="M4.5 4C4.5 2.9 6 2 8 2s3.5.9 3.5 2-1.5 2-3.5 2-3.5.9-3.5 2 1.5 2 3.5 2 3.5.9 3.5 2-1.5 2-3.5 2-3.5-.9-3.5-2"/></svg>',
    prompt: "Analyze my tax optimization opportunities for this year. Consider:\n- Current Freistellungsauftrag usage and remaining allowance\n- Teilfreistellung rates on my ETFs\n- Tax-loss harvesting opportunities (any holdings with unrealized losses)\n- Vorabpauschale impact\n- Specific actions I should take before year-end, with exact euro amounts.",
  },
  {
    label: "Invest €500", desc: "allocate · rebalance", color: "#22d3ee",
    svg: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12l4-4 3 3 5-6"/><path d="M10 5h4v4"/></svg>',
    prompt: "I have €500 to invest right now. Given my current allocation, target weights, and rebalancing needs, what exactly should I buy? Show:\n- Specific ticker(s) and number of shares\n- Cost at current prices\n- How this changes my allocation percentages\n- Tax implications of this purchase\nOptimize for getting closer to my target allocation.",
  },
  {
    label: "Crash −20%", desc: "stress test · impact", color: "#f87171",
    svg: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3l4 5-3 4.5"/><path d="M7 5l4 5-3 4.5"/><path d="M14 2v4h-4"/></svg>',
    prompt: "Model a scenario where all equity positions drop 20% (bonds drop 5%). For each holding, show:\n- Current value → projected value\n- New unrealized P&L\n- New portfolio allocation weights\nThen analyze: total portfolio impact, any tax-loss harvesting opportunities that would arise, and whether I should change my strategy.",
  },
  {
    label: "vs Benchmark", desc: "VWCE comparison", color: "#a78bfa",
    svg: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6.5"/><circle cx="8" cy="8" r="3"/><circle cx="8" cy="8" r="0.5" fill="currentColor"/></svg>',
    prompt: "Compare my portfolio to a simple MSCI World (VWCE) single-ETF approach. Analyze:\n- Expected return differences (equity vs bond allocation drag)\n- Fee comparison (TER of my ETFs vs VWCE)\n- Diversification: what am I gaining from multiple positions?\n- Tax efficiency: Teilfreistellung impact across my mix\n- Honest assessment: is my multi-ETF approach worth the complexity?",
  },
];

function getSystemPrompt(fsa) {
  return `You are a financial advisor for a German tax-resident ETF investor.

German tax rules:
- Abgeltungssteuer: 25% flat tax on capital gains
- Solidaritätszuschlag: 5.5% surcharge on the Abgeltungssteuer
- Teilfreistellung (partial exemption): equity ETF = 30%, mixed fund = 15%, bond/other = 0%
- Freistellungsauftrag (annual tax-free allowance): EUR ${fsa}
- Vorabpauschale: annual prepayment tax on accumulating ETFs based on Basiszins

Respond in clear, well-structured markdown. Use ## headings to organize sections, **bold** for key figures, bullet lists for findings, and | tables | for comparisons where helpful. Be specific — always reference actual ticker names, share counts, and euro amounts from the portfolio data. When suggesting trades, calculate exact quantities and costs at current prices. Keep it concise but thorough.`;
}

export function AiAdvisor({ data }) {
  const [activeIdx, setActiveIdx] = useState(null);
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clipboardMsg, setClipboardMsg] = useState(null);
  const abortRef = useRef(null);
  const { generateMarkdown } = useMarkdownExport(data);

  const ai = data.ai || {};
  const hasKey = ai.provider && ai.api_key;

  const runAnalysis = useCallback(
    async (idx) => {
      const scenario = AI_SCENARIOS[idx];
      const system = getSystemPrompt(data.freistellungsauftrag);
      const userMsg = generateMarkdown() + "\n\n---\n\nTask: " + scenario.prompt;

      setActiveIdx(idx);
      setError(null);

      // No API key — clipboard flow
      if (!hasKey) {
        const fullPrompt = system + "\n\n---\n\n" + userMsg;
        let copied = false;
        try {
          await navigator.clipboard.writeText(fullPrompt);
          copied = true;
        } catch {}
        setClipboardMsg({ label: scenario.label, copied });
        window._aiPromptCache = fullPrompt;
        return;
      }

      // Streaming flow
      setClipboardMsg(null);
      setOutput("");
      setLoading(true);

      try {
        const stream = getStream(ai, system, userMsg);
        let fullText = "";
        for await (const chunk of stream) {
          fullText += chunk;
          setOutput(fullText);
        }
        if (!fullText.trim()) {
          setError("Empty response from provider.");
        }
      } catch (err) {
        setError(err.message);
      }

      setLoading(false);
    },
    [data, ai, hasKey, generateMarkdown],
  );

  const copyPrompt = useCallback(() => {
    const p = window._aiPromptCache || "";
    const fallback = () => {
      const ta = document.createElement("textarea");
      ta.value = p;
      ta.style.cssText = "position:fixed;left:-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(p).catch(fallback);
    } else {
      fallback();
    }
    setClipboardMsg((prev) => prev && { ...prev, copied: true });
  }, []);

  return (
    <div class="card" style="margin-bottom:28px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px">
        <h2 style="margin-bottom:0">AI Advisor</h2>
        <span style="font-size:12px;color:var(--text3)">
          {hasKey
            ? ai.provider + (ai.model ? " · " + ai.model : "")
            : <>No provider — run <code style="background:var(--surface2);padding:1px 6px;border-radius:6px;font-size:11px;font-family:'JetBrains Mono',monospace">pt setup run</code> to configure</>}
        </span>
      </div>

      <div class="ai-chips">
        {AI_SCENARIOS.map((s, i) => (
          <button
            key={i}
            class={`ai-chip${activeIdx === i ? " active" : ""}`}
            style={{ "--chip-color": s.color }}
            disabled={loading}
            onClick={() => runAnalysis(i)}
          >
            <span class="ai-chip-icon" style={{ color: s.color }} dangerouslySetInnerHTML={{ __html: s.svg }} />
            <span class="ai-chip-label">{s.label}</span>
            <span class="ai-chip-desc">{s.desc}</span>
          </button>
        ))}
      </div>

      <div class="ai-output">
        {clipboardMsg && (
          <div class="ai-clipboard-flow">
            <div class="ai-clipboard-success">
              <span class="ai-clipboard-icon">{clipboardMsg.copied ? "✓" : "ℹ"}</span>
              <span>
                <strong>{clipboardMsg.label}</strong>{" "}
                {clipboardMsg.copied ? "prompt copied to clipboard" : "prompt ready"}
              </span>
            </div>
            <p class="ai-clipboard-hint">Open your AI assistant and paste:</p>
            <div class="ai-open-buttons">
              <button class="ai-open-btn ai-open-claude" onClick={() => window.open("https://claude.ai/new", "_blank")}>Claude</button>
              <button class="ai-open-btn ai-open-chatgpt" onClick={() => window.open("https://chatgpt.com/", "_blank")}>ChatGPT</button>
              <button class="ai-open-btn ai-open-gemini" onClick={() => window.open("https://gemini.google.com/app", "_blank")}>Gemini</button>
            </div>
            <p class="ai-clipboard-alt">
              <button class="ai-copy-btn" onClick={copyPrompt}>Copy prompt</button>
              <span>or add an API key for in-dashboard streaming: <code>pt setup run</code></span>
            </p>
          </div>
        )}

        {loading && (
          <div class="ai-loading">
            <span class="ai-spinner" /> Generating {AI_SCENARIOS[activeIdx]?.label.toLowerCase()}…
          </div>
        )}

        {output && <Prose markdown={output} />}

        {error && (
          <div class="ai-error" style={output ? "margin-top:16px" : ""}>
            <strong>Error:</strong> {error}
          </div>
        )}
      </div>
    </div>
  );
}
