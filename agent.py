import time

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

    print(f"[ANALYZE] {headline[:90]}")
    analysis = analyze_news(news_item)

    if not analysis:
        log_event("analysis", news_item, status="failed", details="LLM analysis returned no result")
        return

    log_event("analysis", news_item, analysis=analysis, status="complete")

    validation = validate_trade_candidate(analysis, portfolio_store.snapshot())
    log_event(
        "validation",
        news_item,
        analysis=analysis,
        status="approved" if validation["approved"] else "rejected",
        details="; ".join(validation["reasons"]) if validation["reasons"] else "passed",
    )

    print(
        f"    -> {analysis['company']} | panic={analysis['panic_score']} | action={analysis['action']} "
        f"| valid={validation['approved']}"
    )

    if not validation["approved"]:
        return

    if analysis["action"] == "IGNORE":
        return

    trade_result = execute_trade(news_item, analysis, validation, portfolio_store)
    log_trade(news_item, analysis, validation, trade_result)

    if trade_result["status"] in {"simulated", "placed"}:
        print(
            f"[ALERT] {analysis['company']} | {analysis['action']} {trade_result['quantity']} "
            f"shares | stop-loss {trade_result['stop_loss_pct']}%"
        )


def run_news_pulse_agent():
    seen_store = SeenNewsStore()
    portfolio_store = PortfolioStore()

    print("\n" + "=" * 60)
    print("NEWSPULSE AI: AUTONOMOUS AGENT IS LIVE")
    print("=" * 60)
    print(f"[INFO] Scan interval: {settings.scan_interval_seconds}s | Broker mode: {settings.broker_mode}")
    print(
        "[INFO] Env status | "
        f"GROQ_API_KEY: {env_status('GROQ_API_KEY')} | "
        f"NEWS_API_KEY: {env_status('NEWS_API_KEY')} | "
        f"FINNHUB_API_KEY: {env_status('FINNHUB_API_KEY')}"
    )

    while True:
        print("\n[LOG] Fetching latest headlines...")
        headlines = get_all_headlines()

        if not headlines:
            print("[WARN] No headlines fetched in this cycle.")
        else:
            print(f"[LOG] {len(headlines)} total headlines fetched. Processing fresh items...")
            for news_item in headlines:
                process_news_item(news_item, seen_store, portfolio_store)
                time.sleep(settings.analysis_pause_seconds)

        print(f"[INFO] Cycle complete. Next scan in {settings.scan_interval_seconds} seconds.")
        time.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    run_news_pulse_agent()
