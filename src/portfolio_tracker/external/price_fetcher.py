"""Price fetching via yfinance for stocks, ETFs, and bonds."""

from decimal import Decimal
from typing import Optional

import yfinance as yf
from datetime import timedelta

from ..core.exceptions import PriceFetchError

# European ETF tickers often need an exchange suffix for yfinance.
# Map known tickers to their Yahoo Finance symbol.
TICKER_OVERRIDES = {
    # Current Revolut holdings (Xetra)
    "IS3Q": "IS3Q.DE",
    "XDWT": "XDWT.DE",
    "DBXJ": "DBXJ.DE",
    "EXI2": "EXI2.DE",
    "IS3C": "IS3C.DE",
    "IS3K": "IS3K.DE",
    "QDVY": "QDVY.DE",
    "IBCD": "IBCD.DE",
    # Portfolio A targets (Xetra)
    "VWCE": "VWCE.DE",
    "VVSM": "VVSM.DE",
    "XAIX": "XAIX.DE",
    "HEAL": "HEAL.DE",
    "VAGF": "VAGF.DE",
}

# Exchange suffixes to try if direct lookup fails
EXCHANGE_SUFFIXES = [".DE", ".L", ".AS", ".PA", ".MI", ""]


class PriceFetcher:
    """Fetches prices for stocks, ETFs, and bonds via Yahoo Finance."""

    @staticmethod
    def _try_fetch(symbol: str) -> Optional[float]:
        """Try to get a price for a single Yahoo Finance symbol. Returns None on failure."""
        try:
            ticker = yf.Ticker(symbol)
            # Try fast_info first
            try:
                info = ticker.fast_info
                price = getattr(info, "last_price", None)
                if price is not None and price > 0:
                    return float(price)
            except Exception:
                pass
            # Fallback to history
            try:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    return float(hist["Close"].iloc[-1])
            except Exception:
                pass
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_price(symbol: str) -> Optional[Decimal]:
        """Fetch current price for a single symbol.

        Handles European ETF tickers by trying known overrides
        and common exchange suffixes (.DE, .L, etc.).
        """
        # 1. Check override map
        if symbol.upper() in TICKER_OVERRIDES:
            price = PriceFetcher._try_fetch(TICKER_OVERRIDES[symbol.upper()])
            if price is not None:
                return Decimal(str(round(price, 4)))

        # 2. Try the symbol as-is
        price = PriceFetcher._try_fetch(symbol)
        if price is not None:
            return Decimal(str(round(price, 4)))

        # 3. Try with exchange suffixes
        base = symbol.split(".")[0]
        for suffix in EXCHANGE_SUFFIXES:
            candidate = base + suffix
            if candidate == symbol:
                continue
            price = PriceFetcher._try_fetch(candidate)
            if price is not None:
                return Decimal(str(round(price, 4)))

        return None

    @staticmethod
    def fetch_historical_price(
        ticker: str, start: str, end: str, last: bool = False
    ) -> Optional[Decimal]:
        """Fetch a historical closing price within a date window (YYYY-MM-DD).

        Uses the first available close if last=False, or last if last=True.
        Useful for Jan 1 (first trading day) and Dec 31 (last trading day).
        """
        yahoo_symbol = TICKER_OVERRIDES.get(ticker.upper(), ticker)
        try:
            t = yf.Ticker(yahoo_symbol)
            hist = t.history(start=start, end=end)
            if not hist.empty:
                price = float(hist["Close"].iloc[-1 if last else 0])
                return Decimal(str(round(price, 4)))
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_batch(symbols: list[str]) -> dict[str, Optional[Decimal]]:
        """Fetch prices for multiple symbols at once."""
        results: dict[str, Optional[Decimal]] = {}
        for symbol in symbols:
            try:
                results[symbol] = PriceFetcher.fetch_price(symbol)
            except Exception:
                results[symbol] = None
        return results
