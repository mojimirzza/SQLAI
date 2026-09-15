"""
Zero-Mem SQLite Adapter — Star Schema Edition
----------------------------------------------
Stores raw query records in SQLite.
Builds MemoryContext via deterministic algorithms (regex, frequency counting).
Zero LLM usage for memory management.

Performance target: build_memory_context < 50ms on 10k records.
"""
import sqlite3
import json
import uuid
import re
from datetime import datetime, timedelta
from collections import Counter
from typing import Any

from ports.memory_store_port import MemoryStorePort, QueryRecord, MemoryContext


# --- Deterministic entity extractors for transaction monitoring domain ---

# Server name patterns (Persian/English)
SERVER_PATTERNS = [
    r"(?:سرور|server)[s\s]+([\u0600-\u06FFa-zA-Z0-9_-]+)",
    r"(?:سرور|server)\s*[:=]?\s*([\u0600-\u06FFa-zA-Z0-9_-]+)",
]

# Device category patterns
DEVICE_PATTERNS = [
    r"(?:دستگاه|device|ترمینال|terminal)[s\s]+([\u0600-\u06FFa-zA-Z0-9_-]+)",
    r"(?:نوع دستگاه|device type|device_category)[s\s]+([\u0600-\u06FFa-zA-Z0-9_-]+)",
]

# Status code patterns
STATUS_PATTERNS = [
    r"(?:وضعیت|status)[s\s]+(?:کد|code)?\s*[:=]?\s*(\d+)",
    r"(?:وضعیت|status)[s\s]+([\u0600-\u06FFa-zA-Z]+)",
]

# Time range patterns (Persian + English)
TIME_RANGE_PATTERNS = [
    r"(?:امروز|today)",
    r"(?:دیروز|yesterday)",
    r"(?:این هفته|this week)",
    r"(?:این ماه|this month)",
    r"(?:ماه قبل|last month)",
    r"(?:هفته قبل|last week)",
    r"(?:سه ماه|۳ ماه|سه‌ماه)[\s\w]*(?:اخیر|گذشته)?",
    r"(?:شش ماه|۶ ماه)[\s\w]*(?:اخیر|گذشته)?",
    r"(?:یک سال|۱ سال)[\s\w]*(?:اخیر|گذشته)?",
    r"(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)",
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"\d{4}-\d{2}-\d{2}",
    r"\d{8}",  # YYYYMMDD
]

# Time-of-day patterns
TIME_OF_DAY_PATTERNS = [
    r"(?:صبح|morning)",
    r"(?:ظهر|afternoon|بعدازظهر)",
    r"(?:عصر|evening|شب)",
    r"(?:شب|night)",
]

# Metric category patterns in query text
METRIC_PATTERNS = {
    "total_transactions": r"(?:تعداد تراکنش|تعداد تراکنش‌ها|transaction count|total transactions)",
    "total_amount": r"(?:مبلغ|مبلغ تراکنش|amount|total amount|جمع مبلغ)",
    "approval_rate": r"(?:نرخ موفقیت|approval rate|درصد موفق|موفقیت)",
    "avg_switch_latency": r"(?:latency|latancy|تأخیر|تاخیر|switch latency|میانگین تأخیر)",
    "stuck_transactions": r"(?:گیر|stuck|گیرکرده|معطل|pending|stuck transactions)",
    "hot_card_count": r"(?:کارت داغ|hot card|کارت مشکوک|مشکوک)",
    "error_count": r"(?:خطا|error|تعداد خطا|errors|خطاهای)",
}

# User preference signals
UNIT_PATTERNS = [
    (r"(?:میلیون|million)[\s\w]*(?:ریال|تومان|rial|toman)?", "million"),
    (r"(?:میلیارد|billion)[\s\w]*(?:ریال|تومان|rial|toman)?", "billion"),
    (r"(?:هزار|thousand)[\s\w]*(?:ریال|تومان|rial|toman)?", "thousand"),
]


class SQLiteMemoryAdapter(MemoryStorePort):
    """File-based SQLite memory. No external dependencies. Flat, append-only schema."""

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    intent_category TEXT,
                    intent_query_type TEXT DEFAULT 'aggregate',
                    intent_entities TEXT,
                    generated_sql TEXT,
                    sql_metric TEXT,
                    sql_dimensions TEXT,
                    sql_filters TEXT,
                    sql_joins TEXT,            -- JSON list of join dicts
                    execution_row_count INTEGER DEFAULT 0,
                    execution_success INTEGER DEFAULT 1,
                    response_type TEXT,
                    confidence REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_time ON query_records(user_id, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON query_records(session_id, timestamp DESC)")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(query_records)").fetchall()}
            if "intent_query_type" not in columns:
                conn.execute("ALTER TABLE query_records ADD COLUMN intent_query_type TEXT DEFAULT 'aggregate'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON query_records(intent_category, user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query_type ON query_records(intent_query_type, user_id)")
            conn.commit()

    def save(self, record: QueryRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO query_records
                (id, user_id, session_id, query_text, timestamp, intent_category,
                 intent_query_type, intent_entities, generated_sql, sql_metric, sql_dimensions,
                 sql_filters, sql_joins, execution_row_count, execution_success,
                 response_type, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id, record.user_id, record.session_id, record.query_text,
                record.timestamp.isoformat(), record.intent_category, record.intent_query_type,
                json.dumps(record.intent_entities, ensure_ascii=False),
                record.generated_sql, record.sql_metric,
                json.dumps(record.sql_dimensions, ensure_ascii=False),
                json.dumps(record.sql_filters, ensure_ascii=False),
                json.dumps(record.sql_joins, ensure_ascii=False),
                record.execution_row_count, 1 if record.execution_success else 0,
                record.response_type, record.confidence
            ))
            conn.commit()

    def build_memory_context(self, user_id: str, session_id: str,
                            current_query_text: str) -> MemoryContext:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT * FROM query_records
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (user_id,)).fetchall()

            records = [self._row_to_record(r) for r in rows]

            same_session = [r for r in records if r.session_id == session_id]

            # --- Entity-Context Graph ---
            category_counts = Counter(r.intent_category for r in records if r.intent_category)
            frequent_categories = [cat for cat, _ in category_counts.most_common(5)]

            entity_values: dict[str, list[str]] = {}
            for r in records:
                for key, val in (r.intent_entities or {}).items():
                    if val is not None and val != "":
                        entity_values.setdefault(key, []).append(str(val))

            frequent_entities = {}
            for key, vals in entity_values.items():
                top3 = [v for v, _ in Counter(vals).most_common(3)]
                if top3:
                    frequent_entities[key] = top3

            # --- Preferences ---
            all_texts = " ".join(r.query_text for r in records)
            user_preferences = self._extract_preferences(all_texts)

            # --- Cross-reference ---
            last_similar = self._find_last_similar(records, current_query_text)

            # --- Domain-specific extractions ---
            recent_texts = " ".join(r.query_text for r in records[:20])
            referenced_time_ranges = self._extract_time_ranges(recent_texts)
            referenced_servers = self._extract_servers(recent_texts)
            referenced_devices = self._extract_devices(recent_texts)
            referenced_statuses = self._extract_statuses(recent_texts)

        return MemoryContext(
            frequent_categories=frequent_categories,
            frequent_entities=frequent_entities,
            user_preferences=user_preferences,
            recent_queries=records[:10],
            same_session_queries=same_session[:5],
            last_similar_category=last_similar.get("category") if last_similar else None,
            last_similar_entities=last_similar.get("entities", {}) if last_similar else {},
            referenced_time_ranges=referenced_time_ranges,
            referenced_servers=referenced_servers,
            referenced_device_categories=referenced_devices,
            referenced_status_codes=referenced_statuses,
        )

    def get_session_history(self, session_id: str, limit: int = 10) -> list[QueryRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM query_records
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit)).fetchall()
            return [self._row_to_record(r) for r in rows]

    def _row_to_record(self, row: sqlite3.Row) -> QueryRecord:
        return QueryRecord(
            id=row["id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            query_text=row["query_text"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            intent_category=row["intent_category"] or "",
            intent_query_type=(row["intent_query_type"] if "intent_query_type" in row.keys() else None) or "aggregate",
            intent_entities=json.loads(row["intent_entities"] or "{}"),
            generated_sql=row["generated_sql"] or "",
            sql_metric=row["sql_metric"],
            sql_dimensions=json.loads(row["sql_dimensions"] or "[]"),
            sql_filters=json.loads(row["sql_filters"] or "[]"),
            sql_joins=json.loads(row["sql_joins"] or "[]"),
            execution_row_count=row["execution_row_count"] or 0,
            execution_success=bool(row["execution_success"]),
            response_type=row["response_type"] or "",
            confidence=row["confidence"] or 0.0,
        )

    def _extract_preferences(self, text: str) -> dict[str, str]:
        prefs = {}
        for pattern, unit_key in UNIT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                prefs["unit"] = unit_key
                break
        return prefs

    def _extract_time_ranges(self, text: str) -> list[str]:
        found = []
        for pattern in TIME_RANGE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)
        seen = set()
        return [m for m in found if not (m in seen or seen.add(m))]

    def _extract_servers(self, text: str) -> list[str]:
        found = []
        for pattern in SERVER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)
        seen = set()
        return [m for m in found if not (m in seen or seen.add(m))]

    def _extract_devices(self, text: str) -> list[str]:
        found = []
        for pattern in DEVICE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)
        seen = set()
        return [m for m in found if not (m in seen or seen.add(m))]

    def _extract_statuses(self, text: str) -> list[str]:
        found = []
        for pattern in STATUS_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)
        seen = set()
        return [m for m in found if not (m in seen or seen.add(m))]

    def _find_last_similar(self, records: list[QueryRecord],
                          current_text: str) -> dict[str, Any] | None:
        current_words = set(current_text.lower().split())
        best_score = 0
        best_record = None

        for r in records[:20]:
            record_words = set(r.query_text.lower().split())
            overlap = len(current_words & record_words)
            if overlap > best_score:
                best_score = overlap
                best_record = r

        if best_record and best_score >= 1:
            return {
                "category": best_record.intent_category,
                "entities": best_record.intent_entities,
                "query_text": best_record.query_text,
                "sql": best_record.generated_sql,
            }
        return None
