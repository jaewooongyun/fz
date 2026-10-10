#!/bin/bash
# diff-parse: not-a-diff — 게시 payload 와 GitHub 응답(JSON)만 다룬다. diff_hunk 는 고정 응답의 문자열 값일 뿐 해석하지 않는다.
# 인라인 리뷰 착지 검증 판정 (F-150 · F-256 · F-282 · SC-14) — skills/fz-peer-review/scripts/verify_landing.py 와
# modules/peer-review-inline-anchoring.md `### 7)` 절을 오프라인 gh shim 으로 잰다.
#
# ⛔ 네트워크 0 · 실 gh 0: 이 러너가 임시 폴더에 gh shim 을 쓰고 PATH 맨 앞에 둔다 · GH_* · GITHUB_TOKEN env 를 지운다.
#    shim 은 공용 tests/fixtures/peer-review/_shim/gh 의 규약을 따른다 — 고정 응답만 · gh 2.87.3 `gh api` 의 실재 플래그만 ·
#    미지원 호출 · 플래그 · --jq 는 거부하고 `UNSUPPORTED` 로 기록한다. 공용 shim 은 `pr view` · `pr diff` 만 알아 `api` 는 여기서 둔다.
#    DELETE 는 거부하지 않고 받아서 `REQ DELETE …` 로 기록한다 — 거부하면 삭제 시도가 오류로 묻혀 '삭제 0' 단언이 헛돈다.
#    ⛔ 실 gh API 로 재는 셀은 없다 — 실 API 확인은 UNRUN 이고 이 fixture 결과로 대신 인증하지 않는다.
# 고정 응답의 모양 = 실측 3회(F-150 · F-256 · F-282): 리뷰 하위 컬렉션은 line · side · start_* 가 null 이고 position · diff_hunk 만 있다.
#   개별 조회(/pulls/comments/{id})는 line · side · start_* · subject_type 을 준다.
#
# 셀 (--cells verdict) — verify_landing.py 를 shim 에 직접 돌린다
#   ok-two-call            하위 컬렉션 null · 개별 조회 정상 → OK. 호출이 둘로 갈린다(하위 컬렉션 1회 `--jq .[].id` · id 마다 개별 1회) ·
#                          고정 응답에 비대칭이 실제로 있다(대조군 — 편한 응답으로 통과하지 않게)
#   single-line-start-null 단일 줄(start_* 안 보냄) · 응답 start_* null → OK (UNVERIFIED 아님)
#   mismatch-confirmed     line 이 non-null 인데 다르다 → MISMATCH · confirmBeforeDelete 에만 · 삭제 0 · 재게시 0
#   null-required          보낸 필드(side · start_side)가 null → UNVERIFIED · confirmBeforeDelete 0 · 삭제 0
#   head-moved             POST~GET 사이 head 이동(line null · original_line 있음 — EC-32) → UNVERIFIED · 이유에 original_line · 삭제 0 · 재게시 0
#   head-moved-remapped    head 이동 뒤 이월(line · start_line 재매핑 · commit_id 전진 · original_commit_id = payload commit_id ·
#                          original_* = 게시값) → OK · 이유에 'original_* 로 대조' · confirmBeforeDelete 0 · 삭제 0
#   head-moved-remapped-wrong  같은 이월인데 original_line ≠ 게시값 → MISMATCH · confirmBeforeDelete 에만 · 삭제 0
#   head-moved-unknown-origin  commit_id 전진 · original_commit_id 도 payload 와 다르다 → UNVERIFIED(게시 시점 위치 확인 불가) · 삭제 0
#   missing                payload 3 · id 2 → OK · OK · MISSING
#   four-values            한 리뷰에 OK · MISMATCH · UNVERIFIED · MISSING(하위 컬렉션 순서는 payload 와 다르다) · 확정 MISMATCH 도 삭제 0
#   zero-ids               하위 컬렉션 id 0건 → MISSING 이 아니라 UNVERIFIED(측정 실패를 먼저 의심)
#   fetch-fail             개별 조회 404 → 그 항목 UNVERIFIED · unpaired 에 id
#   body-altered           게시 본문 ≠ payload 본문 · 코멘트 1건 → MISSING 이 아니라 UNVERIFIED · unpaired 1 · 삭제 0 · 재게시 0
#   same-body-two          같은 본문 둘(기대 10 · 20) · 착지 20 · 30 → 20 은 OK 로 먼저 짝지어지고 남은 하나만 MISMATCH
#   same-body-single-multi 같은 본문 · 같은 끝 줄의 단일 줄 항목과 다중 줄 항목 · 응답은 다중 → 단일 순서 → 최대 매칭으로 둘 다 OK
#                          (순서대로 고르면 단일 줄 항목이 다중 줄 응답을 먼저 가져가 다중 줄 항목이 UNVERIFIED — closing validate ISSUE-140)
#   explicit-null-start    payload 단일 줄에 start_line · start_side 를 null 로 명시 → 안 보낸 것으로 세어 OK
#   unrun-subcollection    하위 컬렉션 HTTP 500 → exit 2 · 판정 JSON 없음
#   unrun-no-gh            PATH 에 gh 없음 → exit 2(실 API 를 못 부르면 UNRUN)
# 셀 (--cells doc) — 문서가 같은 결정을 말하는가(키워드 존재가 아니라 판정별 방향)
#   doc-section7           `### 7)` 절에 verify_landing.py · /pulls/comments/{id} · 네 판정 · 무조건 삭제 문장 0 · 판정 표를 행 단위로 —
#                          UNVERIFIED 대응에 '금지' 가 있고 DELETE · '재게시한다' 0 · MISMATCH 대응에 '확인받은 뒤' 가 있고 '없이' 0 ·
#                          MISSING 대응에 '사용자 확인 뒤' · 단일 줄 규칙 줄 · DELETE 줄마다 '확인받은 뒤'/'사용자 확인 뒤' 이고 '없이' 0
#   doc-fewshot            Few-shot GOOD 에 '불일치 발견 시 해당 코멘트 삭제 후 재게시' 0 · 개별 조회 · UNVERIFIED · 사용자 확인 ·
#                          UNVERIFIED 를 주어로 말하는 줄(UNVERIFIED 뒤에 조사)이 1줄 이상이고 모두 '지우지도' 또는 '금지'
#   doc-skill-deliver      fz-peer-review SKILL.md Deliver 흐름 줄의 착지 검증에 verify_landing.py · UNVERIFIED
#   regress-section6       `### 6) 게시 실행` 의 POST 줄이 그대로다
#   doc-direction-negatives 반대 방향 사본 5건(UNVERIFIED 행 → 삭제 후 재게시 · → 바로 지운다 · Few-shot UNVERIFIED 도 삭제 ·
#                          MISMATCH 확인 없이 삭제 · 단일 줄 규칙 삭제)을 임시 사본 문서로 만들어 위 두 셀의 단언이 각각 FAIL 하는지
# 셀 (--cells wiring) — `### 7)` 절 첫 bash 블록을 그대로 재생한다({N} 만 채운다 · FZ_PLUGIN_ROOT=트리 · cwd 에 payload.json)
#   payload 는 scripts/render_review.py 가 render-single-source/review.json 에서 만든 것(인라인 7건 · `<!-- fz-review:ID -->` 표지)
#   wiring-replay          블록 exit 0 · helper 판정 OK 7 · 판정의 이슈 id = payload 표지 집합(render_review MARK 짝맞춤) ·
#                          POST 1회 · 보낸 본문 = payload.json(§6 게시 회귀) · 하위 컬렉션 1회 · 개별 조회 = id 수 · DELETE 0 · 거부 0
#   wiring-call-removed    같은 블록에서 verify_landing.py 호출 줄을 지운 사본 → 위 단언이 FAIL 해야 통과(호출 제거 음성 · 배선 탐지기 양성 대조)
#   wiring-nonok-no-delete 착지 1건 MISMATCH · 1건 head 이동 → 블록 exit 1 · MISMATCH 1 · UNVERIFIED 1 · DELETE 0 · POST 1(재게시 0)
# 기준 트리(be8c871)는 verify_landing.py 가 없고 §7 블록이 하위 컬렉션 필드를 jq 로 바로 뽑는다 → verdict · doc · wiring 이 FAIL → exit 1.
# 기대 셀 집합(F-408): 묶음별 셀 이름을 EXPECTED 상수로 둔다 — 고른 묶음의 합집합과 실제로 판정한 셀이 정확히 같지 않으면 단언 실패(1).
#   셀을 지우거나 이름을 바꾸면 EXPECTED 도 고쳐야 통과한다(셀 삭제가 diff 에 드러난다)
# exit: 0 전건 통과 · 1 단언 실패(판정 줄 뒤에만) · 3 준비 실패(인자 · 도구 · 렌더 입력 · 단언기 고장 · 0셀)
#   ⛔ 기능 부재(helper 없음 · 블록에 호출 없음)는 단언 실패(1)다 — 준비 실패(3)와 섞지 않는다.
#   python 의 미처리 예외(기본 exit 1)는 excepthook 으로 3, python 이 0/1/3 밖으로 끝나면 바깥 셸이 3 으로 바꾼다.
# usage: run.sh [--tree <플러그인 트리>] [--cells verdict,doc,wiring]   (기본: 이 fixture 가 든 트리 · 전 셀 — health-check 는 인자 없이 부른다)
set -u

DONE=0 TMP=""
finish() {
  local rc=$?
  [ -n "$TMP" ] && rm -rf "${TMP:?}"
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ] && [ "$DONE" -ne 1 ]; then
    echo "SETUP 판정 줄 없이 끝났다(exit $rc) — 단언 실패(1)가 아니라 준비 실패 3 으로 낸다"
    exit 3
  fi
  exit "$rc"
}
trap finish EXIT
setup_fail() { echo "SETUP $*"; exit 3; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || setup_fail "fixture 경로 해석 실패"
TREE="$(cd "$HERE/../../../.." && pwd)" || setup_fail "기본 트리 해석 실패"
ALL_GROUPS="verdict doc wiring"
CELLS="$(printf '%s' "$ALL_GROUPS" | tr ' ' ',')"   # ⛔ 쉼표로 잇는다 — 공백으로 이으면 인자 없는 실행이 0셀
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || setup_fail "--tree 에 경로가 없다"
            TREE="$(cd "$2" 2>/dev/null && pwd)" || setup_fail "--tree 경로 없음: $2"; shift 2 ;;
    --cells) [ $# -ge 2 ] || setup_fail "--cells 에 값이 없다"; CELLS="$2"; shift 2 ;;
    *) setup_fail "알 수 없는 인자: $1" ;;
  esac
done
for g in $(printf '%s' "$CELLS" | tr ',' ' '); do
  case " $ALL_GROUPS " in *" $g "*) ;; *) setup_fail "알 수 없는 셀 묶음: $g (지원: $ALL_GROUPS)" ;; esac
done
for c in python3 bash; do command -v "$c" >/dev/null 2>&1 || setup_fail "$c 부재"; done
[ -f "$TREE/modules/peer-review-inline-anchoring.md" ] || setup_fail "모듈 없음: $TREE/modules/peer-review-inline-anchoring.md"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-landing-verify.XXXXXX")" || setup_fail "임시 폴더 실패"
mkdir -p "$TMP/home" "$TMP/shim" "$TMP/cells" "$TMP/nogh" || setup_fail "임시 하위 폴더 실패"

# ── 격리 (네트워크 · 실 gh 0) ────────────────────────────────
for v in $(env | sed -n 's/^\(GH_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$v"; done
unset GITHUB_TOKEN GITHUB_ENTERPRISE_TOKEN
export HOME="$TMP/home" PYTHONDONTWRITEBYTECODE=1

# ── gh shim — `gh api` 고정 응답. 응답은 셀 폴더 routes.json {"<METHOD> <경로>": {"status": N, "body": …}} ──
cat > "$TMP/shim/gh" <<'SHIM'
#!/usr/bin/env python3
import json, os, re, sys
a = sys.argv[1:]
if a == ["--version"]:
    print("gh version 2.87.3 (fixture shim)")
    sys.exit(0)
cell, repo = os.environ.get("FZ_GH_SHIM_DIR", ""), os.environ.get("FZ_GH_SHIM_REPO", "")
if not cell or not os.path.isdir(cell) or not repo:
    print("gh-shim: FZ_GH_SHIM_DIR · FZ_GH_SHIM_REPO 미설정 — 러너 밖 호출을 거부한다", file=sys.stderr)
    sys.exit(1)
log = open(os.path.join(cell, "gh-calls.log"), "a", encoding="utf-8")
log.write("CALL " + " ".join(a) + "\n")
log.flush()


def refuse(msg):
    log.write("UNSUPPORTED " + msg + "\n")
    log.flush()
    print(msg, file=sys.stderr)
    sys.exit(1)


if a[:1] != ["api"]:
    refuse("gh-shim: 미지원 호출 " + " ".join(a))
VAL = {"-X": "method", "--method": "method", "--input": "input", "-q": "jq", "--jq": "jq", "-H": "header", "--header": "header"}
REAL = {"-F", "--field", "-f", "--raw-field", "-i", "--include", "--silent", "--slurp", "-t", "--template",
        "--hostname", "--cache", "-p", "--preview", "--verbose"}   # gh 2.87.3 `gh api` 의 실재 플래그 — 이 shim 은 받지 않는다
opt, pos, i, rest = {"paginate": False, "header": []}, [], 0, a[1:]
while i < len(rest):
    x = rest[i]
    if x == "--paginate":
        opt["paginate"], i = True, i + 1
    elif x in VAL and i + 1 < len(rest):
        if VAL[x] == "header":
            opt["header"].append(rest[i + 1])
        else:
            opt[VAL[x]] = rest[i + 1]
        i += 2
    elif x in REAL:
        refuse("gh-shim: 실재 플래그지만 미지원 " + x)
    elif x.startswith("-"):
        refuse("unknown flag: " + x)
    else:
        pos.append(x)
        i += 1
if len(pos) != 1:
    refuse("accepts 1 arg(s), received %d" % len(pos))
method = opt.get("method") or ("POST" if opt.get("input") else "GET")
if opt["paginate"] and method != "GET":
    refuse("the `--paginate` option is not supported for non-GET requests")
ep = pos[0].lstrip("/")
pre = next((p for p in ("repos/{owner}/{repo}/", "repos/%s/" % repo) if ep.startswith(p)), None)
if pre is None:
    refuse("gh-shim: 이 저장소 밖 엔드포인트 " + ep)
path, jq = ep[len(pre):], opt.get("jq")
log.write("REQ %s %s%s%s\n" % (method, path, " paginate" if opt["paginate"] else "", " jq=" + jq if jq else ""))
log.flush()
if method == "DELETE":
    sys.exit(0)   # 204 — 본문 없음
if method == "POST" and opt.get("input"):
    n = sum(1 for f in os.listdir(cell) if f.startswith("posted-")) + 1
    with open(opt["input"], "rb") as src, open(os.path.join(cell, "posted-%d.json" % n), "wb") as dst:
        dst.write(src.read())
routes = json.load(open(os.path.join(cell, "routes.json"), encoding="utf-8"))
r = routes.get("%s %s" % (method, path)) or {"status": 404, "body": None}
st, body = r["status"], r["body"]
if st >= 400:
    msg = {404: "Not Found", 500: "Server Error"}.get(st, "HTTP Error")
    print(json.dumps(body or {"message": msg, "documentation_url": "https://docs.github.com/rest", "status": str(st)}))
    print("gh: %s (HTTP %d)" % (msg, st), file=sys.stderr)
    sys.exit(1)
show = lambda v: print(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
if jq is None:
    show(body)
elif re.fullmatch(r"\.[A-Za-z_][A-Za-z0-9_]*", jq) and isinstance(body, dict):
    show(body.get(jq[1:]))
elif re.fullmatch(r"\.\[\]\.[A-Za-z_][A-Za-z0-9_]*", jq) and isinstance(body, list):
    for e in body:
        show(e.get(jq[4:]))
else:
    refuse("gh-shim: 미지원 --jq " + jq)
SHIM
chmod +x "$TMP/shim/gh" || setup_fail "shim 권한 실패"
export PATH="$TMP/shim:$PATH"
[ "$(command -v gh)" = "$TMP/shim/gh" ] || setup_fail "PATH 맨 앞 gh 가 shim 이 아니다: $(command -v gh)"
[ -z "$(env | sed -n '/^GH_/p')" ] || setup_fail "GH_* env 가 남았다"

python3 -B - "$TREE" "$CELLS" "$TMP" <<'PY'
import json, os, re, shutil, subprocess, sys, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash


class Setup(Exception):
    pass


TREE, CELLS, TMP = sys.argv[1:4]
want = lambda g: g in CELLS.split(",")
HELPER = os.path.join(TREE, "skills/fz-peer-review/scripts/verify_landing.py")
MOD = os.path.join(TREE, "modules/peer-review-inline-anchoring.md")
SKILL = os.path.join(TREE, "skills/fz-peer-review/SKILL.md")
RR = os.path.join(TREE, "scripts/render_review.py")
REVIEW = os.path.join(TREE, "tests/fixtures/peer-review/render-single-source/review.json")
FX = os.path.join(TREE, "skills/fz-peer-review/references/fixtures/synthetic-sample.patch")
PR, RID, REPO = "4242", "5550001", "fixture-owner/fixture-repo"
HEAD = "0123456789abcdef0123456789abcdef01234567"
HEAD_NEXT = "89abcdef0123456789abcdef0123456789abcdef"    # POST 뒤 push 로 전진한 head
HEAD_OTHER = "fedcba9876543210fedcba9876543210fedcba98"   # payload 와 무관한 head
EXPECTED = {
    "verdict": ["ok-two-call", "single-line-start-null", "mismatch-confirmed", "null-required", "head-moved", "head-moved-remapped",
                "head-moved-remapped-wrong", "head-moved-unknown-origin", "missing", "four-values", "zero-ids", "fetch-fail",
                "body-altered", "same-body-two", "same-body-single-multi", "explicit-null-start", "unrun-subcollection", "unrun-no-gh"],
    "doc": ["doc-section7", "doc-fewshot", "doc-skill-deliver", "regress-section6", "doc-direction-negatives"],
    "wiring": ["wiring-replay", "wiring-call-removed", "wiring-nonok-no-delete"],
}
DEL_SENTENCE = "불일치한 코멘트는 조회로 얻은"
OLD_GOOD = "불일치 발견 시 해당 코멘트 삭제 후 재게시"
SEC6_POST = "gh api repos/{owner}/{repo}/pulls/{N}/reviews -X POST --input payload.json"
MARK_RE = re.compile(r"<!-- fz-review:([A-Za-z0-9:_.\-]+) -->")
VERDICT_ROW = re.compile(r"^\|\s*`(OK|MISMATCH|UNVERIFIED|MISSING)`\s*\|")
UNV_SUBJECT = re.compile(r"UNVERIFIED\s?[가-힣]")   # 'UNVERIFIED 는 · 도 · 를 …' — 판정 나열('· UNVERIFIED ·')은 빼고 주어로 말하는 줄만
CONFIRM = ("확인받은 뒤", "사용자 확인 뒤")
# 반대 방향 사본(리뷰 E1-20 D1 · D1b · D2 · D3 · D6) — (이름, 바꿀 구절, 바꾼 구절). 구절은 문서에 정확히 1번 있어야 사본을 만든다
DOC_NEG = [
    ("D1 UNVERIFIED 행 → 삭제 후 재게시", "| ⛔ **삭제·재게시 금지** — 판정 그대로 사용자에게 보고한다 |", "| 삭제(`gh api -X DELETE …`) 확인 후 재게시한다 |"),
    ("D1b UNVERIFIED 행 → 바로 지운다", "| ⛔ **삭제·재게시 금지** — 판정 그대로 사용자에게 보고한다 |", "| 바로 지우고 다시 올린다 |"),
    ("D2 Few-shot UNVERIFIED 도 삭제", "→ UNVERIFIED 는 지우지도 다시 올리지도 않고 보고 · MISMATCH", "→ UNVERIFIED 도 삭제 후 다시 올린다 · MISMATCH"),
    ("D3 MISMATCH 확인 없이 삭제", "사용자에게 보이고 **확인받은 뒤에만** 삭제(", "확인 없이 바로 삭제("),
    ("D6 단일 줄 규칙 삭제", "- 단일 줄 코멘트는 `start_line`·`start_side` 를 보내지 않으므로 응답의 두 값이 null 이어도 `OK` 다\n", ""),
]

RAN, FAILS, N = [], [], [0]


def check(cell, ok, what):
    if cell not in RAN:
        RAN.append(cell)
    N[0] += 1
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}")
    if not ok:
        FAILS.append(f"{cell}: {what}")


def read(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return ""


def section(text, head):
    """`head` 로 시작하는 줄 다음부터 `##` 로 시작하는 다음 줄 앞까지(CHECK 의 sec() 와 같은 경계)."""
    out, on = [], False
    for line in text.split("\n"):
        if on and line.startswith("##"):
            break
        if on:
            out.append(line)
        if not on and line.startswith(head):
            on = True
    return out


def first_bash(lines):
    out, on = None, False
    for line in lines:
        if not on and line.startswith("```bash"):
            on, out = True, []
            continue
        if on and line.startswith("```"):
            return out
        if on:
            out.append(line)
    return None


# ── 응답 모양 ───────────────────────────────────────────────
def sub_item(cid, w):
    """리뷰 하위 컬렉션 — 실측 모양(F-150 · F-256 · F-282): 앵커 필드 null · position · diff_hunk 만."""
    return {"id": cid, "pull_request_review_id": int(RID), "commit_id": HEAD, "path": w["path"], "body": w["body"],
            "line": None, "side": None, "start_line": None, "start_side": None, "original_line": None,
            "position": 7, "original_position": 7, "diff_hunk": "@@ -1,3 +1,4 @@ fixture"}


def one(cid, w, **over):
    """개별 조회 — 앵커 필드가 채워진다. over 로 셀마다 바꾼다."""
    d = {"id": cid, "pull_request_review_id": int(RID), "commit_id": HEAD, "original_commit_id": HEAD, "path": w["path"], "body": w["body"],
         "line": w["line"], "side": w["side"], "original_line": w["line"],
         "start_line": w.get("start_line"), "start_side": w.get("start_side"), "original_start_line": w.get("start_line"),
         "subject_type": "line", "position": 7, "original_position": 7, "diff_hunk": "@@ -1,3 +1,4 @@ fixture"}
    d.update(over)
    return d


def mkcell(name, wants, landed, over=None, sub_status=200, fail_ids=(), order=None):
    """landed = payload 색인 목록(그 항목들이 게시됐다) · over = {색인: 개별 응답 덮어쓰기} · order = 하위 컬렉션 순서(색인)."""
    d = os.path.join(TMP, "cells", name)
    os.makedirs(d)
    over = over or {}
    cid = {i: 7001 + i for i in landed}
    seq = order if order is not None else landed
    routes = {f"POST pulls/{PR}/reviews": {"status": 200, "body": {"id": int(RID), "state": "COMMENTED", "commit_id": HEAD}},
              f"GET pulls/{PR}/reviews/{RID}/comments": {"status": sub_status,
                                                         "body": [sub_item(cid[i], {**wants[i], **over.get(i, {})}) for i in seq] if sub_status == 200 else None}}
    for i in landed:
        if cid[i] not in fail_ids:
            routes[f"GET pulls/comments/{cid[i]}"] = {"status": 200, "body": one(cid[i], wants[i], **over.get(i, {}))}
    json.dump(routes, open(os.path.join(d, "routes.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"commit_id": HEAD, "event": "COMMENT", "body": "report", "comments": wants},
              open(os.path.join(d, "payload.json"), "w", encoding="utf-8"), ensure_ascii=False)
    open(os.path.join(d, "gh-calls.log"), "w").close()
    return d, cid, routes


def env_for(d, path=None):
    e = dict(os.environ, FZ_GH_SHIM_DIR=d, FZ_GH_SHIM_REPO=REPO, FZ_PLUGIN_ROOT=TREE)
    if path is not None:
        e["PATH"] = path
    return e


def helper(d, path=None):
    r = subprocess.run([sys.executable, "-B", HELPER, "--payload", "payload.json", "--pr", PR, "--review-id", RID],
                       cwd=d, env=env_for(d, path), capture_output=True, text=True, timeout=60)
    try:
        rep = json.loads(r.stdout)
    except ValueError:
        rep = None
    return r.returncode, rep, r.stderr


def calls(d):
    log = read(os.path.join(d, "gh-calls.log")).splitlines()
    req = [l[4:] for l in log if l.startswith("REQ ")]
    return {"req": req, "unsup": [l for l in log if l.startswith("UNSUPPORTED")],
            "delete": [x for x in req if x.startswith("DELETE ")], "post": [x for x in req if x.startswith("POST ")],
            "sub": [x for x in req if x.startswith(f"GET pulls/{PR}/reviews/{RID}/comments")],
            "one": [x.split()[1].rsplit("/", 1)[1] for x in req if x.startswith("GET pulls/comments/")]}


def verdicts(rep):
    return [it.get("verdict") for it in rep["items"]] if isinstance(rep, dict) and isinstance(rep.get("items"), list) else None


W_MULTI = {"path": "Sources/Player/MediaEngine.swift", "start_line": 1484, "start_side": "RIGHT", "line": 1513, "side": "RIGHT",
           "body": "<!-- fz-review:M1 -->\n[1/2] 자동 전환 트리거"}
W_SINGLE = {"path": "Sources/Player/MediaEngine.swift", "line": 83, "side": "RIGHT", "body": "<!-- fz-review:Q1 -->\n단일 줄 지적"}
W_LEFT = {"path": "Sources/Old.swift", "start_line": 40, "start_side": "LEFT", "line": 52, "side": "LEFT",
          "body": "<!-- fz-review:A1 -->\n삭제된 코드 지적"}
W_FOURTH = {"path": "Sources/Timeline.swift", "start_line": 423, "start_side": "RIGHT", "line": 428, "side": "RIGHT",
            "body": "<!-- fz-review:C1 -->\n조기 return"}


def no_delete(c, d, what="삭제 0 · 재게시 0(helper 는 POST · DELETE 를 하지 않는다)"):
    k = calls(d)
    check(c, not k["delete"] and not k["post"] and not k["unsup"], f"{what} — DELETE {len(k['delete'])} · POST {len(k['post'])} · 거부 {len(k['unsup'])}")


def verdict_cells():
    c = "ok-two-call"
    d, cid, routes = mkcell(c, [W_MULTI], [0])
    sub0 = routes[f"GET pulls/{PR}/reviews/{RID}/comments"]["body"][0]
    one0 = routes[f"GET pulls/comments/{cid[0]}"]["body"]
    check(c, sub0["line"] is None and sub0["side"] is None and sub0["position"] is not None and one0["line"] == W_MULTI["line"],
          "대조군 — 고정 응답에 비대칭이 있다(하위 컬렉션 line · side null · position 있음 / 개별 조회 line 채움)")
    rc, rep, err = helper(d)
    check(c, rc == 0 and verdicts(rep) == ["OK"], f"하위 컬렉션 null 인데 개별 조회로 OK — exit {rc} · 판정 {verdicts(rep)} · {err.strip()[-120:]}")
    k = calls(d)
    check(c, len(k["sub"]) == 1 and " paginate" in k["sub"][0] and k["sub"][0].endswith("jq=.[].id"),
          f"하위 컬렉션은 id 수집 1회(--paginate · --jq .[].id) — {k['sub']}")
    check(c, k["one"] == [str(cid[0])], f"id 마다 개별 조회 /pulls/comments/{{id}} — {k['one']}")
    no_delete(c, d)

    c = "single-line-start-null"
    d, cid, _ = mkcell(c, [W_SINGLE], [0])
    rc, rep, err = helper(d)
    got = rep["items"][0].get("got") if verdicts(rep) else None
    check(c, rc == 0 and verdicts(rep) == ["OK"] and got and got.get("start_line") is None and got.get("start_side") is None,
          f"단일 줄 · 응답 start_* null → OK(UNVERIFIED 아님) — exit {rc} · 판정 {verdicts(rep)}")

    c = "mismatch-confirmed"
    d, cid, _ = mkcell(c, [W_SINGLE], [0], over={0: {"line": 84, "original_line": 84}})
    rc, rep, err = helper(d)
    check(c, rc == 1 and verdicts(rep) == ["MISMATCH"], f"non-null 값이 다르다 → MISMATCH · exit 1 — exit {rc} · 판정 {verdicts(rep)}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [cid[0]],
          f"확정 MISMATCH 는 confirmBeforeDelete 에만 오른다(사용자 확인 뒤) — {rep.get('confirmBeforeDelete') if isinstance(rep, dict) else None}")
    no_delete(c, d, "확정 MISMATCH 도 확인 전 삭제 0 · 재게시 0")

    c = "null-required"
    d, cid, _ = mkcell(c, [W_MULTI], [0], over={0: {"side": None, "start_side": None}})
    rc, rep, err = helper(d)
    check(c, rc == 1 and verdicts(rep) == ["UNVERIFIED"], f"보낸 필드 null → UNVERIFIED — exit {rc} · 판정 {verdicts(rep)}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [], "UNVERIFIED 는 삭제 후보가 아니다(confirmBeforeDelete 0)")
    no_delete(c, d)

    c = "head-moved"
    d, cid, _ = mkcell(c, [W_MULTI], [0], over={0: {"line": None, "start_line": None, "original_line": 1513, "original_start_line": 1484}})
    rc, rep, err = helper(d)
    why = rep["items"][0].get("reason", "") if verdicts(rep) else ""
    check(c, rc == 1 and verdicts(rep) == ["UNVERIFIED"] and "original_line" in why,
          f"POST~GET 사이 head 이동(line null · original_line 있음) → UNVERIFIED · 이유에 original_line — exit {rc} · 판정 {verdicts(rep)} · {why[:80]}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [], "head 이동은 삭제 후보가 아니다")
    no_delete(c, d, "UNVERIFIED 삭제 0 · 재게시 0")

    c = "head-moved-remapped"
    d, cid, _ = mkcell(c, [W_MULTI], [0], over={0: {"commit_id": HEAD_NEXT, "line": 1520, "start_line": 1491}})
    rc, rep, err = helper(d)
    it = rep["items"][0] if verdicts(rep) else {}
    got = it.get("got") or {}
    check(c, rc == 0 and verdicts(rep) == ["OK"] and "original_* 로 대조" in it.get("reason", ""),
          f"이월(line · start_line 재매핑 · commit_id 전진) · original_* = 게시값 → OK · 이유에 'original_* 로 대조' — exit {rc} · 판정 {verdicts(rep)} · {it.get('reason', '')[:80]}")
    check(c, got.get("commit_id") == HEAD_NEXT and got.get("original_commit_id") == HEAD and got.get("original_start_line") == W_MULTI["start_line"],
          f"보고 got 에 commit_id · original_commit_id · original_start_line — {[got.get(k) for k in ('commit_id', 'original_commit_id', 'original_start_line')]}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [], "이월된 정상 게시는 삭제 후보가 아니다(confirmBeforeDelete 0)")
    no_delete(c, d)

    c = "head-moved-remapped-wrong"
    d, cid, _ = mkcell(c, [W_MULTI], [0], over={0: {"commit_id": HEAD_NEXT, "line": 1520, "start_line": 1491, "original_line": 1514}})
    rc, rep, err = helper(d)
    why = rep["items"][0].get("reason", "") if verdicts(rep) else ""
    check(c, rc == 1 and verdicts(rep) == ["MISMATCH"] and "original_* 로 대조" in why,
          f"이월인데 original_line ≠ 게시값 → MISMATCH · 이유에 'original_* 로 대조' — exit {rc} · 판정 {verdicts(rep)} · {why[:80]}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [cid[0]],
          f"MISMATCH 는 confirmBeforeDelete 에만 — {rep.get('confirmBeforeDelete') if isinstance(rep, dict) else None}")
    no_delete(c, d, "확정 MISMATCH 도 확인 전 삭제 0 · 재게시 0")

    c = "head-moved-unknown-origin"
    d, cid, _ = mkcell(c, [W_MULTI], [0], over={0: {"commit_id": HEAD_NEXT, "original_commit_id": HEAD_OTHER, "line": 1520, "start_line": 1491}})
    rc, rep, err = helper(d)
    why = rep["items"][0].get("reason", "") if verdicts(rep) else ""
    check(c, rc == 1 and verdicts(rep) == ["UNVERIFIED"] and "게시 시점 위치를 확인할 수 없다" in why,
          f"commit_id 전진 · original_commit_id ≠ payload → UNVERIFIED(게시 시점 위치 확인 불가) — exit {rc} · 판정 {verdicts(rep)} · {why[:80]}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [], "확인 불가는 삭제 후보가 아니다(confirmBeforeDelete 0)")
    no_delete(c, d)

    c = "missing"
    d, cid, _ = mkcell(c, [W_MULTI, W_SINGLE, W_LEFT], [0, 1])
    rc, rep, err = helper(d)
    check(c, rc == 1 and verdicts(rep) == ["OK", "OK", "MISSING"], f"payload 3 · id 2 → OK · OK · MISSING — exit {rc} · 판정 {verdicts(rep)}")

    c = "four-values"
    ws = [W_MULTI, W_SINGLE, W_LEFT, W_FOURTH]
    d, cid, _ = mkcell(c, ws, [0, 1, 2], order=[2, 0, 1],
                       over={1: {"line": 90, "original_line": 90}, 2: {"line": None, "start_line": None, "original_line": 52}})
    rc, rep, err = helper(d)
    cnt = rep.get("counts") if isinstance(rep, dict) else None
    check(c, rc == 1 and verdicts(rep) == ["OK", "MISMATCH", "UNVERIFIED", "MISSING"]
          and cnt == {"OK": 1, "MISMATCH": 1, "UNVERIFIED": 1, "MISSING": 1},
          f"네 값 구분(하위 컬렉션 순서 ≠ payload 순서) — exit {rc} · 판정 {verdicts(rep)} · {cnt}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [cid[1]],
          f"confirmBeforeDelete = MISMATCH id 하나 — {rep.get('confirmBeforeDelete') if isinstance(rep, dict) else None}")
    k = calls(d)
    check(c, sorted(k["one"]) == sorted(str(cid[i]) for i in (0, 1, 2)), f"개별 조회 = 하위 컬렉션 id 3건 — {k['one']}")
    no_delete(c, d, "확정 MISMATCH 가 섞여도 확인 전 삭제 0 · 재게시 0")

    c = "zero-ids"
    d, cid, _ = mkcell(c, [W_MULTI, W_SINGLE], [])
    rc, rep, err = helper(d)
    check(c, rc == 1 and verdicts(rep) == ["UNVERIFIED", "UNVERIFIED"], f"하위 컬렉션 0건 → MISSING 아닌 UNVERIFIED — exit {rc} · 판정 {verdicts(rep)}")

    c = "fetch-fail"
    d, cid, _ = mkcell(c, [W_MULTI, W_SINGLE], [0, 1], fail_ids=(7002,))
    rc, rep, err = helper(d)
    up = [u.get("id") for u in rep.get("unpaired", [])] if isinstance(rep, dict) else None
    check(c, rc == 1 and verdicts(rep) == ["OK", "UNVERIFIED"] and up == [7002],
          f"개별 조회 404 → 그 항목 UNVERIFIED · unpaired 에 id — exit {rc} · 판정 {verdicts(rep)} · unpaired {up}")

    c = "body-altered"
    d, cid, _ = mkcell(c, [W_SINGLE], [0], over={0: {"body": W_SINGLE["body"] + "\n(서버가 바꿔 돌려준 본문)"}})
    rc, rep, err = helper(d)
    up = [u.get("id") for u in rep.get("unpaired", [])] if isinstance(rep, dict) else None
    check(c, rc == 1 and verdicts(rep) == ["UNVERIFIED"] and up == [cid[0]],
          f"게시 본문 ≠ payload 본문 · 코멘트 1건 → MISSING 아닌 UNVERIFIED · unpaired 1 — exit {rc} · 판정 {verdicts(rep)} · unpaired {up}")
    no_delete(c, d)

    c = "same-body-two"
    wa = dict(W_SINGLE, line=10, body="<!-- fz-review:Q2 -->\n같은 본문")
    wb = dict(wa, line=20)
    d, cid, _ = mkcell(c, [wa, wb], [0, 1], over={0: {"line": 20, "original_line": 20}, 1: {"line": 30, "original_line": 30}})
    rc, rep, err = helper(d)
    ids = [it.get("id") for it in rep["items"]] if verdicts(rep) else None
    check(c, rc == 1 and verdicts(rep) == ["MISMATCH", "OK"] and ids == [cid[1], cid[0]],
          f"같은 본문 둘 · 착지 20 · 30 → 기대 20 이 20 과 먼저 짝(OK) · 기대 10 은 남은 30 과 MISMATCH — exit {rc} · 판정 {verdicts(rep)} · id {ids}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [cid[1]],
          f"confirmBeforeDelete = 어긋난 하나뿐(정상 착지는 오르지 않는다) — {rep.get('confirmBeforeDelete') if isinstance(rep, dict) else None}")
    no_delete(c, d)

    c = "same-body-single-multi"
    ws = dict(W_SINGLE, line=10, body="<!-- fz-review:Q3 -->\n같은 본문 · 같은 끝 줄")
    wm = dict(ws, start_line=5, start_side="RIGHT")
    d, cid, _ = mkcell(c, [ws, wm], [0, 1], order=[1, 0])
    rc, rep, err = helper(d)
    ids = [it.get("id") for it in rep["items"]] if verdicts(rep) else None
    check(c, rc == 0 and verdicts(rep) == ["OK", "OK"] and ids == [cid[0], cid[1]],
          f"단일 줄 · 다중 줄 같은 본문 · 응답 다중 → 단일 → 단일은 단일과 · 다중은 다중과 짝(둘 다 OK) — exit {rc} · 판정 {verdicts(rep)} · id {ids}")
    check(c, isinstance(rep, dict) and rep.get("confirmBeforeDelete") == [] and not rep.get("unpaired"),
          f"삭제 후보 0 · 짝 없음 0 — {rep.get('confirmBeforeDelete') if isinstance(rep, dict) else None}")
    no_delete(c, d)

    c = "explicit-null-start"
    d, cid, _ = mkcell(c, [dict(W_SINGLE, start_line=None, start_side=None)], [0])
    rc, rep, err = helper(d)
    check(c, rc == 0 and verdicts(rep) == ["OK"], f"payload 단일 줄 start_line · start_side 명시 null → 안 보낸 것 · OK — exit {rc} · 판정 {verdicts(rep)}")

    c = "unrun-subcollection"
    d, cid, _ = mkcell(c, [W_MULTI], [0], sub_status=500)
    rc, rep, err = helper(d)
    check(c, rc == 2 and rep is None and "UNRUN" in err, f"하위 컬렉션 HTTP 500 → exit 2 · 판정 JSON 없음 — exit {rc} · {err.strip()[-100:]}")
    no_delete(c, d)

    c = "unrun-no-gh"
    d, cid, _ = mkcell(c, [W_MULTI], [0])
    rc, rep, err = helper(d, path=os.path.join(TMP, "nogh"))
    check(c, rc == 2 and rep is None and "gh 부재" in err, f"PATH 에 gh 없음 → exit 2(UNRUN) — exit {rc} · {err.strip()[-100:]}")
    check(c, not read(os.path.join(d, "gh-calls.log")), "gh 호출 0(shim 도 실 gh 도 불리지 않았다)")


def verdict_rows(s7):
    """§7 판정 표 → {판정: [칸 목록, …]} — 칸 = [판정, 조건, 대응]."""
    rows = {}
    for l in s7:
        m = VERDICT_ROW.match(l)
        if m:
            rows.setdefault(m.group(1), []).append([x.strip() for x in l.strip().strip("|").split("|")])
    return rows


def good_lines(tail):
    """Few-shot 코드블록마다 'GOOD:' 줄부터 블록 끝까지."""
    out, on, good = [], False, False
    for l in tail.split("\n"):
        if l.startswith("```"):
            on, good = not on, False
            continue
        if on and l.startswith("GOOD:"):
            good = True
        if on and good:
            out.append(l)
    return out


def doc_asserts(text):
    """문서 본문 → {셀: [(무엇, 통과), …]} — doc-section7 · doc-fewshot 단언. 실제 문서와 반대 방향 사본에 같은 함수를 쓴다."""
    s7 = section(text, "### 7) ")
    j7 = "\n".join(s7)
    rows = verdict_rows(s7)
    resp = lambda v: rows[v][0][2] if len(rows.get(v, [])) == 1 and len(rows[v][0]) == 3 else None
    unv, mis, mss = resp("UNVERIFIED"), resp("MISMATCH"), resp("MISSING")
    dels = [l for l in text.split("\n") if "-X DELETE" in l]
    blk = first_bash(s7) or []
    single = [l for l in s7 if l.startswith("- 단일 줄") and "start_line" in l and "`OK`" in l and "UNVERIFIED" not in l]
    tail = text.split("## 8. Few-shot", 1)[1] if "## 8. Few-shot" in text else ""
    unv_good = [l for l in good_lines(tail) if UNV_SUBJECT.search(l)]
    return {
        "doc-section7": [
            (f"`### 7)` 절({len(s7)}줄)에 verify_landing.py · 개별 조회 · 네 판정",
             bool(s7) and "verify_landing.py" in j7 and "/pulls/comments/{id}" in j7 and all(v in j7 for v in ("OK", "MISMATCH", "UNVERIFIED", "MISSING"))),
            (f"무조건 삭제 문장 '{DEL_SENTENCE}…' 0", bool(text) and DEL_SENTENCE not in text),
            (f"판정 표 — 네 판정이 한 행씩 3칸 — {sorted((v, len(r)) for v, r in rows.items())}",
             all(resp(v) is not None for v in ("OK", "MISMATCH", "UNVERIFIED", "MISSING"))),
            (f"UNVERIFIED 행 대응에 '금지' · DELETE 0 · '재게시한다' 0 — {unv!r}",
             unv is not None and "금지" in unv and "DELETE" not in unv and "재게시한다" not in unv),
            (f"MISMATCH 행 대응에 '확인받은 뒤' · '없이' 0 — {(mis or '')[:60]!r}", mis is not None and "확인받은 뒤" in mis and "없이" not in mis),
            (f"MISSING 행 대응에 '사용자 확인 뒤' — {mss!r}", mss is not None and "사용자 확인 뒤" in mss),
            (f"단일 줄 규칙 줄(- 단일 줄 … start_line … `OK`) {len(single)}개", len(single) == 1),
            (f"DELETE 를 말하는 줄 {len(dels)}개가 모두 '확인받은 뒤' · '사용자 확인 뒤' 중 하나를 말하고 '없이' 0",
             bool(dels) and all(any(p in l for p in CONFIRM) and "없이" not in l for l in dels)),
            (f"§7 bash 블록({len(blk)}줄)에 DELETE 0 — 재생해도 지우지 않는다", bool(blk) and not any("DELETE" in l for l in blk)),
        ],
        "doc-fewshot": [
            (f"Few-shot GOOD — '{OLD_GOOD}' 0 · 개별 조회 · UNVERIFIED · 사용자 확인",
             bool(tail) and OLD_GOOD not in tail and "/pulls/comments/{id}" in tail and "UNVERIFIED" in tail and "사용자 확인" in tail),
            (f"Few-shot GOOD 에서 UNVERIFIED 를 주어로 말하는 줄 {len(unv_good)}개가 모두 '지우지도' 또는 '금지'",
             bool(unv_good) and all("지우지도" in l or "금지" in l for l in unv_good)),
        ],
    }


def doc_cells():
    text = read(MOD)
    A = doc_asserts(text)
    c = "doc-section7"
    for what, ok in A[c]:
        check(c, ok, what)

    c = "doc-fewshot"
    for what, ok in A[c]:
        check(c, ok, what)

    c = "doc-skill-deliver"
    dl = [l for l in read(SKILL).split("\n") if l.startswith("`앵커 계산(") and "착지 검증" in l]
    check(c, len(dl) == 1 and "verify_landing.py" in dl[0] and "UNVERIFIED" in dl[0] and "사용자 확인" in dl[0],
          f"SKILL.md Deliver 흐름 줄({len(dl)}개)의 착지 검증 = verify_landing.py · UNVERIFIED 금지 · 사용자 확인")

    c = "regress-section6"
    s6 = section(text, "### 6) ")
    check(c, SEC6_POST in s6, f"`### 6) 게시 실행` POST 줄 그대로 — {SEC6_POST}")

    c = "doc-direction-negatives"
    d = os.path.join(TMP, "cells", c)
    os.makedirs(d)
    for k, (name, old, new) in enumerate(DOC_NEG):
        n = text.count(old)
        if n != 1:
            check(c, False, f"{name}: 바꿀 구절이 문서에 {n}번 — 1번이어야 반대 방향 사본을 만든다")
            continue
        p = os.path.join(d, f"neg-{k}.md")
        open(p, "w", encoding="utf-8").write(text.replace(old, new))
        bad = [what for cell in ("doc-section7", "doc-fewshot") for what, ok in doc_asserts(read(p))[cell] if not ok]
        check(c, bool(bad), f"{name} 사본 → doc 단언 FAIL {len(bad)}건(0 이면 방향을 못 잰다) — {[b[:50] for b in bad[:2]]}")


def rendered_payload():
    out = os.path.join(TMP, "render")
    for p in (RR, REVIEW, FX):
        if not os.path.isfile(p):
            raise Setup(f"렌더 입력 없음: {p}")
    r = subprocess.run([sys.executable, "-B", RR, "--review", REVIEW, "--diff", FX, "--out-dir", out], capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not os.path.isfile(os.path.join(out, "payload.json")):
        raise Setup(f"render_review.py 렌더 실패(exit {r.returncode}): {r.stderr.strip()[-200:]}")
    raw = open(os.path.join(out, "payload.json"), "rb").read()
    pay = json.loads(raw)
    if len(pay.get("comments", [])) != 7:
        raise Setup(f"렌더 payload 인라인 {len(pay.get('comments', []))}건 — 7건 전제 불성립")
    return raw, pay


def replay(name, block, raw, pay, over=None):
    d = os.path.join(TMP, "cells", name)
    ws = pay["comments"]
    n = len(ws)
    os.makedirs(d)
    cid = {i: 7101 + i for i in range(n)}
    routes = {f"POST pulls/{PR}/reviews": {"status": 200, "body": {"id": int(RID), "state": "COMMENTED", "commit_id": HEAD}},
              f"GET pulls/{PR}/reviews/{RID}/comments": {"status": 200, "body": [sub_item(cid[i], ws[i]) for i in reversed(range(n))]}}
    for i in range(n):
        routes[f"GET pulls/comments/{cid[i]}"] = {"status": 200, "body": one(cid[i], ws[i], **(over or {}).get(i, {}))}
    json.dump(routes, open(os.path.join(d, "routes.json"), "w", encoding="utf-8"), ensure_ascii=False)
    open(os.path.join(d, "payload.json"), "wb").write(raw)
    open(os.path.join(d, "gh-calls.log"), "w").close()
    src = "\n".join(block or []).replace("{N}", PR)
    r = subprocess.run(["bash", "-c", src], cwd=d, env=env_for(d), capture_output=True, text=True, timeout=120)
    try:
        rep = json.loads(r.stdout)
    except ValueError:
        rep = None
    return d, cid, r, rep


def wiring_asserts(d, cid, r, rep, raw, pay):
    """§7 재생 단언 — (이름, 통과) 목록. wiring-replay 는 전부 통과 · wiring-call-removed 는 하나 이상 FAIL 이어야 한다."""
    k = calls(d)
    marks = sorted(m for c in pay["comments"] for m in MARK_RE.findall(c["body"]))
    got = sorted(it.get("issue") or "" for it in rep["items"]) if verdicts(rep) else None
    posted = [f for f in sorted(os.listdir(d)) if f.startswith("posted-")]
    same = len(posted) == 1 and open(os.path.join(d, posted[0]), "rb").read() == raw
    return [
        (f"블록 exit 0 (exit {r.returncode} · {r.stderr.strip()[-80:]})", r.returncode == 0),
        (f"helper 판정 OK {len(pay['comments'])} — {rep.get('counts') if isinstance(rep, dict) else '판정 JSON 없음'}",
         isinstance(rep, dict) and rep.get("counts", {}).get("OK") == len(pay["comments"]) and (verdicts(rep) or []).count("OK") == len(pay["comments"])),
        (f"판정의 이슈 id = payload 표지 집합(render_review MARK 짝맞춤) — {got}", got == marks),
        (f"POST 1회 · 보낸 본문 = payload.json 바이트(§6 게시 회귀) — POST {len(k['post'])} · 일치 {same}", len(k["post"]) == 1 and same),
        (f"하위 컬렉션 1회(--jq .[].id) — {k['sub']}", len(k["sub"]) == 1 and k["sub"][0].endswith("jq=.[].id")),
        (f"개별 조회 = id {len(cid)}건 각 1회 — {len(k['one'])}회", sorted(k["one"]) == sorted(str(v) for v in cid.values())),
        (f"DELETE 0 · 거부 0 — DELETE {len(k['delete'])} · 거부 {k['unsup'][:1]}", not k["delete"] and not k["unsup"]),
    ]


def wiring_cells():
    raw, pay = rendered_payload()
    text = read(MOD)
    s7 = section(text, "### 7) ")
    block = first_bash(s7)

    c = "wiring-replay"
    check(c, block is not None, f"`### 7)` 절에 bash 블록이 있다({len(block or [])}줄)")
    d, cid, r, rep = replay(c, block, raw, pay)
    for what, ok in wiring_asserts(d, cid, r, rep, raw, pay):
        check(c, ok, what)

    c = "wiring-call-removed"
    cut = [l for l in (block or []) if "verify_landing.py" not in l]
    removed = len(block or []) - len(cut)
    check(c, removed >= 1, f"사본에서 verify_landing.py 호출 줄 {removed}개를 지웠다")
    d, cid, r, rep = replay(c, cut, raw, pay)
    bad = [what for what, ok in wiring_asserts(d, cid, r, rep, raw, pay) if not ok]
    check(c, bool(bad), f"호출 줄 없는 사본의 재생은 배선 단언이 FAIL 한다({len(bad)}건 — {bad[:2]})")

    c = "wiring-nonok-no-delete"
    ws = pay["comments"]
    single = next(i for i, w in enumerate(ws) if "start_line" not in w)
    multi = next(i for i, w in enumerate(ws) if "start_line" in w)
    d, cid, r, rep = replay(c, block, raw, pay, over={single: {"line": ws[single]["line"] + 5, "original_line": ws[single]["line"] + 5},
                                                         multi: {"line": None, "start_line": None, "original_line": ws[multi]["line"]}})
    k = calls(d)
    cnt = rep.get("counts") if isinstance(rep, dict) else None
    check(c, r.returncode == 1 and cnt == {"OK": len(ws) - 2, "MISMATCH": 1, "UNVERIFIED": 1, "MISSING": 0},
          f"MISMATCH 1 · UNVERIFIED 1 → 블록 exit 1 — exit {r.returncode} · {cnt}")
    check(c, not k["delete"] and len(k["post"]) == 1 and not k["unsup"],
          f"확인 전 삭제 0 · 재게시 0(POST 는 처음 1회뿐) — DELETE {len(k['delete'])} · POST {len(k['post'])} · 거부 {len(k['unsup'])}")


def main():
    if want("verdict"):
        verdict_cells()
    if want("doc"):
        doc_cells()
    if want("wiring"):
        wiring_cells()
    if not RAN:
        raise Setup("판정한 셀이 0개 — 셀 선택이 아무것도 고르지 않았다(통과로 읽지 않는다)")
    # F-408 — 판정한 셀 = 고른 묶음의 기대 셀 합집합. check() 를 거치지 않는다(거치면 그 이름이 RAN 에 들어간다)
    exp = [x for g in EXPECTED if want(g) for x in EXPECTED[g]]
    if set(RAN) != set(exp) or len(RAN) != len(exp):
        what = f"기대 셀 집합 — 빠짐 {sorted(set(exp) - set(RAN))} · 더함 {sorted(set(RAN) - set(exp))} · 판정 {len(RAN)} · 기대 {len(exp)}"
        print(f"FAIL  {what}")
        FAILS.append(what)
    print()
    print(f"{len(FAILS)} 건 실패")
    if FAILS:
        return 1
    print(f"LANDING_VERIFY_OK cells={CELLS} ran={len(RAN)}({' '.join(RAN)}) checks={N[0]}")
    return 0


try:
    sys.exit(main())
except Setup as ex:
    print(f"SETUP {ex}")
    sys.exit(3)
PY
rc=$?
DONE=1
case "$rc" in
  0|1|3) exit "$rc" ;;
  *) echo "SETUP python 이 0/1/3 밖으로 끝났다 (exit $rc)"; exit 3 ;;
esac
