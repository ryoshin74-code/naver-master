# 코덱스용 프롬프트 — alfredo 초기 셋업 (Phase 0)

> 총사령관이 코덱스 세션에 복사-붙여넣기하는 1회성 작업지시서.
> 붙여넣기 전에 `【 】` 부분만 채운다. 그 외는 수정 불필요.

---

```
[네이버 마스터 — alfredo 초기 셋업 작업지시서]

너는 macOS 머신 "alfredo"에서 일하는 셋업 엔지니어다. 아래 단계를 순서대로 수행하고,
마지막에 "결과 보고서" 양식대로 보고하라. 터미널과 브라우저를 사용할 수 있다.

== 절대 규칙 (위반 금지) ==
R1. 어떤 사이트에서도 아이디·비밀번호를 입력하지 마라. 로그인 화면을 만나면 멈추고
    나(사용자)에게 "직접 로그인해 주세요"라고 요청한 뒤, 내가 완료했다고 하면 이어서 진행하라.
R2. API 키·토큰 값을 화면에 출력하거나, 파일로 복사하거나, 보고서에 적지 마라.
R3. .env 와 ops/state/ 안의 파일은 어떤 경우에도 git에 추가·커밋하지 마라. git push 도 하지 마라.
R4. 이 지시서에 없는 작업(다른 파일 수정, 다른 앱 조작, 설정 변경)은 하지 마라.
R5. 한 단계가 실패하면 2회까지만 재시도하고, 그래도 실패하면 다음 단계로 넘어가지 말고
    그 시점까지의 결과 보고서를 출력한 뒤 멈춰라.
R6. sudo 가 필요한 상황을 만나면 직접 시도하지 말고 멈추고 보고하라.

== 사전 정보 (사용자가 채움) ==
- 유튜브 채널: 【채널 ID 또는 채널 URL】
- 네이버 블로그 ID: 【blog.naver.com/ 뒤의 아이디】
- 게시할 카페 URL: 【본인 운영 카페 URL】
- 카페 게시판 이름: 【게시판 이름】

== 단계 ==

[1] 사전 점검
  - command -v brew git python3 가 모두 존재하는지 확인. 없으면 멈추고 보고 (R6: brew 설치는 직접 하지 마라).
  - python3 --version 이 3.11 이상인지 확인.

[2] 저장소 클론
  - git clone -b claude/great-planck-l3y8eb https://github.com/ryoshin74-code/naver-master.git ~/naver-master
  - 이미 ~/naver-master 가 있으면 클론 대신: cd ~/naver-master && git fetch origin && git checkout claude/great-planck-l3y8eb && git pull
  - 인증 오류가 나면 멈추고 사용자에게 GitHub 인증을 요청하라 (R1).

[3] 도구 설치
  - brew install yt-dlp ffmpeg  (이미 있으면 brew upgrade 는 하지 말 것)
  - yt-dlp --version, ffmpeg -version 출력의 첫 줄을 기록.

[4] 파이썬 환경
  - cd ~/naver-master
  - python3 -m venv .venv
  - .venv/bin/pip install -e .

[5] 설정 파일 작성
  - cp config/settings.example.yaml config/settings.yaml
  - "사전 정보"의 값으로 settings.yaml 의 다음 항목을 채워라:
    youtube.channel_id / naver.blog_id / naver.cafe.club_url / naver.cafe.menu_name
  - 채널 ID 대신 URL을 받았다면: 브라우저로 그 채널 페이지를 열고 페이지 소스에서
    "channelId":"UC..." 값을 찾아 사용하라 (UC로 시작하는 24자).
  - tone_guide 와 disclosure_text 는 건드리지 마라 (추후 사용자가 채움).

[6] 비밀키 입력 (사용자 직접)
  - cp .env.example .env && open -t .env
  - 여기서 멈추고 사용자에게 요청하라: "텍스트 편집기에 열린 .env 에
    OPENAI_API_KEY, KAKAO_REST_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 값을
    직접 붙여넣고 저장한 뒤 '완료'라고 말해 주세요.
    (KAKAO_CLIENT_SECRET 은 카카오 앱에서 Client Secret 을 켠 경우에만)"
  - 사용자가 완료를 알리면, 값을 읽지 말고 다음 명령으로 '빈 키 이름만' 확인하라 (R2):
    awk -F= '/^[A-Z]/ && $2=="" {print $1" 이(가) 비어 있음"}' .env
  - OPENAI_API_KEY 나 KAKAO_REST_API_KEY 가 비어 있으면 다시 사용자에게 요청하라.

[7] DB 초기화
  - .venv/bin/python3 -m naver_master init-db

[8] 카카오 1회 인증
  a. 사용자에게 확인 요청: "developers.kakao.com 의 해당 앱에서
     ① 카카오 로그인 활성화  ② Redirect URI 에 http://localhost:8889 등록
     ③ 동의항목에서 '카카오톡 메시지 전송(talk_message)' 설정
     이 세 가지가 되어 있나요? 안 되어 있으면 직접 설정 후 알려주세요." (로그인이 필요한 사이트이므로 R1)
  b. 터미널: .venv/bin/python3 -m naver_master kakao-auth
  c. 출력된 인증 URL을 기본 브라우저로 열어라. 카카오 계정이 이미 로그인돼 있으면
     동의 화면에서 [동의하고 계속하기]를 눌러라. 로그인 화면이 나오면 멈추고 사용자에게 (R1).
  d. localhost:8889 로 이동하면 "연결할 수 없음" 페이지가 떠도 정상이다.
     주소창의 전체 URL을 복사해 터미널 프롬프트("> ")에 붙여넣어라.
  e. "인증 완료" 메시지를 확인하라.

[9] 스모크 테스트
  - .venv/bin/python3 -m naver_master smoke --send
  - 출력 전체(✅/❌ 표)를 보고서에 그대로 포함하라.
  - 사용자에게 "카톡 '나와의 채팅'에 테스트 메시지가 도착했는지 확인해 주세요"라고 요청하라.

[10] launchd 등록 (스모크의 '유튜브 RSS' 항목이 ✅일 때만)
  - REPO=$HOME/naver-master
  - mkdir -p "$REPO/ops/state/logs"
  - sed "s|__REPO__|$REPO|g" "$REPO/ops/launchd/com.navermaster.watch.plist" > ~/Library/LaunchAgents/com.navermaster.watch.plist
  - launchctl load ~/Library/LaunchAgents/com.navermaster.watch.plist
  - launchctl list | grep navermaster 로 등록 확인.

[11] 첫 폴링
  - .venv/bin/python3 -m naver_master watch --no-alerts
  - 출력 JSON을 보고서에 포함하라 (registered 에 최근 영상들이 잡히고, 설명란에
    구매 링크가 없는 영상은 held 로 분류되는 것이 정상이다).

== 결과 보고서 양식 ==
1. 단계별 결과 표: 단계 번호 | 성공/실패/건너뜀 | 비고 한 줄
2. 설치 버전: yt-dlp, ffmpeg, python
3. [9] 스모크 테스트 출력 전문
4. [11] watch 출력 JSON
5. 막힌 항목과 사용자가 해야 할 조치 목록
```

---

## 사용 후

- 보고서(특히 스모크 테스트 ✅/❌ 표와 watch JSON)를 총괄 지휘관(Claude 세션)에게 전달하면
  P2(영상 분석) 제작이 이어진다.
- ❌ 항목 중 "네이버 API 키"는 카페 게시 경로(공식 API vs 컴퓨터유즈) 분기 판단에 필요하다.
