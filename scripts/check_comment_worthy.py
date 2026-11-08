#!/usr/bin/env python3
"""check_comment_worthy.py — 큐레이션한 리뷰(review.json 에 `excluded` 키)의 코멘트 가치 계약 검사 (Curate · D1~D4).

왜: 피어 리뷰가 후보를 거의 다 코멘트로 올렸다 — 도달 경로 없는 추론 · SDK 내부 가정 · 이미 달린 스레드 중복 · 원래 있던 문제까지.
Curate 는 후보마다 "코멘트 | 제외(E1~E8)" 를 고르게 하고, 이 검사기가 그 결과를 기계로 본다(문서 규칙만으로는 발화하지 않았다 — F-285).

issue(코멘트할 것) 필수:
  kind             bug | structure | quality | intent-question
  evidence[]       하나 이상이 `path:line[-line]@sha` — sha 는 review.json `target.sha`(gather 의 target.json · PR 이면 headRefOid)의 접두
                   (`pr.headSha` 는 게시 메타일 뿐이다 — 브랜치 대상은 pr 이 없다)
  bug              repro{status: reproduced | code-determined, how} · symptom_screen · symptom_reach
  structure|quality measure(관례 표본 N:M · 중복 줄 수 · 결함 위험 — 측정값 없는 구조 제안은 E3)
  origin           regression · improvement 중 하나(pre-existing 은 E4 로 제외 · 리포트 ④ · 그 밖 표기는 위반 — F-037 우회 차단)
  base_evidence    origin=regression 이면 `path:line@sha` — sha 는 review.json meta.base_sha 이고, meta.base_sha 는 review.json 폴더의
                   base-sha.txt(gather 가 base/ 를 뜬 커밋)와 같다. 그 파일이 없으면 판정 불가(exit 2) · head · 로컬 develop sha 는 위반(F-037)
  suggestion       있다(조치 없는 지적은 E6) — intent-question 은 질문이 조치라 면제
  refute           재검증 기록(반박 시도와 결과)
  comment          코드 펜스 밖 산문 ≤ 4줄 · 마무리 어조(…부탁드립니다 · …여쭙습니다 · ?)가 없으면 WARN(차단 아님)
  duplicateOf      있으면 위반 — 중복은 E5 로 제외한다
  기존 스레드      existing-threads.json(status ok)에 같은 path ±3줄 스레드가 있으면 duplicateOf(→ 제외) 또는 distinctFrom[{thread, why}]
excluded[]       {id, what, code E1~E8, reason} · E5 = duplicateOf(+선택 reply 답글 초안) · E8 = refute
strengths        string[] 그대로 · 원소마다 strengthGaps[{claim(= 그 강점), uncovered(그 강점이 못 막는 시나리오 — 비지 않음)}](F-117 · F-517)
  E1 도달 경로 미확인(코드 경로만 있음)       E2 SDK · 바이너리 내부 동작 가정       E3 결함 없는 설계 선호(측정값 없음)
  E4 원래 있던 문제 — 리포트 ④ 참고          E5 기존 스레드와 중복(스레드 id)        E6 작성자가 할 조치가 없음
  E7 작업 트리에서 읽은 사실(대상 SHA 아님)   E8 재검증에서 반박됨(반박 근거 인용)
커버리지         candidates(review.json `candidates` 가 가리키는 merged.json `candidates[].id` ∪ synthesized `issues[].id`)
                 ⊆ issues ∪ excluded ∪ covers. covers: 대상 id 는 candidates 에 실재 · 한 후보는 소유자 하나 · 소유자 id 는 covers 대상이 아니다.
                 excluded 의 covers 는 묶음 제외다(대상 id 를 모두 적는다)
GPT 패스         review.json 옆 `gpt-independent/` 가 있는데(GPT 독립 패스가 돌았다) merged.json 이 candidates 에 없으면 판정 불가 —
                 review.json `gptPass` 가 있으면 폴더보다 선언이 먼저다 — `independent` 면 merged.json 필수 · `challenger` · `none` 이면 묻지 않는다

사용: check_comment_worthy.py REVIEW_JSON   (렌더러 render_review.py 가 `check_review()` 를 import 한다)
exit: 0 PASS · 1 VIOLATION · 2 UNRUN(파일 · target · 후보 원본 부재 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from check_synthesized import normalize  # noqa: E402 — 두 생산자 모양을 같은 규칙으로 읽는다(F-530)

KINDS = ("bug", "structure", "quality", "intent-question")
ORIGINS = ("regression", "pre-existing", "improvement")    # workflows/peer-review.js finding 스키마 origin enum 과 같다
CODES = tuple(f"E{n}" for n in range(1, 9))
REPRO = ("reproduced", "code-determined")
EVIDENCE_RE = re.compile(r"(?s)^(?P<path>.+):(?P<a>\d+)(?:-(?P<b>\d+))?@(?P<sha>[0-9a-f]{7,40})$")   # 경로는 공백 · @ · : 를 가질 수 있다 — 끝의 :줄@sha 만 떼어 낸다
CLOSING_RE = re.compile(r"(?:(?:부탁드립니다|여쭙습니다)[.!]?|\?)\s*$")
NEAR = 3
SHA_RE = re.compile(r"[0-9a-f]{7,40}\Z")
BASE_SHA_FILE = "base-sha.txt"   # gather.sh 가 base/ 를 실제로 떠 온 커밋 — review.json 폴더(target.json 과 같은 자리)


def _same_sha(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def _txt(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def prose_lines(comment: str) -> list:
    out, fence = [], False
    for ln in comment.splitlines():
        if ln.strip().startswith("```"):
            fence = not fence
            continue
        if not fence and ln.strip():
            out.append(ln.strip())
    return out


def load_candidates(review: dict, base: pathlib.Path):
    """(후보 id 집합, 출처 목록, UNRUN 사유 | None)."""
    srcs = review.get("candidates")
    if not isinstance(srcs, list) or not srcs or not all(isinstance(s, str) and s for s in srcs):
        return None, [], "candidates(후보 원본 파일 목록 — merged.json · synthesized-issues.json)가 없다"
    ids, used = set(), []
    for rel in srcs:
        p = base / rel
        if not p.is_file():
            return None, used, f"후보 원본 {rel} 이 없다 — 어떤 후보가 처분됐는지 판정할 수 없다"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return None, used, f"후보 원본 {rel} 을 읽지 못했다 — {type(e).__name__}"
        shape, items, problems = normalize(data)
        if shape is None:
            return None, used, f"후보 원본 {rel} 의 모양을 모른다(issues[] · candidates[] 없음)"
        if problems:   # 깨진 후보를 버리고 남은 것만 세면 커버리지가 그 후보를 놓친다
            return None, used, f"후보 원본 {rel} 에 판정할 수 없는 항목 — {problems[0]}"
        ids |= {str(x["id"]) for x in items}
        used.append(rel)
    # 이번 실행의 GPT 경로를 review.json `gptPass` 로 밝혔으면(challenger · none) 남은 gpt-independent/ 로 병합본을 요구하지 않는다 —
    # 같은 작업 폴더에서 독립 패스 뒤 challenger 로 다시 돌린 경우다. 밝히지 않았으면 폴더가 안전망이다
    merged = any(pathlib.PurePath(r).name == "merged.json" for r in used)
    if review.get("gptPass") == "independent" and not merged:   # 선언이 폴더보다 먼저다
        return None, used, "gptPass=independent 인데 merged.json 이 후보 원본에 없다 — GPT 전용 후보의 처분을 볼 수 없다"
    if review.get("gptPass") not in ("challenger", "none", "independent") and (base / "gpt-independent").is_dir() and not merged:
        return None, used, "GPT 독립 패스가 돌았는데(gpt-independent/) merged.json 이 후보 원본에 없다 — GPT 전용 후보의 처분을 볼 수 없다"
    return ids, used, None


def threads_of(base: pathlib.Path):
    """(스레드 목록 | None, 대조 줄)."""
    p = base / "existing-threads.json"
    if not p.is_file():
        return None, "기존 스레드 대조 불가 — existing-threads.json 없음"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"기존 스레드 대조 불가 — existing-threads.json 읽기 실패({type(e).__name__})"
    st = d.get("status")
    if st != "ok":
        return None, f"기존 스레드 대조 불가 — status {st}" + (f" · {d.get('reason')}" if d.get("reason") else "")
    cs = [c for c in d.get("comments") or [] if isinstance(c, dict)]
    return cs, f"기존 스레드 {len(cs)}개와 대조"


def check_review(review: dict, base: pathlib.Path):
    """(code, 위반 목록, WARN 목록, 정보 {thread_line, candidates})."""
    bad, warn = [], []
    info = {"thread_line": "", "candidates": 0}
    tgt = review.get("target")
    sha = _txt(tgt.get("sha")).lower() if isinstance(tgt, dict) else ""
    if len(sha) < 7:
        return UNRUN, ["target.sha 가 없다 — evidence 의 @sha 를 대조할 기준이 없다(gather 의 target.json 을 review.json target 으로)"], warn, info
    cands, _, why = load_candidates(review, base)
    if why:
        return UNRUN, [why], warn, info
    info["candidates"] = len(cands)
    threads, info["thread_line"] = threads_of(base)
    issues = [i for i in review.get("issues") or [] if isinstance(i, dict)]
    excluded = review.get("excluded")
    if not isinstance(excluded, list):
        return VIOLATION, ["excluded 가 배열이 아니다"], warn, info
    # ⛔ regression 은 base 커밋에서 보인 근거가 필요하다(F-037) — evidence(@head)만으로는 '원래 없었다' 를 증명하지 못하고,
    #    base 를 낡은 로컬 develop 으로 읽으면 틀린 근거로 충족된다(F-240). 기준은 gather 가 base/ 를 뜬 커밋 하나다
    regress = [i for i in issues if i.get("origin") == "regression"]
    if regress:
        try:
            base_sha = (base / BASE_SHA_FILE).read_text(encoding="utf-8").strip().lower()
        except OSError:
            return UNRUN, [f"regression 이슈 {len(regress)}건인데 {BASE_SHA_FILE} 가 없다 — base 근거를 대조할 기준이 없다(gather 산출물)"], warn, info
        if not SHA_RE.match(base_sha):
            return UNRUN, [f"{BASE_SHA_FILE} 가 커밋 sha 꼴이 아니다 — {base_sha[:20]!r}"], warn, info
        meta = review.get("meta") if isinstance(review.get("meta"), dict) else {}
        msha = _txt(meta.get("base_sha")).lower()
        if not SHA_RE.match(msha):
            bad.append("meta.base_sha 가 없거나 커밋 sha 꼴이 아니다 — regression 근거의 기준 커밋")
        elif not _same_sha(msha, base_sha):
            bad.append(f"meta.base_sha {msha[:12]} ≠ {BASE_SHA_FILE} {base_sha[:12]} — gather 가 base/ 를 뜬 커밋이 아니다(F-037)")
        for i in regress:
            be = i.get("base_evidence")
            bes = [be] if isinstance(be, str) else ([x for x in be if isinstance(x, str)] if isinstance(be, list) else [])
            ms = [m for m in (EVIDENCE_RE.match(x.strip()) for x in bes) if m]
            if not ms:
                bad.append(f"{i.get('id')}: regression 은 base_evidence(`path:line@base-sha`)가 필요하다 — base 커밋에서 없던 것을 보인다(F-037)")
            elif not any(_same_sha(m["sha"].lower(), base_sha) for m in ms):
                bad.append(f"{i.get('id')}: base_evidence @sha 가 base {base_sha[:12]} 가 아니다 — head · 로컬 develop 근거는 regression 을 증명하지 못한다")
    # 강점은 string[] 그대로 · 원소마다 그 강점이 못 막는 시나리오(strengthGaps)를 둔다(F-117 · F-517)
    if "strengths" in review:
        st = review.get("strengths")
        if not isinstance(st, list) or not all(isinstance(s, str) for s in st):
            bad.append("strengths 는 string[] 이다 — 못 막는 시나리오는 strengthGaps[{claim, uncovered}] 에 둔다")
        else:
            gaps_raw = review.get("strengthGaps")
            if gaps_raw is not None and not isinstance(gaps_raw, list):
                bad.append("strengthGaps 가 배열이 아니다")
            gaps = {g["claim"].strip(): _txt(g.get("uncovered")) for g in (gaps_raw if isinstance(gaps_raw, list) else [])
                    if isinstance(g, dict) and isinstance(g.get("claim"), str)}
            for s in st:
                if s.strip() not in gaps:
                    bad.append(f"강점 {s.strip()[:30]!r} 에 strengthGaps 항목이 없다 — 이 강점이 못 막는 시나리오(uncovered)를 적는다")
                elif not gaps[s.strip()]:
                    bad.append(f"강점 {s.strip()[:30]!r} 의 strengthGaps.uncovered 가 비었다")
    owners = {}
    for kind, rows in (("issue", issues), ("excluded", excluded)):
        for x in rows:
            if not isinstance(x, dict):
                bad.append(f"{kind} 항목이 객체가 아니다")
                continue
            xid = str(x.get("id"))
            for t in [xid] + [str(c) for c in x.get("covers") or []]:
                if t == xid and t not in cands:
                    continue   # 새로 만든 id(묶음 · 질문)는 후보에 없어도 된다
                if t in owners and owners[t] != xid:   # 같은 항목이 자기 id 를 covers 에도 적은 것은 이중 소유가 아니다
                    bad.append(f"covers 이중 소유 — 후보 {t} 를 {owners[t]} 와 {xid} 가 함께 가진다")
                owners[t] = xid
            for c in x.get("covers") or []:
                if str(c) not in cands:
                    bad.append(f"{xid}.covers — {c} 는 후보에 없다(댕글링)")
    covered_by = {(str(c), str(x.get("id"))) for rows in (issues, excluded) for x in rows if isinstance(x, dict) for c in x.get("covers") or []}
    for rows in (issues, excluded):
        for x in rows:
            xid = str(x.get("id")) if isinstance(x, dict) else None
            if xid and any(t == xid and o != xid for t, o in covered_by):
                bad.append(f"{xid} — 소유자 id 가 다른 항목의 covers 대상이다(순환)")
    lost = sorted(cands - set(owners))
    if lost:
        bad.append(f"조용히 사라진 후보 {len(lost)}건 — {', '.join(lost[:6])} · issues · excluded · covers 어디에도 없다")
    for i in issues:
        iid = i.get("id")
        k = i.get("kind")
        if k not in KINDS:
            bad.append(f"{iid}: kind 는 {' · '.join(KINDS)} 중 하나다 — {k!r}")
        ev = [e for e in i.get("evidence") or [] if isinstance(e, str)]
        pinned = [m for m in (EVIDENCE_RE.match(e.strip()) for e in ev) if m]
        if not pinned:
            bad.append(f"{iid}: evidence 에 `path:line@sha` 가 없다")
        elif not any(sha.startswith(m["sha"]) or m["sha"].startswith(sha) for m in pinned):
            bad.append(f"{iid}: evidence @sha 가 리뷰 대상 {sha[:12]} 와 다르다 — 작업 트리에서 읽은 사실이면 E7")
        if k == "bug":
            r = i.get("repro") if isinstance(i.get("repro"), dict) else {}
            if r.get("status") not in REPRO or not _txt(r.get("how")):
                bad.append(f"{iid}: bug 는 repro{{status: {' | '.join(REPRO)}, how}} 가 필요하다 — 미재현이면 질문으로 내리거나 E1")
            if not (_txt(i.get("symptom_screen")) and _txt(i.get("symptom_reach"))):
                bad.append(f"{iid}: bug 는 symptom_screen · symptom_reach 가 필요하다(Gate 4.7-S)")
        if k in ("structure", "quality") and not _txt(i.get("measure")):
            bad.append(f"{iid}: {k} 제안은 measure(관례 표본 N:M · 중복 줄 수 · 결함 위험)가 필요하다 — 없으면 E3")
        if i.get("origin") not in ORIGINS:
            # ⛔ 어휘를 닫는다 — 'Regression' · 'new-code' 처럼 적으면 regression 의 base 근거 검사(F-037)를 통째로 건너뛴다
            bad.append(f"{iid}: origin {i.get('origin')!r} 은 정본 어휘({' · '.join(ORIGINS)}) 밖이다")
        elif i.get("origin") == "pre-existing":
            bad.append(f"{iid}: origin 이 pre-existing — 원래 있던 문제는 E4 로 제외한다(리포트 ④)")
        if k != "intent-question" and not _txt(i.get("suggestion")):
            bad.append(f"{iid}: suggestion 이 없다 — 작성자가 할 조치가 없으면 E6")
        if not _txt(i.get("refute")):
            bad.append(f"{iid}: refute(재검증 기록 — 반박 시도와 결과)가 없다")
        pl = prose_lines(_txt(i.get("comment")))
        if not pl:
            bad.append(f"{iid}: comment 가 없다")
        elif len(pl) > 4:
            bad.append(f"{iid}: comment 산문 {len(pl)}줄 > 4 — 근거는 evidence 로 옮긴다")
        elif not CLOSING_RE.search(pl[-1]):
            warn.append(f"{iid}: comment 마무리 어조(…부탁드립니다 · …여쭙습니다 · 질문)가 없다")
        if i.get("duplicateOf"):
            bad.append(f"{iid}: duplicateOf 가 있는 항목은 코멘트가 아니다 — E5 로 제외한다")
        if threads:
            ds = {str(d.get("thread")) for d in i.get("distinctFrom") or [] if isinstance(d, dict) and _txt(d.get("why"))}
            for s in i.get("sites") or []:
                if not isinstance(s, dict):
                    continue
                for t in threads:
                    ln = t.get("line") or t.get("original_line")
                    a = s.get("start")
                    b = s.get("end") if isinstance(s.get("end"), int) else a
                    if t.get("path") == s.get("path") and isinstance(ln, int) and isinstance(a, int) \
                            and a - NEAR <= ln <= b + NEAR and str(t.get("id")) not in ds:
                        bad.append(f"{iid}: 기존 스레드 {t.get('id')}({t.get('path')}:{ln}) 근처다 — E5(duplicateOf) 로 빼거나 distinctFrom[{{thread, why}}]")
    for x in excluded:
        if not isinstance(x, dict):
            continue
        xid = x.get("id")
        if x.get("code") not in CODES:
            bad.append(f"excluded {xid}: code 는 E1~E8 이다 — {x.get('code')!r}")
        if not _txt(x.get("reason")):
            bad.append(f"excluded {xid}: reason 이 없다")
        if x.get("code") == "E5" and not x.get("duplicateOf"):
            bad.append(f"excluded {xid}: E5 는 duplicateOf(스레드 id)가 필요하다")
        if x.get("code") == "E8" and not _txt(x.get("refute")):
            bad.append(f"excluded {xid}: E8 은 refute(반박 근거)가 필요하다")
    return (VIOLATION if bad else OK), bad, warn, info


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    SHA = "abc1234def5678"
    BSHA = "0123456789abcdef0123456789abcdef01234567"   # base-sha.txt — gather 가 base/ 를 뜬 커밋
    MERGED = {"inputs": {"claude": 2, "gpt": 1, "gptUnavailable": None, "evidenceChecked": True},
              "candidates": [{"id": "claude:C1", "source": "claude", "severity": "major"},
                             {"id": "claude:C2", "source": "claude", "severity": "minor", "origin": "pre-existing"},
                             {"id": "gpt:G1", "source": "gpt", "severity": "minor"}],
              "summary": {"candidatesIn": 3, "candidatesOut": 3}}
    ISSUE = {"id": "A1", "kind": "bug", "severity": "major", "origin": "regression", "covers": ["claude:C1"],
             "evidence": [f"src/a.swift:11-12@{SHA[:7]}"], "base_evidence": f"src/a.swift:11@{BSHA[:7]}", "repro": {"status": "code-determined", "how": "nil 경로"},
             "symptom_screen": "목록", "symptom_reach": "탭 → 목록", "suggestion": "guard 추가", "refute": "반박 실패 — 호출 1곳",
             "comment": "nil 이면 목록이 비어 보입니다.\nguard 를 두면 좋겠습니다. 확인 부탁드립니다.",
             "sites": [{"path": "src/a.swift", "start": 11, "end": 12}]}
    BASE = {"verdict": "v", "target": {"kind": "pr", "ref": "pr-1", "sha": SHA}, "meta": {"base_sha": BSHA}, "candidates": ["merged.json"],
            "issues": [ISSUE],
            "excluded": [{"id": "claude:C2", "what": "원래 있던 문제", "code": "E4", "reason": "base 에도 같다"},
                         {"id": "gpt:G1", "what": "SDK 가정", "code": "E2", "reason": "SDK 내부 동작 가정"}]}
    with tempfile.TemporaryDirectory() as t:
        seq = [0]

        def run(review, merged=MERGED, threads=None, gpt_dir=False, extra=None, base_sha=BSHA, cli=False):
            seq[0] += 1
            d = pathlib.Path(t) / f"c{seq[0]}"
            d.mkdir()
            if base_sha is not None:
                (d / BASE_SHA_FILE).write_text(base_sha + "\n", encoding="utf-8")
            for name, obj in (extra or {}).items():
                (d / name).write_text(json.dumps(obj), encoding="utf-8")
            if merged is not None:
                (d / "merged.json").write_text(json.dumps(merged), encoding="utf-8")
            if threads is not None:
                (d / "existing-threads.json").write_text(json.dumps(threads), encoding="utf-8")
            if gpt_dir:
                (d / "gpt-independent").mkdir()
            if cli:   # 실제 CLI — 기본 경로(플래그 없이 review.json 폴더의 base-sha.txt)를 사용자가 부르는 꼴로 잰다
                (d / "review.json").write_text(json.dumps(review), encoding="utf-8")
                return subprocess.run([sys.executable, os.path.abspath(__file__), str(d / "review.json")],
                                      capture_output=True, text=True).returncode, [], [], {}
            return check_review(json.loads(json.dumps(review)), d)

        def mod(**kw):
            r = json.loads(json.dumps(BASE))
            for k, v in kw.items():
                r[k] = v
            return r

        def mi(**kw):
            i = json.loads(json.dumps(ISSUE))
            for k, v in kw.items():
                if v is None:
                    i.pop(k, None)
                else:
                    i[k] = v
            return mod(issues=[i])

        case("curated-ok", run(BASE)[0] == OK, run(BASE)[1])
        case("candidate-lost", run(mod(excluded=BASE["excluded"][:1]))[0] == VIOLATION)
        case("covers-dangling", run(mi(covers=["claude:C1", "claude:NOPE"]))[0] == VIOLATION)
        case("covers-double-owner", run(mod(excluded=BASE["excluded"] + [{"id": "B1", "what": "w", "code": "E3", "reason": "취향", "covers": ["claude:C1"]}]))[0] == VIOLATION)
        case("self-cover-not-double", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E4", "reason": "r", "covers": ["claude:C2"]},
                                                        BASE["excluded"][1]]))[0] == OK)
        case("covers-cycle", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E4", "reason": "r", "covers": ["gpt:G1"]},
                                               {"id": "B2", "what": "w", "code": "E3", "reason": "r", "covers": ["claude:C2"]}]))[0] == VIOLATION)
        case("evidence-missing", run(mi(evidence=None))[0] == VIOLATION)
        case("evidence-path-with-space", run(mi(evidence=["Sources/My View.swift:11@abc1234"]))[0] == OK)
        case("malformed-candidate-unrun", run(BASE, merged={"candidates": [{"id": "claude:C1", "severity": "major"}, None]})[0] == UNRUN)
        case("site-end-null-near-thread", run(mi(sites=[{"path": "src/a.swift", "start": 11, "end": None}]),
                                              threads={"status": "ok", "comments": [{"id": 77, "path": "src/a.swift", "line": 13}]})[0] == VIOLATION)
        case("evidence-sha-mismatch", run(mi(evidence=["src/a.swift:11@fff0000"]))[0] == VIOLATION)
        case("bug-needs-repro", run(mi(repro={"status": "not-reproduced", "how": "x"}))[0] == VIOLATION)
        case("bug-needs-symptom", run(mi(symptom_reach=None))[0] == VIOLATION)
        case("structure-needs-measure", run(mi(kind="structure", repro=None))[0] == VIOLATION)
        case("structure-with-measure-ok", run(mi(kind="structure", repro=None, measure="관례 4:1"))[0] == OK)
        case("preexisting-not-comment", run(mi(origin="pre-existing"))[0] == VIOLATION)
        case("question-no-suggestion-ok", run(mi(kind="intent-question", repro=None, suggestion=None, comment="의도가 X 인지 여쭙습니다"))[0] == OK)
        case("needs-refute", run(mi(refute=None))[0] == VIOLATION)
        case("comment-too-long", run(mi(comment="1\n2\n3\n4\n5"))[0] == VIOLATION)
        case("comment-fence-not-counted", run(mi(comment="a\n```\nx\ny\nz\nw\n```\n부탁드립니다"))[0] == OK)
        r = run(mi(comment="첫 줄\n둘째 줄"))
        case("closing-tone-warn", r[0] == OK and len(r[2]) == 1, r)
        case("duplicate-is-not-comment", run(mi(duplicateOf="T9"))[0] == VIOLATION)
        th = {"status": "ok", "comments": [{"id": 77, "path": "src/a.swift", "line": 13}]}
        case("near-thread-needs-disposition", run(BASE, threads=th)[0] == VIOLATION)
        case("near-thread-distinct-ok", run(mi(distinctFrom=[{"thread": 77, "why": "다른 줄 다른 결함"}]), threads=th)[0] == OK)
        case("threads-unavailable-line", "status unavailable" in run(BASE, threads={"status": "unavailable", "reason": "gh 실패"})[3]["thread_line"])
        case("e5-needs-duplicate-of", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E5", "reason": "r"}, BASE["excluded"][1]]))[0] == VIOLATION)
        case("e8-needs-refute", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E8", "reason": "r"}, BASE["excluded"][1]]))[0] == VIOLATION)
        case("bad-code", run(mod(excluded=[{"id": "claude:C2", "what": "w", "code": "E9", "reason": "r"}, BASE["excluded"][1]]))[0] == VIOLATION)
        case("no-target-unrun", run(mod(target=None))[0] == UNRUN)
        case("merged-missing-unrun", run(BASE, merged=None)[0] == UNRUN)
        case("evidence-path-with-newline", run(mi(evidence=["Sources/a\nb.swift:11@abc1234"]))[0] == OK)
        case("stale-gpt-dir-challenger-ok", run(mod(candidates=["syn.json"], gptPass="challenger"), merged=None, gpt_dir=True, extra={"syn.json": MERGED})[0] == OK)
        case("declared-independent-without-merged-unrun", run(mod(candidates=["syn.json"], gptPass="independent"), merged=None, extra={"syn.json": MERGED})[0] == UNRUN)
        case("stale-gpt-dir-undeclared-unrun", run(mod(candidates=["syn.json"]), merged=None, gpt_dir=True, extra={"syn.json": MERGED})[0] == UNRUN)
        case("gpt-ran-without-merged-unrun", run(mod(candidates=["syn.json"]), merged=None, gpt_dir=True)[0] == UNRUN)
        # F-037 — regression 의 base 근거
        case("regression-without-base-evidence", run(mi(base_evidence=None))[0] == VIOLATION)
        case("regression-base-evidence-head-sha-rejected", run(mi(base_evidence=f"src/a.swift:11@{SHA[:7]}"))[0] == VIOLATION)
        case("regression-base-evidence-local-develop-rejected", run(mi(base_evidence="src/a.swift:11@feedfacecafe"))[0] == VIOLATION)
        r = run(BASE)
        case("regression-base-evidence-ok", r[0] == OK and not r[1], r[1])
        case("base-sha-default-review-dir", run(BASE, cli=True)[0] == OK and run(BASE, base_sha="feedfacecafe00", cli=True)[0] == VIOLATION)
        case("base-sha-missing-unrun", run(BASE, base_sha=None)[0] == UNRUN and run(mi(origin="improvement"), base_sha=None)[0] == OK)
        case("origin-outside-vocabulary-rejected", run(mi(origin="Regression"))[0] == VIOLATION and run(mi(origin="new-code"))[0] == VIOLATION)
        wrong = mi(base_evidence="src/a.swift:11@2222222")
        wrong["meta"] = {"base_sha": "2222222222222222"}
        case("meta-and-evidence-both-wrong-rejected", run(wrong)[0] == VIOLATION and run(wrong, cli=True)[0] == VIOLATION)
        # F-117 · F-517 — 강점이 못 막는 시나리오
        case("strength-gap-missing", run(mod(strengths=["범위가 맞다"]))[0] == VIOLATION)
        case("strength-gap-empty-uncovered", run(mod(strengths=["범위가 맞다"], strengthGaps=[{"claim": "범위가 맞다", "uncovered": " "}]))[0] == VIOLATION)
        r = run(mod(strengths=["범위가 맞다"], strengthGaps=[{"claim": "범위가 맞다", "uncovered": "동시 호출 경로는 이 PR 이 막지 않는다"}]))
        case("strength-gap-ok", r[0] == OK, r[1])
        case("strengths-string-array-kept", run(mod(strengths=[{"claim": "범위가 맞다"}], strengthGaps=[{"claim": "범위가 맞다", "uncovered": "u"}]))[0] == VIOLATION
             and r[0] == OK)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("review", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.review:
        print("UNRUN: REVIEW_JSON 이 필요하다", file=sys.stderr)
        return UNRUN
    p = pathlib.Path(a.review)
    try:
        review = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"UNRUN: 읽기 실패 — {type(e).__name__}: {e}", file=sys.stderr)
        return UNRUN
    if not isinstance(review, dict) or "excluded" not in review:
        print("UNRUN: excluded 키가 없다 — 큐레이션하지 않은 리뷰다", file=sys.stderr)
        return UNRUN
    code, bad, warn, info = check_review(review, p.parent)
    print(f"코멘트 가치 — issues {len(review.get('issues') or [])} · excluded {len(review.get('excluded') or [])} · 후보 {info['candidates']} · {info['thread_line']}")
    for b in bad:
        print(f"  ✗ {b}")
    for w in warn:
        print(f"  WARN {w}")
    return code


if __name__ == "__main__":
    sys.exit(main())
