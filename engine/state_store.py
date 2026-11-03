"""
SQLite State Store & Delivery Ledger for IntentRadar (v3.1).
Resolves Audit Finding #8:
- Cross-run deduplication by (source, source_id)
- Content hash & version tracking when an existing thread/issue is updated
- Strict separation of published_at, updated_at, first_seen_at, and last_seen_at
- Per-client delivery version tracking so unchanged threads are never re-pushed, while updated threads trigger re-evaluation
"""

import hashlib
import os
import sqlite3
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, Optional


def compute_content_hash(title: str, content: str) -> str:
    norm_title = " ".join((title or "").strip().split())
    norm_body = " ".join((content or "").strip().split())
    payload = f"{norm_title}\n{norm_body}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class IntentStateStore:
    """Thread-safe SQLite store for signal deduplication, version tracking, and client delivery history."""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            state_dir = os.path.join(tempfile.gettempdir(), "intent_radar_internal")
            os.makedirs(state_dir, exist_ok=True)
            db_path = os.path.join(state_dir, "intent_radar_state.sqlite3")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS signals_ledger (
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    normalized_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    version_num INTEGER NOT NULL DEFAULT 1,
                    raw_content TEXT NOT NULL,
                    PRIMARY KEY (source, source_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS client_deliveries (
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    delivered_version INTEGER NOT NULL,
                    delivered_at TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    PRIMARY KEY (source, source_id, client_id)
                )
                """
            )
            self._conn.commit()

    def upsert_signal(self, sig: Any) -> Dict[str, Any]:
        """
        Upserts a signal by (source, source_id).
        Returns dict with keys:
        - status: 'new' | 'updated' | 'unchanged'
        - version_num: int
        - should_analyze: bool
        - first_seen_at: str
        - last_seen_at: str
        """
        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        source = getattr(sig, "source", "Unknown")
        source_id = getattr(sig, "source_id", getattr(sig, "id", ""))
        norm_url = getattr(sig, "normalized_url", getattr(sig, "url", ""))
        title = getattr(sig, "title", "")
        author = getattr(sig, "author", "Unknown")
        published_at = getattr(sig, "timestamp", now_utc) or now_utc
        updated_at = getattr(sig, "updated_at", None) or published_at
        collected_at = getattr(sig, "collected_at", now_utc) or now_utc
        raw_text = getattr(sig, "raw_content", None) or getattr(sig, "content", "")
        c_hash = compute_content_hash(title, raw_text)

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT content_hash, version_num, first_seen_at, published_at FROM signals_ledger WHERE source = ? AND source_id = ?",
                (source, source_id),
            )
            row = cur.fetchone()

            if row is None:
                version_num = 1
                status = "new"
                should_analyze = True
                first_seen = collected_at
                cur.execute(
                    """
                    INSERT INTO signals_ledger (
                        source, source_id, normalized_url, title, author,
                        published_at, updated_at, first_seen_at, last_seen_at,
                        content_hash, version_num, raw_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source,
                        source_id,
                        norm_url,
                        title,
                        author,
                        published_at,
                        updated_at,
                        first_seen,
                        collected_at,
                        c_hash,
                        version_num,
                        raw_text,
                    ),
                )
            elif row["content_hash"] != c_hash:
                version_num = int(row["version_num"]) + 1
                status = "updated"
                should_analyze = True
                first_seen = row["first_seen_at"]
                # Preserve original published_at while recording new updated_at
                orig_pub = row["published_at"] or published_at
                cur.execute(
                    """
                    UPDATE signals_ledger
                    SET normalized_url = ?, title = ?, author = ?,
                        published_at = ?, updated_at = ?, last_seen_at = ?,
                        content_hash = ?, version_num = ?, raw_content = ?
                    WHERE source = ? AND source_id = ?
                    """,
                    (
                        norm_url,
                        title,
                        author,
                        orig_pub,
                        updated_at,
                        collected_at,
                        c_hash,
                        version_num,
                        raw_text,
                        source,
                        source_id,
                    ),
                )
            else:
                version_num = int(row["version_num"])
                status = "unchanged"
                should_analyze = False
                first_seen = row["first_seen_at"]
                cur.execute(
                    """
                    UPDATE signals_ledger
                    SET last_seen_at = ?, updated_at = ?
                    WHERE source = ? AND source_id = ?
                    """,
                    (collected_at, updated_at, source, source_id),
                )

            self._conn.commit()

        sig.content_hash = c_hash
        sig.version_num = version_num
        sig.sync_status = status
        sig.first_seen_at = first_seen
        sig.last_seen_at = collected_at
        return {
            "status": status,
            "version_num": version_num,
            "content_hash": c_hash,
            "should_analyze": should_analyze,
            "first_seen_at": first_seen,
            "last_seen_at": collected_at,
        }

    def should_deliver(self, source: str, source_id: str, client_id: str, version_num: int) -> bool:
        """Returns True if this (source, source_id) has never been delivered to client_id or has a newer version_num."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT delivered_version FROM client_deliveries WHERE source = ? AND source_id = ? AND client_id = ?",
                (source, source_id, client_id),
            )
            row = cur.fetchone()
            if row is None:
                return True
            return int(row["delivered_version"]) < int(version_num)

    def record_delivery(
        self,
        source: str,
        source_id: str,
        client_id: str,
        version_num: int,
        channel: str = "webhook",
    ) -> None:
        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO client_deliveries (source, source_id, client_id, delivered_version, delivered_at, channel)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, source_id, client_id) DO UPDATE SET
                    delivered_version = excluded.delivered_version,
                    delivered_at = excluded.delivered_at,
                    channel = excluded.channel
                """,
                (source, source_id, client_id, int(version_num), now_utc, channel),
            )
            self._conn.commit()

    def get_signal_record(self, source: str, source_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM signals_ledger WHERE source = ? AND source_id = ?",
                (source, source_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
