"""P1 감지 — 유튜브 채널 RSS를 폴링해 새 영상을 DB에 등록하고 D+1 게시를 예약한다.

RSS는 API 쿼터·키 없이 동작하며 영상 설명(media:description)까지 내려주므로
구매 링크 추출도 여기서 처리한다.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlite3 import Connection

import requests

from .config import load_settings
from .db import connect, init_db

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

URL_RE = re.compile(r"https?://[^\s)\]>'\"<]+")
YOUTUBE_HOSTS = ("youtube.com", "youtu.be")


@dataclass
class FeedEntry:
    video_id: str
    title: str
    published_at: str  # ISO8601
    description: str


def fetch_feed(channel_id: str, timeout: int = 30) -> str:
    resp = requests.get(FEED_URL.format(channel_id=channel_id), timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_feed(xml_text: str) -> list[FeedEntry]:
    root = ET.fromstring(xml_text)
    entries: list[FeedEntry] = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=NS)
        title = entry.findtext("atom:title", default="", namespaces=NS)
        published = entry.findtext("atom:published", default="", namespaces=NS)
        description = entry.findtext(
            "media:group/media:description", default="", namespaces=NS
        )
        if video_id:
            entries.append(FeedEntry(video_id, title, published, description))
    return entries


def extract_purchase_url(description: str) -> str | None:
    """설명란에서 유튜브가 아닌 첫 번째 링크를 구매 링크로 본다."""
    for url in URL_RE.findall(description or ""):
        host = url.split("/", 3)[2].lower() if "://" in url else ""
        if not any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS):
            return url.rstrip(".,;")
    return None


def process_entries(
    conn: Connection, entries: list[FeedEntry], delay_hours: int = 24
) -> tuple[list[dict], list[dict]]:
    """새 영상을 등록한다. 반환: (정상 등록 목록, 구매링크 없어 보류된 목록)."""
    registered: list[dict] = []
    held: list[dict] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for e in entries:
        exists = conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ?", (e.video_id,)
        ).fetchone()
        if exists:
            continue
        purchase_url = extract_purchase_url(e.description)
        try:
            published = datetime.fromisoformat(e.published_at)
        except ValueError:
            published = datetime.now(timezone.utc)
        publish_at = (published + timedelta(hours=delay_hours)).isoformat(
            timespec="seconds"
        )
        status = "detected" if purchase_url else "hold_no_link"
        conn.execute(
            "INSERT INTO videos (video_id, title, published_at, detected_at,"
            " purchase_url, publish_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (e.video_id, e.title, e.published_at, now, purchase_url, publish_at, status),
        )
        record = {
            "video_id": e.video_id,
            "title": e.title,
            "purchase_url": purchase_url,
            "publish_at": publish_at,
        }
        (registered if purchase_url else held).append(record)
    conn.commit()
    return registered, held


def due_videos(conn: Connection) -> list[dict]:
    """게시 예정 시각이 지난 미처리 영상 — P2 분석 트리거 대상."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT video_id, title, publish_at, status FROM videos"
        " WHERE status = 'detected' AND publish_at <= ? ORDER BY publish_at",
        (now,),
    ).fetchall()
    return [dict(r) for r in rows]


def poll(send_alerts: bool = True) -> dict:
    """1회 폴링. launchd가 매시 호출한다."""
    settings = load_settings()
    channel_id = (settings.get("youtube") or {}).get("channel_id") or ""
    if not channel_id or channel_id.startswith("UCxxxx"):
        raise SystemExit("config/settings.yaml 의 youtube.channel_id 를 채워 주세요.")
    delay = int((settings.get("youtube") or {}).get("post_delay_hours", 24))

    entries = parse_feed(fetch_feed(channel_id))
    conn = connect()
    init_db(conn)
    released = retry_held(conn, entries)
    registered, held = process_entries(conn, entries, delay)
    conn.close()

    if held and send_alerts:
        from . import kakao

        for h in held:
            kakao.try_send(
                f"[네이버마스터] 경고: 새 영상 '{h['title']}' 설명란에서 구매 링크를"
                " 찾지 못해 보류했습니다. 설명란에 링크를 추가하면 다음 폴링에서"
                " 자동 해제됩니다."
            )
    return {
        "checked": len(entries),
        "registered": registered,
        "held": held,
        "released": released,
    }


def retry_held(conn: Connection, entries: list[FeedEntry]) -> list[dict]:
    """보류(hold_no_link) 건의 설명란을 다시 확인해 링크가 생겼으면 해제한다."""
    released: list[dict] = []
    held_rows = conn.execute(
        "SELECT video_id FROM videos WHERE status = 'hold_no_link'"
    ).fetchall()
    held_ids = {r["video_id"] for r in held_rows}
    for e in entries:
        if e.video_id not in held_ids:
            continue
        purchase_url = extract_purchase_url(e.description)
        if purchase_url:
            conn.execute(
                "UPDATE videos SET purchase_url = ?, status = 'detected'"
                " WHERE video_id = ?",
                (purchase_url, e.video_id),
            )
            released.append({"video_id": e.video_id, "purchase_url": purchase_url})
    conn.commit()
    return released
