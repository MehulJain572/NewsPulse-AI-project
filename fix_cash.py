import sqlite3
import os
from datetime import datetime, timezone

db_path = os.path.join("data", "news_pulse.db")
conn = sqlite3.connect(db_path)

print("[LOG] Resetting portfolio...")

# 1. Reset Wallet
conn.execute("UPDATE cash_balance SET cash_inr = 1000000.0 WHERE user_id = 1")

# 2. Clear old data
conn.execute("DELETE FROM holdings WHERE user_id = 1")
conn.execute("DELETE FROM portfolio_events WHERE user_id = 1")

# 3. Add a Demo Holding (So holdings section isn't empty)
# Bought at 2500, Current is 2650 (6% Profit)
current_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
conn.execute("""
    INSERT INTO holdings (user_id, symbol, qty, avg_price, current_price, price_updated_at) 
    VALUES (1, 'RELIANCE', 10, 2500.0, 2650.0, ?)
""", (current_time,))

# 4. Create Baseline Portfolio Events (To render the Performance Curve and P&L)
# Initial deposit event
conn.execute("""
    INSERT INTO portfolio_events (user_id, timestamp, event_type, symbol, qty_change, cash_change, running_cash, details) 
    VALUES (1, ?, 'system_init', '', 0, 1000000.0, 1000000.0, 'Baseline initialization')
""", (current_time,))

# The fake trade event that makes the graph move
# 10 Lakh cash + 26,500 holding value = Total Net Worth ₹10,26,500
conn.execute("""
    INSERT INTO portfolio_events (user_id, timestamp, event_type, symbol, qty_change, cash_change, running_cash, details) 
    VALUES (1, ?, 'trade', 'RELIANCE', 10, -25000.0, 1026500.0, 'Demo startup holding injected')
""", (current_time,))

conn.commit()
conn.close()
print("✅ STARTUP READY: Wallet set to ₹10,00,000, baseline holding added, and P&L initialized.")