"""SQLite 连接与查询助手。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import pandas as pd

from config import DATA_DIR, DB_PATH

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# activities 表写入列（与 insert_activity 对应）
ACTIVITY_COLS = [
    "filename", "source", "sport", "start_time", "duration_s", "timer_s",
    "distance_m", "avg_speed_mps", "max_speed_mps", "avg_hr", "max_hr",
    "avg_cadence", "avg_stride_length", "avg_vertical_oscillation", "avg_stance_time",
    "avg_power", "calories", "ele_gain_m", "ele_loss_m", "avg_grade",
]


@contextmanager
def get_conn():
    """上下文管理的连接：正常退出时提交，最终关闭。

    加了 timeout 和每次连接都设 WAL，以应对大批量导入时的短暂锁冲突。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)  # 默认 5 秒改成 30 秒
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # 每次连接都设(WAL 是连接级设置)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """建表（幂等）。同时把 WAL 持久化（跨连接生效）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate(conn)


def _column_exists(conn, table: str, col: str) -> bool:
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def _migrate(conn) -> None:
    """补齐旧库缺失的列（CREATE TABLE IF NOT EXISTS 不会为已存在的表加列）。幂等。"""
    additions = {
        "records": [
            ("stride_length_m", "REAL"),
            ("vertical_oscillation_cm", "REAL"),
            ("stance_time_ms", "REAL"),
        ],
        "activities": [
            ("avg_stride_length", "REAL"),
            ("avg_vertical_oscillation", "REAL"),
            ("avg_stance_time", "REAL"),
        ],
    }
    for table, cols in additions.items():
        for col, typ in cols:
            if not _column_exists(conn, table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


# --------------------------------------------------------------------------- #
# 查询
# --------------------------------------------------------------------------- #
def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


# --------------------------------------------------------------------------- #
# 写入
# --------------------------------------------------------------------------- #
def insert_activity(data: dict) -> int:
    placeholders = ",".join("?" * len(ACTIVITY_COLS))
    sql = f"INSERT INTO activities ({','.join(ACTIVITY_COLS)}) VALUES ({placeholders})"
    with get_conn() as conn:
        cur = conn.execute(sql, [data.get(c) for c in ACTIVITY_COLS])
        return cur.lastrowid


def insert_records(activity_id: int, records: list[dict]) -> None:
    if not records:
        return
    rows = [
        (
            activity_id, r.get("elapsed_s"), r.get("hr"), r.get("cadence"),
            r.get("speed_mps"), r.get("distance_m"), r.get("altitude_m"),
            r.get("lat"), r.get("lon"), r.get("power"),
            r.get("stride_length_m"), r.get("vertical_oscillation_cm"), r.get("stance_time_ms"),
        )
        for r in records
    ]
    sql = (
        "INSERT INTO records (activity_id, elapsed_s, hr, cadence, speed_mps, "
        "distance_m, altitude_m, lat, lon, power, "
        "stride_length_m, vertical_oscillation_cm, stance_time_ms) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    with get_conn() as conn:
        conn.executemany(sql, rows)


def insert_laps(activity_id: int, laps: list[dict]) -> None:
    if not laps:
        return
    rows = [
        (
            activity_id, l.get("lap_index"), l.get("start_time"), l.get("duration_s"),
            l.get("distance_m"), l.get("avg_hr"), l.get("max_hr"),
            l.get("avg_speed_mps"), l.get("calories"),
        )
        for l in laps
    ]
    sql = (
        "INSERT INTO laps (activity_id, lap_index, start_time, duration_s, distance_m, "
        "avg_hr, max_hr, avg_speed_mps, calories) VALUES (?,?,?,?,?,?,?,?,?)"
    )
    with get_conn() as conn:
        conn.executemany(sql, rows)


# --------------------------------------------------------------------------- #
# 便捷
# --------------------------------------------------------------------------- #
def filename_exists(filename: str) -> bool:
    return query_one("SELECT 1 AS x FROM activities WHERE filename=? LIMIT 1", (filename,)) is not None


def activity_count() -> int:
    row = query_one("SELECT COUNT(*) AS n FROM activities")
    return int(row["n"]) if row else 0


def delete_activity(activity_id: int) -> None:
    execute("DELETE FROM activities WHERE id=?", (activity_id,))
