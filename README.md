# 🌐 NewsPulse_Ai Trading Bot

NewsPulse is an advanced, multi-tenant AI trading agent and web dashboard designed for dynamic market environments. It operates as a fully stateful pipeline that analyzes financial news in real-time, calculates market panic, and seamlessly routes execution approvals to users via 1-Click Telegram Deep Linking.

## ✨ Key Features
* **Multi-Tenant SaaS Architecture:** Isolated data environments allowing multiple users to manage distinct portfolios concurrently.
* **AI-Powered Panic Detection:** Utilizes Groq LLMs to analyze market sentiment, extracting target companies and assigning actionable "Panic Scores".
* **1-Click Telegram Approvals:** Enterprise-grade deep linking (`tg://` & `https://t.me`) allows users to instantly authorize or reject paper trades via their connected Telegram app.
* **Interactive Web Dashboard:** A sleek Flask-based UI for monitoring core holdings, performance charts, and live trade activity trails.

## ⚙️ The Pipeline
1. **Ingestion:** Pulls real-time headlines from Google News RSS, Finnhub, and NewsAPI.
2. **Deduplication:** Filters noise and persists unique data in a `seen_news` cache.
3. **Analysis:** Routes fresh headlines to the LLM to extract the targeted company, calculate the panic score (0-100), and determine the proposed action (BUY/SELL).
4. **Validation:** Checks user cash balances, portfolio holdings, and strict threshold rules.
5. **Authorization:** Dispatches an interactive approval request directly to the specific user's mapped Telegram chat.
6. **Execution:** Executes simulated paper trades based on live user input and securely logs the transaction.

## 🚀 Setup & Installation

### Prerequisites
Create a `.env` file in the root directory and configure your secure credentials. Ensure this file is added to your `.gitignore`.

**Required:**
* `GROQ_API_KEY`
* `NEWS_API_KEY`
* `FINNHUB_API_KEY`
* `JWT_SECRET` (For secure dashboard session management)
* `TELEGRAM_BOT_TOKEN` (From BotFather)
* `TELEGRAM_BOT_USERNAME` (Exact bot username without the '@')

**Optional Configurations:**
* `PORT=5000`
* `SCAN_INTERVAL_SECONDS=60`
* `PANIC_THRESHOLD=80` (AI will only trigger trades on high-panic news)
* `TRADE_QUANTITY=100`
* `ESTIMATED_TRADE_VALUE_INR=250000`
* `BROKER_MODE=paper`

### Run Locally
Install the required dependencies and start the unified Flask server (which simultaneously boots the web dashboard and the background AI agent).

```bash
pip install -r requirements.txt
python app.py