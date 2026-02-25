# Portfolio Tracker — Plans

## 1. Trade Republic Integration

### 1a. Manual CSV Import (priority — do this first)
Trade Republic allows exporting transaction history as CSV from the app or website. Implement `pt import tr <file.csv>` following the same pattern as `pt import revolut`.

- Download a sample CSV from TR and study the format
- Parse: buys, sells, dividends, Sparplan purchases, fees
- Create portfolio + holdings + transactions + cash_transactions
- Idempotent re-import via `source_id` (same pattern as Revolut importer)
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

## 2. Migration Workflow (Revolut → Trade Republic)

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

## 3. Sparplan (DCA) Tracking

Monthly Sparplan — automated purchases in Trade Republic.

- `sparplan` table in DB: portfolio_id, holding_id, amount_eur, frequency (monthly/biweekly), active
- `pt sparplan set 2 VWCE 300` — set €300/month on VWCE
- `pt sparplan list 2` — show all active Sparpläne
- `pt sparplan simulate 2 --months 12` — simulation: what the portfolio will look like after N months
- Dashboard: DCA progress section

---

## 4. Performance History

Currently only a snapshot of the current state exists. Historical tracking is needed.

- Daily portfolio value snapshot into a `portfolio_snapshots` table (date, portfolio_id, holdings_value, cash_balance, total_value)
- Time-weighted return (TWR) — correct return calculation accounting for cash flows
- `pt stats performance 1 --period 1y` — show return over a period
- Dashboard: portfolio value chart over time
- Can be automated via `pt snapshot` run by cron / scheduler

---

## 5. Multi-Portfolio Support

During migration, two portfolios (Revolut + TR) will coexist. DB-level support already exists, but still needed:

- `pt portfolio compare 1 2` — compare two portfolios side by side
- `pt stats summary --all` — combined statistics across all portfolios
- Dashboard: portfolio switcher + combined view
- Aggregate cash balance / P&L across all portfolios

---

## 6. Alerts & Notifications

- Deviation from target exceeds threshold → rebalancing reminder
- P&L reaches a certain amount
- Freistellungsauftrag nearly exhausted
- Dividend received
- Implementation: `pt alerts check` (via cron) + console output or email/Telegram

---

## 7. Steuererklärung Export

Export data for Anlage KAP (tax return appendix):

- Total dividends for the year
- Realized gains/losses
- Vorabpauschale paid
- Freistellungsauftrag used
- Format: CSV or PDF report
- Command: `pt tax report --year 2026`

---

## 8. Tax & Math Engine Refactoring

The core financial logic lives in `core/calculator.py` as a large monolithic class. Before this project can be reliably extended (or used by others), the math layer needs to be extracted, documented, and covered by tests.

### What to extract

| Module | Responsibility |
|--------|---------------|
| `core/tax/abgeltungssteuer.py` | Abgeltungssteuer + Soli + Kirchensteuer calculation |
| `core/tax/teilfreistellung.py` | TFS rates per §20 InvStG, weighted portfolio TFS |
| `core/tax/vorabpauschale.py` | §18 InvStG annual prepayment tax (Basisertrag formula) |
| `core/tax/freistellungsauftrag.py` | FSA allocation across income types |
| `core/finance/fifo.py` | FIFO lot matching for realized gain calculation |
| `core/finance/returns.py` | TWR, simple return, cost basis calculations |

### What good looks like

- Each module is a **pure function** — no DB access, no I/O, only `Decimal` in, `Decimal` out
- Fully documented with docstrings including legal references (§ InvStG, § EStG)
- 100% test coverage via `pytest` with known-good values from official BMF examples
- `PortfolioCalculator` becomes a thin orchestration layer that calls these modules
- CLI commands stay unchanged — pure refactor, no behavior change

### Why this matters

- Makes German tax logic auditable and trustworthy
- Enables contributors to understand and verify calculations independently
- Required foundation before adding Steuererklärung export or more complex tax scenarios

---

## 9. pytr Auto-Sync (optional)

See section 1b above. Lower priority — depends on 1a being stable first.

---

## Priorities

| # | Task | Complexity | Value |
|---|------|------------|-------|
| 1 | TR CSV import | Medium | High — no TR data without this |
| 2 | Migration workflow | Low | High — needed before Revolut liquidation |
| 3 | Tax & math engine refactoring | Medium | High — foundation for correctness and contributions |
| 4 | Performance history | Medium | Medium — nice, but not urgent |
| 5 | Sparplan tracking | Low | Medium — after DCA setup in TR |
| 6 | Multi-portfolio compare | Low | Medium — partially works already |
| 7 | Steuererklärung export | Medium | Low — once a year |
| 8 | Alerts | Medium | Low — nice to have |
| 9 | pytr auto-sync | High | Low — private API, unstable |

---

## Completed

| Feature | Notes |
|---------|-------|
| **Revolut CSV import** (`pt import revolut`) | Idempotent, interactive ticker resolution, auto price fetch |
| **Vorabpauschale calculator** (`pt tax vorabpauschale`) | Full §18 InvStG implementation with caching |
| **User-agnostic configuration** (`pt setup run`) | Interactive wizard, `config.json`, FSA/tax rates/currency |
