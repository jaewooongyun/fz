# 실표본 재생 러너 공통 (F-358) — 외부 형식 파서(GPT 스트림 로그 · Claude Code transcript · Workflow journal)를 바꾸면
# 합성 셀만으로는 실제 기록 형식과 어긋난 것을 못 본다. 실제 기록을 구조만 남기고 스크럽한 표본을 고정해 대상 트리의
# 계측기로 다시 읽는다. 부르는 곳: tests/fixtures/gpt/rollout-replay · tests/fixtures/wf-metrics/transcript-replay ·
# tests/fixtures/wf-metrics/journal-replay 의 run.sh (각자 이 파일을 경로로 싣는다 — 대상 트리가 아니라 러너가 든 트리의 것) ·
# 캡처 ID 감사(capture_id_audit)는 tests/fixtures/leak-gates/capture-ids/run.sh (이 파일을 대상 트리 — --tree · 기본은 러너가 든
# 트리 — 에서 싣는다: leak-gates 러너는 대상 트리의 코드를 시험한다).
#
# 표본 폴더 계약
#   provenance.json  cli_version · captured_at · scrub · samples[{file, sha256}] — file 은 폴더 안 상대 경로
#   판정  표본 부재(목록의 파일이 없음 · samples=[] · provenance.json 없음) → UNRUN(exit 2, PASS 아님)
#         형식(필수 키 · samples 모양 · file/sha256 형식) · 해시 불일치 · 스크럽 위반 · 읽기 오류 → FAIL(exit 1)
#         셀 안 예외(준비 실패) · 누수 규칙 정본(scripts/leak_rules.py) 적재 실패 → 3 — 예외를 1 로 내면 '기준 트리 exit 1' 이
#         결함 재현 없이 통과한다
# 스크럽 감사는 표본(provenance.json + 목록 파일)만 본다. 러너 코드는 보지 않는다.
#   공통 규칙  홈 절대 경로 · `~/` · 사용자 이름이 든 프로젝트 폴더 이름 · OS 임시 폴더 · 메일 주소 · 비밀값 꼴
#              홈 경로 · 메일은 누수 규칙 정본(이 파일이 든 트리의 scripts/leak_rules.py)의 캡처 정책으로 맞춘다 — 문서
#              정책과 달리 자리표시 이름 · 예약 도메인도 전부 거부한다
#   형식 규칙  스트림 로그 = 배너 머리(둘째 구분선까지)만 · transcript/journal/meta/layout = 허용 키만 + 자유 문장 금지
#   ⛔ 소비 프로젝트 이름을 금지어로 적지 않는다(적으면 그 이름이 공개 저장소에 들어간다) — 자유 문장 자체를 금지한다
# 캡처 ID 감사(capture_id_audit)는 표본 감사와 따로 돈다 — 범위는 한 폴더(보통 tests/fixtures) 아래 모든 파일(확장자를 가리지 않는다 —
#   *.sh · *.ts · *.json 같은 시험 코드 · 자료도 세션 ID 를 싣는다)이고 보는 것은 세션 ID(UUID 꼴)와 워크플로 실행 ID 꼴 둘뿐이다.
#   그 폴더가 git 작업 트리 안이면 git 이 내보낼 파일(추적 + 무시되지 않은 미추적)만 본다 — 무시된 부산물(.DS_Store 등)은 범위 밖이고
#   통째로 무시된 폴더는 내려가지 않는다. 그 git 은 부르는 쪽의 GIT_DIR 등(훅이 내보낸다)과 설정 주입(GIT_CONFIG_PARAMETERS ·
#   GIT_CONFIG_COUNT/KEY/VALUE · GIT_CONFIG_GLOBAL · GIT_CONFIG_SYSTEM)을 지우고 부른다 — 답은 그 폴더가 든 작업 트리와 그 설정에서 온다.
#   줄마다 누수 규칙 정본의 capture_id_tokens 를 부른다 — ANSI 제어열 걷기와 합성 목록(SYNTHETIC_SESSION_IDS · SYNTHETIC_RUN_IDS)
#   대조는 정본 한 벌이다(여기 사본을 두지 않는다).
#   목록은 값이다(대역 규칙이 아니다: 실제 UUIDv7 도 0 으로 시작한다)
#   표본용 형식 규칙(format_hits — 스트림 로그 = 배너만 등)은 이 범위에 쓰지 않는다 — 평문 배너 뒤에 본문을 둔 로그가 그 규칙에 걸린다.
#   읽기 · 디코드 실패(NUL 포함 — 정본의 읽기 계약)는 건너뛰지 않고 따로 돌려준다 · 순회 실패(무시되지 않은 폴더)는 정본의 Unrun(판정 불가)이다
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import traceback

OK, FAIL, UNRUN, SETUP = 0, 1, 2, 3
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _load_leak_rules():
    """누수 규칙 정본(이 파일이 든 트리의 scripts/leak_rules.py) → (모듈, None) | (None, 사유). 홈 경로 · 메일 매칭을 여기 따로
    두지 않는다(사본은 한 벌만 고쳐진다).
    ⛔ 싣지 못해도 예외를 올리지 않는다 — 러너의 싣기(exec_module)는 감싸지 않아 처리되지 않은 예외가 exit 1(결함 재현)로 읽힌다.
       run() 이 준비 실패(3)로 끝낸다."""
    path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "scripts", "leak_rules.py"))
    try:
        spec = importlib.util.spec_from_file_location("fz_leak_rules", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:   # noqa: BLE001 — 부재 · 문법 오류 · 적재 중 예외 모두 준비 실패다
        return None, f"누수 규칙 정본을 싣지 못했다: {path} — {type(e).__name__}: {e}"
    return mod, None


LEAK, LEAK_ERR = _load_leak_rules()
# 정본이 판정하는 자리 표지 — GENERIC 에서 이 표지인 규칙은 정본 캡처 정책(홈 경로 · 메일 — 자리표시 이름 · 예약 도메인도 전부
#   거부)의 적중을 쓴다. 규칙 이름 · 순서는 그대로다
CANON = None
# 캡처 정책의 계열 id → 이 감사의 규칙 이름(오염 주입 셀 · 출력이 쓰는 이름)
CAPTURE_RULES = {"home": "home-path", "home-slug": "user-slug", "mail": "email"}
GENERIC = (
    ("home-path", CANON),
    ("tilde-path", re.compile(r"(?<![\w$])~/")),
    ("user-slug", CANON),
    ("os-tmp", re.compile(r"/private/(?:tmp|var)/|/var/folders/")),
    ("email", CANON),
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
    if LEAK is None:   # run() 이 먼저 3 으로 끝낸다 — 직접 부른 곳도 매칭 없이 '위반 0' 을 내지 않게
        raise RuntimeError(LEAK_ERR)
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        canon = {}
        for f in LEAK.line_hits(line, LEAK.POLICY_CAPTURE, []):
            canon.setdefault(CAPTURE_RULES.get(f.rule, f.rule), f.token)   # 규칙마다 줄의 첫 적중 — rx.search 와 같은 단위
        for rule, rx in GENERIC:
            if rx is CANON:
                tok = canon.pop(rule, None)
            else:
                m = rx.search(line)
                tok = m.group(0) if m else None
            if tok is not None:
                out.append((i, rule, tok[:40]))
        out += [(i, rule, tok[:40]) for rule, tok in canon.items()]   # 캡처 정책에 새로 든 계열 — 버리지 않는다
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
    bare, slug = "cwd /" + "Users" + "/someone\n", "dir -" + "Users" + "-someone\n"   # 끝 `/` 없는 홈 경로 · 끝 하이픈 없는 편 꼴
    secret = "sk-" + "proj" + "Q7x2" * 6
    common = [("home-path", primary, lambda t: t.replace("@RUN@", home + "run", 1) if "@RUN@" in t else t + home + "\n", "home-path"),
              ("secret", primary, lambda t: t.replace("(scrubbed)", secret, 1) if "(scrubbed)" in t else t + secret + "\n", "secret"),
              ("home-bare", primary, lambda t: t + bare, "home-path"), ("home-slug", primary, lambda t: t + slug, "user-slug")]
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
    재생 셀은 돌리지 않는다(검증 안 된 표본을 읽지 않는다). F-408: 돈 셀 이름이 expected 와 다르면 FAIL.
    누수 규칙 정본을 싣지 못했으면 셀을 하나도 돌리지 않고 준비 실패(3)다 — 스크럽 감사의 홈 경로 · 메일 매칭이 정본이다."""
    tag = name.upper()
    if LEAK is None:   # ⛔ 정본 없이 감사를 돌리지 않는다 — 매칭 없이 '위반 0' 으로 지나가지 않게
        print(f"SETUP leak-rules: {LEAK_ERR}")
        print(f"{tag}-SETUP 0/{len(expected)} — 준비 실패 leak-rules")
        print("CELLS n=0 ran=")
        return SETUP
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


# ── 캡처 ID 감사 — 한 폴더 아래 모든 파일의 세션 ID · 워크플로 실행 ID ──────────────────────────────────────────
# 저장소를 바꾸는 git 환경 변수 — 훅이나 다른 도구가 내보낸다. 남기면 git 이 root 가 든 작업 트리가 아니라 그 저장소로 답한다
_GIT_REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                 "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")
# 설정을 바꾸는 git 환경 변수 — 명령 범위 설정(GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT 와 그 GIT_CONFIG_KEY_<n> · GIT_CONFIG_VALUE_<n>
#   묶음 — 묶음은 접두로 지운다)은 저장소 로컬 core.excludesFile 을 이기고, 전역 · 시스템 설정 경로(GIT_CONFIG_GLOBAL · GIT_CONFIG_SYSTEM)는
#   그보다 앞서는 값이 없을 때 무시 규칙을 정한다
_GIT_CONFIG_ENV = ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")
_GIT_CONFIG_PREFIX = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


def _git_ignored(root):
    """root 가 git 작업 트리 안이면 그 아래의 무시된 미추적 파일과 통째로 무시된 폴더 → root 기준 상대 경로 집합(git 이 내보내지 않는
    것). 폴더는 `<경로>/` 한 줄이다(--directory — 추적 파일이 없고 안이 전부 무시된 폴더. git 은 그 안을 읽지 않는다).
    작업 트리 밖 · git 부재 · git 실패면 빈 집합이다 — 그때는 걸은 파일 전부를 본다(범위를 줄이는 쪽으로 틀리지 않는다).
    ⛔ git 은 부르는 쪽의 저장소 환경 변수(_GIT_REPO_ENV)와 설정 환경 변수(_GIT_CONFIG_ENV · 키/값 묶음)를 지우고 부른다 — 답은 늘 root 가
       든 작업 트리와 그 설정에서 온다. 남기면 다른 저장소나 주입한 설정의 (더 넓을 수 있는) 무시 규칙으로 감사할 파일이 빠진다.
    ⛔ `git status --ignored` 로 바꾸지 않는다 — 그 꼴은 무시 파일과 읽을 수 없는 무시되지 않은 하위 폴더가 함께 든 폴더를 `<폴더>/` 한 줄로
       접는다. 그러면 걷기가 그 폴더를 가지쳐, 읽지 못한 하위 폴더가 내던 Unrun 이 조용히 사라진다."""
    env = {k: v for k, v in os.environ.items()
           if k not in _GIT_REPO_ENV and k not in _GIT_CONFIG_ENV and not k.startswith(_GIT_CONFIG_PREFIX)}
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"], capture_output=True,
                           env=env)
    except OSError:
        return set()
    return {p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p} if r.returncode == 0 else set()


def capture_files(root):
    """root 아래 모든 파일(확장자를 가리지 않는다) → root 기준 상대 경로(순회 순서 — 폴더 · 파일 이름 정렬). 숨은 폴더도 본다.
    root 가 git 작업 트리 안이면 git 이 내보낼 파일만 — 추적 파일과 무시되지 않은 미추적 파일이다. 걸은 파일에서 무시된 미추적 파일만
    뺀다: 폴더를 열면 OS 가 만드는 .DS_Store 같은 무시된 부산물이 감사를 판정 불가로 만들지 않게. 무시 규칙에 걸려도 추적하는 파일 ·
    아직 커밋하지 않은 새 파일은 본다. 작업 트리 밖(이력 없는 사본 · 임시 폴더)이면 걸은 파일 전부다.
    통째로 무시된 폴더(_git_ignored 의 `<경로>/`)는 내려가지 않는다 — 읽을 수 없는 무시된 폴더가 감사를 판정 불가로 만들지 않는다.
    그 git 은 부르는 쪽의 GIT_DIR 등 · 설정 주입과 무관하게 root 가 든 작업 트리에 묻는다(_git_ignored).
    심볼릭 링크 폴더는 따라가지 않는다(가리키는 곳은 이 트리의 캡처가 아니다). ⛔ 순회 오류(root 부재 포함 — 내려간 폴더, 곧 무시되지 않은
    폴더에서만 난다)는 정본의 Unrun(판정 불가 — 정본 tree_files 와 같은 형식)이다 — 다 읽지 못한 범위를 '위반 0' 으로 읽지 않는다."""
    if LEAK is None:   # 정본 없이 범위를 정하지 않는다
        raise RuntimeError(LEAK_ERR)
    errors, out = [], []
    ignored = _git_ignored(root)   # 걷기 전에 묻는다 — 무시된 폴더를 내려가기 전에 가지친다
    for dp, dns, fns in os.walk(root, onerror=errors.append):
        dns.sort()
        dns[:] = [d for d in dns if os.path.relpath(os.path.join(dp, d), root) + "/" not in ignored]
        out += [os.path.relpath(os.path.join(dp, f), root) for f in sorted(fns)]
    if errors:
        raise LEAK.Unrun(f"폴더를 다 읽지 못했다: {errors[0]}")
    return [rel for rel in out if rel not in ignored]


def capture_id_hits(text):
    """본문 → [(줄, 종류, 토큰)] — 종류 session-id(UUID 꼴) | run-id(실행 ID 꼴). 줄마다 정본의 capture_id_tokens(ANSI 제어열을 걷고
    합성 목록 밖 값만 낸다)를 부른다 — 걷기 · 대조의 사본을 여기 두지 않는다."""
    if LEAK is None:   # 정본 없이 '위반 0' 을 내지 않는다
        raise RuntimeError(LEAK_ERR)
    return [(i, kind, tok) for i, line in enumerate(text.split("\n"), 1) for kind, tok in LEAK.capture_id_tokens(line)]


def capture_id_audit(root):
    """root 아래 파일(capture_files 의 범위) → (파일 수, [(파일, 줄, 종류, 토큰)], [(읽지 못한 파일, 사유)]). 형식 규칙(format_hits)은 쓰지 않는다.
    경로 이름도 본다(적중의 줄은 0) — 세션 기록은 `<세션 ID>.jsonl` · `wf_<실행 ID>/…` 처럼 이름에 ID 가 든다. 내용이 깨끗해도 이름은 공개된다.
    ⛔ 읽기 · 디코드 실패 · NUL 바이트(정본의 읽기 계약 read_text)는 건너뛰지 않고 셋째 목록에 싣는다 — 부르는 쪽은 판정 불가로 끝낸다.
       순회 실패는 정본의 Unrun 이 그대로 올라간다. 파일 수 0 도 부르는 쪽이 판정 불가로 읽는다(범위를 못 찾은 감사는 통과가 아니다)."""
    if LEAK is None:
        raise RuntimeError(LEAK_ERR)
    hits, unread = [], []
    rels = capture_files(root)
    for rel in rels:
        try:
            text = LEAK.read_text(os.path.join(root, rel), rel)
        except LEAK.Unrun as e:
            unread.append((rel, str(e)))
            continue
        hits += [(rel, i, kind, tok) for i, kind, tok in capture_id_hits(text)]
    hits += [(rel, 0, kind, tok) for rel in rels for kind, tok in LEAK.capture_id_tokens(rel)]
    return len(rels), hits, unread
