#!/usr/bin/env python3
"""
Simulate Portfolio A and B vs actual Revolut Robo performance.

Uses the actual Revolut CSV investment dates and amounts,
then allocates those same amounts across the model portfolios.

Historical prices are approximated from:
- Annual returns (from Yahoo Finance / web search)
- 52-week ranges
- Current known prices (Feb 2026)
- Linear interpolation between anchor points

This is an approximation, not exact backtesting.
"""

import csv
import sys
from decimal import Decimal
from datetime import datetime, date
from collections import defaultdict

sys.path.insert(0, "src")

# ============================================================
# APPROXIMATE MONTHLY PRICES (EUR, Xetra)
# Reconstructed from annual returns + known anchor points
# ============================================================
# Approach: use known end-of-year prices and interpolate monthly
#
# VWCE:  2024 return +17.65%, 2025 return +22.45%
#        End 2023 ~€100, End 2024 ~€118, End 2025 ~€144, Feb 2026 ~€149
# VVSM:  2024 return +24.10%, massive rally in 2025
#        End 2023 ~€34, End 2024 ~€42, peak ~€60 mid-2025, Feb 2026 ~€61
# XAIX:  2024 return ~+30%, 2025 return ~+27%
#        End 2023 ~€92, End 2024 ~€120, End 2025 ~€152, Feb 2026 ~€150
# HEAL:  2024 return ~+5%, 2025 return ~+21%
#        End 2023 ~€7.2, End 2024 ~€7.5, End 2025 ~€9.1, Feb 2026 ~€9.0
# LOCK:  2024 return ~+15%, 2025 return ~-13%
#        End 2023 ~€7.5, End 2024 ~€8.6, peak ~€10 mid-2025, Feb 2026 ~€8.2
# BTEC:  2024 return ~+3%, 2025 return ~+10%
#        End 2023 ~€9.2, End 2024 ~€9.5, End 2025 ~€10.4, Feb 2026 ~€10.3
# VAGF:  2024 return ~+4%, 2025 return ~+3%
#        End 2023 ~€22.5, End 2024 ~€23.4, End 2025 ~€24.1, Feb 2026 ~€23.8

# Monthly prices dict: ticker -> {(year, month): price}
# We only need dates where actual investments happened
def interp_price(anchor_points: list, year: int, month: int) -> float:
    """Linearly interpolate between (year, month, price) anchor points."""
    target = year + (month - 1) / 12.0
    # Find surrounding anchors
    for i in range(len(anchor_points) - 1):
        y1, m1, p1 = anchor_points[i]
        y2, m2, p2 = anchor_points[i + 1]
        t1 = y1 + (m1 - 1) / 12.0
        t2 = y2 + (m2 - 1) / 12.0
        if t1 <= target <= t2:
            frac = (target - t1) / (t2 - t1) if t2 != t1 else 0
            return p1 + frac * (p2 - p1)
    # Extrapolate from last two points
    y1, m1, p1 = anchor_points[-2]
    y2, m2, p2 = anchor_points[-1]
    t1 = y1 + (m1 - 1) / 12.0
    t2 = y2 + (m2 - 1) / 12.0
    if t2 == t1:
        return p2
    frac = (target - t1) / (t2 - t1)
    return p1 + frac * (p2 - p1)


# Anchor points: (year, month, price_eur)
# Derived from known annual returns, 52-week ranges, and current prices
PRICE_ANCHORS = {
    "VWCE": [
        (2024, 1, 100.0), (2024, 4, 107.0), (2024, 7, 112.0),
        (2024, 10, 116.0), (2024, 12, 118.0),
        (2025, 3, 122.0), (2025, 6, 130.0), (2025, 9, 138.0),
        (2025, 12, 144.0), (2026, 2, 149.0),
    ],
    "VVSM": [
        (2024, 1, 34.0), (2024, 4, 38.0), (2024, 7, 46.0),
        (2024, 10, 40.0), (2024, 12, 42.0),
        (2025, 3, 44.0), (2025, 6, 56.0), (2025, 9, 52.0),
        (2025, 12, 58.0), (2026, 2, 61.0),
    ],
    "XAIX": [
        (2024, 1, 92.0), (2024, 4, 100.0), (2024, 7, 112.0),
        (2024, 10, 115.0), (2024, 12, 120.0),
        (2025, 3, 128.0), (2025, 6, 150.0), (2025, 9, 145.0),
        (2025, 12, 152.0), (2026, 2, 150.0),
    ],
    "HEAL": [
        (2024, 1, 7.20), (2024, 4, 7.30), (2024, 7, 7.50),
        (2024, 10, 7.40), (2024, 12, 7.55),
        (2025, 3, 7.80), (2025, 6, 8.40), (2025, 9, 8.80),
        (2025, 12, 9.10), (2026, 2, 9.00),
    ],
    "LOCK": [
        (2024, 1, 7.50), (2024, 4, 7.80), (2024, 7, 8.30),
        (2024, 10, 8.50), (2024, 12, 8.65),
        (2025, 3, 9.20), (2025, 6, 9.80), (2025, 9, 9.00),
        (2025, 12, 8.50), (2026, 2, 8.23),
    ],
    "BTEC": [
        (2024, 1, 9.20), (2024, 4, 9.30), (2024, 7, 9.50),
        (2024, 10, 9.40), (2024, 12, 9.50),
        (2025, 3, 9.70), (2025, 6, 10.00), (2025, 9, 10.20),
        (2025, 12, 10.40), (2026, 2, 10.30),
    ],
    "VAGF": [
        (2024, 1, 22.50), (2024, 4, 22.80), (2024, 7, 23.00),
        (2024, 10, 23.20), (2024, 12, 23.40),
        (2025, 3, 23.50), (2025, 6, 23.60), (2025, 9, 23.80),
        (2025, 12, 24.10), (2026, 2, 23.83),
    ],
}


def get_price(ticker: str, dt: datetime) -> float:
    return interp_price(PRICE_ANCHORS[ticker], dt.year, dt.month)


def get_current_price(ticker: str) -> float:
    return PRICE_ANCHORS[ticker][-1][2]


# Portfolio allocations
PORTFOLIO_A = {
    "VWCE": 0.60,
    "VVSM": 0.10,
    "XAIX": 0.10,
    "HEAL": 0.10,
    "VAGF": 0.10,
}

PORTFOLIO_B = {
    "VWCE": 0.50,
    "VVSM": 0.08,
    "XAIX": 0.08,
    "HEAL": 0.07,
    "LOCK": 0.07,
    "BTEC": 0.05,
    "VAGF": 0.15,
}


def simulate_portfolio(name: str, allocations: dict, investments: list) -> dict:
    """
    Simulate a portfolio given allocations and investment schedule.
    investments = [(datetime, amount_eur), ...]

    Returns: {ticker: {shares, cost, current_value}}
    """
    holdings = {t: {"shares": 0.0, "cost": 0.0} for t in allocations}

    for dt, amount in investments:
        for ticker, weight in allocations.items():
            invest_amount = float(amount) * weight
            price = get_price(ticker, dt)
            shares = invest_amount / price
            holdings[ticker]["shares"] += shares
            holdings[ticker]["cost"] += invest_amount

    # Calculate current value
    total_cost = 0.0
    total_value = 0.0
    results = {}

    for ticker, data in holdings.items():
        cur_price = get_current_price(ticker)
        cur_value = data["shares"] * cur_price
        results[ticker] = {
            "shares": data["shares"],
            "cost": data["cost"],
            "value": cur_value,
            "pnl": cur_value - data["cost"],
            "pnl_pct": ((cur_value / data["cost"]) - 1) * 100 if data["cost"] > 0 else 0,
        }
        total_cost += data["cost"]
        total_value += cur_value

    results["_TOTAL"] = {
        "cost": total_cost,
        "value": total_value,
        "pnl": total_value - total_cost,
        "pnl_pct": ((total_value / total_cost) - 1) * 100 if total_cost > 0 else 0,
    }
    return results


def parse_eur(s: str) -> float:
    return float(s.strip().replace("EUR ", "").replace("€", "").replace(",", ""))


def main():
    # Read actual investment schedule from Revolut CSV
    investments = []  # (datetime, amount)
    total_invested = 0.0
    tx_csv = "data/revolut_transactions.csv"

    with open(tx_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Type"].strip() == "BUY - MARKET":
                dt = datetime.fromisoformat(row["Date"].strip().replace("Z", "+00:00"))
                amount = parse_eur(row["Total Amount"])
                investments.append((dt, amount))
                total_invested += amount

    print(f"Total buy transactions: {len(investments)}")
    print(f"Total invested: €{total_invested:,.2f}")
    print(f"Period: {investments[0][0].strftime('%b %Y')} — {investments[-1][0].strftime('%b %Y')}")
    print()

    # Simulate both portfolios
    result_a = simulate_portfolio("Portfolio A", PORTFOLIO_A, investments)
    result_b = simulate_portfolio("Portfolio B", PORTFOLIO_B, investments)

    # Actual Revolut result
    actual_value = 15448.96
    actual_cost = 14048.13  # from our DB (slightly less than total_invested due to rounding)
    actual_divs = 453.22
    actual_fees = 131.78
    actual_net = actual_value - actual_cost + actual_divs - actual_fees

    # Print comparison
    print("=" * 78)
    print("   COMPARISON: REVOLUT ROBO vs PORTFOLIO A vs PORTFOLIO B")
    print("   (Same investment dates and amounts, different allocation)")
    print("=" * 78)

    # Revolut Actual
    print(f"\n{'─'*78}")
    print(f"  📊 ACTUAL: Revolut Robo-Advisor (8 ETF)")
    print(f"{'─'*78}")
    print(f"  Invested:       €{actual_cost:>10,.2f}")
    print(f"  Current value:  €{actual_value:>10,.2f}")
    print(f"  Unrealized P&L: €{actual_value - actual_cost:>10,.2f}  ({(actual_value/actual_cost-1)*100:>+.1f}%)")
    print(f"  Dividends:      €{actual_divs:>10,.2f}")
    print(f"  Fees:          -€{actual_fees:>10,.2f}")
    print(f"  NET TOTAL:      €{actual_net:>10,.2f}  ({actual_net/actual_cost*100:>+.1f}%)")

    # Portfolio A
    ra = result_a["_TOTAL"]
    print(f"\n{'─'*78}")
    print(f"  🅰️  PORTFOLIO A: Conservative Growth (5 ETF)")
    print(f"  60% VWCE / 10% VVSM / 10% XAIX / 10% HEAL / 10% VAGF")
    print(f"{'─'*78}")
    print(f"  Invested:       €{ra['cost']:>10,.2f}")
    print(f"  Current value:  €{ra['value']:>10,.2f}")
    print(f"  Unrealized P&L: €{ra['pnl']:>10,.2f}  ({ra['pnl_pct']:>+.1f}%)")
    print(f"  Fees:            €      0.00  (TR free Sparpläne)")
    print(f"  NET TOTAL:      €{ra['pnl']:>10,.2f}  ({ra['pnl_pct']:>+.1f}%)")
    print()
    for t in ["VWCE", "VVSM", "XAIX", "HEAL", "VAGF"]:
        r = result_a[t]
        print(f"    {t:6s}  cost €{r['cost']:>8,.2f}  value €{r['value']:>8,.2f}  P&L {r['pnl_pct']:>+6.1f}%")

    # Portfolio B
    rb = result_b["_TOTAL"]
    print(f"\n{'─'*78}")
    print(f"  🅱️  PORTFOLIO B: Balanced Megatrends (7 ETF)")
    print(f"  50% VWCE / 8% VVSM / 8% XAIX / 7% HEAL / 7% LOCK / 5% BTEC / 15% VAGF")
    print(f"{'─'*78}")
    print(f"  Invested:       €{rb['cost']:>10,.2f}")
    print(f"  Current value:  €{rb['value']:>10,.2f}")
    print(f"  Unrealized P&L: €{rb['pnl']:>10,.2f}  ({rb['pnl_pct']:>+.1f}%)")
    print(f"  Fees:            €      0.00  (TR free Sparpläne)")
    print(f"  NET TOTAL:      €{rb['pnl']:>10,.2f}  ({rb['pnl_pct']:>+.1f}%)")
    print()
    for t in ["VWCE", "VVSM", "XAIX", "HEAL", "LOCK", "BTEC", "VAGF"]:
        r = result_b[t]
        print(f"    {t:6s}  cost €{r['cost']:>8,.2f}  value €{r['value']:>8,.2f}  P&L {r['pnl_pct']:>+6.1f}%")

    # Delta comparison
    print(f"\n{'='*78}")
    print(f"  📊 DELTA COMPARISON")
    print(f"{'='*78}")
    print(f"  {'':30s} {'Revolut':>12s} {'Port. A':>12s} {'Port. B':>12s}")
    print(f"  {'─'*30} {'─'*12} {'─'*12} {'─'*12}")
    print(f"  {'Invested':30s} €{actual_cost:>10,.2f} €{ra['cost']:>10,.2f} €{rb['cost']:>10,.2f}")
    print(f"  {'Current Value':30s} €{actual_value:>10,.2f} €{ra['value']:>10,.2f} €{rb['value']:>10,.2f}")
    print(f"  {'Unrealized P&L':30s} €{actual_value-actual_cost:>10,.2f} €{ra['pnl']:>10,.2f} €{rb['pnl']:>10,.2f}")
    print(f"  {'P&L %':30s} {(actual_value/actual_cost-1)*100:>+10.1f}% {ra['pnl_pct']:>+10.1f}% {rb['pnl_pct']:>+10.1f}%")
    print(f"  {'Dividends':30s} €{actual_divs:>10,.2f}       €0.00       €0.00")
    print(f"  {'Fees':30s}-€{actual_fees:>10,.2f}       €0.00       €0.00")
    print(f"  {'NET GAIN':30s} €{actual_net:>10,.2f} €{ra['pnl']:>10,.2f} €{rb['pnl']:>10,.2f}")

    # Difference vs actual
    diff_a = ra['pnl'] - actual_net
    diff_b = rb['pnl'] - actual_net
    print(f"\n  {'vs Revolut Robo':30s}             {'+' if diff_a >= 0 else ''}€{diff_a:>9,.2f}  {'+' if diff_b >= 0 else ''}€{diff_b:>9,.2f}")

    print(f"\n{'='*78}")
    print(f"  ⚠️  DISCLAIMER")
    print(f"{'='*78}")
    print(f"  • Prices approximate (interpolated from annual returns + known anchors)")
    print(f"  • Past performance does not predict future results")
    print(f"  • Portfolio A/B are accumulating → no dividends but price includes them")
    print(f"  • Revolut dividends (€453) reinvested by Robo → already in portfolio value")
    print(f"  • Real execution would differ due to spreads, timing, fractional shares")
    print()


if __name__ == "__main__":
    main()
