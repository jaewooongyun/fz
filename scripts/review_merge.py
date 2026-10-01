#!/usr/bin/env python3
# diff-parse: hunk-state — `@@ -a,b +c,d @@` 헤더로 hunk 범위를 추적하고, hunk 안에서는 남은 줄 수를 세어
#   `+++`·`---` 로 시작하는 소스 행을 파일 헤더로 오인하지 않는다(증거 재실측의 대상 텍스트를 모은다).
"""리뷰 발견의 결정론 병합 (S20 · 정본 `modules/peer-review-gates.md` § MergeContract).

Lead 가 손으로 하던 기계 작업만 한다 — 판정(`include`·`observation`·`exclude`)은 하지 않는다.

  dedup 키     파일 + line_range 겹침 + 축(§3). 축이 다르면 같은 자리라도 별건. craft 항목은 결함과 섞지 않는다
  경로         후보 경로를 diff 경로로 푼다(basename · `./` · git 따옴표 · 탭 꼬리) — 경로 의미는 diff_anchors.py 한 곳이다
  보존         ⛔ 후보를 지우지 않는다 — 입력 후보 수 = 출력 후보 수(AC-4). 같은 키는 그룹으로 묶을 뿐이다
  귀속         그룹마다 both · claude_only · gpt_only (GPT 독립 첫 패스와 Claude 렌즈 중 누가 찾았나)
  근거 재실측   증거 속 인용(백틱 구간, 없으면 전문)이 그 파일 hunk 에 공백 정규화 후 **전부** 있으면 evidenceVerified.
               file 이 없거나 diff 에서 경로를 못 푼 후보는 false(hold) + 사유 — 전 파일을 뒤지지 않는다
  게시 등급     post · hold · suggestion — 미확인 근거는 hold(삭제 아님) · craft 는 ruleRef 가 있고 confidence 80 이상일
               때만 post(확신도가 낮으면 suggestion 채널) · pre-existing 은 suggestion 으로 cap(§7) · confidence 80 미만 결함은 hold
  GPT verdict  reverse → disposition question + oracle(§6 — 이종 검증에 삭제 권한을 주지 않는다). 등급은 hold 이고
               보고서에는 question 에만 싣는다 · challenge → Lead 확인
  contested    교차 판정이 갈린 항목은 원본 severity 와 crossVerdicts 를 그대로 둔다(스크립트가 고르지 않는다)
  입력 계약     severity 는 네 값 · confidence 는 0-100 숫자(없어도 된다) · id 는 겹치지 않는다(reviews 는 겹친 id 에 렌즈를
               붙여 가른다) · verdict 는 §6 네 종류이고 대상이 Claude 후보에 있다 — 어기면 거부. 알아보지 못하는 형태는 exit 2

모드
  --claude FILE (--gpt FILE | --gpt-unavailable 사유) --diff FILE [--out FILE]   병합
  --check-fixture DIR   tests/fixtures/peer-review/tier2-merge — 전건 보존 · 입력 순서가 바뀌어도 같은 그룹 ·
                        후보 수와 그룹 수가 그 폴더의 merge-expect.json 과 같다
  --self-test

exit: 0=병합 · 1=거부(오염된 GPT 입력 · 계약 위반) · 2=측정 실패(⛔ 통과 아님 — GPT 입력도 사유도 없을 때 · 알아보지 못하는 형태 포함)
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import functools
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import tempfile

OK, REJECT, UNRUN = 0, 1, 2
SEVERITIES = ("critical", "major", "minor", "suggestion")
GRADES = ("post", "hold", "suggestion")
VERDICT_KINDS = ("agree", "supplement", "challenge", "reverse")   # §6
CONFIDENCE_FLOOR = 80                      # OVERRIDE 의 보고 하한과 같은 값 — 여기서는 삭제가 아니라 hold 로 쓴다
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
QUOTE_RE = re.compile(r"`([^`\n]+)`")
HERE = os.path.dirname(os.path.abspath(__file__))
ANCHORS = pathlib.Path(HERE).parent / "skills" / "fz-peer-review" / "scripts" / "diff_anchors.py"


class Unrun(Exception):
    pass


class Reject(Exception):
    pass


@functools.lru_cache(maxsize=None)
def anchors():
    """diff 경로 의미(git 따옴표 8진 · 탭 꼬리 · a/ b/ · basename 해석)는 diff_anchors.py 한 곳에 둔다 — 여기서 다시 짜지 않는다."""
    if not ANCHORS.is_file():
        raise Unrun(f"diff_anchors.py 가 없다 — {ANCHORS}")
    spec = importlib.util.spec_from_file_location("diff_anchors", ANCHORS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── diff → 파일별 hunk 텍스트 ──────────────────────────────────────
def hunk_text(diff: str) -> dict:
    """파일 경로 → hunk 안 모든 행(문맥 · 추가 · 삭제)의 내용. 삭제된 파일은 `--- a/` 경로로 귀속한다.
    헤더 경로는 diff_anchors 와 같게 푼다 — git 은 공백 경로 끝에 탭을 붙이고 비ASCII 경로를 따옴표 8진으로 쓴다."""
    da = anchors()
    files: dict = {}
    cur = old_path = None
    rem_old = rem_new = 0
    for line in diff.split("\n"):
        if rem_old > 0 or rem_new > 0:
            tag = line[:1]
            if tag in ("-", "+", " "):
                if tag in ("-", " "):
                    rem_old -= 1
                if tag in ("+", " "):
                    rem_new -= 1
                if cur is not None:
                    files.setdefault(cur, []).append(line[1:])
            continue                                 # '\ No newline at end of file' 는 세지 않는다
        if line.startswith("diff --git "):
            cur = old_path = None
            continue
        if line.startswith("--- "):
            p = da.strip_prefix(da.unquote_path(line[4:]))
            old_path = None if p == "/dev/null" else p
            continue
        if line.startswith("+++ "):
            p = da.strip_prefix(da.unquote_path(line[4:]))
            cur = old_path if p == "/dev/null" else p
            continue
        m = HUNK_RE.match(line)
        if m and cur is not None:
            rem_old = int(m.group(2)) if m.group(2) is not None else 1
            rem_new = int(m.group(4)) if m.group(4) is not None else 1
    return {f: norm("\n".join(v)) for f, v in files.items()}


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def resolve_file(c: dict, texts) -> str | None:
    """후보 경로를 diff 경로로 푼다 — §3 그룹 키와 근거 재실측이 같은 경로를 본다. 못 풀면 diff_anchors 의 사유를 돌려준다."""
    if texts is None or not c.get("file"):
        return None
    path, why = anchors().resolve_path(c["file"], texts)
    if path is not None and path != c["file"]:
        c["fileAsGiven"], c["file"] = c["file"], path
    return why


def evidence_check(cand: dict, texts, path_why) -> tuple:
    """(판정, 사유). 판정 None = 재실측하지 않았다(fixture). 인용 구간이 모두 **그 파일** hunk 에 있어야 true.
    ⛔ file 이 없으면 false — 전 파일을 뒤지면 다른 파일의 같은 문자열이 확인으로 오인된다."""
    if texts is None:
        return None, None
    if not cand.get("file"):
        return False, "file 없음 — 어느 hunk 인지 몰라 재실측하지 않았다"
    if path_why:
        return False, f"경로를 diff 에서 풀지 못했다 — {path_why}"
    ev = cand.get("evidence") or ""
    spans = [norm(q) for q in QUOTE_RE.findall(ev)] or [norm(ev)]
    spans = [s for s in spans if len(s) >= 3]
    if not spans:
        return False, "3자 이상의 인용이 없다"
    missing = sum(1 for s in spans if s not in texts[cand["file"]])
    return missing == 0, (f"인용 {missing}/{len(spans)} 구간이 그 파일 hunk 에 없다" if missing else None)


# ── 입력 정규화 ────────────────────────────────────────────────────
def spans(line_range) -> list:
    out = []
    for part in re.split(r"[,;]", str(line_range or "")):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if nums:
            out.append((min(nums), max(nums)))
    return out


def gpt_path(p):
    """GPT 독립 첫 패스는 격리 dir 의 `head/` 스냅샷을 본다 — 접두를 벗겨 레포 상대 경로로 맞춘다."""
    if not p:
        return p
    if "/head/" in p:
        return p.split("/head/", 1)[1]
    return p[len("head/"):] if p.startswith("head/") else p


def candidate(item: dict, source: str, lens) -> dict:
    if not isinstance(item, dict) or item.get("id") in (None, ""):
        raise Reject(f"{source} 후보가 id 를 가진 객체가 아니다 — {str(item)[:80]}")
    cid = f"{source}:{item['id']}"
    sev = item.get("finalSeverity") or item.get("severity")   # Tier 3 는 finalSeverity 가 확정값이다. Tier 2 의 crossSeverity 는 제안이라 원본을 쓴다(§9)
    if sev not in SEVERITIES:
        raise Reject(f"{cid} — severity {sev!r} 는 {' · '.join(SEVERITIES)} 밖이다(없으면 게시 등급을 매길 수 없다)")
    conf = item.get("confidence")
    if conf is not None and (isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 100):
        raise Reject(f"{cid} — confidence {conf!r} 는 0-100 숫자가 아니다(문자열이면 확신도 하한을 조용히 비켜 간다)")
    return {
        "id": cid, "source": source, "lens": lens,
        "file": gpt_path(item.get("file")) if source == "gpt" else item.get("file"),
        "line_range": item.get("line_range"),
        "discoveryAxis": item.get("discoveryAxis") or "unknown",
        "craftAxis": item.get("craftAxis"), "ruleRef": item.get("ruleRef"),
        "severity": sev,
        "origin": item.get("origin"), "confidence": conf,
        "evidence": item.get("evidence"),
        "title": item.get("title") or item.get("description"),
        "crossVerdict": item.get("crossVerdict"), "crossVerdicts": item.get("crossVerdicts"),
        "counterVerdict": item.get("counterVerdict"),
    }


def items_of(obj: dict, keys=("issues", "findings")):
    """issues · findings 배열 — 둘 다 없으면 None(0건으로 세지 않는다)."""
    return next((obj[k] for k in keys if isinstance(obj.get(k), list)), None)


def unique(cands: list, qualify: bool = False) -> list:
    """id 가 겹치면 verdict 대상과 그룹 멤버가 모호해진다. reviews 입력은 겹친 id 에 렌즈를 붙여 가르고, 그래도 겹치면 거부한다."""
    n = collections.Counter(c["id"] for c in cands)
    if qualify:
        for c in cands:
            if n[c["id"]] > 1 and c["lens"]:
                src, rest = c["id"].split(":", 1)
                c["id"] = f"{src}:{c['lens']}:{rest}"
        n = collections.Counter(c["id"] for c in cands)
    dup = sorted(i for i, k in n.items() if k > 1)
    if dup:
        raise Reject(f"후보 id 가 겹친다 — {dup}")
    return cands


def claude_candidates(doc) -> list:
    if not isinstance(doc, dict):
        raise Unrun("Claude 입력이 JSON 객체가 아니다")
    items = items_of(doc)
    if items is not None:
        return unique([candidate(i, "claude", str(i.get("id", "")).split(":")[0] or None if isinstance(i, dict) else None) for i in items])
    if isinstance(doc.get("reviews"), list):
        out = []
        for n, r in enumerate(doc["reviews"]):
            got = items_of(r) if isinstance(r, dict) else None
            if got is None:
                raise Unrun(f"reviews[{n}] 에 issues · findings 배열이 없다 — 그 렌즈를 0건으로 세지 않는다")
            out += [candidate(i, "claude", r.get("agent")) for i in got]
        return unique(out, qualify=True)
    raise Unrun("Claude 입력에 issues · findings · reviews 가 없다")


def gpt_candidates(doc) -> tuple:
    if not isinstance(doc, dict):
        raise Unrun("GPT 입력이 JSON 객체가 아니다")
    if doc.get("contaminated") is True or doc.get("contamination"):
        raise Reject(f"GPT 입력에 오염 표시가 있다 — 독립 첫 패스가 아니다: {doc.get('contamination') or 'contaminated: true'}")
    items = items_of(doc, keys=("findings", "issues"))
    if items is None:
        raise Unrun("GPT 입력에 findings · issues 배열이 없다 — 알아보지 못하는 형태를 GPT 0건으로 병합하지 않는다")
    verdicts = doc.get("verdicts") or []
    if not isinstance(verdicts, list):
        raise Unrun("GPT verdicts 가 배열이 아니다")
    # GPT 독립 첫 패스는 craft 를 결함과 다른 배열에 둔다(schemas/gpt_independent_review_schema.json) — 빠뜨리면 craft 지적이 조용히 사라진다.
    #    렌즈 "craft" 로 읽어 id 가 결함과 겹칠 때만 gpt:gpt:X · gpt:craft:X 로 가른다. craftAxis 가 없으면 결함 채널로 섞이므로 거부한다
    craft = doc.get("craft")
    if craft is not None and not isinstance(craft, list):
        raise Unrun("GPT craft 가 배열이 아니다")
    for c in craft or []:
        if not isinstance(c, dict) or not c.get("craftAxis"):
            raise Reject(f"GPT craft 항목에 craftAxis 가 없다 — 결함 채널로 섞지 않는다: {str(c)[:80]}")
    return unique([candidate(i, "gpt", "gpt") for i in items] + [candidate(c, "gpt", "craft") for c in craft or []], qualify=True), verdicts


def gpt_sidecars(gpt_path: str, diff_path: str) -> None:
    """런처(gpt_independent.sh) 산출이면 옆 파일로 판정한다 — 런처는 오염을 본문이 아니라 `.contaminated` 옆 파일로만 남긴다.
    감사가 없으면 런처 밖 입력(/fz-gpt review 등 — 독립성을 주장하지 않는 기존 경로)이라 그대로 받는다."""
    stem = gpt_path[:-5] if gpt_path.endswith(".json") else gpt_path
    if os.path.exists(stem + ".contaminated"):
        raise Reject(f"GPT 독립 첫 패스가 오염으로 끝났다({stem}.contaminated) — 병합하지 않는다")
    if not os.path.exists(stem + ".audit.json"):
        return
    audit = load(stem + ".audit.json")
    if audit.get("exit") != 0 or audit.get("isolationApplied") is not True:
        raise Reject(f"GPT 독립 첫 패스가 통과하지 못했다 — exit {audit.get('exit')} · 격리 {audit.get('isolationApplied')} · {audit.get('note')}")
    want = (audit.get("inputs") or {}).get("diff.patch")
    if not want:
        raise Unrun("런처 감사에 diff 해시가 없다 — 어느 diff 를 봤는지 모르는 GPT 입력으로 판정하지 않는다")
    try:
        got = hashlib.sha256(pathlib.Path(diff_path).read_bytes()).hexdigest()
    except OSError as e:
        raise Unrun(f"diff 를 읽을 수 없다 — {e}")
    if want != got:
        raise Reject(f"stale — GPT 독립 첫 패스가 본 diff({want[:12]})와 병합 diff({got[:12]})가 다르다. 다시 돌리거나 --gpt-unavailable 로 사유를 적는다")


# ── 병합 ───────────────────────────────────────────────────────────
def axis_key(c):
    return ("craft", c["craftAxis"]) if c.get("craftAxis") else ("defect", c["discoveryAxis"])


def group(cands: list) -> list:
    """union-find — 같은 파일 · 같은 축 · 줄 범위가 겹치면 한 그룹. 위치를 모르면 혼자다."""
    parent = list(range(len(cands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    sp = [spans(c.get("line_range")) for c in cands]
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = cands[i], cands[j]
            if not a.get("file") or a.get("file") != b.get("file") or axis_key(a) != axis_key(b) or not sp[i] or not sp[j]:
                continue
            if any(x[0] <= y[1] and y[0] <= x[1] for x in sp[i] for y in sp[j]):
                parent[find(i)] = find(j)
    buckets: dict = {}
    for i in range(len(cands)):
        buckets.setdefault(find(i), []).append(cands[i])
    return list(buckets.values())


def grade(c: dict) -> str:
    sev = c["effectiveSeverity"]
    if c.get("disposition") == "question":
        return "hold"                                # §6 reverse — oracle 로 판별하기 전에는 게시하지 않는다
    if c["evidenceVerified"] is False:
        return "hold"
    conf = c.get("confidence")
    low = isinstance(conf, (int, float)) and conf < CONFIDENCE_FLOOR
    if c.get("craftAxis"):
        return "post" if c.get("ruleRef") and sev in ("critical", "major", "minor") and not low else "suggestion"
    if sev == "suggestion":
        return "suggestion"
    return "hold" if low else "post"


def merge(claude: list, gpt: list, verdicts: list, texts, gpt_unavailable) -> dict:
    cands = [dict(c) for c in claude + gpt]
    by_id = {c["id"]: c for c in cands}
    for c in cands:
        path_why = resolve_file(c, texts)
        c["effectiveSeverity"] = "suggestion" if c.get("origin") == "pre-existing" else c.get("severity")
        c["nonBlocking"] = c.get("origin") == "improvement"
        c["evidenceVerified"], c["evidenceNote"] = evidence_check(c, texts, path_why)
        c["disposition"] = None                      # ⛔ exclude 는 매기지 않는다 — include·observation 도 Lead 판정
        c["leadCheck"] = c.get("crossVerdict") == "contested"
        c["foundBy"] = [c["source"]]
    for v in verdicts:
        kind = v.get("verdict") if isinstance(v, dict) else None
        if kind not in VERDICT_KINDS:
            raise Reject(f"GPT verdict 종류 {kind!r} 는 §6 밖이다 — {' · '.join(VERDICT_KINDS)}")
        c = by_id.get(f"claude:{v.get('target')}")
        if c is None:
            raise Reject(f"GPT verdict 대상 {v.get('target')!r} 가 Claude 후보에 없다 — 조용히 버리지 않는다")
        c["gptVerdict"] = kind
        if kind == "agree":
            c["foundBy"].append("gpt-verdict")
        elif kind == "supplement":
            c["gptNote"] = v.get("note")
        elif kind == "challenge":
            c["leadCheck"] = True
            c["gptNote"] = v.get("note")
        elif kind == "reverse":
            c["disposition"] = "question"
            c["oracle"] = v.get("oracle") or v.get("note") or "판별 방법 미기재 — Lead 가 적는다"
    for c in cands:
        c["grade"] = grade(c)
    groups = sorted(group(cands), key=lambda g: min((m.get("file") or "", (spans(m.get("line_range")) or [(0, 0)])[0][0], m["id"]) for m in g))
    out, gsum = [], []
    for n, g in enumerate(groups, 1):
        srcs = {m["source"] for m in g}
        attr = "both" if {"claude", "gpt"} <= srcs else ("claude_only" if "claude" in srcs else "gpt_only")
        members = sorted(g, key=lambda m: m["id"])
        for m in members:
            m["group"] = n
            m["attribution"] = attr
            out.append(m)
        gsum.append({"group": n, "file": members[0].get("file"), "axis": list(axis_key(members[0])), "attribution": attr,
                     "members": [m["id"] for m in members]})
    if len(out) != len(cands):
        raise Reject(f"후보 보존 위반 — 입력 {len(cands)} ≠ 출력 {len(out)}(AC-4)")
    if any(c.get("disposition") == "exclude" for c in out):
        raise Reject("disposition exclude 는 Lead 전용이다")
    # 보고서는 후보를 한 목록에만 싣는다 — question 은 등급 목록보다 앞선다(post 만 읽는 소비자가 GPT 가 뒤집은 항목을 게시하지 않게)
    report = {g: [c["id"] for c in out if c["grade"] == g and c["disposition"] != "question"] for g in GRADES}
    report |= {"question": [c["id"] for c in out if c["disposition"] == "question"],
               "leadCheck": [c["id"] for c in out if c["leadCheck"]]}
    return {
        "schemaVersion": 1,
        "inputs": {"claude": len(claude), "gpt": len(gpt), "gptVerdicts": len(verdicts), "gptUnavailable": gpt_unavailable,
                   "evidenceChecked": texts is not None},
        "candidates": out,
        "groups": gsum,
        "report": report,
        "summary": {"candidatesIn": len(cands), "candidatesOut": len(out), "groups": len(gsum),
                    "attribution": {a: sum(1 for g in gsum if g["attribution"] == a) for a in ("both", "claude_only", "gpt_only")},
                    "grade": {k: len(report[k]) for k in (*GRADES, "question")},
                    "contested": sum(1 for c in out if c.get("crossVerdict") == "contested"),
                    "evidenceUnverified": sum(1 for c in out if c["evidenceVerified"] is False)},
    }


def load(path: str):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Unrun(f"JSON 을 읽을 수 없다 — {path}: {e}")


def run_merge(a) -> int:
    if not a.claude or not a.diff:
        raise Unrun("--claude 와 --diff 가 필요하다(근거 재실측 없이는 게시 등급을 매기지 않는다)")
    if not a.gpt and not (a.gpt_unavailable or "").strip():
        raise Unrun("GPT 독립 입력(--gpt)이 없는데 사유(--gpt-unavailable)도 없다 — 조용히 Claude 단독으로 병합하지 않는다")
    if a.gpt:
        gpt_sidecars(a.gpt, a.diff)
    gpt, verdicts = gpt_candidates(load(a.gpt)) if a.gpt else ([], [])
    try:
        texts = hunk_text(pathlib.Path(a.diff).read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        raise Unrun(f"diff 를 읽을 수 없다 — {e}")
    result = merge(claude_candidates(load(a.claude)), gpt, verdicts, texts, None if a.gpt else a.gpt_unavailable.strip())
    text = json.dumps(result, ensure_ascii=False, indent=1) + "\n"
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    s = result["summary"]
    print(f"MERGE OK — 후보 {s['candidatesIn']}→{s['candidatesOut']} · 그룹 {s['groups']} · {s['attribution']} · {s['grade']}", file=sys.stderr)
    return OK


def check_fixture(d: pathlib.Path) -> int:
    doc = load(str(d / "stage1-input.json"))
    want = load(str(d / "merge-expect.json"))      # ⛔ 폴더가 자기 기대 수를 든다 — 세기만 하고 대조하지 않으면 0건 · 무병합도 통과한다
    if not isinstance(want, dict) or not all(isinstance(want.get(k), int) for k in ("candidates", "groups")):
        raise Unrun(f"{d / 'merge-expect.json'} 에 candidates · groups 정수가 없다")
    base = claude_candidates(doc)
    runs = []
    rng = random.Random(20260927)                    # 고정 시드 — 같은 입력이면 같은 섞기
    orders = [list(base), list(reversed(base)), rng.sample(base, len(base))]
    for order in orders:
        r = merge(order, [], [], None, "fixture — GPT 입력 없음")
        runs.append((r["summary"]["candidatesOut"], sorted(tuple(g["members"]) for g in r["groups"])))
    n_in = len(base)
    kept = n_in > 0 and n_in == want["candidates"] and all(out == n_in for out, _ in runs)
    stable = all(g == runs[0][1] for _, g in runs)
    grouped = len(runs[0][1]) == want["groups"]
    ok = kept and stable and grouped
    print(f"{'FIXTURE OK  ' if ok else 'FIXTURE FAIL'} {d.name} — 입력 {n_in}(기대 {want['candidates']}) · 출력 {[o for o, _ in runs]} · "
          f"그룹 {len(runs[0][1])}(기대 {want['groups']}) · 입력 순서 {len(orders)}가지에서 {'같은' if stable else '⛔다른'} 그룹")
    return OK if ok else REJECT


# ── self-test ──────────────────────────────────────────────────────
DIFF = ("diff --git a/src/a.swift b/src/a.swift\n--- a/src/a.swift\n+++ b/src/a.swift\n@@ -10,2 +10,4 @@\n"
        " let service = APIClient.shared\n-let x = 1\n+let  x =   2\n++++ literal plus line\n+func load() { service.fetch() }\n"
        "diff --git a/src/b.swift b/src/b.swift\n--- a/src/b.swift\n+++ b/src/b.swift\n@@ -1 +1 @@\n-old\n+new\n")
QDIFF = ("diff --git a/.claude-plugin/plugin.json b/.claude-plugin/plugin.json\n--- a/.claude-plugin/plugin.json\n"
         "+++ b/.claude-plugin/plugin.json\n@@ -1 +1 @@\n-\"1\"\n+\"version\": \"4.42.0\"\n"
         "diff --git a/src/my file.swift b/src/my file.swift\n--- a/src/my file.swift\t\n+++ b/src/my file.swift\t\n"
         "@@ -1 +1 @@\n-old\n+let spaced = 1\n"
         "diff --git \"a/src/\\355\\225\\234.swift\" \"b/src/\\355\\225\\234.swift\"\n--- \"a/src/\\355\\225\\234.swift\"\n"
         "+++ \"b/src/\\355\\225\\234.swift\"\n@@ -1 +1 @@\n-old\n+let hangul = 1\n")   # git 실측 형태 — 공백 경로는 끝에 탭 · 비ASCII 는 따옴표 8진


def issue(i, file="src/a.swift", lr="10-12", axis="structure", sev="major", origin="regression", conf=90, ev="`APIClient.shared`", **kw):
    d = {"id": i, "file": file, "line_range": lr, "discoveryAxis": axis, "severity": sev, "origin": origin,
         "confidence": conf, "evidence": ev, "description": f"d{i}"}
    d.update(kw)
    return d


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' — {got}'}")

    def raises(fn, exc):
        try:
            fn()
        except exc:
            return True
        return False

    texts = hunk_text(DIFF)
    M = lambda claude, gpt=(), verdicts=(), t=texts: merge([candidate(c, "claude", "l") for c in claude],  # noqa: E731
                                                          [candidate(g, "gpt", "gpt") for g in gpt], list(verdicts), t, None)

    def t_group():
        r = M([issue("A1"), issue("A2", axis="runtime_safety")])
        case("axis-separate — 같은 줄이라도 축이 다르면 별건", r["summary"]["groups"] == 2, r["groups"])
        r = M([issue("A1"), issue("Q1", lr="11")])
        case("same-key-group — 같은 파일·겹침·같은 축은 한 그룹, 둘 다 남는다", r["summary"]["groups"] == 1 and r["summary"]["candidatesOut"] == 2, r["groups"])
        r = M([issue(f"X{i}", lr=str(10 + i % 3)) for i in range(7)])
        case("preserve-count — 입력 후보 수 = 출력 후보 수(AC-4)", r["summary"]["candidatesIn"] == r["summary"]["candidatesOut"] == 7, r["summary"])
        base = [issue(f"S{i}", lr=f"{10 + i}-{11 + i}", axis=("structure", "correctness")[i % 2]) for i in range(6)]
        g_a = sorted(tuple(g["members"]) for g in M(base)["groups"])
        g_b = sorted(tuple(g["members"]) for g in M(list(reversed(base)))["groups"])
        case("order — 입력 순서가 바뀌어도 같은 그룹", g_a == g_b, f"{g_a} ≠ {g_b}")

    def t_evidence():
        r = M([issue("E1", ev="`let x = 2`"), issue("E2", axis="correctness", ev="`service.missing()`")])
        e1, e2 = (next(c for c in r["candidates"] if c["id"] == f"claude:{k}") for k in ("E1", "E2"))
        case("evidence — 공백이 달라도 인용이 있으면 verified · post", e1["evidenceVerified"] is True and e1["grade"] == "post", e1)
        case("evidence — 인용이 없으면 false · hold 이고 지우지 않는다", e2["evidenceVerified"] is False and e2["grade"] == "hold" and r["summary"]["candidatesOut"] == 2, e2)
        r = M([issue("H1", ev="`+++ literal plus line`")])
        case("hunk-state — hunk 안의 `+++` 행은 헤더가 아니라 내용이다", r["candidates"][0]["evidenceVerified"] is True, r["candidates"][0])
        c = M([issue("F1", file=None)])["candidates"][0]
        case("no-file — file 없는 후보는 전 파일을 뒤지지 않는다(false · hold · 사유) — 다른 파일의 같은 문자열을 확인으로 오인하지 않는다",
             c["evidenceVerified"] is False and c["grade"] == "hold" and "file 없음" in (c["evidenceNote"] or ""), c)

    def t_paths():
        q = hunk_text(QDIFF)
        case("diff-paths — git 따옴표 8진 · 탭 꼬리 경로를 레포 경로로 푼다(diff_anchors 와 같은 의미)",
             sorted(q) == [".claude-plugin/plugin.json", "src/my file.swift", "src/한.swift"], sorted(q))
        r = M([issue("B1", file="a.swift")], gpt=[issue("G1", file="src/a.swift")])
        b1 = next(c for c in r["candidates"] if c["id"] == "claude:B1")
        case("basename — 후보 경로를 diff 경로로 풀어 같은 자리 GPT 발견과 한 그룹(both) · 근거 확인 · 받은 경로 보존",
             r["summary"]["attribution"] == {"both": 1, "claude_only": 0, "gpt_only": 0} and b1["file"] == "src/a.swift"
             and b1.get("fileAsGiven") == "a.swift" and b1["evidenceVerified"] is True, r["groups"])
        c = merge([candidate(issue("D1", file="./.claude-plugin/plugin.json", lr="1", ev='`"version": "4.42.0"`'), "claude", "l")],
                  [], [], q, None)["candidates"][0]
        case("dot-dir — 선두 ./ 만 벗기고 폴더 이름의 점은 남긴다(diff_anchors.resolve_path)",
             c["file"] == ".claude-plugin/plugin.json" and c["evidenceVerified"] is True, c)

    def t_verdicts():
        r = M([issue("A1")], verdicts=[{"target": "A1", "verdict": "reverse", "oracle": "load() 가 main 에서 불리는지 로그로 본다"}])
        c = r["candidates"][0]
        case("gpt-reverse — question 으로 바꾸고 oracle 을 적는다(삭제 아님)", c["disposition"] == "question" and "oracle" in c and r["summary"]["candidatesOut"] == 1, c)
        case("reverse-grade — question 은 게시 등급 hold · 보고서는 question 에만(post · hold · suggestion 목록에 없다)",
             c["grade"] == "hold" and r["report"]["question"] == ["claude:A1"] and all("claude:A1" not in r["report"][g] for g in GRADES)
             and r["summary"]["grade"]["question"] == 1, (c["grade"], r["report"]))
        cv = [{"by": "arch", "verdict": "agree"}, {"by": "quality", "verdict": "false_positive"}]
        r = M([issue("C1", sev="minor", crossVerdict="contested", crossVerdicts=cv)])
        c = r["candidates"][0]
        case("contested — 원본 severity · crossVerdicts 보존 · Lead 확인", c["severity"] == "minor" and c["crossVerdicts"] == cv and c["leadCheck"] and c["disposition"] is None, c)
        case("verdict-contract — 대상이 없는 verdict · §6 밖 종류 · 객체가 아닌 verdict 는 거부(조용히 버리지 않는다)",
             raises(lambda: M([issue("A1")], verdicts=[{"target": "ZZ", "verdict": "agree"}]), Reject)
             and raises(lambda: M([issue("A1")], verdicts=[{"target": "A1", "verdict": "approve"}]), Reject)
             and raises(lambda: M([issue("A1")], verdicts=["agree"]), Reject))

    def t_attribution():
        r = M([issue("A1"), issue("A2", file="src/b.swift", lr="1", ev="`new`")],
              gpt=[issue("G1", file="/tmp/fz-gpt-iso/head/src/a.swift", lr="12"), issue("G2", file="head/src/c.swift", lr="5")])
        case("attribution — both · claude_only · gpt_only", r["summary"]["attribution"] == {"both": 1, "claude_only": 1, "gpt_only": 1}, r["summary"]["attribution"])
        g1 = next(c for c in r["candidates"] if c["id"] == "gpt:G1")
        case("gpt-path — 격리 dir 의 head/ 접두를 벗겨 레포 경로로 맞춘다", g1["file"] == "src/a.swift" and g1["attribution"] == "both", g1["file"])

    def t_grades():
        r = M([issue("L1", conf=70), issue("L2", axis="naming", conf=60, craftAxis="naming"), issue("L3", conf=95),
               issue("L4", axis="placement", conf=60, craftAxis="placement", ruleRef="R3")])
        grades = {c["id"]: c["grade"] for c in r["candidates"]}
        case("confidence-grading — 확신도 낮은 결함 hold · 낮은 craft 는 규칙 인용이 있어도 suggestion 채널 · 높은 결함 post(삭제 없음)",
             grades == {"claude:L1": "hold", "claude:L2": "suggestion", "claude:L3": "post", "claude:L4": "suggestion"}, grades)
        r = M([issue("K1", craftAxis="naming", ruleRef="R3"), issue("K2")])
        case("craft-channel — craft 는 같은 자리·축의 결함과 섞지 않는다 · ruleRef 있으면 post",
             r["summary"]["groups"] == 2 and next(c for c in r["candidates"] if c["id"] == "claude:K1")["grade"] == "post", r["groups"])
        r = M([issue("P1", origin="pre-existing")])
        c = r["candidates"][0]
        case("pre-existing — severity 를 suggestion 으로 cap(§7) · 원본 severity 는 남는다", c["effectiveSeverity"] == "suggestion" and c["severity"] == "major" and c["grade"] == "suggestion", c)
        r = M([issue("Z1", disposition="exclude")])
        case("no-exclude — 입력이 무엇이든 exclude 를 매기지 않는다", all(c["disposition"] != "exclude" for c in r["candidates"]), r["candidates"])

    def t_inputs():
        case("input-contract — severity 네 값 밖 · confidence 비숫자 · 0-100 밖 · id 없음은 거부 · confidence 생략은 받는다",
             raises(lambda: candidate(issue("V1", sev="high"), "claude", "l"), Reject)
             and raises(lambda: candidate(issue("V2", conf="85"), "claude", "l"), Reject)
             and raises(lambda: candidate(issue("V3", conf=850), "claude", "l"), Reject)
             and raises(lambda: candidate(issue(None), "claude", "l"), Reject)
             and not raises(lambda: candidate(issue("V4", conf=None), "claude", "l"), Reject))
        try:
            got = sorted(c["id"] for c in claude_candidates(
                {"reviews": [{"agent": "arch", "findings": [issue("Q1")]}, {"agent": "quality", "issues": [issue("Q1", lr="40")]}]}))
        except (Reject, Unrun) as e:
            got = repr(e)
        case("reviews — findings 키 리뷰도 읽는다 · 렌즈 간 같은 id 는 렌즈를 붙여 가른다", got == ["claude:arch:Q1", "claude:quality:Q1"], got)
        case("reviews-contract — issues · findings 가 없는 리뷰는 exit 2 · 같은 렌즈 안 id 중복은 거부",
             raises(lambda: claude_candidates({"reviews": [{"agent": "arch", "verdict": "pass"}]}), Unrun)
             and raises(lambda: claude_candidates({"reviews": [{"agent": "arch", "issues": [issue("Q1"), issue("Q1")]}]}), Reject))
        g, _ = gpt_candidates({"issues": [issue("X1")], "craft": [issue("X1", axis="naming", craftAxis="naming"), issue("K9", craftAxis="placement")]})
        case("gpt-craft — craft 배열도 읽는다 · 결함과 id 가 겹칠 때만 렌즈로 가른다 · craft 는 craft 채널",
             sorted(c["id"] for c in g) == ["gpt:K9", "gpt:craft:X1", "gpt:gpt:X1"] and [axis_key(c)[0] for c in g if c["id"] == "gpt:K9"] == ["craft"],
             sorted(c["id"] for c in g))
        case("gpt-craft-axis — craftAxis 가 없는 craft 항목은 거부 · craft 가 배열이 아니면 exit 2",
             raises(lambda: gpt_candidates({"issues": [], "craft": [issue("K1")]}), Reject)
             and raises(lambda: gpt_candidates({"issues": [], "craft": {"x": 1}}), Unrun))
        case("gpt-shape — findings · issues 배열이 없는 GPT 입력은 exit 2(GPT 0건으로 병합하지 않는다)",
             raises(lambda: gpt_candidates({"result": {"findings": [issue("G1")]}}), Unrun) and raises(lambda: gpt_candidates([issue("G1")]), Unrun))
        # 근거 재실측은 evidence 를 읽는다 — GPT 스키마가 그 필드를 받지 않으면 GPT 항목은 늘 hold 다(리뷰 G1: craft 에 evidence 가 없었다)
        sch = json.loads((pathlib.Path(__file__).resolve().parent.parent / "schemas" / "gpt_independent_review_schema.json").read_text(encoding="utf-8"))
        need = {k: "evidence" in sch["properties"][k]["items"]["required"] for k in ("issues", "craft")}
        case("schema-contract — GPT 독립 리뷰 스키마의 issues · craft 둘 다 evidence 를 필수로 받는다", all(need.values()), need)

    def t_fixture():
        with tempfile.TemporaryDirectory(prefix="fz-review-merge-fx-") as tmp:
            def fx(name, issues, expect):
                d = pathlib.Path(tmp) / name
                d.mkdir()
                (d / "stage1-input.json").write_text(json.dumps({"issues": issues}), encoding="utf-8")
                if expect is not None:
                    (d / "merge-expect.json").write_text(json.dumps(expect), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        return check_fixture(d)
                    except Unrun:
                        return UNRUN
            pair = [issue("F1"), issue("F2", lr="11")]
            case("fixture — 0건 입력 · 기대와 다른 그룹 수는 거부 · 기대 파일이 없으면 exit 2",
                 fx("empty", [], {"candidates": 0, "groups": 0}) == REJECT and fx("mismatch", pair, {"candidates": 2, "groups": 2}) == REJECT
                 and fx("noexpect", pair, None) == UNRUN)
            case("⛔ 양성 대조 — 후보 수 · 그룹 수가 기대와 같으면 FIXTURE OK", fx("ok", pair, {"candidates": 2, "groups": 1}) == OK)

    def t_cli():
        me = pathlib.Path(__file__).resolve()
        with tempfile.TemporaryDirectory(prefix="fz-review-merge-") as tmp:
            t = pathlib.Path(tmp)
            (t / "claude.json").write_text(json.dumps({"issues": [issue("A1")]}), encoding="utf-8")
            (t / "diff.patch").write_text(DIFF, encoding="utf-8")
            (t / "gpt-bad.json").write_text(json.dumps({"contaminated": True, "findings": [issue("G1")]}), encoding="utf-8")
            (t / "gpt-shape.json").write_text(json.dumps({"result": {"findings": [issue("G1")]}}), encoding="utf-8")
            base_args = [sys.executable, str(me), "--claude", str(t / "claude.json"), "--diff", str(t / "diff.patch")]
            rc = subprocess.run(base_args, capture_output=True, text=True).returncode
            case("gpt-missing — GPT 입력도 사유도 없으면 exit 2", rc == UNRUN, f"exit {rc}")
            rc = subprocess.run(base_args + ["--gpt-unavailable", "quota 소진"], capture_output=True, text=True).returncode
            case("gpt-unavailable — 사유가 있으면 Claude 단독으로 병합한다", rc == OK, f"exit {rc}")
            rc = subprocess.run(base_args + ["--gpt", str(t / "gpt-bad.json")], capture_output=True, text=True).returncode
            case("gpt-contaminated — 오염 표시가 붙은 GPT 입력은 거부(exit 1)", rc == REJECT, f"exit {rc}")
            rc = subprocess.run(base_args + ["--gpt", str(t / "gpt-shape.json")], capture_output=True, text=True).returncode
            case("gpt-shape-cli — 알아보지 못하는 GPT 입력은 exit 2", rc == UNRUN, f"exit {rc}")
            # Tier 1(Workflow 없음) — Lead 가 쓰는 발견 모양(modules/fz-gpt-subcommands-aux.md § review — Lead 순서 4)을 그대로 받는다
            (t / "lead-findings.json").write_text(json.dumps({"issues": [{"id": "L1", "severity": "minor", "file": "src/a.swift", "line_range": "10-12",
                                                                        "discoveryAxis": "correctness", "title": "t", "evidence": "`let x = 2`"}]}), encoding="utf-8")
            p = subprocess.run([sys.executable, str(me), "--claude", str(t / "lead-findings.json"), "--diff", str(t / "diff.patch"),
                                "--gpt-unavailable", "tier1 시험", "--out", str(t / "tier1.json")], capture_output=True, text=True)
            got = json.loads((t / "tier1.json").read_text(encoding="utf-8"))["candidates"] if p.returncode == OK else p.stderr[-200:]
            case("tier1-shape — 문서가 정한 Lead 발견 모양을 병합한다(근거 재실측 verified)",
                 p.returncode == OK and len(got) == 1 and got[0]["evidenceVerified"] is True, got)
            # 런처 옆 파일 — 본문은 멀쩡해도 옆 파일이 실패를 말하면 병합하지 않는다
            good = hashlib.sha256((t / "diff.patch").read_bytes()).hexdigest()
            def arm(name, audit=None, contaminated=False):
                (t / f"{name}.json").write_text(json.dumps({"issues": [issue("G1")], "craft": []}), encoding="utf-8")
                if audit is not None:
                    (t / f"{name}.audit.json").write_text(json.dumps(audit), encoding="utf-8")
                if contaminated:
                    (t / f"{name}.contaminated").write_text("{}", encoding="utf-8")
                return subprocess.run(base_args + ["--gpt", str(t / f"{name}.json")], capture_output=True, text=True).returncode
            ok_audit = {"exit": 0, "isolationApplied": True, "inputs": {"diff.patch": good}}
            case("sidecar-ok — 감사 통과 · diff 해시 일치면 병합한다", arm("arm-ok", ok_audit) == OK)
            case("sidecar-plain — 감사가 없는 GPT 입력(런처 밖)은 기존대로 받는다", arm("arm-plain") == OK)
            case("sidecar-contaminated — .contaminated 옆 파일이 있으면 거부(exit 1)", arm("arm-bad", ok_audit, contaminated=True) == REJECT)
            case("sidecar-failed — 감사 exit≠0(시간 초과 · 6축 후검사 등)이면 거부",
                 arm("arm-timeout", dict(ok_audit, exit=16, note="시간 초과")) == REJECT)
            case("sidecar-isolation — 격리 미적용이면 거부", arm("arm-iso", dict(ok_audit, isolationApplied=False)) == REJECT)
            case("sidecar-running — 런처가 감사를 끝내지 못한 run(exit null · 'running' 선기록)은 거부",
                 arm("arm-running", {"exit": None, "note": "running"}) == REJECT)
            case("sidecar-stale — GPT 가 본 diff 해시가 병합 diff 와 다르면 거부",
                 arm("arm-stale", dict(ok_audit, inputs={"diff.patch": "0" * 64})) == REJECT)
            case("sidecar-nohash — 감사에 diff 해시가 없으면 exit 2", arm("arm-nohash", {"exit": 0, "isolationApplied": True}) == UNRUN)

    for t in (t_group, t_evidence, t_paths, t_verdicts, t_attribution, t_grades, t_inputs, t_fixture, t_cli):
        try:
            t()
        except Exception as e:   # ⛔ 케이스 안의 예외는 FAIL 로 센다 — 크래시로 끝나면 몇 건이 안 돌았는지 모른다
            case(f"{t.__name__} — 예외", False, repr(e))
    print(f"self-test {sum(results)}/{len(results)} passed")
    return OK if all(results) else REJECT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--claude")
    ap.add_argument("--gpt")
    ap.add_argument("--gpt-unavailable", metavar="사유")
    ap.add_argument("--diff")
    ap.add_argument("--out")
    ap.add_argument("--check-fixture", metavar="DIR")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    try:
        if a.self_test:
            return self_test()
        if a.check_fixture:
            return check_fixture(pathlib.Path(a.check_fixture).expanduser())
        return run_merge(a)
    except Reject as e:
        print(f"REJECT: {e}", file=sys.stderr)
        return REJECT
    except Unrun as e:
        print(f"UNRUN: {e}", file=sys.stderr)
        return UNRUN


if __name__ == "__main__":
    sys.exit(main())
