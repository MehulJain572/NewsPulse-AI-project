import os
from dataclasses import dataclass

from env_utils import load_local_env

load_local_env()


def _env_int(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    scan_interval_seconds: int = _env_int("SCAN_INTERVAL_SECONDS", 60)
    analysis_pause_seconds: float = _env_float("ANALYSIS_PAUSE_SECONDS", 1)
    panic_threshold: int = _env_int("PANIC_THRESHOLD", 80)
    trade_quantity: int = _env_int("TRADE_QUANTITY", 100)
    stop_loss_pct: float = _env_float("STOP_LOSS_PCT", 2.5)
    estimated_trade_value_inr: float = _env_float("ESTIMATED_TRADE_VALUE_INR", 100000)
    min_cash_buffer_inr: float = _env_float("MIN_CASH_BUFFER_INR", 10000)
    broker_mode: str = os.getenv("BROKER_MODE", "paper").strip().lower()
    allow_sell_without_holdings: bool = os.getenv("ALLOW_SELL_WITHOUT_HOLDINGS", "false").lower() == "true"
    market_open_hour: int = _env_int("MARKET_OPEN_HOUR", 9)
    market_open_minute: int = _env_int("MARKET_OPEN_MINUTE", 15)
    market_close_hour: int = _env_int("MARKET_CLOSE_HOUR", 15)
    market_close_minute: int = _env_int("MARKET_CLOSE_MINUTE", 30)


settings = Settings()
