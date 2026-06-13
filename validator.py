import re
from datetime import datetime, time, timedelta, timezone
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None

    class ZoneInfoNotFoundError(Exception):
        pass

from settings import settings


COMPANY_REGISTRY = {
    "RELIANCE": {"symbol": "RELIANCE", "exchange": "NSE"},
    "RELIANCE INDUSTRIES": {"symbol": "RELIANCE", "exchange": "NSE"},
    "RIL": {"symbol": "RELIANCE", "exchange": "NSE"},
    "ADANI": {"symbol": "ADANIENT", "exchange": "NSE"},
    "ADANI GROUP": {"symbol": "ADANIENT", "exchange": "NSE"},
    "ADANI ENTERPRISES": {"symbol": "ADANIENT", "exchange": "NSE"},
    "ADANI PORTS": {"symbol": "ADANIPORTS", "exchange": "NSE"},
    "ADANI POWER": {"symbol": "ADANIPOWER", "exchange": "NSE"},
    "ADANI GREEN": {"symbol": "ADANIGREEN", "exchange": "NSE"},
    "ADANI TOTAL GAS": {"symbol": "ADANITOTAL", "exchange": "NSE"},
    "TATA MOTORS": {"symbol": "TATAMOTORS", "exchange": "NSE"},
    "TATA": {"symbol": "TATAMOTORS", "exchange": "NSE"},
    "TATA STEEL": {"symbol": "TATASTEEL", "exchange": "NSE"},
    "TATA CONSULTANCY": {"symbol": "TCS", "exchange": "NSE"},
    "TCS": {"symbol": "TCS", "exchange": "NSE"},
    "TATA POWER": {"symbol": "TATAPOWER", "exchange": "NSE"},
    "TATA CONSUMER": {"symbol": "TATACONSUM", "exchange": "NSE"},
    "TATA COMMUNICATIONS": {"symbol": "TATACOMM", "exchange": "NSE"},
    "TATA ELXSI": {"symbol": "TATAELXSI", "exchange": "NSE"},
    "INFOSYS": {"symbol": "INFY", "exchange": "NSE"},
    "INFY": {"symbol": "INFY", "exchange": "NSE"},
    "HDFC BANK": {"symbol": "HDFCBANK", "exchange": "NSE"},
    "HDFC": {"symbol": "HDFCBANK", "exchange": "NSE"},
    "HDFC LIFE": {"symbol": "HDFCLIFE", "exchange": "NSE"},
    "HDFC ASSET": {"symbol": "HDFCAMC", "exchange": "NSE"},
    "ICICI BANK": {"symbol": "ICICIBANK", "exchange": "NSE"},
    "ICICI": {"symbol": "ICICIBANK", "exchange": "NSE"},
    "ICICI PRUDENTIAL": {"symbol": "ICICIPRULI", "exchange": "NSE"},
    "SBI": {"symbol": "SBIN", "exchange": "NSE"},
    "STATE BANK": {"symbol": "SBIN", "exchange": "NSE"},
    "AXIS BANK": {"symbol": "AXISBANK", "exchange": "NSE"},
    "AXIS": {"symbol": "AXISBANK", "exchange": "NSE"},
    "KOTAK MAHINDRA": {"symbol": "KOTAKBANK", "exchange": "NSE"},
    "KOTAK": {"symbol": "KOTAKBANK", "exchange": "NSE"},
    "YES BANK": {"symbol": "YESBANK", "exchange": "NSE"},
    "MARUTI": {"symbol": "MARUTI", "exchange": "NSE"},
    "MARUTI SUZUKI": {"symbol": "MARUTI", "exchange": "NSE"},
    "MSIL": {"symbol": "MARUTI", "exchange": "NSE"},
    "MAHINDRA": {"symbol": "M&M", "exchange": "NSE"},
    "MAHINDRA & MAHINDRA": {"symbol": "M&M", "exchange": "NSE"},
    "M&M": {"symbol": "M&M", "exchange": "NSE"},
    "BAJAJ FINANCE": {"symbol": "BAJFINANCE", "exchange": "NSE"},
    "BAJAJ FINSERV": {"symbol": "BAJAJFINSV", "exchange": "NSE"},
    "BAJAJ AUTO": {"symbol": "BAJAJ-AUTO", "exchange": "NSE"},
    "BAJAJ": {"symbol": "BAJAJ-AUTO", "exchange": "NSE"},
    "WIPRO": {"symbol": "WIPRO", "exchange": "NSE"},
    "HCL": {"symbol": "HCLTECH", "exchange": "NSE"},
    "HCL TECH": {"symbol": "HCLTECH", "exchange": "NSE"},
    "HCL TECHNOLOGIES": {"symbol": "HCLTECH", "exchange": "NSE"},
    "TECH MAHINDRA": {"symbol": "TECHM", "exchange": "NSE"},
    "NTPC": {"symbol": "NTPC", "exchange": "NSE"},
    "NATIONAL THERMAL": {"symbol": "NTPC", "exchange": "NSE"},
    "ONGC": {"symbol": "ONGC", "exchange": "NSE"},
    "OIL AND NATURAL GAS": {"symbol": "ONGC", "exchange": "NSE"},
    "COAL INDIA": {"symbol": "COALINDIA", "exchange": "NSE"},
    "POWER GRID": {"symbol": "POWERGRID", "exchange": "NSE"},
    "L&T": {"symbol": "LT", "exchange": "NSE"},
    "LARSEN": {"symbol": "LT", "exchange": "NSE"},
    "LARSEN & TOUBRO": {"symbol": "LT", "exchange": "NSE"},
    "ITC": {"symbol": "ITC", "exchange": "NSE"},
    "HUL": {"symbol": "HINDUNILVR", "exchange": "NSE"},
    "HINDUSTAN UNILEVER": {"symbol": "HINDUNILVR", "exchange": "NSE"},
    "ASIAN PAINTS": {"symbol": "ASIANPAINT", "exchange": "NSE"},
    "NESTLE": {"symbol": "NESTLEIND", "exchange": "NSE"},
    "NESTLE INDIA": {"symbol": "NESTLEIND", "exchange": "NSE"},
    "BHARTI AIRTEL": {"symbol": "BHARTIARTL", "exchange": "NSE"},
    "AIRTEL": {"symbol": "BHARTIARTL", "exchange": "NSE"},
    "JIO": {"symbol": "JIOFIN", "exchange": "NSE"},
    "RELIANCE JIO": {"symbol": "JIOFIN", "exchange": "NSE"},
    "SUN PHARMA": {"symbol": "SUNPHARMA", "exchange": "NSE"},
    "SUN PHARMACEUTICAL": {"symbol": "SUNPHARMA", "exchange": "NSE"},
    "DR REDDY": {"symbol": "DRREDDY", "exchange": "NSE"},
    "DR. REDDY": {"symbol": "DRREDDY", "exchange": "NSE"},
    "CIPLA": {"symbol": "CIPLA", "exchange": "NSE"},
    "DIVIS": {"symbol": "DIVISLAB", "exchange": "NSE"},
    "DIVI'S": {"symbol": "DIVISLAB", "exchange": "NSE"},
    "APOLLO HOSPITALS": {"symbol": "APOLLOHOSP", "exchange": "NSE"},
    "APOLLO": {"symbol": "APOLLOHOSP", "exchange": "NSE"},
    "HINDALCO": {"symbol": "HINDALCO", "exchange": "NSE"},
    "HINDALCO INDUSTRIES": {"symbol": "HINDALCO", "exchange": "NSE"},
    "JSW STEEL": {"symbol": "JSWSTEEL", "exchange": "NSE"},
    "JSW": {"symbol": "JSWSTEEL", "exchange": "NSE"},
    "ULTRATECH": {"symbol": "ULTRACEMCO", "exchange": "NSE"},
    "ULTRATECH CEMENT": {"symbol": "ULTRACEMCO", "exchange": "NSE"},
    "GRASIM": {"symbol": "GRASIM", "exchange": "NSE"},
    "EICHER MOTORS": {"symbol": "EICHERMOT", "exchange": "NSE"},
    "ROYAL ENFIELD": {"symbol": "EICHERMOT", "exchange": "NSE"},
    "HERO MOTOCORP": {"symbol": "HEROMOTOCO", "exchange": "NSE"},
    "HERO": {"symbol": "HEROMOTOCO", "exchange": "NSE"},
    "BRITANNIA": {"symbol": "BRITANNIA", "exchange": "NSE"},
    "TITAN": {"symbol": "TITAN", "exchange": "NSE"},
    "TITAN COMPANY": {"symbol": "TITAN", "exchange": "NSE"},
    "AVENUE SUPERMARTS": {"symbol": "DMART", "exchange": "NSE"},
    "DMART": {"symbol": "DMART", "exchange": "NSE"},
    "ZOMATO": {"symbol": "ZOMATO", "exchange": "NSE"},
    "PAYTM": {"symbol": "PAYTM", "exchange": "NSE"},
    "ONE97": {"symbol": "PAYTM", "exchange": "NSE"},
    "VEDANTA": {"symbol": "VEDL", "exchange": "NSE"},
    "VODAFONE": {"symbol": "IDEA", "exchange": "NSE"},
    "VODAFONE IDEA": {"symbol": "IDEA", "exchange": "NSE"},
    "IDEA": {"symbol": "IDEA", "exchange": "NSE"},
}

_WORD_RE = re.compile(r"[A-Z0-9&.]+")


def resolve_company(company_name):
    lookup = (company_name or "").strip().upper()
    if not lookup:
        return None

    if lookup in COMPANY_REGISTRY:
        return COMPANY_REGISTRY[lookup]

    input_tokens = set(_WORD_RE.findall(lookup))

    best = None
    best_count = -1
    for alias, company in COMPANY_REGISTRY.items():
        alias_tokens = set(_WORD_RE.findall(alias))
        if alias_tokens and alias_tokens.issubset(input_tokens):
            if len(alias_tokens) > best_count:
                best_count = len(alias_tokens)
                best = company

    if best:
        return best

    return None


def is_market_open(now=None):
    current = now or _get_india_now()
    if current.weekday() >= 5:
        return False

    open_at = time(settings.market_open_hour, settings.market_open_minute)
    close_at = time(settings.market_close_hour, settings.market_close_minute)
    return open_at <= current.time() <= close_at


IST = timezone(timedelta(hours=5, minutes=30))


def _get_india_now():
    if ZoneInfo is not None:
        for tz_name in ("Asia/Kolkata", "Asia/Calcutta"):
            try:
                return datetime.now(ZoneInfo(tz_name))
            except ZoneInfoNotFoundError:
                continue

    return datetime.now(IST)


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

    if action == "BUY" and company_info:
        symbol = company_info["symbol"]
        holding = holdings.get(symbol, {})
        current_price = holding.get("current_price", 0) if isinstance(holding, dict) else 0
        if current_price <= 0:
            current_price = settings.estimated_trade_value_inr / settings.trade_quantity
        required_cash = current_price * settings.trade_quantity + settings.min_cash_buffer_inr
        if cash_inr < required_cash:
            reasons.append(
                f"Available cash (₹{cash_inr:,.0f}) below required "
                f"₹{required_cash:,.0f} ({settings.trade_quantity} × ₹{current_price:,.2f} + buffer)"
            )

    if action == "SELL" and company_info and not settings.allow_sell_without_holdings:
        holding = holdings.get(company_info["symbol"], {})
        available_qty = int(holding.get("qty", 0)) if isinstance(holding, dict) else int(holding)
        if available_qty < settings.trade_quantity:
            reasons.append("Insufficient holdings available for sell order.")

    return {
        "approved": not reasons,
        "reasons": reasons,
        "company_info": company_info,
        "quantity": settings.trade_quantity,
    }
