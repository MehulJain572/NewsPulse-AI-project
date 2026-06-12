import csv
from datetime import datetime
from pathlib import Path

#this code records everything
LOG_DIR = Path("data")
EVENT_LOG = LOG_DIR / "events.csv"
TRADE_LOG = LOG_DIR / "trades.csv"


def _append_csv(path, row, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_event(stage, news_item, analysis=None, status="", details=""):
    _append_csv(
        EVENT_LOG,
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "stage": stage,
            "status": status,
            "source": news_item.get("source", ""),
            "headline": news_item.get("headline", ""),
            "company": (analysis or {}).get("company", ""),
            "panic_score": (analysis or {}).get("panic_score", ""),
            "action": (analysis or {}).get("action", ""),
            "details": details,
        },
        ["timestamp", "stage", "status", "source", "headline", "company", "panic_score", "action", "details"],
    )


def log_trade(news_item, analysis, validation, trade_result):
    _append_csv(
        TRADE_LOG,
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "source": news_item.get("source", ""),
            "headline": news_item.get("headline", ""),
            "company": analysis.get("company", ""),
            "symbol": (validation.get("company_info") or {}).get("symbol", ""),
            "action": analysis.get("action", ""),
            "panic_score": analysis.get("panic_score", ""),
            "quantity": trade_result.get("quantity", ""),
            "status": trade_result.get("status", ""),
            "broker_mode": trade_result.get("broker_mode", ""),
            "estimated_value_inr": trade_result.get("estimated_value_inr", ""),
            "stop_loss_pct": trade_result.get("stop_loss_pct", ""),
            "details": trade_result.get("details", ""),
        },
        [
            "timestamp",
            "source",
            "headline",
            "company",
            "symbol",
            "action",
            "panic_score",
            "quantity",
            "status",
            "broker_mode",
            "estimated_value_inr",
            "stop_loss_pct",
            "details",
        ],
    )
