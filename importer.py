import csv
import json
import os
from io import StringIO
from urllib import request


FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")


DETECTORS = [
    {
        "name": "groww",
        "hint": lambda h: "avg. buy price" in h and any(c in ("symbol", "quantity") for c in h),
        "parse": lambda r: {
            "symbol": _clean_symbol(r.get("Symbol", r.get("symbol", ""))),
            "qty": int(float(r.get("Quantity", r.get("quantity", 0)))),
            "avg_price": float(r.get("Avg. Buy Price", r.get("avg. buy price", r.get("Buy Price", 0)))),
            "ltp": float(r.get("LTP", r.get("ltp", r.get("Current Price", 0)))),
        },
    },
    {
        "name": "zerodha",
        "hint": lambda h: "trading symbol" in h and "average price" in h,
        "parse": lambda r: {
            "symbol": _clean_symbol(r.get("Trading Symbol", r.get("trading symbol", ""))),
            "qty": int(float(r.get("Quantity", r.get("quantity", 0)))),
            "avg_price": float(r.get("Average Price", r.get("average price", 0))),
            "ltp": float(r.get("Current Price", r.get("current price", r.get("LTP", 0)))),
        },
    },
    {
        "name": "upstox",
        "hint": lambda h: "trading symbol" in h and "buy price" in h,
        "parse": lambda r: {
            "symbol": _clean_symbol(r.get("Trading Symbol", r.get("trading symbol", ""))),
            "qty": int(float(r.get("Quantity", r.get("quantity", 0)))),
            "avg_price": float(r.get("Buy Price", r.get("buy price", 0))),
            "ltp": float(r.get("LTP", r.get("ltp", r.get("Current Price", 0)))),
        },
    },
    {
        "name": "generic",
        "hint": lambda h: "symbol" in h and "quantity" in h,
        "parse": lambda r: {
            "symbol": _clean_symbol(r.get("Symbol", r.get("symbol", r.get("Ticker", "")))),
            "qty": int(float(r.get("Quantity", r.get("qty", r.get("Qty", 0))))),
            "avg_price": float(r.get("Avg Price", r.get("avg_price", r.get("Buy Price", r.get("Price", 0))))),
            "ltp": float(r.get("LTP", r.get("ltp", r.get("Current Price", 0)))),
        },
    },
]


def _clean_symbol(s: str) -> str:
    s = s.strip().upper()
    for suffix in [".NS", ".NSE", ".BSE", " ", "-EQ"]:
        s = s.replace(suffix, "")
    return s.strip()


def _finnhub_quote(symbol: str) -> float | None:
    if not FINNHUB_KEY:
        return None
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}.NSE&token={FINNHUB_KEY}"
        with request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            c = data.get("c")
            return float(c) if c and c > 0 else None
    except Exception:
        return None


def detect_format(headers: list[str]) -> dict | None:
    cleaned = [h.strip().lower() for h in headers]
    for d in DETECTORS:
        if d["hint"](cleaned):
            return d
    return None


def parse_csv(content: str) -> dict:
    result = {"format": "unknown", "holdings": [], "errors": []}
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        result["errors"].append("Empty or invalid CSV")
        return result

    detector = detect_format(reader.fieldnames)
    if not detector:
        result["errors"].append(f"Unrecognised format. Columns: {', '.join(reader.fieldnames)}")
        return result

    result["format"] = detector["name"]
    for i, row in enumerate(reader, 1):
        try:
            parsed = detector["parse"](row)
            if not parsed["symbol"] or parsed["qty"] <= 0:
                continue
            current_price = parsed["ltp"]
            fp = _finnhub_quote(parsed["symbol"])
            if fp:
                current_price = fp
            result["holdings"].append({
                "symbol": parsed["symbol"],
                "qty": parsed["qty"],
                "avg_price": parsed["avg_price"],
                "current_price": current_price if current_price > 0 else parsed["avg_price"],
            })
        except (ValueError, TypeError) as e:
            result["errors"].append(f"Row {i}: {e}")

    return result
