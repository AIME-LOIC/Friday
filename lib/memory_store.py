"""
Simple Postgres-backed memory store for Friday.

- Tries to connect to PostgreSQL using settings from config.json (database section)
- If connection fails or psycopg2 is missing, it becomes a no-op so Friday still runs
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:
    psycopg2 = None
    Json = None


class FridayMemory:
    def __init__(self, config_path: Optional[str] = None):
        self.enabled = False
        self.conn = None

        if not psycopg2:
            return

        try:
            if not config_path:
                config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
            with open(config_path, "r") as f:
                cfg = json.load(f) or {}
        except Exception:
            cfg = {}

        db_cfg = cfg.get("database", {})
        if not db_cfg or not db_cfg.get("enabled", False):
            return

        try:
            self.conn = psycopg2.connect(
                host=db_cfg.get("host", "localhost"),
                port=db_cfg.get("port", 5432),
                dbname=db_cfg.get("name", "friday"),
                user=db_cfg.get("user", "friday"),
                password=db_cfg.get("password", "sir")
            )
            self._ensure_schema()
            self.enabled = True
        except Exception as e:
            print(f"FridayMemory disabled (DB error): {e}")
            self.conn = None
            self.enabled = False

    def _ensure_schema(self):
        if not self.conn:
            return
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS friday_memory (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                meta JSONB
            );
            """
        )
        self.conn.commit()
        cur.close()

    def log(self, kind: str, text: str, meta: Optional[Dict[str, Any]] = None):
        """Store a small memory item (conversation, game result, etc.)."""
        if not self.enabled or not self.conn:
            return
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO friday_memory (kind, text, meta) VALUES (%s, %s, %s);",
                (kind, text, Json(meta) if Json and meta is not None else None),
            )
            self.conn.commit()
            cur.close()
        except Exception as e:
            print(f"FridayMemory log error: {e}")

