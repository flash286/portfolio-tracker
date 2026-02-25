"""Base importer infrastructure: ImportResult dataclass and BaseImporter ABC."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from hashlib import sha256


@dataclass
class ImportResult:
    portfolio_id: int
    portfolio_name: str
    holdings_created: int = 0
    holdings_skipped: int = 0
    buys_imported: int = 0
    buys_skipped: int = 0
    dividends_imported: int = 0
    dividends_skipped: int = 0
    cash_imported: int = 0
    cash_skipped: int = 0
    unknown_tickers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False


class _DryRunAbort(Exception):
    pass


class BaseImporter(ABC):
    SOURCE_PREFIX: str  # "revolut", "tr", etc.

    def __init__(
        self,
        portfolio_name: str,
        portfolio_id: int | None = None,
        dry_run: bool = False,
        interactive: bool = True,
    ):
        self.portfolio_name = portfolio_name
        self.portfolio_id = portfolio_id
        self.dry_run = dry_run
        self.interactive = interactive

    def run(self, *args, **kwargs) -> ImportResult:
        """Wrap _run_import atomically. Dry-run: writes then rolls back."""
        from ..data.database import get_db
        db = get_db()
        result = ImportResult(portfolio_id=0, portfolio_name=self.portfolio_name)
        try:
            with db.transaction():
                result = self._run_import(*args, **kwargs)
                result.dry_run = self.dry_run
                if self.dry_run:
                    raise _DryRunAbort()
        except _DryRunAbort:
            pass  # rollback happened; result is still valid
        return result

    def _make_source_id(self, raw: str) -> str:
        digest = sha256(raw.encode()).hexdigest()[:16]
        return f"{self.SOURCE_PREFIX}:{digest}"

    @abstractmethod
    def _run_import(self, *args, **kwargs) -> ImportResult: ...
