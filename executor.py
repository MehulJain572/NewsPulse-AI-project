from settings import settings

#this code executes the trades
def execute_trade(news_item, analysis, validation, portfolio_store):
    symbol = validation["company_info"]["symbol"]
    quantity = validation["quantity"]
    estimated_value = settings.estimated_trade_value_inr

    result = {
        "status": "skipped",
        "broker_mode": settings.broker_mode,
        "symbol": symbol,
        "quantity": quantity,
        "action": analysis["action"],
        "estimated_value_inr": estimated_value,
        "stop_loss_pct": settings.stop_loss_pct,
        "details": "",
    }

    if settings.broker_mode == "paper":
        portfolio_store.apply_paper_trade(symbol, analysis["action"], quantity, estimated_value)
        result["status"] = "simulated"
        result["details"] = "Paper trade executed and portfolio updated."
        return result

    if settings.broker_mode in {"zerodha", "upstox"}:
        result["status"] = "pending_adapter"
        result["details"] = (
            f"{settings.broker_mode} adapter not implemented yet. "
            "Keep BROKER_MODE=paper until API wiring is added."
        )
        return result

    result["details"] = "Unknown broker mode."
    return result
