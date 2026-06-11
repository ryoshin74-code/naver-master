"""카카오 '나에게 보내기' — 아침 보고와 긴급 알림 발송 채널.

토큰은 ops/state/tokens/kakao.json 에 보관(커밋 금지)하며,
refresh token rotation(갱신 시 새 refresh token 저장)을 반드시 따른다.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from .config import TOKENS_DIR, env

AUTH_HOST = "https://kauth.kakao.com"
API_HOST = "https://kapi.kakao.com"
TOKEN_PATH = TOKENS_DIR / "kakao.json"
TEXT_LIMIT = 200  # 텍스트 템플릿 최대 길이 (초과분은 카카오가 자름)
DEFAULT_REDIRECT_URI = "http://localhost:8889"


# ── 토큰 보관 ──────────────────────────────────────────────


def _load_tokens() -> dict:
    if not TOKEN_PATH.exists():
        raise SystemExit(
            "카카오 토큰이 없습니다. 먼저 `python -m naver_master kakao-auth` 를 실행해"
            " 1회 인증을 완료해 주세요."
        )
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


def _save_tokens(tokens: dict) -> None:
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    merged = {}
    if TOKEN_PATH.exists():
        merged = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    merged.update({k: v for k, v in tokens.items() if v is not None})
    merged["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    TOKEN_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    os.chmod(TOKEN_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600


# ── OAuth ─────────────────────────────────────────────────


def build_authorize_url(redirect_uri: str = DEFAULT_REDIRECT_URI) -> str:
    params = {
        "client_id": env("KAKAO_REST_API_KEY", required=True),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "talk_message",
    }
    return f"{AUTH_HOST}/oauth/authorize?{urlencode(params)}"


def parse_code(pasted: str) -> str:
    """사용자가 붙여넣은 리다이렉트 URL(또는 code 값)에서 인가 코드를 꺼낸다."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        qs = parse_qs(urlparse(pasted).query)
        codes = qs.get("code")
        if not codes:
            raise SystemExit("URL에 code 파라미터가 없습니다. 주소창 전체를 붙여넣어 주세요.")
        return codes[0]
    return pasted


def _token_request(data: dict) -> dict:
    secret = env("KAKAO_CLIENT_SECRET")
    if secret:
        data["client_secret"] = secret
    resp = requests.post(f"{AUTH_HOST}/oauth/token", data=data, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"카카오 토큰 요청 실패 ({resp.status_code}): {resp.text}")
    return resp.json()


def exchange_code(code: str, redirect_uri: str = DEFAULT_REDIRECT_URI) -> dict:
    tokens = _token_request(
        {
            "grant_type": "authorization_code",
            "client_id": env("KAKAO_REST_API_KEY", required=True),
            "redirect_uri": redirect_uri,
            "code": code,
        }
    )
    _save_tokens(tokens)
    return tokens


def refresh() -> str:
    """access token 갱신. 새 refresh token이 내려오면 반드시 저장(rotation)."""
    stored = _load_tokens()
    tokens = _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": env("KAKAO_REST_API_KEY", required=True),
            "refresh_token": stored["refresh_token"],
        }
    )
    _save_tokens(tokens)
    return tokens["access_token"]


# ── 발송 ──────────────────────────────────────────────────


def split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """200자 제한 대응 — 줄 단위로 욕심껏 묶고, 한 줄이 너무 길면 강제 분할."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks or [""]


def _post_memo(access_token: str, text: str, web_url: str | None) -> requests.Response:
    template: dict = {"object_type": "text", "text": text}
    if web_url:
        template["link"] = {"web_url": web_url, "mobile_web_url": web_url}
    return requests.post(
        f"{API_HOST}/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=30,
    )


def send_text(text: str, web_url: str | None = None) -> int:
    """긴 텍스트는 분할 발송한다. 401이면 1회 갱신 후 재시도. 반환: 발송 건수."""
    stored = _load_tokens()
    access_token = stored.get("access_token", "")
    sent = 0
    for chunk in split_text(text):
        resp = _post_memo(access_token, chunk, web_url)
        if resp.status_code == 401:
            access_token = refresh()
            resp = _post_memo(access_token, chunk, web_url)
        if resp.status_code != 200:
            raise RuntimeError(f"카카오 발송 실패 ({resp.status_code}): {resp.text}")
        sent += 1
    return sent


def try_send(text: str, web_url: str | None = None) -> bool:
    """실패해도 파이프라인을 멈추지 않는 발송 (경고·알림용)."""
    try:
        send_text(text, web_url)
        return True
    except (SystemExit, Exception) as exc:  # noqa: BLE001 - 알림 실패는 치명적이지 않다
        print(f"[kakao] 발송 실패 (무시하고 계속): {exc}")
        return False
