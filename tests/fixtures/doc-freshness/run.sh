#!/bin/bash
# 문서 최신성 lint(scripts/lint_doc_freshness.py)의 Claude Code 버전 대조 fixture — 대조 모드 exit 세 갈래와 기본 실행의 무네트워크를 동작으로 본다.
#
# 왜: 기본 실행은 health-check 가 부른다 — 네트워크에 묶이면 격리 · 오프라인 환경에서 거짓 실패나 지연이 난다. 그래서 기본 실행은
#     설치 버전과 기준 줄의 대소만 보고(경고), changelog 대조는 옵션(--online · --changelog-file)으로만 켠다.
#     대조 모드가 조회 실패를 통과(0)로 읽으면 기준 뒤의 새 기본 모델 공지를 조용히 놓친다 — 조회 실패는 판정 불가(2)다.
#
# 셀 (대조 셀은 이 폴더의 합성 changelog 사본을 --changelog-file 로 넣는다 — 네트워크 없음 · 기준은 root/ 의 표지 2.1.312):
#   cc-version-match        기준 뒤 항목(2.1.318 · 2.1.321)에 새 기본 모델 공지가 없다 → exit 0. 기준과 같거나 낮은 항목(2.1.312 · 2.1.300)의
#                           공지는 대조 대상이 아니다 — '기준 뒤' 거르기가 깨지면 여기서 1 이 된다
#   cc-version-mismatch     같은 사본의 2.1.321 에 'Added Claude … now the default …' 줄이 있다 → exit 1 · cc-new-default-model · 2.1.321
#   cc-version-lookup-fail  없는 사본 경로 · 기준 표지 없이 산문에만 버전이 있는 루트(root-no-marker/) → 둘 다 exit 2 + '판정 불가'
#   offline-no-network      이 트리에 기본 실행(인자 없음)을 돌린다. 감사 훅(sitecustomize · PYTHONPATH — 자식 python 에도 걸린다)이
#                           이름 조회 · 연결 · URL 요청 시도를 기록하고 막는다 — 기록이 하나라도 있으면 FAIL(예외를 삼켜도 기록은 남는다).
#                           가짜 claude(PATH 앞 · 99.0.0)로 버전 확인이 실제로 돌았는지(cc-version-ahead 경고 · 인자 --version 한 번)도 본다.
#                           양성 대조: 같은 훅 아래 이름 조회 한 번이 기록돼야 한다 — 훅이 죽어 있으면 공허 통과다
# 출력: 셀마다 `PASS|FAIL <셀> — <근거>` · 끝에 `doc-freshness: PASS|FAIL`
# exit: 0 전건 통과 · 1 셀 FAIL · 2 준비 실패(`UNRUN:` 표지 — ⛔ 통과 아님)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd)"
FX="$ROOT/tests/fixtures/doc-freshness"
LINT="$ROOT/scripts/lint_doc_freshness.py"
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: SETUP python3 없음"; exit 2; }
for f in "$LINT" "$FX/root/guides/llm-references.md" "$FX/root-no-marker/guides/llm-references.md" \
         "$FX/changelog-match.md" "$FX/changelog-mismatch.md"; do
  [ -f "$f" ] || { echo "UNRUN: SETUP $f 없음"; exit 2; }
done
T="$(mktemp -d "${TMPDIR:-/tmp}/fz-doc-freshness.XXXXXX")" || { echo "UNRUN: SETUP 임시 폴더를 만들지 못했다"; exit 2; }
trap 'rm -rf "$T"' EXIT
export PYTHONDONTWRITEBYTECODE=1

FAILN=0
ok() { echo "PASS $1 — $2"; }
no() { echo "FAIL $1 — $2"; FAILN=$((FAILN + 1)); }
# lint <인자…> → OUT · RC (stderr 포함 — 판정 불가 문구는 stderr 로 나온다)
lint() { OUT="$(cd "$ROOT" && python3 "$LINT" "$@" 2>&1)"; RC=$?; }
last() { printf '%s\n' "$OUT" | tail -1 | cut -c1-160; }

# ── cc-version-match
lint "$FX/root" --changelog-file "$FX/changelog-match.md"
if [ "$RC" -eq 0 ] && ! printf '%s\n' "$OUT" | grep -q 'cc-new-default-model' && printf '%s\n' "$OUT" | grep -qE '기준 뒤 항목 [1-9]'; then
  ok cc-version-match "rc=0 · $(printf '%s\n' "$OUT" | grep -E '기준 뒤 항목' | head -1)"
else
  no cc-version-match "rc=$RC (기대 0 · 기준 뒤 항목 1개 이상 · 새 기본 모델 공지 0) — $(last)"
fi

# ── cc-version-mismatch
lint "$FX/root" --changelog-file "$FX/changelog-mismatch.md"
if [ "$RC" -eq 1 ] && printf '%s\n' "$OUT" | grep -q 'cc-new-default-model' && printf '%s\n' "$OUT" | grep -q '2\.1\.321'; then
  ok cc-version-mismatch "rc=1 · cc-new-default-model · 2.1.321"
else
  no cc-version-mismatch "rc=$RC (기대 1 · cc-new-default-model · 2.1.321) — $(last)"
fi

# ── cc-version-lookup-fail — 두 갈래 모두 2 + 판정 불가
why=""
lint "$FX/root" --changelog-file "$FX/no-such-changelog.md"
{ [ "$RC" -eq 2 ] && printf '%s\n' "$OUT" | grep -q '판정 불가'; } || why="$why 없는 사본 rc=$RC($(last))"
lint "$FX/root-no-marker" --changelog-file "$FX/changelog-mismatch.md"
{ [ "$RC" -eq 2 ] && printf '%s\n' "$OUT" | grep -q '판정 불가'; } || why="$why 표지 없는 루트 rc=$RC($(last))"
if [ -z "$why" ]; then
  ok cc-version-lookup-fail "없는 사본 · 표지 없는 루트 → 둘 다 rc=2 + 판정 불가"
else
  no cc-version-lookup-fail "기대 rc=2 + 판정 불가 —$why"
fi

# ── offline-no-network
mkdir -p "$T/probe" "$T/bin"
cat > "$T/probe/sitecustomize.py" <<'PY'
# offline-no-network 감사 훅 — 네트워크 요청 시도를 기록하고 막는다(이 fixture 의 임시 폴더에서만 쓴다)
import os
import sys

_LOG = os.environ.get("FZ_NET_PROBE_LOG")
_EVENTS = {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex",
           "socket.gethostbyaddr", "socket.sendto", "socket.sendmsg", "urllib.Request", "http.client.connect"}


def _hook(event, args):
    if _LOG and event in _EVENTS:
        with open(_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{event} {args!r:.160}\n")
        raise ConnectionError(f"offline probe: {event} 차단")


sys.addaudithook(_hook)
PY
cat > "$T/bin/claude" <<SH
#!/bin/sh
printf '%s\n' "\$*" >> "$T/claude-args"
echo "99.0.0 (Claude Code)"
SH
chmod +x "$T/bin/claude"
# probe <기록 파일> <명령…> — 가짜 claude 를 PATH 앞에, 감사 훅을 PYTHONPATH 앞에 둔다
probe() { PATH="$T/bin:$PATH" PYTHONPATH="$T/probe${PYTHONPATH:+:$PYTHONPATH}" FZ_NET_PROBE_LOG="$1" "${@:2}"; }
probe "$T/ctl.log" python3 -c 'import socket
try:
    socket.getaddrinfo("localhost", 80)
except OSError:
    pass' >/dev/null 2>&1
OUT="$(cd "$ROOT" && probe "$T/net.log" python3 "$LINT" 2>&1)"; RC=$?
why=""
[ -s "$T/ctl.log" ] || why="$why 양성 대조 실패(훅이 이름 조회를 기록하지 못했다 — 공허 통과 위험)"
case "$RC" in 0|1) ;; *) why="$why 기본 실행 rc=$RC($(last))" ;; esac
[ -s "$T/net.log" ] && why="$why 외부 요청 시도 $(grep -c . "$T/net.log")건: $(head -1 "$T/net.log" | cut -c1-120)"
printf '%s\n' "$OUT" | grep -q 'cc-version-ahead' || why="$why 버전 확인이 돌지 않았다(cc-version-ahead 없음)"
[ "$(cat "$T/claude-args" 2>/dev/null)" = "--version" ] || why="$why 가짜 claude 인자='$(cat "$T/claude-args" 2>/dev/null | tr '\n' ' ')' (기대 --version 한 번)"
if [ -z "$why" ]; then
  ok offline-no-network "기본 실행 rc=$RC · 외부 요청 시도 0건(양성 대조 $(grep -c . "$T/ctl.log")건 기록) · cc-version-ahead · claude --version 한 번"
else
  no offline-no-network "${why# }"
fi

echo
if [ "$FAILN" -eq 0 ]; then echo "doc-freshness: PASS"; exit 0; fi
echo "doc-freshness: FAIL (${FAILN}셀)"
exit 1
