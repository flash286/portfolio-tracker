"""Revolut CSV importer."""

import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt

from ..core.models import (
    AssetType,
    CashTransaction,
    CashTransactionType,
    Holding,
    Portfolio,
    TaxLot,
    Transaction,
    TransactionType,
)
from ..data.repositories.cash_repo import CashRepository
from ..data.repositories.holdings_repo import HoldingsRepository
from ..data.repositories.lots_repo import LotsRepository
from ..data.repositories.portfolios_repo import PortfoliosRepository
from ..data.repositories.transactions_repo import TransactionsRepository
from .base import BaseImporter, ImportResult
from .registry import ETF_REGISTRY

_console = Console()

# Path to the user-editable registry (lives next to config.json / portfolio.db)
def _user_registry_path() -> Path:
    from ..data.database import _find_project_root
    return _find_project_root() / "user_registry.json"


def load_user_registry() -> dict[str, dict]:
    path = _user_registry_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_user_registry(registry: dict[str, dict]) -> None:
    path = _user_registry_path()
    with open(path, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")


class RevolutImporter(BaseImporter):
    SOURCE_PREFIX = "revolut"

    def _run_import(
        self,
        tx_csv: Path,
        pnl_csv: Optional[Path] = None,
    ) -> ImportResult:
        portfolios_repo = PortfoliosRepository()
        portfolio = self._get_or_create_portfolio(portfolios_repo)
        result = ImportResult(portfolio_id=portfolio.id, portfolio_name=portfolio.name)

        pnl_meta_map = self._parse_pnl_meta(pnl_csv) if pnl_csv else {}
        holding_map = self._ensure_holdings(tx_csv, portfolio.id, pnl_meta_map, result)

        with open(tx_csv, newline="", encoding="utf-8-sig") as f:
            for lineno, row in enumerate(csv.DictReader(f), 2):
                self._process_row(row, lineno, portfolio.id, holding_map, result)

        self._recalculate_holdings(holding_map)
        return result

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    def _get_or_create_portfolio(self, portfolios_repo: PortfoliosRepository):
        if self.portfolio_id is not None:
            p = portfolios_repo.get_by_id(self.portfolio_id)
            if p is None:
                raise ValueError(f"Portfolio ID {self.portfolio_id} not found")
            return p
        existing = portfolios_repo.get_by_name(self.portfolio_name)
        if existing:
            return existing
        return portfolios_repo.create(Portfolio(
            name=self.portfolio_name,
            description="Revolut Robo-Advisor — imported via pt import revolut",
        ))

    # ------------------------------------------------------------------
    # Holdings pre-scan
    # ------------------------------------------------------------------

    def _ensure_holdings(
        self,
        tx_csv: Path,
        portfolio_id: int,
        pnl_meta_map: dict[str, dict],
        result: ImportResult,
    ) -> dict[str, int]:
        """Pre-scan CSV, create missing holdings, return ticker → holding_id map."""
        holdings_repo = HoldingsRepository()
        user_registry = load_user_registry()

        # Collect unique tickers that appear in buy/dividend rows
        tickers: set[str] = set()
        with open(tx_csv, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                tx_type = row.get("Type", "").strip()
                ticker = row.get("Ticker", "").strip()
                if ticker and tx_type in ("BUY - MARKET", "DIVIDEND"):
                    tickers.add(ticker)

        holding_map: dict[str, int] = {}
        for ticker in sorted(tickers):
            meta = (
                ETF_REGISTRY.get(ticker)
                or pnl_meta_map.get(ticker)
                or user_registry.get(ticker)
            )

            if meta is None:
                meta = self._resolve_unknown_ticker(ticker, user_registry)

            if meta is None:
                result.unknown_tickers.append(ticker)
                result.warnings.append(
                    f"Unknown ticker {ticker!r} — skipped. "
                    f"Run again to enter ISIN interactively, or add to user_registry.json."
                )
                continue

            isin = meta["isin"]
            existing = holdings_repo.get_by_isin(portfolio_id, isin)
            if existing:
                holding_map[ticker] = existing.id
                result.holdings_skipped += 1
            else:
                h = holdings_repo.create(Holding(
                    portfolio_id=portfolio_id,
                    isin=isin,
                    asset_type=AssetType(meta["type"]),
                    name=meta["name"],
                    ticker=ticker,
                    teilfreistellung_rate=Decimal(meta["tfs"]),
                ))
                holding_map[ticker] = h.id
                result.holdings_created += 1

        return holding_map

    # ------------------------------------------------------------------
    # Interactive ISIN resolution
    # ------------------------------------------------------------------

    def _resolve_unknown_ticker(
        self, ticker: str, user_registry: dict[str, dict]
    ) -> Optional[dict]:
        """Prompt the user for ISIN + metadata and persist to user_registry.json."""
        if not self.interactive:
            return None

        _console.print(f"\n[yellow]Unknown ticker:[/yellow] [bold]{ticker}[/bold]")
        _console.print(
            "  Not found in registry or P&L CSV. "
            "Look up the ISIN on [link=https://www.justetf.com]justetf.com[/link] "
            "or your broker."
        )

        isin = Prompt.ask("  ISIN (12 chars, or Enter to skip)", default="").strip().upper()
        if not isin or len(isin) != 12:
            _console.print(f"  [dim]Skipping {ticker}.[/dim]")
            return None

        asset_type = Prompt.ask(
            "  Asset type", choices=["etf", "bond", "stock"], default="etf"
        )
        default_tfs = "0.3" if asset_type == "etf" else "0"
        tfs = Prompt.ask("  Teilfreistellung rate (0–1)", default=default_tfs)
        name = Prompt.ask("  Fund name", default=ticker)

        meta = {"isin": isin, "name": name, "type": asset_type, "tfs": tfs}

        user_registry[ticker] = meta
        save_user_registry(user_registry)
        _console.print("  [green]Saved[/green] → user_registry.json\n")

        return meta

    # ------------------------------------------------------------------
    # Row processing
    # ------------------------------------------------------------------

    def _process_row(
        self,
        row: dict,
        lineno: int,
        portfolio_id: int,
        holding_map: dict[str, int],
        result: ImportResult,
    ) -> None:
        tx_repo = TransactionsRepository()
        cash_repo = CashRepository()

        tx_type = row.get("Type", "").strip()
        ticker = row.get("Ticker", "").strip()
        date_str = row.get("Date", "").strip()

        if not date_str:
            return

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            result.warnings.append(f"Line {lineno}: unparseable date {date_str!r}, skipped")
            return

        raw = ",".join(row.values())
        sid = self._make_source_id(raw)

        if tx_type == "BUY - MARKET":
            if ticker not in holding_map:
                return
            try:
                qty = Decimal(row["Quantity"])
                price = self._parse_eur(row["Price per share"])
                total = self._parse_eur(row["Total Amount"])
            except (InvalidOperation, KeyError) as e:
                result.warnings.append(f"Line {lineno}: parse error {e}, skipped")
                return

            tx = tx_repo.create(Transaction(
                holding_id=holding_map[ticker],
                transaction_type=TransactionType.BUY,
                quantity=qty, price=price, transaction_date=dt,
                notes="Revolut CSV import",
            ), source_id=sid)
            if tx is not None:
                lots_repo = LotsRepository()
                lots_repo.create(TaxLot(
                    holding_id=holding_map[ticker], acquired_date=dt,
                    quantity=qty, cost_per_unit=price, quantity_remaining=qty,
                    buy_transaction_id=tx.id,
                ))
                cash_repo.create(CashTransaction(
                    portfolio_id=portfolio_id,
                    cash_type=CashTransactionType.BUY,
                    amount=-total, transaction_date=dt,
                    description=f"Buy {ticker} ({qty} × €{price})",
                ), source_id=f"{sid}:cash")
                result.buys_imported += 1
                result.cash_imported += 1
            else:
                result.buys_skipped += 1
                result.cash_skipped += 1

        elif tx_type == "DIVIDEND":
            if ticker not in holding_map:
                return
            try:
                amount = self._parse_eur(row["Total Amount"])
            except (InvalidOperation, KeyError) as e:
                result.warnings.append(f"Line {lineno}: parse error {e}, skipped")
                return

            tx = tx_repo.create(Transaction(
                holding_id=holding_map[ticker],
                transaction_type=TransactionType.DIVIDEND,
                quantity=Decimal("0"), price=amount, transaction_date=dt,
                notes="Revolut dividend",
            ), source_id=sid)
            if tx is not None:
                cash_repo.create(CashTransaction(
                    portfolio_id=portfolio_id,
                    cash_type=CashTransactionType.DIVIDEND,
                    amount=amount, transaction_date=dt,
                    description=f"Dividend from {ticker}",
                ), source_id=f"{sid}:cash")
                result.dividends_imported += 1
                result.cash_imported += 1
            else:
                result.dividends_skipped += 1
                result.cash_skipped += 1

        elif tx_type == "CASH TOP-UP":
            try:
                amount = self._parse_eur(row["Total Amount"])
            except (InvalidOperation, KeyError) as e:
                result.warnings.append(f"Line {lineno}: parse error {e}, skipped")
                return

            ct = cash_repo.create(CashTransaction(
                portfolio_id=portfolio_id,
                cash_type=CashTransactionType.TOP_UP,
                amount=amount, transaction_date=dt,
                description="Revolut top-up",
            ), source_id=sid)
            if ct is not None:
                result.cash_imported += 1
            else:
                result.cash_skipped += 1

        elif tx_type == "ROBO MANAGEMENT FEE":
            try:
                fee = self._parse_eur(row["Total Amount"])
            except (InvalidOperation, KeyError) as e:
                result.warnings.append(f"Line {lineno}: parse error {e}, skipped")
                return

            ct = cash_repo.create(CashTransaction(
                portfolio_id=portfolio_id,
                cash_type=CashTransactionType.FEE,
                amount=fee, transaction_date=dt,
                description="Robo management fee",
            ), source_id=sid)
            if ct is not None:
                result.cash_imported += 1
            else:
                result.cash_skipped += 1

    # ------------------------------------------------------------------
    # Post-import recalculation
    # ------------------------------------------------------------------

    def _recalculate_holdings(self, holding_map: dict[str, int]) -> None:
        """Recompute shares and cost_basis from full transaction history."""
        holdings_repo = HoldingsRepository()
        tx_repo = TransactionsRepository()

        for _ticker, hid in holding_map.items():
            h = holdings_repo.get_by_id(hid)
            if h is None:
                continue
            txs = tx_repo.list_by_holding(hid)
            total_shares = Decimal("0")
            total_cost = Decimal("0")
            for tx in txs:
                if tx.transaction_type == TransactionType.BUY:
                    total_shares += tx.quantity
                    total_cost += tx.quantity * tx.price
            h.shares = total_shares
            h.cost_basis = total_cost
            holdings_repo.save(h)

    # ------------------------------------------------------------------
    # P&L metadata extraction
    # ------------------------------------------------------------------

    _PNL_SECTIONS = {"Income from Sells", "Other income & fees"}

    def _parse_pnl_meta(self, pnl_csv: Path) -> dict[str, dict]:
        """
        Parse both sections of the Revolut P&L CSV and return ticker → metadata.

        The file has two sections with different column layouts, each preceded
        by a section-header line and then a CSV header row.  We reset the
        active headers whenever we hit a section marker.

        Returns: {ticker: {isin, name, type, tfs}}
        """
        result: dict[str, dict] = {}
        try:
            with open(pnl_csv, newline="", encoding="utf-8-sig") as f:
                raw_rows = list(csv.reader(f))

            headers: list[str] = []
            for row in raw_rows:
                if not row or all(c.strip() == "" for c in row):
                    continue
                first = row[0].strip()
                if first in self._PNL_SECTIONS:
                    headers = []  # next non-empty row will be the header
                    continue
                if not headers:
                    headers = [c.strip() for c in row]
                    continue
                # Data row — zip against current section's headers
                data = dict(zip(headers, (c.strip() for c in row)))
                symbol = data.get("Symbol", "").strip().upper()
                isin = data.get("ISIN", "").strip()
                name = data.get("Security name", "").strip()
                if symbol and len(isin) == 12:
                    result[symbol] = self._infer_meta(isin, name)
        except (OSError, csv.Error):
            pass
        return result

    @staticmethod
    def _infer_meta(isin: str, name: str) -> dict:
        """Infer asset type and Teilfreistellung rate from the security name."""
        for suffix in (" dividend", " dividends"):
            if name.lower().endswith(suffix):
                name = name[: -len(suffix)].strip()
                break
        is_bond = any(w in name.lower() for w in ("bond", "treasury", "gilt"))
        return {
            "isin": isin,
            "name": name,
            "type": "bond" if is_bond else "etf",
            "tfs": "0" if is_bond else "0.3",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_eur(s: str) -> Decimal:
        cleaned = s.strip().replace("EUR ", "").replace("€", "").replace(",", "")
        return Decimal(cleaned)
