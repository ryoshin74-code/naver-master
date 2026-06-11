"""Phase 0 스모크 테스트 — 모든 외부 연결과 로컬 환경을 한 번에 점검한다.

사용: python -m naver_master smoke [--send]
--send 를 주면 카톡 실발송까지 테스트한다.
"""

from __future__ import annotations

import shutil
import subprocess

import requests

from . import kakao, watcher
from .config import CONFIG_PATH, PAUSE_PATH, env, is_paused, load_settings
from .db import connect, init_db


def _check(name: str, fn) -> tuple[str, bool, str]:
    try:
        detail = fn() or "OK"
        return name, True, str(detail)
    except Exception as exc:  # noqa: BLE001 - 점검 실패는 모아서 보고
        return name, False, str(exc)


def _settings() -> dict:
    return load_settings()


def run(send_test: bool = False) -> bool:
    checks: list[tuple[str, bool, str]] = []

    def check_settings():
        s = _settings()
        channel = (s.get("youtube") or {}).get("channel_id") or ""
        if not channel or channel.startswith("UCxxxx"):
            raise RuntimeError("youtube.channel_id 가 비어 있습니다")
        return f"settings.yaml OK (채널 {channel[:8]}…)"

    def check_env_keys():
        missing = [k for k in ("OPENAI_API_KEY", "KAKAO_REST_API_KEY") if not env(k)]
        if missing:
            raise RuntimeError(f".env 에 누락: {', '.join(missing)}")
        return "필수 키 존재"

    def check_db():
        conn = connect()
        init_db(conn)
        n = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        return f"DB OK (등록 영상 {n}건)"

    def check_rss():
        s = _settings()
        channel = (s.get("youtube") or {}).get("channel_id") or ""
        entries = watcher.parse_feed(watcher.fetch_feed(channel))
        if not entries:
            raise RuntimeError("RSS 응답에 영상이 없습니다 (채널 ID 확인)")
        return f"RSS OK (최근 영상 {len(entries)}건, 최신: {entries[0].title[:30]})"

    def check_tool(tool: str):
        def inner():
            path = shutil.which(tool)
            if not path:
                raise RuntimeError(f"{tool} 미설치 (brew install {tool})")
            out = subprocess.run(
                [tool, "--version"], capture_output=True, text=True, timeout=20
            )
            ver = (out.stdout or out.stderr).strip().splitlines()[0][:40]
            return f"{ver}"
        return inner

    def check_openai():
        key = env("OPENAI_API_KEY", required=True)
        resp = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"키 검증 실패 ({resp.status_code}): {resp.text[:120]}")
        model = (_settings().get("llm") or {}).get("model", "")
        ids = {m.get("id") for m in resp.json().get("data", [])}
        if model and model not in ids:
            return f"키 OK — 단, 설정 모델 '{model}' 이 목록에 없음 (settings.yaml 확인)"
        return f"키 OK (설정 모델: {model or '미지정'})"

    def check_kakao():
        kakao.refresh()
        return "토큰 갱신 OK (rotation 저장 완료)"

    def check_kakao_send():
        n = kakao.send_text("[네이버마스터] 스모크 테스트 — 이 메시지가 보이면 보고 채널 정상입니다.")
        return f"실발송 OK ({n}건)"

    def check_naver_keys():
        missing = [k for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET") if not env(k)]
        if missing:
            raise RuntimeError(
                f".env 에 누락: {', '.join(missing)} (카페 API 사용 전까지는 경고만)"
            )
        return "카페 API 키 존재 (권한 발급 여부는 첫 게시 시 확인)"

    def check_pause():
        if is_paused():
            raise RuntimeError(f"비상정지 상태입니다: {PAUSE_PATH} 삭제 전까지 게시 중단")
        return "PAUSE 없음 (정상 운영 상태)"

    checks.append(_check("설정 파일", check_settings))
    checks.append(_check("환경변수(.env)", check_env_keys))
    checks.append(_check("SQLite DB", check_db))
    checks.append(_check("유튜브 RSS", check_rss))
    checks.append(_check("yt-dlp", check_tool("yt-dlp")))
    checks.append(_check("ffmpeg", check_tool("ffmpeg")))
    checks.append(_check("OpenAI API", check_openai))
    checks.append(_check("카카오 토큰", check_kakao))
    if send_test:
        checks.append(_check("카카오 실발송", check_kakao_send))
    checks.append(_check("네이버 API 키", check_naver_keys))
    checks.append(_check("비상정지 플래그", check_pause))

    print()
    print("=" * 64)
    print(" 네이버 마스터 — Phase 0 스모크 테스트")
    print("=" * 64)
    all_ok = True
    for name, ok, detail in checks:
        mark = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f" {mark} {name:14s} {detail}")
    print("=" * 64)
    print(" 종합: " + ("모든 점검 통과 — Phase 1 진행 가능" if all_ok else "실패 항목을 해결한 뒤 다시 실행하세요"))
    print("=" * 64)
    return all_ok
