import { useState, useCallback } from "preact/hooks";
import { Header } from "./components/Header";
import { KpiGrid } from "./components/KpiGrid";
import { KpiRow2 } from "./components/KpiRow2";
import { TabNav } from "./components/TabNav";
import { DonutChart } from "./components/overview/DonutChart";
import { PnlChart } from "./components/overview/PnlChart";
import { PerformanceChart, filterSnapsByPeriod, calcTwr } from "./components/overview/PerformanceChart";
import { HoldingsTable } from "./components/holdings/HoldingsTable";
import { FsaBar } from "./components/tax/FsaBar";
import { TaxSummary } from "./components/tax/TaxSummary";
import { RealizedGains } from "./components/tax/RealizedGains";
import { DeviationChart } from "./components/rebalancing/DeviationChart";
import { AiAdvisor } from "./components/analysis/AiAdvisor";

const PERIOD_LABELS = { "1m": "1M", "3m": "3M", "6m": "6M", "1y": "1Y", "2y": "2Y", all: "All" };

export function App({ data }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [period, setPeriod] = useState("1y");

  const dateStr = new Date(data.generated_at).toLocaleDateString("de-DE", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });

  // TWR calculation for KPI row
  const snaps = filterSnapsByPeriod(data.snapshots || [], period);
  const twr = calcTwr(snaps, data.cash_flows);

  // Donut chart data
  const holdingItems = data.holdings
    .filter((h) => h.weight > 0)
    .map((h) => ({ name: h.ticker || h.isin?.slice(0, 6), label: h.name || h.isin, value: Number(h.weight) }));

  const typeItems = Object.entries(data.allocation_by_type).map(([k, v]) => ({
    name: k, label: k, value: Number(v),
  }));

  const hasRealized = data.realized?.sell_count > 0;

  return (
    <div class="container">
      <Header data={data} />
      <KpiGrid summary={data.summary} />
      <KpiRow2 summary={data.summary} twr={twr} periodLabel={PERIOD_LABELS[period]} />
      <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Overview */}
      <div id="tab-overview" class={`tab-panel${activeTab === "overview" ? " active" : ""}`} role="tabpanel">
        <div class="charts-row animate-in" style="--delay:450ms">
          <div class="card">
            <h2>Allocation by Holding</h2>
            <DonutChart items={holdingItems} id="holding" />
          </div>
          <div class="card">
            <h2>Allocation by Type</h2>
            <DonutChart items={typeItems} id="type" />
          </div>
        </div>
        <div class="card animate-in" style="--delay:500ms;margin-bottom:28px">
          <h2>P&amp;L by Holding</h2>
          <PnlChart holdings={data.holdings} />
        </div>
        <div class="card animate-in" style="--delay:550ms;margin-bottom:28px">
          <PerformanceChart data={data} period={period} onPeriodChange={setPeriod} />
        </div>
      </div>

      {/* Holdings */}
      <div id="tab-holdings" class={`tab-panel${activeTab === "holdings" ? " active" : ""}`} role="tabpanel">
        <HoldingsTable holdings={data.holdings} />
      </div>

      {/* Tax */}
      <div id="tab-tax" class={`tab-panel${activeTab === "tax" ? " active" : ""}`} role="tabpanel">
        <div class="card" style="margin-bottom:28px">
          <h2>
            Freistellungsauftrag{" "}
            <span style="opacity:0.4;font-size:11px;font-weight:400;text-transform:none;letter-spacing:0">(tax-free allowance)</span>
          </h2>
          <FsaBar tax={data.tax} freistellungsauftrag={data.freistellungsauftrag} />
        </div>
        <div class="charts-row" style={!hasRealized ? { gridTemplateColumns: "1fr" } : {}}>
          <div class="card">
            <h2>Tax Summary (Germany)</h2>
            <TaxSummary tax={data.tax} freistellungsauftrag={data.freistellungsauftrag} />
          </div>
          <RealizedGains realized={data.realized} />
        </div>
      </div>

      {/* Rebalancing */}
      <div id="tab-rebalancing" class={`tab-panel${activeTab === "rebalancing" ? " active" : ""}`} role="tabpanel">
        <div class="card" style="margin-bottom:28px">
          <h2>Target vs Actual</h2>
          <DeviationChart deviations={data.deviations} />
        </div>
      </div>

      {/* AI Analysis */}
      <div id="tab-analysis" class={`tab-panel${activeTab === "analysis" ? " active" : ""}`} role="tabpanel">
        <AiAdvisor data={data} />
      </div>

      <div class="footer">Portfolio Tracker Dashboard · {dateStr}</div>
    </div>
  );
}
