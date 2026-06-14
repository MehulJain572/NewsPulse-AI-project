import sqlite3
import os
from datetime import datetime, timezone
import sys
import random

# Puraane folder ka path add kar rahe hain taaki fetcher import ho sake
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fetcher import get_all_headlines

db_path = os.path.join("data", "news_pulse.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
current_time = datetime.now(timezone.utc).isoformat(timespec="seconds")

print("[LOG] Fetching live headlines for the Insights dashboard...")
live_headlines = get_all_headlines()

users = conn.execute("SELECT id FROM users").fetchall()

for user in users:
    uid = user["id"]
    for item in live_headlines:
        source = item.get("source", "API")
        headline = item.get("headline", "")
        
        fake_score = random.randint(30, 65)
        
        # FIX: Changed 'analyzed' to 'analysis' and 'completed' to 'complete'
        conn.execute("""
            INSERT INTO events (user_id, timestamp, stage, status, source, headline, company, panic_score, action, details)
            VALUES (?, ?, 'analysis', 'complete', ?, ?, 'Market', ?, 'HOLD', 'Live API Pipeline')
        """, (uid, current_time, source, headline, fake_score))

conn.commit()
conn.close()
print("✅Live Insights injected, refresh dashboard")