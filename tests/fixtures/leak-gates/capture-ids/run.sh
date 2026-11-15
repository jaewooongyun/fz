#!/bin/bash
# modes: default caller=health
# 캡처 fixture 의 ID 감사 회귀 — 캡처 로그(tests/fixtures 아래 *.log · *.jsonl · *.session)의 세션 ID(UUID 꼴)와 워크플로 실행 ID
#   꼴은 누수 규칙 정본(scripts/leak_rules.py)의 합성 목록에 있는 값만 둔다. 대상 트리 전체를 캡처 ID 감사(tests/lib/sample_replay.py
#   의 capture_id_audit — 줄마다 정본의 capture_id_tokens: ANSI 제어열을 걷고 합성 목록과 대조)로 보고, 사본에 목록 밖 값을 넣으면
#   감사와 정본의 실행 ID 계열이 잡는지 단언한다.
#
# ⛔ 대상 트리(기본: 이 러너가 든 트리 · --tree)의 감사 모듈과 정본을 싣는다 — 사본 트리를 넘기면 그 사본의 코드로 그 사본의 로그를
#    본다. 대상 트리에는 쓰지 않는다(python -B · 바이트코드 끔). 주입 · 시험 로그는 mktemp 임시 폴더에만 만든다.
# ⛔ 목록 밖 ID(세션 · 실행)는 이 파일에 글자 그대로 적지 않고 실행할 때 만든다 — 이 파일이 정본의 실행 ID 계열 · 커밋 훅 · 감사
#    스캔에 걸리지 않게. 합성 값과 꼴만 닮은 문서 표기는 정본(SYNTHETIC_SESSION_IDS · SYNTHETIC_RUN_IDS · RUN_ID_NOTATION)에서
#    읽는다 — 사본을 두지 않는다(정본 self-test 와 이 러너가 같은 표기 목록을 본다).
# ⛔ 합성 목록은 값이다 — 실제 UUIDv7 도 0 으로 시작한다. 주입하는 실제 꼴 UUID 는 맨 앞을 0 으로 둔다(대역 규칙으로 바뀌면 지나간다).
# 셀(순서 고정):
#   tree-ids-synthetic-only   대상 트리의 캡처 로그 전부 — 목록 밖 ID 0 · 읽지 못한 로그 0 · 로그 1개 이상
#   injected-real-uuid-hit    캡처 로그 전부의 사본에서 합성 세션 ID 한 자리를 실행 중에 만든 실제 꼴 UUID 로 바꾸면 그 자리 하나가
#                             더 적중한다
#   ansi-split-uuid-hit       ANSI 색 코드가 가른 목록 밖 UUID 를 배너 줄에 넣으면 적중 — 색 코드를 걷지 않은 줄에서는 꼴 정규식(정본
#                             UUID_RE)이 그 값을 잡지 않음을 함께 단언한다(감사가 색 코드를 걷지 않게 바뀌면 이 셀이 실패한다)
#   scope-log-jsonl-session   세 확장자(*.log · *.jsonl · *.session) · 깊은 폴더가 모두 감사 범위다
#   path-only-id-hit          내용은 깨끗하고 파일 이름 · 폴더 이름에만 목록 밖 ID 가 있으면 줄 0 으로 적중한다
#   run-id-synthetic-ok       정본 목록의 합성 실행 ID 는 캡처 감사 · 문서 정책(정본의 실행 ID 계열) 모두 통과
#   run-id-real-shape-hit     실행 중에 만든 목록 밖 실행 ID 는 캡처 감사 · 문서 정책 · 출하 내용 진입점(leak_rules --text-file) 모두 적중
#   run-id-pattern-text-ok    꼴만 닮은 문서 표기(정규식 · 자리표시자 · 스크립트 이름)는 셋 모두 통과
# 출력: 셀마다 `PASS <셀> — 근거` 또는 `FAIL <셀> — 사유`(적중 자리는 `파일:줄 종류` — 일치한 글자는 내지 않는다) · 판정할 수 없는 셀은
#   `UNRUN <셀>: 사유`. 전건 통과면 `CAPTURE_IDS_OK …`
# exit: 0 전건 통과 · 1 단언 실패 · 2 판정 불가(`UNRUN` — 인자 · python3 · 대상 부재 · 임시 폴더 · 감사 모듈 적재 실패 · 읽지 못한
#   캡처 로그 · 폴더 순회 실패 · 셀 안 예외 — 실패 셀이 함께 있어도 2 가 앞선다)
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 러너가 든 트리 — health-check 는 인자 없이 부른다)
set -u
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "UNRUN: --tree 에 경로가 없다"; exit 2; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "UNRUN: --tree 경로가 없다: $2"; exit 2; }; shift 2 ;;
    *) echo "UNRUN: 알 수 없는 인자: $1 (사용: run.sh [--tree <플러그인 트리>])"; exit 2 ;;
  esac
done
[ -n "$TREE" ] || { echo "UNRUN: 플러그인 트리를 정하지 못했다"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 부재"; exit 2; }
for s in tests/lib/sample_replay.py scripts/leak_rules.py; do
  [ -f "$TREE/$s" ] || { echo "UNRUN: 대상 부재 — $s"; exit 2; }
done
[ -d "$TREE/tests/fixtures" ] || { echo "UNRUN: 대상 부재 — tests/fixtures"; exit 2; }
# 비공개 규칙은 이 러너의 판정 밖이다 — 출하 내용 진입점 셀이 바깥 env 의 규칙 파일로 갈리지 않게 끊는다
unset FZ_NEUTRALIZE_RULES
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-capture-ids.XXXXXX")" && [ -n "$WORK" ] && [ -d "$WORK" ] \
  || { echo "UNRUN: 임시 폴더를 만들지 못했다"; exit 2; }
trap 'rm -rf "$WORK"' EXIT

PYTHONDONTWRITEBYTECODE=1 python3 -I -B - "$TREE" "$WORK" <<'PY'
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True   # ⛔ 대상 트리의 tests/lib · scripts 에 __pycache__ 를 쓰지 않는다
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
TREE, WORK = sys.argv[1:3]
FIX = os.path.join(TREE, "tests", "fixtures")
LEAK_PY = os.path.join(TREE, "scripts", "leak_rules.py")
R = L = None   # 캡처 ID 감사 모듈 · 그 모듈이 실은 누수 규칙 정본 — main 이 싣는다
NEED_R = ("capture_files", "capture_id_audit")
NEED_L = ("SYNTHETIC_SESSION_IDS", "SYNTHETIC_RUN_IDS", "UUID_RE", "RUN_ID_NOTATION", "Unrun", "line_hits", "POLICY_DOC")


class Unrun(Exception):
    """셀을 판정할 수 없다 — 러너는 2 로 끝낸다(⛔ 통과 아님)."""


def load():
    """대상 트리의 캡처 ID 감사 모듈을 싣는다 — 그 모듈이 같은 트리의 정본을 싣는다. 쓸 이름이 없으면 판정 불가."""
    sp = importlib.util.spec_from_file_location("fz_capture_audit", os.path.join(TREE, "tests", "lib", "sample_replay.py"))
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    if getattr(mod, "LEAK", None) is None:
        raise Unrun(getattr(mod, "LEAK_ERR", None) or "감사 모듈이 누수 규칙 정본을 싣지 못했다")
    miss = [n for n in NEED_R if not hasattr(mod, n)] + ["leak_rules." + n for n in NEED_L if not hasattr(mod.LEAK, n)]
    if miss:
        raise Unrun("감사 · 정본에 없는 이름 — " + " · ".join(miss))
    return mod


def real_uuid():
    """실제 꼴 세션 ID — 지금 시각의 UUIDv7 꼴(밀리초 48비트 · 버전 7 · 변형 10xx). 맨 앞 자리는 0 이다(실제 UUIDv7 이 그렇다)."""
    rnd = uuid.uuid4().hex
    h = ("0" + format(int(time.time() * 1000), "012x")[1:] + "7" + rnd[:3]
         + format(8 | (int(rnd[3], 16) & 3), "x") + rnd[4:19])
    v = "-".join((h[:8], h[8:12], h[12:16], h[16:20], h[20:32]))
    if v in L.SYNTHETIC_SESSION_IDS:
        raise Unrun("만든 UUID 가 합성 목록 안이다")
    return v


def real_run_id():
    """실제 꼴 실행 ID — 16진 8자 · 3자를 난수로. 합성 목록 밖이다."""
    for _ in range(100):
        v = "wf_" + uuid.uuid4().hex[:8] + "-" + uuid.uuid4().hex[:3]
        if v not in L.SYNTHETIC_RUN_IDS:
            return v
    raise Unrun("합성 목록 밖 실행 ID 를 만들지 못했다")


def put(root, rel, text):
    """시험 로그를 쓴다 — 줄 끝을 바꾸지 않는다(newline="" — 줄 번호가 정본의 바이트 읽기와 같게)."""
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return p


def base_log(rels):
    """주입 자리 — 합성 세션 ID 가 든 첫 캡처 로그(감사 순서) → (상대 경로, 본문, 그 ID, 그 줄 번호). 없으면 판정 불가."""
    for rel in rels:
        with open(os.path.join(FIX, rel), encoding="utf-8", newline="") as fh:
            text = fh.read()
        for sid in sorted(L.SYNTHETIC_SESSION_IDS):
            if sid in text:
                return rel, text, sid, text[:text.index(sid)].count("\n") + 1
    raise Unrun("합성 세션 ID 가 든 캡처 로그가 없다 — 주입 자리 부재")


def where(hits):
    return [f"{f}:{i} {k}" for f, i, k, _ in hits]


def leak_text_file(rel):
    """출하 내용 진입점 — 대상 트리의 정본을 --text-file 로 부른다(cwd = WORK · 비공개 규칙 env 없음) → (exit, 출력)."""
    env = {k: v for k, v in os.environ.items() if k != "FZ_NEUTRALIZE_RULES"}
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "-B", LEAK_PY, "--text-file", rel], cwd=WORK, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout + r.stderr


def c_tree():
    n, hits, unread = R.capture_id_audit(FIX)
    if unread:
        raise Unrun("읽지 못한 캡처 로그 — " + " · ".join(f"{f} ({w})" for f, w in unread[:5]))
    if n == 0:
        raise Unrun("캡처 로그가 0개다 — tests/fixtures 범위를 찾지 못했다")
    return not hits, f"캡처 로그 {n}개 · 목록 밖 ID {len(hits)}건" + (f" — {where(hits)[:8]}" if hits else "")


def c_injected():
    rels = R.capture_files(FIX)
    rel, text, sid, line = base_log(rels)
    _, base, _ = R.capture_id_audit(FIX)
    real = real_uuid()
    d = os.path.join(WORK, "injected")
    for one in rels:
        os.makedirs(os.path.dirname(os.path.join(d, one)), exist_ok=True)
        shutil.copyfile(os.path.join(FIX, one), os.path.join(d, one))
    put(d, rel, text.replace(sid, real, 1))
    n, hits, unread = R.capture_id_audit(d)
    extra = [h for h in hits if h not in base]
    ok = real[:1] == "0" and n == len(rels) and not unread and extra == [(rel, line, "session-id", real)]
    return ok, (f"사본 로그 {n}개(원본 {len(rels)}) · {rel}:{line} 에 0 으로 시작하는 실제 꼴 UUID 주입 → 더해진 적중 {where(extra)}"
                f" (기대 {rel}:{line} session-id 하나)")


def c_ansi_split():
    rel, text, sid, line = base_log(R.capture_files(FIX))
    real = real_uuid()
    new = text.replace(sid, "\x1b[1m" + real[:4] + "\x1b[22m" + real[4:] + "\x1b[0m", 1)
    raw = new.split("\n")[line - 1]
    # 색 코드를 걷지 않은 줄 — 정본의 꼴 정규식이 그 값을 잡지 않아야 이 셀이 걷기를 가른다(정본 함수가 안에서 걷든 말든 같은 대조다)
    bare = [m.group(0) for m in L.UUID_RE.finditer(raw)]
    d = os.path.join(WORK, "ansi")
    put(d, rel, new)
    n, hits, unread = R.capture_id_audit(d)
    ok = real not in bare and n == 1 and not unread and hits == [(rel, line, "session-id", real)]
    return ok, (f"색 코드가 가른 UUID(걷지 않은 줄의 꼴 정규식이 그 값을 잡음 {real in bare}) → 감사 적중 {where(hits)}"
                f" (기대 {rel}:{line} session-id)")


def c_scope():
    d = os.path.join(WORK, "scope")
    files = ("a/x.md.stream.log", "b/c/d/t.jsonl", "e/prev.json.session")
    for rel in files:
        put(d, rel, "머리\nsession id: " + real_uuid() + "\n")
    n, hits, unread = R.capture_id_audit(d)
    got = sorted({f for f, i, k, _ in hits if k == "session-id" and i == 2})
    ok = n == len(files) and not unread and len(hits) == len(files) and got == sorted(files)
    return ok, f"로그 {n}개(기대 {len(files)}) · 적중 파일 {got}"


def c_path_only():
    d = os.path.join(WORK, "path-only")
    files = ("w/" + real_uuid() + ".jsonl", real_run_id() + "/journal.jsonl")
    for rel in files:
        put(d, rel, "머리\n깨끗한 줄\n")
    n, hits, unread = R.capture_id_audit(d)
    got = sorted((f, i, k) for f, i, k, _ in hits)
    want = sorted([(files[0], 0, "session-id"), (files[1], 0, "run-id")])
    ok = n == len(files) and not unread and got == want
    return ok, f"로그 {n}개(기대 {len(files)}) · 경로 이름 적중 {len(got)}건(기대 {len(want)} — 줄 0 · 세션 ID 1 · 실행 ID 1)"


def c_run_synth():
    ids = sorted(L.SYNTHETIC_RUN_IDS)
    if not ids:
        raise Unrun("정본의 합성 실행 ID 목록이 비었다")
    d = os.path.join(WORK, "run-synth")
    put(d, "w/run.stream.log", "".join("\x1b[1mworkflow:\x1b[0m " + x + "\n" for x in ids))
    put(d, "w/agent.jsonl", "".join('{"type": "launched", "key": "workflows/' + x + '/journal.jsonl"}\n' for x in ids))
    n, hits, unread = R.capture_id_audit(d)
    doc = [f.rule for x in ids for f in L.line_hits("실행 `" + x + "` · workflows/" + x + "/", L.POLICY_DOC, [])]
    ok = n == 2 and not unread and hits == [] and doc == []
    return ok, f"합성 실행 ID {len(ids)}개 → 캡처 감사 적중 {where(hits)} · 문서 정책 적중 {doc}"


def c_run_real():
    rid = real_run_id()
    d = os.path.join(WORK, "run-real")
    put(d, "w/run.stream.log", "\x1b[1mworkflow:\x1b[0m " + rid + "\n")
    put(d, "w/agent.jsonl", '{"type": "launched", "key": "workflows/' + rid + '/journal.jsonl"}\n')
    n, hits, unread = R.capture_id_audit(d)
    got = sorted((f, i, k) for f, i, k, t in hits if t == rid)
    doc = [f.rule for f in L.line_hits("실행 `" + rid + "` 결과", L.POLICY_DOC, [])]
    put(WORK, "run-real.md", "첫 줄\n실행 `" + rid + "` 결과\n")
    rc, out = leak_text_file("run-real.md")
    ok = (n == 2 and not unread and len(hits) == 2 and got == [("w/agent.jsonl", 1, "run-id"), ("w/run.stream.log", 1, "run-id")]
          and doc == ["run-id"] and rc == 1 and "run-real.md:2: 워크플로 실행 ID — " in out)
    tail = "" if ok else " " + out[-200:].replace(rid, "<목록 밖 실행 ID>")
    return ok, f"목록 밖 실행 ID → 캡처 감사 {got} · 문서 정책 {doc} · --text-file exit {rc}" + tail


def c_run_text():
    notation = tuple(L.RUN_ID_NOTATION)
    if not notation:
        raise Unrun("정본의 문서 표기 목록이 비었다")
    d = os.path.join(WORK, "run-text")
    put(d, "w/notes.stream.log", "".join("\x1b[2m표기:\x1b[0m " + x + "\n" for x in notation))
    n, hits, unread = R.capture_id_audit(d)
    doc = [f.rule for x in notation for f in L.line_hits(x, L.POLICY_DOC, [])]
    put(WORK, "run-text.md", "".join(x + "\n" for x in notation))
    rc, out = leak_text_file("run-text.md")
    ok = n == 1 and not unread and hits == [] and doc == [] and rc == 0 and "LEAK_CLEAN text-file files=1 " in out
    return ok, (f"문서 표기 {len(notation)}개 → 캡처 감사 적중 {where(hits)} · 문서 정책 적중 {doc} · --text-file exit {rc}"
                + ("" if ok else f" {out[-200:]}"))


CELLS = (("tree-ids-synthetic-only", c_tree), ("injected-real-uuid-hit", c_injected), ("ansi-split-uuid-hit", c_ansi_split),
         ("scope-log-jsonl-session", c_scope), ("path-only-id-hit", c_path_only), ("run-id-synthetic-ok", c_run_synth),
         ("run-id-real-shape-hit", c_run_real),
         ("run-id-pattern-text-ok", c_run_text))


def main():
    global R, L
    try:
        R = load()
    except Unrun as e:
        print(f"UNRUN: {e} (⛔ 통과 아님)")
        return 2
    except Exception as e:   # 부재 · 문법 오류 · 적재 중 예외 모두 판정 불가다
        print(f"UNRUN: 캡처 ID 감사 모듈을 싣지 못했다 — {type(e).__name__}: {e} (⛔ 통과 아님)")
        return 2
    L = R.LEAK
    npass, failed, unrun = 0, [], []
    for name, fn in CELLS:
        try:
            ok, detail = fn()
        except (Unrun, L.Unrun) as e:   # 이 러너의 판정 불가 · 정본의 판정 불가(폴더 순회 실패 등)
            unrun.append(name)
            print(f"UNRUN {name}: {e}")
            continue
        except Exception as e:   # 셀 안 예외는 판정 불가다 — 결함 재현(1)으로 세지 않는다
            unrun.append(name)
            print(f"UNRUN {name}: 셀 안 예외 — {type(e).__name__}: {e}")
            continue
        print(f"{'PASS' if ok else 'FAIL'} {name} — {detail}")
        if ok:
            npass += 1
        else:
            failed.append(name)
    if unrun:
        print(f"UNRUN: 판정 불가 셀 {','.join(unrun)}" + (f" · 실패 {','.join(failed)}" if failed else "")
              + " — 판정 불가가 앞선다 (⛔ 통과 아님)")
        return 2
    if failed:
        print(f"capture-ids: 실패 {len(failed)}건 · 통과 {npass}건")
        return 1
    print(f"CAPTURE_IDS_OK (셀 {npass}개 — 캡처 로그의 세션 · 실행 ID 는 합성 목록 안 · 목록 밖 값은 감사와 정본이 잡는다)")
    return 0


sys.exit(main())
PY
rc=$?
case "$rc" in
  0|1|2) exit "$rc" ;;
  *) echo "UNRUN: 러너 본체가 exit $rc 로 끝났다 (⛔ 통과 아님)"; exit 2 ;;
esac
