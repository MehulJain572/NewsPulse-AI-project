import time
import threading
from notifier import send_approval_request, bot
from brain import analyze_news
import db
from fetcher import get_all_headlines

def process_news_item(news_item, user_id, seen_store, portfolio_store):
    headline = news_item["headline"]
    if seen_store.has_seen(news_item["fingerprint"]): return

    print(f"\n[ANALYZE] Processing: {headline[:80]}...")
    time.sleep(2) 
    analysis = analyze_news(news_item)
    if not analysis: return
    seen_store.mark_seen(news_item["fingerprint"])

    score = analysis.get('panic_score', 0)
    action = analysis.get('action', 'IGNORE')
    company = analysis.get('company', 'Market')
    
    print(f"    -> Company: {company} | Panic Score: {score} | Action: {action}")

    # --- FIX 1: LOG TO EVENTS TABLE SO "INSIGHTS" TAB POPULATES ---
    db.log_event_db(
        user_id=user_id,
        stage="scanned",
        status="completed",
        source=news_item.get("source", "unknown"),
        headline=headline,
        company=company,
        panic_score=score,
        action=action,
        details=analysis.get('reason', 'Routine market scan')
    )
    # -------------------------------------------------------------

    # ONLY AUTHORIZE IF SCORE IS HIGH (NATURAL AI LOGIC)
    if score >= 80:
        print(f"    ⚠️ [ALERT] High Intensity Signal detected!")
        request_id = send_approval_request(
            user_id, company, action, score, analysis.get('reason', 'Market Move'),
            headline=headline, estimated_value=250000
        )
        
        # Wait for mobile response
        start_wait = time.time()
        print("    ⏳ Waiting for Telegram approval (120s timeout)...")
        while time.time() - start_wait < 120:
            status = db.get_approval_status(request_id)
            
            # --- FIX 2: DEMO BYPASS FOR SUNDAY FAKE NEWS ---
            # Agar news source Manual_Test hai, toh hum Telegram approval ka wait nahi karenge
            if news_item.get("source") == "Manual_Test":
                print("    ⚡ [DEMO BYPASS] Auto-approving fake news for execution!")
                status = "approved"
            # -----------------------------------------------

            if status == "approved":
                # EXECUTE AND UPDATE DB
                db.log_trade_db(user_id, news_item["source"], headline, company, "RELIANCE", 
                                action, score, 100, 250000, "simulated", "Authorized", 2500.0)
                print(f"    🔥 [SUCCESS] Trade Executed! Check Dashboard.")
                break
            if status == "rejected": 
                print(f"    ❌ [REJECTED] Trade cancelled via Telegram.")
                break
            time.sleep(1)

def run_news_pulse_agent():
    db.init_db()
    print("\n" + "=" * 60)
    print("AETHER TRADING AGENT: PURE DATA-DRIVEN MODE")
    print("=" * 60)
    if bot: threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    from state import SeenNewsStore, PortfolioStore
    user_id = 1
    seen_store = SeenNewsStore(user_id)
    portfolio_store = PortfolioStore(user_id)

    while True:
        headlines = get_all_headlines()
        for item in headlines:
            process_news_item(item, user_id, seen_store, portfolio_store)
        time.sleep(30)

if __name__ == "__main__":
    run_news_pulse_agent()