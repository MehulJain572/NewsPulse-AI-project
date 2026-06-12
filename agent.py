import time
import threading
from notifier import send_approval_request, user_responses, bot
# this code integrates all the 5 phases and make them work together
from brain import analyze_news
from env_utils import env_status
from executor import execute_trade
from fetcher import get_all_headlines
from logger import log_event, log_trade
from settings import settings
from state import SeenNewsStore, PortfolioStore
from validator import validate_trade_candidate

def process_news_item(news_item, seen_store, portfolio_store):
    headline = news_item["headline"]
    fingerprint = news_item["fingerprint"]

    if seen_store.has_seen(fingerprint):
        return

    seen_store.mark_seen(fingerprint)
    log_event("ingestion", news_item, status="fresh")

    print(f"\n[ANALYZE] {headline[:90]}...")
    analysis = analyze_news(news_item)

    if not analysis:
        log_event("analysis", news_item, status="failed", details="LLM analysis returned no result")
        return

    log_event("analysis", news_item, analysis=analysis, status="complete")

    validation = validate_trade_candidate(analysis, portfolio_store.snapshot())
    
    print(
        f"    -> {analysis['company']} | panic={analysis['panic_score']} | action={analysis['action']} "
        f"| valid={validation['approved']}"
    )
    
    if analysis["panic_score"] >= 80:
        company = analysis['company']
        
        send_approval_request(
            company, 
            analysis['action'], 
            analysis['panic_score'], 
            analysis.get('reason', 'Critical Market Event Detected')
        )
        
        print(f"    ⚠️ [ALERT] High Panic ({analysis['panic_score']})! Request sent to Telegram. Waiting for approval...")
        
        start_time = time.time()
        authorized = False
        
        while time.time() - start_time < 60: 
            if user_responses.get(company) == "YES":
                authorized = True
                break
            if user_responses.get(company) == "NO":
                authorized = False
                break
            time.sleep(1)
        
        if authorized:
            if validation.get("company_info") and validation["company_info"].get("symbol"):
                print(f"    ✅ [AUTHORIZED] Mobile approval received for {company}! Proceeding...")
                validation["approved"] = True 
                user_responses.pop(company, None) 
            else:
                print(f"    ⚠️ [SKIP] Approval received, but '{company}' is not a listed stock. Skipping trade execution.")
                user_responses.pop(company, None)
                return
        else:
            print(f"    ❌ [ABORTED] Trade for {company} was rejected or timed out.")
            log_event("authorization", news_item, status="rejected", details="User denied or timeout")
            return

    if not validation["approved"]:
        log_event("validation", news_item, status="rejected", details="; ".join(validation["reasons"]))
        return

    if analysis["action"] == "IGNORE":
        return

    trade_result = execute_trade(news_item, analysis, validation, portfolio_store)
    log_trade(news_item, analysis, validation, trade_result)

    if trade_result["status"] in {"simulated", "placed"}:
        print(
            f"\n🔥 [TRADE EXECUTED] {analysis['company']} | {analysis['action']} {trade_result['quantity']} "
            f"shares | stop-loss {trade_result['stop_loss_pct']}%"
        )


def run_news_pulse_agent():
    seen_store = SeenNewsStore()
    portfolio_store = PortfolioStore()

    print("\n" + "=" * 60)
    print("NEWSPULSE AI: AUTONOMOUS AGENT IS LIVE (DEMO MODE)")
    print("=" * 60)
    
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    print("[INFO] Telegram Mobile Link active.")

    while True:
        print("\n[LOG] Scanning for fresh news...")
        headlines = get_all_headlines()

        if not headlines:
            print("[WARN] No headlines fetched.")
        else:
            print(f"[LOG] Processing {len(headlines)} items...")
            for news_item in headlines:
                process_news_item(news_item, seen_store, portfolio_store)
                time.sleep(2) 

        print(f"\n[INFO] Cycle complete. Next scan in {settings.scan_interval_seconds}s.")
        time.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    run_news_pulse_agent()