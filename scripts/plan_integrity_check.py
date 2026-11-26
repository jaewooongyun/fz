#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 검사 대상 JSON 과 fixture 디렉토리를 인자로
#   받고, 문서 경로는 주석 인용뿐이다 (lint #N6 면제 형태 c).
"""plan_integrity_check.py — plan-collaborative 반환의 **참조 무결성**을 본다. 구조 검사다.

⛔ 이 스크립트가 재는 것과 아닌 것 (이름이 과대 주장하지 않도록 명시 — GPT verify #7):
  재는 것: 문서 **내부 참조**가 서로를 가리키는가 —
    · `rtm[].stepId` 가 `steps[].id` 에 있는가        (계획이 자기 Step 을 가리키는가)
    · CC `links[].sourceId` 가 `edgeCases[].id` 에 있는가 (교차가 실재하는 케이스를 가리키는가)
    · `readScope` · `writeScope[].file` 한 항목에 경로가 하나인가(F-599 — 묶음이면 분해 제안을 내고 실패한다)
    · `writeScope[].file` 이 `readScope` 안에 있는가   (⛔ 읽지도 않은 파일을 고치기로 하지 않았는가)
      — 단 **신규 생성 파일은 면제**한다. 존재하지 않는 파일은 읽을 수 없으므로 readScope 에 있을 수 없다.
        ⛔ 이 면제가 없던 1차 판에서 실제 플랜(TKT-0101)의 신규 3파일이 위반으로 뜨는 오탐이 있었다
        (2026-09-11 실데이터 대조로 발견 — fixture 만으로는 드러나지 않았다). 면제 조건은
        rationale·file 에 `신규`/`new` 표기가 있는 것이며, 표기 없는 범위 밖 파일은 여전히 위반이다.
    · `steps[].verify` 가 VerifySpec 계약을 지키는가   (command=criterion+command+expect · manual=criterion · 선택 칸 pin=command 의 경로 배열)
    · id 가 유일한가                                    (중복은 개수 검사를 무력화한다)
  `--plan-doc` (plan 마크다운 — plan-v{N} · plan-final) 에서 재는 것(round 2 S17):
    · `경로:줄` 바로 뒤 따옴표 인용이 그 원문 줄과 같은가(F-432 — 렌즈가 규칙을 반대로 인용했다 · `--root` 가 있을 때)
    · "F-NNN 이 기록한" 꼴 근거 문장의 문단에 엔트리 원문 줄 포인터(`entries/F-NNN-*.md:줄`)가 있는가(F-453 — 기억으로 인용했다)
    · 보강 표지 `⊕` 가 남았는가 · Step 제목 id 가 겹치는가(F-315 — 중간본도 단일 최신 상태로 접는다)
    · (WARN) 수치 주장의 출처(F-185) · '0건 · 없다 · 미발견' 주장의 같은 줄 대조값(F-611 · F-726) ·
      위험 표 완화 칸의 '결정 · decided · expected by decision' 주장의 같은 행 결정 출처(F-636)
  ⛔ 재지 못하는 것: 계획이 **요구사항을 충족하는가** · 그 파일이 실제로 존재하는가 ·
     verify 가 제목이 말하는 것을 측정하는가. 앞의 둘은 Lead·GPT 판정이고, 마지막은
     `gpt-exec.sh verify-gates` 의 measurement_fit 축이다.

입력: `plan-collaborative.js` 반환 JSON (`plan` + `lensOutputs`). ⛔ `lensOutputs` 가 없으면
  CC 참조 검사는 **skip 이 아니라 'unavailable' 로 보고**한다 — 볼 수 없었던 것을 통과로 쓰지 않는다.

exit: 0=전부 충족 / 1=위반 또는 입력 결함(측정 실패) / 2=사용법
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

VERIFY_REQUIRED = {"command": ("criterion", "command", "expect"), "manual": ("criterion",)}
# 신규 생성 표기 — 이 표기가 있으면 readScope 포함 검사를 면제하고 note 로만 남긴다.
NEW_FILE_MARKERS = ("신규", "new file", "New file", "(new)", "생성")


def _path_head(raw) -> str:
    """범위 항목에서 설명(`— 설명` · `(설명)`) · 백틱 · `§X ` 를 뗀 경로 자리 원문."""
    t = str(raw).strip().strip("`")
    t = re.split(r"\s+[—–-]\s+|\s+\(", t)[0].strip().strip("`")
    return re.sub(r"^§\S+\s*", "", t).strip()


def norm_path(raw: str) -> str:
    """readScope 항목은 순수 경로가 아니다 — `경로 — 설명`·`§X 경로`·백틱 포함 형태가 섞인다.
    ⛔ 문자열 동일성으로 비교하면 전부 위반으로 뜬다(GPT verify #7). 경로 토큰만 뽑아 정규화한다."""
    t = _path_head(raw).lstrip("./").rstrip("/")
    return os.path.normpath(t) if t else ""


SCOPE_SEP_CHARS = ",;·、"
_SEG = r"[A-Za-z0-9_.@+~${}-]+(?: [A-Za-z0-9_.@+~${}-]+)*"     # 경로 마디 — 마디 안 공백 하나씩은 허용(`My File.swift`)
PATH_PIECE = re.compile(rf"({_SEG}(?:/{_SEG})*/?)(?::\d+(?:[-–]\d+)?)?\Z")
PATH_EXT = re.compile(r"\.[A-Za-z]\w{0,5}/?\Z")
BRACE_ALT = re.compile(r"\{([^{}]*,[^{}]*)\}")


def _complete_path(p: str) -> bool:
    m = PATH_PIECE.match(p)
    return bool(m) and "/" in m.group(1).strip("/") and (PATH_EXT.search(m.group(1)) is not None or m.group(1).endswith("/"))


def _scope_tokens(head: str) -> list:
    """구분자(쉼표 · 세미콜론 · 가운뎃점)로 자른다 — `{a,b}` 안의 쉼표는 자르지 않는다(중괄호 전개 꼴).
    공백은 셋으로 가른다: 조각이 모두 완결 경로(`/` 를 품고 `.확장자` · `/` 로 끝남)면 자른다(`a/x.py b/y.py`) · 덩어리 전체가
    공백 든 경로 하나로 읽히면(`Sources/My File.swift`) 자르지 않는다 · 그 밖(경로 + 낱말 · `§3 c.md`)은 공백으로 자른다.
    - Note: 산문이 낀 덩어리(`docs/x.md and src/y.md`)는 공백 든 경로 하나로 읽혀 묶음을 놓칠 수 있다 — 실제 공백 경로를 둘로 쪼개는
      거짓 위반(하드 실패)보다 놓침(경고 없음) 쪽을 골랐다."""
    chunks, buf, depth = [], "", 0
    for ch in head + ",":
        depth = max(0, depth + (ch == "{") - (ch == "}"))
        if depth == 0 and ch in SCOPE_SEP_CHARS:
            if buf.strip().strip("`").strip():
                chunks.append(buf.strip().strip("`").strip())
            buf = ""
        else:
            buf += ch
    out = []
    for c in chunks:
        parts = [p.strip("`") for p in c.split() if p.strip("`")]
        if len(parts) > 1 and not all(_complete_path(p) for p in parts) and "/" in c and PATH_PIECE.match(c):
            out.append(c)
        else:
            out.extend(parts)
    return out


def _expand_braces(tok: str) -> list:
    m = BRACE_ALT.search(tok)
    if not m:
        return [tok]
    return [y for alt in m.group(1).split(",") for y in _expand_braces(tok[:m.start()] + alt.strip() + tok[m.end():])]


def bundled_paths(raw) -> list:
    """F-599 — 범위 항목 하나의 경로 자리에 경로가 둘 이상 묶였으면 그 경로들(적힌 그대로 · 분해 제안용) · 아니면 [].

    경로 꼴 조각(`/` 를 품거나 `.확장자` 로 끝나는 ASCII 토큰 · 뒤 `:줄` 은 뗀다)만 센다 — `§3` · `L10` · 낱말은 경로가 아니라 묶음이 아니다.
    설명(`— …`)은 먼저 떼므로 설명 속 쉼표는 묶음이 아니다. `dir/{a,b}/x.md` 는 전개해 센다.
    ⛔ 분해는 제안일 뿐 통과 근거가 아니다 — 구분자 추측이 reader 마다 갈리면(F-576) 같은 반환이 도구마다 다르게 읽힌다.
       호출자는 묶음을 위반으로 내고, Lead 가 목록을 고쳐 다시 넣어 포함 관계를 다시 잰다.
    """
    pieces = [e for t in _scope_tokens(_path_head(raw)) for e in _expand_braces(t)]
    paths = [m.group(1) for m in (PATH_PIECE.match(x) for x in pieces)
             if m and ("/" in m.group(1).strip("/") or PATH_EXT.search(m.group(1)))]
    return paths if len(paths) > 1 else []


def _bundle_violation(field: str, raw, parts: list) -> str:
    return (f"{field} 항목 하나에 경로 {len(parts)}개가 묶였다 — {str(raw)[:120]!r} → 분해 제안: "
            f"{json.dumps(parts, ensure_ascii=False)} (한 항목 = 경로 하나로 고쳐 다시 넣는다 · 포함 관계는 고친 목록으로 다시 잰다)")


def check(doc: dict) -> tuple:
    """반환 (violations, notes). notes 는 'unavailable' 류 관측(통과가 아니다)."""
    v, notes = [], []
    plan = doc.get("plan")
    if not isinstance(plan, dict):
        return ["plan 객체가 없다 (입력 결함 — 측정 실패)"], notes

    steps = plan.get("steps") or []
    ids = [s.get("id") for s in steps if isinstance(s, dict)]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        v.append(f"steps.id 중복: {sorted(dup)}")
    id_set = {i for i in ids if i}
    if not id_set:
        v.append("steps.id 가 하나도 없다 (0/0 통과 금지)")

    # ① verify 계약
    for s in steps:
        if not isinstance(s, dict):
            v.append("steps 항목이 객체가 아니다")
            continue
        ver = s.get("verify")
        sid = s.get("id", "?")
        if not isinstance(ver, dict):
            v.append(f"{sid}: verify 객체 없음")
            continue
        kind = ver.get("kind")
        if kind not in VERIFY_REQUIRED:
            v.append(f"{sid}: verify.kind 가 command|manual 이 아니다 ({kind!r})")
            continue
        for key in VERIFY_REQUIRED[kind]:
            if not str(ver.get(key) or "").strip():
                v.append(f"{sid}: verify({kind}) 에 {key} 누락")
        pin = ver.get("pin")                            # F-622 — 원장 PIN 으로 옮겨지는 선택 칸(gate_check.py pin_of 와 같은 규칙)
        if pin not in (None, []):
            if kind != "command":
                v.append(f"{sid}: verify.pin 은 kind=command 에서만 — 수동 게이트는 명령을 돌리지 않는다")
            elif not isinstance(pin, list) or any(not isinstance(x, str) or not x.strip() or any(c in x for c in ",\n\r") for x in pin):
                v.append(f"{sid}: verify.pin 은 경로 문자열 배열이다(빈 항목 · 쉼표 · 개행 금지 — 원장 PIN 은 쉼표로 나눠 읽는다) — {pin!r}")

    # ② rtm → steps
    rtm = plan.get("rtm") or []
    for row in rtm:
        if not isinstance(row, dict):
            v.append("rtm 항목이 객체가 아니다")
            continue
        sid = row.get("stepId")
        # 한 행이 여러 Step 을 가리키는 표기(`S1,S2` · `S1·S2`)를 허용한다 — 실측 형태다
        refs = [t.strip() for t in re.split(r"[,·/]| and ", str(sid or "")) if t.strip()]
        if not refs:
            v.append(f"rtm({row.get('reqId', '?')}): stepId 비어 있음")
        for r in refs:
            if r not in id_set:
                v.append(f"rtm({row.get('reqId', '?')}): stepId {r!r} 가 steps.id 에 없다")

    # ③ writeScope ⊆ readScope
    # F-599 — 묶음 항목은 위반이다(통과시키지 않는다). 포함 관계는 분해 제안 기준으로 함께 잰다 — 묶음 때문에 생긴 거짓 위반은 빠지고
    #   나머지 포함 관계 위반은 그대로 남는다. 어느 쪽이든 묶음 위반이 있으니 exit 1 이다
    read = set()
    for x in plan.get("readScope") or []:
        parts = bundled_paths(x)
        if parts:
            v.append(_bundle_violation("readScope", x, parts))
            read.update(norm_path(p) for p in parts)
        elif norm_path(x):
            read.add(norm_path(x))
    new_exempt = []
    for w in plan.get("writeScope") or []:
        if not isinstance(w, dict):
            v.append("writeScope 항목이 객체가 아니다")
            continue
        f = norm_path(w.get("file"))
        blob = f"{w.get('file') or ''} {w.get('rationale') or ''}"
        is_new = any(m in blob for m in NEW_FILE_MARKERS)
        parts = bundled_paths(w.get("file"))
        if parts:                                       # 묶음은 신규 표기 면제보다 먼저 — 묶인 신규 파일이 면제로 빠져나가지 않는다
            v.append(_bundle_violation("writeScope.file", w.get("file"), parts))
        elif not f:
            v.append("writeScope 에 file 이 비어 있다")
        elif read and f not in read:
            if is_new:
                new_exempt.append(os.path.basename(f) or f)
            else:
                v.append(f"writeScope {f!r} 가 readScope 에 없다 (읽지 않은 파일을 변경 대상으로 둠 — 신규면 rationale 에 '신규' 를 표기하라)")
    if new_exempt:
        notes.append(f"신규 생성 표기로 readScope 포함 검사 면제 {len(new_exempt)}건: {', '.join(new_exempt[:5])}")
    if not read:
        notes.append("readScope 가 비어 있어 writeScope 포함 관계는 unavailable")

    # ④ CC links → edgeCases.id  (lensOutputs 필요)
    lens = doc.get("lensOutputs")
    if not isinstance(lens, dict):
        notes.append("lensOutputs 없음 — CC 참조 검사 unavailable (plan-collaborative S5a 이전 산출)")
    else:
        edge = (lens.get("edge") or {}).get("edgeCases") or []
        case_ids = {e.get("id") for e in edge if isinstance(e, dict) and e.get("id")}
        if not case_ids:
            notes.append("edgeCases 가 비어 있어 CC 참조는 unavailable")
        for tag in ("impactOnEdge", "edgeOnImpact"):
            cc = lens.get(tag)
            if not isinstance(cc, dict):
                continue
            for l in cc.get("links") or []:
                if not isinstance(l, dict):
                    v.append(f"{tag}.links 항목이 객체가 아니다")
                    continue
                src = l.get("sourceId")
                if case_ids and src not in case_ids:
                    v.append(f"{tag}: sourceId {src!r} 가 edgeCases.id 에 없다")
    return v, notes


# ── plan 문서(마크다운) 검사 — round 2 S17 ────────────────────────────────
QUOTE_AFTER_REF = re.compile(r"`?([\w./-]+\.[A-Za-z]\w{0,5}):(\d+)`?[\s—–:·-]{0,4}[\"“「]([^\"”」\n]{4,})[\"”」]")
FINDING_CLAIM = re.compile(r"F-(\d{3})\s*(?:이|가|은|는|의)?\s*(?:기록한|지목한|적은|보고한|남긴|에 따르면|에 기록된)")
STEP_HEADING = re.compile(r"^#{2,4}\s+(S\d+[a-z]?)\b", re.M)
AMEND_MARK = "⊕"
COUNT_CLAIM = re.compile(r"(?<![\w.-])\d[\d,.]*\s?(?:건|개(?!월)|곳|줄|행|파일|회|번|배|초|%|토큰|케이스|셀)")   # 단위 뒤 조사 · 서술어는 붙는다(12개다)
PATH_LINE_CLAIM = re.compile(r"[\w./-]+\.[A-Za-z]\w{0,5}:\d+")
CLAIM_EVIDENCE = re.compile(r"\[verified:|code-context(?:\.md)?(?::\d+|#[\w-]+)")
# '0건 · 없다 · 미발견' 부재 주장 — `10건` 의 0 · `잴 수 없다`(능력) · `필요 없다`(결정)는 부재 주장이 아니다
ABSENCE_CLAIM = re.compile(r"(?<![\d.,])0\s?건|(?<!수 )(?<!필요 )없다(?![가-힣])|미발견")
# 대조값 = 단위가 붙은 양수 적중 수가 든 표지 — 양성 대조는 적중이 1 이상이다(빈 `[대조:]` · `저장소 전체에서 0건` ·
#   F-번호 · `a.py:12` 같은 숫자만 든 표지는 대조값이 아니다)
_POS_HIT = r"(?<![\w.:-])[1-9][\d,]*\s?(?:건|개(?!월)|곳|줄|행|파일|회|번|케이스|셀)"
CONTROL_VALUE = re.compile(rf"\[대조:[^\]]*{_POS_HIT}|(?:양성 대조|저장소 전체)[^\n]*?{_POS_HIT}")
# F-636 — 위험 표의 완화 칸(머리 '완화 · Mitigation' · fz 계획의 위험 표가 가장 많이 쓰는 '대응')의 '결정됨' 주장.
# 한국어는 결정이 끝난 꼴만 잡는다 — 맨 '결정' 은 실측 계획에서 '…갈지 결정' · '사용자 결정(…)' 같은 미결 꼴이었다. 결정론 · 결정적도 아니다
MITIGATION_HEAD = re.compile(r"(?i)완화|mitigation|대응")
DECIDED_CLAIM = re.compile(r"(?i)\bdecided\b|\bby decision\b|결정(?:됨|됐|된|되었|했|함|대로|에\s?따|\s?사항|의 결과)")
# 미결 표기 — F-636 이 처방한 '미결 — 사용자 결정' · 고친 행의 'NOT decided … user decides' 는 결정 주장이 아니다
NOT_DECIDED = re.compile(r"(?i)\bnot\s+(?:yet\s+)?decided\b|\bundecided\b|\b(?:to|will) be decided\b|미결|결정되지|결정 ?전|결정할|결정해야|결정 필요|결정 대기")
# 결정 출처 — 문서 · 기록 파일의 `파일:줄`(코드 `파일:줄` 은 위험이 사는 자리라 결정 출처가 아니다) · 따옴표 원문 인용(4글자 이상)
DECISION_SOURCE = re.compile(r"[\w./-]+\.(?:md|markdown|txt|rst|adoc|tsv|csv|jsonl?|ya?ml|log):\d+|[\"“「][^\"”」\n]{4,}[\"”」]")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\*\*|`", "", s)).strip()


def _lines_of(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().split("\n")
    except (OSError, UnicodeDecodeError):
        return None


def check_doc(text: str, root=None, findings=None) -> tuple:
    """plan 마크다운 — (violations, notes). root · findings 가 없으면 그 대조는 unavailable 로 남긴다(통과가 아니다)."""
    v, notes = [], []
    quoted = 0
    for m in QUOTE_AFTER_REF.finditer(text):           # F-432 — 인용은 원문 줄과 글자가 같아야 한다(의역은 따옴표에 넣지 않는다)
        path, line, quote = m.group(1), int(m.group(2)), m.group(3)
        quoted += 1
        reg = re.match(r"(?:.*/)?entries/(F-\d{3}.*)$", path)   # 레지스트리 포인터는 --findings-dir 기준이다
        base, rel = (findings, reg.group(1)) if reg else (root, path)
        if not base:
            continue
        lines = _lines_of(os.path.join(base, rel))
        if lines is None:
            v.append(f"인용 대상을 열 수 없다: {path}:{line}")
            continue
        window = _flat(" ".join(lines[max(0, line - 1):line + 2]))
        if _flat(quote) not in window:
            src = _flat(lines[line - 1]) if 0 < line <= len(lines) else "(줄 없음)"
            v.append(f"{path}:{line} 인용이 원문과 다르다 — 인용 {quote[:60]!r} · 원문 {src[:80]!r}")
    if quoted and not (root and findings):
        notes.append(f"따옴표 인용 {quoted}건 — --root · --findings-dir 중 없는 쪽의 원문 대조 unavailable")
    for para in re.split(r"\n\s*\n", text):           # F-453 — finding 을 근거로 쓴 문장은 같은 문단에 원문 줄 포인터
        for m in FINDING_CLAIM.finditer(para):
            fid = m.group(1)
            ptr = re.search(r"entries/(F-%s[^\s:`)\"]*\.md):(\d+)" % fid, para)
            if not ptr:
                v.append(f"F-{fid} 을 근거로 쓴 문장에 엔트리 원문 줄 인용(entries/F-{fid}-*.md:줄)이 없다 — 기억으로 인용하지 않는다")
                continue
            if findings:
                lines = _lines_of(os.path.join(findings, ptr.group(1)))
                if lines is None or not (0 < int(ptr.group(2)) <= len(lines)):
                    v.append(f"F-{fid} 포인터 {ptr.group(1)}:{ptr.group(2)} 가 레지스트리에서 열리지 않는다")
    if FINDING_CLAIM.search(text) and not findings:
        notes.append("--findings-dir 가 없어 finding 포인터의 실재 대조 unavailable")
    amend = [i + 1 for i, ln in enumerate(text.split("\n")) if AMEND_MARK in ln]
    if amend:                                          # F-315 — 중간본에 보강 표지가 남으면 옛 문구와 새 문구가 함께 산다
        v.append(f"보강 표지 ⊕ 가 {len(amend)}줄 남았다(줄 {amend[:5]}) — plan-v{{N}} 도 단일 최신 상태로 접는다")
    ids = STEP_HEADING.findall(text)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        v.append(f"Step 제목 id 중복: {dup}")
    return v, notes


def unverified_claims(text: str) -> list:
    """F-185 — 수치 · 건수(`12건`) · 경로 줄(`a.py:30`) 주장 중 같은 줄에 `[verified:` 나 code-context 행 참조가 없는 것 → [(줄, 원문)].
    위반이 아니라 WARN 이다 — 주장마다 출처를 달라는 신호이고, 판정(사실인가)은 Lead · GPT 몫이다. 코드 블록 · 인라인 코드 안 숫자는 주장이 아니다."""
    out, fence = [], False
    for i, ln in enumerate(text.split("\n"), 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or CLAIM_EVIDENCE.search(ln):
            continue
        if COUNT_CLAIM.search(re.sub(r"`[^`]*`", "", ln)) or PATH_LINE_CLAIM.search(ln):
            out.append((i, ln.strip()))
    return out


def absence_without_control(text: str) -> list:
    """F-611 · F-726 — '0건 · 없다 · 미발견' 주장 중 같은 줄에 대조값(`[대조:` · 양성 대조 · 저장소 전체 수)이 없는 것 → [(줄, 원문)].
    `[verified:` 출처가 있어도 본다 — 출처는 '무엇으로 쟀나' 이고, 대조값은 '그 도구가 주장이 겨누는 영역에서 보이나' 다(F-726 은 대조값이
    다른 기간에서 나왔다). unverified_claims 와 같은 WARN 이고 같은 범위(코드 블록 · 인라인 코드 제외)를 본다.

    - Note: 표지에는 단위가 붙은 양수 적중 수(`3건` · `12파일`)가 있어야 한다. 대조값의 영역(기간 · 언어 · 파일 집합)이 주장과 같은지는 보지 않는다 —
      문장 규칙(`modules/cross-validation.md` § Negative-Result Gate)이 맡는다. 0 이 아닌 과소 집계(F-611)도 이 경고 밖이다."""
    out, fence = [], False
    for i, ln in enumerate(text.split("\n"), 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or CONTROL_VALUE.search(ln):
            continue
        if ABSENCE_CLAIM.search(re.sub(r"`[^`]*`", "", ln)):
            out.append((i, ln.strip()))
    return out


def _cells(row: str) -> list:
    """마크다운 표 행의 칸 — 인라인 코드 안 `|` 와 `\\|` 는 칸 경계가 아니다."""
    t = re.sub(r"`[^`]*`", lambda m: m.group(0).replace("|", "\0"), row.strip()).replace("\\|", "\0")
    t = t[1:] if t.startswith("|") else t
    t = t[:-1] if t.endswith("|") else t
    return [c.replace("\0", "|").strip() for c in t.split("|")]


def decided_without_source(text: str) -> list:
    """F-636 — 위험 표(머리 행에 '완화 · Mitigation · 대응' 칸)의 완화 칸이 결정됨(결정됨 · 결정에 따라 · decided · expected by decision)을
    말하는데 같은 행에 결정 출처(사용자 원문 인용 · 문서:줄)가 없는 행 → [(줄, 원문)]. 미결 표기('미결 — 사용자 결정' · 'NOT decided' ·
    '…갈지 결정')는 결정 주장이 아니다. absence_without_control 과 같은 WARN 이고 같은 범위(코드 블록 · 완화 칸의 인라인 코드 제외)를 본다 —
    완화 칸이 없는 표 · 산문은 보지 않는다.

    - Note: 출처는 꼴만 본다 — 문서 · 기록 파일(md · txt · tsv · json · yaml …)의 `파일:줄` 이나 따옴표 인용이 같은 행에 있으면 출처로 센다
      (코드 `파일:줄` 은 세지 않는다). 그 줄 · 인용이 그 결정을 적었는지는 Lead · 사람 몫이다. 한국어 맨 '결정'(사용자 결정 · 결정한다)은
      결정 주장으로 세지 않는다 — 끝난 결정을 맨 낱말로만 적으면 놓친다."""
    out, fence, col = [], False, None
    lines = text.split("\n")
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            fence, col = not fence, None
            continue
        if fence or not ln.lstrip().startswith("|"):
            col = None                                  # 표가 끝났다 — 다음 표는 머리 행에서 완화 칸을 다시 잡는다
            continue
        if TABLE_SEP.match(ln):
            continue
        if i < len(lines) and TABLE_SEP.match(lines[i]):   # 머리 행(다음 줄이 구분 행)
            col = next((k for k, h in enumerate(_cells(ln)) if MITIGATION_HEAD.search(h)), None)
            continue
        cells = _cells(ln)
        if col is None or col >= len(cells):
            continue
        claim = re.sub(r"`[^`]*`", "", cells[col])
        if DECIDED_CLAIM.search(claim) and not NOT_DECIDED.search(claim) and not DECISION_SOURCE.search(ln):
            out.append((i, ln.strip()))
    return out


def run_doc(path: str, root=None, findings=None, quiet: bool = False) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        if not quiet:
            print(f"FAIL: plan 문서를 읽을 수 없다: {path} ({type(exc).__name__})")
        return 1
    v, notes = check_doc(text, root, findings)
    if not quiet:
        for n in notes:
            print(f"  ⚠️ {n}")
        claims = unverified_claims(text)
        for ln, s in claims:
            print(f"  WARN 미검증 주장 줄 {ln}: {s[:100]}")
        if claims:
            print(f"  WARN 미검증 주장 {len(claims)}건 — 같은 줄에 [verified: 출처] 나 code-context 행 참조를 단다(위반 아님 · exit 무관)")
        absent = absence_without_control(text)
        for ln, s in absent:
            print(f"  WARN 대조값 없는 부재 주장 줄 {ln}: {s[:100]}")
        if absent:
            print(f"  WARN 대조값 없는 부재 주장 {len(absent)}건 — 같은 줄에 [대조: 같은 도구가 주장이 겨누는 영역에서 찾은 양성 대조 · 저장소 전체 수]를 단다"
                  "(위반 아님 · exit 무관 · modules/cross-validation.md § Negative-Result Gate)")
        undecided = decided_without_source(text)
        for ln, s in undecided:
            print(f"  WARN 출처 없는 결정 완화 줄 {ln}: {s[:100]}")
        if undecided:
            print(f"  WARN 출처 없는 결정 완화 {len(undecided)}건 — 위험 표 완화 칸이 '결정됨' 이면 같은 행에 결정 출처(사용자 원문 인용 · 문서:줄)를 단다 · "
                  "못 달면 '미결 — 사용자 결정' 으로 쓴다(위반 아님 · exit 무관 · F-636)")
        for x in v:
            print(f"  VIOLATION {x}")
        print((f"integrity=FAIL ({len(v)} 위반) " if v else "INTEGRITY_PASS ") + os.path.basename(path))
    return 1 if v else 0


def run_one(path: str, quiet: bool = False) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        if not quiet:
            print(f"FAIL: 입력을 읽을 수 없다: {path} ({type(exc).__name__}: {exc})")
        return 1
    if not isinstance(doc, dict):
        if not quiet:
            print(f"FAIL: 최상위가 객체가 아니다: {path}")
        return 1
    v, notes = check(doc)
    if not quiet:
        for n in notes:
            print(f"  ⚠️ {n}")
        for x in v:
            print(f"  VIOLATION {x}")
    if v:
        if not quiet:
            print(f"integrity=FAIL ({len(v)} 위반) {os.path.basename(path)}")
        return 1
    if not quiet:
        print(f"INTEGRITY_PASS ({os.path.basename(path)} — 위반 0"
              + (f" · unavailable {len(notes)}건" if notes else "") + ")")
    return 0


def self_test(fixture_dir: str) -> int:
    """양성 1 + 음성 N. ⛔ 음성이 없으면 '검사기가 살아 있는가' 를 못 본다."""
    good = os.path.join(fixture_dir, "good.json")
    bads = sorted(glob.glob(os.path.join(fixture_dir, "bad-*.json")))
    if not os.path.isfile(good) or not bads:
        print(f"FAIL: fixture 부족 — good.json {os.path.isfile(good)} · bad-*.json {len(bads)}건")
        return 1
    passed, fails = 0, []
    if run_one(good, quiet=True) == 0:
        passed += 1
    else:
        fails.append("good.json 이 통과하지 않았다 (양성 실패)")
    for b in bads:
        if run_one(b, quiet=True) == 1:
            passed += 1
        else:
            fails.append(f"{os.path.basename(b)} 가 통과했다 (음성 실패 — 위반을 못 잡는다)")
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    bundle_cells = (("f599-read-bundle-split-suggested", "bad-read-bundle.json", '분해 제안: ["c.md", "d.md"]'),
                    ("f599-write-bundle-split-suggested", "bad-write-bundle.json", '분해 제안: ["new-a.js", "new-b.js"]'))
    for cell, name, want in bundle_cells:               # F-599 — 묶음 음성은 exit 만이 아니라 분해 제안(묶음 원문이 아닌 경로 배열)을 낸다
        try:
            with open(os.path.join(fixture_dir, name), "r", encoding="utf-8") as fh:
                got = check(json.load(fh))[0]
        except (OSError, ValueError) as exc:
            got = [f"fixture 를 읽을 수 없다 ({type(exc).__name__})"]
        if any(want in x for x in got):
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — 위반 {got} (기대 {want!r})")
            print(f"FAIL {cell}: 위반 {got} (기대 {want!r})")
    # 공백 든 한 경로는 묶음이 아니다 · 완결 경로 둘을 공백으로 붙이면 묶음이다(GPT check 8.5 P2)
    sp = [bundled_paths("Sources/My File.swift"), bundled_paths("App Resources/a.png, App Resources/b.png"),
          bundled_paths("scripts/a.py scripts/b.py"), bundled_paths("§X c.md, d.md (참고)")]
    cell = "f599-space-in-single-path-not-bundle"
    if sp == [[], ["App Resources/a.png", "App Resources/b.png"], ["scripts/a.py", "scripts/b.py"], ["c.md", "d.md"]]:
        passed += 1
        if listing:
            print(f"PASS {cell}")
    else:
        fails.append(f"{cell} — {sp}")
        print(f"FAIL {cell}: {sp}")
    doc = os.path.join(fixture_dir, "doc")
    doc_cells = 0
    if os.path.isdir(doc):                              # plan 문서 셀(round 2 S17) — 셀마다 양성(good.md) 대조를 함께 본다
        doc_cells = 7
        root, ents = os.path.join(doc, "root"), os.path.join(doc, "entries")

        def doc_v(name):
            with open(os.path.join(doc, name), "r", encoding="utf-8") as fh:
                return check_doc(fh.read(), root, ents)[0]
        good_v = doc_v("good.md")
        for cell, name, need in (("f432-plan-quote-mismatch", "bad-quote.md", ("인용이 원문과 다르다",)),
                                 ("f453-finding-claim-unquoted", "bad-finding.md", ("엔트리 원문 줄 인용", "레지스트리에서 열리지 않는다")),
                                 ("f315-amend-marker-left", "bad-amend.md", ("보강 표지 ⊕", "Step 제목 id 중복"))):
            got = doc_v(name)
            ok = not good_v and all(any(n in x for x in got) for n in need)
            if ok:
                passed += 1
                if listing:
                    print(f"PASS {cell}")
            else:
                fails.append(f"{cell} — 위반 {got} · good.md {good_v}")
                print(f"FAIL {cell}: 위반 {got} · good.md {good_v}")
        with open(os.path.join(doc, "claims.md"), "r", encoding="utf-8") as fh:   # F-185 — 경고 줄 집합이 정확히 근거 없는 두 줄
            text = fh.read()
        got = [ln for ln, _s in unverified_claims(text)]
        cell = "r3-f185-prose-claim-unverified-warn"
        if got == [5, 8] and check_doc(text)[0] == []:
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — 경고 줄 {got} (기대 [5, 8])")
            print(f"FAIL {cell}: 경고 줄 {got} (기대 [5, 8])")
        # F-611 · F-726 — 대조값 없는 부재 주장 경고 줄 집합이 정확히 5 · 6 · 7 · 15 ~ 19(빈 표지 · 0 뿐인 표지 · ID · 줄 번호만 든 표지 포함 · 출처만 단 줄 포함 · 대조값 · 능력 · 결정 · 10건 · 코드는 제외)
        with open(os.path.join(doc, "absence.md"), "r", encoding="utf-8") as fh:
            text = fh.read()
        got = [ln for ln, _s in absence_without_control(text)]
        cell = "t-domain-absence-claim-no-control-warn"
        if got == [5, 6, 7, 15, 16, 17, 18, 19] and check_doc(text)[0] == []:
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — 경고 줄 {got} (기대 [5, 6, 7, 15, 16, 17, 18, 19])")
            print(f"FAIL {cell}: 경고 줄 {got} (기대 [5, 6, 7, 15, 16, 17, 18, 19])")
        # 운영 경로 — fz-plan Gate 1 은 --plan-doc(run_doc)의 출력을 읽는다. 함수만 재면 run_doc 의 호출을 지워도 통과한다(채점 2차 ISSUE-005)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc_doc = run_doc(os.path.join(doc, "absence.md"))
        shown = re.findall(r"WARN 대조값 없는 부재 주장 줄 (\d+):", buf.getvalue())
        cell = "t-domain-run-doc-prints-warn-exit-0"
        if rc_doc == 0 and [int(x) for x in shown] == [5, 6, 7, 15, 16, 17, 18, 19] and "WARN 대조값 없는 부재 주장 8건" in buf.getvalue():
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — rc={rc_doc} 줄 {shown}")
            print(f"FAIL {cell}: rc={rc_doc} 줄 {shown}")
        # F-636 — 출처 없는 '결정됨' 완화 경고 줄 집합이 정확히 7(엔트리 plan-v1 수정 전 행) · 11(같은 행의 코드 파일:줄은 출처가 아니다) ·
        #   18(한국어 '결정에 따라 예상됨') · 24('대응' 칸의 '결정됨'). 출처 있는 행(따옴표 인용 · 완화 칸 · 다른 칸의 문서:줄 · 「」 인용 ·
        #   기록 tsv:줄) · 미결 표기(NOT decided · 미결 — 사용자 결정 · …갈지 결정 · 다르면 사용자 결정) · 결정론 · 인라인 코드 · 완화 칸 없는 표 ·
        #   산문 · 코드 블록은 0
        with open(os.path.join(doc, "risk-decided.md"), "r", encoding="utf-8") as fh:
            text = fh.read()
        got = [ln for ln, _s in decided_without_source(text)]
        cell = "f636-risk-decided-without-source-warn"
        if got == [7, 11, 18, 24] and check_doc(text)[0] == []:
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — 경고 줄 {got} (기대 [7, 11, 18, 24])")
            print(f"FAIL {cell}: 경고 줄 {got} (기대 [7, 11, 18, 24])")
        # 운영 경로 — 같은 경고가 --plan-doc(run_doc) 출력에 실리고 exit 는 그대로다(fz-plan Gate 1 은 run_doc 출력을 읽는다)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc_doc = run_doc(os.path.join(doc, "risk-decided.md"))
        shown = re.findall(r"WARN 출처 없는 결정 완화 줄 (\d+):", buf.getvalue())
        cell = "f636-run-doc-prints-decided-warn-exit-0"
        if rc_doc == 0 and [int(x) for x in shown] == [7, 11, 18, 24] and "WARN 출처 없는 결정 완화 4건" in buf.getvalue():
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — rc={rc_doc} 줄 {shown}")
            print(f"FAIL {cell}: rc={rc_doc} 줄 {shown}")
    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    if fails:
        print(f"plan_integrity self-test {passed}/{total} passed")
        return 1
    print(f"INTEGRITY_SELFTEST_OK (양성 1 · 음성 {len(bads)} · 묶음 셀 {len(bundle_cells)} · 문서 셀 {doc_cells} — {passed}/{total})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="plan 반환의 참조 무결성 검사")
    ap.add_argument("target", nargs="?", help="workflow-result.json 경로")
    ap.add_argument("--self-test", metavar="FIXTURE_DIR", help="fixture 디렉토리로 양성·음성 self-test")
    ap.add_argument("--plan-doc", metavar="MD", help="plan 마크다운(plan-v{N} · plan-final) 검사 — 인용 · finding 근거 · 단일 최신 상태")
    ap.add_argument("--root", help="--plan-doc 의 `경로:줄` 인용을 대조할 저장소 루트")
    ap.add_argument("--findings-dir", help="--plan-doc 의 finding 포인터를 대조할 레지스트리 entries/")
    args = ap.parse_args()
    if args.self_test:
        return self_test(args.self_test)
    if args.plan_doc:
        return run_doc(args.plan_doc, args.root, args.findings_dir)
    if not args.target:
        ap.print_help()
        return 2
    return run_one(args.target)


if __name__ == "__main__":
    sys.exit(main())
