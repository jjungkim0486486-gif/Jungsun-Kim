"""
Storage Layer - SQLite 기반 상품 이력 및 트렌드 데이터 저장
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "radar.db")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """DB 초기화 - 테이블 생성"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
            -- 상품 기본 정보
            CREATE TABLE IF NOT EXISTS products (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT UNIQUE NOT NULL,
                source          TEXT NOT NULL,
                title           TEXT NOT NULL,
                category        TEXT,
                price_usd       REAL,
                cost_usd        REAL,
                rating          REAL,
                review_count    INTEGER,
                image_url       TEXT,
                product_url     TEXT,
                supplier        TEXT,
                shipping_days   INTEGER,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            -- 트렌드 스냅샷 (시간대별 기록)
            CREATE TABLE IF NOT EXISTS trend_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT NOT NULL,
                snapshot_at     TEXT NOT NULL,
                search_volume   INTEGER DEFAULT 0,
                sales_count     INTEGER DEFAULT 0,
                tiktok_views    INTEGER DEFAULT 0,
                tiktok_videos   INTEGER DEFAULT 0,
                viral_score     REAL DEFAULT 0,
                trend_score     REAL DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );

            -- 레이더 점수 (최종 평가)
            CREATE TABLE IF NOT EXISTS radar_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT NOT NULL,
                scored_at       TEXT NOT NULL,
                viral_score     REAL DEFAULT 0,
                trend_score     REAL DEFAULT 0,
                profit_score    REAL DEFAULT 0,
                quality_score   REAL DEFAULT 0,
                shipping_score  REAL DEFAULT 0,
                total_score     REAL DEFAULT 0,
                is_24h_spike    INTEGER DEFAULT 0,
                is_3d_repeat    INTEGER DEFAULT 0,
                spike_ratio     REAL DEFAULT 0,
                repeat_days     INTEGER DEFAULT 0,
                meta_json       TEXT DEFAULT '{}',
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );

            -- 익스포트 이력
            CREATE TABLE IF NOT EXISTS export_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT NOT NULL,
                platform        TEXT NOT NULL,
                exported_at     TEXT DEFAULT (datetime('now')),
                status          TEXT DEFAULT 'pending',
                external_id     TEXT,
                meta_json       TEXT DEFAULT '{}'
            );

            -- 인덱스
            CREATE INDEX IF NOT EXISTS idx_trend_product ON trend_snapshots(product_id, snapshot_at);
            CREATE INDEX IF NOT EXISTS idx_radar_total ON radar_scores(total_score DESC);
            CREATE INDEX IF NOT EXISTS idx_radar_dated ON radar_scores(scored_at, total_score DESC);
        """)


def upsert_product(p: dict) -> None:
    """상품 정보 삽입 또는 업데이트"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO products (product_id, source, title, category, price_usd, cost_usd,
                rating, review_count, image_url, product_url, supplier, shipping_days, updated_at)
            VALUES (:product_id, :source, :title, :category, :price_usd, :cost_usd,
                :rating, :review_count, :image_url, :product_url, :supplier, :shipping_days, datetime('now'))
            ON CONFLICT(product_id) DO UPDATE SET
                title = excluded.title,
                price_usd = excluded.price_usd,
                cost_usd = excluded.cost_usd,
                rating = excluded.rating,
                review_count = excluded.review_count,
                shipping_days = excluded.shipping_days,
                updated_at = datetime('now')
        """, p)


def insert_snapshot(product_id: str, data: dict) -> None:
    """트렌드 스냅샷 저장"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO trend_snapshots
                (product_id, snapshot_at, search_volume, sales_count,
                 tiktok_views, tiktok_videos, viral_score, trend_score)
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            data.get("search_volume", 0),
            data.get("sales_count", 0),
            data.get("tiktok_views", 0),
            data.get("tiktok_videos", 0),
            data.get("viral_score", 0),
            data.get("trend_score", 0),
        ))


def insert_radar_score(product_id: str, scores: dict) -> None:
    """레이더 최종 점수 저장"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO radar_scores
                (product_id, scored_at, viral_score, trend_score, profit_score,
                 quality_score, shipping_score, total_score,
                 is_24h_spike, is_3d_repeat, spike_ratio, repeat_days, meta_json)
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            scores.get("viral_score", 0),
            scores.get("trend_score", 0),
            scores.get("profit_score", 0),
            scores.get("quality_score", 0),
            scores.get("shipping_score", 0),
            scores.get("total_score", 0),
            int(scores.get("is_24h_spike", False)),
            int(scores.get("is_3d_repeat", False)),
            scores.get("spike_ratio", 0),
            scores.get("repeat_days", 0),
            json.dumps(scores.get("meta", {}), ensure_ascii=False),
        ))


def get_recent_snapshots(product_id: str, hours: int = 24) -> list[dict]:
    """최근 N시간 내 스냅샷 조회"""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM trend_snapshots
            WHERE product_id = ? AND snapshot_at >= ?
            ORDER BY snapshot_at ASC
        """, (product_id, cutoff)).fetchall()
        return [dict(r) for r in rows]


def get_daily_scores(product_id: str, days: int = 3) -> list[dict]:
    """최근 N일 레이더 점수 조회"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT DATE(scored_at) as day, AVG(total_score) as avg_score,
                   MAX(viral_score) as peak_viral, MAX(trend_score) as peak_trend
            FROM radar_scores
            WHERE product_id = ? AND scored_at >= ?
            GROUP BY DATE(scored_at)
            ORDER BY day ASC
        """, (product_id, cutoff)).fetchall()
        return [dict(r) for r in rows]


def get_top_products(limit: int = 20, min_score: float = 65.0) -> list[dict]:
    """오늘 기준 최상위 상품 조회"""
    today = datetime.utcnow().date().isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.*, rs.total_score, rs.viral_score, rs.trend_score,
                   rs.profit_score, rs.quality_score, rs.shipping_score,
                   rs.is_24h_spike, rs.is_3d_repeat, rs.spike_ratio,
                   rs.repeat_days, rs.meta_json, rs.scored_at
            FROM radar_scores rs
            JOIN products p ON p.product_id = rs.product_id
            WHERE DATE(rs.scored_at) = ? AND rs.total_score >= ?
            ORDER BY rs.total_score DESC
            LIMIT ?
        """, (today, min_score, limit)).fetchall()
        return [dict(r) for r in rows]


def get_all_tracked_products() -> list[dict]:
    """추적 중인 모든 상품 조회"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.*, MAX(rs.total_score) as best_score
            FROM products p
            LEFT JOIN radar_scores rs ON rs.product_id = p.product_id
            GROUP BY p.product_id
            ORDER BY best_score DESC NULLS LAST
        """).fetchall()
        return [dict(r) for r in rows]
