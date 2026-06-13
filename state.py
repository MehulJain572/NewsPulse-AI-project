import db


class SeenNewsStore:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def has_seen(self, fingerprint):
        return db.has_seen_news(self.user_id, fingerprint)

    def mark_seen(self, fingerprint):
        db.mark_seen_news(self.user_id, fingerprint)


class PortfolioStore:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def snapshot(self):
        return db.get_portfolio_snapshot(self.user_id)

    def current_price_for(self, symbol):
        holdings = db.get_holdings(self.user_id)
        h = holdings.get(symbol)
        if h and h.get("current_price", 0) > 0:
            return h["current_price"]
        cached = db.get_cached_price(symbol)
        if cached and cached > 0:
            return cached
        return None

    def apply_paper_trade(self, symbol, action, quantity, price):
        state = db.get_portfolio_snapshot(self.user_id)
        cash = state["cash_inr"]
        holdings = state["holdings"]
        estimated_value = round(price * quantity, 2)

        if action == "BUY":
            holding = holdings.get(symbol, {"qty": 0, "avg_price": 0.0})
            total_cost = holding["qty"] * holding["avg_price"] + estimated_value
            new_qty = holding["qty"] + quantity
            new_avg = round(total_cost / new_qty, 2) if new_qty > 0 else 0
            db.upsert_holding(self.user_id, symbol, new_qty, new_avg)
            db.set_cash_balance(self.user_id, round(cash - estimated_value, 2))

        elif action == "SELL":
            holding = holdings.get(symbol)
            if holding is None or holding["qty"] < quantity:
                quantity = holding["qty"] if holding else 0
            if holding and quantity > 0:
                sale_value = round(price * quantity, 2)
                remaining_qty = holding["qty"] - quantity
                if remaining_qty <= 0:
                    db.delete_holding(self.user_id, symbol)
                else:
                    db.upsert_holding(self.user_id, symbol, remaining_qty, holding["avg_price"])
                db.set_cash_balance(self.user_id, round(cash + sale_value, 2))

        return db.get_portfolio_snapshot(self.user_id)


class PendingTradeQueue:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def enqueue(self, news_item, analysis, validation, status='queued_market_closed', approval_request_id=None):
        db.enqueue_pending(self.user_id, news_item, analysis, validation,
                           status=status, approval_request_id=approval_request_id)

    def dequeue_all(self):
        return db.dequeue_all_pending(self.user_id)

    def peek_all(self):
        return db.get_all_pending(self.user_id)

    @property
    def is_empty(self):
        return db.pending_count(self.user_id, status='queued_market_closed') == 0
