"""Price fetching via yfinance for stocks, ETFs, and bonds."""

from decimal import Decimal
from typing import Optional

import yfinance as yf

from ..core.exceptions import PriceFetchError


class PriceFetcher:
    """Fetches prices for stocks, ETFs, and bonds via Yahoo Finance."""

    @staticmethod
    def fetch_price(symbol: str) -> Optional[Decimal]:
        """Fetch current price for a single symbol."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = getattr(info, "last_price", None)
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price is not None:
                return Decimal(str(round(price, 4)))
            return None
        except Exception as e:
            raise PriceFetchError(f"Failed to fetch price for {symbol}: {e}")

    @staticmethod
    def fetch_batch(symbols: list[str]) -> dict[str, Optional[Decimal]]:
        """Fetch prices for multiple symbols at once."""
        results: dict[str, Optional[Decimal]] = {}
        for symbol in symbols:
            try:
                results[symbol] = PriceFetcher.fetch_price(symbol)
            except PriceFetchError:
                results[symbol] = None
        return results
