import time
import threading
from datetime import datetime
from notifier import send_approval_request, bot
from brain import analyze_news
from env_utils import env_status
from executor import execute_trade
from fetcher import get_all_headlines
import db
from settings import settings
from state import SeenNewsStore, PortfolioStore, PendingTradeQueue
from validator import validate_trade_candidate, is_market_open


def process_news_item(news_item, user_id, seen_store, portfolio_store, pending_queue):
    headline = news_item["headline"]
    fingerprint = news_item["fingerprint"]

    if seen_store.has_seen(fingerprint):
        return

    db.log_event_db(user_id, "ingestion", "fresh", news_item.get("source", ""),
                     headline, "", 0, "", "")

    print(f"\n[ANALYZE] [{user_id}] {headline[:90]}...")
    analysis = analyze_news(news_item)

    if not analysis:
        db.log_event_db(user_id, "analysis", "failed", news_item.get("source", ""),
                         headline, "LLM analysis returned no result", 0, "", "")
        return

    seen_store.mark_seen(fingerprint)
    db.log_event_db(user_id, "analysis", "complete", news_item.get("source", ""),
                     headline, analysis.get("company", ""), analysis.get("panic_score", 0),
                     analysis.get("action", ""), analysis.get("reason", ""))

    validation = validate_trade_candidate(analysis, portfolio_store.snapshot())

    print(
        f"    -> [{user_id}] {analysis['company']} | panic={analysis['panic_score']} | action={analysis['action']} "
        f"| valid={validation['approved']}"
    )

    if analysis["panic_score"] >= settings.panic_threshold:
        company = analysis['company']

        request_id = send_approval_request(
            user_id,
            company,
            analysis['action'],
            analysis['panic_score'],
            analysis.get('reason', 'Critical Market Event Detected'),
            headline=news_item.get("headline", ""),
            estimated_value=settings.estimated_trade_value_inr,
        )

        print(f"    ⚠️ [{user_id}] [ALERT] High Panic ({analysis['panic_score']})! Approval request #{request_id} sent. Non-blocking — trade will execute once approved.")

        pending_queue.enqueue(
            news_item, analysis, validation,
            status='pending_approval', approval_request_id=request_id,
        )
        db.log_event_db(user_id, "authorization", "pending", news_item.get("source", ""),
                         headline, company, analysis.get("panic_score", 0),
                         analysis.get("action", ""), f"Approval request #{request_id}")
        return

    if not validation["approved"]:
        reasons = validation["reasons"]
        if reasons == ["Market is currently closed."]:
            pending_queue.enqueue(news_item, analysis, validation)
            print(f"    📌 [{user_id}] [QUEUED] Market closed. Trade for {analysis['company']} queued for next market open.")
            db.log_event_db(user_id, "validation", "queued", news_item.get("source", ""),
                             headline, analysis.get("company", ""), analysis.get("panic_score", 0),
                             analysis.get("action", ""), "Market closed; queued for next open")
        else:
            db.log_event_db(user_id, "validation", "rejected", news_item.get("source", ""),
                             headline, analysis.get("company", ""), analysis.get("panic_score", 0),
                             analysis.get("action", ""), "; ".join(reasons))
        return

    if analysis["action"] == "IGNORE":
        return

    trade_result = execute_trade(news_item, analysis, validation, portfolio_store)

    db.log_trade_db(user_id, news_item.get("source", ""), headline,
                     analysis.get("company", ""),
                     trade_result.get("symbol", ""),
                     analysis.get("action", ""),
                     analysis.get("panic_score", 0),
                     trade_result.get("quantity", 0),
                     trade_result.get("estimated_value_inr", 0),
                     trade_result.get("status", ""),
                     trade_result.get("details", ""),
                     execution_price=trade_result.get("execution_price", 0))

    if trade_result["status"] in {"simulated", "placed"}:
        print(
            f"\n🔥 [{user_id}] [TRADE EXECUTED] {analysis['company']} | {analysis['action']} {trade_result['quantity']} "
            f"shares | stop-loss {trade_result['stop_loss_pct']}%"
        )


def revalidate_and_execute(pending_entry, portfolio_store, user_id):
    news_item = pending_entry["news_item"]
    analysis = pending_entry["analysis"]
    validation = pending_entry["validation"]

    fresh_portfolio = portfolio_store.snapshot()
    fresh_validation = validate_trade_candidate(analysis, fresh_portfolio)

    if not is_market_open():
        print(f"    ⏸️ [{user_id}] Market closed — cannot execute queued {analysis['company']} trade yet.")
        return False

    created_raw = pending_entry.get("created_at", "")
    if created_raw:
        try:
            created_dt = datetime.fromisoformat(created_raw)
            now_dt = datetime.now(created_dt.tzinfo) if created_dt.tzinfo else datetime.now()
            if (now_dt - created_dt).total_seconds() > 86400:
                print(f"    ⏰ [{user_id}] Queued trade for {analysis['company']} is stale (>24h). Skipping.")
                db.log_event_db(user_id, "validation", "expired", news_item.get("source", ""),
                                news_item.get("headline", ""), analysis.get("company", ""),
                                analysis.get("panic_score", 0), analysis.get("action", ""),
                                "Queued trade expired (>24h old)")
                return False
        except (ValueError, TypeError):
            pass

    if not fresh_validation["approved"]:
        reasons = "; ".join(fresh_validation["reasons"])
        print(f"    ⏰ [{user_id}] Re-validation failed for {analysis['company']}: {reasons}")
        db.log_event_db(user_id, "validation", "rejected", news_item.get("source", ""),
                        news_item.get("headline", ""), analysis.get("company", ""),
                        analysis.get("panic_score", 0), analysis.get("action", ""), reasons)
        return False

    if analysis["action"] == "IGNORE":
        return False

    trade_result = execute_trade(news_item, analysis, fresh_validation, portfolio_store)
    db.log_trade_db(user_id, news_item.get("source", ""), news_item.get("headline", ""),
                     analysis.get("company", ""),
                     trade_result.get("symbol", ""),
                     analysis.get("action", ""),
                     analysis.get("panic_score", 0),
                     trade_result.get("quantity", 0),
                     trade_result.get("estimated_value_inr", 0),
                     trade_result.get("status", ""),
                     trade_result.get("details", ""),
                     execution_price=trade_result.get("execution_price", 0))
    if trade_result["status"] in {"simulated", "placed"}:
        print(f"\n🔥 [{user_id}] [QUEUED TRADE EXECUTED] {analysis['company']} | {analysis['action']} {trade_result['quantity']} shares | stop-loss {trade_result['stop_loss_pct']}%")
    return True


def run_news_pulse_agent():
    db.init_db()
    print("\n" + "=" * 60)
    print("AETHER TRADING AGENT IS LIVE (DEMO MODE)")
    print("=" * 60)

    if bot is not None:
        threading.Thread(target=bot.infinity_polling, daemon=True).start()
        print("[INFO] Telegram Bot active.")
    else:
        print("[INFO] Telegram disabled (no bot token).")

    market_was_open = is_market_open()
    user_stores = {}

    while True:
        market_is_open = is_market_open()

        users = db.get_all_active_users()
        if not users:
            print("[LOG] No active users registered. Waiting...")
            time.sleep(30)
            continue

        for user in users:
            uid = user["id"]
            if uid not in user_stores:
                user_stores[uid] = {
                    "seen": SeenNewsStore(uid),
                    "portfolio": PortfolioStore(uid),
                    "pending": PendingTradeQueue(uid),
                    "market_was_open": market_was_open,
                }
            stores = user_stores[uid]

            # Process pending approval requests — check for approvals, rejections, or expiry
            for pending in db.get_pending_approval_trades(uid):
                ar_status = pending["ar_status"]
                ar_company = pending["ar_company"]
                ar_action = pending["ar_action"]
                ar_panic_score = pending["ar_panic_score"]
                ar_expires_at = pending["ar_expires_at"]

                # Check expiry first
                expired = False
                if ar_expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(ar_expires_at)
                        now_dt = datetime.now(expires_dt.tzinfo) if expires_dt.tzinfo else datetime.now()
                        if now_dt > expires_dt:
                            db.update_approval_status(pending["approval_request_id"], "expired")
                            db.update_pending_status(pending["id"], "expired")
                            print(f"    ⏰ [{uid}] Approval request #{pending['approval_request_id']} for {ar_company} expired.")
                            expired = True
                    except (ValueError, TypeError):
                        pass
                if expired:
                    continue

                if ar_status == "approved":
                    if market_is_open:
                        print(f"    ✅ [{uid}] Approval received for {ar_company}. Executing...")
                        ok = revalidate_and_execute(pending, stores["portfolio"], uid)
                        db.update_pending_status(pending["id"], "executed" if ok else "rejected")
                    else:
                        print(f"    ⏸️ [{uid}] {ar_company} approved but market closed. Will execute when market opens.")
                elif ar_status == "rejected":
                    print(f"    ❌ [{uid}] Trade for {ar_company} was rejected by user.")
                    db.log_event_db(uid, "authorization", "rejected", pending["news_item"].get("source", ""),
                                     pending["news_item"].get("headline", ""), ar_company,
                                     ar_panic_score, ar_action, "User denied via Telegram")
                    db.update_pending_status(pending["id"], "rejected")

        if not market_was_open and market_is_open:
            for user in users:
                uid = user["id"]
                stores = user_stores.get(uid)
                if stores and not stores["pending"].is_empty:
                    print(f"\n[LOG] Market opened! Processing queued trades for user {uid}...")
                    for entry in stores["pending"].dequeue_all():
                        ok = revalidate_and_execute(entry, stores["portfolio"], uid)
                        time.sleep(2)

        market_was_open = market_is_open

        print("\n[LOG] Scanning for fresh news...")
        headlines = get_all_headlines()

        if not headlines:
            print("[WARN] No headlines fetched.")
        else:
            print(f"[LOG] Processing {len(headlines)} items for {len(users)} user(s)...")
            for news_item in headlines:
                for user in users:
                    uid = user["id"]
                    stores = user_stores[uid]
                    process_news_item(news_item, uid,
                                      stores["seen"],
                                      stores["portfolio"],
                                      stores["pending"])
                    time.sleep(1)

        print(f"\n[INFO] Cycle complete. Next scan in {settings.scan_interval_seconds}s.")
        time.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    run_news_pulse_agent()
