import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from env_utils import load_local_env

load_local_env()

import db
import importer
from auth_bp import auth_bp, token_required
from push_utils import send_push_to_user, get_vapid_public_key

DATA_DIR = Path(__file__).parent / "data"

app = Flask(__name__, static_folder="static", static_url_path="")
app.register_blueprint(auth_bp)

db.init_db()
db.migrate_db()


@app.route("/api/stats")
@token_required
def api_stats():
    user_id = request.current_user["user_id"]
    user = db.get_user_by_id(user_id)
    holdings = db.get_holdings(user_id)
    cash = db.get_cash_balance(user_id)
    events = db.get_events(user_id)
    trades = db.get_trades(user_id)
    holdings_count = sum(h["qty"] for h in holdings.values())
    holdings_symbols = len(holdings)

    today = datetime.now().strftime("%Y-%m-%d")
    headlines_today = sum(
        1 for e in events
        if e.get("timestamp", "").startswith(today)
        and e.get("stage") == "analysis"
        and e.get("status") == "complete"
    )

    return jsonify({
        "cash": cash,
        "holdings_count": holdings_count,
        "holdings_symbols": holdings_symbols,
        "headlines_today": headlines_today,
        "trades_count": len(trades),
        "pending_count": db.pending_count(user_id),
        "has_telegram": bool(user and user.get("telegram_chat_id")),
    })


@app.route("/api/portfolio")
@token_required
def api_portfolio():
    user_id = request.current_user["user_id"]
    cash = db.get_cash_balance(user_id)
    holdings = db.get_holdings(user_id)

    holdings_list = []
    for symbol, data in holdings.items():
        avg = data["avg_price"]
        cur = data["current_price"] if data["current_price"] > 0 else avg
        qty = data["qty"]
        invest = round(qty * avg, 2)
        curr_val = round(qty * cur, 2)
        pnl = round(curr_val - invest, 2)
        pnl_pct = round((cur - avg) / avg * 100, 2) if avg > 0 else 0
        holdings_list.append({
            "symbol": symbol,
            "qty": qty,
            "avg_price": avg,
            "current_price": cur,
            "invested": invest,
            "current_value": curr_val,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "price_updated_at": data.get("price_updated_at"),
        })

    holdings_value = sum(h["current_value"] for h in holdings_list)
    total_pnl = sum(h["pnl"] for h in holdings_list)
    total_invested = round(sum(h["invested"] for h in holdings_list), 2)
    return jsonify({
        "cash": round(cash, 2),
        "holdings": holdings_list,
        "total_value": round(cash + holdings_value, 2),
        "total_invested": total_invested,
        "total_pnl": total_pnl,
    })


@app.route("/api/portfolio/import", methods=["POST"])
@token_required
def api_portfolio_import():
    user_id = request.current_user["user_id"]
    content_type = request.content_type or ""
    if "multipart/form-data" in content_type:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file uploaded"}), 400
        raw = file.read().decode("utf-8", errors="replace")
    else:
        data = request.get_json(silent=True) or {}
        raw = data.get("csv", "")
        if not raw:
            return jsonify({"error": "No csv data"}), 400
    result = importer.parse_csv(raw)
    if result["errors"]:
        return jsonify(result), 400
    db.add_holding_batch(user_id, result["holdings"])
    db.log_portfolio_event(user_id, "import", details=f"Imported {len(result['holdings'])} holdings")
    return jsonify({"ok": True, "count": len(result["holdings"]), "format": result["format"]})


@app.route("/api/portfolio/refresh-prices", methods=["POST"])
@token_required
def api_portfolio_refresh():
    user_id = request.current_user["user_id"]
    holdings = db.get_holdings(user_id)
    count = 0
    for symbol in holdings:
        price = importer._finnhub_quote(symbol)
        if price:
            db.update_current_price(user_id, symbol, price)
            count += 1
    return jsonify({"ok": True, "updated": count})


@app.route("/api/headlines")
@token_required
def api_headlines():
    user_id = request.current_user["user_id"]
    filter_type = request.args.get("filter", "all")
    events = db.get_events(user_id)

    headlines = []
    for e in events:
        if e.get("stage") != "analysis" or e.get("status") != "complete":
            continue
        try:
            score = int(e.get("panic_score", 0))
        except (ValueError, TypeError):
            score = 0
        action = e.get("action", "IGNORE")

        if score >= 80:
            importance = "critical"
        elif score >= 50:
            importance = "important"
        else:
            importance = "normal"

        if filter_type != "all" and importance != filter_type:
            continue

        headlines.append({
            "timestamp": e.get("timestamp", ""),
            "source": e.get("source", ""),
            "headline": e.get("headline", ""),
            "company": e.get("company", ""),
            "panic_score": score,
            "action": action,
            "importance": importance,
        })

    return jsonify(headlines)


@app.route("/api/trades")
@token_required
def api_trades():
    user_id = request.current_user["user_id"]
    trades = db.get_trades(user_id)
    return jsonify(trades)


@app.route("/api/portfolio-history")
@token_required
def api_portfolio_history():
    user_id = request.current_user["user_id"]
    events = list(db.get_portfolio_events(user_id))
    live_holdings = db.get_holdings(user_id)

    holdings = {}
    history = []
    for ev in events:
        sym = ev.get("symbol") or ""
        qty_change = ev.get("qty_change", 0) or 0
        if sym and qty_change != 0:
            cur = holdings.get(sym, 0)
            new_qty = cur + qty_change
            if new_qty <= 0:
                holdings.pop(sym, None)
            else:
                holdings[sym] = new_qty

        h_value = 0.0
        for sym, qty in holdings.items():
            h_info = live_holdings.get(sym, {})
            price = h_info.get("current_price", 0) or h_info.get("avg_price", 0)
            h_value += qty * price

        history.append({
            "timestamp": ev["timestamp"],
            "cash": round(ev["running_cash"], 2),
            "holdings_value": round(h_value, 2),
            "total": round(ev["running_cash"] + h_value, 2),
        })

    return jsonify(history)


@app.route("/api/pending")
@token_required
def api_pending():
    user_id = request.current_user["user_id"]
    pending = db.get_all_pending(user_id)
    return jsonify(pending)


@app.route("/api/push/subscribe", methods=["POST"])
@token_required
def push_subscribe():
    user_id = request.current_user["user_id"]
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "")
    keys = data.get("keys", {})
    if not endpoint:
        return jsonify({"error": "endpoint required"}), 400
    db.save_push_subscription(user_id, endpoint, keys.get("auth", ""), keys.get("p256dh", ""))
    return jsonify({"ok": True})


@app.route("/api/push/unsubscribe", methods=["POST"])
@token_required
def push_unsubscribe():
    user_id = request.current_user["user_id"]
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "")
    if endpoint:
        db.delete_push_subscription(user_id, endpoint)
    else:
        db.delete_all_push_subscriptions(user_id)
    return jsonify({"ok": True})


@app.route("/api/push/vapid-key")
def push_vapid_key():
    return jsonify({"public_key": get_vapid_public_key()})


@app.route("/api/push/test")
@token_required
def push_test():
    user_id = request.current_user["user_id"]
    ok = send_push_to_user(user_id, "Test Notification", "This is a test push from Aether.")
    return jsonify({"sent": ok})


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
