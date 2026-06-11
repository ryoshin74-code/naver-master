"""SQLite 스키마와 연결 헬퍼. 모든 게시·승인·보고 기록의 단일 원장."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    published_at TEXT NOT NULL,            -- 유튜브 송출 시각 (ISO8601)
    detected_at  TEXT NOT NULL,            -- P1이 감지한 시각
    purchase_url TEXT,                     -- 영상 설명란에서 추출한 구매 링크
    publish_at   TEXT,                     -- D+1 게시 예정 시각
    status       TEXT NOT NULL DEFAULT 'detected',
    -- detected | hold_no_link | analyzing | drafted | approved | posted | failed
    analyzed_json TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    post_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id   TEXT NOT NULL REFERENCES videos(video_id),
    channel    TEXT NOT NULL CHECK (channel IN ('blog', 'cafe')),
    title      TEXT NOT NULL,
    body_path  TEXT,                       -- 본문 파일 경로 (ops/state/drafts/)
    url        TEXT,                       -- 게시 후 실제 URL
    status     TEXT NOT NULL DEFAULT 'draft',
    -- draft | approved | posting | posted | verified | failed | hold
    posted_at  TEXT
);

CREATE TABLE IF NOT EXISTS comments (
    comment_id  TEXT PRIMARY KEY,          -- 채널별 고유 식별자
    post_id     INTEGER NOT NULL REFERENCES posts(post_id),
    author      TEXT,
    body        TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'unclassified',
    -- reaction(호응성) | inquiry(문의성) | sensitive(민감성) | unclassified
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replies (
    reply_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id  TEXT NOT NULL REFERENCES comments(comment_id),
    body        TEXT NOT NULL,
    approval_id INTEGER REFERENCES approvals(approval_id),
    status      TEXT NOT NULL DEFAULT 'draft',  -- draft | approved | posted | hold | failed
    posted_at   TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL CHECK (target_type IN ('post', 'reply')),
    target_id   TEXT NOT NULL,
    verdict     TEXT NOT NULL CHECK (verdict IN ('PASS', 'HOLD', 'FAIL')),
    scores_json TEXT,
    reasons     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stats (
    date     TEXT NOT NULL,
    channel  TEXT NOT NULL CHECK (channel IN ('blog', 'cafe')),
    visitors INTEGER,
    views    INTEGER,
    likes    INTEGER,
    raw_json TEXT,
    PRIMARY KEY (date, channel)
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id     TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    type        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'issued',
    -- issued | doing | success | partial | failed | blocked | timeout
    issued_at   TEXT NOT NULL,
    finished_at TEXT,
    report_path TEXT
);
"""


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else DB_PATH
    if isinstance(db_path, Path) and str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    own = conn is None
    if conn is None:
        conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    if own:
        return conn
    return conn
