"""설정·경로·환경변수 로딩."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "settings.yaml"
ENV_PATH = ROOT / ".env"
STATE_DIR = ROOT / "ops" / "state"
DB_PATH = STATE_DIR / "naver_master.db"
TOKENS_DIR = STATE_DIR / "tokens"
PAUSE_PATH = STATE_DIR / "PAUSE"
LOGS_DIR = STATE_DIR / "logs"


def load_env(path: Path = ENV_PATH) -> None:
    """.env 를 환경변수로 로드한다. 이미 설정된 변수는 덮어쓰지 않는다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(key: str, required: bool = False) -> str | None:
    load_env()
    value = os.environ.get(key) or None
    if required and not value:
        raise SystemExit(f"환경변수 {key} 가 필요합니다. .env.example 을 참고해 .env 에 채워 주세요.")
    return value


def load_settings(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise SystemExit(
            f"설정 파일이 없습니다: {path}\n"
            "config/settings.example.yaml 을 복사해 config/settings.yaml 을 만들어 주세요."
        )
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_paused() -> bool:
    """비상정지 플래그. 존재하면 모든 게시·답글·발송 작업을 중단한다."""
    return PAUSE_PATH.exists()
