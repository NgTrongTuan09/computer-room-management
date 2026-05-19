# Activity DB - SQLite storage for client activity history
# Stores activity logs: processes and window titles (approx. browser activity)

import sqlite3
from pathlib import Path
import time
from typing import List, Optional, Dict

DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "activity.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    name TEXT,
    url TEXT,
    ts INTEGER NOT NULL
);
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def insert_activity(client_id: str, activity_type: str, name: str = "", url: str = "", ts: Optional[int] = None):
    """Insert a single activity record into the DB"""
    if ts is None:
        ts = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO activities (client_id, activity_type, name, url, ts) VALUES (?, ?, ?, ?, ?)",
            (client_id, activity_type, name, url, ts)
        )
        conn.commit()
    finally:
        conn.close()


def bulk_insert(client_id: str, entries: List[Dict]):
    """Insert multiple activity entries. Each entry is a dict with keys: type,name,url,ts"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        data = []
        for e in entries:
            ts = e.get("ts") or int(time.time())
            data.append((client_id, e.get("type", "unknown"), e.get("name", ""), e.get("url", ""), ts))
        cur.executemany(
            "INSERT INTO activities (client_id, activity_type, name, url, ts) VALUES (?, ?, ?, ?, ?)",
            data
        )
        conn.commit()
    finally:
        conn.close()


def get_activities(client_id: str, since_ts: Optional[int] = None, limit: int = 500) -> List[Dict]:
    """Query activity history for a client. Returns list of dicts ordered desc by ts."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        if since_ts:
            cur.execute(
                "SELECT activity_type, name, url, ts FROM activities WHERE client_id = ? AND ts >= ? ORDER BY ts DESC LIMIT ?",
                (client_id, since_ts, limit)
            )
        else:
            cur.execute(
                "SELECT activity_type, name, url, ts FROM activities WHERE client_id = ? ORDER BY ts DESC LIMIT ?",
                (client_id, limit)
            )
        rows = cur.fetchall()
        return [
            {"type": r[0], "name": r[1], "url": r[2], "ts": r[3]} for r in rows
        ]
    finally:
        conn.close()
