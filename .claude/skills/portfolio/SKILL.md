---
name: portfolio
description: Manage the investment portfolio. Use "import <file>" to import transactions from any broker CSV, or "summary" to show a full overview with stats, allocation, rebalancing drift, and tax snapshot. Works with any broker export — Trading 212, Interactive Brokers, Trade Republic, etc.
user-invocable: true
allowed-tools: Read, Bash, Glob
---

Arguments: $ARGUMENTS

---

## Dispatch

Read `$ARGUMENTS`:

- Starts with `import` → run the **Import workflow** below (remaining args = file path)
- Starts with `summary` → run the **Summary workflow** below
- Empty / anything else → ask the user: "What would you like to do?\n[1] Import transactions from a broker CSV\n[2] Show portfolio summary"

---

## Import workflow

**Goal:** Import transactions from a broker CSV into the portfolio tracker using `pt` CLI commands.

### 1 — Read and understand the CSV

Read the file using the Read tool. Identify these columns (exact names vary by broker):

| Column | Alternatives |
|--------|-------------|
| Date | Transaction Date, Time |
| Type | Action, Transaction Type |
| ISIN | Symbol, Ticker |
| Quantity | Shares, Units, No. of shares |
| Price | Price per share, Rate |
| Name | Security Name, Instrument |
| Amount | Total, Value |

If any column mapping is unclear, ask the user before proceeding.

### 2 — Dry-run preview

Before writing anything, show:
- Total rows
- Count by type (buys, sells, dividends, deposits, fees)
- Date range (oldest → newest)
- Unique tickers / ISINs

Ask: "Should I proceed with the import?"

### 3 — Select or create portfolio

```bash
pt portfolio list
```

Ask which portfolio to use, or create a new one:
```bash
pt portfolio create "<broker name>"
```

Note the portfolio ID (PID).

### 4 — Import rows (chronological order — oldest first)

**Deposits:**
```bash
pt cash add <PID> <amount> --type top_up --desc "<description>"
```

**Withdrawals:**
```bash
pt cash add <PID> -<amount> --type withdrawal --desc "<description>"
```

**Fees / management charges:**
```bash
pt cash add <PID> -<amount> --type fee --desc "<description>"
```

**Buy / Sell:**

First check if the holding exists:
```bash
pt holdings list <PID>
```

If the ISIN is not found — create the holding:
```bash
pt holdings add <PID> <ISIN> <type> --name "<name>" --ticker <TICKER> --tfs-rate <rate>
```

- `type`: `etf`, `stock`, `bond`, `crypto`
- `tfs-rate`: `0.3` equity ETF · `0.15` mixed fund · `0.0` stock/crypto/bond

Record the transaction (use holding ID from `pt holdings list`):
```bash
pt tx buy  <HOLDING_ID> <quantity> <price> --date <YYYY-MM-DD>
pt tx sell <HOLDING_ID> <quantity> <price> --date <YYYY-MM-DD>
```

**Dividends:**
```bash
pt cash add <PID> <amount> --type dividend --desc "Dividend: <ticker>"
```

### 5 — Verify

```bash
pt prices fetch <PID>
pt stats summary <PID>
```

### Important notes

- **NOT idempotent** — running twice creates duplicates. Always show the preview first.
- **Chronological order** — oldest transactions first so FIFO lots are correct.
- **EUR only** — if the CSV uses another currency, ask the user to confirm exchange rates.
- **ISIN required** — if the CSV only has a ticker, ask the user for the ISIN.

---

## Summary workflow

**Goal:** Give a comprehensive portfolio overview with actionable recommendations.

### 1 — List portfolios

```bash
pt portfolio list
```

If only one portfolio, use it automatically. Otherwise ask which to summarize.

### 2 — Stats and allocation

```bash
pt stats summary <PID>
pt stats allocation <PID>
```

### 3 — Holdings detail

```bash
pt holdings list <PID>
```

Note: largest positions, biggest winners/losers, any holdings with no current price.

### 4 — Rebalancing drift

```bash
pt rebalance check <PID>
```

Show which assets are overweight / underweight (skip if no targets configured).

### 5 — Tax snapshot (optional)

Ask: "Would you like a tax summary for the current year?"

If yes:
```bash
pt tax realized <PID>
pt tax vorabpauschale <PID>
```

### 6 — Recommendations

Give 1-3 concrete next steps based on the data, for example:
- "Prices are stale — run `pt prices fetch <PID>`"
- "ETF allocation is 8% above target — consider selling some VWCE"
- "You have €1,200 in cash — deploy it to stay on target"
- "FSA is 73% used with 4 months left in the year"
