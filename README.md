# 네이버 마스터

전자동 네이버 카페·블로그 운영 관리 및 결과보고 시스템.
기획·정책은 [`CLAUDE.md`](CLAUDE.md)와 [`docs/`](docs/)를 본다.

## alfredo (MacBook Pro M5) 설치 — Phase 0

```bash
# 0. 요구사항: Python 3.11+, Homebrew
brew install yt-dlp ffmpeg

# 1. 저장소와 의존성 (venv — macOS 시스템 파이썬 제약 대응)
git clone -b claude/great-planck-l3y8eb https://github.com/ryoshin74-code/naver-master.git ~/naver-master
cd ~/naver-master
python3 -m venv .venv
.venv/bin/pip install -e .

# 2. 설정 채우기
cp config/settings.example.yaml config/settings.yaml   # 채널 ID·카페·말투 샘플
cp .env.example .env                                   # OpenAI·카카오·네이버 키

# 3. DB 초기화 + 카카오 1회 인증
.venv/bin/python3 -m naver_master init-db
.venv/bin/python3 -m naver_master kakao-auth   # 안내에 따라 브라우저 인증 1회

# 4. 스모크 테스트 (전부 ✅ 이면 Phase 1 진행 가능)
.venv/bin/python3 -m naver_master smoke --send
```

## launchd 등록 (P1 감지, 매시 폴링)

```bash
REPO=$HOME/naver-master
mkdir -p "$REPO/ops/state/logs"
sed "s|__REPO__|$REPO|g" "$REPO/ops/launchd/com.navermaster.watch.plist" \
  > ~/Library/LaunchAgents/com.navermaster.watch.plist
launchctl load ~/Library/LaunchAgents/com.navermaster.watch.plist
```

## 명령어 (`PY=~/naver-master/.venv/bin/python3`)

| 명령 | 설명 |
|---|---|
| `$PY -m naver_master smoke [--send]` | 환경·외부연결 전체 점검 |
| `$PY -m naver_master watch` | 유튜브 RSS 1회 폴링 (새 영상 → D+1 예약) |
| `$PY -m naver_master due` | 분석(P2) 착수 대상 목록 |
| `$PY -m naver_master kakao-test "메시지"` | 카톡 발송 테스트 |
| `touch ops/state/PAUSE` | **비상정지** (게시·답글 전면 중단) |
| `rm ops/state/PAUSE` | 운영 재개 |

## 개발

```bash
.venv/bin/python3 -m unittest discover -s tests -v
```

개발 브랜치: `claude/great-planck-l3y8eb`
