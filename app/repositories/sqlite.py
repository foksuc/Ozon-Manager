from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from app.domain.models import Operation, OperationItem, SnapshotItem


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS operations (
 operation_id TEXT PRIMARY KEY,
 action_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 created_by TEXT NOT NULL,
 requested_by_user TEXT NOT NULL,
 operation_type TEXT NOT NULL DEFAULT 'UPDATE_PRICE',
 status TEXT NOT NULL,
 confirmation_at TEXT,
 completed_at TEXT,
 error_summary TEXT,
 correlation_id TEXT,
 request_fingerprint TEXT,
 snapshot_id TEXT,
 source_snapshot_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_operations_action ON operations(action_id);
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_fingerprint ON operations(request_fingerprint);
CREATE TABLE IF NOT EXISTS operation_items (
 operation_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
 operation_id TEXT NOT NULL REFERENCES operations(operation_id),
 product_id TEXT NOT NULL,
 old_action_price TEXT NOT NULL,
 requested_action_price TEXT NOT NULL,
 actual_action_price TEXT,
 old_current_boost TEXT,
 new_current_boost TEXT,
 status TEXT NOT NULL,
 error TEXT,
 warning TEXT,
 verification_result TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_operation ON operation_items(operation_id);
CREATE INDEX IF NOT EXISTS idx_items_product ON operation_items(product_id);
CREATE TABLE IF NOT EXISTS promotion_snapshots (
 snapshot_id TEXT NOT NULL,
 operation_id TEXT NOT NULL REFERENCES operations(operation_id),
 action_id TEXT NOT NULL,
 product_id TEXT NOT NULL,
 price TEXT,
 action_price TEXT NOT NULL,
 current_boost TEXT,
 min_boost TEXT,
 max_boost TEXT,
 price_min_elastic TEXT,
 price_max_elastic TEXT,
 membership TEXT,
 timestamp TEXT NOT NULL,
 auto_add_date TEXT,
 present INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(snapshot_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_operation ON promotion_snapshots(operation_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_product ON promotion_snapshots(product_id);
CREATE TABLE IF NOT EXISTS errors (
 error_id INTEGER PRIMARY KEY AUTOINCREMENT,
 operation_id TEXT NOT NULL REFERENCES operations(operation_id),
 operation_item_id INTEGER,
 created_at TEXT NOT NULL,
 error_class TEXT NOT NULL,
 http_status INTEGER,
 endpoint TEXT,
 message TEXT NOT NULL,
 response_classification TEXT,
 retryable INTEGER NOT NULL DEFAULT 0,
 details TEXT
);
CREATE INDEX IF NOT EXISTS idx_errors_operation ON errors(operation_id);
CREATE TABLE IF NOT EXISTS promotions (
 action_id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 state TEXT,
 start_at TEXT,
 end_at TEXT,
 metadata_json TEXT,
 last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS participants (
 action_id TEXT NOT NULL,
 product_id TEXT NOT NULL,
 offer_id TEXT,
 name TEXT,
 membership TEXT,
 availability TEXT,
 last_seen_at TEXT NOT NULL,
 PRIMARY KEY(action_id, product_id)
);
"""


def _s(value):
    return None if value is None else str(value)


class SQLiteRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)
            columns = {row["name"] for row in con.execute("PRAGMA table_info(operations)")}
            if "operation_type" not in columns:
                con.execute("ALTER TABLE operations ADD COLUMN operation_type TEXT NOT NULL DEFAULT 'UPDATE_PRICE'")
            if "source_snapshot_id" not in columns:
                con.execute("ALTER TABLE operations ADD COLUMN source_snapshot_id TEXT")
            snapshot_columns = {row["name"] for row in con.execute("PRAGMA table_info(promotion_snapshots)")}
            if "auto_add_date" not in snapshot_columns:
                con.execute("ALTER TABLE promotion_snapshots ADD COLUMN auto_add_date TEXT")
            if "present" not in snapshot_columns:
                con.execute("ALTER TABLE promotion_snapshots ADD COLUMN present INTEGER NOT NULL DEFAULT 1")
            con.execute("""CREATE TABLE IF NOT EXISTS auto_add_snapshots (
                snapshot_id TEXT NOT NULL,
                operation_id TEXT NOT NULL REFERENCES operations(operation_id),
                action_id TEXT NOT NULL,
                auto_add_date TEXT NOT NULL,
                product_id TEXT NOT NULL,
                present INTEGER NOT NULL,
                price TEXT,
                action_price TEXT,
                quantity_to_auto_add TEXT,
                raw_json TEXT,
                timestamp TEXT NOT NULL,
                PRIMARY KEY(snapshot_id, product_id)
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_auto_add_snapshots_operation ON auto_add_snapshots(operation_id)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_auto_add_snapshots_product ON auto_add_snapshots(product_id)")

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def save_operation(self, op: Operation) -> None:
        with self.connect() as con:
            con.execute("""INSERT OR REPLACE INTO operations
                (operation_id,action_id,created_at,created_by,requested_by_user,operation_type,status,confirmation_at,completed_at,error_summary,correlation_id,request_fingerprint,snapshot_id,source_snapshot_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                op.operation_id, op.action_id, op.created_at, op.created_by, op.requested_by_user, op.operation_type,
                op.status.value, op.confirmation_at, op.completed_at, op.error_summary,
                op.correlation_id, op.request_fingerprint, op.snapshot_id, op.source_snapshot_id))
            con.execute("DELETE FROM operation_items WHERE operation_id=?", (op.operation_id,))
            for item in op.items:
                con.execute("""INSERT INTO operation_items
                    (operation_id,product_id,old_action_price,requested_action_price,actual_action_price,old_current_boost,new_current_boost,status,error,warning,verification_result)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                    item.operation_id, item.product_id, str(item.old_action_price), str(item.requested_action_price),
                    _s(item.actual_action_price), _s(item.old_current_boost), _s(item.new_current_boost),
                    item.status.value, item.error, item.warning, item.verification_result))

    def save_snapshot(self, snapshot_id: str, operation_id: str, items: Iterable[SnapshotItem]) -> None:
        with self.connect() as con:
            for s in items:
                con.execute("""INSERT INTO promotion_snapshots
                    (snapshot_id,operation_id,action_id,product_id,price,action_price,current_boost,min_boost,max_boost,price_min_elastic,price_max_elastic,membership,timestamp,auto_add_date,present)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    snapshot_id, operation_id, s.action_id, s.product_id, _s(s.price), str(s.action_price),
                    _s(s.current_boost), _s(s.min_boost), _s(s.max_boost), _s(s.price_min_elastic),
                    _s(s.price_max_elastic), s.membership, s.timestamp, s.auto_add_date, int(s.present)))

    def get_operation(self, operation_id: str):
        with self.connect() as con:
            return con.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()

    def list_operation_items(self, operation_id: str):
        with self.connect() as con:
            return con.execute("SELECT * FROM operation_items WHERE operation_id=? ORDER BY product_id", (operation_id,)).fetchall()

    def save_auto_add_absent_snapshot(self, snapshot_id: str, operation_id: str, action_id: str, auto_add_date: str, product_ids: list[str], *, action_prices: dict[str, Decimal] | None = None) -> None:
        action_prices = action_prices or {}
        with self.connect() as con:
            for product_id in product_ids:
                con.execute("""INSERT INTO auto_add_snapshots
                    (snapshot_id,operation_id,action_id,auto_add_date,product_id,present,price,action_price,quantity_to_auto_add,raw_json,timestamp)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                    snapshot_id, operation_id, str(action_id), str(auto_add_date), str(product_id), 0, None,
                    _s(action_prices.get(str(product_id))), None, json.dumps({"state": "ABSENT"}, ensure_ascii=False),
                    __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()))

    def get_snapshot(self, snapshot_id: str) -> list[sqlite3.Row]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM promotion_snapshots WHERE snapshot_id=? ORDER BY product_id", (snapshot_id,)).fetchall()
            if rows:
                return rows
            return con.execute("""SELECT snapshot_id,operation_id,action_id,product_id,price,action_price,NULL AS current_boost,
                    NULL AS min_boost,NULL AS max_boost,NULL AS price_min_elastic,NULL AS price_max_elastic,
                    'auto_add_absent' AS membership,timestamp,auto_add_date,present
                    FROM auto_add_snapshots WHERE snapshot_id=? ORDER BY product_id""", (snapshot_id,)).fetchall()

    def record_error(self, operation_id: str, error_class: str, message: str, *, operation_item_id=None, http_status=None, endpoint=None, response_classification=None, retryable=False, details=None):
        with self.connect() as con:
            con.execute("""INSERT INTO errors(operation_id,operation_item_id,created_at,error_class,http_status,endpoint,message,response_classification,retryable,details)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (operation_id, operation_item_id, __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), error_class, http_status, endpoint, message, response_classification, int(retryable), json.dumps(details) if details else None))

    def has_fingerprint(self, fingerprint: str) -> bool:
        with self.connect() as con:
            return con.execute("SELECT 1 FROM operations WHERE request_fingerprint=? LIMIT 1", (fingerprint,)).fetchone() is not None

    def list_operations(self, limit: int = 100):
        """Return promotion operations with UI/reporting aggregates.

        The operations table intentionally stores operation metadata only;
        product/success/failure counts live in operation_items.  Expose those
        derived values as aliases so history consumers do not depend on
        non-existent columns in the base table.
        """
        with self.connect() as con:
            return con.execute("""
                SELECT
                    o.*,
                    COALESCE(i.product_count, 0) AS product_count,
                    COALESCE(i.success_count, 0) AS success_count,
                    COALESCE(i.failed_count, 0) AS failed_count
                FROM operations AS o
                LEFT JOIN (
                    SELECT
                        operation_id,
                        COUNT(*) AS product_count,
                        SUM(CASE WHEN status IN ('SUCCESS', 'WARNING') THEN 1 ELSE 0 END) AS success_count,
                        SUM(CASE WHEN status IN ('SUCCESS', 'WARNING') THEN 0 ELSE 1 END) AS failed_count
                    FROM operation_items
                    GROUP BY operation_id
                ) AS i ON i.operation_id = o.operation_id
                ORDER BY o.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

# Stock-management persistence is intentionally separate from promotion history.
STOCK_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_operations (
 operation_id TEXT PRIMARY KEY,
 created_at TEXT NOT NULL,
 operation_type TEXT NOT NULL,
 status TEXT NOT NULL,
 product_count INTEGER NOT NULL,
 success_count INTEGER NOT NULL DEFAULT 0,
 failed_count INTEGER NOT NULL DEFAULT 0,
 snapshot_id TEXT,
 error_summary TEXT
);
CREATE INDEX IF NOT EXISTS idx_stock_operations_created ON stock_operations(created_at);
CREATE TABLE IF NOT EXISTS stock_operation_items (
 operation_id TEXT NOT NULL REFERENCES stock_operations(operation_id),
 row_key TEXT NOT NULL,
 product_id TEXT NOT NULL,
 sku TEXT,
 offer_id TEXT,
 warehouse_id INTEGER NOT NULL,
 warehouse_name TEXT,
 old_present INTEGER NOT NULL,
 old_reserved INTEGER NOT NULL,
 old_free_stock INTEGER NOT NULL,
 requested_free_stock INTEGER NOT NULL,
 actual_present INTEGER,
 actual_reserved INTEGER,
 actual_free_stock INTEGER,
 status TEXT NOT NULL,
 error TEXT,
 PRIMARY KEY(operation_id, row_key)
);
CREATE INDEX IF NOT EXISTS idx_stock_items_operation ON stock_operation_items(operation_id);
CREATE TABLE IF NOT EXISTS stock_snapshots (
 snapshot_id TEXT NOT NULL,
 operation_id TEXT NOT NULL REFERENCES stock_operations(operation_id),
 row_key TEXT NOT NULL,
 product_id TEXT NOT NULL,
 sku TEXT,
 offer_id TEXT,
 warehouse_id INTEGER NOT NULL,
 warehouse_name TEXT,
 present INTEGER NOT NULL,
 reserved INTEGER NOT NULL,
 free_stock INTEGER NOT NULL,
 updated_at TEXT,
 created_at TEXT NOT NULL,
 PRIMARY KEY(snapshot_id, row_key)
);
CREATE INDEX IF NOT EXISTS idx_stock_snapshots_operation ON stock_snapshots(operation_id);
"""

# Monkey-patch-free helpers are attached to the existing repository class below.
def _stock_init(self):
    with self.connect() as con:
        con.executescript(STOCK_SCHEMA)


def _create_stock_operation(self, *, operation_id, operation_type, status, product_count, snapshot_id=None):
    from datetime import datetime, timezone
    with self.connect() as con:
        con.execute("""INSERT INTO stock_operations
            (operation_id,created_at,operation_type,status,product_count,snapshot_id)
            VALUES(?,?,?,?,?,?)""", (
            operation_id, datetime.now(timezone.utc).isoformat(), operation_type, status, product_count, snapshot_id))


def _update_stock_operation_status(self, operation_id, status, *, success_count=None, failed_count=None, error_summary=None):
    fields = ["status=?"]
    values = [status]
    if success_count is not None:
        fields.append("success_count=?"); values.append(int(success_count))
    if failed_count is not None:
        fields.append("failed_count=?"); values.append(int(failed_count))
    if error_summary is not None:
        fields.append("error_summary=?"); values.append(str(error_summary))
    values.append(operation_id)
    with self.connect() as con:
        con.execute(f"UPDATE stock_operations SET {', '.join(fields)} WHERE operation_id=?", values)


def _save_stock_snapshot(self, snapshot_id, operation_id, changes):
    from datetime import datetime, timezone
    with self.connect() as con:
        for c in changes:
            con.execute("""INSERT INTO stock_snapshots
                (snapshot_id,operation_id,row_key,product_id,sku,offer_id,warehouse_id,warehouse_name,present,reserved,free_stock,updated_at,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                snapshot_id, operation_id, c.key, c.product_id, c.sku, c.offer_id, c.warehouse_id, c.warehouse_name,
                c.old_present, c.old_reserved, c.old_free_stock, c.updated_at,
                datetime.now(timezone.utc).isoformat()))


def _save_stock_item_result(self, operation_id, change, *, status, error=None, actual=None):
    actual = actual or {}
    with self.connect() as con:
        con.execute("""INSERT INTO stock_operation_items
            (operation_id,row_key,product_id,sku,offer_id,warehouse_id,warehouse_name,old_present,old_reserved,old_free_stock,requested_free_stock,actual_present,actual_reserved,actual_free_stock,status,error)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(operation_id,row_key) DO UPDATE SET
              actual_present=excluded.actual_present,
              actual_reserved=excluded.actual_reserved,
              actual_free_stock=excluded.actual_free_stock,
              status=excluded.status,
              error=excluded.error""", (
            operation_id, change.key, change.product_id, change.sku, change.offer_id, change.warehouse_id,
            change.warehouse_name, change.old_present, change.old_reserved, change.old_free_stock,
            change.requested_free_stock, actual.get("present"), actual.get("reserved"), actual.get("free_stock"), status, error))


def _list_stock_operation_items(self, operation_id):
    with self.connect() as con:
        return con.execute("SELECT * FROM stock_operation_items WHERE operation_id=? ORDER BY warehouse_name, product_id", (operation_id,)).fetchall()


def _list_stock_operations(self, limit=100):
    with self.connect() as con:
        return con.execute("SELECT * FROM stock_operations ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()


def _get_stock_operation(self, operation_id):
    with self.connect() as con:
        return con.execute("SELECT * FROM stock_operations WHERE operation_id=?", (operation_id,)).fetchone()


def _get_stock_snapshot(self, snapshot_id):
    with self.connect() as con:
        return con.execute("SELECT * FROM stock_snapshots WHERE snapshot_id=? ORDER BY warehouse_name, product_id", (snapshot_id,)).fetchall()

SQLiteRepository._stock_init = _stock_init
SQLiteRepository.create_stock_operation = _create_stock_operation
SQLiteRepository.update_stock_operation_status = _update_stock_operation_status
SQLiteRepository.save_stock_snapshot = _save_stock_snapshot
SQLiteRepository.save_stock_item_result = _save_stock_item_result
SQLiteRepository.list_stock_operation_items = _list_stock_operation_items
SQLiteRepository.list_stock_operations = _list_stock_operations
SQLiteRepository.get_stock_operation = _get_stock_operation
SQLiteRepository.get_stock_snapshot = _get_stock_snapshot

# Ensure stock tables exist for every repository instance without changing the
# existing promotion schema contract.
_original_sqlite_init = SQLiteRepository.__init__
def _patched_sqlite_init(self, path):
    _original_sqlite_init(self, path)
    self._stock_init()
SQLiteRepository.__init__ = _patched_sqlite_init
