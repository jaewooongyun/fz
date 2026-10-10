# 실표본 재생 러너 공통 (F-358) — 외부 형식 파서(GPT 스트림 로그 · Claude Code transcript · Workflow journal)를 바꾸면
# 합성 셀만으로는 실제 기록 형식과 어긋난 것을 못 본다. 실제 기록을 구조만 남기고 스크럽한 표본을 고정해 대상 트리의
# 계측기로 다시 읽는다. 부르는 곳: tests/fixtures/gpt/rollout-replay · tests/fixtures/wf-metrics/transcript-replay ·
# tests/fixtures/wf-metrics/journal-replay 의 run.sh (각자 이 파일을 경로로 싣는다 — 대상 트리가 아니라 러너가 든 트리의 것).
#
# 표본 폴더 계약
#   provenance.json  cli_version · captured_at · scrub · samples[{file, sha256}] — file 은 폴더 안 상대 경로
#   판정  표본 부재(목록의 파일이 없음 · samples=[] · provenance.json 없음) → UNRUN(exit 2, PASS 아님)
#         형식(필수 키 · samples 모양 · file/sha256 형식) · 해시 불일치 · 스크럽 위반 · 읽기 오류 → FAIL(exit 1)
#         셀 안 예외(준비 실패) → 3 — 예외를 1 로 내면 '기준 트리 exit 1' 이 결함 재현 없이 통과한다
# 스크럽 감사는 표본(provenance.json + 목록 파일)만 본다. 러너 코드는 보지 않는다.
#   공통 규칙  홈 절대 경로 · `~/` · 사용자 이름이 든 프로젝트 폴더 이름 · OS 임시 폴더 · 메일 주소 · 비밀값 꼴
#   형식 규칙  스트림 로그 = 배너 머리(둘째 구분선까지)만 · transcript/journal/meta/layout = 허용 키만 + 자유 문장 금지
#   ⛔ 소비 프로젝트 이름을 금지어로 적지 않는다(적으면 그 이름이 공개 저장소에 들어간다) — 자유 문장 자체를 금지한다
import hashlib
import json
import os
import re
import shutil
import tempfile
import traceback

OK, FAIL, UNRUN, SETUP = 0, 1, 2, 3
_HEX64 = re.compile(r"[0-9a-f]{64}")

GENERIC = (
    ("home-path", re.compile(r"/(?:Users|home)/[^/\s\"'<>]+/")),
    ("tilde-path", re.compile(r"(?<![\w$])~/")),
    ("user-slug", re.compile(r"-(?:Users|home)-[A-Za-z0-9._]+-")),
    ("os-tmp", re.compile(r"/private/(?:tmp|var)/|/var/folders/")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("secret", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                          r"|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})|-----BEGIN [A-Z ]*PRIVATE KEY-----"
                          r"|\bBearer\s+[A-Za-z0-9._~+/-]{20,}")),
)
MAX_STR = 1200   # 남겨도 되는 문자열(셸 명령 · 알림)의 상한 — 넘으면 본문이 딸려 온 것이다

# ── 형식 규칙 ─────────────────────────────────────────────────────────────────────────────
_ANSI = r"(?:\x1b\[[0-9;]*m)?"
BANNER_LINE = re.compile(r"Reading additional input from stdin\.\.\.|\S.* v\d+\.\d+\.\d+|-{8,}|"
                         + _ANSI + r"(?:workdir|model|provider|approval|sandbox|reasoning effort|reasoning summaries|session id):"
                         + _ANSI + r" \S+|")
SEP = re.compile(r"-{8,}")
# 남겨도 되는 문장 — 플러그인 프롬프트의 `[역할]` 줄 · 하네스 표지 · 작업 알림(결과 본문 `<result>` 없는 꼴) · 백그라운드 안내
TEXT_OK = re.compile(r"(?:\[역할\] [^\n]*|\[Request interrupted by user\]|\(scrubbed\)"
                     r"|<task-notification>\n(?:<(task-id|tool-use-id|output-file|status|summary)>[^<\n]*</\1>\n)+</task-notification>"
                     r"|Command running in background with ID: \w+\. Output is being written to: \S+\. You will be notified "
                     r"when it completes\. To check interim output, use Read on that file path\."
                     r"|<command-message>[\w:-]+</command-message>\n<command-name>/[\w:-]+</command-name>\n"
                     r"<command-args>\(scrubbed\)</command-args>)?")
EVENT_KEYS = {"type", "timestamp", "cwd", "version", "effort", "isMeta", "operation", "content", "message"}
MSG_KEYS = {"id", "role", "model", "stop_reason", "usage", "content"}
BLOCK_KEYS = {"type", "id", "name", "input", "tool_use_id", "content", "text", "thinking", "is_error"}
INPUT_KEYS = {"command", "run_in_background"}
JOURNAL_KEYS = {"type", "key", "agentId", "label", "phase", "result"}
META_KEYS = {"agentType", "description", "workflowPhase", "spawnDepth", "requestShape", "requestNonInteractive", "model"}
LAYOUT_KEYS = {"transcript", "gpt_log_dir", "tasks_dir", "files"}
LAYOUT_FILE_KEYS = {"path", "from", "text", "mtime"}


def _stream_log(text):
    out, seps = [], 0
    for i, line in enumerate(text.split("\n"), 1):
        if seps >= 2 and line:
            out.append((i, "banner-only", "둘째 구분선 뒤 본문"))
        elif not BANNER_LINE.fullmatch(line):
            out.append((i, "banner-only", "배너 머리 밖 줄"))
        seps += bool(SEP.fullmatch(line))
    if seps < 2:
        out.append((0, "banner-only", f"구분선 {seps}개 — 배너가 아니다"))
    return out


def _text_ok(s):
    return isinstance(s, str) and bool(TEXT_OK.fullmatch(s))


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def _transcript_line(ev):
    bad = []
    if not isinstance(ev, dict):
        return ["객체가 아니다"]
    bad += [f"이벤트 키 {k}" for k in sorted(set(ev) - EVENT_KEYS)]
    if "content" in ev and not _text_ok(ev["content"]):
        bad.append("이벤트 content 자유 문장")
    m = ev.get("message")
    if m is not None:
        if not isinstance(m, dict):
            return bad + ["message 가 객체가 아니다"]
        bad += [f"message 키 {k}" for k in sorted(set(m) - MSG_KEYS)]
        if set(m.get("usage") or {}) - {"output_tokens"}:
            bad.append("usage 는 output_tokens 만")
        c = m.get("content")
        if isinstance(c, str) and c and not _text_ok(c):
            bad.append("message content 자유 문장")
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                bad.append("content 블록이 객체가 아니다")
                continue
            bad += [f"블록 키 {k}" for k in sorted(set(b) - BLOCK_KEYS)]
            if b.get("thinking"):
                bad.append("thinking 본문")
            if "text" in b and b["text"] and not _text_ok(b["text"]):
                bad.append("text 블록 자유 문장")
            bc = b.get("content")
            if b.get("type") == "tool_result" and not (_text_ok(bc) or isinstance(bc, list) and all(
                    isinstance(x, dict) and set(x) <= {"type", "text"} and _text_ok(x.get("text")) for x in bc)):
                bad.append("tool_result 본문")
            if b.get("type") == "advisor_tool_result" and bc not in (None, {"type": "advisor_result"}):
                bad.append("advisor 결과 본문")
            bad += [f"입력 키 {k}" for k in sorted(set(b.get("input") or {}) - INPUT_KEYS)]
    bad += ["문자열 길이 상한 초과" for s in _strings(ev) if len(s) > MAX_STR][:1]
    return bad


def _empty(v):
    return v in ("", [], {}, None) or isinstance(v, dict) and all(_empty(x) for x in v.values())


def _journal_line(ev):
    if not isinstance(ev, dict):
        return ["객체가 아니다"]
    bad = [f"journal 키 {k}" for k in sorted(set(ev) - JOURNAL_KEYS)]
    if ev.get("type") not in ("launched", "started", "failed", "result"):
        bad.append(f"journal type {ev.get('type')!r}")
    if "result" in ev and not _empty(ev["result"]):
        bad.append("result 본문(최상위 키만 · 값은 비운다)")
    return bad


def _json_lines(text, check):
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            out.append((i, "format", "JSON 줄이 아니다"))
            continue
        out += [(i, "structure", w) for w in check(ev)]
    return out


def _json_doc(text, check):
    try:
        doc = json.loads(text)
    except ValueError:
        return [(0, "format", "JSON 문서가 아니다")]
    return [(0, "structure", w) for w in check(doc)]


def _meta(doc):
    return ["객체가 아니다"] if not isinstance(doc, dict) else [f"meta 키 {k}" for k in sorted(set(doc) - META_KEYS)]


def _layout(doc):
    if not isinstance(doc, dict):
        return ["객체가 아니다"]
    bad = [f"layout 키 {k}" for k in sorted(set(doc) - LAYOUT_KEYS)]
    for f in doc.get("files") or []:
        bad += [f"layout 파일 키 {k}" for k in sorted(set(f) - LAYOUT_FILE_KEYS)] if isinstance(f, dict) else ["파일 항목 모양"]
        if isinstance(f, dict) and len(str(f.get("text") or "")) > 200:
            bad.append("layout text 길이 상한(200) 초과")
    return bad


def format_hits(rel, text):
    """형식별 스크럽 규칙 — 파일 이름으로 형식을 고른다. → [(줄, 규칙, 사유)]"""
    base = os.path.basename(rel)
    if base.endswith(".stream.log"):
        return _stream_log(text)
    if base == "journal.jsonl":
        return _json_lines(text, _journal_line)
    if base.endswith(".jsonl"):
        return _json_lines(text, _transcript_line)
    if base.endswith(".meta.json"):
        return _json_doc(text, _meta)
    if base == "layout.json":
        return _json_doc(text, _layout)
    if base == "provenance.json":
        return []
    return [(0, "format", "알 수 없는 표본 형식")]


def scrub_hits(rel, text):
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        for rule, rx in GENERIC:
            m = rx.search(line)
            if m:
                out.append((i, rule, m.group(0)[:40]))
    return out + format_hits(rel, text)


# ── provenance · 감사 ────────────────────────────────────────────────────────────────────
def check_provenance(here):
    """→ (code, 사유, provenance). 원장 CHECK 의 provenance 판정과 같은 순서: 형식 → 부재(UNRUN) → 해시."""
    p = os.path.join(here, "provenance.json")
    if not os.path.isfile(p):
        return UNRUN, "UNRUN: sample missing provenance.json", None
    try:
        with open(p, encoding="utf-8") as fh:
            prov = json.load(fh)
    except (OSError, ValueError) as e:
        return FAIL, f"provenance.json 읽기 · 형식 오류 — {type(e).__name__}", None
    s = prov.get("samples") if isinstance(prov, dict) else None
    if not (isinstance(prov, dict) and all(k in prov for k in ("cli_version", "captured_at", "scrub")) and isinstance(s, list)):
        return FAIL, "provenance 필수 키(cli_version · captured_at · scrub · samples 배열) 위반", None
    for x in s:
        if not (isinstance(x, dict) and isinstance(x.get("file"), str) and x["file"] and isinstance(x.get("sha256"), str)
                and _HEX64.fullmatch(x["sha256"])):
            return FAIL, f"sample 형식 위반(file 비지 않은 문자열 · sha256 64자리 hex): {x!r:.80}", None
        if os.path.isabs(x["file"]) or ".." in x["file"].split("/"):
            return FAIL, f"sample 경로가 폴더 밖: {x['file']}", None
    miss = [x["file"] for x in s if not os.path.isfile(os.path.join(here, x["file"]))]
    if miss or not s:
        return UNRUN, "UNRUN: sample missing " + (",".join(miss) if miss else "(samples=[])"), prov
    for x in s:
        try:
            with open(os.path.join(here, x["file"]), "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
        except OSError as e:
            return FAIL, f"표본 읽기 오류 {x['file']}: {type(e).__name__}", prov
        if got != x["sha256"]:
            return FAIL, f"해시 불일치 {x['file']}: {got[:12]} ≠ 기록 {x['sha256'][:12]}", prov
    return OK, f"표본 {len(s)}개 · 필수 키 · 해시 재계산 일치", prov


def audit(here, prov):
    """provenance.json + 목록 파일의 스크럽 위반 → [(파일, 줄, 규칙, 발췌)]. 읽기 오류도 위반(read-error)이다."""
    hits = []
    for rel in ["provenance.json"] + [x["file"] for x in prov["samples"]]:
        try:
            with open(os.path.join(here, rel), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            hits.append((rel, 0, "read-error", type(e).__name__))
            continue
        hits += [(rel, i, r, w) for i, r, w in scrub_hits(rel, text)]
    return hits


def copy_fixture(here, dst):
    """표본 폴더 사본(provenance.json + 목록 파일) — 오염 주입은 사본에만 한다."""
    shutil.copy2(os.path.join(here, "provenance.json"), os.path.join(dst, "provenance.json"))
    with open(os.path.join(here, "provenance.json"), encoding="utf-8") as fh:
        for x in json.load(fh)["samples"]:
            os.makedirs(os.path.dirname(os.path.join(dst, x["file"])), exist_ok=True)
            shutil.copy2(os.path.join(here, x["file"]), os.path.join(dst, x["file"]))
    return dst


def contamination_cell(here, tmp, primary, mutations):
    """오염 주입 대조 — 사본 표본에 오염을 하나씩 넣고 스크럽 감사 · provenance 가 둘 다 잡는지 본다(감사 규칙 적중 + 해시 FAIL).
    공통 셋(primary 표본에 홈 경로 · 비밀값 꼴, 표본 삭제 → UNRUN) + mutations = [(이름, 표본, 바꿀 함수 text→text, 기대 규칙)]."""
    home = "/" + "Users" + "/someone/"            # ⛔ 이 파일에도 홈 경로 글자를 그대로 두지 않는다
    secret = "sk-" + "proj" + "Q7x2" * 6
    common = [("home-path", primary, lambda t: t.replace("@RUN@", home + "run", 1) if "@RUN@" in t else t + home + "\n", "home-path"),
              ("secret", primary, lambda t: t.replace("(scrubbed)", secret, 1) if "(scrubbed)" in t else t + secret + "\n", "secret")]
    seen, missed = [], []
    for name, rel, fn, rule in common + list(mutations):
        d = copy_fixture(here, tempfile.mkdtemp(dir=tmp))
        p = os.path.join(d, rel)
        with open(p, encoding="utf-8") as fh:
            t = fh.read()
        t2 = fn(t)
        if t2 == t:
            raise RuntimeError(f"주입 {name} 이 표본을 바꾸지 못했다 — 주입 자리 부재")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(t2)
        with open(os.path.join(d, "provenance.json"), encoding="utf-8") as fh:
            rules = {r for f, _, r, _ in audit(d, json.load(fh)) if f == rel}
        code, _, _ = check_provenance(d)
        (seen if rule in rules and code == FAIL else missed).append(name)
    d = copy_fixture(here, tempfile.mkdtemp(dir=tmp))   # 표본 삭제 → UNRUN(2)
    os.remove(os.path.join(d, primary))
    code, why, _ = check_provenance(d)
    (seen if code == UNRUN and why.startswith("UNRUN: sample missing") else missed).append("sample-removed")
    return not missed, (f"탐지 {len(seen)}/{len(seen) + len(missed)} ({','.join(seen)})"
                        + (f" · 못 잡음 {','.join(missed)}" if missed else ""))


def run(name, here, expected, cells, tmp):
    """셀을 차례로 돌리고 판정 줄 · 요약 · `CELLS` 줄을 찍은 뒤 exit 코드를 돌려준다.
    cells = [(셀 이름, 함수 prov→(ok, 사유))]. 첫 두 셀은 provenance · scrub 고정 — 둘 중 하나가 FAIL 이면
    재생 셀은 돌리지 않는다(검증 안 된 표본을 읽지 않는다). F-408: 돈 셀 이름이 expected 와 다르면 FAIL."""
    tag = name.upper()
    ran, failed, setup = ["provenance"], [], []
    code, why, prov = check_provenance(here)
    print(f"{'PASS' if code == OK else 'FAIL' if code == FAIL else 'UNRUN'} provenance: {why}")
    if code == UNRUN:
        print(why if why.startswith("UNRUN:") else "UNRUN: " + why)
        print(f"{tag}-UNRUN")
        print(f"CELLS n={len(ran)} ran={','.join(ran)}")
        return UNRUN
    if code == FAIL:
        failed.append("provenance")
    else:
        ran.append("scrub")
        hits = audit(here, prov)
        for f, i, r, w in hits[:8]:
            print(f"  scrub {f}:{i} {r} — {w}")
        print(f"{'PASS' if not hits else 'FAIL'} scrub: 위반 {len(hits)}건 (표본 {len(prov['samples'])}개 + provenance.json)")
        if hits:
            failed.append("scrub")
    if not failed:
        for cname, fn in cells:
            ran.append(cname)
            try:
                ok, detail = fn(prov)
            except Exception as e:   # noqa: BLE001 — 셀 안 예외는 준비 실패(3)다. 결함 재현(1)으로 세지 않는다
                setup.append(cname)
                print(f"SETUP {cname}: {type(e).__name__}: {e}")
                traceback.print_exc(limit=3)
                continue
            print(f"{'PASS' if ok else 'FAIL'} {cname}: {detail}")
            if not ok:
                failed.append(cname)
    else:
        print("SKIP " + ",".join(c for c, _ in cells) + ": 표본 검증(provenance · scrub) 실패 — 재생하지 않는다")
    cells_line = f"CELLS n={len(ran)} ran={','.join(ran)}"
    total = len(expected)
    passed = len([c for c in ran if c not in failed and c not in setup])
    if setup:   # ⛔ 실패 셀이 함께 있어도 3 — 예외 난 셀의 결함 재현 여부를 모른다
        print(f"{tag}-SETUP {passed}/{total} — 준비 실패 {','.join(setup)}" + (f" · 실패 {','.join(failed)}" if failed else ""))
        print(cells_line)
        return SETUP
    if tuple(ran) != tuple(expected):
        failed.append("cell-set")
        print(f"FAIL cell-set: 돈 셀 = 기대 집합이 아니다 — 없음={sorted(set(expected) - set(ran))} · "
              f"뜻밖={sorted(set(ran) - set(expected))} · 순서={ran}")
    if failed:
        print(f"{tag}-FAIL {passed}/{total} — {','.join(failed)}")
        print(cells_line)
        return FAIL
    print(f"{tag}-OK {passed}/{total}")
    print(cells_line)
    return OK
