# NewsPulse-AI-project

NewsPulse is a news-driven trading agent prototype for Indian markets. It now runs as a stateful pipeline:

- Phase 1: pulls headlines from Google News RSS, Finnhub, and NewsAPI
- Phase 1.5: removes duplicate headlines and persists a `seen_news` cache
- Phase 2: sends fresh headlines to Groq/LLM for company, panic score, and action
- Phase 3: validates mapped listed companies, market hours, cash, and holdings
- Phase 4: executes paper trades with stop-loss metadata
- Phase 5: logs events and trades into CSV files under `data/`

## Environment

Required:

- `GROQ_API_KEY`
- `NEWS_API_KEY`
- `FINNHUB_API_KEY`

Optional:

- `SCAN_INTERVAL_SECONDS=60`
- `PANIC_THRESHOLD=80`
- `TRADE_QUANTITY=100`
- `STOP_LOSS_PCT=2.5`
- `ESTIMATED_TRADE_VALUE_INR=100000`
- `MIN_CASH_BUFFER_INR=10000`
- `BROKER_MODE=paper`
- `ALLOW_SELL_WITHOUT_HOLDINGS=false`

## Run

```bash
python agent.py
```

The default broker mode is `paper`, so trades are simulated and written to `data/trades.csv`.
