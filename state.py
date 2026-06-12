import json
from pathlib import Path


DATA_DIR = Path("data")
SEEN_NEWS_FILE = DATA_DIR / "seen_news.json"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


class SeenNewsStore:
    def __init__(self, path=SEEN_NEWS_FILE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _save(self):
        self.path.write_text(json.dumps(self._seen[-1000:], indent=2), encoding="utf-8")

    def has_seen(self, fingerprint):
        return fingerprint in self._seen

    def mark_seen(self, fingerprint):
        if fingerprint not in self._seen:
            self._seen.append(fingerprint)
            self._save()


class PortfolioStore:
    def __init__(self, path=PORTFOLIO_FILE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(
                {
                    "cash_inr": 500000,
                    "holdings": {
                        "RELIANCE": 0,
                        "ADANIENT": 0,
                        "TATAMOTORS": 0,
                        "INFY": 0,
                        "HDFCBANK": 0,
                    },
                }
            )

    def _read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload):
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def snapshot(self):
        return self._read()

    def apply_paper_trade(self, symbol, action, quantity, estimated_value):
        state = self._read()
        holdings = state.setdefault("holdings", {})
        holdings.setdefault(symbol, 0)

        if action == "BUY":
            holdings[symbol] += quantity
            state["cash_inr"] = round(state.get("cash_inr", 0) - estimated_value, 2)
        elif action == "SELL":
            holdings[symbol] = max(0, holdings[symbol] - quantity)
            state["cash_inr"] = round(state.get("cash_inr", 0) + estimated_value, 2)

        self._write(state)
        return state
