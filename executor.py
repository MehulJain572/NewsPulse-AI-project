import db
from settings import settings


def _resolve_price(symbol, portfolio_store, quantity):
    price = portfolio_store.current_price_for(symbol)
    if price is None or price <= 0:
        price = settings.estimated_trade_value_inr / quantity if quantity > 0 else 0
    return round(price, 2)


def execute_trade(news_item, analysis, validation, portfolio_store):
    symbol = validation["company_info"]["symbol"]
    quantity = validation["quantity"]
    price = _resolve_price(symbol, portfolio_store, quantity)
    estimated_value = round(price * quantity, 2)

    db.set_cached_price(symbol, price)

    result = {
        "status": "skipped",
        "broker_mode": settings.broker_mode,
        "symbol": symbol,
        "quantity": quantity,
        "action": analysis["action"],
        "estimated_value_inr": estimated_value,
        "execution_price": price,
        "stop_loss_pct": settings.stop_loss_pct,
        "details": "",
    }

    if settings.broker_mode == "paper":
        portfolio_store.apply_paper_trade(symbol, analysis["action"], quantity, price)
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
