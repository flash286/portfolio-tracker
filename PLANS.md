# Portfolio Tracker — Plans

## 1. Trade Republic Integration

### 1a. Manual CSV Import (priority — do this first)
Trade Republic allows exporting transaction history as CSV from the app or website. Write `scripts/import_tr.py` following the same pattern as `import_revolut_csv.py`.

- Download a sample CSV from TR and study the format
- Parse: buys, sells, dividends, Sparplan purchases, fees
- Create portfolio + holdings + transactions + cash_transactions
- Support idempotent re-import (no duplicate transactions)
- Command: `pt import tr <file.csv>`

### 1b. Automatic Sync via pytr (optional, after 1a)
[pytr](https://github.com/pytr-org/pytr) is an unofficial Python library for the Trade Republic private WebSocket API.

Capabilities: fetching portfolio data, exporting transactions, downloading PDF documents.

Caveats:
- **Private API** — may break without notice on TR updates
- **Authentication**: web login requires a 4-digit code each session; app login logs you out of the mobile app
- **Instability** — multiple forks exist due to the original being abandoned
- **No guarantees** — not affiliated with Trade Republic

Plan: use pytr optionally as a fallback for `pt sync tr`. The primary path is manual CSV import.

---

## 2. Vorabpauschale Calculator

Vorabpauschale is the annual tax on unrealized gains for accumulating funds in Germany. All 5 ETFs in Portfolio A are accumulating, making this relevant.

Formula:
```
Basisertrag = Fondswert_01.01 × Basiszins × 0.7
Vorabpauschale = min(Basisertrag, actual_gain_for_year)
Teilfreistellung = 30% for Aktienfonds (>51% equity)
Taxable_amount = Vorabpauschale × (1 - Teilfreistellung)
Tax = Taxable_amount × 26.375% (Abgeltungssteuer + Soli)
```

- Basiszins is published by Bundesbank each January
- Need to store Fondswert on Jan 1 of each year
- Teilfreistellung depends on fund type (30% equity, 15% mixed, 0% bond)
- Deducted from Freistellungsauftrag
- Command: `pt tax vorabpauschale <portfolio_id> --year 2026`

---

## 3. Migration Workflow (Revolut → Trade Republic)

Step-by-step guided workflow for migration:

```
pt migrate plan 1 --target-portfolio 2
```

1. Show current Revolut portfolio and cash
2. Calculate tax on selling all positions (Abgeltungssteuer, accounting for Freistellungsauftrag)
3. Show post-sale amount after taxes
4. Show target allocation in TR per Portfolio A
5. Calculate specific purchases (quantity × price) for each ETF
6. Show the final plan: what to sell → how much you'll receive → what to buy

---

## 4. Sparplan (DCA) Tracking

Monthly Sparplan — automated purchases in Trade Republic.

- `sparplan` table in DB: portfolio_id, holding_id, amount_eur, frequency (monthly/biweekly), active
- `pt sparplan set 2 VWCE 300` — set €300/month on VWCE
- `pt sparplan list 2` — show all active Sparpläne
- `pt sparplan simulate 2 --months 12` — simulation: what the portfolio will look like after N months
- Dashboard: DCA progress section

---

## 5. Performance History

Currently only a snapshot of the current state exists. Historical tracking is needed.

- Daily portfolio value snapshot into a `portfolio_snapshots` table (date, portfolio_id, holdings_value, cash_balance, total_value)
- Time-weighted return (TWR) — correct return calculation accounting for cash flows
- `pt stats performance 1 --period 1y` — show return over a period
- Dashboard: portfolio value chart over time
- Can be automated via `pt snapshot` run by cron / scheduler

---

## 6. Multi-Portfolio Support

During migration, two portfolios (Revolut + TR) will coexist. Already supported at the DB level, but still needed:

- `pt portfolio compare 1 2` — compare two portfolios
- `pt stats summary --all` — combined statistics across all portfolios
- Dashboard: portfolio switcher + combined view
- Aggregate cash balance / P&L across all portfolios

---

## 7. Alerts & Notifications

- Deviation from target exceeds threshold → rebalancing reminder
- P&L reaches a certain amount
- Freistellungsauftrag nearly exhausted
- Dividend received
- Implementation: `pt alerts check` (via cron) + console output or email/Telegram

---

## 8. Steuererklärung Export

Export data for Anlage KAP (tax return appendix):

- Total dividends for the year
- Realized gains/losses
- Vorabpauschale paid
- Freistellungsauftrag used
- Format: CSV or PDF report
- Command: `pt tax report --year 2026`

---

## 9. User-Agnostic Configuration

Personal specifics for a single user are currently hardcoded. These should be moved to a config file.

### What is hardcoded today

| Location | What | Where |
|----------|------|-------|
| `calculator.py` | `DEFAULT_FREISTELLUNGSAUFTRAG = €2000` (married) | core |
| `calculator.py` | Tax rates 25% + 5.5% Soli | core |
| `dashboard.py` | `isin_names` — hardcoded Portfolio A tickers | dashboard |
| `dashboard.py` | `fsaTotal = 2000` in JS | dashboard |
| `CLAUDE.md` / `AGENTS.md` | Name, citizenship, broker, tax profile | docs |
| `price_fetcher.py` | `TICKER_OVERRIDES` — only Revolut + Portfolio A tickers | external |

### What to do

**`config.toml` at project root** (created on first run):
```toml
[tax]
country = "DE"
freistellungsauftrag = 2000   # 1000 single / 2000 married
abgeltungssteuer_rate = 0.25
soli_rate = 0.055
kirchensteuer = false

[user]
name = ""          # optional, for display only
currency = "EUR"

[prices]
default_exchange_suffix = ".DE"
```

**`pt config set tax.freistellungsauftrag 1000`** — CLI for changes

**Remove from code:**
- Hardcoded `€2,000` → read from config
- `isin_names` in dashboard → pull from holdings in DB (almost done already)
- `fsaTotal = 2000` in JS → pass from Python in JSON data

**Remove from documentation:**
- Personal data (name, citizenship) → keep only as examples in `README`
- `CLAUDE.md` should contain only technical project specifics

### What NOT to change

- German tax model as default (target audience — DE residents)
- SQLite as storage — sufficient for a single user
- CLI-first approach

---

## Priorities

| # | Task | Complexity | Value |
|---|------|------------|-------|
| 1 | TR CSV import | Medium | High — no data without this |
| 2 | Vorabpauschale | Medium | High — directly affects taxes |
| 3 | Migration workflow | Low | High — needed right now |
| 4 | Performance history | Medium | Medium — nice, but not urgent |
| 5 | Sparplan tracking | Low | Medium — after DCA setup in TR |
| 6 | Multi-portfolio | Low | Medium — partially works already |
| 7 | User-agnostic config | Medium | Medium — needed before open source |
| 8 | pytr auto-sync | High | Low — private API, unstable |
| 9 | Alerts | Medium | Low — nice to have |
| 10 | Steuererklärung | Medium | Low — once a year |
