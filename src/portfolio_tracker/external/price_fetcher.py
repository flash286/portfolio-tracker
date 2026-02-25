"""Price fetching via yfinance for stocks, ETFs, and bonds."""

from decimal import Decimal
from typing import Optional

import yfinance as yf

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
    def _try_fetch(symbol: str) -> Optional[Decimal]:
        """Try to get a price for a single Yahoo Finance symbol. Returns None on failure."""
        try:
            ticker = yf.Ticker(symbol)
            # Try fast_info first
            try:
                info = ticker.fast_info
                price = getattr(info, "last_price", None)
                if price is not None and price > 0:
                    return Decimal(str(price)).quantize(Decimal("0.0001"))
            except Exception:
                pass
            # Fallback to history
            try:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    return Decimal(str(hist["Close"].iloc[-1])).quantize(Decimal("0.0001"))
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
                return price

        # 2. Try the symbol as-is
        price = PriceFetcher._try_fetch(symbol)
        if price is not None:
            return price

        # 3. Try with exchange suffixes
        base = symbol.split(".")[0]
        for suffix in EXCHANGE_SUFFIXES:
            candidate = base + suffix
            if candidate == symbol:
                continue
            price = PriceFetcher._try_fetch(candidate)
            if price is not None:
                return price

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
                return Decimal(str(hist["Close"].iloc[-1 if last else 0])).quantize(Decimal("0.0001"))
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_price_series(
        ticker: str,
        start: str,
        end: str,
        interval: str = "1wk",
    ) -> dict[str, Decimal]:
        """Fetch historical Close prices for a ticker.

        Tries TICKER_OVERRIDES first, then the raw ticker, then exchange suffixes.

        Args:
            ticker:   Portfolio ticker (e.g. "VWCE").
            start:    ISO date string "YYYY-MM-DD" (inclusive).
            end:      ISO date string "YYYY-MM-DD" (exclusive).
            interval: yfinance interval — "1d", "1wk", or "1mo".

        Returns:
            Dict mapping date strings "YYYY-MM-DD" to Decimal close prices.
            Empty dict if the ticker cannot be resolved or yfinance returns no data.
        """
        ticker_upper = ticker.upper()
        candidates: list[str] = []
        if ticker_upper in TICKER_OVERRIDES:
            candidates.append(TICKER_OVERRIDES[ticker_upper])
        candidates.append(ticker)
        base = ticker.split(".")[0]
        for suffix in EXCHANGE_SUFFIXES:
            candidate = base + suffix
            if candidate not in candidates:
                candidates.append(candidate)

        for symbol in candidates:
            try:
                hist = yf.Ticker(symbol).history(
                    start=start, end=end, interval=interval, auto_adjust=True
                )
                if hist.empty:
                    continue
                result: dict[str, Decimal] = {}
                for ts, close in hist["Close"].items():
                    # yfinance returns tz-aware pandas Timestamps
                    d = ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]
                    result[d] = Decimal(str(close)).quantize(Decimal("0.0001"))
                return result
            except Exception:
                continue
        return {}

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
