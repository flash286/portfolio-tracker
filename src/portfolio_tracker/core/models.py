"""Data models for the portfolio tracker."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class AssetType(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    ETF = "etf"
    BOND = "bond"


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"


class CashTransactionType(str, Enum):
    TOP_UP = "top_up"
    WITHDRAWAL = "withdrawal"
    FEE = "fee"
    DIVIDEND = "dividend"  # cash received from dividends
    BUY = "buy"            # cash spent on purchases
    SELL = "sell"           # cash received from sales


@dataclass
class Portfolio:
    name: str
    description: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Holding:
    portfolio_id: int
    isin: str
    asset_type: AssetType
    shares: Decimal = Decimal("0")
    cost_basis: Decimal = Decimal("0")
    teilfreistellung_rate: Decimal = Decimal("0")
    id: Optional[int] = None
    name: str = ""  # Human-readable name (e.g. "Apple Inc.")
    ticker: str = ""  # Yahoo Finance ticker for price fetching (e.g. "AAPL")
    current_price: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def current_value(self) -> Decimal:
        if self.current_price is None:
            return Decimal("0")
        return self.shares * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.current_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> Decimal:
        if self.cost_basis == 0:
            return Decimal("0")
        return (self.unrealized_pnl / self.cost_basis * 100).quantize(Decimal("0.01"))


@dataclass
class Transaction:
    holding_id: int
    transaction_type: TransactionType
    quantity: Decimal
    price: Decimal
    transaction_date: datetime
    notes: str = ""
    realized_gain: Optional[Decimal] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @property
    def total_value(self) -> Decimal:
        return self.quantity * self.price


@dataclass
class PricePoint:
    holding_id: int
    price: Decimal
    fetch_date: datetime
    source: str = ""
    id: Optional[int] = None


@dataclass
class TargetAllocation:
    portfolio_id: int
    asset_type: str  # Can be AssetType value or specific symbol
    target_percentage: Decimal
    rebalance_threshold: Decimal = Decimal("5.0")
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class RebalanceTrade:
    action: TransactionType
    isin: str
    asset_type: AssetType
    shares: Decimal
    current_price: Decimal
    reason: str
    name: str = ""
    ticker: str = ""

    @property
    def trade_value(self) -> Decimal:
        return self.shares * self.current_price


@dataclass
class CashTransaction:
    """Cash movement in a portfolio (top-up, withdrawal, fee, etc.)."""
    portfolio_id: int
    cash_type: CashTransactionType
    amount: Decimal  # positive = cash in, negative = cash out
    transaction_date: datetime
    description: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class TaxLot:
    """A FIFO tax lot created by a buy transaction."""
    holding_id: int
    acquired_date: datetime
    quantity: Decimal
    cost_per_unit: Decimal
    quantity_remaining: Decimal
    id: Optional[int] = None
    buy_transaction_id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class TaxInfo:
    """German tax calculation results."""
    gross_gain: Decimal = Decimal("0")
    teilfreistellung_exempt: Decimal = Decimal("0")
    freistellungsauftrag_used: Decimal = Decimal("0")
    taxable_gain: Decimal = Decimal("0")
    abgeltungssteuer: Decimal = Decimal("0")  # 25%
    solidaritaetszuschlag: Decimal = Decimal("0")  # 5.5% of Abgeltungssteuer
    total_tax: Decimal = Decimal("0")
    net_gain: Decimal = Decimal("0")
