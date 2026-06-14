import time
import threading
from notifier import send_approval_request, bot
from brain import analyze_news
import db
from fetcher import get_all_headlines
from state import SeenNewsStore, PortfolioStore, PendingTradeQueue


def send_and_enqueue(news_item, analysis, user_id, pending_queue):
    score = analysis.get("panic_score", 0)
    company = analysis.get("company", "Market")
    action = analysis.get("action", "IGNORE")
    headline = news_item.get("headline", "")

    request_id = send_approval_request(
        user_id, company, action, score,
        analysis.get("reason", "Market Move"),
        headline=headline, estimated_value=250000
    )

    pending_queue.enqueue(
        news_item, analysis, {"approved": True, "reasons": []},
        status="pending_approval", approval_request_id=request_id,
    )

    db.log_event_db(user_id, "authorization", "pending",
                     news_item.get("source", ""), headline, company,
                     score, action, f"Approval request #{request_id}")


def process_pending_approvals(user_id):
    for pending in db.get_pending_approval_trades(user_id):
        ar_status = pending.get("ar_status")
        news_item = pending["news_item"]
        analysis = pending["analysis"]
        company = pending.get("ar_company", analysis.get("company", ""))
        score = pending.get("ar_panic_score", analysis.get("panic_score", 0))
        action = pending.get("ar_action", analysis.get("action", ""))
        headline = news_item.get("headline", "")
        pending_id = pending["id"]

        if ar_status == "approved":
            print(f"    ✅ [User {user_id}] Approval received for {company}. Executing...")
            db.log_trade_db(
                user_id, news_item.get("source", ""), headline,
                company, pending.get("symbol", company),
                action, score, 100, 250000,
                "simulated", "Authorized", 2500.0
            )
            db.update_pending_status(pending_id, "executed")
            db.log_event_db(user_id, "authorization", "approved",
                             news_item.get("source", ""), headline,
                             company, score, action, "Approved via Telegram")

        elif ar_status == "rejected":
            print(f"    ❌ [User {user_id}] Trade for {company} rejected.")
            db.log_event_db(user_id, "authorization", "rejected",
                             news_item.get("source", ""), headline,
                             company, score, action, "Rejected via Telegram")
            db.update_pending_status(pending_id, "rejected")


def process_news_item(news_item, user_id, seen_store, portfolio_store, pending_queue):
    headline = news_item["headline"]
    if seen_store.has_seen(news_item["fingerprint"]):
        return

    analysis = analyze_news(news_item)
    if not analysis:
        return
    seen_store.mark_seen(news_item["fingerprint"])

    score = analysis.get("panic_score", 0)
    action = analysis.get("action", "IGNORE")
    company = analysis.get("company", "Market")

    print(f"    [User {user_id}] {company} | panic={score} | action={action}")

    db.log_event_db(
        user_id=user_id, stage="analysis", status="complete",
        source=news_item.get("source", "unknown"),
        headline=headline, company=company,
        panic_score=score, action=action,
        details=analysis.get("reason", "Routine market scan"),
    )

    if score >= 80 and action in ("BUY", "SELL"):
        send_and_enqueue(news_item, analysis, user_id, pending_queue)
        print(f"    ⚠️ [User {user_id}] High panic ({score})! Approval request sent to Telegram.")


def run_news_pulse_agent():
    db.init_db()
    print("\n" + "=" * 60)
    print("AETHER TRADING AGENT: MULTI-USER MODE")
    print("=" * 60)
    if bot:
        threading.Thread(target=bot.infinity_polling, daemon=True).start()
        print("[INFO] Telegram Bot active.")
    else:
        print("[INFO] Telegram disabled (no bot token).")

    user_stores = {}

    while True:
        users = db.get_all_active_users()
        if not users:
            time.sleep(30)
            continue

        # Init stores for any new users
        for user in users:
            uid = user["id"]
            if uid not in user_stores:
                user_stores[uid] = {
                    "seen": SeenNewsStore(uid),
                    "portfolio": PortfolioStore(uid),
                    "pending": PendingTradeQueue(uid),
                }

        # Process pending approvals for each user (non-blocking)
        for user in users:
            process_pending_approvals(user["id"])

        # Fetch and process headlines
        headlines = get_all_headlines()
        if not headlines:
            print("[LOG] No headlines fetched. Waiting...")
            time.sleep(30)
            continue

        print(f"[LOG] Processing {len(headlines)} headlines for {len(users)} user(s)...")
        for news_item in headlines:
            for user in users:
                uid = user["id"]
                stores = user_stores[uid]
                process_news_item(news_item, uid,
                                  stores["seen"],
                                  stores["portfolio"],
                                  stores["pending"])
                time.sleep(0.5)

        print("[INFO] Cycle complete. Next scan in 30s.")
        time.sleep(30)


if __name__ == "__main__":
    run_news_pulse_agent()
