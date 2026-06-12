from datetime import datetime, time

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None

    class ZoneInfoNotFoundError(Exception):
        pass

from settings import settings


COMPANY_REGISTRY = {
    "RELIANCE": {"symbol": "RELIANCE", "exchange": "NSE"},
    "RELIANCE INDUSTRIES": {"symbol": "RELIANCE", "exchange": "NSE"},
    "ADANI": {"symbol": "ADANIENT", "exchange": "NSE"},
    "ADANI GROUP": {"symbol": "ADANIENT", "exchange": "NSE"},
    "ADANI ENTERPRISES": {"symbol": "ADANIENT", "exchange": "NSE"},
    "TATA MOTORS": {"symbol": "TATAMOTORS", "exchange": "NSE"},
    "TATA": {"symbol": "TATAMOTORS", "exchange": "NSE"},
    "INFOSYS": {"symbol": "INFY", "exchange": "NSE"},
    "INFY": {"symbol": "INFY", "exchange": "NSE"},
    "HDFC BANK": {"symbol": "HDFCBANK", "exchange": "NSE"},
}


def resolve_company(company_name):
    lookup = (company_name or "").strip().upper()

    if lookup in COMPANY_REGISTRY:
        return COMPANY_REGISTRY[lookup]

    for alias, company in COMPANY_REGISTRY.items():
        if alias in lookup or lookup in alias:
            return company

    return None


def is_market_open(now=None):
    current = now or _get_india_now()
    if current.weekday() >= 5:
        return False

    open_at = time(settings.market_open_hour, settings.market_open_minute)
    close_at = time(settings.market_close_hour, settings.market_close_minute)
    return open_at <= current.time() <= close_at


def _get_india_now():
    if ZoneInfo is not None:
        for tz_name in ("Asia/Kolkata", "Asia/Calcutta"):
            try:
                return datetime.now(ZoneInfo(tz_name))
            except ZoneInfoNotFoundError:
                continue

    return datetime.now()


def validate_trade_candidate(analysis, portfolio):
    reasons = []
    company_info = resolve_company(analysis["company"])
    action = analysis["action"]
    panic_score = analysis["panic_score"]

    if not company_info:
        reasons.append("Company is not mapped to a supported NSE/BSE listing.")

    if action == "SELL" and panic_score < settings.panic_threshold:
        reasons.append(f"Panic score below threshold {settings.panic_threshold}.")

    if action == "IGNORE":
        reasons.append("AI recommended IGNORE.")

    if not is_market_open():
        reasons.append("Market is currently closed.")

    cash_inr = float(portfolio.get("cash_inr", 0))
    holdings = portfolio.get("holdings", {})

    if action == "BUY":
        required_cash = settings.estimated_trade_value_inr + settings.min_cash_buffer_inr
        if cash_inr < required_cash:
            reasons.append("Available cash is below required trade value plus buffer.")

    if action == "SELL" and company_info and not settings.allow_sell_without_holdings:
        available_qty = int(holdings.get(company_info["symbol"], 0))
        if available_qty < settings.trade_quantity:
            reasons.append("Insufficient holdings available for sell order.")

    return {
        "approved": not reasons,
        "reasons": reasons,
        "company_info": company_info,
        "quantity": settings.trade_quantity,
    }
