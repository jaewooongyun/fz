#!/usr/bin/env python3
# lint:no-root-anchor — 검사 대상은 cwd(또는 -C · --tree 인자)의 저장소다. 자기 위치로 옮겨 가면 훅 · 임시 저장소 대신 플러그인 트리를 잰다
# diff-parse: hunk-state — git 축(parse_added)은 `diff --git` 머리 구간과 `@@` hunk 를 구분해 hunk 안의 `+` 줄만 추가 줄로 센다
"""leak_rules.py — 공개 저장소에 두면 안 되는 식별자 규칙의 정본.

왜: 같은 규칙을 진입점마다 따로 적으면 한 벌만 고쳐지고 나머지는 옛 규칙으로 돈다. 매칭 코드는 여기 한 벌만 두고,
무엇을 통과시키고 어느 규칙 계열을 돌릴지는 부르는 쪽이 정책 값(POLICY_DOC · POLICY_CAPTURE)으로 고른다.

규칙 계열 — 모양만 본다(프로젝트 이름은 없다). 계열마다 안정 id(왼쪽)와 표시 라벨이 있고, 적중은 둘 다 싣는다
  home         개인 홈 경로 — 홈 아래 계정 폴더(Users · home). 정책이 허용한 자리표시 이름만 통과한다. 점으로 시작하는
               이름은 계정이 아니라 설정 폴더라 두 정책 모두 계정 자리로 잡지 않는다(`.` · `..` 마디는 잡는다).
               계정 자리는 `/` · 공백 · 따옴표 · 꺾쇠 · 백틱 · `: , ; ) ] |` · ASCII 밖 글자 · 줄 끝에서 끝난다 — 끝에 `/` 가 없는
               꼴(환경 변수 값 · JSON 값 · 문장 속 경로)도 잡는다. 이름 끝의 마침표는 문장부호로 보고 이름에서 뺀다.
               문서 정책은 계정 꼴 글자로 시작하는 자리를 그 앞쪽 런으로 판정한다 — 뒤에 붙은 글자(JSON 의 이스케이프 · 닫는 중괄호 ·
               굵게 표시)가 실제 계정을 '계정 꼴 아님' 으로 바꾸지 않는다
  home-slug    하이픈으로 편 홈 경로 — 도구가 작업 폴더의 절대 경로에서 `/` 를 `-` 로 바꿔 만든 폴더 이름(`-Users-<계정>-…`).
               통과는 home 과 같다(문서 정책은 자리표시 이름 · 캡처 정책은 전부 거부). 캡처 정책은 앞에 다른 글자가 붙은 꼴(드라이브 글자 ·
               볼륨 이름 뒤)도 본다 — 계정 뒤에 하이픈이 있을 때. 문서 정책은 그 꼴을 보지 않는다(낱말 사이 하이픈과 가를 수 없다)
  dev-home     개인 작업 폴더 경로 — 홈 아래 dev 폴더의 하위 폴더 이름. 정책이 허용한 자리표시 이름만 통과한다.
               홈을 적는 꼴 셋(물결표 · `$HOME` 과 `${HOME}` · 절대 경로) 뒤를 보고 끝 경계는 home 과 같다. 절대 경로 꼴은 계정이
               통과할 때만 본다(통과하지 못하는 계정은 home 이 잡는다 · 꺾쇠 자리표시 `<이름>` 은 통과하는 계정이다) — 이 꼴에서만 트리의 합성 이름(DOC_DEV_ABS_NAMES)이 더 통과한다
  mail         메일 주소 — 정책이 허용한 도메인과 그 하위 도메인만 통과한다. 예약 TLD 전체를 허용하지 않는다
  placeholder  자리표시자 번호 — 중립 접두(PLACEHOLDER_PREFIXES · 대소문자 무시 · 하이픈 또는 밑줄 선택 · 숫자 2~6)는
               예약 번호일 때만 통과한다. 예약 번호 = 0 으로 시작하는 3~5자리 + 트리에 이미 있는 합성 번호(RESERVED_SYNTHETIC)
  key          티켓 키 꼴 — 대문자 2~6 + 하이픈 + 숫자 3~6(경계는 영숫자 — `-` · `_` 로 이은 꼴도 잡는다). 통과는 KEY_OK 이름공간 · 번호가 예약 번호인 KEY_RESERVED_ONLY 이름공간 ·
               합성 키(SYNTHETIC_KEYS — 정확한 토큰)뿐이다
  pr           PR 번호 꼴 — `PR` 뒤 번호(대소문자 무시 · 공백 · 하이픈 · 쌍점 · `#` 선택 · 왼쪽 경계는 영숫자 — `_` 로 이은 꼴도 잡는다) · `#` 뒤 번호 · `<소유자>/<저장소>#` 뒤
               번호 · pull 경로(`/pull/` · `/pulls/`) 뒤 번호. 모두 3자리부터 본다(순번 · lint 번호 인용은 1~2자리다). 예약 번호는 통과한다
  run-id       워크플로 실행 ID 꼴(접두까지 대소문자 무시) — 전체 꼴(`wf_` + 16진 8자 + `-` + 16진 3자)과 접미사 없는 꼴(`wf_` 뒤
               16진 8자에서 끝나는 꼴 — 접미사가 16진 3자가 아닌 표기는 `wf_` 와 앞 8자까지 잡고, `wf_` 뒤 16진이 9자 이상 이어지는
               토큰은 잡지 않는다). 합성 목록(SYNTHETIC_RUN_IDS)의 값만 통과한다 — 대역이 아니라 값 목록이고 값은 전체 꼴뿐이라 접미사
               없는 꼴은 언제나 적중이다. 꼴만 닮은 문서 표기(정규식 · 자리표시자 · 스크립트 이름)는 맞지 않는다
  private      비공개 규칙 — 공개하지 않을 이름(조직 · 제품 이름 등)은 공개 트리에 두지 않고 파일로 받는다(한 줄 한 정규식 · `#` 주석 · 빈 파일 = 내장만).
               해석 순서: `--rules FILE` > env FZ_NEUTRALIZE_RULES > 없음(내장 규칙만). 훅(--hook-policy — 커밋 훅 · push 훅)은
               env 다음에 git 설정 fz.neutralizeRules 를 보고, 그래도 없으면 유지관리자 표지(git 설정 fz.maintainer)가 참일 때
               판정 불가다
정책은 돌릴 계열도 고른다 — POLICY_DOC 은 등록된 계열 전부(새 계열은 `@family` 로 등록만 하면 들어간다), POLICY_CAPTURE 는
home · home-slug · mail 만이다. 캡처 fixture(tests/fixtures 아래 모든 파일 — 확장자를 가리지 않는다 · git 작업 트리 안이면 git 이 내보낼 파일만: 무시된 미추적 부산물은 뺀다)의 세션 ID(UUID 꼴)와 실행 ID 는
정책이 아니라 캡처 ID 감사(tests/lib/sample_replay.py 의
capture_id_audit)가 이 모듈의 capture_id_tokens 로 본다 — ANSI 제어열을 걷고 합성 목록(SYNTHETIC_SESSION_IDS · SYNTHETIC_RUN_IDS)
밖 값만 낸다(걷기 · 대조는 여기 한 벌이다). 신원(author · committer · tagger 의 메일)은 내용과 다른 축이다 — noreply 둘(IDENTITY_EXACT ·
IDENTITY_SUFFIX)만 통과한다. 훅 정책의 커밋마다 축(push 훅)은 이 신원 메일 규칙을 유지관리자 표지가 참일 때만 켠다(비공개 규칙은
신원 칸에도 표지와 무관하게 본다).

경로 이름 축: 깨끗한 내용의 파일을 식별자가 든 이름으로 더할 수 있으므로 --tree · --range · --staged · --commits 는 파일 · 폴더
  이름에도 같은 계열과 비공개 규칙을 건다(문서 정책 — 자리표시 이름은 통과한다). --tree 와 미추적 파일은 경로 전부, git 축은 새로
  생긴 이름만 본다(더한 파일 · 개명과 복사의 새 이름 — `--diff-filter=ACR`). 지운 파일과 내용 · 모드만 바뀐 파일의 이름은 보지
  않는다 — 나쁜 이름을 지우는 정리가 막히지 않는다. ⛔ 이름은 추가 줄에서 얻지 않는다(빈 새 파일 · 내용이 그대로인 개명은 hunk 가
  없다). 적중은 그 토큰이 처음 나타나는 가장 얕은 마디에 한 번 붙는다(폴더는 끝에 `/` — 폴더 이름 하나가 아래 파일 수만큼
  불어나지 않는다). 줄 번호가 없고 라벨이 `경로 이름 · ` 로 시작한다: `  ❌ 마디: 경로 이름 · <라벨> — 토큰`.
  새 경로의 윗폴더 이름도 본다 — 이미 있던 폴더여도 그 아래에 새 파일을 더하면 그 폴더 마디에서 적중한다(이름을 고치게 한다).
  계열과 비공개 규칙은 내용과 같은 정규식이라(티켓 키 꼴의 경계도 같다 — `-` · `_` 로 이은 이름도 잡는다) 한계도 같다 — 마디는 `/` 로 시작하는 누적 경로로 맞추므로 `^` · `$` 로 고정한 비공개 규칙은 이름에 맞지 않고, `/` 를
  넘어 길게 잡는 규칙은 아래 파일마다 다른 토큰으로 되풀이될 수 있다. 홈 경로 계열은 끝 마디가 계정
  이름인 경로(파일 · 링크 · 하위 저장소)도 잡는다. 모양만 닮은 이름도 적중한다(`<이름>@2x.<확장자>` 는 메일 주소 꼴 · 가짜 홈
  fixture 의 `home/<이름>/` 은 홈 경로 꼴) — 이름을 바꾸거나 자리표시 이름을 쓴다. UTF-8 이 아닌 이름은 바이트를 풀어 그대로 본다.

읽기 계약: 검사 대상은 UTF-8 로 읽는다. 읽기 실패 · 디코드 실패 · NUL 바이트(UTF-16 · 바이너리) · 규칙 파일 읽기 실패 ·
  규칙 정규식 오류는 건너뛰지 않고 판정 불가(Unrun · exit 2)다 — 건너뛰면 그 안의 식별자가 검사 없이 지나간다.
  git 축은 git 실행 · 종료 실패 · 풀리지 않는 ref 와 git 이 바이너리로 본 파일(numstat 의 `-` — 모든 git 축)도 판정 불가다 —
  추가 줄을 텍스트로 잴 수 없으면 0(쟀고 깨끗하다)을 내지 않는다. 커밋 · 태그 객체의 신원 · 메시지 · 머리 · 주석도 같은 계약으로
  읽고 어느 칸도 건너뛰지 않는다(구조 값인 객체 이름 · 종류 머리만 텍스트로 보지 않는다).

모드
  --text-file F   파일 하나의 본문(문서 정책)
  --tree [DIR]    DIR(기본: -C 또는 cwd)의 공개 후보 파일 전문(문서 정책). DIR 이 git 작업 트리의 꼭대기면 추적 파일(작업 트리에서
                  지운 것 제외)과 무시되지 않은 미추적 파일, 아니면(git 이 아닌 사본 · 바깥 저장소 안의 하위 폴더) 폴더 전체(.git
                  제외 — 무시 파일도 읽는다). 빈 트리 대비 전문 검사(첫 출하)에 쓴다
  --range REF     커밋 범위 축 — REF 대비 작업 트리의 추가 줄 · 새 경로 이름과 미추적 파일 전문(문서 정책). `A..B` 면 두 커밋 사이(미추적
                  제외 · 빈 쪽은 HEAD). diff 는 --no-renames 다 — 개명한 파일은 새 경로의 전문이 추가 줄이다(rename 탐지가
                  켜지면 개명한 파일 속 남은 식별자가 '안 바뀐 줄' 로 빠진다)
  --staged        스테이징 축 — 인덱스가 HEAD 에 더한 줄과 새 경로 이름만(문서 정책 · 작업 트리 · 미추적 파일은 보지 않는다). 개명은 옛
                  경로와 짝지어(-M) 실제로 바뀐 줄만 본다 — 개명만으로 기존 정당 참조가 막히지 않고, 남은 내용은 커밋 범위 축이 잡는다
  --commits SPEC  커밋마다 축 — 범위의 커밋을 하나씩 본다: 신원(author · committer — 신원 정책) · 메시지 · 그 밖의 머리(서명
                  gpgsig 등) · 추가 줄 · 새 경로 이름(문서 정책). 병합 태그 머리(mergetag)에 박힌 태그 객체는 --tag 와 같은 판정이다. SPEC 문법은
                  --range 와 같다 — `A..B` = B 에서 닿고 A 에서 닿지 않는 커밋(빈 쪽은 HEAD) · REF = REF 에서 닿는 커밋 전부(루트부터
                  — 기준 태그가 없는 첫 출하). 추가 줄은 첫 부모 대비(병합 커밋도 · --no-renames)이고 루트 커밋은 빈 트리 대비다 —
                  범위의 두 끝만 비교하면 중간 커밋에서 더했다가 지운 줄을 놓친다.
                  함께 받는 것(--commits 밖에서 주면 판정 불가):
                    --exclude REF  더 뺄 끝(여러 번 · rev-list 의 ^REF) — push 훅이 원격이 가졌다고 확인한 tip 을 넘긴다
                    --tag NAME     태그 축(여러 번 · 이름 또는 refs/tags/…) — 주석 태그의 tagger(신원 정책)와 주석 본문 · 그 밖의
                                   머리(문서 정책). 가벼운 태그는 그 칸이 없다 — 빈 값을 위반으로도 통과 증거로도 읽지 않고 세기만
                                   한다. 태그 이름은 종류와 무관하게 경로 이름 규칙으로 본다(`태그 이름 <마디>`). 가리키는 커밋이
                                   검사 범위(SPEC 의 끝과 --exclude 에서 닿는 커밋) 밖이면 판정 불가다 — 그 태그를 올리면 함께
                                   나가는 커밋을 이 실행이 보지 않았다. 풀리지 않거나 커밋을 가리키지 않는 태그도 판정 불가
                    --ref-name NAME  공개될 ref 이름(여러 번 · push 의 목적지 이름 — `refs/heads/` · `refs/tags/` 머리는 걷는다)을
                                   경로 이름 규칙으로 본다(`ref 이름 <마디>`)
                    --with-tree    작업 트리 전문(--tree 와 같은 판정)을 함께 본다 — 첫 출하는 커밋에 들지 않은 공개 후보도 본다
                  적중 자리(해시는 앞 12자): `신원 <해시> author|committer` · `메시지 <해시>:줄` · `머리 <해시> <머리 이름>:줄` ·
                  `추가 줄 <해시> 경로:줄` · `경로 <해시> 마디`(경로 이름) · `tagger <태그>` · `주석 <태그>:줄` · `머리 <태그> <머리 이름>:줄` · `전문 경로:줄`.
                  병합 태그는 <태그> 자리가 `mergetag <해시>` 다. 끝 줄: `LEAK_* commits:SPEC commits=N annotated=N lightweight=N
                  [ with-tree] files=N …` — 판정 불가로 일찍 끝나도 같은 꼴이다(못 잰 수는 0)
  --identity-mail MAIL
                  신원 한 벌 — 메일(신원 메일 규칙: noreply 둘만 통과 · --hook-policy 여도 언제나 켠다)과 함께 받는 이름(--identity-name
                  NAME — 빈 값이면 메일만 · --identity-mail 밖에서 주면 판정 불가)에 비공개 규칙을 건다(메일 · 이름 칸 — identity_hits).
                  커밋 객체 밖에서 신원을 미리 재는 호출자(격리 clone 스크립트 — 원본 로컬 설정 · 신원 환경 변수)가 메일 정규식 사본
                  없이 부른다 — 비공개 규칙을 그 저장소의 훅과 같은 순서로 풀려면 -C 와 --hook-policy 를 함께 준다. 적중 자리는 `신원` ·
                  끝 줄 `LEAK_* identity-mail files=1 …`
  --release-body TAG
                  발행된 릴리스 — `gh release view TAG --json name,body` 가 돌려주는 제목과 본문(--text-file 과 같은 판정 — 문서 정책 ·
                  내장 규칙 + 비공개 규칙). 출하 절차의 발행 뒤 검사다: 발행 전에는 노트 파일을 --text-file 로 보고, 발행한 뒤 실제로
                  올라간 글자를 이 모드로 다시 본다 — 발행 명령이 노트 파일이 아닌 본문(커밋 메시지 · 태그 주석에서 지은 본문 · 손으로
                  고친 본문)을 올리면 그 글자는 노트 검사를 거치지 않는다. gh 는 PATH 에서 찾아 -C(없으면 cwd)에서 부른다. 판정 불가(2):
                  태그가 비었거나 `-` 로 시작함 · gh 부재 · 실행 실패 · 0 아닌 종료(인증 만료 · 오프라인 · 그 태그의 릴리스 없음) · UTF-8
                  아닌 출력 · JSON 아님 · 제목 · 본문 칸 없음 · 빈 본문 — 읽지 못한 본문을 '위반 없음' 으로 읽지 않는다. 적중 자리는
                  `<TAG> 제목:줄` · `<TAG> 본문:줄` · 끝 줄 `LEAK_* release-body:TAG files=1 …`(읽지 못하면 files=0)
  --self-test     셀마다 `PASS <이름>` 한 줄(환경 변수 없이) · 실패면 `FAIL <이름>: …` · 끝에 `self-test N/M passed`
공통: --rules FILE · -C DIR(상대 경로의 기준이자 --tree 의 기본 대상 — 자기 위치로 옮겨 가지 않는다. env FZ_NEUTRALIZE_RULES 의
      상대 경로도 -C 기준이다). git 은 replace ref 를 끄고 부른다 — 검사는 실제로 나갈 객체를 읽는다. git 축의 대상은 -C(없으면
      cwd)가 든 저장소 전체다 — 하위 폴더로 좁히지 않는다(작업 트리 · 인덱스 · 커밋 가운데 무엇을 보는지는 모드마다 위에 적었다)
      --hook-policy  훅(커밋 훅 · push 훅)의 정책 — 비공개 규칙 해석과 신원 축 스위치(문서 정책 · 계열 선택은 그대로). env 다음에
                     git 설정 fz.neutralizeRules(`~` 를 푼다 · 상대 경로는 -C 기준)를 본다. 끝내 없으면 유지관리자 표지(git 설정
                     fz.maintainer)가 참이거나 참 거짓으로 읽히지 않을 때 판정 불가(2), 아니면 내장 규칙만 보고 `NOTE:` 안내 한
                     줄을 낸다. 경로를 줬는데 읽지 못하면 표지와 무관하게 판정 불가다. 규칙 파일을 풀었는데
                     규칙이 0개(빈 파일 · 주석뿐)이고 표지가 참이어도 판정 불가다. --commits 와 함께면 커밋 · 태그의 신원 메일
                     규칙(noreply 만 통과)을 표지가 참일 때만 켠다 — 참이 아니면 끄고 `NOTE:` 한 줄을 낸다(공개 기여자의 개인 메일은
                     막지 않는다 · 메시지 · 머리 · 추가 줄 · 태그 주석 · 비공개 규칙은 그대로 본다). 표지를 참 거짓으로 읽지 못하면
                     판정 불가다. ⛔ 이 플래그가 없으면 git 설정을 읽지 않고 신원 축은 언제나 엄격하다 — 출하 게이트는 규칙 파일을
                     명시로 받고 표지로 추정하지 않는다
exit: 0 = 쟀고 적중 0(`LEAK_CLEAN …`) · 1 = 적중(`  ❌ 경로:줄: 라벨 — 토큰` · `LEAK_HIT …` — --commits 는 경로 앞에 축과
      해시 또는 태그가 붙고, --release-body 는 경로 자리에 `<태그> 제목` · `<태그> 본문` 이 오고, 줄이 없는 적중(신원 · tagger · 경로 이름)은
      `  ❌ 자리: 라벨 — 토큰`) · 2 = 판정 불가(`UNRUN: 사유` 한 줄씩 · `LEAK_UNRUN …` — 적중이 함께 있어도 2 다)
출력: 경로 · 토큰 · 사유에 든 UTF-8 밖 바이트는 백슬래시 이스케이프로 적는다 — 출력 실패가 exit 계약(1 · 2)을 바꾸지 않게
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

OK, HIT, UNRUN = 0, 1, 2
SELF = os.path.abspath(__file__)   # self-test 가 CLI 를 자식 프로세스로 부를 때만 쓴다 — 검사 대상을 정하는 데 쓰지 않는다

# ── 매칭 코드 — 한 벌만 둔다 ──────────────────────────────────────────────────────────
# 홈 경로 — 계정 자리를 넓게 잡고 무엇을 통과시킬지는 정책이 정한다. 자리는 `/` · 공백 · 따옴표 · 꺾쇠 · 백틱 · `: , ; ) ] |` ·
#   ASCII 밖 글자(한글 조사) · 줄 끝에서 끝난다 — 끝에 `/` 를 요구하면 환경 변수 값 · JSON 값 · 문장 속 경로를 놓친다.
#   이름 끝의 마침표는 문장부호로 보고 뺀다(자리표시 이름 뒤 마침표가 허용 목록을 빗나가지 않게) — 점만으로 된 마디는 그대로 잡는다.
#   끝 글자는 소비하지 않는다 — 소비하면 바로 이어지는 두 번째 홈 경로를 놓친다.
#   점으로 시작하는 이름(`.codex` 같은 설정 폴더)은 계정이 아니다 — 임시 HOME 아래 설정 폴더를 계정으로 읽지 않게 두 정책 모두
#   자리로 잡지 않는다. 진짜 계정 아래의 점폴더는 계정 자리가 먼저 잡혀 그대로 적중한다. `.` · `..` 마디는 자리로 남긴다 —
#   건너뛰면 그 마디 뒤에 적은 계정 경로가 적중 없이 지나간다
HOME_RE = re.compile(r"/(?:Users|home)/(?!\.[^./])"
                     r"(\.+(?=[/\s\"'<>:,;)\]`|\x80-\U0010ffff]|$)"
                     r"|[^/\s\"'<>:,;)\]`|\x80-\U0010ffff]*[^./\s\"'<>:,;)\]`|\x80-\U0010ffff])")
# 홈 아래 dev 폴더의 하위 폴더 — 그 이름이 작성자 머신의 폴더 배치를 드러낸다. 홈을 적는 꼴 셋(물결표 · 환경 변수 · 절대 경로)
#   뒤를 본다. 이름 자리를 끝내는 법은 홈 경로와 같다. 절대 경로 꼴의 계정은 acct 묶음에 담는다 — 계열 함수가 그 계정이 통과할
#   때만 이 계열로 판정한다(통과하지 못하는 계정은 홈 경로 계열이 같은 자리를 이미 잡는다). 꺾쇠 자리표시(`<user>`)는 계정 자리의 글자
#   집합 밖이라 따로 받는다 — 받지 않으면 그 뒤의 dev 폴더 이름이 어느 계열에도 걸리지 않는다
DEV_RE = re.compile(r"(?:~|\$\{?HOME\}?|/(?:Users|home)/(?P<acct><[^<>/\s]+>|[^/\s\"'<>:,;)\]`|\x80-\U0010ffff]+))"
                    r"/dev/(?P<name>[^/\s\"'<>:,;)\]`|\x80-\U0010ffff]*[^./\s\"'<>:,;)\]`|\x80-\U0010ffff])")
# 하이픈으로 편 홈 경로 — 도구가 작업 폴더의 절대 경로에서 `/` 를 `-` 로 바꿔 만든 폴더 이름(`-Users-<계정>-…`). 계정 자리는 다음
#   하이픈 앞까지다(계정 이름 속 하이픈과 구분자를 가를 수 없다 — 앞 조각으로 판정한다. 앞 조각이 자리표시 이름과 같은 계정은 문서
#   정책에서 통과한다 — 받아들이는 한계). 왼쪽 경계는 영숫자 · 하이픈이 아닌 것이다 — 옵션 이름(`--home-…`)과 낱말 사이 하이픈은
#   이 꼴이 아니다. 이름 끝의 마침표는 문장부호로 보고 뺀다
HOME_SLUG_RE = re.compile(r"(?<![A-Za-z0-9-])-(?:Users|home)-([A-Za-z0-9._]*[A-Za-z0-9_])")
# 앞에 다른 글자가 붙은 편 꼴(드라이브 글자 · 볼륨 이름 뒤에 이어진 것) — 왼쪽 경계가 없는 대신 계정 뒤의 하이픈을 요구한다(옵션 이름은
#   뒤에 하이픈이 없다). 계정 꼴을 가리지 않는 정책(캡처 감사)만 쓴다 — 문서에서는 낱말 사이 하이픈과 가를 수 없다
HOME_SLUG_ATTACHED_RE = re.compile(r"-(?:Users|home)-[A-Za-z0-9._]+-")
# 계정 이름 꼴 — 문서 정책은 이 꼴이 아닌 자리(`{user}` · `$USER` · 정규식 조각)를 계정으로 보지 않는다
ACCOUNT_SHAPE = re.compile(r"[A-Za-z0-9._-]+")
# 런 머리에서만 맞춰 본다(왼쪽 부정 탐색) — 없으면 구분자 없는 긴 한 줄(base64 덩어리)에서 자리마다 런 끝까지 다시 훑어 줄 길이의
#   제곱만큼 걸린다(훅이 멈춘다). 맞는 것은 같다 — 로컬 파트는 어차피 런 끝에서 끝나야 한다
MAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
# 대문자 키 꼴은 대문자 · 하이픈을 엄격히 본다 — 대소문자 무시 · 하이픈 선택을 여기 걸면 sha256 · rfc3339 같은 토큰이 걸린다.
#   경계는 영숫자로만 둔다 — 브랜치 · 파일 이름처럼 `-` · `_` 로 낱말을 이은 꼴도 키 꼴이다(내용 줄과 경로 이름 축이 이 한 식을 쓴다)
KEY_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,6})-(\d{3,6})(?![A-Za-z0-9])")
# 통과하는 이름공간 — 번호와 무관하게 통과한다. 이름공간마다 통과 이유:
#   ISO · CVE · RFC · UTF · SHA · PEP · GHSA  표준 번호 · 공개 취약점 번호
#   ISSUE                                    fz 지적 id — 스키마(schemas/*.json)가 정한 이슈 id 접두. ⛔ 아래 규칙의 예외다 — 트리가
#                                            예약 대역 밖 번호(날짜 꼴)를 쓴다(KEY_RESERVED_ONLY 로 옮기면 그 쓰임이 적중한다)
#   이름공간을 더할 때는 여기 이유 한 줄을 단다. 원소는 할당 한 줄에 둔다 — 줄 단위 검색이 집합 전체를 본다.
#   ⛔ 자리표시자 접두(PLACEHOLDER_PREFIXES)는 두지 않는다 — 두면 번호와 무관하게 통과한다(self-test 가 교집합 0 을 단언한다)
#   ⛔ ISSUE 밖의 플러그인 id 접두는 여기 두지 않는다 — 이름공간째 통과시키면 같은 접두를 쓰는 실제 키가 내장 규칙을 지나간다.
#      번호가 예약 번호일 때만 통과시킨다(KEY_RESERVED_ONLY)
KEY_OK = frozenset({"ISO", "CVE", "RFC", "UTF", "SHA", "PEP", "GHSA", "ISSUE"})
# 번호가 예약 번호(is_reserved)일 때만 통과하는 이름공간 — 플러그인 자신의 지적 id 접두다. 트리의 쓰임은 모두 0 으로 시작하는
#   3자리라 그대로 통과하고, 같은 접두의 대역 밖 번호는 적중이다. 이름공간마다 통과 이유:
#   ARCH · CODE · REV · VER  스키마(schemas/*.json)가 정한 리뷰 · 검증 id 접두
#   GPT                      GPT 반론 출력의 지적 id(scripts/counter_adapter.py)
#   PLAN                     계획 감사 지적 id 의 하위 접두 — 이슈 id 접두 뒤에 이어 적는다(`<이슈 접두>-PLAN-<번호>`). 경계가 영숫자라
#                            이은 꼴의 뒤 조각도 키 꼴로 읽힌다
KEY_RESERVED_ONLY = frozenset({"ARCH", "CODE", "REV", "VER", "GPT", "PLAN"})
# 트리에 이미 있는 합성 키 — 정확한 토큰만 통과한다(같은 접두의 다른 번호는 적중이다). 토큰마다 출처:
#   ABT 둘     A/B 프로토콜의 필수 패턴(`scripts/check_ab_protocol.py`)과 그 self-test(`scripts/ab_ledger_selftest.py`)
#   FZ 하나    티켓 접두 계약의 2글자 하한 대조(`tests/fixtures/ticket-prefix/extract/run.sh`)
#   AIME 하나  공개 수학 벤치마크 이름 — 연도가 붙는다(가이드의 논문 인용)
#   ⛔ 토큰을 쪼개 적는다 — 이 파일도 같은 규칙 · 커밋 훅 · 감사 스캔으로 훑인다
SYNTHETIC_KEYS = frozenset(["ABT" + "-" + n for n in ("1001", "2001")] + ["FZ" + "-" + "142", "AIME" + "-" + "2025"])
# 중립 자리표시자 접두 — 대소문자 무시 · 하이픈(또는 밑줄) 선택. 번호가 예약 번호일 때만 통과한다
PLACEHOLDER_PREFIXES = ("TICKET", "TKT", "PRJ")
PLACEHOLDER_KEY_RE = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(PLACEHOLDER_PREFIXES) + r")[-_]?(\d{2,6})(?![0-9])", re.I)
# 키 꼴 계열이 판정하지 않고 넘기는 접두 — 자리표시자 접두는 자리표시자 계열이, `PR` 은 PR 번호 계열이 본다.
#   넘기지 않으면 예약 번호를 하이픈 꼴로 적은 PR 번호가 키 꼴로 걸린다
KEY_YIELD = frozenset(PLACEHOLDER_PREFIXES + ("PR",))
# 예약 대역 — 0 으로 시작하는 3~5자리는 실제 티켓 · PR 번호와 겹칠 수 없다. 2자리면 키 꼴(숫자 3자리부터)이 보지 않아
#   대역이 공허하고, 6자리면 fz-guard 의 작업 폴더 이름 꼴(숫자 2~5자리)이 놓친다
RESERVED_BAND = re.compile(r"0\d{2,4}")
# 트리에 이미 있는 합성 번호 — `mods/fz-guard/hooks/guard.py` · `modules/gates.md` · `skills/fz-manage/scripts/parse_memory.py` ·
#   `docs/completion-gates.md` · ticket-prefix 픽스처가 쓴다. 그 파일들을 고치지 않고 통과시킨다
RESERVED_SYNTHETIC = frozenset({"12", "123", "1234", "9999"})
# PR 번호 · `#` 번호 — 3자리부터 본다(1~2자리는 순번 · lint 번호 인용이다). `&#` 뒤는 HTML 문자 참조라 보지 않는다.
#   `PR` 은 대소문자를 가리지 않고 뒤에 공백 · 하이픈 · 쌍점(뒤 공백 하나까지)을 받는다. 왼쪽 경계는 키 꼴과 같은 영숫자다 — `_` 를
#   경계 밖에 두면 `_` 로 이은 PR 번호를 어느 계열도 보지 않는다(키 꼴 계열은 `PR` 접두를 이 계열에 넘긴다). HASH_RE 는 `#` 앞이
#   영숫자면 보지 않는다(앵커 · 낱말에 붙은 `#`) — 그 가운데 `<소유자>/<저장소>#<번호>` 꼴은 REPO_HASH_RE 가(런 머리에서만 맞춰 본다 —
#   MAIL_RE 와 같은 이유), pull 경로 뒤 번호는 PULL_RE 가 본다. ⛔ 쌍점 · 공백 뒤의 숫자뿐인 색 코드는 `#` 번호 꼴로 적중한다 —
#   막는 쪽 오탐이다(색은 이름이나 16진 글자가 든 값으로 적는다)
PR_RE = re.compile(r"(?<![A-Za-z0-9])PR(?:[ -]|: ?)?#?(\d{3,6})(?![0-9])", re.I)
HASH_RE = re.compile(r"(?<![A-Za-z0-9_&#])#(\d{3,6})(?![0-9A-Za-z_])")
REPO_HASH_RE = re.compile(r"(?<![A-Za-z0-9_.-])[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#(\d{3,6})(?![0-9A-Za-z_])")
PULL_RE = re.compile(r"/pulls?/(\d{3,6})(?![0-9])")
# 워크플로 실행 ID 꼴 — 작성자 머신의 실행을 가리키는 값이다. 두 꼴을 한 식으로 잡는다
#   전체 꼴         `wf_` + 16진 8자 + `-` + 16진 3자. 전체 토큰으로 잡는다 — 합성 목록과 대조하는 단위라 앞 8자로 자르지 않는다
#   접미사 없는 꼴  `wf_` 뒤 16진 8자에서 끝나는 꼴(실제 값을 줄여 적은 것). 접미사가 16진 3자가 아닌 표기(모자라거나 16진이 더
#                   이어진다)도 `wf_` 와 앞 8자까지를 이 꼴로 잡는다
#   끝의 부정 전방 탐색이 `wf_` 뒤 16진이 9자 이상 이어지는 토큰(해시가 붙은 이름 따위)을 뺀다. 접두까지 대소문자를 가리지 않는다(re.I —
#   대문자로 적은 실제 값이 지나가지 않게). 꼴만 닮은 문서 표기 — 정규식(`wf_[0-9a-f]{8}-…`) · 자리표시자(`wf_<runId>` · `wf_XXXXXXXX-XXX`) ·
#   스크립트 이름(`fz_wf_metrics.py`) — 는 16진 자리가 아니라 맞지 않는다. ⛔ 접미사 묶음은 잡지 않는 묶음(`(?:…)`)으로 둔다 — 잡는
#   묶음이면 findall 이 전체 토큰 대신 묶음 값을 낸다
RUN_ID_RE = re.compile(r"wf_[0-9a-f]{8}(?:-[0-9a-f]{3})?(?![0-9a-f])", re.I)
# 합성 실행 ID — 공개 트리가 실행 ID 자리에 쓰는 값. 정확한 값만 통과한다 — 대역이 아니라 값 목록이다(같은 꼴의 다른 값 · 대문자 표기는
#   적중). 값은 전체 꼴로만 둔다 — 접미사 없는 꼴은 통과 목록이 없다(0 여덟 자만 적어도 적중이다). 값마다 출처:
#   0 채움 8자 + 순번 16진 3자(001 ~ 010 — 16개)  실행 ID 자리를 새로 채울 때 쓰는 값
#   반복 글자 a 8자 + b 3자                       scripts/fz_telemetry_report.py self-test(워크플로 폴더 · 실행 ID → 이름 해석)
#   반복 글자 1 · 2 · 3 의 8자 + a · b · c 의 3자  tests/fixtures/telemetry/stage-class(check.py 와 그 fixture 폴더 이름 셋)
#   반복 글자 넷은 트리의 시험 자료가 이미 쓰던 합성 값이다 — 폴더 이름과 여러 파일이 얽혀 있어 바꾸지 않고 여기 등재한다
#   ⛔ 실제 실행 ID 를 여기 더하지 않는다 — 트리의 실제 값을 0 채움 값으로 바꾼다. ⛔ 값은 이어 붙여 만든다 — 이 파일에 실행 ID 꼴을
#      글자 그대로 두지 않는다(이 파일도 실행 ID 계열 · 커밋 훅 · 감사 스캔으로 훑인다)
SYNTHETIC_RUN_IDS = frozenset(["wf_" + "0" * 8 + "-" + format(n, "03x") for n in range(1, 17)]
                              + ["wf_" + d * 8 + "-" + s * 3 for d, s in (("a", "b"), ("1", "a"), ("2", "b"), ("3", "c"))])
# UUID 꼴 — 8-4-4-4-12 16진(대소문자 무시). 캡처 ID 대조가 세션 ID 를 이 꼴로 뽑는다. 문서 정책의 계열은 아니다 — 문서의 UUID 는
#   세션이 아닐 수 있다
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
# 합성 세션 ID — 캡처 fixture 가 세션 ID 자리에 쓰는 값. 값 목록이다(대역 규칙이 아니다 — 실제 UUIDv7 도 0 으로 시작한다). 값마다 출처:
#   …0001 ~ …0004  rollout-replay 표본(provenance.json 이 sha256 을 고정한다 — 표본을 다시 쓰지 않는다)
#   …0011          mini-ledger 스트림 로그와 그 기대값(scripts/ab_ledger_selftest_r3.py)
#   1111…5555      가짜 GPT CLI 계열(tests/fixtures/gpt/_shim · kinds-resolve 입력)
#   ⛔ 목록 밖 값을 여기 더하지 않는다 — 세션 ID 자리가 더 필요한 시험(spawn-audit · ticket-prefix · fz-compact spill)은 위 값을
#      다시 쓴다(셀 · 시험마다 따로라 겹쳐도 된다)
#   ⛔ 값은 [0-9a-f-]{36} 꼴이어야 한다 — 수집기 · 래퍼가 그 꼴로 세션을 읽는다(밖이면 세션이 빈 값이 되어 배너 연결 판정이 바뀐다)
#   ⛔ 값은 이어 붙여 만든다 — 이 파일에 UUID 를 글자 그대로 두지 않는다
SYNTHETIC_SESSION_IDS = frozenset(["00000000-0000-7000-8000-" + format(n, "012x") for n in (0x1, 0x2, 0x3, 0x4, 0x11)]
                                  + ["-".join(d * w for d, w in zip("12345", (8, 4, 4, 4, 12)))])
# ANSI 제어열 — 캡처 ID 대조(capture_id_tokens) 전에 걷는다. CSI(색 · 커서 · 지우기 — ESC 또는 JSON 줄의 `\u001b` 표기) · OSC(제목 ·
#   링크 — BEL 또는 ST 로 끝난다) · 두 글자 이스케이프. 색 코드(`…m`)만 걷으면 다른 CSI 가 ID 를 갈랐을 때 놓친다
ANSI_SEQ = re.compile(r"(?:\x1b|\\u001[bB])\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-_]")

# ── 정책 — 무엇을 통과시키고 어느 계열을 돌릴지는 소비자가 고른다 ───────────────────────────────
#   families       돌릴 계열 id 집합 — None 이면 등록된 계열 전부(뒤에 등록한 계열도 들어간다)
#   home_allow · dev_allow  통과하는 계정 자리 이름(홈 경로 · dev 폴더)
#   account_shape  이 꼴이 아닌 자리는 계정으로 보지 않는다 — None 이면 모든 자리가 계정이다
#   mail_allow     통과하는 메일 도메인(하위 도메인 포함)
Policy = collections.namedtuple("Policy", "name families home_allow dev_allow dev_abs_allow account_shape mail_allow")
# 자리표시 계정 이름 — 출하 게이트(neutralize_axis)와 커밋 훅(자리표시 경로 마스크)이 따로 들고 있던 두 목록의 합.
#   루트(Users · home)를 가리지 않는다 — 트리의 기존 합성 값이 두 루트에 걸쳐 있다
DOC_HOME_NAMES = frozenset({"example", "you", "user", "me", "{user}", "<user>", "USER", "$USER",
                            "someone", "Shared", "u", "x"})
# dev 폴더의 자리표시 이름 — 옛 커밋 훅의 자리표시 경로 마스크에서 옮긴 값이다(훅은 사본 없이 이 정본을 부른다)
DOC_DEV_NAMES = frozenset({"gone"})
# 절대 경로 꼴(`<홈 루트>/<자리표시 계정>/dev/<이름>`)에서만 더 통과하는 이름 — 트리의 합성 값이다: 이 저장소 자신의 공개 이름과 범용
#   이름 둘. ⛔ 물결표 · 환경 변수 꼴에는 쓰지 않는다 — 그 꼴은 작성자 머신의 폴더 배치를 그대로 적은 것이라 저장소 이름도 막는다
DOC_DEV_ABS_NAMES = DOC_DEV_NAMES | frozenset({"fz-plugin", "repo", "other"})
# 내용에 남아도 되는 메일 도메인 — 트리에서 실제로 쓰는 예약 도메인 둘 + GitHub noreply · 커밋 trailer 가 쓰는 둘
CONTENT_MAIL_DOMAINS = ("example.com", "example.invalid", "users.noreply.github.com", "anthropic.com")
# 문서 · 출하 내용 — 계열 전부를 돌리고 자리표시 이름을 허용한다
POLICY_DOC = Policy("doc", None, DOC_HOME_NAMES, DOC_DEV_NAMES, DOC_DEV_ABS_NAMES, ACCOUNT_SHAPE, CONTENT_MAIL_DOMAINS)
# 캡처 감사(표본 스크럽 — tests/lib/sample_replay.py 의 scrub_hits) — 홈 경로(두 꼴) · 메일만 돌리고 전부 거부한다. 이 감사의 계약은 이 셋이다 —
#   다른 계열을 넣으면 표본 감사가 넓어진다. 캡처 로그의 세션 ID · 실행 ID 대조는 이 정책이 아니라 캡처 ID 감사(capture_id_tokens)다 —
#   run-id 를 여기 넣지 않는다
POLICY_CAPTURE = Policy("capture", frozenset({"home", "home-slug", "mail"}), frozenset(), frozenset(), frozenset(), None, ())

# 신원 축 — 내용 허용과 따로 둔다(예약 도메인이 신원에서 통과하면 회사 꼴 신원 픽스처가 공허하게 지나간다)
IDENTITY_EXACT = ("noreply" "@github.com",)
IDENTITY_SUFFIX = "@users.noreply.github.com"
# 등록표 밖 적중 id — 신원 축 · 비공개 규칙
IDENTITY, PRIVATE = "identity-mail", "private"

Found = collections.namedtuple("Found", "rule label token")    # 줄 하나의 적중 — rule 은 안정 id, label 은 표시용
Hit = collections.namedtuple("Hit", "line rule label token")   # 본문의 적중 — 줄 번호를 더한다(신원 · tagger 는 줄이 없어 None)


class Unrun(Exception):
    """판정 불가 — 부른 쪽은 exit 2 로 끝낸다(⛔ 통과 아님). 메시지는 사유 한 줄이다."""


# ── 규칙 계열 등록표 — 등록 순서가 판정 순서다 ────────────────────────────────────────────
# 항목 = (안정 id, 표시 라벨, 본문). 본문은 (줄, 정책, taken) → [토큰]. taken 은 번호 계열이 함께 쓰는 '이미 판정한 숫자 자리'
#   목록이다 — 같은 번호를 두 계열이 겹쳐 세지 않게, 먼저 잡은 계열이 그 자리를 가진다. 새 계열은 `@family` 로 덧붙인다
FAMILIES = []


def family(fid: str, label: str):
    """계열 등록 장식자 — id 는 정책 · 적중 · 셀이 가리키는 안정 이름이라 바꾸지 않는다."""
    def deco(fn):
        FAMILIES.append((fid, label, fn))
        return fn
    return deco


def is_reserved(num: str) -> bool:
    """예약 번호인가 — 0 으로 시작하는 3~5자리 또는 트리에 이미 있는 합성 번호."""
    return num in RESERVED_SYNTHETIC or bool(RESERVED_BAND.fullmatch(num))


def _overlaps(span, taken) -> bool:
    return any(span[0] < end and start < span[1] for start, end in taken)


def _account_ok(name: str, allow, policy: Policy) -> bool:
    """통과하는 자리인가 — 허용 이름이거나, 문서 정책에서 계정 꼴이 아닌 글자로 시작하는 자리(`{user}` · `$USER` · 정규식 조각)다.
    계정 꼴로 시작하는 자리는 그 앞쪽 런으로 판정한다(끝의 마침표는 뺀다) — 이름 자리는 경계 글자에서만 끝나므로 뒤에 붙은 글자(JSON 의
    이스케이프 · 닫는 중괄호 · 굵게 표시)까지 담긴다. 통째로 견주면 그 글자 하나로 실제 계정이 '계정 꼴 아님' 이 되어 통과한다."""
    if name in allow:
        return True
    if policy.account_shape is None:
        return False
    m = policy.account_shape.match(name)
    return m is None or m.group(0).rstrip(".") in allow


def _domain_ok(domain: str, allow) -> bool:
    d = domain.lower()
    return any(d == a or d.endswith("." + a) for a in allow)


@family("home", "개인 홈 경로")
def _f_home(line, policy, taken):
    return [m.group(0) + "/" for m in HOME_RE.finditer(line) if not _account_ok(m.group(1), policy.home_allow, policy)]


@family("home-slug", "개인 홈 경로(하이픈 꼴)")
def _f_home_slug(line, policy, taken):
    out = [(m.start(), m.group(0)) for m in HOME_SLUG_RE.finditer(line) if not _account_ok(m.group(1), policy.home_allow, policy)]
    if policy.account_shape is None:   # 계정 꼴을 가리지 않는 정책(캡처 감사) — 앞에 다른 글자가 붙은 꼴도 본다. 같은 자리는 한 번만 센다
        seen = {start for start, _ in out}
        out += [(m.start(), m.group(0)) for m in HOME_SLUG_ATTACHED_RE.finditer(line) if m.start() not in seen]
    return [tok for _, tok in sorted(out)]


@family("dev-home", "개인 작업 폴더 경로")
def _f_dev_home(line, policy, taken):
    out = []
    for m in DEV_RE.finditer(line):
        acct, allow = m.group("acct"), policy.dev_allow
        if acct is not None:
            # 절대 경로 꼴 — 통과하지 못하는 계정은 홈 경로 계열이 같은 자리를 이미 잡는다(한 자리를 두 번 세지 않는다)
            if not _account_ok(acct, policy.home_allow, policy):
                continue
            allow = policy.dev_abs_allow
        if not _account_ok(m.group("name"), allow, policy):
            out.append(m.group(0) + "/")
    return out


@family("mail", "메일 주소")
def _f_mail(line, policy, taken):
    return [m.group(0) for m in MAIL_RE.finditer(line) if not _domain_ok(m.group(1), policy.mail_allow)]


@family("placeholder", "자리표시자 번호")
def _f_placeholder(line, policy, taken):
    out = []
    for m in PLACEHOLDER_KEY_RE.finditer(line):
        taken.append(m.span(2))
        if not is_reserved(m.group(2)):
            out.append(m.group(0))
    return out


@family("key", "티켓 키 꼴")
def _f_key(line, policy, taken):
    out = []
    for m in KEY_RE.finditer(line):
        if m.group(1) in KEY_YIELD or _overlaps(m.span(2), taken):
            continue
        taken.append(m.span(2))
        if m.group(1) in KEY_RESERVED_ONLY and is_reserved(m.group(2)):
            continue
        if m.group(1) not in KEY_OK and m.group(0) not in SYNTHETIC_KEYS:
            out.append(m.group(0))
    return out


@family("pr", "PR 번호 꼴")
def _f_pr(line, policy, taken):
    out = []
    for rx in (PR_RE, HASH_RE, REPO_HASH_RE, PULL_RE):
        for m in rx.finditer(line):
            if _overlaps(m.span(1), taken):
                continue
            taken.append(m.span(1))
            if not is_reserved(m.group(1)):
                out.append(m.group(0))
    return out


def foreign_run_ids(line: str) -> list:
    """줄 → 합성 목록(SYNTHETIC_RUN_IDS) 밖의 실행 ID 꼴 토큰. 실행 ID 계열(문서 정책)과 capture_id_tokens 가 함께 부른다 — 대조를 두 벌
    두지 않는다. ANSI 제어열은 걷지 않는다 — 캡처 줄은 capture_id_tokens 로 본다."""
    return [m.group(0) for m in RUN_ID_RE.finditer(line) if m.group(0) not in SYNTHETIC_RUN_IDS]


def capture_id_tokens(line: str) -> list:
    """캡처 줄 하나 → [(종류, 토큰)] — 종류 session-id(UUID 꼴) | run-id(실행 ID 꼴). ANSI 제어열(ANSI_SEQ)을 걷은 뒤 합성 목록
    (SYNTHETIC_SESSION_IDS · SYNTHETIC_RUN_IDS) 밖 값만 낸다. 캡처 ID 감사(tests/lib/sample_replay.py 의 capture_id_audit)가 부른다.
    ⛔ 걷기를 부르는 쪽에 맡기지 않는다 — 색 코드가 ID 를 가르면 꼴 정규식이 0건이 되어 실제 ID 가 감사 없이 지나간다(fail-open).
       걷기 · 대조는 여기 한 벌이다(소비자는 사본을 두지 않고 이 함수를 부른다)."""
    plain = ANSI_SEQ.sub("", line)
    return ([("session-id", m.group(0)) for m in UUID_RE.finditer(plain) if m.group(0) not in SYNTHETIC_SESSION_IDS]
            + [("run-id", t) for t in foreign_run_ids(plain)])


@family("run-id", "워크플로 실행 ID")
def _f_run_id(line, policy, taken):
    return foreign_run_ids(line)


def line_hits(line: str, policy: Policy, rules) -> list:
    """줄 하나 × 정책 × 비공개 규칙 → [Found(id, 라벨, 토큰)]. 모든 검사 축이 이 함수를 부른다 — 축마다 규칙 사본을 두지 않는다.
    계열은 등록 순서로 돌고, 정책이 고른 계열만 돈다. rules 는 [(라벨, 정규식)] — 부른 쪽이 넘긴 만큼 정책과 무관하게 본다."""
    taken, out = [], []
    for fid, label, fn in FAMILIES:
        if policy.families is None or fid in policy.families:
            out += [Found(fid, label, tok) for tok in fn(line, policy, taken)]
    out += [Found(PRIVATE, label, m.group(0)) for label, rx in rules for m in rx.finditer(line)]
    return out


def text_hits(text: str, policy: Policy, rules) -> list:
    """본문 → [Hit(줄 번호, id, 라벨, 토큰)] — 개행으로 나눈 줄마다 line_hits 를 부른다."""
    return [Hit(n, f.rule, f.label, f.token) for n, line in enumerate(text.split("\n"), 1)
            for f in line_hits(line, policy, rules)]


# 경로 이름 적중의 라벨 접두 — 내용 적중(줄 번호가 있다)과 구분한다
NAME_LABEL = "경로 이름 · "


def _node_found(s: str, policy: Policy, rules) -> collections.Counter:
    """마디 문자열 하나의 적중 수 — 계열과 비공개 규칙은 내용과 같은 line_hits 다(티켓 키 꼴의 경계도 내용과 같다 — 영숫자)."""
    return collections.Counter((f.rule, f.label, f.token) for f in line_hits(s, policy, rules))


def name_hits(paths, policy: Policy, rules) -> list:
    """경로 목록 → [(마디, Hit)] — 파일 · 폴더 이름에 든 식별자(경로 이름 축). 규칙은 다시 쓰지 않는다: 마디마다 _node_found 를 부른다.
    마디는 경로의 앞부분이다(폴더는 끝에 `/`). 적중은 그 토큰이 처음 나타나는 가장 얕은 마디에 한 번만 붙인다 — 윗마디에 이미 있던
    적중을 빼므로 폴더 이름 하나가 그 아래 파일 수만큼 불어나지 않는다. 줄 번호는 없다(Hit.line 이 None).
    마디 앞에 `/` 를 붙여 본다 — 저장소 루트의 홈 꼴 폴더(앞에 `/` 가 없다)도 홈 경로 계열이 잡는다."""
    memo, out = {}, []
    for rel in sorted(set(paths)):
        parts, upper = rel.split("/"), collections.Counter()
        for i in range(1, len(parts) + 1):
            node = "/".join(parts[:i]) + ("/" if i < len(parts) else "")
            if node not in memo:
                memo[node] = _node_found("/" + node, policy, rules)
                out += [(node, Hit(None, rule, NAME_LABEL + label, tok))
                        for (rule, label, tok), k in sorted((memo[node] - upper).items()) for _ in range(k)]
            upper = memo[node]
    return out


REF_HEADS = ("refs/heads/", "refs/tags/")


def ref_name_hits(names, rules, where: str = "ref 이름") -> list:
    """ref 이름(브랜치 · 태그) → [(자리, Hit)] — push 하면 이름이 그대로 공개된다. 규칙은 경로 이름 축과 같다(name_hits — 마디마다
    계열 · 비공개 규칙 — 티켓 키 꼴의 경계도 내용과 같은 식이다). `refs/heads/` · `refs/tags/` 머리는 걷고 본다. 자리가 종류를 말하므로 경로 이름
    라벨 접두는 뗀다."""
    short = []
    for n in names:
        n = next((n[len(h):] for h in REF_HEADS if n.startswith(h)), n)
        if n:
            short.append(n)
    return [(f"{where} {node}", Hit(None, h.rule, h.label[len(NAME_LABEL):], h.token)) for node, h in name_hits(short, POLICY_DOC, rules)]


def identity_hits(name: str, email: str, rules, strict_identity: bool = True) -> list:
    """신원 한 벌(이름 · 메일) → [Found]. strict_identity 면 메일은 noreply 둘만 통과한다(신원 메일 규칙). 이름 · 메일 모두 비공개
    규칙을 본다 — strict_identity 가 거짓이어도(push 훅 · 유지관리자 표지 참 아님) 비공개 규칙은 그대로 본다."""
    e = (email or "").strip().lower()
    out = []
    if strict_identity and not (e in IDENTITY_EXACT or (e.endswith(IDENTITY_SUFFIX) and len(e) > len(IDENTITY_SUFFIX))):
        out.append(Found(IDENTITY, "신원 메일", email or "(빈 값)"))
    for field in (name or "", email or ""):
        out += [Found(PRIVATE, label, m.group(0)) for label, rx in rules for m in rx.finditer(field)]
    return out


def decode_text(data: bytes, shown: str) -> str:
    """검사 대상 디코드의 단일 계약 — UTF-8 엄격. ⛔ 디코드 실패 · NUL 바이트는 Unrun(건너뛰지 않는다).
    NUL 을 보는 이유: BOM 없는 UTF-16 은 UTF-8 디코드를 통과하지만 글자 사이에 NUL 이 끼어 어떤 규칙도 맞지 않는다."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise Unrun(f"UTF-8 로 읽지 못했다: {shown} — 바이트 {e.start}")
    if "\0" in text:
        raise Unrun(f"NUL 바이트가 있다(UTF-16 · 바이너리): {shown} — 텍스트 규칙으로 판정할 수 없다")
    return text


def read_text(path: str, shown: str = "") -> str:
    """파일 → 본문(decode_text 계약). ⛔ 읽기 실패는 Unrun."""
    shown = shown or path
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        raise Unrun(f"읽지 못했다: {shown} — {e.strerror or type(e).__name__}")
    return decode_text(data, shown)


def load_rules(path: str) -> list:
    """비공개 규칙 파일 → [(라벨, 정규식)]. 한 줄 한 정규식 · 빈 줄과 `#` 주석 줄은 건너뛴다 · 빈 파일이면 내장 규칙만.
    파일 머리의 BOM 과 줄 끝의 공백 · 탭은 걷는다 — 정규식에 섞이면 그 규칙이 오류 없이 죽는다(끝 공백이 뜻이면 `[ ]` 로 적는다).
    ⛔ 읽기 · 디코드 · 정규식 오류는 Unrun — 규칙 없이 돌면 비공개 이름이 통과한다. 사유에 규칙 원문을 싣지 않는다."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().split("\n")
    except (OSError, UnicodeDecodeError) as e:
        raise Unrun(f"비공개 규칙 파일을 읽지 못했다: {path} — {type(e).__name__}")
    out = []
    for n, ln in enumerate(lines, 1):
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        try:
            out.append((f"비공개 규칙 {n}", re.compile(ln.rstrip(" \t"))))
        except re.error as e:
            raise Unrun(f"비공개 규칙 {n}번째 줄의 정규식 오류: {e.msg}")
    return out


def _at(base: str, path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(base, path)


# 훅 정책의 git 설정 키 — 유지관리자 표지(참 거짓)와 비공개 규칙 파일 경로. ⛔ 저장소를 다른 체크아웃 · clone 으로 옮겨 커밋 · push 하는
#   절차는 이 두 키도 옮겨야 한다 — 저장소 로컬 설정에만 둔 표지가 그곳에 없으면 그곳의 커밋 훅 · push 훅은 표지 없이 내장 규칙만
#   보고, push 훅은 커밋 · 태그의 신원 메일 규칙도 끈다(identity_strict — 안내 한 줄)
HOOK_MAINTAINER_KEY = "fz.maintainer"
HOOK_RULES_KEY = "fz.neutralizeRules"


def _git_config(base: str, key: str, kind: str):
    """git 설정 값 하나 → 문자열 | None(설정 없음). base 가 든 저장소 · 사용자 · 시스템 설정을 git 의 우선순위대로 읽는다.
    kind 는 git 의 값 형식(--bool · --path)이다 — --path 는 `~` 를 푼다. ⛔ git 실행 실패 · 값 형식 오류(참 거짓이 아닌 표지 등)는
    Unrun — 읽지 못한 표지를 '표지 없음' 으로 읽으면 유지관리자 머신에서 비공개 규칙 없이 0 이 난다."""
    r = _gitb(base, "config", kind, "--get", key)
    if r is None:
        raise Unrun(f"git 을 실행하지 못했다 — 설정 {key}")
    if r.returncode == 1 and not r.stderr.strip():
        return None
    if r.returncode != 0:
        raise Unrun(f"git 설정 {key} 를 읽지 못했다 — {r.stderr.decode('utf-8', 'replace').strip()[:160]}")
    return r.stdout.decode("utf-8", "surrogateescape").rstrip("\n")


def _hook_rules(rules, source: str, base: str, hook_policy: bool):
    """해석한 규칙 → (규칙 목록, 출처). 훅 정책에서 규칙이 0개이고 유지관리자 표지가 참이면 Unrun — 잘리거나 주석만 남은 규칙 파일로 낸
    0 은 통과 증거가 아니다. 표지는 규칙이 0개일 때만 읽는다(규칙이 있는 경로의 동작은 그대로다). 훅 정책이 아니면 빈 파일은
    '내장 규칙만' 이다 — 출하 게이트는 규칙이 없을 때 빈 파일을 명시로 받는다."""
    if hook_policy and not rules and _git_config(base, HOOK_MAINTAINER_KEY, "--bool") == "true":
        raise Unrun(f"유지관리자 표지가 있는데 비공개 규칙이 0개다({source} — 빈 파일이거나 주석뿐이다 · git 설정 {HOOK_MAINTAINER_KEY})")
    return rules, source


def resolve_rules(explicit, base: str, hook_policy: bool = False):
    """비공개 규칙 해석 — `--rules FILE` > env FZ_NEUTRALIZE_RULES > 없음(상대 경로는 둘 다 base 기준). 반환 (규칙 목록, 출처 이름).
    ⛔ 지정한 경로가 비었거나 읽히지 않으면 Unrun — 다음 순위로 내려가지 않는다(지정한 규칙이 조용히 빠진다).
    훅 정책(hook_policy — 커밋 훅 · push 훅)은 env 다음에 git 설정 fz.neutralizeRules(상대 경로는 base 기준)를 보고, 그래도 없으면
    유지관리자 표지(git 설정 fz.maintainer)가 참일 때 Unrun 이다 — 유지관리자 머신에서 비공개 규칙 없이 낸 0 은 통과 증거가 아니다.
    표지가 없으면 내장 규칙만 본다(공개 기여자에게는 비공개 규칙 파일이 없다). 훅 정책에서 푼 규칙이 0개여도 표지가 참이면 Unrun 이다
    (_hook_rules). ⛔ 훅 정책이 아니면 git 설정을 읽지 않는다 — 출하 게이트는 규칙 파일을 명시로 받고 표지로 추정하지 않는다."""
    if explicit is not None:
        if not explicit:
            raise Unrun("--rules 경로가 비었다")
        return _hook_rules(load_rules(_at(base, explicit)), "--rules", base, hook_policy)
    env = os.environ.get("FZ_NEUTRALIZE_RULES", "")
    if env:
        return _hook_rules(load_rules(_at(base, env)), "FZ_NEUTRALIZE_RULES", base, hook_policy)
    if hook_policy:
        cfg = _git_config(base, HOOK_RULES_KEY, "--path")
        if cfg is not None:
            if not cfg:
                raise Unrun(f"git 설정 {HOOK_RULES_KEY} 가 비었다")
            return _hook_rules(load_rules(_at(base, cfg)), f"git 설정 {HOOK_RULES_KEY}", base, hook_policy)
        if _git_config(base, HOOK_MAINTAINER_KEY, "--bool") == "true":
            raise Unrun(f"유지관리자 표지가 있는데 비공개 규칙 파일이 없다(git 설정 {HOOK_MAINTAINER_KEY}) — env FZ_NEUTRALIZE_RULES 나 "
                        f"git 설정 {HOOK_RULES_KEY} 로 규칙 파일을 준다")
    return [], "없음"


def identity_strict(base: str, hook_policy: bool) -> bool:
    """커밋 · 태그의 신원 메일 규칙(noreply 만 통과)을 켤지. 훅 정책이 아니면 언제나 켠다 — 출하 게이트의 신원 축은 표지와 무관하게
    엄격하다. 훅 정책(push 훅)이면 유지관리자 표지(git 설정 fz.maintainer)가 참일 때만 켠다 — 공개 기여자의 개인 메일은 막지 않는다.
    ⛔ 표지를 읽지 못하면(값 형식 오류 · git 실패) Unrun — '표지 없음' 으로 읽으면 유지관리자의 비공개 신원이 검사 없이 지나간다."""
    if not hook_policy:
        return True
    return _git_config(base, HOOK_MAINTAINER_KEY, "--bool") == "true"


# git 을 부르는 머리 — replace ref 를 끈다. replace 는 로컬 조회만 바꾸고 push 는 원본 객체를 보낸다: 켠 채로 읽으면 더러운 커밋을
#   깨끗한 대체 커밋으로 가린 저장소에서 검사는 대체 내용을 보고 0 을 낸다. graft 파일은 이 스위치로 꺼지지 않는다(history_guard)
GIT = ("git", "--no-replace-objects")


def _git(top: str, *args):
    """git 을 top 에서 부른다 — git 실행 파일이 없으면 None."""
    try:
        return subprocess.run([*GIT, "-C", top, "-c", "core.quotepath=off", *args], capture_output=True,
                              text=True, encoding="utf-8", errors="surrogateescape")
    except OSError:
        return None


def _same_dir(a: str, b: str) -> bool:
    """두 경로가 같은 폴더인가 — 글자가 아니라 파일 시스템으로 본다(심볼릭 링크를 거친 경로 · 대소문자를 가리지 않는 볼륨)."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def tree_files(top: str):
    """top 의 공개 후보 파일 → (상대 경로 목록, 방식 'git' | 'walk').
    top 이 git 작업 트리의 꼭대기면 추적 파일(작업 트리에서 지운 것 제외)과 무시되지 않은 미추적 파일 — 아직 커밋하지 않은 새 파일도
    공개 후보다. 아니면(이력 없는 사본 · 바깥 저장소 안의 하위 폴더) 폴더 전체(.git 제외)를 걷는다 — 바깥 저장소의 무시 규칙이
    자기 `.git` 없는 사본의 파일을 가리면 읽지 않은 파일로 0 이 난다. ⛔ 목록 실패 · 폴더 순회 오류는 Unrun."""
    if not os.path.isdir(top):
        raise Unrun(f"--tree 대상이 폴더가 아니다: {top}")
    probe = _git(top, "rev-parse", "--show-toplevel")
    if probe is not None and probe.returncode == 0 and _same_dir(probe.stdout.rstrip("\n"), top):
        ls = _git(top, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        if ls is None or ls.returncode != 0:
            raise Unrun(f"git ls-files 실패 — {(ls.stderr if ls else '').strip()[:160]}")
        rels = sorted({p for p in ls.stdout.split("\0") if p})
        return [p for p in rels if os.path.lexists(os.path.join(top, p))], "git"
    errors, out = [], []
    for dp, dns, fns in os.walk(top, onerror=errors.append):
        out += [os.path.relpath(os.path.join(dp, d), top) for d in dns if os.path.islink(os.path.join(dp, d))]
        dns[:] = sorted(d for d in dns if d != ".git" and not os.path.islink(os.path.join(dp, d)))
        out += [os.path.relpath(os.path.join(dp, f), top) for f in sorted(fns) if f != ".git"]
    if errors:
        raise Unrun(f"폴더를 다 읽지 못했다: {errors[0]}")
    return out, "walk"


def scan_paths(top: str, rels, policy: Policy, rules):
    """상대 경로 목록 → (읽은 파일 수, [(경로, Hit)], [판정 불가 사유]).
    심볼릭 링크는 가리키는 경로 문자열이 내용이다(git 이 담는 것과 같다). 경로 이름도 본다(name_hits) — 폴더를 건너뛰기 전에
    목록 전부를 넘긴다(하위 저장소 경로의 이름도 공개된다)."""
    n, hits, unrun = 0, name_hits(rels, policy, rules), []
    for rel in rels:
        p = os.path.join(top, rel)
        if os.path.isdir(p) and not os.path.islink(p):
            continue   # 하위 저장소(gitlink) · 미추적 중첩 저장소 — 이 저장소의 내용이 아니다
        n += 1
        try:
            text = os.readlink(p) if os.path.islink(p) else read_text(p, rel)
        except Unrun as e:
            unrun.append(str(e))
            continue
        except OSError as e:
            unrun.append(f"링크를 읽지 못했다: {rel} — {e.strerror or type(e).__name__}")
            continue
        hits += [(rel, h) for h in text_hits(text, policy, rules)]
    return n, hits, unrun


def _printable(s: str) -> str:
    """출력용 — surrogateescape 로 풀린 UTF-8 밖 바이트(argv · git 출력 · 파일 이름)를 백슬래시 이스케이프로 적는다.
    ⛔ 그대로 print 하면 UTF-8 strict stdout 에서 UnicodeEncodeError 로 죽는다 — exit 1(적중)로 읽히고 `UNRUN:` 사유 줄 ·
    판정 불가(2)가 사라진다."""
    try:
        return s.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
    except UnicodeEncodeError:   # surrogateescape 대역 밖의 홀로 선 서로게이트
        return s.encode("utf-8", "backslashreplace").decode("utf-8")


def report(label: str, nfiles: int, source: str, rules, hits, unrun) -> int:
    """결과 출력 → exit. hits = [(자리, Hit)] — 자리는 경로다(--commits 는 축 이름과 해시 또는 태그를 앞에 붙이고, --release-body 는
    `<태그> 제목` · `<태그> 본문` 이다). 줄이 없는
    적중(신원 · tagger — Hit.line 이 None)은 `자리: 라벨 — 토큰` 으로 낸다. 판정 불가가 하나라도 있으면 적중이 있어도 2 다(미판정이
    위반보다 앞선다). 줄마다 _printable 을 거친다 — 경로 · 토큰 · 사유에 UTF-8 밖 바이트가 있어도 exit 계약이 깨지지 않는다."""
    for rel, h in hits:
        loc = rel if h.line is None else f"{rel}:{h.line}"
        print(_printable(f"  ❌ {loc}: {h.label} — {h.token}"))
    for why in unrun:
        print(_printable(f"UNRUN: {why} (⛔ 통과 아님)"))
    tail = _printable(f"{label} files={nfiles} rules={len(rules)}({source})")
    if unrun:
        print(f"LEAK_UNRUN {tail} unrun={len(unrun)} hits={len(hits)}")
        return UNRUN
    if hits:
        print(f"LEAK_HIT {tail} hits={len(hits)}")
        return HIT
    print(f"LEAK_CLEAN {tail}")
    return OK


def run_text_file(path: str, shown: str, rules, source: str) -> int:
    hits, unrun = [], []
    try:
        hits = [(shown, h) for h in text_hits(read_text(path, shown), POLICY_DOC, rules)]
    except Unrun as e:
        unrun.append(str(e))
    return report("text-file", 1, source, rules, hits, unrun)


def run_identity_mail(mail: str, name: str, rules, source: str) -> int:
    """신원 한 벌(메일 · 이름) → exit — 신원 정책(identity_hits). 메일은 신원 메일 규칙(noreply 둘만 통과)을 언제나 켜고(--hook-policy
    여도 끄지 않는다 — 부르는 쪽은 커밋 전에 신원을 막으려는 호출자다), 비공개 규칙은 메일 · 이름 칸에 건다. 커밋 객체 밖에서 신원을
    미리 재는 호출자(격리 clone 스크립트 — 원본 로컬 설정 · 신원 환경 변수)가 메일 정규식 사본을 두지 않고 이 판정을 부른다. 적중
    자리는 `신원` 이다(줄이 없는 적중 — report)."""
    hits = [("신원", Hit(None, f.rule, f.label, f.token)) for f in identity_hits(name, mail, rules)]
    return report("identity-mail", 1, source, rules, hits, [])


def release_text(base: str, tag: str):
    """발행된 릴리스 TAG → (제목, 본문) — `gh release view TAG --json name,body`. gh 는 PATH 에서 찾아 base 에서 부른다(어느 GitHub
    저장소인지는 gh 가 그 저장소의 원격 · GH_REPO 로 정한다). 노트 파일을 검사해도 발행 명령이 다른 본문(커밋 메시지 · 태그 주석에서
    지은 본문 · 손으로 고친 본문)을 올리면 그 글자는 검사 없이 나간다 — 출하 절차는 발행 뒤에 실제로 올라간 글자를 이 함수로 다시 읽는다.
    ⛔ 태그가 비었거나 `-` 로 시작함(gh 가 옵션으로 읽는다) · gh 부재 · 실행 실패 · 0 아닌 종료(인증 만료 · 오프라인 · 그 태그의
    릴리스 없음 — 그 실행의 출력은 읽지 않는다) · UTF-8 아닌 출력 · JSON 아님 · 제목 · 본문이 문자열이 아님 · 빈 본문(공백만 포함)은
    Unrun — 읽지 못한 본문을 '위반 없음' 으로 읽으면 발행된 글자가 검사 없이 남는다."""
    if not tag or tag.startswith("-"):
        raise Unrun(f"태그가 비었거나 '-' 로 시작한다: {tag!r}")
    gh = shutil.which("gh")
    if gh is None:
        raise Unrun("gh 가 없다(PATH) — 발행된 릴리스 본문을 읽지 못했다")
    shown = f"gh release view {tag}"
    try:
        r = subprocess.run([gh, "release", "view", tag, "--json", "name,body"], cwd=base, capture_output=True)
    except OSError as e:
        raise Unrun(f"gh 를 실행하지 못했다 — {e.strerror or type(e).__name__}")
    if r.returncode != 0:
        raise Unrun(f"{shown} 실패(exit {r.returncode}) — {r.stderr.decode('utf-8', 'replace').strip()[:160]}")
    try:
        data = json.loads(decode_text(r.stdout, shown))
    except ValueError:
        raise Unrun(f"{shown} 의 출력이 JSON 이 아니다")
    name, body = (data.get("name"), data.get("body")) if isinstance(data, dict) else (None, None)
    if not isinstance(name, str) or not isinstance(body, str):
        raise Unrun(f"{shown} 의 출력에 제목(name) · 본문(body) 문자열이 없다")
    if not body.strip():
        raise Unrun(f"{shown} 의 본문이 비었다 — 본문 없음은 통과가 아니다")
    return name, body


def run_release_body(base: str, tag: str, rules, source: str) -> int:
    """발행된 릴리스의 제목 · 본문 → exit — 노트 파일(--text-file)과 같은 판정(문서 정책 · 내장 규칙 + 비공개 규칙 — text_hits).
    적중 자리는 `<TAG> 제목:줄` · `<TAG> 본문:줄` 이다. 본문을 읽지 못하면 판정 불가다(files=0)."""
    label = f"release-body:{tag}"
    try:
        name, body = release_text(base, tag)
    except Unrun as e:
        return report(label, 0, source, rules, [], [str(e)])
    hits = [(f"{tag} {where}", h) for where, text in (("제목", name), ("본문", body))
            for h in text_hits(text, POLICY_DOC, rules)]
    return report(label, 1, source, rules, hits, [])


def tree_scan(top: str, rules):
    """작업 트리 전문 → (방식 'git' | 'walk', 읽은 파일 수, [(경로, Hit)], [판정 불가 사유]) — --tree 와 --commits --with-tree 가
    함께 쓴다(같은 판정을 두 벌 두지 않는다). 읽은 파일이 0개면 판정 불가 사유다. ⛔ 목록 실패는 Unrun 으로 올린다."""
    rels, how = tree_files(top)
    n, hits, unrun = scan_paths(top, rels, POLICY_DOC, rules)
    if n == 0:
        unrun.append(f"검사한 파일이 0개다: {top}")
    return how, n, hits, unrun


def run_tree(top: str, rules, source: str) -> int:
    try:
        how, n, hits, unrun = tree_scan(top, rules)
    except Unrun as e:
        return report("tree", 0, source, rules, [], [str(e)])
    return report(f"tree:{how}", n, source, rules, hits, unrun)


# ── git 축 — 추가 줄만 본다. 규칙은 다시 쓰지 않는다: 줄마다 line_hits 를 부른다 ──────────────────────────────
# hunk 머리 — 새 쪽 시작 줄 번호만 쓴다
HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# diff 꼴을 사용자 설정과 무관하게 고정한다 — 색(color.ui=always) · 외부 diff · textconv · 접두 생략(diff.noprefix)이 켜져 있으면
#   hunk · 머리를 읽지 못하거나 원문이 아닌 변환 본문을 읽는다
DIFF_FIXED = ("--no-color", "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/")
# 개명 처리는 축마다 다르다. 커밋 범위는 rename 탐지를 끈다 — 켜면 개명한 파일 속 남은 식별자가 '안 바뀐 줄' 로 빠진다.
#   스테이징은 옛 경로와 짝짓는다 — 개명만으로 기존 정당 참조가 막히지 않게 하고, 남은 내용은 밖으로 나가는 관문(커밋 범위)이 잡는다
RANGE_RENAMES, STAGED_RENAMES = "--no-renames", "-M"


def _gitb(top: str, *args, stdin=None):
    """git 을 top 에서 부른다 — 출력은 바이트 그대로(줄바꿈 변환 · 디코드 없음). stdin 은 git 에 넘길 바이트다(None 이면
    넘기지 않는다 — 지금까지의 호출과 같다). git 실행 파일이 없으면 None."""
    try:
        return subprocess.run([*GIT, "-C", top, "-c", "core.quotepath=off", *args], input=stdin, capture_output=True)
    except OSError:
        return None


def _git_out(top: str, what: str, *args, stdin=None) -> bytes:
    """git 출력 바이트. ⛔ 실행 실패 · 0 아닌 종료는 Unrun — 빈 출력을 '바뀐 것 없음' 으로 읽지 않는다."""
    r = _gitb(top, *args, stdin=stdin)
    if r is None:
        raise Unrun(f"git 을 실행하지 못했다 — {what}")
    if r.returncode != 0:
        raise Unrun(f"git {what} 실패 — {r.stderr.decode('utf-8', 'replace').strip()[:160]}")
    return r.stdout


def git_top(base: str) -> str:
    """base 가 든 저장소의 작업 트리 최상위. ⛔ 작업 트리가 없으면(저장소 아님 · bare) Unrun."""
    out = _git_out(base, "rev-parse --show-toplevel", "rev-parse", "--show-toplevel")
    top = out.decode("utf-8", "surrogateescape").rstrip("\n")
    if not top:
        raise Unrun(f"작업 트리를 찾지 못했다: {base}")
    return top


def history_guard(top: str):
    """이력을 걷는 축(--commits)의 전제 — graft 파일에 내용이 있으면 Unrun. graft 는 커밋의 부모를 로컬에서만 바꿔 rev-list 가
    가려진 커밋을 건너뛴다(replace 끄기로 꺼지지 않는다). 검사한 범위와 실제로 나갈 범위가 달라져 0 을 믿을 수 없다."""
    rel = _git_out(top, "rev-parse --git-path", "rev-parse", "--git-path", "info/grafts").decode("utf-8", "surrogateescape").rstrip("\n")
    try:
        with open(_at(top, rel), "rb") as fh:
            body = fh.read()
    except FileNotFoundError:
        return
    except OSError as e:
        raise Unrun(f"graft 파일을 읽지 못했다 — {type(e).__name__}")
    if any(ln.strip() and not ln.lstrip().startswith(b"#") for ln in body.split(b"\n")):
        raise Unrun("graft 파일(info/grafts)에 내용이 있다 — 부모를 로컬에서만 바꿔 검사 범위가 실제로 나갈 커밋과 달라진다(지우고 다시 돈다)")


def resolve_commit(top: str, ref: str) -> str:
    """ref → 커밋 SHA. ⛔ 비었거나 `-` 로 시작하거나(git 이 옵션으로 읽는다) 커밋으로 풀리지 않으면 Unrun."""
    if not ref or ref.startswith("-"):
        raise Unrun(f"기준 ref 가 비었거나 '-' 로 시작한다: {ref!r}")
    r = _gitb(top, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if r is None or r.returncode != 0 or not r.stdout.strip():
        raise Unrun(f"기준 ref 를 풀지 못했다: {ref}")
    return r.stdout.decode("ascii", "replace").strip()


def range_revs(top: str, spec: str):
    """SPEC(`--range` · `--commits` 가 함께 쓴다 — 문법을 두 벌 두지 않는다) → (풀린 커밋 목록, REF 꼴인가).
    REF 꼴이면 [REF], A..B 꼴이면 [A, B](빈 쪽은 HEAD — git 과 같다). 뜻은 부르는 쪽이 정한다 — --range 의 REF 는 REF 대비 작업
    트리(미추적 파일 포함 — 아직 커밋하지 않은 새 파일도 공개 후보다)이고 A..B 는 두 커밋 사이다(--commits 의 뜻은 commit_revs).
    ⛔ 세 점 범위(A...B)는 기준이 병합 기점으로 바뀌어 받지 않는다(Unrun)."""
    if "..." in spec:
        raise Unrun(f"세 점 범위는 받지 않는다: {spec} — REF 또는 A..B 로 기준을 적는다")
    if ".." in spec:
        a, b = spec.split("..", 1)
        return [resolve_commit(top, a or "HEAD"), resolve_commit(top, b or "HEAD")], False
    return [resolve_commit(top, spec)], True


def _numstat(out: bytes):
    """`git diff --numstat -z` → (바뀐 파일 수, [git 이 바이너리로 본 경로]).
    개명 · 복사 항목은 `수<TAB>수<TAB>` 뒤에 옛 경로 · 새 경로가 따로 온다. ⛔ 형식 밖이면 Unrun."""
    toks, n, binary, i = out.split(b"\0"), 0, [], 0
    while i < len(toks):
        tok, i = toks[i], i + 1
        if not tok:
            continue
        parts = tok.split(b"\t", 2)
        if len(parts) != 3:
            raise Unrun("git diff --numstat 출력이 형식 밖이다")
        path = parts[2]
        if not path:
            if i + 1 >= len(toks):
                raise Unrun("git diff --numstat 의 개명 항목이 잘렸다")
            path, i = toks[i + 1], i + 2
        n += 1
        if parts[0] == b"-" or parts[1] == b"-":
            binary.append(path.decode("utf-8", "surrogateescape"))
    return n, binary


def _diff_path(raw: str):
    """`+++ ` 뒤 → 경로(지운 파일이면 None). 공백 든 이름 뒤에 git 이 붙이는 탭을 떼고, C 따옴표는 벗기기만 한다(표시용)."""
    if raw.endswith("\t"):
        raw = raw[:-1]
    if raw == "/dev/null":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return raw[2:] if raw.startswith("b/") else raw


def parse_added(diff: str) -> list:
    """git diff 출력 → [(경로, 새 쪽 줄 번호, 본문)] — hunk 안의 `+` 줄만 추가 줄이다.
    `diff --git` 에서 hunk 상태를 끄고, 머리 구간의 `+++ ` 로 경로를 잡고, `@@` 에서 hunk 를 켠다.
    ⛔ 상태 없이 접두로 고르면 내용이 `++` 로 시작하는 추가 줄(diff 에서 `+++ …`)을 머리로 읽어 놓친다. hunk 머리 · 경로를 못 읽으면 Unrun."""
    out, path, in_hunk, no = [], None, False, 0
    for ln in diff.split("\n"):
        if ln.startswith("diff --git "):
            path, in_hunk = None, False
        elif ln.startswith("@@"):
            m = HUNK_RE.match(ln)
            if not m:
                raise Unrun(f"hunk 머리를 읽지 못했다: {ln[:80]}")
            in_hunk, no = True, int(m.group(1))
        elif not in_hunk:
            if ln.startswith("+++ "):
                path = _diff_path(ln[4:])
        elif ln.startswith("+"):
            if path is None:
                raise Unrun("추가 줄의 경로를 정하지 못했다 — diff 머리가 형식 밖이다")
            out.append((path, no, ln[1:]))
            no += 1
        elif ln.startswith(" "):
            no += 1
    return out


def added_lines(top: str, renames: str, revs):
    """git diff(revs) 의 추가 줄 → (바뀐 파일 수, [(경로, 줄 번호, 본문)], [판정 불가 사유]).
    ⛔ git 이 바이너리로 본 파일(numstat 의 `-`)은 건너뛰지 않고 판정 불가 사유다 — 모든 git 축(추가 줄을 텍스트로 잴 수 없다).
    추가 줄은 decode_text 계약으로 읽는다 — UTF-8 이 아닌 줄이 나온 파일은 사유 하나를 남기고 그 파일의 나머지 줄을 보지 않는다.
    git 실패는 Unrun 으로 올린다."""
    ns = _git_out(top, "diff --numstat", "diff", "--numstat", "-z", renames, *DIFF_FIXED, *revs, "--")
    n, binary = _numstat(ns)
    unrun = [f"git 이 바이너리로 본 파일이다: {p} — 텍스트 규칙으로 판정할 수 없다" for p in binary]
    raw = _git_out(top, "diff", "diff", "-U0", renames, *DIFF_FIXED, *revs, "--")
    out, bad = [], set()
    for path, no, s in parse_added(raw.decode("utf-8", "surrogateescape")):
        if path in bad:
            continue
        try:
            out.append((path, no, decode_text(s.encode("utf-8", "surrogateescape"), f"{path}:{no}")))
        except Unrun as e:
            bad.add(path)
            unrun.append(str(e))
    return n, out, unrun


def added_hits(added, policy: Policy, rules) -> list:
    """[(경로, 줄 번호, 본문)] → [(경로, Hit)] — 줄마다 line_hits 를 부른다(축마다 규칙 사본을 두지 않는다)."""
    return [(p, Hit(no, f.rule, f.label, f.token)) for p, no, text in added for f in line_hits(text, policy, rules)]


def new_paths(top: str, renames: str, revs) -> list:
    """git diff(revs) 에서 새로 생긴 쪽 경로 — 더한 파일 · 개명과 복사의 새 이름(--diff-filter=ACR).
    ⛔ 추가 줄에서 경로를 얻지 않는다 — 빈 새 파일 · 내용이 그대로인 개명은 hunk 가 없다. 지운 파일과 내용 · 모드만 바뀐 파일은 새
    이름이 아니다(나쁜 이름을 지우는 정리가 막히지 않는다). git 실패는 Unrun 으로 올린다."""
    out = _git_out(top, "diff --name-only", "diff", "--name-only", "-z", "--diff-filter=ACR", renames, *DIFF_FIXED, *revs, "--")
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def added_scan(top: str, renames: str, revs, rules):
    """git diff(revs) 의 새 경로 이름 + 추가 줄(문서 정책) → (바뀐 파일 수, [(자리, Hit)], [판정 불가 사유]). 모든 git 축이 이 함수를
    부른다 — 이름 적중(줄 번호 없음)이 앞, 추가 줄 적중이 뒤다."""
    n, added, unrun = added_lines(top, renames, revs)
    return n, name_hits(new_paths(top, renames, revs), POLICY_DOC, rules) + added_hits(added, POLICY_DOC, rules), unrun


def range_scan(top: str, spec: str, rules):
    """커밋 범위 축 → (읽은 파일 수, [(경로, Hit)], [판정 불가 사유]). 기준 대비 새 경로 이름 · 추가 줄(--no-renames) + 작업 트리 비교면
    미추적 파일 전문. 같은 폴더 마디의 이름 적중이 두 목록(추적한 새 경로 · 미추적 경로)에서 나오면 한 번만 센다.
    ⛔ ref · git · 목록 실패는 Unrun 으로 올린다."""
    revs, worktree = range_revs(top, spec)
    n, hits, unrun = added_scan(top, RANGE_RENAMES, revs, rules)
    if worktree:
        ls = _git_out(top, "ls-files --others", "ls-files", "-z", "--others", "--exclude-standard")
        rels = sorted({p for p in ls.decode("utf-8", "surrogateescape").split("\0") if p})
        m, uhits, uunrun = scan_paths(top, rels, POLICY_DOC, rules)
        n, hits, unrun = n + m, hits + [h for h in uhits if h not in hits], unrun + uunrun
    return n, hits, unrun


def staged_scan(top: str, rules):
    """스테이징 축 → (바뀐 파일 수, [(경로, Hit)], [판정 불가 사유]). 인덱스가 HEAD 에 더한 줄과 새 경로 이름(-M)만 — 작업 트리 · 미추적 파일은
    보지 않는다. ⛔ git 실패는 Unrun 으로 올린다."""
    return added_scan(top, STAGED_RENAMES, ["--cached"], rules)


# ── 커밋마다 축 · 태그 축 — 범위의 두 끝만 비교하면 중간 커밋에서 더했다가 지운 줄 · 신원 · 메시지 · 태그 주석을 못 본다 ──────────
# 객체 이름 — rev-list · rev-parse · hash-object 출력은 이 꼴만 받는다(SHA-1 · SHA-256)
OID_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# 신원 머리 값 `이름 <메일> 시각 시간대` — 이름은 마지막 `<` 앞, 메일은 꺾쇠 안이다
IDENT_RE = re.compile(r"(.*)<([^<>]*)>[^<>]*")
# 적중 자리에 싣는 커밋 해시 길이 — 출하 게이트 러너가 이 표기로 단언한다(git 의 짧은 해시처럼 저장소마다 늘어나지 않는다)
SHORT = 12
# 객체 머리 중 텍스트로 보지 않는 구조 값(객체 이름 · 종류). 신원 머리(author · committer · tagger)와 박힌 태그(mergetag)는 따로
#   판정하고, 그 밖의 머리(서명 gpgsig · 인코딩 · 도구가 더한 머리 · 태그 이름)는 문서 정책 텍스트로 본다 — 공개되는 객체의 일부다
COMMIT_STRUCT, TAG_STRUCT = ("tree", "parent"), ("object", "type")


def _cat_batch(top: str, oids) -> dict:
    """객체 목록 → {oid: (종류, 본문 바이트)} — `git cat-file --batch` 한 번(객체마다 git 을 띄우지 않는다).
    ⛔ git 실패 · 없는 객체 · 형식 밖이거나 잘린 출력은 Unrun — 읽지 못한 커밋의 신원 · 메시지를 '없음' 으로 읽지 않는다."""
    if not oids:
        return {}
    data = _git_out(top, "cat-file --batch", "cat-file", "--batch", stdin="".join(o + "\n" for o in oids).encode("ascii"))
    out, pos = {}, 0
    for oid in oids:
        nl = data.find(b"\n", pos)
        head = data[pos:nl].decode("ascii", "replace").split(" ") if nl >= 0 else []
        if len(head) != 3 or head[0] != oid or not head[2].isdigit():
            raise Unrun(f"git cat-file 이 객체를 내지 못했다: {oid[:SHORT]} — {' '.join(head)[:80]}")
        end = nl + 1 + int(head[2])
        if data[end:end + 1] != b"\n":
            raise Unrun(f"git cat-file 출력이 잘렸다: {oid[:SHORT]}")
        out[oid] = (head[1], data[nl + 1:end])
        pos = end + 1
    return out


def _split_object(body: bytes):
    """커밋 · 태그 객체 → ({머리 이름: [값 바이트]}, 메시지 바이트). 머리와 메시지는 첫 빈 줄에서 나뉜다.
    앞이 공백인 줄은 앞 머리 값의 이어지는 줄이다(서명 gpgsig · 병합 태그 mergetag) — 공백 하나를 떼고 그 값에 줄바꿈으로 잇는다
    (mergetag 값은 박힌 태그 객체 전체가 된다). ⛔ 머리가 이어지는 줄로 시작하면 Unrun."""
    head, sep, msg = body.partition(b"\n\n")
    if not sep:
        head, msg = body.rstrip(b"\n"), b""
    fields, last = {}, None
    for ln in head.split(b"\n"):
        if ln[:1] == b" ":
            if last is None:
                raise Unrun("객체 머리가 이어지는 줄로 시작한다 — 형식 밖이다")
            fields[last][-1] += b"\n" + ln[1:]
            continue
        name, _, val = ln.partition(b" ")
        last = name.decode("ascii", "replace")
        fields.setdefault(last, []).append(val)
    return fields, msg


def _ident(val: bytes, shown: str):
    """신원 머리 값 → (이름, 메일). decode_text 계약으로 읽는다. ⛔ 꼴 밖이면 Unrun — 메일을 찾지 못한 신원을 깨끗하다고 읽지 않는다."""
    m = IDENT_RE.fullmatch(decode_text(val, shown))
    if not m:
        raise Unrun(f"신원 머리를 읽지 못했다: {shown}")
    return m.group(1).strip(), m.group(2)


def _ident_hits(where: str, val: bytes, rules, strict_identity: bool = True) -> list:
    """신원 머리 값 하나 → [(자리, Hit)]. 신원은 줄이 없어 Hit.line 이 None 이다(report 가 `자리: 라벨 — 토큰` 으로 낸다).
    strict_identity 가 거짓이어도 신원 꼴은 읽는다(_ident — 꼴 밖이면 Unrun) — 끄는 것은 신원 메일 규칙뿐이다(identity_hits)."""
    name, email = _ident(val, where)
    return [(where, Hit(None, f.rule, f.label, f.token)) for f in identity_hits(name, email, rules, strict_identity)]


def _header_hits(where: str, fields: dict, skip, rules):
    """객체 머리 가운데 skip 밖의 값 → ([(자리, Hit)], [판정 불가 사유]) — 문서 정책 텍스트(자리 `머리 <where> <머리 이름>:줄`).
    서명(gpgsig) 갑옷의 머리줄 · 도구가 더한 머리 · 태그 이름도 공개되는 객체의 일부라 건너뛰지 않는다."""
    hits, unrun = [], []
    for name, vals in fields.items():
        if name in skip:
            continue
        for val in vals:
            at = f"머리 {where} {name}"
            try:
                hits += [(at, h) for h in text_hits(decode_text(val, at), POLICY_DOC, rules)]
            except Unrun as e:
                unrun.append(str(e))
    return hits, unrun


def _tag_object_hits(where: str, body: bytes, rules, strict_identity: bool = True):
    """태그 객체 본문 → ([(자리, Hit)], [판정 불가 사유]) — 로컬 주석 태그(--tag)와 병합 커밋에 박힌 태그(mergetag)가 함께 쓴다.
    tagger 는 신원 정책(자리 `tagger <where>` · strict_identity 가 거짓이면 신원 메일 규칙을 끈다 — identity_hits), 주석 본문은
    문서 정책(`주석 <where>:줄`), 그 밖의 머리는 _header_hits 다.
    ⛔ tagger 머리가 없거나 · 다른 태그를 가리키거나(안쪽 태그의 칸을 보지 못한다) · 머리가 형식 밖이면 사유를 남긴다 — 판정하지
    못한 칸을 깨끗하다고 읽지 않는다."""
    try:
        fields, msg = _split_object(body)
    except Unrun as e:
        return [], [f"{where}: {e}"]
    hits, unrun = _header_hits(where, fields, TAG_STRUCT + ("tagger",), rules)
    if fields.get("type") == [b"tag"]:
        unrun.append(f"태그가 다른 태그를 가리킨다: {where} — 안쪽 태그의 tagger · 주석을 보지 못한다")
    if not fields.get("tagger"):
        unrun.append(f"tagger 머리가 없다: {where} — 신원을 판정할 수 없다")
    for val in fields.get("tagger", []):
        try:
            hits += _ident_hits(f"tagger {where}", val, rules, strict_identity)
        except Unrun as e:
            unrun.append(str(e))
    try:
        hits += [(f"주석 {where}", h) for h in text_hits(decode_text(msg, f"주석 {where}"), POLICY_DOC, rules)]
    except Unrun as e:
        unrun.append(str(e))
    return hits, unrun


def commit_revs(top: str, spec: str, excludes) -> list:
    """`--commits` 값 → rev-list 인자(풀린 SHA · 뺄 끝은 `^SHA`). SPEC 문법은 range_revs 한 벌을 쓰고 뜻만 다르다:
    REF = REF 에서 닿는 커밋 전부(루트부터 — 기준 태그가 없는 첫 출하 · 원격 tip 을 풀 수 없는 push) · A..B = B 에서 닿고 A 에서
    닿지 않는 커밋. excludes 는 더 뺄 끝이다(push 훅이 원격이 가졌다고 확인한 tip). ⛔ 세 점 범위 · 풀리지 않는 ref 는 Unrun."""
    revs, whole = range_revs(top, spec)
    if not whole:
        revs = [revs[1], "^" + revs[0]]
    return revs + ["^" + resolve_commit(top, x) for x in excludes]


def commit_list(top: str, revs) -> list:
    """rev-list → 커밋 SHA 목록(오래된 것부터). ⛔ git 실패 · 형식 밖 줄은 Unrun."""
    shas = _git_out(top, "rev-list", "rev-list", "--reverse", *revs, "--").decode("ascii", "replace").split()
    bad = [s for s in shas if not OID_RE.fullmatch(s)]
    if bad:
        raise Unrun(f"git rev-list 출력이 형식 밖이다: {bad[0][:80]}")
    return shas


def _empty_tree(top: str) -> str:
    """이 저장소 해시 방식의 빈 트리 이름 — 루트 커밋의 추가 줄은 빈 트리 대비다(-w 없이 이름만 낸다 — git 은 빈 트리를 객체 없이도
    안다). ⛔ git 실패 · 형식 밖은 Unrun."""
    oid = _git_out(top, "hash-object", "hash-object", "-t", "tree", os.devnull).decode("ascii", "replace").strip()
    if not OID_RE.fullmatch(oid):
        raise Unrun(f"빈 트리 이름이 형식 밖이다: {oid[:80]}")
    return oid


def commit_scan(top: str, revs, rules, strict_identity: bool = True):
    """커밋마다 축 → (커밋 수, 바뀐 파일 수, [(자리, Hit)], [판정 불가 사유]). 커밋 하나씩 신원(author · committer — 신원 정책 ·
    strict_identity 가 거짓이면 신원 메일 규칙을 끈다) ·
    메시지 · 그 밖의 머리(문서 정책) · 박힌 태그(mergetag — 태그 축과 같은 판정) · 추가 줄(문서 정책 · --no-renames)을 본다.
    추가 줄은 첫 부모 대비다 — 병합 커밋은 옆 가지가 들여온 줄이 여기 나온다(옆 가지 커밋이 범위 밖이어도). 루트 커밋은 빈 트리
    대비다. ⛔ rev-list · 객체 읽기 실패는 Unrun 으로 올린다. 커밋 하나의 머리 · diff · 디코드 실패는 사유로 남기고 다음 커밋을 본다."""
    shas = commit_list(top, revs)
    objs = _cat_batch(top, shas)
    empty, nfiles, hits, unrun = None, 0, [], []
    for sha in shas:
        short = sha[:SHORT]
        kind, body = objs[sha]
        if kind != "commit":
            unrun.append(f"커밋이 아닌 객체다: {short} ({kind})")
            continue
        try:
            fields, msg = _split_object(body)
        except Unrun as e:
            unrun.append(f"{short}: {e}")
            continue
        for role in ("author", "committer"):
            if not fields.get(role):
                unrun.append(f"{role} 머리가 없다: {short} — 신원을 판정할 수 없다")
            for val in fields.get(role, []):
                try:
                    hits += _ident_hits(f"신원 {short} {role}", val, rules, strict_identity)
                except Unrun as e:
                    unrun.append(str(e))
        try:
            hits += [(f"메시지 {short}", h) for h in text_hits(decode_text(msg, f"메시지 {short}"), POLICY_DOC, rules)]
        except Unrun as e:
            unrun.append(str(e))
        hh, hu = _header_hits(short, fields, COMMIT_STRUCT + ("author", "committer", "mergetag"), rules)
        hits, unrun = hits + hh, unrun + hu
        for val in fields.get("mergetag", []):
            th, tu = _tag_object_hits(f"mergetag {short}", val, rules, strict_identity)
            hits, unrun = hits + th, unrun + tu
        parents = fields.get("parent", [])
        try:
            if not parents and empty is None:
                empty = _empty_tree(top)
            old = parents[0].decode("ascii", "replace") if parents else empty
            if not OID_RE.fullmatch(old):
                raise Unrun(f"부모 머리가 형식 밖이다: {old[:80]}")
            n, found, why = added_scan(top, RANGE_RENAMES, [old, sha], rules)
        except Unrun as e:
            unrun.append(f"{short}: {e}")
            continue
        nfiles += n
        hits += [(f"{'경로' if h.line is None else '추가 줄'} {short} {p}", h) for p, h in found]
        unrun += [f"{short}: {w}" for w in why]
    return len(shas), nfiles, hits, unrun


def tag_scan(top: str, names, rules, strict_identity: bool = True, cover=None):
    """태그 축 → (주석 태그 수, 가벼운 태그 수, [(자리, Hit)], [판정 불가 사유]). NAME 은 태그 이름 또는 `refs/tags/…` 다.
    주석 태그는 _tag_object_hits(tagger · 주석 · 그 밖의 머리)로 본다. 가벼운 태그는 tagger · 주석 칸이 없다 — 빈 값을 위반으로도
    통과 증거로도 읽지 않고 세기만 한다. 이름은 종류와 무관하게 ref_name_hits 로 본다(자리 `태그 이름 <마디>`).
    cover 는 검사 범위가 덮은 끝들(`^SHA` — 커밋 범위의 끝과 더 뺀 끝)이다. 태그가 가리키는 커밋에서 닿는데 그 끝들에서 닿지 않는
    커밋이 있으면 사유를 남긴다 — 태그를 올리면 그 커밋도 나가는데 커밋 범위가 보지 않았다. None 이면(범위를 풀지 못했다) 보지 않는다.
    ⛔ 비었거나 `-` 로 시작하는 이름 · 풀리지 않는 태그 · 커밋을 가리키지 않는 태그(트리 · blob — 커밋 범위가 그 내용을 덮지
    못한다)는 그 태그만 사유로 남기고 다음 태그를 본다(다른 태그의 적중은 함께 낸다). 객체 읽기 실패는 Unrun 으로 올린다."""
    found, unrun = [], []
    for name in dict.fromkeys(names):
        if not name or name.startswith("-"):
            unrun.append(f"태그 이름이 비었거나 '-' 로 시작한다: {name!r}")
            continue
        ref = name if name.startswith("refs/tags/") else "refs/tags/" + name
        r = _gitb(top, "rev-parse", "--verify", "--quiet", ref)
        oid = r.stdout.decode("ascii", "replace").strip() if r is not None and r.returncode == 0 else ""
        if not OID_RE.fullmatch(oid):
            unrun.append(f"태그를 풀지 못했다: {name}")
            continue
        c = _gitb(top, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
        if c is None or c.returncode != 0 or not c.stdout.strip():
            unrun.append(f"태그가 커밋을 가리키지 않는다: {name} — 커밋 범위가 그 내용을 덮지 못한다")
            continue
        found.append((name, oid))
        if cover is not None:
            try:
                extra = _git_out(top, "rev-list --count", "rev-list", "--count", c.stdout.decode("ascii", "replace").strip(),
                                 *cover, "--").decode("ascii", "replace").strip()
            except Unrun as e:
                unrun.append(f"{name}: {e}")
                continue
            if extra != "0":
                unrun.append(f"태그가 검사 범위 밖의 커밋 {extra}개를 가리킨다: {name} — 그 태그를 올리면 함께 나가는데 이 실행은 "
                             "보지 않았다(범위에 넣어 다시 돌거나 태그를 지운다)")
    objs = _cat_batch(top, [oid for _, oid in found])
    annotated, lightweight, hits = 0, 0, ref_name_hits([name for name, _ in found], rules, "태그 이름")
    for name, oid in found:
        kind, body = objs[oid]
        if kind != "tag":
            lightweight += 1
            continue
        annotated += 1
        th, tu = _tag_object_hits(name, body, rules, strict_identity)
        hits, unrun = hits + th, unrun + tu
    return annotated, lightweight, hits, unrun


def run_range(base: str, spec: str, rules, source: str) -> int:
    try:
        n, hits, unrun = range_scan(git_top(base), spec, rules)
    except Unrun as e:
        return report(f"range:{spec}", 0, source, rules, [], [str(e)])
    return report(f"range:{spec}", n, source, rules, hits, unrun)


def run_staged(base: str, rules, source: str) -> int:
    try:
        n, hits, unrun = staged_scan(git_top(base), rules)
    except Unrun as e:
        return report("staged", 0, source, rules, [], [str(e)])
    return report("staged", n, source, rules, hits, unrun)


def run_commits(base: str, spec: str, excludes, tags, with_tree: bool, rules, source: str, strict_identity: bool = True,
                ref_names=()) -> int:
    """커밋마다 축 + 태그 축(+ 작업 트리 전문). strict_identity 가 거짓이면(훅 정책 · 유지관리자 표지 참 아님) 커밋 · 태그의 신원 메일
    규칙을 끈다. 축마다 판정 불가를 따로 모은다 — 한 축이 못 돌아도 다른 축의 적중을 함께 내고,
    미판정이 하나라도 있으면 최종 exit 는 2 다(report — 미판정이 위반보다 앞선다). 끝 줄 라벨은 어느 경로로 끝나도 같은 꼴로
    커밋 · 태그 수를 싣는다(못 잰 수는 0) — 범위가 비어 0 이 난 것인지 부른 쪽이 가릴 수 있게."""
    ncommits = nfiles = annotated = lightweight = 0
    hits, unrun, top = ref_name_hits(ref_names, rules), [], None
    try:
        top = git_top(base)
        history_guard(top)   # 걸려도 top 은 남는다 — 아래 축의 적중을 함께 낸다(미판정이 앞선다)
    except Unrun as e:
        unrun.append(str(e))
    if top is not None:
        revs = None
        try:
            revs = commit_revs(top, spec, excludes)
            ncommits, nfiles, chits, cunrun = commit_scan(top, revs, rules, strict_identity)
            hits, unrun = hits + chits, unrun + cunrun
        except Unrun as e:
            unrun.append(str(e))
        cover = None if revs is None else ["^" + r.lstrip("^") for r in revs]
        try:
            annotated, lightweight, thits, tunrun = tag_scan(top, tags, rules, strict_identity, cover)
            hits, unrun = hits + thits, unrun + tunrun
        except Unrun as e:
            unrun.append(str(e))
        if with_tree:
            try:
                _how, m, whits, wunrun = tree_scan(top, rules)
                nfiles, hits, unrun = nfiles + m, hits + [("전문 " + rel, h) for rel, h in whits], unrun + wunrun
            except Unrun as e:
                unrun.append(str(e))
    label = f"commits:{spec} commits={ncommits} annotated={annotated} lightweight={lightweight}" + (" with-tree" if with_tree else "")
    return report(label, nfiles, source, rules, hits, unrun)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="leak_rules.py", description=__doc__.split("\n", 1)[0], allow_abbrev=False)
    ap.add_argument("-C", dest="base", metavar="DIR", help="상대 경로의 기준 · --tree 의 기본 대상 · git 축의 저장소(기본: cwd)")
    ap.add_argument("--rules", metavar="FILE", help="비공개 규칙 파일 — env FZ_NEUTRALIZE_RULES 보다 앞선다")
    ap.add_argument("--hook-policy", action="store_true",
                    help="훅(커밋 훅 · push 훅)의 정책 — env 다음에 git 설정 fz.neutralizeRules 를 보고, 없으면 유지관리자 표지 "
                         "fz.maintainer 로 판정한다. --commits 와 함께면 신원 메일 규칙을 표지가 참일 때만 켠다(문서 정책 · 계열 "
                         "선택은 그대로)")
    ap.add_argument("--exclude", action="append", metavar="REF", help="--commits 에서 더 뺄 끝(여러 번)")
    ap.add_argument("--tag", action="append", metavar="NAME", help="--commits 와 함께 볼 태그(여러 번)")
    ap.add_argument("--ref-name", action="append", metavar="NAME", help="--commits 와 함께 볼 공개될 ref 이름(여러 번 · push 의 목적지 이름)")
    ap.add_argument("--with-tree", action="store_true", help="--commits 와 함께 작업 트리 전문(--tree 와 같은 판정)을 본다")
    ap.add_argument("--identity-name", metavar="NAME", help="--identity-mail 과 함께 볼 신원 이름(비공개 규칙만 건다)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text-file", metavar="F")
    mode.add_argument("--tree", nargs="?", const="", metavar="DIR")
    mode.add_argument("--range", metavar="REF")
    mode.add_argument("--commits", metavar="SPEC")
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--identity-mail", metavar="MAIL")
    mode.add_argument("--release-body", metavar="TAG")
    mode.add_argument("--self-test", action="store_true")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.commits is None and (a.exclude or a.tag or a.ref_name or a.with_tree):
        # 함께 받는 옵션을 다른 모드에 주면 조용히 버리지 않는다 — 버리면 주지 않은 검사를 한 것처럼 0 이 나온다
        print("UNRUN: --exclude · --tag · --ref-name · --with-tree 는 --commits 와 함께만 받는다 — 검사 대상을 정하지 못했다 (⛔ 통과 아님)")
        return UNRUN
    if a.identity_name is not None and a.identity_mail is None:
        print("UNRUN: --identity-name 은 --identity-mail 과 함께만 받는다 — 검사 대상을 정하지 못했다 (⛔ 통과 아님)")
        return UNRUN
    if a.self_test:
        return self_test()
    base = os.path.abspath(a.base) if a.base else os.getcwd()
    strict_identity = True
    try:
        if not os.path.isdir(base):
            raise Unrun(f"-C 대상이 폴더가 아니다: {a.base}")
        rules, source = resolve_rules(a.rules, base, a.hook_policy)
        if a.commits is not None:
            # 신원 축은 커밋마다 축에만 있다 — 다른 모드에서는 표지를 읽지 않는다(커밋 훅 --staged 의 결과가 표지 값으로 바뀌지 않게)
            strict_identity = identity_strict(base, a.hook_policy)
    except Unrun as e:
        print(_printable(f"UNRUN: {e} (⛔ 통과 아님)"))
        return UNRUN
    if a.hook_policy and source == "없음":
        # 공개 기여자 머신 — 막지 않고 무엇을 보지 않았는지 한 줄로 알린다(유지관리자 표지가 있으면 resolve_rules 가 이미 Unrun 이다)
        print(f"NOTE: 비공개 규칙 파일이 없다 — 내장 규칙만 본다(유지관리자는 git 설정 {HOOK_RULES_KEY} 로 규칙 파일을 준다)")
    if not strict_identity:
        print(f"NOTE: 유지관리자 표지(git 설정 {HOOK_MAINTAINER_KEY})가 참이 아니다 — 커밋 · 태그의 신원 메일 규칙(noreply 만 통과)을 "
              "보지 않는다(메시지 · 머리 · 추가 줄 · 태그 주석 · 비공개 규칙은 본다)")
    if a.text_file is not None:
        return run_text_file(_at(base, a.text_file), a.text_file, rules, source)
    if a.tree is not None:
        return run_tree(_at(base, a.tree) if a.tree else base, rules, source)
    if a.range is not None:
        return run_range(base, a.range, rules, source)
    if a.commits is not None:
        return run_commits(base, a.commits, a.exclude or [], a.tag or [], a.with_tree, rules, source, strict_identity,
                           a.ref_name or [])
    if a.staged:
        return run_staged(base, rules, source)
    if a.identity_mail is not None:
        return run_identity_mail(a.identity_mail, a.identity_name or "", rules, source)
    if a.release_body is not None:
        return run_release_body(base, a.release_body, rules, source)
    # 모드를 더하면 분기도 더한다 — 분기 없는 모드가 다른 대상을 재고 0 을 내지 않게 여기서 닫는다
    print("UNRUN: 처리 분기가 없는 모드다 — 검사 대상을 정하지 못했다 (⛔ 통과 아님)")
    return UNRUN


# ── self-test ─────────────────────────────────────────────────────────────────────────
# ⛔ 시험 문자열은 쪼개 적는다 — 이 파일도 같은 규칙 · 커밋 훅 · 출하 게이트 · 감사 스캔으로 훑인다
CELLS = []
_GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                 "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX", "GIT_CEILING_DIRECTORIES", "FZ_NEUTRALIZE_RULES",
                 # 부모 git 이 `-c` 로 넘긴 설정 — 전역 · 시스템 설정을 끊어도 이 둘로는 들어온다(유지관리자 표지 · 서명 강제)
                 "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT")
# 임시 저장소의 git 은 훅 · 서명을 끈다 — 사용자 훅 · 서명 키가 셀 결과를 바꾸지 않게
_GIT_CFG = ("-c", "core.hooksPath=" + os.devnull, "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false")
# 합성 신원 — 신원 축의 허용 꼴(noreply)이라 기본 커밋은 신원 축을 통과한다. 신원을 시험하는 셀은 자기 값으로 덮어쓴다
_ST_NAME, _ST_MAIL = "fz-selftest", "0+fz-selftest" + IDENTITY_SUFFIX
H, HM, DV = "/Us" + "ers/", "/ho" + "me/", "~/d" + "ev/"
# 신원 셀의 회사 꼴 메일 — 예약 TLD 지만 신원 축은 noreply 둘만 통과한다
_CORP = "dev" + "@corp" + ".example"


def _k(*parts) -> str:
    return "".join(parts)


# 트리에 이미 있는 합성 값 — 문서 정책에서 적중 0 이어야 한다
SYNTH_KEY_LINES = (
    "경로 " + _k("TKT-", "1234") + "/index.md · mkdir " + _k("TKT-", "123"),
    "핸드오프 " + _k("TKT-", "9999") + "로 · /path/to/" + _k("PRJ-", "1234") + "/gates",
    _k("TICKET-", "0000") + "/gates · " + _k("TICKET-", "000") + " · " + _k("TKT-", "12") + "suffix · " + _k("PRJ-", "12"),
    "지적 " + _k("ISSUE-", "001") + " · " + _k("ISSUE-", "202616"),
    "hotfix/" + _k("ABT-", "1001") + "-x · " + _k("ABT-", "2001"),
    "PR " + "#" + "123" + " 리뷰 · " + _k("NOTASK-", "20261110") + " · " + _k("TKT-", "0") + " base · " + _k("TKT-", "2"),
)
# 두 루트(Users · home) × 자리표시 이름 전부 — 루트를 가리지 않고 통과한다
SYNTH_HOME_LINES = tuple("예시 " + top + name + "/a" for top in (H, HM)
                         for name in ("example", "someone", "Shared", "u", "x", "user", "me", "you", "USER", "{user}", "$USER"))
SYNTH_DEV_LINES = (DV + "gone/x", DV + "{user}/x", "자리 " + DV + "<이름>/")
SYNTH_MAIL_LINES = ("fixture" + "@example.invalid", "dev" + "@example.com", "t" + "@sub.example.com",
                    "Co-Authored-By: x <" + "noreply" + "@anthropic.com>", "1+u" + "@users.noreply.github.com")
SYNTH_ALL = SYNTH_KEY_LINES + SYNTH_HOME_LINES + SYNTH_DEV_LINES + SYNTH_MAIL_LINES
# 개명 셀의 본문 — 열 줄 뒤에 남은 식별자 한 줄. 짧으면 한 줄만 바꿔도 유사도가 rename 문턱(50%)에 걸린다
RENAME_BODY = "".join(f"줄 {i}\n" for i in range(1, 11)) + "남은 " + H + "alice/w\n"
# 목록 밖 실행 ID — 쪼개 적고 실행할 때 잇는다(이 파일이 실행 ID 계열 · 커밋 훅 · 감사 스캔에 걸리지 않게). 목록 바로 밖의 0 채움 값 둘 ·
#   임의 16진 · 16진만 대문자 · 접두까지 대문자(합성 목록은 소문자 값이라 대문자 표기는 목록 밖이다)
RUN_ID_FOREIGN = ("wf_" + "0" * 8 + "-" + "011", "wf_" + "0" * 8 + "-" + "000", "wf_" + "1a2b" + "3c4d" + "-" + "5e6",
                  "wf_" + "ABCD" + "EF12" + "-" + "3F4", "WF_" + "1A2B" + "3C4D" + "-" + "5E6")
# 접미사 없는 실행 ID — `wf_` 뒤 16진 8자에서 끝나는 꼴(줄여 적은 실제 값). 쪼개 적는다(위와 같은 이유). 임의 16진 · 0 여덟 자(합성 값의
#   앞 8자와 같아도 통과 목록이 없다) · 대문자 · 접미사가 16진 3자가 아닌 표기 셋(2자 · 1자 · 4자). 적중 토큰은 언제나 `wf_` 와 앞 8자다.
#   ⛔ 앞 셋([0] · [1] · [2])은 접미사 없이 둔다 — run-id-long-hex-ok 가 그 뒤에 16진을 이어 붙여 9자 이상 표본과 대조 표본을 만든다
RUN_ID_BARE = ("wf_" + "1a2b" + "3c4d", "wf_" + "0" * 8, "WF_" + "1A2B" + "3C4D", "wf_" + "0" * 8 + "-" + "01",
               "wf_" + "1a2b" + "3c4d" + "-" + "5", "wf_" + "1a2b" + "3c4d" + "-" + "5e6f")
# 목록 밖 세션 ID(UUIDv7 꼴 — 0 으로 시작한다) — 쪼개 적는다
SESSION_FOREIGN = "0" + "19a" + "5b2c" + "-1d3e-7f40-8a5b-" + "6c7d8e9f0a1b"
# 꼴만 닮은 문서 표기(정규식 · 자리표시자 · 스크립트 이름) — 문서 정책 · 캡처 ID 대조에서 적중 0 이어야 한다. capture-ids 러너
#   (tests/fixtures/leak-gates/capture-ids/run.sh)도 이 목록을 읽는다 — 표기를 더할 때 여기 한 곳만 고친다
RUN_ID_NOTATION = ("wf_[0-9a-f]{8}-[0-9a-f]{3}", "wf_[0-9a-f]{8}-…", "wf_<runId>", "wf_XXXXXXXX-XXX", "wf_xxxxxxxx-xxx",
                   "fz_wf_metrics.py", "workflows/wf_{runId}/journal.jsonl")


def cell(name: str):
    """셀 등록 — 본문은 (임시 폴더) → (통과 여부, 실패 설명). 새 셀은 이 장식자로 덧붙인다."""
    def deco(fn):
        CELLS.append((name, fn))
        return fn
    return deco


def _env(tmp: str, extra=None) -> dict:
    """자식 프로세스 환경 — 사용자 · 시스템 git 설정과 기본 무시 파일, 저장소를 가리키는 git env, 비공개 규칙 env 를 끊고
    합성 신원을 둔다(셀 결과가 머신마다 갈리지 않게)."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_CEILING_DIRECTORIES=os.path.dirname(tmp),
               XDG_CONFIG_HOME=os.path.join(tmp, ".xdg"), GIT_AUTHOR_NAME=_ST_NAME, GIT_AUTHOR_EMAIL=_ST_MAIL,
               GIT_COMMITTER_NAME=_ST_NAME, GIT_COMMITTER_EMAIL=_ST_MAIL, PYTHONIOENCODING="utf-8")
    env.update(extra or {})
    return env


def _w(root: str, rel: str, body) -> str:
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(body if isinstance(body, bytes) else body.encode("utf-8"))
    return p


def _tgit(tmp: str, root: str, *args, extra=None) -> str:
    """임시 저장소의 git — 격리 환경(_env) · 훅과 서명 끔(_GIT_CFG). extra 는 덧씌울 env 다(신원 셀이 author · committer 를
    바꾼다 — 주석 태그의 tagger 는 committer 값으로 찍힌다). 실패면 RuntimeError(셀 준비 실패 → 셀 FAIL)."""
    r = subprocess.run(["git", "-C", root, *_GIT_CFG, *args], env=_env(tmp, extra), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} 실패: {r.stderr.strip()[:160]}")
    return r.stdout


def _repo(tmp: str, tracked: dict, untracked=None) -> str:
    """tmp/r 에 git 저장소 — tracked 는 인덱스에 올리고(커밋하지 않는다) untracked 는 파일만 둔다."""
    root = os.path.join(tmp, "r")
    os.makedirs(root)
    for rel, body in tracked.items():
        _w(root, rel, body)
    _tgit(tmp, root, "init", "-q")
    if tracked:
        _tgit(tmp, root, "add", "-A")
    for rel, body in (untracked or {}).items():
        _w(root, rel, body)
    return root


def _commit_all(tmp: str, root: str, msg: str, extra=None) -> str:
    """작업 트리 전부를 커밋하고 그 SHA 를 돌려준다 — _repo 가 인덱스에만 올린 것을 기준 커밋으로 만든다(격리 환경 · 합성 신원 —
    extra 로 그 커밋의 신원 env 를 덮어쓴다)."""
    _tgit(tmp, root, "add", "-A")
    _tgit(tmp, root, "commit", "-qm", msg, extra=extra)
    return _tgit(tmp, root, "rev-parse", "HEAD").strip()


def _cli(tmp: str, args, cwd=None, extra=None):
    """이 파일의 CLI 를 자식 프로세스로 — (exit, stdout+stderr)."""
    p = subprocess.run([sys.executable, SELF, *args], cwd=cwd or tmp, env=_env(tmp, extra), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def _ids(hits) -> list:
    return [h.rule for h in hits]


def _rule_tokens(hits) -> list:
    """적중 → [(id, 토큰)] — capture_id_tokens 의 (종류, 토큰) 꼴과 같아 두 대조를 같은 기대값으로 비교한다."""
    return [(h.rule, h.token) for h in hits]


def _short(sha: str) -> str:
    return sha[:SHORT]


@cell("home-placeholder-doc-ok-capture-rejected")
def _c_home_policy(tmp):
    line = "예시 " + H + "example/work/a.md"
    doc, cap = line_hits(line, POLICY_DOC, []), line_hits(line, POLICY_CAPTURE, [])
    return doc == [] and _ids(cap) == ["home"], f"문서 {doc} · 캡처 {cap}"


@cell("home-doc-placeholder-union-ok")
def _c_home_union(tmp):
    got = [h for ln in SYNTH_HOME_LINES for h in line_hits(ln, POLICY_DOC, [])]
    return got == [], f"문서 정책 적중 {got}"


@cell("home-account-name-hit")
def _c_home_account(tmp):
    lines = (H + "alice/work", "cfg=" + HM + "bob/.cfg", H + "fixture-user/x", H + "{x}/" + H + "carol/y")
    doc = [len(line_hits(ln, POLICY_DOC, [])) for ln in lines]
    cap = [len(line_hits(ln, POLICY_CAPTURE, [])) for ln in lines]
    return doc == [1, 1, 1, 1] and cap == [1, 1, 1, 2], f"문서 {doc} · 캡처 {cap}"


@cell("dev-home-placeholder-ok-account-hit")
def _c_dev_home(tmp):
    quiet = [h for ln in SYNTH_DEV_LINES for h in line_hits(ln, POLICY_DOC, [])]
    loud = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in (DV + "alice/x", "cd " + DV + "fz-work/sub")]
    return quiet == [] and loud == [["dev-home"]] * 2, f"통과해야 할 적중 {quiet} · 줄별 적중 {loud}"


@cell("home-no-trailing-slash-hit")
def _c_home_bare(tmp):
    # 끝에 `/` 가 없는 홈 경로 — 환경 변수 값 · JSON 값 · PATH 조각 · 한글 조사 · 백틱 · 괄호 · 문장 끝 마침표 · 줄 끝 · 쉼표로 이은 둘
    loud = ("export HOME=" + H + "alice", '"cwd":"' + H + 'alice"', "PATH=" + H + "alice:/opt/bin", H + "alice에서 연다",
            "`" + H + "alice`", "(" + H + "alice)", "경로는 " + H + "alice.", HM + "bob", H + "alice, " + H + "carol;")
    # 자리표시 이름은 문장부호가 붙어도 통과한다(캡처 정책은 그것도 거부한다) · 점으로 시작하는 이름 · 이름 없는 루트는 자리가 아니다
    quiet = ("경로는 " + H + "example.", H + "you", "cd " + H + "you, 그다음", "(" + H + "user)", H + ".codex", "루트 " + H,
             H + "<user>")
    doc = [[f.token for f in line_hits(ln, POLICY_DOC, [])] for ln in loud]
    cap = [[f.token for f in line_hits(ln, POLICY_CAPTURE, [])] for ln in loud]
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    qcap = [len(line_hits(ln, POLICY_CAPTURE, [])) for ln in quiet[:4]]
    # 토큰까지 본다 — 문서 정책은 앞쪽 계정 꼴로 판정하므로, 경계 글자가 빠져도 적중 수는 같고 토큰에 뒤 글자가 딸려 온다
    want = [[H + "alice/"]] * 7 + [[HM + "bob/"], [H + "alice/", H + "carol/"]]
    # 받아들이는 과잉 차단 — 경로 중간의 홈 루트 이름 마디 뒤 이름도 계정 자리로 읽는다(왼쪽 경계를 두면 마운트 경로 아래의 홈 경로를 놓친다)
    mid = _ids(line_hits("src" + HM + "index.ts", POLICY_DOC, []))
    return (doc == want and cap == want and q == [] and qcap == [1] * 4 and mid == ["home"],
            f"문서 {doc} · 캡처 {cap} · 통과해야 할 적중 {q} · 캡처(자리표시) {qcap} · 경로 중간 마디 {mid}")


@cell("home-slug-hit-placeholder-ok")
def _c_home_slug(tmp):
    # 하이픈으로 편 홈 경로 — 끝 하이픈이 없어도 · 앞이 밑줄이어도 잡는다. 옵션 이름 · 낱말 사이 하이픈 · 영숫자에 붙은 꼴은 아니다
    us, hs = "-Us" + "ers-", "-ho" + "me-"
    loud = ("~/.claude/projects/" + us + "alice-dev-Proj/memory/MEMORY.md", "cwd " + hs + "bob", "x_" + us + "carol-w", us + "alice.")
    quiet = ("~/.claude/projects/" + us + "you-dev-x/", us + "example.", "--home-dir", "sweet-home-page", "a" + us + "alice-x")
    # 앞에 다른 글자가 붙은 꼴(드라이브 글자 · 볼륨 이름 뒤 · 영숫자에 붙은 꼴) — 캡처 정책만 본다(계정 뒤에 하이픈이 있을 때 · 한 자리는 한 번).
    #   문서 정책은 보지 않는다(받아들이는 한계). 옵션 이름 · 낱말 사이 하이픈은 캡처 정책에서도 이 꼴이 아니다
    attached = ("C-" + us + "alice-proj", "-Volumes-Data" + us + "alice-proj", quiet[4])
    doc = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    cap = [_ids(line_hits(ln, POLICY_CAPTURE, [])) for ln in loud + quiet[:2] + attached]
    capq = [h for ln in quiet[2:4] for h in line_hits(ln, POLICY_CAPTURE, [])]
    q = [h for ln in quiet + attached for h in line_hits(ln, POLICY_DOC, [])]
    dot = [f.token for f in line_hits(loud[3], POLICY_DOC, [])]   # 이름 끝의 마침표는 토큰에 담지 않는다(판정은 앞쪽 계정 꼴이라 적중 수로는 안 보인다)
    return (doc == [["home-slug"]] * 4 and cap == [["home-slug"]] * 9 and q == [] and capq == [] and dot == [us + "alice"],
            f"문서 {doc} · 캡처 {cap} · 통과해야 할 적중 {q} · 캡처에서도 아닌 꼴 {capq} · 마침표 뒤 토큰 {dot}")


@cell("dev-home-prefixes-hit")
def _c_dev_prefixes(tmp):
    # 홈을 적는 꼴 셋 · 끝에 `/` 가 없는 꼴. 절대 경로 꼴은 계정이 통과할 때만 이 계열이 본다 — 통과 못 하는 계정은 홈 경로 계열 하나만 적중한다.
    #   절대 경로 꼴에서만 통과하는 이름(저장소 이름 · 범용 이름)은 물결표 · 환경 변수 꼴에서는 적중이다
    d = "/d" + "ev/"
    loud = ("$HOME" + d + "alice-app/x", "${HOME}" + d + "alice-app", DV + "alice-app", "cd " + DV + "alice-app.",
            H + "you" + d + "alice-app/src", DV + "fz-plugin/x", "$HOME" + d + "repo", H + "<user>" + d + "alice-app/src")
    quiet = (H + "example" + d + "fz-plugin/x", H + "u" + d + "repo/", H + "u" + d + "other", DV + "gone", "$HOME" + d + "gone/x",
             H + "you" + d + "gone.", H + "<user>" + d + "fz-plugin/x")
    doc = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    own = _ids(line_hits(H + "alice" + d + "app/x", POLICY_DOC, []))
    return (doc == [["dev-home"]] * 8 and q == [] and own == ["home"],
            f"줄별 적중 {doc} · 통과해야 할 적중 {q} · 계정이 걸리는 줄 {own}")


@cell("key-joined-boundary-hit")
def _c_key_joined(tmp):
    # 낱말을 `-` · `_` 로 이은 꼴(브랜치 · 파일 이름을 내용에 적은 것)도 키 꼴이다. 계획 감사 지적 id 의 하위 접두는 예약 번호일 때만 통과한다
    loud = ("fix-" + _k("XYZ-", "4821"), _k("XYZ-", "4821") + "_notes.md", "a_" + _k("XYZ-", "4821") + "-b", "ISSUE-" + _k("PLAN-", "4821"))
    quiet = ("ISSUE-" + _k("PLAN-", "003"), "x-" + _k("ISO-", "8601") + "_y", "sha-256 · utf-8", _k("XYZ-", "4821") + "x")
    lo = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    return lo == [["key"]] * 4 and q == [], f"줄별 적중 {lo} · 통과해야 할 적중 {q}"


@cell("pr-case-colon-repo-pull-hit")
def _c_pr_forms(tmp):
    # 소문자 · 쌍점 · `<소유자>/<저장소>#` · pull 경로. 예약 번호는 네 꼴 모두 통과한다 · 앵커와 낱말 끝의 pr 은 이 꼴이 아니다
    r, pl = "org/repo" + "#", "/pu" + "ll/"
    loud = ("pr " + "4821", "Pr#" + "4821", "PR: " + "4821", "PR:" + "4821", "fixes " + r + "4821", "see github.com/o/r" + pl + "4821",
            "/pu" + "lls/" + "4821", "pr-" + "482", "fix_PR-" + "4821", "x_PR#" + "4821", "notes_pr" + "4821" + "_review.md")
    quiet = ("PR: " + "0123", r + "1234", pl + "012", "expr " + "4821", "docs/page" + "#" + "L4821", "pr " + "48", "x_PR-" + "0123")
    lo = [len(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    # `_` 로 이은 꼴은 경로 이름 축에서도 같다(한 식을 쓴다) — 예약 번호는 통과한다
    nm = [h.rule for _, h in name_hits(["d/notes_pr" + "4821" + "_review.md", "d/x_PR-" + "0123" + ".md"], POLICY_DOC, [])]
    return lo == [1] * len(loud) and q == [] and nm == ["pr"], f"줄별 적중 수 {lo} · 통과해야 할 적중 {q} · 이름 축 {nm}"


@cell("account-leading-run-judged")
def _c_account_lead_run(tmp):
    # 이름 뒤에 경계가 아닌 글자가 붙은 꼴 — JSON 의 이스케이프 개행 · 이스케이프 따옴표 · 셸 기본값의 닫는 중괄호 · 굵게 표시. 이름 자리가
    #   그 글자까지 담아도 앞쪽 계정 꼴로 판정한다. 자리표시 이름(뒤에 마침표가 있어도) · 계정 꼴이 아닌 글자로 시작하는 자리는 그대로 통과한다
    d = "/d" + "ev/"
    loud = ('"stdout":"' + H + 'alice\\n"', 'cd \\"' + H + 'alice\\"', "${X:-" + H + "alice}", "**" + H + "alice**",
            "${X:-~" + d + "alice-app}", '"cwd":"~' + d + 'alice-app\\n"')
    quiet = ("${X:-" + H + "you}", '"cwd":"' + H + 'example\\n"', "**경로는 " + H + "example.**", H + "{user}x", H + "$USER\\n",
             H + "[^/]+", "${X:-~" + d + "gone}")
    lo = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    return lo == [["home"]] * 4 + [["dev-home"]] * 2 and q == [], f"줄별 적중 {lo} · 통과해야 할 적중 {q}"


@cell("long-line-linear-time")
def _c_long_line(tmp):
    # 구분자 없는 긴 한 줄(base64 덩어리 꼴) — 메일 · 저장소 참조 식이 런 머리에서만 맞춰 보므로 길이에 비례한다. 런 속 자리마다 다시
    #   훑으면 길이의 제곱이라(이 길이에서 식 하나에 몇 초) 커밋 훅이 멈춘다. 상한은 느린 머신의 선형 시간보다 훨씬 넉넉하다
    import time
    start = time.time()
    hits = len(line_hits("A" * 80000, POLICY_DOC, [])) + len(line_hits("a-b_c." * 13000, POLICY_CAPTURE, []))
    took = time.time() - start
    return hits == 0 and took < 2.0, f"적중 {hits} · {took:.2f}초(기대 2초 미만)"


@cell("capture-policy-home-mail-only")
def _c_capture_families(tmp):
    line = " · ".join((H + "alice/x", "a" + "@corp.example", DV + "alice/x", _k("TKT-", "4821"), "PR " + "7531",
                       _k("ABC-", "1234")))
    cap, doc = _ids(line_hits(line, POLICY_CAPTURE, [])), _ids(line_hits(line, POLICY_DOC, []))
    want_doc = ["home", "dev-home", "mail", "placeholder", "key", "pr"]
    return cap == ["home", "mail"] and doc == want_doc, f"캡처 {cap} · 문서 {doc}"


@cell("family-registry-consistent")
def _c_registry(tmp):
    ids = [fid for fid, _, _ in FAMILIES]
    named = set()
    for p in (POLICY_DOC, POLICY_CAPTURE):
        if p.families is not None:
            named |= set(p.families)
    ok = len(ids) == len(set(ids)) and named <= set(ids) and not ({IDENTITY, PRIVATE} & set(ids))
    return ok, f"등록 {ids} · 정책이 고른 {sorted(named)}"


@cell("neg-lowercase-tokens")
def _c_neg_lower(tmp):
    got = line_hits("sha256 · utf8 · rfc3339 · iso8601 · utf-8 · sha-256 · base64 · pep8 · md5", POLICY_DOC, [])
    return got == [], f"적중 {got}"


@cell("existing-synthetic-keys-ok")
def _c_synth_keys(tmp):
    got = [h for ln in SYNTH_KEY_LINES for h in line_hits(ln, POLICY_DOC, [])]
    return got == [], f"합성 값이 걸렸다 {got}"


@cell("band-reserved-ok")
def _c_band_ok(tmp):
    lines = (_k("TKT-", "0123"), _k("tkt", "0456") + "-plan", "plan-" + _k("prj_", "04567"), _k("Ticket-", "012"),
             _k("TKT", "1234") + "를")
    got = [h for ln in lines for h in line_hits(ln, POLICY_DOC, [])]
    return got == [], f"예약 번호가 걸렸다 {got}"


@cell("band-out-of-band-hit")
def _c_band_hit(tmp):
    lines = (_k("TKT-", "4821"), "plan-" + _k("tkt", "4821") + "-holes", _k("PRJ_", "48210"), _k("TKT-", "012345"),
             _k("TKT-", "01"), _k("ticket", "77"))
    got = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in lines]
    return got == [["placeholder"]] * len(lines), f"줄별 적중 {got}"


@cell("band-not-for-other-prefixes")
def _c_band_other(tmp):
    lines = (_k("ABC-", "0123"), _k("ABC-", "1234"))
    got = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in lines]
    return got == [["key"]] * len(lines), f"줄별 적중 {got}"


@cell("pr-number-3digit-floor")
def _c_pr_floor(tmp):
    quiet = ("PR 1 · PR 12 · #3/#5 선례 · #12", "PR " + "#" + "123", "lint " + "#" + "N2", "&" + "#" + "7531;")
    # 세 자리 표본이 하한을 못 박는다 — 네 자리 표본만으로는 하한을 넷으로 올려도 이 셀이 통과한다
    loud = ("PR " + "7531", "PR#" + "7531", "PR " + "#" + "7531", "실측 " + "#" + "7532" + ":", "PR-" + "7531",
            "PR " + "753", "PR#" + "753", "실측 " + "#" + "753" + ":")
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    lo = [len(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    return q == [] and lo == [1] * len(loud), f"통과해야 할 적중 {q} · 줄별 적중 수 {lo}"


@cell("pr-hyphen-reserved-ok")
def _c_pr_hyphen(tmp):
    quiet = [h for ln in ("PR-" + "0123", "PR-" + "123", "PR-" + "04567") for h in line_hits(ln, POLICY_DOC, [])]
    loud = _ids(line_hits("PR-" + "7531", POLICY_DOC, []))
    return quiet == [] and loud == ["pr"], f"예약 번호 적중 {quiet} · 비예약 {loud}"


@cell("selftest-env-drops-parent-git-config")
def _c_env_parent_config(tmp):
    # 부모 git 이 `-c` 로 넘긴 설정이 셀의 git 에 닿지 않는다 — 닿으면 유지관리자 표지 같은 설정이 셀 저장소의 전제를 바꾼다
    root = _repo(tmp, {"a.md": "ok\n"})
    inject = {"GIT_CONFIG_PARAMETERS": "'fz.maintainer=true'", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "fz.maintainer",
              "GIT_CONFIG_VALUE_0": "true"}
    old = {k: os.environ.get(k) for k in inject}
    os.environ.update(inject)
    try:
        p = subprocess.run(["git", "-C", root, "config", "--get", "fz.maintainer"], env=_env(tmp), capture_output=True, text=True)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return p.returncode == 1 and p.stdout.strip() == "", f"rc={p.returncode} 값={p.stdout.strip()!r}"


@cell("mail-content-allow-narrow")
def _c_mail(tmp):
    loud = ("d" + "@corp.example", "e" + "@example.org", "f" + "@mail.example", "g" + "@example.com.evil.io",
            "h" + "@notexample.com")   # 허용 도메인으로 끝나지만 점 경계가 없다
    q = [h for ln in SYNTH_MAIL_LINES for h in line_hits(ln, POLICY_DOC, [])]
    lo = [len(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    cap = [len(line_hits(ln, POLICY_CAPTURE, [])) for ln in SYNTH_MAIL_LINES]
    return (q == [] and lo == [1] * len(loud) and cap == [1] * len(SYNTH_MAIL_LINES)), f"허용 적중 {q} · 밖 {lo} · 캡처 {cap}"


@cell("corp-example-rejected-identity-and-content")
def _c_corp(tmp):
    mail = "dev" + "@corp" + ".example"
    ident = identity_hits("dev", mail, [])
    content = line_hits("Author: dev <" + mail + "> · 태그 주석", POLICY_DOC, [])
    return _ids(ident) == [IDENTITY] and _ids(content) == ["mail"], f"신원 {ident} · 내용 {content}"


@cell("identity-noreply-only")
def _c_identity(tmp):
    ok = [identity_hits("x", "1+u" + IDENTITY_SUFFIX, []), identity_hits("GitHub", IDENTITY_EXACT[0], [])]
    bad = [identity_hits("x", "noreply" + "@example.com", []), identity_hits("x", "", []),
           identity_hits("x", IDENTITY_SUFFIX, [])]
    content = line_hits("noreply" + "@example.com", POLICY_DOC, [])
    return (ok == [[], []] and [len(b) for b in bad] == [1, 1, 1] and content == []), f"통과 {ok} · 거부 {bad} · 내용 {content}"


@cell("private-rules-content-and-identity")
def _c_private(tmp):
    rules = [("비공개 규칙 1", re.compile("(?i)" + "acme"))]
    c = line_hits("Acme 앱 출시", POLICY_DOC, rules)
    i = identity_hits("Acme Bot", "1+u" + IDENTITY_SUFFIX, rules)
    return _ids(c) == [PRIVATE] and _ids(i) == [PRIVATE], f"내용 {c} · 신원 {i}"


@cell("text-file-clean-exit0")
def _c_text_clean(tmp):
    _w(tmp, "n.md", "\n".join(SYNTH_ALL) + "\n")
    rc, out = _cli(tmp, ["--text-file", "n.md"])
    return rc == OK and "LEAK_CLEAN text-file files=1 " in out, f"rc={rc} {out[-300:]}"


@cell("text-file-hit-exit1")
def _c_text_hit(tmp):
    _w(tmp, "t.md", "첫 줄\n작업 " + H + "alice/work\n")
    rc, out = _cli(tmp, ["--text-file", "t.md"])
    return rc == HIT and "t.md:2: 개인 홈 경로" in out, f"rc={rc} {out[-300:]}"


@cell("text-file-missing-exit2")
def _c_text_missing(tmp):
    rc, out = _cli(tmp, ["--text-file", "absent.md"])
    return rc == UNRUN and "UNRUN:" in out, f"rc={rc} {out[-300:]}"


@cell("undecodable-input-exit2")
def _c_undecodable(tmp):
    _w(tmp, "u16.txt", b"\xff\xfe" + "티켓".encode("utf-16-le"))
    _w(tmp, "l1.txt", b"caf\xe9\n")
    got = [_cli(tmp, ["--text-file", f]) for f in ("u16.txt", "l1.txt")]
    return all(rc == UNRUN and "UTF-8" in out for rc, out in got), f"{[(rc, out[-160:]) for rc, out in got]}"


@cell("nul-bytes-exit2")
def _c_nul(tmp):
    _w(tmp, "u16.txt", ("PR " + "7531").encode("utf-16-le"))
    rc, out = _cli(tmp, ["--text-file", "u16.txt"])
    return rc == UNRUN and "NUL" in out, f"rc={rc} {out[-300:]}"


@cell("rules-file-unreadable-exit2")
def _c_rules_unreadable(tmp):
    _w(tmp, "n.md", "깨끗한 본문\n")
    _w(tmp, "bad-enc.txt", b"\xff(?i)x\n")
    absent = os.path.join(tmp, "absent.txt")
    runs = [_cli(tmp, ["--text-file", "n.md", "--rules", "absent.txt"]),
            _cli(tmp, ["--text-file", "n.md", "--rules", tmp]),
            _cli(tmp, ["--text-file", "n.md", "--rules", ""]),
            _cli(tmp, ["--text-file", "n.md", "--rules", "bad-enc.txt"]),
            _cli(tmp, ["--text-file", "n.md"], extra={"FZ_NEUTRALIZE_RULES": absent})]
    return all(rc == UNRUN and "UNRUN:" in out for rc, out in runs), f"{[(rc, out[-120:]) for rc, out in runs]}"


@cell("rules-bad-regex-exit2")
def _c_rules_regex(tmp):
    _w(tmp, "n.md", "깨끗한 본문\n")
    _w(tmp, "r.txt", "# 주석\n(" + "unclosed\n")
    rc, out = _cli(tmp, ["--text-file", "n.md", "--rules", "r.txt"])
    return rc == UNRUN and "정규식 오류" in out, f"rc={rc} {out[-300:]}"


@cell("rules-resolution-order")
def _c_rules_order(tmp):
    _w(tmp, "n.md", "Acme 앱\n")
    rp = _w(tmp, "r.txt", "# 비공개 이름\n(?i)" + "acme\n")
    absent = os.path.join(tmp, "absent.txt")
    got = [_cli(tmp, ["--text-file", "n.md", "--rules", "r.txt"])[0],
           _cli(tmp, ["--text-file", "n.md"], extra={"FZ_NEUTRALIZE_RULES": rp})[0],
           _cli(tmp, ["--text-file", "n.md", "--rules", "r.txt"], extra={"FZ_NEUTRALIZE_RULES": absent})[0],
           _cli(tmp, ["--text-file", "n.md"])[0]]
    return got == [HIT, HIT, HIT, OK], f"--rules · env · --rules 가 env 보다 앞섬 · 규칙 없음 → {got}"


@cell("tree-cwd-repo-synthetic-clean")
def _c_tree_clean(tmp):
    root = _repo(tmp, {"a.md": "\n".join(SYNTH_ALL) + "\n", ".gitignore": "ignored.txt\n", "gone.txt": "지울 파일\n"},
                 {"b/c.txt": "합성 " + H + "example/x\n", "ignored.txt": _k("TKT-", "4821") + "\n"})
    os.remove(os.path.join(root, "gone.txt"))
    rc, out = _cli(tmp, ["--tree"], cwd=root)
    return rc == OK and "LEAK_CLEAN tree:git files=3 " in out, f"rc={rc} {out[-300:]}"


@cell("tree-untracked-file-scanned")
def _c_tree_untracked(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"}, {"u.txt": "둘째 줄에\n" + _k("TKT-", "4821") + "\n"})
    rc, out = _cli(tmp, ["--tree"], cwd=root)
    return rc == HIT and "u.txt:2: 자리표시자 번호" in out, f"rc={rc} {out[-300:]}"


@cell("tree-undecodable-exit2")
def _c_tree_undecodable(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n", "l1.txt": b"caf\xe9\n"})
    rc, out = _cli(tmp, ["--tree"], cwd=root)
    return rc == UNRUN and "l1.txt" in out, f"rc={rc} {out[-300:]}"


@cell("tree-dash-C-and-positional")
def _c_tree_c(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    got = [_cli(tmp, ["-C", root, "--tree"]), _cli(tmp, ["--tree", root]), _cli(tmp, ["--tree", "r"])]
    # tree:git 을 요구한다 — -C 를 버리면 cwd(tmp)를 걸어 tree:walk files=1 로도 0 이 난다
    return all(rc == OK and "tree:git files=1 " in out for rc, out in got), f"{[(rc, out[-120:]) for rc, out in got]}"


@cell("tree-not-a-repo-walks")
def _c_tree_walk(tmp):
    plain = os.path.join(tmp, "plain")
    _w(plain, "d/x.txt", "작업 " + H + "alice/w\n")
    _w(plain, "ok.md", "깨끗\n")
    rc, out = _cli(tmp, ["--tree", "plain"])
    return rc == HIT and "LEAK_HIT tree:walk files=2 " in out, f"rc={rc} {out[-300:]}"


@cell("tree-subdir-of-outer-repo-walks")
def _c_tree_outer(tmp):
    # 바깥 저장소 안의 사본(자기 .git 없음) — 바깥의 무시 규칙이 사본의 파일을 가리면 안 된다. 꼭대기에서는 git 방식 그대로이고,
    #   심볼릭 링크를 거친 꼭대기 경로도 같은 폴더로 읽는다(경로 글자로 견주면 걷기로 떨어져 무시 파일까지 읽는다)
    root = _repo(tmp, {"a.md": "깨끗\n", ".gitignore": "*.log\n"},
                 {"export/ok.md": "깨끗\n", "export/run.log": "작업 " + H + "alice/w\n"})
    link = os.path.join(tmp, "lnk")
    os.symlink(root, link)
    sub, top, via = _cli(tmp, ["--tree", os.path.join(root, "export")]), _cli(tmp, ["--tree", root]), _cli(tmp, ["--tree", link])
    ok = (sub[0] == HIT and "LEAK_HIT tree:walk files=2 " in sub[1] and "run.log:1: 개인 홈 경로" in sub[1]
          and all(rc == OK and "LEAK_CLEAN tree:git files=3 " in out for rc, out in (top, via)))
    return ok, f"하위 폴더 rc={sub[0]} {sub[1][-200:]} · 꼭대기 rc={top[0]} {top[1][-120:]} · 링크 rc={via[0]} {via[1][-120:]}"


@cell("tree-empty-exit2")
def _c_tree_empty(tmp):
    root = _repo(tmp, {})
    rc, out = _cli(tmp, ["--tree"], cwd=root)
    return rc == UNRUN and "0개" in out, f"rc={rc} {out[-300:]}"


@cell("range-added-lines-only")
def _c_range_added(tmp):
    root = _repo(tmp, {"a.md": "기준 " + H + "alice/w\n둘째\n"})
    _commit_all(tmp, root, "base")
    # 기준에 있던 줄은 세지 않는다. 내용이 `++` 로 시작하는 추가 줄은 diff 에서 `+++ …` 다 — 상태 없이 `+++ ` 를 머리로 읽는
    #   파서는 이 줄을 경로로 바꿔 놓친다
    _w(root, "a.md", "기준 " + H + "alice/w\n둘째\n" + "++ " + H + "bob/x\n")
    rc, out = _cli(tmp, ["--range", "HEAD"], cwd=root)
    ok = rc == HIT and "a.md:3: 개인 홈 경로" in out and "a.md:1:" not in out and " hits=1" in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("range-untracked-file-scanned")
def _c_range_untracked(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "n/u.md", "첫 줄\n" + "a" + "@corp.example\n")
    rc, out = _cli(tmp, ["--range", "HEAD"], cwd=root)
    return rc == HIT and "n/u.md:2: 메일 주소" in out, f"rc={rc} {out[-300:]}"


@cell("rename-with-residual")
def _c_rename_residual(tmp):
    root = _repo(tmp, {"old.md": RENAME_BODY})
    base = _commit_all(tmp, root, "base")
    _tgit(tmp, root, "mv", "old.md", "new.md")
    _commit_all(tmp, root, "rename")
    got = [_cli(tmp, ["--range", base], cwd=root), _cli(tmp, ["--range", base + "..HEAD"], cwd=root)]
    return all(rc == HIT and "new.md:11: 개인 홈 경로" in out for rc, out in got), f"{[(rc, out[-160:]) for rc, out in got]}"


@cell("range-commit-pair")
def _c_range_pair(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n" + _k("TKT-", "4821") + "\n")
    head = _commit_all(tmp, root, "add")
    # 두 커밋 사이 범위는 작업 트리 · 미추적 파일을 보지 않는다
    _w(root, "a.md", "깨끗\n" + _k("TKT-", "4821") + "\n작업 트리만 " + H + "bob/w\n")
    _w(root, "u.md", "미추적 " + H + "alice/w\n")
    rc, out = _cli(tmp, ["--range", base + ".." + head], cwd=root)
    ok = rc == HIT and "a.md:2: 자리표시자 번호" in out and " hits=1" in out and "u.md" not in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("staged-index-not-worktree")
def _c_staged_index(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n", "b.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n색인 " + H + "alice/w\n")
    _tgit(tmp, root, "add", "a.md")
    _w(root, "a.md", "깨끗\n")                                    # 작업 트리에서는 지웠다 — 인덱스에만 남는다
    _w(root, "b.md", "깨끗\n작업 트리만 " + H + "bob/w\n")        # 스테이징하지 않았다
    _w(root, "u.md", "미추적 " + H + "carol/w\n")
    rc, out = _cli(tmp, ["--staged"], cwd=root)
    ok = rc == HIT and "a.md:2: 개인 홈 경로" in out and " hits=1" in out and "b.md" not in out and "u.md" not in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("staged-rename-paired-ok")
def _c_staged_rename(tmp):
    root = _repo(tmp, {"old.md": RENAME_BODY})
    _commit_all(tmp, root, "base")
    _tgit(tmp, root, "mv", "old.md", "new.md")
    _w(root, "new.md", RENAME_BODY + "깨끗한 새 줄\n")
    _tgit(tmp, root, "add", "new.md")
    quiet = _cli(tmp, ["--staged"], cwd=root)
    _w(root, "new.md", RENAME_BODY + "새 줄 " + H + "bob/w\n")
    _tgit(tmp, root, "add", "new.md")
    loud = _cli(tmp, ["--staged"], cwd=root)
    ok = quiet[0] == OK and loud[0] == HIT and "new.md:12: 개인 홈 경로" in loud[1] and "alice" not in loud[1]
    return ok, f"개명+깨끗한 줄 rc={quiet[0]} · 개명+적중 줄 rc={loud[0]} {loud[1][-200:]}"


@cell("git-binary-exit2")
def _c_git_binary(tmp):
    # 스테이징 축도 2 다 — 인덱스의 바이너리 추가는 텍스트 규칙으로 잴 수 없고, 0 은 잰 뒤에만 낸다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "b.bin", b"\x00\x01\x02bin\x00")
    _tgit(tmp, root, "add", "b.bin")
    got = [_cli(tmp, ["--range", "HEAD"], cwd=root), _cli(tmp, ["--staged"], cwd=root)]
    return all(rc == UNRUN and "바이너리" in out and "b.bin" in out for rc, out in got), f"{[(rc, out[-160:]) for rc, out in got]}"


@cell("git-undecodable-line-exit2")
def _c_git_undecodable(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n".encode("utf-8") + b"caf\xe9\n")
    _tgit(tmp, root, "add", "a.md")
    got = [_cli(tmp, ["--range", "HEAD"], cwd=root), _cli(tmp, ["--staged"], cwd=root)]
    return all(rc == UNRUN and "UTF-8" in out and "a.md:2" in out for rc, out in got), f"{[(rc, out[-160:]) for rc, out in got]}"


@cell("git-axis-unresolvable-exit2")
def _c_git_unresolvable(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    plain = os.path.join(tmp, "plain")
    os.makedirs(plain)
    runs = [_cli(tmp, ["--range", "no-such-ref"], cwd=root), _cli(tmp, ["--range", "HEAD...HEAD"], cwd=root),
            _cli(tmp, ["--range=-x"], cwd=root), _cli(tmp, ["--range", "HEAD"], cwd=plain), _cli(tmp, ["--staged"], cwd=plain)]
    return all(rc == UNRUN and "UNRUN:" in out for rc, out in runs), f"{[(rc, out[-120:]) for rc, out in runs]}"


@cell("non-utf8-path-shown-exit2")
def _c_non_utf8_path(tmp):
    # argv · git 출력의 UTF-8 밖 바이트는 surrogateescape 로 풀린다. 그대로 print 하면 UTF-8 strict stdout 에서 죽어 exit 1(적중)로
    #   읽힌다 — 판정 불가(2) · 사유 줄 · 끝 줄이 그대로 나와야 한다
    rc, out = _cli(tmp, ["--text-file", "caf" + chr(0xDCE9) + ".md"])
    shown = "UNRUN: 읽지 못했다: caf" + chr(92) + "xe9.md"
    return rc == UNRUN and shown in out and "LEAK_UNRUN text-file" in out, f"rc={rc} {out[-300:]}"


@cell("commits-corp-identity-exit1")
def _c_commits_identity(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    c1 = _commit_all(tmp, root, "author", extra={"GIT_AUTHOR_EMAIL": _CORP})
    _w(root, "c.md", "깨끗\n")
    c2 = _commit_all(tmp, root, "committer", extra={"GIT_COMMITTER_EMAIL": _CORP})
    rc, out = _cli(tmp, ["--commits", base + "..HEAD"], cwd=root)
    ok = (rc == HIT and f"신원 {_short(c1)} author: 신원 메일" in out and f"신원 {_short(c2)} committer: 신원 메일" in out
          and " hits=2" in out)
    return ok, f"rc={rc} {out[-400:]}"


@cell("commits-intermediate-line-exit1")
def _c_commits_intermediate(tmp):
    # 범위의 두 끝만 비교하면(--range A..B) 중간 커밋에서 더했다가 지운 줄이 보이지 않는다 — 커밋마다 축은 그 커밋에서 잡는다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n중간 " + H + "alice/w\n")
    mid = _commit_all(tmp, root, "add")
    _w(root, "a.md", "깨끗\n")
    _commit_all(tmp, root, "drop")
    per, ends = _cli(tmp, ["--commits", base + "..HEAD"], cwd=root), _cli(tmp, ["--range", base + "..HEAD"], cwd=root)
    ok = per[0] == HIT and f"추가 줄 {_short(mid)} a.md:2: 개인 홈 경로" in per[1] and " hits=1" in per[1] and ends[0] == OK
    return ok, f"커밋마다 rc={per[0]} {per[1][-300:]} · 두 끝 rc={ends[0]}"


@cell("commits-message-exit1")
def _c_commits_message(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    sha = _commit_all(tmp, root, "제목\n\n본문 " + _k("ABC-", "1234"))
    rc, out = _cli(tmp, ["--commits", base + "..HEAD"], cwd=root)
    ok = rc == HIT and f"메시지 {_short(sha)}:3: 티켓 키 꼴" in out and " hits=1" in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("tag-annotated-tagger-exit1")
def _c_tag_tagger(tmp):
    # 태그만 미는 경우 — 커밋 범위가 비어도 tagger 를 본다(tagger 는 committer 값으로 찍힌다). 다른 태그가 풀리지 않아도 이 태그의
    #   적중은 함께 나온다(exit 는 2 — 미판정이 위반보다 앞선다)
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _tgit(tmp, root, "tag", "-a", "v1", "-m", "릴리스", extra={"GIT_COMMITTER_EMAIL": _CORP})
    rc, out = _cli(tmp, ["--commits", base + "..HEAD", "--tag", "v1"], cwd=root)
    mixed = _cli(tmp, ["--commits", base + "..HEAD", "--tag", "no-such-tag", "--tag", "v1"], cwd=root)
    ok = (rc == HIT and "tagger v1: 신원 메일" in out and " hits=1" in out and "commits=0 annotated=1 " in out
          and mixed[0] == UNRUN and "tagger v1: 신원 메일" in mixed[1] and "no-such-tag" in mixed[1])
    return ok, f"rc={rc} {out[-300:]} · 섞임 rc={mixed[0]} {mixed[1][-300:]}"


@cell("tag-annotation-body-exit1")
def _c_tag_body(tmp):
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _tgit(tmp, root, "tag", "-a", "v2", "-m", "주석 첫 줄\n\n문의 " + "a" + "@corp.example")
    rc, out = _cli(tmp, ["--commits", base + "..HEAD", "--tag", "refs/tags/v2"], cwd=root)
    ok = rc == HIT and "주석 refs/tags/v2:3: 메일 주소" in out and " hits=1" in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("tag-lightweight-range-only")
def _c_tag_lightweight(tmp):
    # 가벼운 태그는 tagger · 주석 칸이 없다 — 빈 값을 위반으로도 통과 증거로도 읽지 않는다: 범위가 깨끗하면 0, 더러우면 1
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    _commit_all(tmp, root, "clean")
    _tgit(tmp, root, "tag", "v3")
    quiet = _cli(tmp, ["--commits", base + "..HEAD", "--tag", "v3"], cwd=root)
    _w(root, "c.md", "작업 " + H + "bob/w\n")
    _commit_all(tmp, root, "dirty")
    _tgit(tmp, root, "tag", "-f", "v3")
    loud = _cli(tmp, ["--commits", base + "..HEAD", "--tag", "v3"], cwd=root)
    ok = (quiet[0] == OK and "commits=1 annotated=0 lightweight=1 " in quiet[1]
          and loud[0] == HIT and "c.md:1: 개인 홈 경로" in loud[1] and " hits=1" in loud[1])
    return ok, f"깨끗 rc={quiet[0]} {quiet[1][-200:]} · 더러움 rc={loud[0]} {loud[1][-200:]}"


@cell("commits-merge-first-parent-exit1")
def _c_commits_merge(tmp):
    # 옆 가지 커밋이 범위 밖이어도(A..B 의 A 에서 닿는다) 병합이 들여온 줄은 첫 부모 대비 병합 커밋의 추가 줄이다 —
    #   두 번째 부모 · 결합 diff 대비로 보면 이 줄이 빠진다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    trunk = _tgit(tmp, root, "symbolic-ref", "--short", "HEAD").strip()
    _tgit(tmp, root, "branch", "side")
    _w(root, "c.md", "깨끗\n")
    _commit_all(tmp, root, "trunk")
    _tgit(tmp, root, "checkout", "-q", "side")
    _w(root, "s.md", "옆 " + H + "alice/w\n")
    side = _commit_all(tmp, root, "side")
    _tgit(tmp, root, "checkout", "-q", trunk)
    _tgit(tmp, root, "merge", "--no-ff", "--no-edit", "-q", "-m", "merge", "side")
    merge = _tgit(tmp, root, "rev-parse", "HEAD").strip()
    rc, out = _cli(tmp, ["--commits", side + "..HEAD"], cwd=root)
    ok = rc == HIT and f"추가 줄 {_short(merge)} s.md:1: 개인 홈 경로" in out and " hits=1" in out and "commits=2 " in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("commits-root-vs-empty-tree-exit1")
def _c_commits_root(tmp):
    root = _repo(tmp, {"a.md": "첫 줄\n루트 " + H + "alice/w\n"})
    sha = _commit_all(tmp, root, "root")
    rc, out = _cli(tmp, ["--commits", "HEAD"], cwd=root)
    ok = rc == HIT and f"추가 줄 {_short(sha)} a.md:2: 개인 홈 경로" in out and "commits=1 " in out
    return ok, f"rc={rc} {out[-300:]}"


@cell("commits-undecodable-added-exit2")
def _c_commits_undecodable(tmp):
    # UTF-8 이 아닌 텍스트(latin-1)는 줄 디코드에서, UTF-16 은 git 이 바이너리로 봐서 — 둘 다 건너뛰지 않고 2 다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "l1.txt", b"caf\xe9\n")
    _w(root, "u16.txt", ("PR " + "7531").encode("utf-16-le"))
    _commit_all(tmp, root, "encodings")
    rc, out = _cli(tmp, ["--commits", base + "..HEAD"], cwd=root)
    ok = rc == UNRUN and "UTF-8" in out and "l1.txt" in out and "바이너리" in out and "u16.txt" in out
    return ok, f"rc={rc} {out[-400:]}"


@cell("commits-hit-and-unrun-exit2")
def _c_commits_mixed(tmp):
    # 미판정이 위반보다 앞선다 — 적중 줄은 그대로 내고 exit 는 2 다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n작업 " + H + "alice/w\n")
    leak = _commit_all(tmp, root, "leak")
    _w(root, "l1.txt", b"caf\xe9\n")
    _commit_all(tmp, root, "latin1")
    rc, out = _cli(tmp, ["--commits", base + "..HEAD"], cwd=root)
    ok = (rc == UNRUN and f"추가 줄 {_short(leak)} a.md:2: 개인 홈 경로" in out and "LEAK_UNRUN commits:" in out
          and " hits=1" in out)
    return ok, f"rc={rc} {out[-400:]}"


@cell("commits-clean-range-exit0")
def _c_commits_clean(tmp):
    root = _repo(tmp, {"a.md": "\n".join(SYNTH_ALL) + "\n"})
    base = _commit_all(tmp, root, "합성 값 " + SYNTH_KEY_LINES[0])
    _w(root, "b.md", "\n".join(SYNTH_ALL) + "\n")
    _commit_all(tmp, root, "합성 메일 " + SYNTH_MAIL_LINES[0])
    _tgit(tmp, root, "tag", "-a", "v1", "-m", "합성 " + SYNTH_HOME_LINES[0])
    got = [_cli(tmp, ["--commits", base + "..HEAD", "--tag", "v1"], cwd=root), _cli(tmp, ["--commits", "HEAD"], cwd=root)]
    ok = (got[0][0] == OK and "LEAK_CLEAN commits:" in got[0][1] and "commits=1 annotated=1 " in got[0][1]
          and got[1][0] == OK and "commits=2 " in got[1][1])
    return ok, f"{[(rc, out[-200:]) for rc, out in got]}"


@cell("commits-unresolvable-exit2")
def _c_commits_unresolvable(tmp):
    # 판정 불가로 일찍 끝나도 끝 줄은 같은 꼴이다(못 잰 수는 0) — 끝 줄에서 필드를 읽는 쪽이 경로마다 갈리지 않게
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "t.txt", "트리\n")
    _tgit(tmp, root, "tag", "blobtag", _tgit(tmp, root, "hash-object", "-w", "t.txt").strip())
    plain = os.path.join(tmp, "plain")
    os.makedirs(plain)
    runs = [_cli(tmp, ["--commits", "no-such-ref"], cwd=root), _cli(tmp, ["--commits", "HEAD...HEAD"], cwd=root),
            _cli(tmp, ["--commits", "HEAD", "--exclude", "no-such-ref"], cwd=root),
            _cli(tmp, ["--commits", "HEAD", "--tag", "no-such-tag"], cwd=root),
            _cli(tmp, ["--commits", "HEAD", "--tag", "blobtag"], cwd=root),
            _cli(tmp, ["--commits", "HEAD"], cwd=plain), _cli(tmp, ["--tree", "--tag", "v1"], cwd=root)]
    tail = "LEAK_UNRUN commits:no-such-ref commits=0 annotated=0 lightweight=0 files=0 "
    ok = all(rc == UNRUN and "UNRUN:" in out for rc, out in runs) and tail in runs[0][1]
    return ok, f"{[(rc, out[-120:]) for rc, out in runs]}"


@cell("commits-with-tree-full-text")
def _c_commits_with_tree(tmp):
    # 기준 없는 첫 출하 — 커밋에 들지 않은 공개 후보(미추적 파일)는 --with-tree 가 본다. 읽지 못하는 미추적 파일은 2 다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "root")
    _w(root, "n/u.md", "첫 줄\n미추적 " + H + "alice/w\n")
    bare = _cli(tmp, ["--commits", "HEAD"], cwd=root)
    full = _cli(tmp, ["--commits", "HEAD", "--with-tree"], cwd=root)
    _w(root, "n/l1.txt", b"caf\xe9\n")
    bad = _cli(tmp, ["--commits", "HEAD", "--with-tree"], cwd=root)
    ok = (bare[0] == OK and full[0] == HIT and "전문 n/u.md:2: 개인 홈 경로" in full[1] and " with-tree " in full[1]
          and bad[0] == UNRUN and "n/l1.txt" in bad[1])
    return ok, f"rc {bare[0]} · {full[0]} {full[1][-200:]} · {bad[0]} {bad[1][-200:]}"


@cell("commits-exclude-tips")
def _c_commits_exclude(tmp):
    # push 훅이 넘기는 원격 tip — 뺄 끝마다 그 끝에서 닿는 커밋이 빠지고, 여러 개를 함께 받는다
    root = _repo(tmp, {"a.md": "루트 " + H + "alice/w\n"})
    r0 = _commit_all(tmp, root, "root")
    _w(root, "b.md", "다음 " + H + "bob/w\n")
    c1 = _commit_all(tmp, root, "c1")
    _w(root, "c.md", "깨끗\n")
    _commit_all(tmp, root, "c2")
    got = [_cli(tmp, ["--commits", "HEAD"], cwd=root), _cli(tmp, ["--commits", "HEAD", "--exclude", r0], cwd=root),
           _cli(tmp, ["--commits", "HEAD", "--exclude", r0, "--exclude", c1], cwd=root)]
    ok = ([rc for rc, _ in got] == [HIT, HIT, OK] and " hits=2" in got[0][1] and " hits=1" in got[1][1]
          and "commits=1 " in got[2][1])
    return ok, f"{[(rc, out[-160:]) for rc, out in got]}"


@cell("key-fz-namespaces-ok")
def _c_key_namespaces(tmp):
    # 플러그인 자신의 지적 id 접두(KEY_RESERVED_ONLY)는 예약 번호일 때만, 트리의 합성 키 · 공개 벤치마크 이름(SYNTHETIC_KEYS)은 그 토큰일
    #   때만 통과한다. 같은 접두의 대역 밖 번호 · 같은 접두의 다른 번호 · 그 밖의 대문자 접두(이름공간과 한 글자 다른 것 포함)는 적중이다.
    #   자리표시자 접두가 통과 이름공간에 들면 번호와 무관하게 통과한다 — 교집합 0 을 실행으로 단언한다
    quiet = (_k("ARCH-", "001") + " · " + _k("CODE-", "003"), "예: " + _k("REV-", "001") + " · " + _k("VER-", "001"),
             "C:" + _k("GPT-", "001"), _k("FZ-", "142") + " 는 매치", _k("AIME-", "2025") + " 는 +12%")
    out_of_band = (_k("ARCH-", "4821"), _k("CODE-", "417"), _k("REV-", "2001"), _k("VER-", "512"), _k("GPT-", "1001"))
    other_token = (_k("FZ-", "143"), _k("AIME-", "2024"))
    loud = ((_k("ABC-", "1234"), _k("ARC-", "001"), _k("FZZ-", "142"), _k("GPTX-", "001"), _k("AIM-", "2025"))
            + out_of_band + other_token)
    q = [h for ln in quiet for h in line_hits(ln, POLICY_DOC, [])]
    lo = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in loud]
    clash = KEY_OK & {p.upper() for p in PLACEHOLDER_PREFIXES}
    ok = q == [] and lo == [["key"]] * len(loud) and not clash
    return ok, f"통과해야 할 적중 {q} · 줄별 적중 {lo} · 통과 이름공간에 든 자리표시자 접두 {sorted(clash)}"


@cell("home-dotfolder-not-account")
def _c_home_dotfolder(tmp):
    # 임시 HOME 아래 설정 폴더(점으로 시작)는 계정이 아니다 — 두 정책 모두. 진짜 계정 아래의 점폴더와 `.` 마디는 그대로 적중한다
    quiet = ("$T" + HM + ".codex/auth.json", "$T" + HM + ".fz/gpt-choice/s", "cp " + H + ".config/a")
    loud = (H + "alice/.codex/x", HM + "bob/.fz/y", H + "./alice/x")
    q = [(p.name, h) for ln in quiet for p in (POLICY_DOC, POLICY_CAPTURE) for h in line_hits(ln, p, [])]
    lo = [[_ids(line_hits(ln, p, [])) for p in (POLICY_DOC, POLICY_CAPTURE)] for ln in loud]
    return q == [] and lo == [[["home"], ["home"]]] * len(loud), f"통과해야 할 적중 {q} · 줄별 적중 {lo}"


@cell("commits-object-headers-mergetag-exit1")
def _c_commits_headers(tmp):
    # 커밋 객체의 다른 머리도 공개된다 — 서명 태그를 병합하면 mergetag 머리에 태그 객체가 통째로 박히고(tagger · 주석), 서명
    #   머리(gpgsig)의 갑옷에도 머리줄이 있다. git 은 서명할 때만 이 머리를 남겨 셀은 커밋 객체를 직접 짓는다(서명 키 없이)
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    _commit_all(tmp, root, "next")
    head, _, msg = _tgit(tmp, root, "cat-file", "commit", "HEAD").partition("\n\n")
    tag = ("object " + base, "type commit", "tag v9", "tagger t <" + _CORP + "> 1700000000 +0000", "", "주석 첫 줄",
           "문의 " + "b" + "@corp.example")
    sig = ("fake-signature", "Comment: " + "c" + "@corp.example", "", "AAAA")
    body = head + "\nmergetag " + "\n ".join(tag) + "\ngpgsig " + "\n ".join(sig) + "\n\n" + msg
    sha = _tgit(tmp, root, "hash-object", "-t", "commit", "-w", _w(tmp, "obj.txt", body)).strip()
    s = _short(sha)
    rc, out = _cli(tmp, ["--commits", base + ".." + sha], cwd=root)
    ok = (rc == HIT and f"tagger mergetag {s}: 신원 메일" in out and f"주석 mergetag {s}:2: 메일 주소" in out
          and f"머리 {s} gpgsig:2: 메일 주소" in out and " hits=3" in out and "commits=1 " in out)
    return ok, f"rc={rc} {out[-500:]}"


@cell("hook-policy-maintainer-no-rules-exit2")
def _c_hook_maintainer(tmp):
    # 유지관리자 머신에서 비공개 규칙 없이 낸 0 은 통과 증거가 아니다 — 표지가 참이고 규칙이 없으면 내용이 깨끗해도 판정 불가다.
    #   참 거짓으로 읽히지 않는 표지도 판정 불가다 — 읽지 못한 표지를 '표지 없음' 으로 읽으면 같은 0 이 난다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n둘째\n")
    _tgit(tmp, root, "add", "a.md")
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "true")
    on = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "maybe")
    bad = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    ok = (on[0] == UNRUN and "유지관리자 표지가 있는데 비공개 규칙 파일이 없다" in on[1]
          and bad[0] == UNRUN and f"git 설정 {HOOK_MAINTAINER_KEY} 를 읽지 못했다" in bad[1])
    return ok, f"표지 참 rc={on[0]} {on[1][-200:]} · 표지 maybe rc={bad[0]} {bad[1][-200:]}"


@cell("hook-policy-maintainer-empty-rules-exit2")
def _c_hook_empty_rules(tmp):
    # 잘리거나(0바이트) 주석만 남은 규칙 파일 — 유지관리자 머신에서 규칙 0개로 낸 0 은 통과 증거가 아니다(출처 셋 모두). 표지가 없으면
    #   (공개 기여자) 그대로 0 이고, 훅 정책이 아니면 빈 파일은 '내장 규칙만' 이다(출하 게이트의 계약)
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\n둘째\n")
    _tgit(tmp, root, "add", "a.md")
    empty, comment = _w(tmp, "empty.txt", ""), _w(tmp, "comment.txt", "# 주석뿐\n\n")
    _tgit(tmp, root, "config", HOOK_RULES_KEY, empty)
    no_marker = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "true")
    by_cfg = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    by_env = _cli(tmp, ["--staged", "--hook-policy"], cwd=root, extra={"FZ_NEUTRALIZE_RULES": comment})
    by_flag = _cli(tmp, ["--staged", "--hook-policy", "--rules", empty], cwd=root)
    plain = _cli(tmp, ["--staged", "--rules", empty], cwd=root)
    msg = "유지관리자 표지가 있는데 비공개 규칙이 0개다"
    ok = (no_marker[0] == OK and "rules=0(git 설정" in no_marker[1]
          and all(rc == UNRUN and msg in out for rc, out in (by_cfg, by_env, by_flag))
          and plain[0] == OK and "rules=0(--rules)" in plain[1])
    return ok, f"{[(rc, out[-140:]) for rc, out in (no_marker, by_cfg, by_env, by_flag, plain)]}"


@cell("hook-policy-no-marker-builtin-only")
def _c_hook_builtin(tmp):
    # 표지가 없거나 거짓이면(공개 기여자) 내장 규칙만 본다 — 비공개 이름은 지나가고 내장 계열은 그대로 적중하며 안내 한 줄이 나온다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\nAcme 앱\n작업 " + H + "alice/w\n")
    _tgit(tmp, root, "add", "a.md")
    unset = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "false")
    off = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    ok = all(rc == HIT and "a.md:3: 개인 홈 경로" in out and " hits=1" in out and "rules=0(없음)" in out and "NOTE: " in out
             for rc, out in (unset, off))
    return ok, f"표지 없음 rc={unset[0]} {unset[1][-200:]} · 표지 거짓 rc={off[0]} {off[1][-200:]}"


@cell("hook-policy-git-config-rules")
def _c_hook_config_rules(tmp):
    # git 설정의 규칙 경로가 쓰인다(절대 경로 · base 기준 상대 경로) · 순서는 --rules > env > git 설정 · 경로를 줬는데 읽지 못하면
    #   표지와 무관하게 판정 불가다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    rp = _w(tmp, "r.txt", "# 비공개 이름\n(?i)" + "acme\n")
    _w(root, "a.md", "깨끗\nAcme 앱\n")
    _tgit(tmp, root, "add", "a.md")
    _tgit(tmp, root, "config", HOOK_RULES_KEY, rp)
    used = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_RULES_KEY, os.path.join("..", "r.txt"))
    relative = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_RULES_KEY, os.path.join(tmp, "absent.txt"))
    unreadable = _cli(tmp, ["--staged", "--hook-policy"], cwd=root)
    by_flag = _cli(tmp, ["--staged", "--hook-policy", "--rules", rp], cwd=root)
    by_env = _cli(tmp, ["--staged", "--hook-policy"], cwd=root, extra={"FZ_NEUTRALIZE_RULES": rp})
    src = f"(git 설정 {HOOK_RULES_KEY})"
    ok = (used[0] == HIT and "a.md:2: 비공개 규칙" in used[1] and src in used[1] and relative[0] == HIT and src in relative[1]
          and unreadable[0] == UNRUN and "비공개 규칙 파일을 읽지 못했다" in unreadable[1]
          and by_flag[0] == HIT and "(--rules)" in by_flag[1] and by_env[0] == HIT and "(FZ_NEUTRALIZE_RULES)" in by_env[1])
    return ok, f"{[(rc, out[-120:]) for rc, out in (used, relative, unreadable, by_flag, by_env)]}"


@cell("no-hook-policy-ignores-git-config")
def _c_no_hook_policy(tmp):
    # 플래그 없이 부르는 호출(출하 게이트 · 범위 축)은 git 설정을 읽지 않는다 — 표지가 참이고 규칙 경로가 읽히지 않아도 내장 규칙만 본다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, "a.md", "깨끗\nAcme 앱\n")
    _tgit(tmp, root, "add", "a.md")
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "true")
    _tgit(tmp, root, "config", HOOK_RULES_KEY, os.path.join(tmp, "absent.txt"))
    rc, out = _cli(tmp, ["--staged"], cwd=root)
    return rc == OK and "LEAK_CLEAN staged files=1 rules=0(없음)" in out and "NOTE: " not in out, f"rc={rc} {out[-300:]}"


@cell("hook-policy-identity-maintainer-only")
def _c_hook_identity(tmp):
    # 커밋마다 축의 신원 메일 규칙(noreply 만 통과)은 훅 정책에서 유지관리자 표지가 참일 때만 켠다(push 훅 — 공개 기여자의 개인 메일은
    #   막지 않는다). 표지가 참이 아니어도 추가 줄과 비공개 규칙(신원 칸 포함)은 본다. 훅 정책이 아닌 호출(출하 게이트)은 표지와 무관하게
    #   언제나 엄격하다 · 참 거짓으로 읽히지 않는 표지는 판정 불가다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    sha = _commit_all(tmp, root, "회사 신원", extra={"GIT_AUTHOR_EMAIL": _CORP})
    _tgit(tmp, root, "tag", "-a", "v1", "-m", "릴리스", extra={"GIT_COMMITTER_EMAIL": _CORP})
    args = ["--commits", base + "..HEAD", "--tag", "v1"]
    lax, strict = _cli(tmp, args + ["--hook-policy"], cwd=root), _cli(tmp, args, cwd=root)
    _tgit(tmp, root, "config", HOOK_RULES_KEY, _w(tmp, "r.txt", "# 비공개 이름\n(?i)corp\n"))
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "true")
    on = _cli(tmp, args + ["--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "maybe")
    bad = _cli(tmp, args + ["--hook-policy"], cwd=root)
    _tgit(tmp, root, "config", HOOK_MAINTAINER_KEY, "false")
    _w(root, "c.md", "작업 " + H + "alice/w\n")
    _commit_all(tmp, root, "dirty")
    rest = _cli(tmp, args + ["--hook-policy"], cwd=root)
    s, off = _short(sha), "신원 메일 규칙(noreply 만 통과)을 보지 않는다"
    mail, private = (f"신원 {s} author: 신원 메일", "tagger v1: 신원 메일"), (f"신원 {s} author: 비공개 규칙", "tagger v1: 비공개 규칙")
    ok = (lax[0] == OK and off in lax[1] and "commits=1 annotated=1 " in lax[1]
          and strict[0] == HIT and all(x in strict[1] for x in mail) and " hits=2" in strict[1] and off not in strict[1]
          and on[0] == HIT and all(x in on[1] for x in mail + private) and " hits=4" in on[1] and off not in on[1]
          and bad[0] == UNRUN and f"git 설정 {HOOK_MAINTAINER_KEY} 를 읽지 못했다" in bad[1]
          and rest[0] == HIT and off in rest[1] and all(x in rest[1] for x in private) and "c.md:1: 개인 홈 경로" in rest[1]
          and " hits=3" in rest[1] and not any(x in rest[1] for x in mail))
    return ok, f"{[(rc, out[-160:]) for rc, out in (lax, strict, on, bad, rest)]}"


@cell("identity-mail-cli")
def _c_identity_mail(tmp):
    # 커밋 객체 밖 신원 판정의 진입점(격리 clone 스크립트가 메일 정규식 사본 없이 부른다) — 메일은 noreply 만 통과 · 회사 꼴 · 빈 값은
    #   적중 · 비공개 규칙은 메일 · 이름 칸에 건다(noreply 꼴이어도 · 훅 정책이면 -C 저장소의 git 설정 규칙 파일) · 이름은 메일과 함께만
    #   받고, 다른 모드의 함께 받는 옵션을 주면 판정 불가다
    noreply = "--identity-mail=" + "1+u" + IDENTITY_SUFFIX
    ok = _cli(tmp, [noreply])
    corp = _cli(tmp, ["--identity-mail=" + _CORP])
    empty = _cli(tmp, ["--identity-mail="])
    rp = _w(tmp, "r.txt", "# 비공개 이름\n(?i)" + "acme\n")
    private = _cli(tmp, ["--identity-mail=" + "1+acme" + IDENTITY_SUFFIX, "--rules", rp])
    root = _repo(tmp, {})
    _tgit(tmp, root, "config", HOOK_RULES_KEY, rp)
    named = _cli(tmp, [noreply, "--identity-name=Acme Bot", "--hook-policy"], cwd=root)
    lone = _cli(tmp, ["--identity-name=x", "--tree"])
    mixed = _cli(tmp, [noreply, "--tag", "v1"])
    res = (ok[0] == OK and "LEAK_CLEAN identity-mail files=1 rules=0(없음)" in ok[1]
           and corp[0] == HIT and "  ❌ 신원: 신원 메일 — " + _CORP in corp[1] and "LEAK_HIT identity-mail files=1 " in corp[1]
           and empty[0] == HIT and "  ❌ 신원: 신원 메일 — (빈 값)" in empty[1]
           and private[0] == HIT and "  ❌ 신원: 비공개 규칙 2 — acme" in private[1] and "rules=1(--rules)" in private[1]
           and "신원 메일 —" not in private[1]
           and named[0] == HIT and "  ❌ 신원: 비공개 규칙 2 — Acme" in named[1] and f"rules=1(git 설정 {HOOK_RULES_KEY}) hits=1" in named[1]
           and lone[0] == UNRUN and "--identity-name" in lone[1] and mixed[0] == UNRUN)
    return res, f"{[(rc, out[-160:]) for rc, out in (ok, corp, empty, private, named, lone, mixed)]}"


@cell("release-body-unreadable-exit2")
def _c_release_body_unreadable(tmp):
    # 발행된 본문을 읽지 못하면 판정 불가(2)다 — gh 부재(PATH 를 빈 폴더로 좁힌다 · gh 가 깔린 머신에서도 부재)와 `-` 로 시작하는
    #   태그(gh 가 옵션으로 읽는다 — gh 를 찾기 전에 끝낸다). 가짜 gh 로 보는 판정(깨끗 · 적중 · gh 실패 · JSON 아님 · 빈 본문)은
    #   tests/fixtures/leak-gates/release-body 러너가 돈다
    bare = os.path.join(tmp, "bin")
    os.makedirs(bare)
    gone = _cli(tmp, ["--release-body", "v1.0.0"], extra={"PATH": bare})
    dash = _cli(tmp, ["--release-body=-x"], extra={"PATH": bare})
    ok = (gone[0] == UNRUN and "UNRUN: gh 가 없다" in gone[1] and "LEAK_UNRUN release-body:v1.0.0 files=0 " in gone[1]
          and dash[0] == UNRUN and "태그가 비었거나 '-' 로 시작한다" in dash[1] and "gh 가 없다" not in dash[1])
    return ok, f"{[(rc, out[-160:]) for rc, out in (gone, dash)]}"


@cell("run-id-synthetic-list-ok")
def _c_run_id_synthetic(tmp):
    # 합성 목록 — 0 채움 16개와 등재한 반복 글자 넷을 따로 센다(등재가 조용히 늘지 않게) · 모두 전체 꼴(접미사 없는 꼴은 목록에 두지
    #   않는다) · 문서 정책 · 캡처 ID 대조 모두 적중 0(한 줄에 모아도 · 경로 · JSON 값 안이어도)
    ids = sorted(SYNTHETIC_RUN_IDS)
    zero = [x for x in ids if x[3:11] == "0" * 8]
    rep = [x for x in ids if x not in zero and len(set(x[3:11])) == 1 and len(set(x[12:])) == 1]
    full = all(len(x) == 15 and x[11] == "-" and RUN_ID_RE.fullmatch(x) is not None for x in ids)
    lines = (" · ".join(ids), "workflows/" + ids[0] + "/journal.jsonl", '"wf": "' + ids[-1] + '"')
    got = [h for ln in lines for h in line_hits(ln, POLICY_DOC, [])]
    cap = [t for ln in lines for t in capture_id_tokens(ln)]
    ok = len(ids) == 20 and len(zero) == 16 and len(rep) == 4 and full and got == [] and cap == []
    return ok, f"목록 {len(ids)}개(0 채움 {len(zero)} · 반복 글자 {len(rep)}) · 전체 꼴 {full} · 문서 정책 {got} · 캡처 ID {cap}"


@cell("run-id-out-of-list-hit")
def _c_run_id_foreign(tmp):
    # 목록 밖 실행 ID 꼴은 적중 — 목록 바로 밖의 0 채움 값 · 임의 16진 · 대문자(16진만 · 접두까지) · 파일 이름 안. 캡처 ID 대조도 같은
    #   값을 낸다(대조는 한 벌). 캡처 정책은 이 계열을 돌리지 않는다(home · mail 만). 출하 내용 진입점(--text-file)도 같은 판정이다
    lines = RUN_ID_FOREIGN + ("foo-" + RUN_ID_FOREIGN[2] + ".js",)
    got = [_ids(line_hits(ln, POLICY_DOC, [])) for ln in lines]
    tok = [capture_id_tokens(x) for x in RUN_ID_FOREIGN]
    cap = [h for ln in lines for h in line_hits(ln, POLICY_CAPTURE, [])]
    _w(tmp, "w.md", "첫 줄\n실행 `" + RUN_ID_FOREIGN[2] + "` 결과\n")
    rc, out = _cli(tmp, ["--text-file", "w.md"])
    ok = (got == [["run-id"]] * len(lines) and tok == [[("run-id", x)] for x in RUN_ID_FOREIGN] and cap == []
          and rc == HIT and "w.md:2: 워크플로 실행 ID — " in out)
    return ok, f"줄별 적중 {got} · 캡처 ID {tok} · 캡처 정책 {cap} · rc={rc} {out[-200:]}"


@cell("run-id-doc-notation-ok")
def _c_run_id_notation(tmp):
    # 꼴만 닮은 문서 표기는 문서 정책 · 캡처 ID 대조 모두 적중하지 않는다 — 트리에 정규식 · 자리표시자 · 스크립트 이름 표기가 많다
    doc = [h for ln in RUN_ID_NOTATION for h in line_hits(ln, POLICY_DOC, [])]
    cap = [t for ln in RUN_ID_NOTATION for t in capture_id_tokens(ln)]
    return doc == [] and cap == [], f"문서 정책 {doc} · 캡처 ID {cap}"


@cell("run-id-bare-hit")
def _c_run_id_bare(tmp):
    # 접미사 없는 꼴은 통과 목록 없이 적중이다 — 0 여덟 자도 · 대문자도 · 접미사가 16진 3자가 아닌 표기도. 토큰은 `wf_` 와 앞 8자다.
    #   단독 · 문장 · 괄호 · 경로 안 · 줄 끝 어디서나 같고 캡처 ID 대조와 출하 내용 진입점(--text-file)도 같은 판정이다. 같은 줄의 합성
    #   값(전체 꼴)은 앞 8자로 잘리지 않아 적중하지 않는다
    ctx = ("{}", "{} probe", "실측: {}", "(probe {}, typeof=string)", "workflows/{}/journal.jsonl")
    got = [_rule_tokens(line_hits(c.format(x), POLICY_DOC, [])) for x in RUN_ID_BARE for c in ctx]
    want = [[("run-id", x[:11])] for x in RUN_ID_BARE for _ in ctx]
    tok = [capture_id_tokens(x) for x in RUN_ID_BARE]
    mixed = _rule_tokens(line_hits(" · ".join((RUN_ID_BARE[1],) + tuple(sorted(SYNTHETIC_RUN_IDS))), POLICY_DOC, []))
    _w(tmp, "w.md", "첫 줄\n실측 " + RUN_ID_BARE[0] + " probe\n")
    rc, out = _cli(tmp, ["--text-file", "w.md"])
    ok = (got == want and tok == [[("run-id", x[:11])] for x in RUN_ID_BARE] and mixed == [("run-id", RUN_ID_BARE[1])]
          and rc == HIT and "w.md:2: 워크플로 실행 ID — " + RUN_ID_BARE[0] + "\n" in out)
    return ok, f"줄별 적중 {got} · 캡처 ID {tok} · 합성 값과 한 줄 {mixed} · rc={rc} {out[-200:]}"


@cell("run-id-long-hex-ok")
def _c_run_id_long_hex(tmp):
    # `wf_` 뒤 16진이 9자 이상 이어지는 토큰(해시가 붙은 이름 따위)은 실행 ID 꼴이 아니다 — 접미사 없는 꼴로도 · 전체 꼴로도 잡지
    #   않는다(9자 이상 뒤에 접미사가 붙어도 · 대문자여도). 대조: 같은 표본(RUN_ID_BARE[0]) 뒤가 16진이 아니면 적중이다(끝의 전방 탐색을
    #   빼면 위 표본이 적중하고, 16진 밖 글자까지 막으면 대조가 실패한다). 두 쪽을 같은 상수에서 만든다 — 표본이 바뀌어도 대조가 갈리지 않게
    long_hex = (RUN_ID_BARE[0] + "5", RUN_ID_BARE[1] + "0" * 4, "build-wf_" + "0123abcd" * 5 + ".log",
                RUN_ID_BARE[1] + "0-" + "001", RUN_ID_BARE[2] + "5E")
    doc = [h for ln in long_hex for h in line_hits(ln, POLICY_DOC, [])]
    cap = [t for ln in long_hex for t in capture_id_tokens(ln)]
    cut = [_ids(line_hits(RUN_ID_BARE[0] + c, POLICY_DOC, [])) for c in ("-x", "_x", ".log")]
    ok = doc == [] and cap == [] and cut == [["run-id"]] * 3
    return ok, f"9자 이상 16진 — 문서 정책 {doc} · 캡처 ID {cap} · 16진 8자에서 끊긴 대조 {cut}"


@cell("run-id-registered-synthetic-ok")
def _c_run_id_registered(tmp):
    # 등재한 반복 글자 값 넷 — 트리의 시험 자료가 쓰는 자리(워크플로 폴더 경로 · `unnamed:` 이름 · 인라인 스크립트 이름)에서 문서 정책 ·
    #   캡처 ID 대조 모두 적중 0. 값 목록이라 이웃 값(마지막 글자만 다른 값 · 대문자 표기)은 적중이다
    reg = sorted(x for x in SYNTHETIC_RUN_IDS if x[3:11] != "0" * 8)
    uses = [u.format(x) for x in reg for u in ("subagents/workflows/{}/journal.jsonl", "unnamed:{}", "foo-{}.js")]
    doc = [h for ln in uses for h in line_hits(ln, POLICY_DOC, [])]
    cap = [t for ln in uses for t in capture_id_tokens(ln)]
    near = [x[:-1] + ("0" if x[-1] != "0" else "1") for x in reg] + [x.upper() for x in reg]
    loud = [_rule_tokens(line_hits(x, POLICY_DOC, [])) for x in near]
    ok = len(reg) == 4 and doc == [] and cap == [] and loud == [[("run-id", x)] for x in near]
    return ok, f"등재 {len(reg)}개 · 쓰는 자리 문서 정책 {doc} · 캡처 ID {cap} · 이웃 값 적중 {loud}"


@cell("session-id-synthetic-shape")
def _c_session_ids(tmp):
    # 합성 세션 ID — 6개 · 모두 [0-9a-f-]{36} 꼴(수집기 · 래퍼가 읽는 꼴)이자 UUID 꼴이고 목록 안 값은 남지 않는다. 목록 밖 UUID 꼴은
    #   0 으로 시작해도 · 대문자여도 남는다 — 목록은 대역이 아니라 값이다
    ids = sorted(SYNTHETIC_SESSION_IDS)
    shaped = all(re.fullmatch(r"[0-9a-f-]{36}", x) and UUID_RE.fullmatch(x) for x in ids)
    quiet = [capture_id_tokens("session id: " + x) for x in ids]
    loud = [capture_id_tokens("세션 " + SESSION_FOREIGN), capture_id_tokens("id=" + SESSION_FOREIGN.upper())]
    want = [[("session-id", SESSION_FOREIGN)], [("session-id", SESSION_FOREIGN.upper())]]
    ok = len(ids) == 6 and shaped and quiet == [[]] * len(ids) and loud == want
    return ok, f"목록 {len(ids)}개 · 꼴 {shaped} · 목록 안 {quiet} · 목록 밖 {loud}"


@cell("capture-id-ansi-stripped")
def _c_capture_ansi(tmp):
    # 캡처 줄의 ANSI 제어열은 정본(capture_id_tokens)이 걷는다 — 색 코드(ESC · JSON 줄의 `\u001b` 표기) · 다른 CSI · OSC 링크가 가른
    #   목록 밖 ID 도 적중이다. 대조: 걷지 않은 줄에서는 꼴 정규식이 그 값을 잡지 않는다(걷기를 빼면 이 셀이 실패한다). 색 코드 안의
    #   합성 값은 통과한다
    esc, jesc, sid, rid = "\x1b", "\\u001b", SESSION_FOREIGN, RUN_ID_FOREIGN[2]
    lines = (esc + "[1m" + sid[:4] + esc + "[22m" + sid[4:] + esc + "[0m",
             '{"text": "' + jesc + "[2m" + sid[:9] + jesc + "[0m" + sid[9:] + '"}',
             "run " + rid[:5] + esc + "[K" + rid[5:] + " · " + esc + "]8;;x" + "\x07" + rid[:8] + esc + "]8;;" + esc + "\\" + rid[8:])
    want = [[("session-id", sid)], [("session-id", sid)], [("run-id", rid), ("run-id", rid)]]
    got = [capture_id_tokens(ln) for ln in lines]
    bare = [UUID_RE.findall(ln) + RUN_ID_RE.findall(ln) for ln in lines]
    synth = capture_id_tokens(esc + "[2msession id:" + esc + "[0m " + min(SYNTHETIC_SESSION_IDS) + " · " + esc + "[1m"
                              + min(SYNTHETIC_RUN_IDS) + esc + "[0m")
    ok = got == want and bare == [[]] * len(lines) and synth == []
    return ok, f"걷은 적중 {got} · 걷지 않은 줄의 꼴 {bare} · 색 코드 안 합성 값 {synth}"


# ── 경로 이름 축 — 내용은 깨끗하고 이름에만 식별자가 있다. 배선(전문 · 스테이징 · 커밋마다 · 커밋 범위)마다 셀을 둔다 ──
_BAD_DIR = "docs" + H + "alice/"
_NAME_HOME = NAME_LABEL + "개인 홈 경로"
_CLEAN_BODY = "".join(f"줄 {i}\n" for i in range(1, 7))


@cell("name-hits-shallowest-node")
def _c_name_hits(tmp):
    # 같은 폴더 아래 파일 둘 · 더 깊은 파일 → 폴더 마디에 한 번 · 자리표시 이름 폴더와 깨끗한 경로는 0 · 파일 이름의 키 꼴은 파일 마디
    key = _k("ABC-", "4821")
    got = name_hits(["x" + H + "alice/a.md", "x" + H + "alice/b/c.md", "x" + H + "example/d.md", "n/" + key + ".md", "plain/f.md"],
                    POLICY_DOC, [])
    want = [("n/" + key + ".md", "key", key), ("x" + H + "alice/", "home", H + "alice/")]
    ok = [(p, h.rule, h.token) for p, h in got] == want and all(h.line is None and h.label.startswith(NAME_LABEL) for _, h in got)
    return ok, repr(got)[:300]


@cell("name-key-joined-shapes")
def _c_name_key(tmp):
    # 이름에서 흔한 이음 꼴 셋 — 키 꼴의 경계는 영숫자뿐이라(내용과 이름이 한 식을 쓴다) 이은 꼴도 잡는다. 통과 규칙은 그대로다(영숫자에 붙은 꼴 ·
    #   예약 번호 자리표시자 · 허용 이름공간은 0)
    key = _k("ABC-", "4821")
    hit = ["d/fix-" + key + ".md", "d/" + key + "_fix.md", "d/fix_" + key + ".md"]
    quiet = ["d/x" + key + ".md", "d/fix_" + _k("TKT-", "0123") + ".md", "d/fix_" + _k("ISO-", "8601") + ".md"]
    got = [(p, h.rule, h.token) for p, h in name_hits(hit + quiet, POLICY_DOC, [])]
    return got == [(p, "key", key) for p in sorted(hit)], repr(got)[:300]


@cell("tree-name-shallowest-node-once")
def _c_tree_name(tmp):
    # 전문 축 — 폴더 이름의 적중은 그 폴더 마디에 한 번(아래 파일 둘) · 자리표시 이름 폴더는 통과한다
    root = _repo(tmp, {_BAD_DIR + "w/a.md": "깨끗\n", _BAD_DIR + "w/b.md": "깨끗\n", "docs" + H + "example/c.md": "깨끗\n"})
    rc, out = _cli(tmp, ["--tree"], cwd=root)
    return rc == HIT and f"{_BAD_DIR}: {_NAME_HOME} — {H}alice/" in out and " hits=1" in out, f"rc={rc} {out[-300:]}"


@cell("tree-name-private-rule-and-root-home")
def _c_tree_name_private(tmp):
    # 비공개 규칙은 이름에도 건다 · 저장소 루트의 홈 꼴 폴더(앞에 `/` 가 없다)도 홈 경로 계열이 잡는다
    root = _repo(tmp, {"pkg/acme-app/x.md": "깨끗\n", H[1:] + "bob/y.md": "깨끗\n"})
    rp = _w(tmp, "r.txt", "(?i)" + "acme\n")
    bare, ruled = _cli(tmp, ["--tree"], cwd=root), _cli(tmp, ["--tree", "--rules", rp], cwd=root)
    ok = (bare[0] == HIT and " hits=1" in bare[1] and f"{H[1:]}bob/: {_NAME_HOME}" in bare[1]
          and ruled[0] == HIT and " hits=2" in ruled[1] and "pkg/acme-app/: " + NAME_LABEL + "비공개 규칙 1 — acme" in ruled[1])
    return ok, f"규칙 없음 rc={bare[0]} {bare[1][-200:]} · 규칙 rc={ruled[0]} {ruled[1][-300:]}"


@cell("staged-name-pure-rename-and-empty-file")
def _c_staged_name(tmp):
    # 추가 줄이 없는 새 이름 — 내용이 그대로인 개명과 빈 새 파일은 hunk 가 없다. 새 경로 목록(--diff-filter=ACR)이 잡는다
    root = _repo(tmp, {"keep/a.md": _CLEAN_BODY})
    _commit_all(tmp, root, "base")
    os.makedirs(os.path.join(root, _BAD_DIR))
    _tgit(tmp, root, "mv", "keep/a.md", _BAD_DIR + "a.md")
    moved = _cli(tmp, ["--staged"], cwd=root)
    _tgit(tmp, root, "mv", _BAD_DIR + "a.md", "keep/a.md")
    _w(root, "new" + H + "bob/empty.md", "")
    _tgit(tmp, root, "add", "-A")
    empty = _cli(tmp, ["--staged"], cwd=root)
    ok = (moved[0] == HIT and f"{_BAD_DIR}: {_NAME_HOME}" in moved[1] and " hits=1" in moved[1]
          and empty[0] == HIT and f"new{H}bob/: {_NAME_HOME}" in empty[1] and " hits=1" in empty[1])
    return ok, f"개명 rc={moved[0]} {moved[1][-200:]} · 빈 파일 rc={empty[0]} {empty[1][-200:]}"


@cell("staged-name-delete-and-modify-legacy-ok")
def _c_staged_name_legacy(tmp):
    # 새 이름이 아니면 걸지 않는다 — 나쁜 이름의 기존 파일을 지우거나 고치는 스테이징(정리)은 통과한다
    root = _repo(tmp, {_BAD_DIR + "gone.md": "깨끗\n", _BAD_DIR + "kept.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _tgit(tmp, root, "rm", "-q", _BAD_DIR + "gone.md")
    _w(root, _BAD_DIR + "kept.md", "깨끗\n둘째 줄\n")
    _tgit(tmp, root, "add", "-A")
    rc, out = _cli(tmp, ["--staged"], cwd=root)
    return rc == OK, f"rc={rc} {out[-300:]}"


@cell("staged-name-new-file-under-legacy-folder")
def _c_staged_name_under_legacy(tmp):
    # 새 경로의 윗폴더 이름도 본다 — 이미 있던 나쁜 이름의 폴더 아래에 새 파일을 더하면 그 폴더 마디에서 막는다
    root = _repo(tmp, {_BAD_DIR + "kept.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    _w(root, _BAD_DIR + "new.md", "깨끗\n")
    _tgit(tmp, root, "add", "-A")
    rc, out = _cli(tmp, ["--staged"], cwd=root)
    return rc == HIT and f"{_BAD_DIR}: {_NAME_HOME}" in out and " hits=1" in out, f"rc={rc} {out[-300:]}"


@cell("commits-name-per-commit-range-ends-miss")
def _c_commits_name(tmp):
    # 중간 커밋에서 더했다가 지운 이름 — 커밋마다 축은 그 커밋에서 잡고(자리 `경로 <해시> 마디`) 두 끝 비교는 못 본다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, _BAD_DIR + "n.md", "깨끗\n")
    mid = _commit_all(tmp, root, "add")
    _tgit(tmp, root, "rm", "-q", _BAD_DIR + "n.md")
    _commit_all(tmp, root, "drop")
    per, ends = _cli(tmp, ["--commits", base + "..HEAD"], cwd=root), _cli(tmp, ["--range", base + "..HEAD"], cwd=root)
    ok = per[0] == HIT and f"경로 {_short(mid)} {_BAD_DIR}: {_NAME_HOME}" in per[1] and " hits=1" in per[1] and ends[0] == OK
    return ok, f"커밋마다 rc={per[0]} {per[1][-300:]} · 두 끝 rc={ends[0]}"


@cell("range-name-committed-and-untracked")
def _c_range_name(tmp):
    # 커밋 범위 축 — 기준 뒤에 커밋한 새 이름(두 끝 비교)과 작업 트리의 미추적 새 이름(작업 트리 비교)을 잡는다. 커밋한 파일과 같은
    #   폴더의 미추적 파일은 그 폴더 마디를 다시 세지 않는다(둘 = 커밋한 폴더 한 번 + 다른 폴더 한 번)
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, _BAD_DIR + "n.md", "깨끗\n")
    _commit_all(tmp, root, "add")
    _w(root, "tmp" + H + "bob/u.md", "깨끗\n")
    _w(root, _BAD_DIR + "u2.md", "깨끗\n")
    ends, work = _cli(tmp, ["--range", base + "..HEAD"], cwd=root), _cli(tmp, ["--range", base], cwd=root)
    ok = (ends[0] == HIT and f"{_BAD_DIR}: {_NAME_HOME}" in ends[1] and " hits=1" in ends[1]
          and work[0] == HIT and f"tmp{H}bob/: {_NAME_HOME}" in work[1] and " hits=2" in work[1])
    return ok, f"두 끝 rc={ends[0]} {ends[1][-200:]} · 작업 트리 rc={work[0]} {work[1][-300:]}"


@cell("commits-replace-ref-ignored")
def _c_replace_ref(tmp):
    # replace ref 는 로컬 조회만 바꾼다 — push 는 원본을 보낸다. 더러운 커밋을 같은 트리의 깨끗한 커밋으로 가려도 원본을 읽는다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    dirty = _commit_all(tmp, root, "작업 " + _k("ABC-", "1234"))
    clean = _tgit(tmp, root, "commit-tree", dirty + "^{tree}", "-p", base, "-m", "작업").strip()
    _tgit(tmp, root, "replace", dirty, clean)
    rc, out = _cli(tmp, ["--commits", base + ".." + dirty], cwd=root)
    return rc == HIT and f"메시지 {_short(dirty)}:1: 티켓 키 꼴" in out and " hits=1" in out, f"rc={rc} {out[-300:]}"


@cell("commits-grafts-exit2")
def _c_grafts(tmp):
    # graft 파일은 부모를 로컬에서만 바꾼다 — 가려진 커밋을 rev-list 가 건너뛴다(replace 끄기로 꺼지지 않는다) → 판정 불가
    root = _repo(tmp, {"a.md": "깨끗\n"})
    base = _commit_all(tmp, root, "base")
    _w(root, "b.md", "깨끗\n")
    _commit_all(tmp, root, "작업 " + _k("ABC-", "1234"))
    _w(root, "c.md", "깨끗\n")
    tip = _commit_all(tmp, root, "tip")
    plain = _cli(tmp, ["--commits", base + ".." + tip], cwd=root)
    _w(root, ".git/info/grafts", tip + " " + base + "\n")
    rc, out = _cli(tmp, ["--commits", base + ".." + tip], cwd=root)
    _w(root, ".git/info/grafts", "# 주석뿐\n\n")
    quiet = _cli(tmp, ["--commits", base + ".." + tip], cwd=root)
    ok = plain[0] == HIT and rc == UNRUN and "graft 파일" in out and quiet[0] == HIT
    return ok, f"없음 rc={plain[0]} · 있음 rc={rc} {out[-200:]} · 주석뿐 rc={quiet[0]}"


@cell("tag-outside-range-exit2")
def _c_tag_outside(tmp):
    # 검사 범위 밖의 이력을 가리키는 태그 — 올리면 그 커밋이 함께 나가는데 범위는 보지 않았다 → 판정 불가(가벼운 태그 · 주석 태그)
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    empty = _tgit(tmp, root, "hash-object", "-t", "tree", "-w", os.devnull).strip()
    side = _tgit(tmp, root, "commit-tree", empty, "-m", "옆 이력 " + _k("ABC-", "1234")).strip()
    _tgit(tmp, root, "tag", "old-light", side)
    _tgit(tmp, root, "tag", "-a", "old-note", "-m", "옛 판", side)
    _tgit(tmp, root, "tag", "here")
    light = _cli(tmp, ["--commits", "HEAD", "--tag", "old-light"], cwd=root)
    noted = _cli(tmp, ["--commits", "HEAD", "--tag", "old-note"], cwd=root)
    inside = _cli(tmp, ["--commits", "HEAD", "--tag", "here"], cwd=root)
    known = _cli(tmp, ["--commits", "HEAD", "--exclude", side, "--tag", "old-light"], cwd=root)
    ok = (light[0] == UNRUN and "검사 범위 밖의 커밋 1개" in light[1] and "old-light" in light[1]
          and noted[0] == UNRUN and "old-note" in noted[1]
          and inside[0] == OK and "lightweight=1 " in inside[1] and known[0] == OK)
    return ok, f"가벼운 rc={light[0]} {light[1][-160:]} · 주석 rc={noted[0]} · 안쪽 rc={inside[0]} · 뺀 끝 rc={known[0]}"


@cell("tag-and-ref-name-rules")
def _c_ref_names(tmp):
    # 태그 · ref 이름은 push 하면 그대로 공개된다 — 경로 이름 규칙(계열 · 비공개 규칙 — 내용과 같은 식)으로 본다
    root = _repo(tmp, {"a.md": "깨끗\n"})
    _commit_all(tmp, root, "base")
    key = _k("ABC-", "1234")
    _tgit(tmp, root, "tag", key)
    _tgit(tmp, root, "tag", "fix-acme-hotfix")
    _tgit(tmp, root, "tag", "v1.2.3")
    rules = _w(tmp, "rules.txt", "acme\n")
    light = _cli(tmp, ["--commits", "HEAD", "--tag", key], cwd=root)
    priv = _cli(tmp, ["--commits", "HEAD", "--rules", rules, "--tag", "refs/tags/fix-acme-hotfix"], cwd=root)
    ref = _cli(tmp, ["--commits", "HEAD", "--ref-name", "refs/heads/feature/" + key], cwd=root)
    quiet = _cli(tmp, ["--commits", "HEAD", "--tag", "v1.2.3", "--ref-name", "refs/heads/main", "--ref-name", "refs/tags/v1.2.3"], cwd=root)
    alone = _cli(tmp, ["--tree", "--ref-name", "x"], cwd=root)
    ok = (light[0] == HIT and f"태그 이름 {key}: 티켓 키 꼴" in light[1] and " hits=1" in light[1]
          and priv[0] == HIT and "태그 이름 fix-acme-hotfix: 비공개 규칙 1" in priv[1]
          and ref[0] == HIT and f"ref 이름 feature/{key}: 티켓 키 꼴" in ref[1]
          and quiet[0] == OK and alone[0] == UNRUN)
    return ok, f"태그 rc={light[0]} {light[1][-160:]} · 규칙 rc={priv[0]} · ref rc={ref[0]} {ref[1][-160:]} · 깨끗 rc={quiet[0]} · 홀로 rc={alone[0]}"


@cell("rules-file-bom-and-trailing-space")
def _c_rules_bom(tmp):
    # 파일 머리의 BOM · 줄 끝 공백이 정규식에 섞이면 그 규칙이 오류 없이 죽는다 — 걷고 읽는다
    f = _w(tmp, "m.md", "문의는 Acme. 로\n")
    bom = _w(tmp, "bom.txt", b"\xef\xbb\xbfAcme\n")
    trail = _w(tmp, "trail.txt", "Acme \t\n")
    got = [_cli(tmp, ["--text-file", f, "--rules", r]) for r in (bom, trail)]
    return all(rc == HIT and "비공개 규칙 1" in out for rc, out in got), f"{[(rc, out[-120:]) for rc, out in got]}"


@cell("rules-env-relative-to-C")
def _c_rules_env_rel(tmp):
    # env 의 상대 경로도 -C 기준이다(--rules · git 설정과 같다) — cwd 의 같은 이름 파일을 읽지 않는다
    root, cwd = os.path.join(tmp, "r"), os.path.join(tmp, "elsewhere")
    _w(root, "m.md", "문의는 Acme 로\n")
    _w(root, "r.txt", "Acme\n")
    _w(cwd, "r.txt", "")
    rc, out = _cli(tmp, ["-C", root, "--text-file", "m.md"], cwd=cwd, extra={"FZ_NEUTRALIZE_RULES": "r.txt"})
    return rc == HIT and "비공개 규칙 1" in out and "rules=1(FZ_NEUTRALIZE_RULES)" in out, f"rc={rc} {out[-300:]}"


def self_test() -> int:
    passed = 0
    for name, fn in CELLS:
        tmp = os.path.realpath(tempfile.mkdtemp(prefix="fz-leak-rules-"))
        try:
            ok, detail = fn(tmp)
        except (OSError, RuntimeError, subprocess.SubprocessError, Unrun) as e:
            ok, detail = False, f"셀 준비 실패 — {type(e).__name__}: {e}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if ok:
            passed += 1
            print(f"PASS {name}")
        else:
            print(f"FAIL {name}: {detail}")
    print(f"self-test {passed}/{len(CELLS)} passed")
    return OK if passed == len(CELLS) else 1


if __name__ == "__main__":
    sys.exit(main())
