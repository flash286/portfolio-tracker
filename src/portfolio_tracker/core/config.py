"""Application configuration — loaded from config.json at project root."""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    country: str = "DE"
    freistellungsauftrag: Decimal = Decimal("2000")
    abgeltungssteuer_rate: Decimal = Decimal("0.25")
    soli_rate: Decimal = Decimal("0.055")
    kirchensteuer: bool = False
    currency: str = "EUR"
    default_exchange_suffix: str = ".DE"
    user_name: str = ""


_DEFAULTS = AppConfig()
_cached: Optional[AppConfig] = None


def _config_path() -> Path:
    from ..data.database import _find_project_root
    return _find_project_root() / "config.json"


def get_config() -> AppConfig:
    global _cached
    if _cached is not None:
        return _cached
    path = _config_path()
    if not path.exists():
        _cached = AppConfig()
        return _cached
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _cached = AppConfig(
            country=data.get("country", _DEFAULTS.country),
            freistellungsauftrag=Decimal(str(data.get("freistellungsauftrag", 2000))),
            abgeltungssteuer_rate=Decimal(str(data.get("abgeltungssteuer_rate", 0.25))),
            soli_rate=Decimal(str(data.get("soli_rate", 0.055))),
            kirchensteuer=bool(data.get("kirchensteuer", False)),
            currency=data.get("currency", _DEFAULTS.currency),
            default_exchange_suffix=data.get("default_exchange_suffix", _DEFAULTS.default_exchange_suffix),
            user_name=data.get("user_name", ""),
        )
    except Exception:
        _cached = AppConfig()
    return _cached


def save_config(cfg: AppConfig) -> None:
    global _cached
    _cached = cfg
    data = {
        "country": cfg.country,
        "freistellungsauftrag": float(cfg.freistellungsauftrag),
        "abgeltungssteuer_rate": float(cfg.abgeltungssteuer_rate),
        "soli_rate": float(cfg.soli_rate),
        "kirchensteuer": cfg.kirchensteuer,
        "currency": cfg.currency,
        "default_exchange_suffix": cfg.default_exchange_suffix,
        "user_name": cfg.user_name,
    }
    _config_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
