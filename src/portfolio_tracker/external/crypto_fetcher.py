"""Crypto price fetching via CoinGecko free API."""

from decimal import Decimal
from typing import Optional

import requests

from ..core.exceptions import PriceFetchError

# Map common crypto symbols to CoinGecko IDs
SYMBOL_TO_COINGECKO = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "LTC": "litecoin",
    "BNB": "binancecoin",
}

COINGECKO_API = "https://api.coingecko.com/api/v3"


class CryptoFetcher:
    """Fetches crypto prices via CoinGecko (free, no API key)."""

    @staticmethod
    def fetch_price(symbol: str, currency: str = "eur") -> Optional[Decimal]:
        """Fetch current price for a single crypto symbol."""
        coin_id = SYMBOL_TO_COINGECKO.get(symbol.upper())
        if coin_id is None:
            # Try using symbol as-is (lowercase) as CoinGecko ID
            coin_id = symbol.lower()

        try:
            resp = requests.get(
                f"{COINGECKO_API}/simple/price",
                params={"ids": coin_id, "vs_currencies": currency},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if coin_id in data and currency in data[coin_id]:
                return Decimal(str(data[coin_id][currency]))
            return None
        except Exception as e:
            raise PriceFetchError(f"Failed to fetch crypto price for {symbol}: {e}")

    @staticmethod
    def fetch_batch(symbols: list[str], currency: str = "eur") -> dict[str, Optional[Decimal]]:
        """Fetch prices for multiple crypto symbols."""
        coin_ids = []
        symbol_to_id = {}
        for s in symbols:
            s_upper = s.upper()
            coin_id = SYMBOL_TO_COINGECKO.get(s_upper, s.lower())
            coin_ids.append(coin_id)
            symbol_to_id[s_upper] = coin_id

        results: dict[str, Optional[Decimal]] = {}
        try:
            resp = requests.get(
                f"{COINGECKO_API}/simple/price",
                params={"ids": ",".join(coin_ids), "vs_currencies": currency},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for symbol, coin_id in symbol_to_id.items():
                if coin_id in data and currency in data[coin_id]:
                    results[symbol] = Decimal(str(data[coin_id][currency]))
                else:
                    results[symbol] = None
        except Exception:
            for s in symbols:
                results[s.upper()] = None
        return results
