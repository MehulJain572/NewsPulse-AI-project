import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path("data") / "news_pulse.db"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            telegram_chat_id TEXT,
            linking_code    TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            is_active       INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            UNIQUE(user_id, key)
        );

        CREATE TABLE IF NOT EXISTS holdings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL REFERENCES users(id),
            symbol           TEXT NOT NULL,
            qty              INTEGER NOT NULL DEFAULT 0,
            avg_price        REAL NOT NULL DEFAULT 0.0,
            current_price    REAL NOT NULL DEFAULT 0.0,
            price_updated_at TEXT,
            UNIQUE(user_id, symbol)
        );

        CREATE TABLE IF NOT EXISTS cash_balance (
            user_id     INTEGER PRIMARY KEY REFERENCES users(id),
            cash_inr    REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            timestamp   TEXT NOT NULL,
            stage       TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT '',
            source      TEXT NOT NULL DEFAULT '',
            headline    TEXT NOT NULL DEFAULT '',
            company     TEXT NOT NULL DEFAULT '',
            panic_score INTEGER NOT NULL DEFAULT 0,
            action      TEXT NOT NULL DEFAULT '',
            details     TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS trades (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL REFERENCES users(id),
            timestamp           TEXT NOT NULL,
            source              TEXT NOT NULL DEFAULT '',
            headline            TEXT NOT NULL DEFAULT '',
            company             TEXT NOT NULL DEFAULT '',
            symbol              TEXT NOT NULL DEFAULT '',
            action              TEXT NOT NULL DEFAULT '',
            panic_score         INTEGER NOT NULL DEFAULT 0,
            quantity            INTEGER NOT NULL DEFAULT 0,
            estimated_value_inr REAL NOT NULL DEFAULT 0,
            status              TEXT NOT NULL DEFAULT '',
            details             TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            endpoint    TEXT NOT NULL,
            auth_key    TEXT NOT NULL,
            p256dh_key  TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, endpoint)
        );

        CREATE TABLE IF NOT EXISTS seen_news (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            fingerprint TEXT NOT NULL,
            seen_at     TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, fingerprint)
        );

        CREATE TABLE IF NOT EXISTS pending_trades (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL REFERENCES users(id),
            news_item_json      TEXT NOT NULL,
            analysis_json       TEXT NOT NULL,
            validation_json     TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'queued_market_closed',
            approval_request_id INTEGER REFERENCES approval_requests(id),
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS approval_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            chat_id         TEXT,
            message_id      INTEGER,
            company         TEXT NOT NULL,
            headline        TEXT NOT NULL DEFAULT '',
            action          TEXT NOT NULL,
            panic_score     INTEGER NOT NULL DEFAULT 0,
            estimated_value REAL NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
        CREATE INDEX IF NOT EXISTS idx_trades_user ON trades(user_id);
        CREATE INDEX IF NOT EXISTS idx_seen_user ON seen_news(user_id, fingerprint);
        CREATE INDEX IF NOT EXISTS idx_pending_user ON pending_trades(user_id);
        CREATE INDEX IF NOT EXISTS idx_approval_user_status ON approval_requests(user_id, status);

        CREATE TABLE IF NOT EXISTS price_cache (
            symbol      TEXT PRIMARY KEY,
            price       REAL NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS portfolio_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            timestamp       TEXT NOT NULL,
            event_type      TEXT NOT NULL,
            symbol          TEXT,
            qty_change      INTEGER NOT NULL DEFAULT 0,
            cash_change     REAL NOT NULL DEFAULT 0,
            running_cash    REAL NOT NULL DEFAULT 0,
            details         TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_portfolio_events_user ON portfolio_events(user_id);
    """)
    conn.commit()
    conn.close()


def migrate_db():
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE holdings ADD COLUMN current_price REAL NOT NULL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE holdings ADD COLUMN price_updated_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE pending_trades ADD COLUMN status TEXT NOT NULL DEFAULT 'queued_market_closed'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE pending_trades ADD COLUMN approval_request_id INTEGER REFERENCES approval_requests(id)")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN execution_price REAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("""
        UPDATE cash_balance
        SET cash_inr = 0.0
        WHERE cash_inr = 500000.0
          AND user_id IN (
              SELECT cb.user_id
              FROM cash_balance cb
              LEFT JOIN holdings h ON h.user_id = cb.user_id
              LEFT JOIN trades t ON t.user_id = cb.user_id
              WHERE cb.cash_inr = 500000.0
              GROUP BY cb.user_id
              HAVING COUNT(h.id) = 0 AND COUNT(t.id) = 0
          )
    """)
    conn.commit()
    conn.close()


# ── Users ──────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    user_id = cur.lastrowid
    conn.execute("INSERT INTO cash_balance (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    return user_id


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_linking_code(code: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE linking_code = ?", (code,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_linking_code(user_id: int, code: str):
    conn = get_conn()
    conn.execute("UPDATE users SET linking_code = ? WHERE id = ?", (code, user_id))
    conn.commit()
    conn.close()


def update_password_hash(user_id: int, new_hash: str):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()


def link_telegram(user_id: int, chat_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET telegram_chat_id = ?, linking_code = NULL WHERE id = ?",
        (chat_id, user_id),
    )
    conn.commit()
    conn.close()


def get_all_active_users() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM users WHERE is_active = 1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── User Settings ──────────────────────────────────────

def get_user_setting(user_id: int, key: str, default=None):
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
        (user_id, key),
    ).fetchone()
    conn.close()
    if row:
        return row["value"]
    return default


def set_user_setting(user_id: int, key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
        (user_id, key, value),
    )
    conn.commit()
    conn.close()


# ── Portfolio ──────────────────────────────────────────

def get_cash_balance(user_id: int) -> float:
    conn = get_conn()
    row = conn.execute(
        "SELECT cash_inr FROM cash_balance WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cash_inr"] if row else 0.0


def set_cash_balance(user_id: int, cash_inr: float):
    conn = get_conn()
    conn.execute(
        "INSERT INTO cash_balance (user_id, cash_inr) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET cash_inr = excluded.cash_inr",
        (user_id, round(cash_inr, 2)),
    )
    conn.commit()
    conn.close()


def get_holdings(user_id: int) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, qty, avg_price, current_price, price_updated_at FROM holdings WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()
    return {
        r["symbol"]: {
            "qty": r["qty"],
            "avg_price": r["avg_price"],
            "current_price": r["current_price"],
            "price_updated_at": r["price_updated_at"],
        }
        for r in rows
    }


def upsert_holding(user_id: int, symbol: str, qty: int, avg_price: float, current_price: float = 0.0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO holdings (user_id, symbol, qty, avg_price, current_price) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, symbol) DO UPDATE SET "
        "qty = excluded.qty, avg_price = excluded.avg_price, current_price = excluded.current_price",
        (user_id, symbol, qty, round(avg_price, 2), round(current_price, 2)),
    )
    conn.commit()
    conn.close()


def delete_holding(user_id: int, symbol: str):
    conn = get_conn()
    conn.execute(
        "DELETE FROM holdings WHERE user_id = ? AND symbol = ?",
        (user_id, symbol),
    )
    conn.commit()
    conn.close()


def clear_holdings(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def update_current_price(user_id: int, symbol: str, price: float):
    conn = get_conn()
    conn.execute(
        "UPDATE holdings SET current_price = ?, price_updated_at = ? WHERE user_id = ? AND symbol = ?",
        (round(price, 2), datetime.now(timezone.utc).isoformat(timespec="seconds"), user_id, symbol),
    )
    conn.commit()
    conn.close()


def get_cached_price(symbol: str) -> float | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT price FROM price_cache WHERE symbol = ?", (symbol,)
    ).fetchone()
    conn.close()
    return row["price"] if row else None


def set_cached_price(symbol: str, price: float):
    conn = get_conn()
    conn.execute(
        "INSERT INTO price_cache (symbol, price, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(symbol) DO UPDATE SET price = excluded.price, updated_at = excluded.updated_at",
        (symbol, round(price, 2), datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def add_holding_batch(user_id: int, holdings: list[dict]):
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE user_id = ?", (user_id,))
    for h in holdings:
        conn.execute(
            "INSERT INTO holdings (user_id, symbol, qty, avg_price, current_price, price_updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, h["symbol"], h["qty"], round(h["avg_price"], 2),
             round(h.get("current_price", 0), 2),
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
    conn.commit()
    conn.close()


# ── Events / Trades ────────────────────────────────────

def log_event_db(user_id: int, stage: str, status: str, source: str,
                  headline: str, company: str, panic_score: int,
                  action: str, details: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO events (user_id, timestamp, stage, status, source, "
        "headline, company, panic_score, action, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
         stage, status, source, headline, company, panic_score, action, details),
    )
    conn.commit()
    conn.close()


def log_trade_db(user_id: int, source: str, headline: str, company: str,
                  symbol: str, action: str, panic_score: int, quantity: int,
                  estimated_value_inr: float, status: str, details: str,
                  execution_price: float = 0.0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO trades (user_id, timestamp, source, headline, company, "
        "symbol, action, panic_score, quantity, estimated_value_inr, status, details, execution_price) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
         source, headline, company, symbol, action, panic_score,
         quantity, estimated_value_inr, status, details, execution_price),
    )
    conn.commit()
    conn.close()
    cash_change = -estimated_value_inr if action == "BUY" else estimated_value_inr
    log_portfolio_event(user_id, "trade", symbol, quantity, cash_change,
                        f"{action} {quantity} {symbol} @ {execution_price}")


def log_portfolio_event(user_id: int, event_type: str, symbol: str = "",
                        qty_change: int = 0, cash_change: float = 0.0,
                        details: str = ""):
    running = get_cash_balance(user_id)
    conn = get_conn()
    conn.execute(
        "INSERT INTO portfolio_events (user_id, timestamp, event_type, symbol, "
        "qty_change, cash_change, running_cash, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
         event_type, symbol, qty_change, round(cash_change, 2), round(running, 2), details),
    )
    conn.commit()
    conn.close()


def get_portfolio_events(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM portfolio_events WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_events(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trades(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM trades WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Seen News ──────────────────────────────────────────

def has_seen_news(user_id: int, fingerprint: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM seen_news WHERE user_id = ? AND fingerprint = ?",
        (user_id, fingerprint),
    ).fetchone()
    conn.close()
    return row is not None


def mark_seen_news(user_id: int, fingerprint: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO seen_news (user_id, fingerprint) VALUES (?, ?)",
        (user_id, fingerprint),
    )
    conn.commit()
    conn.close()


# ── Pending Trades ─────────────────────────────────────

def enqueue_pending(user_id: int, news_item: dict, analysis: dict, validation: dict,
                    status: str = 'queued_market_closed', approval_request_id: int = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO pending_trades (user_id, news_item_json, analysis_json, validation_json, status, approval_request_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, json.dumps(news_item), json.dumps(analysis), json.dumps(validation),
         status, approval_request_id),
    )
    conn.commit()
    conn.close()


def dequeue_all_pending(user_id: int, status: str = 'queued_market_closed') -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM pending_trades WHERE user_id = ? AND status = ? ORDER BY id",
        (user_id, status),
    ).fetchall()
    conn.execute("DELETE FROM pending_trades WHERE user_id = ? AND status = ?", (user_id, status))
    conn.commit()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "news_item": json.loads(r["news_item_json"]),
            "analysis": json.loads(r["analysis_json"]),
            "validation": json.loads(r["validation_json"]),
            "created_at": r["created_at"],
            "id": r["id"],
        })
    return result


def get_all_pending(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM pending_trades WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["news_item"] = json.loads(d.pop("news_item_json", "{}"))
        d["analysis"] = json.loads(d.pop("analysis_json", "{}"))
        d["validation"] = json.loads(d.pop("validation_json", "{}"))
        result.append(d)
    return result


def update_pending_status(pending_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE pending_trades SET status = ? WHERE id = ?", (status, pending_id))
    conn.commit()
    conn.close()


def create_approval_request(user_id: int, company: str, headline: str, action: str,
                            panic_score: int, estimated_value: float,
                            timeout_seconds: int = 120) -> int:
    conn = get_conn()
    expires_at = datetime.now(timezone.utc).isoformat(timespec="seconds") if timeout_seconds <= 0 else None
    if timeout_seconds > 0:
        expires_dt = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
        expires_at = expires_dt.isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO approval_requests (user_id, company, headline, action, panic_score, estimated_value, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, company, headline, action, panic_score, estimated_value, expires_at),
    )
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    return request_id


def get_approval_request(request_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM approval_requests WHERE id = ?", (request_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_approval_chat_info(request_id: int, chat_id: str, message_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE approval_requests SET chat_id = ?, message_id = ? WHERE id = ?",
        (chat_id, message_id, request_id),
    )
    conn.commit()
    conn.close()


def update_approval_status(request_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE approval_requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()
    conn.close()


def get_pending_approval_trades(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT pt.*, ar.id AS ar_id, ar.user_id AS ar_user_id, ar.chat_id AS ar_chat_id, "
        "ar.message_id AS ar_message_id, ar.company AS ar_company, ar.headline AS ar_headline, "
        "ar.action AS ar_action, ar.panic_score AS ar_panic_score, ar.estimated_value AS ar_estimated_value, "
        "ar.status AS ar_status, ar.created_at AS ar_created_at, ar.expires_at AS ar_expires_at "
        "FROM pending_trades pt "
        "JOIN approval_requests ar ON ar.id = pt.approval_request_id "
        "WHERE pt.user_id = ? AND pt.status = 'pending_approval' AND ar.status != 'expired'",
        (user_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["news_item"] = json.loads(d["news_item_json"])
        d["analysis"] = json.loads(d["analysis_json"])
        d["validation"] = json.loads(d["validation_json"])
        result.append(d)
    return result


def pending_count(user_id: int, status: str = None) -> int:
    conn = get_conn()
    if status:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pending_trades WHERE user_id = ? AND status = ?",
            (user_id, status),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pending_trades WHERE user_id = ?", (user_id,)
        ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_portfolio_snapshot(user_id: int) -> dict:
    return {
        "cash_inr": get_cash_balance(user_id),
        "holdings": get_holdings(user_id),
    }


# ── Push Subscriptions ────────────────────────────────

def save_push_subscription(user_id: int, endpoint: str, auth_key: str, p256dh_key: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO push_subscriptions (user_id, endpoint, auth_key, p256dh_key) "
        "VALUES (?, ?, ?, ?)",
        (user_id, endpoint, auth_key, p256dh_key),
    )
    conn.commit()
    conn.close()


def get_push_subscriptions(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM push_subscriptions WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_push_subscription(user_id: int, endpoint: str):
    conn = get_conn()
    conn.execute(
        "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
        (user_id, endpoint),
    )
    conn.commit()
    conn.close()


def delete_all_push_subscriptions(user_id: int):
    conn = get_conn()
    conn.execute(
        "DELETE FROM push_subscriptions WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()
