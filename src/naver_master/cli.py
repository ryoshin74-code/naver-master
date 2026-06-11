"""명령행 진입점.

  python -m naver_master init-db        DB 초기화
  python -m naver_master smoke [--send] Phase 0 스모크 테스트
  python -m naver_master kakao-auth     카카오 1회 인증 (대화형)
  python -m naver_master kakao-test MSG 카톡 테스트 발송
  python -m naver_master watch          유튜브 RSS 1회 폴링 (launchd 매시 호출)
  python -m naver_master due            분석(P2) 착수 대상 영상 목록
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="naver_master", description="네이버 마스터 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="SQLite 스키마 생성")

    p_smoke = sub.add_parser("smoke", help="Phase 0 스모크 테스트")
    p_smoke.add_argument("--send", action="store_true", help="카톡 실발송까지 테스트")

    p_auth = sub.add_parser("kakao-auth", help="카카오 OAuth 1회 인증")
    p_auth.add_argument("--redirect-uri", default=None, help="앱에 등록한 Redirect URI")

    p_ktest = sub.add_parser("kakao-test", help="카톡 테스트 발송")
    p_ktest.add_argument("message", nargs="?", default="[네이버마스터] 테스트 메시지입니다.")

    p_watch = sub.add_parser("watch", help="유튜브 RSS 1회 폴링")
    p_watch.add_argument("--no-alerts", action="store_true", help="카톡 경고 발송 생략")

    sub.add_parser("due", help="게시 예정 시각이 지난 영상 목록")

    args = parser.parse_args(argv)

    if args.command == "init-db":
        from .db import connect, init_db

        conn = connect()
        init_db(conn)
        conn.close()
        print("DB 초기화 완료: ops/state/naver_master.db")
        return 0

    if args.command == "smoke":
        from .doctor import run

        return 0 if run(send_test=args.send) else 1

    if args.command == "kakao-auth":
        from . import kakao

        redirect_uri = args.redirect_uri or kakao.DEFAULT_REDIRECT_URI
        print("1) 카카오 개발자 콘솔의 [카카오 로그인 > Redirect URI] 에 아래 값이 등록돼 있어야 합니다:")
        print(f"   {redirect_uri}")
        print("2) 아래 URL을 브라우저에서 열어 동의를 완료하세요:")
        print(f"   {kakao.build_authorize_url(redirect_uri)}")
        print("3) 이동된 주소창의 전체 URL(또는 code 값)을 붙여넣으세요:")
        pasted = input("> ")
        tokens = kakao.exchange_code(kakao.parse_code(pasted), redirect_uri)
        print(f"인증 완료. 토큰 저장: ops/state/tokens/kakao.json"
              f" (refresh 유효기간 약 2개월, 매일 자동 갱신됨)")
        _ = tokens
        return 0

    if args.command == "kakao-test":
        from . import kakao

        n = kakao.send_text(args.message)
        print(f"발송 완료 ({n}건). 카톡 '나와의 채팅'을 확인하세요.")
        return 0

    if args.command == "watch":
        from .config import is_paused
        from .watcher import poll

        # PAUSE 중에도 감지(수집)는 계속한다 — 경고 발송만 멈춘다 (불변 원칙 5)
        result = poll(send_alerts=not args.no_alerts and not is_paused())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "due":
        from .db import connect, init_db
        from .watcher import due_videos

        conn = connect()
        init_db(conn)
        rows = due_videos(conn)
        conn.close()
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
