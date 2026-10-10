# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
"""ab_ledger_judge.py — A/B 원장 계측기의 한 부분: 채점(score · 가린 검증 꾸러미) · 판정(judge) · 원천 대조(verify_sources).

진입점 · 설계 · 측정 규약은 ab_ledger.py 머리말에 있다(이 파일은 그 실행 코드를 나눠 담는다).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics

from ab_ledger_base import (AXES6, AXES_ALLOWED, DEFAULT_EFFORT, DEFAULT_MODEL, FAIL, GATED, GPT_PASS_CRIT, LINE_TOL,
    MTIME_TOL_S, PASS, SEVERITIES, UNRUN, WALL_XCHECK_PCT, instrument_sha, norm_model, read_json, sha_text)
from ab_ledger_collect import (build_row, collect_spec_args)


# ── score (순수) — ⛔ 진성 여부는 가린 검증자가 정한다. 위치 매칭은 검증자에게 주는 힌트뿐이다 ──────────────
# `path:12` · `path:L12-20` 에 더해 실제 산출물이 쓰는 `` `path` L52–65 `` · `path L4-10` · `path#L4` 도 후보다
#   (v4.40.0 리뷰: peer-review C1 인용 5곳이 후보에서 빠진 채 점수는 verified=True 였다)
CITE_RE = re.compile(r"`?([A-Za-z0-9_./-]+\.[A-Za-z]{1,6})`?(?::L?|\s+L|#L)(\d+)(?:\s*[-–~]\s*L?(\d+))?")
PATH_SCRUB_RE = re.compile(r"(?:/Users|/home|/private|/tmp|/var)/[^\s`'\")\]]+")


CTX_CAP = 1600   # 후보 문맥 상한 — 렌더러 절(표 행 + What + Suggestion) 실측 최대 1,153자 · 조각 pack.json 한 줄 ≤ 2000 을 지킨다
BLOCK_START_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|\|)")


def _blocks(text):
    """글머리·번호·제목·표 행 또는 빈 줄에서 끊은 문단들 — 한 지적의 근거 문장이 이어지는 단위."""
    out, cur = [], []
    for line in text.splitlines():
        if not line.strip() or (BLOCK_START_RE.match(line) and cur):
            if cur:
                out.append("\n".join(cur))
            cur = [line] if line.strip() else []
        else:
            cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def _sep_row(blk):
    b = blk.strip()
    return b.startswith("|") and "-" in b and set(b.replace("|", "").strip()) <= set("-: ")


def _one_row_table(blks, i):
    """blks[i] 가 머리 · 구분선 · 데이터 1행짜리 표의 데이터 행인가 — 렌더러가 지적마다 앞에 두는 위치 표다.
    주장은 표 뒤 문단(**What**)에 있다. 여러 행 표(Lead 보고서)는 행마다 주장을 적으므로 해당 없음.
    ⛔ `_blocks` 는 표 행마다 블록을 끊는다 — 표 전체가 아니라 앞뒤 블록으로 판별한다."""
    row = lambda j: 0 <= j < len(blks) and blks[j].lstrip().startswith("|")
    return (i >= 2 and row(i) and not _sep_row(blks[i]) and _sep_row(blks[i - 1]) and row(i - 2)
            and not _sep_row(blks[i - 2]) and not row(i - 3) and not row(i + 1))


def cite_spans(texts, rules=None):
    """→ [(파일, 시작, 끝, 인용이 든 문단)] — 후보 추출. 문단 전체를 남겨 검증자가 **주장과 근거**를 함께 보게 한다.
    인용 행이 1행짜리 위치 표면 다음 `#` 제목 · `<!--` 마커 전까지 뒤 블록을 문맥에 붙인다 — 붙이지 않으면 렌더러
    보고서의 코드 위치 후보가 주장 없는 표 행만 문맥으로 받는다(실측 review C 23~25/후보).
    붙인 블록(What · Suggestion) 안의 인용도 같은 절 문맥을 쓴다 — 판정 단위는 렌더러 지적 절이다(What 안 근거 인용이
    같은 절 위치 표의 라벨 파일을 보게).
    문맥 상한은 CTX_CAP 이다(800 에서는 C 의 Suggestion 꼬리만 잘렸다).
    rules(fixture 가 선언한 규칙 출처 파일)로 풀리는 인용은 뺀다 — 참조는 발견이 아니다(검증 비율 분모에 들지 않는다)."""
    seen, out = set(), []
    for t in texts:
        blks = _blocks(t)
        sec_ctx, sec_end = None, -1
        for i, blk in enumerate(blks):
            ctx = blk.strip()
            if i < sec_end:
                ctx = sec_ctx      # 렌더러 지적 절의 What · Suggestion 안 인용 — 절 문맥
            elif _one_row_table(blks, i):
                j = i + 1
                while j < len(blks):
                    nxt = blks[j].strip()
                    if nxt.startswith("#") or nxt.startswith("<!--"):
                        break
                    ctx += "\n\n" + nxt
                    j += 1
                sec_ctx, sec_end = ctx, j
            for m in CITE_RE.finditer(blk):
                f = m.group(1)[2:] if m.group(1).startswith("./") else m.group(1)
                if rules and any(_same_file(f, r) for r in rules):
                    continue
                s, e = int(m.group(2)), int(m.group(3) or m.group(2))
                k = (f, min(s, e), max(s, e))
                if k not in seen:
                    seen.add(k)
                    out.append(k + (ctx[:CTX_CAP],))
    return sorted(out)


def cand_id(sp):
    return f"{sp[0]}:{sp[1]}" + (f"-{sp[2]}" if sp[2] != sp[1] else "")


def _same_file(cited, label_file):
    return cited == label_file or label_file.endswith("/" + cited) or cited.endswith("/" + label_file)


def rule_files(fxdir):
    """fixture 가 선언한 규칙 출처 파일(`expected-index.json` files) — 선언이 없으면 [](규칙 인용 제외 없음 · 옛 동작)."""
    try:
        return list(read_json(os.path.join(fxdir, "expected-index.json")).get("files") or [])
    except (OSError, ValueError, AttributeError):
        return []


def fixture_files(fxdir):
    """fixture 의 base/ · head/ 아래 파일 상대 경로(합집합 · `.fixture` 접미 제거) — 인용 해석용."""
    out = set()
    for side in ("base", "head"):
        root = os.path.join(fxdir, side)
        for dp, _, fns in os.walk(root):
            for f in fns:
                rel = os.path.relpath(os.path.join(dp, f), root)
                out.add(rel[:-len(".fixture")] if rel.endswith(".fixture") else rel)
    return sorted(out)


def resolve_cited(cited, files):
    """인용 파일 → 같은-파일 대조에 쓸 경로 · None(미해석).
    ① fixture 파일 목록이 없거나 경로 성분 끝이 맞는 파일이 있으면 인용 그대로 — 기존 규칙이 판정한다
    ② 아니면 인용 basename 이 fixture 파일 basename 의 **문자열 접미**인 파일이 정확히 하나일 때 그 파일
       (약칭 — `Interactor.swift` → `App/Watchlist/WatchlistInteractor.swift`). 둘 이상 · 0개면 None.
    ⛔ 실측: B 의 Lead 보고서는 약칭(`EditRow.swift` · `VC.swift`)을, C 의 렌더러 산출은 전체 경로를 쓴다 —
       경로 성분 끝만 받으면 인용 형식이 arm 차이가 된다."""
    if not files or any(_same_file(cited, f) for f in files):
        return cited
    base = cited.rsplit("/", 1)[-1]
    hit = [f for f in files if f.rsplit("/", 1)[-1].endswith(base)]
    return hit[0] if len(hit) == 1 else None


def near_labels(sp, labels, files=None):
    r = resolve_cited(sp[0], files)
    return [] if r is None else [lab["id"] for lab in labels["issues"] if _same_file(r, lab["file"])
                                 and sp[1] - LINE_TOL <= lab["line_end"] and lab["line_start"] <= sp[2] + LINE_TOL]


def score_review(labels, texts, verdicts=None, files=None, rules=None):
    """후보(인용) 마다 가린 검증자 판정 {real, label_ids, severity, axis} 로 센다. 라벨로 매핑된 발견은 **라벨의**
    severity·axis 로, 라벨 밖 진성 발견은 판정의 값으로 센다. 한 라벨은 한 번만 센다. 판정이 빠진 후보가 있으면 verified=False.
    files(fixture 파일 목록)가 있으면 인용 파일을 풀어(`resolve_cited`) 같은-파일 대조를 하고, 못 푼 인용의 라벨 매핑은
    받되 `mapping_unchecked` 로 센다(후보 수). rules 는 `cite_spans` 로 넘긴다(규칙 문서 인용 제외)."""
    spans = cite_spans(texts, rules)
    base = {"kind": "review", "candidates": len(spans), "labels_total": len(labels["issues"]),
            "empty": not any(t.strip() for t in texts)}
    if verdicts is None:
        return dict(base, verified=False, unverified=len(spans), by_severity=None, by_axis=None, labels_found=[],
                    verified_true=None, verified_ratio=None, mapping_errors=[], mapping_unchecked=0,
                    mapping_context=0)
    lab = {x["id"]: x for x in labels["issues"]}
    found, extras, unverified, real_n, bad, unchecked, via_ctx_n = set(), [], 0, 0, [], 0, 0
    for sp in spans:
        v = verdicts.get(cand_id(sp))
        if not isinstance(v, dict) or not isinstance(v.get("real"), bool):
            unverified += 1      # ⛔ "false" 같은 문자열은 판정이 아니다 — 참으로 읽히지 않게 미검증으로
            continue
        if not v["real"]:
            continue
        raw_ids = v.get("label_ids") or []
        r = resolve_cited(sp[0], files)
        own = [i for i in raw_ids if i in lab and (r is None or _same_file(r, lab[i]["file"]))]
        # 같은 지적 문단이 인용한 다른 파일의 라벨 — 렌더러의 1행 위치 표는 결함 위치와 근거 위치를 나란히 적는다(§14)
        ctx_files = [] if r is None else [x for x in (resolve_cited(mm.group(1)[2:] if mm.group(1).startswith("./")
                                                                    else mm.group(1), files)
                                                      for mm in CITE_RE.finditer(sp[3])) if x]
        via_ctx = [i for i in raw_ids if i in lab and i not in own and any(_same_file(x, lab[i]["file"]) for x in ctx_files)]
        ids = own + via_ctx
        if len(ids) != len(raw_ids):
            # ⛔ 없는 라벨·다른 파일의 라벨로 매핑 — 판정 형식 오류다. 무시하고 넘어가면 발견이 사라진다(미검증)
            bad.append(f"{cand_id(sp)}→{[i for i in raw_ids if i not in ids]}")
            unverified += 1
            continue
        if not ids and not (v.get("severity") in SEVERITIES and v.get("axis") in AXES_ALLOWED):
            # ⛔ real=true 인데 라벨도 severity·axis 도 없으면 어디에도 안 세진다 — B=C=0 으로 SC-3 이 통과한다(미검증)
            bad.append(f"{cand_id(sp)}: real 인데 라벨·severity·axis 없음")
            unverified += 1
            continue
        real_n += 1
        if ids:
            found.update(ids)
            if r is None:
                unchecked += 1   # 못 푼 인용(약칭 · fixture 밖 파일)의 라벨 매핑 — 채점기가 파일을 대조하지 못했다(검증자 매핑을 받았다)
            if via_ctx:
                via_ctx_n += 1   # 같은 지적 문단의 다른 인용 파일로 받은 매핑(후보 수)
        else:
            extras.append(v)
    by_sev = {s: 0 for s in SEVERITIES}
    by_axis = {x: 0 for x in AXES_ALLOWED}
    for i in found:
        by_sev[lab[i]["severity"]] += 1
        by_axis[lab[i]["axis"]] += 1
    for v in extras:
        by_sev[v["severity"]] += 1
        by_axis[v["axis"]] += 1
    ok = unverified == 0
    return dict(base, verified=ok, unverified=unverified, by_severity=by_sev, by_axis=by_axis,
                labels_found=sorted(found), verified_true=real_n,
                verified_ratio=round(real_n / len(spans), 4) if spans and ok else None, mapping_errors=bad,
                mapping_unchecked=unchecked, mapping_context=via_ctx_n)


def _items(v):
    return v if isinstance(v, list) else ([v] if isinstance(v, dict) else [])


def plan_items(rubric):
    """채점표 → [(id, severity, 판정 기준, 힌트 키워드)]. 절·질문·10배 부하·의존성 장애·롤백 = major, 잔재·소비자 = critical."""
    out = [(it["id"], "major", it.get("criterion", ""), it.get("keywords") or [])
           for k in ("sections", "questions") for v in (rubric.get(k) or {}).values() for it in _items(v)]
    out += [(it["id"], "major", it.get("criterion", ""), it.get("keywords") or [])
            for k in ("load_10x", "dependency_failure", "rollback") for it in _items(rubric.get(k))]
    out += [(it["id"], "critical", f"잔재 `{it.get('symbol')}`({it.get('file')}) 의 제거·처리를 계획이 명시한다", [it.get("symbol")])
            for it in rubric.get("residues") or []]
    out += [(it["id"], "critical", f"소비자 `{it.get('symbol')}`({it.get('file')}) 에 대한 영향과 수정을 계획이 명시한다",
             [it.get("symbol")]) for it in rubric.get("consumers") or []]
    return out


def score_plan(rubric, text, verdicts=None):
    """항목마다 가린 검증자 판정 {covered} 로 센다. ⛔ 키워드 적중만으로는 세지 않는다(부정문·다른 절의 용어도 맞는다)."""
    items = plan_items(rubric)
    base = {"kind": "plan", "items_total": len(items), "empty": not text.strip(), "items": [i[0] for i in items],
            "items_by_severity": {s: sum(1 for i in items if i[1] == s) for s in SEVERITIES}}
    if verdicts is None:
        return dict(base, verified=False, unverified=len(items), by_severity=None, covered=[])
    by_sev = {s: 0 for s in SEVERITIES}
    covered, unverified = [], 0
    for iid, sev, _, _ in items:
        v = verdicts.get(iid)
        if not isinstance(v, dict) or not isinstance(v.get("covered"), bool):
            unverified += 1
        elif v["covered"]:
            covered.append(iid)
            by_sev[sev] += 1
    return dict(base, verified=unverified == 0, unverified=unverified, by_severity=by_sev, covered=covered)


BLIND_INSTRUCTIONS = (
    "너는 가린 검증자다. items 의 산출물이 어느 실험 조건에서 나왔는지 모른다(anon id 만 있다). 판정 값은 JSON boolean 이다. "
    "review 항목: candidates 마다 context(그 지적 문단)를 읽고, fixtures[fixture].source 의 diff·파일로 **직접 확인**한 뒤 "
    "{real, label_ids, severity, axis, reason} 을 낸다. real=true 는 지적이 **코드로 확인되는 실제 결함·개선점**일 때만이다 — "
    "주장만 있고 코드와 맞지 않거나, 줄·파일이 틀렸거나, 정상 판정·단순 언급이면 false. label_ids=라벨 중 그 지적이 **내용으로** "
    "가리키는 것(near_labels 는 위치 힌트일 뿐). 라벨이 요구하는 조건(예: 대안 제시)을 충족할 때만 매핑한다. 라벨 밖 진성 지적이면 "
    "label_ids=[] 에 severity·axis 를 네가 정한다. reason 에 확인한 코드 위치를 적는다. "
    "plan 항목: fixtures[fixture].requirement 와 rubric 을 보고 각 항목에 {covered, reason} — 계획 본문이 그 기준을 **명시적으로 "
    "판정·이행**하면 true(부정문·용어 나열·다른 맥락의 언급은 false). 출력 = {anon: {cid 또는 항목 id: 판정}} JSON 하나.")


def _fixture_source(fxdir, cited):
    """fixture 의 base/·head/ → 검증자가 볼 diff 와 파일 본문(인용된 파일 + 변경 파일). git 없이 difflib 로 만든다."""
    import difflib
    b, h = os.path.join(fxdir, "base"), os.path.join(fxdir, "head")
    if not os.path.isdir(b):
        return None

    def read_tree(d):
        out = {}
        for dp, _, fn in os.walk(d):
            for f in fn:
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, d)
                rel = rel[:-len(".fixture")] if rel.endswith(".fixture") else rel
                try:
                    with open(full, encoding="utf-8") as fh:
                        out[rel] = fh.read()
                except (OSError, UnicodeDecodeError):
                    continue
        return out
    base = read_tree(b)
    head = dict(base, **(read_tree(h) if os.path.isdir(h) else {}))
    changed = sorted(k for k in head if base.get(k) != head.get(k))
    diff = "".join("".join(difflib.unified_diff(base.get(k, "").splitlines(True), head[k].splitlines(True),
                                                fromfile=f"a/{k}", tofile=f"b/{k}")) for k in changed)
    want = set(changed) | {k for k in head for c in list(cited) + rule_files(fxdir)
                           if _same_file(resolve_cited(c, sorted(head)) or c, k)}
    return {"diff": diff, "files": {k: head[k] for k in sorted(want)}}


def blind_pack(rows, fixtures_root, salt):
    """→ (검증자에게 줄 꾸러미, 열쇠). 꾸러미에는 run_id·arm·순서·경로가 없다 — 열쇠는 검증자에게 주지 않는다."""
    items, key, fixtures, cited = [], {}, {}, {}
    for r in rows:
        anon = "X" + sha_text(salt + r["run_id"])[:8]
        key[anon] = r["run_id"]
        texts = []
        for pth in (r.get("sources") or {}).get("artifacts") or []:
            try:
                with open(pth, encoding="utf-8", errors="replace") as fh:
                    texts.append(fh.read())
            except OSError:
                texts.append("")
        fxdir = os.path.join(fixtures_root, r.get("fixture") or "")
        if os.path.isfile(os.path.join(fxdir, "labels.json")):
            labels = read_json(os.path.join(fxdir, "labels.json"))
            fixtures[r["fixture"]] = {"kind": "review", "labels": [
                {k: x.get(k) for k in ("id", "axis", "severity", "file", "line_start", "line_end", "summary")}
                for x in labels["issues"]]}
            spans = cite_spans(texts, rule_files(fxdir))
            ff = fixture_files(fxdir)
            cited.setdefault(r["fixture"], (fxdir, set()))[1].update(sp[0] for sp in spans)
            items.append({"anon": anon, "kind": "review", "fixture": r["fixture"],
                          "artifacts_sha": [x.get("sha256") for x in r.get("artifacts") or []], "candidates": [
                {"cid": cand_id(sp), "file": sp[0], "lines": [sp[1], sp[2]], "context": PATH_SCRUB_RE.sub("<path>", sp[3]),
                 "near_labels": near_labels(sp, labels, ff)} for sp in spans]})
        elif os.path.isfile(os.path.join(fxdir, "rubric.json")):
            rubric = read_json(os.path.join(fxdir, "rubric.json"))
            req = os.path.join(fxdir, rubric.get("requirement") or "requirement.md")
            fixtures[r["fixture"]] = {"kind": "plan", "requirement": open(req, encoding="utf-8").read() if os.path.isfile(req) else None,
                                      "rubric": [{"id": i, "severity": s, "criterion": c, "hints": h}
                                                 for i, s, c, h in plan_items(rubric)]}
            items.append({"anon": anon, "kind": "plan", "fixture": r["fixture"],
                          "artifacts_sha": [x.get("sha256") for x in r.get("artifacts") or []],
                          "text": PATH_SCRUB_RE.sub("<path>", "\n\n".join(texts))})
        else:
            raise ValueError(f"채점표 없음 — {fxdir}")
    # ⛔ fixture 의 **모든** run 이 인용한 파일을 모은 뒤 source 를 한 번 만든다(run 마다 덮어쓰면 앞 run 의 근거가 빠진다)
    for fx, (fxdir, files) in cited.items():
        fixtures[fx]["source"] = _fixture_source(fxdir, sorted(files))
    items.sort(key=lambda x: x["anon"])
    pack = {"schema": "ab-blind/1", "instructions": BLIND_INSTRUCTIONS, "fixtures": fixtures, "items": items,
            "instrument_sha": instrument_sha()}
    return pack, key


def blind_unpack(pack, key, verdicts_anon):
    """검증자 판정(anon 기준) → run_id 기준. 빠진 후보·항목은 missing 으로 돌려준다(⛔ 조용히 채우지 않는다)."""
    runs, arts, missing = {}, {}, []
    for it in pack["items"]:
        v = verdicts_anon.get(it["anon"]) or {}
        need = [c["cid"] for c in it.get("candidates", [])] if it["kind"] == "review" else \
            [x["id"] for x in pack["fixtures"][it["fixture"]]["rubric"]]
        missing += [f"{it['anon']}:{n}" for n in need if n not in v]
        runs[key[it["anon"]]] = {n: v[n] for n in need if n in v}
        arts[key[it["anon"]]] = it.get("artifacts_sha")     # ⛔ 판정은 **이 산출물 버전**에 대한 것이다
    return runs, arts, missing


# ── judge (순수) ─────────────────────────────────────────────────────────
def row_invalid(row, score, opts):
    """run 1개의 무효 사유. ⛔ 무효 run 은 0건으로 세지 않고 비교에서 뺀다(AC-5)."""
    why = []
    lead, wf, g = row.get("lead") or {}, row.get("wf") or {}, row.get("gpt") or {}
    if "AC-4" in (opts.get("require") or []) and row.get("phase") not in ("baseline", None) \
            and row.get("workflow") in ("fz-review", "fz-peer-review"):
        # ⛔ AC-4 — 병합을 기본으로 둔 변경안(R-C S25)의 리뷰는 결정론 병합을 거친다. 후보 수가 줄었거나 병합 흔적이 없으면
        #    후보 보존을 확인하지 못한다. 판정이 AC-4 를 요구할 때만 본다 — 병합이 없는 변경안 · 기준선 판정은 이 계약 밖이다
        mg = row.get("merge") or {}
        sm = mg.get("summaries") or []
        if mg.get("violations"):
            why.append(f"AC-4 후보 보존 위반(병합 거부) {mg['violations']}회")
        bad = [(x.get("in"), x.get("out")) for x in sm if x.get("in") != x.get("out")]
        if bad:
            why.append(f"AC-4 입력 후보 수 ≠ 출력 {bad}")
        if not sm and not mg.get("violations"):
            why.append("AC-4 병합 흔적 없음 — 후보 보존을 확인하지 못한다")
    if norm_model(lead.get("model")) != opts["model"]:
        why.append(f"AC-1 Lead model {lead.get('model')}≠{opts['model']}")
    if lead.get("effort") != opts["effort"]:
        why.append(f"AC-1 Lead effort {lead.get('effort')}≠{opts['effort']}")
    wm = sorted({norm_model(m) for m in wf.get("models") or {}})
    we = sorted(wf.get("efforts") or {})
    if wm != [opts["model"]]:
        why.append(f"AC-1 워커 model {wm or 'unavailable'}")
    if we != [opts["effort"]]:
        why.append(f"AC-1 워커 effort {we or 'unavailable'}")
    if (g.get("ok") or 0) > (g.get("banners") or 0) or (g.get("unlinked") or 0) > 0:
        why.append(f"AC-1 GPT 배너 {g.get('banners')}/{g.get('ok')} (미연결 {g.get('unlinked')}) — 성공 호출의 model·effort 판정 불가")
    if (g.get("failed") or 0) > 0:
        why.append(f"AC-5 GPT 호출 실패 {g.get('failed')}건 — 실패가 섞인 run 은 대표값이 아니다")
    pl = row.get("plugin") or {}
    if not pl.get("tree_hash"):
        why.append("플러그인 트리 해시 없음 — arm 의 트리를 증명하지 못한다")
    elif not pl.get("source") or not pl.get("source_tree_hash"):
        why.append("플러그인 원본 선언 없음 — 사본이 무엇의 복제인지 증명하지 못한다")
    elif pl.get("source_tree_hash") != pl.get("tree_hash"):
        why.append(f"플러그인 사본이 선언된 원본({pl.get('source')})과 다르다")
    comp = row.get("complete") or {}
    if not comp.get("ok"):
        why.append("AC-5 미완주 — " + "; ".join((comp.get("why") or ["사유 없음"])[:3]))
    if score is not None and score.get("empty"):
        why.append("AC-5 빈 산출물 — 0건으로 세지 않는다")
    st = row.get("state") or {}
    if not st.get("start_hash") or not st.get("pristine_hash") or st.get("leak") is None:
        why.append("AC-7 시작 상태 미기록")
    elif st.get("problems"):
        why.append(f"AC-7 감시 불완전: {st['problems'][:2]}")
    elif st["leak"]:
        why.append(f"AC-7 시작 상태가 기준과 다르다: {st['leak']}")
    if not (row.get("input") or {}).get("hash") or not (row.get("input") or {}).get("tree_hash"):
        why.append("input-hash 없음(또는 입력 트리 해시 없음)")
    if (wf.get("advisor") or 0) > 0:
        why.append(f"워커 advisor {wf['advisor']}회 (0 이어야 한다)")
    wall = row.get("wall") or {}
    for w in wall.get("workflows") or []:
        if w.get("delta_pct") is None:
            why.append(f"wall_workflow 교차 불가 {w.get('run_id')} (에이전트 {w.get('wf_s')}s · Lead {w.get('lead_s')}s)")
        elif w["delta_pct"] > WALL_XCHECK_PCT:
            why.append(f"wall_workflow 두 자 차이 {w['delta_pct']}% > {WALL_XCHECK_PCT}% "
                       f"({w.get('run_id')}: 에이전트 {w.get('wf_s')}s · Lead {w.get('lead_s')}s)")
    md = wall.get("mtime_delta_s")
    if md is None or abs(md) > MTIME_TOL_S:
        why.append(f"최종 산출물 mtime 교차 실패 Δ={md}s (허용 {MTIME_TOL_S}s)")
    if opts.get("plugin_sha"):
        p = row.get("plugin") or {}
        if not str(p.get("sha") or "").startswith(opts["plugin_sha"]):
            why.append(f"plugin SHA {str(p.get('sha'))[:12]}≠{opts['plugin_sha']}")
        if p.get("dirty") is not False:
            why.append(f"plugin 트리 미커밋 변경(dirty={p.get('dirty')} · 기록 시점 {p.get('at')})")
    return why


def _key_fields(row, score):
    lead, inj, g = row.get("lead") or {}, row.get("injected") or {}, row.get("gpt") or {}
    k = {"input-hash": (row.get("input") or {}).get("hash"), "instrument": row.get("instrument_sha"),
         "injected": (inj.get("User"), inj.get("Project"), inj.get("AutoMem")),
         "cli": tuple(lead.get("cli_versions") or ()),
         # arm 마다 트리가 하나여야 한다 — 키 이름에 arm 을 넣어 B·C 풀을 나눈다
         f"plugin-tree:{row.get('arm')}": (row.get("plugin") or {}).get("tree_hash")}
    # ⛔ GPT 배너는 **배너가 있는 run 끼리만** 비교한다 — 호출 유무 자체는 변경안이 바꿀 수 있는 대상이다
    if g.get("models") or g.get("efforts"):
        k["gpt"] = (tuple(g.get("models") or ()), tuple(g.get("versions") or ()))
    # ⛔ Lead 가 `--effort` 를 명시한 호출은 측정 대상의 행동이다 — 기본값으로 간 호출의 effort 만 환경으로 비교한다(F-333)
    dflt = g.get("efforts_default", g.get("efforts"))
    if dflt:
        k["gpt-effort"] = tuple(dflt)
    if score is not None:
        k["labels"] = score.get("fixture_sha")
    return k


def _ordered_json(v):
    return json.dumps(v, sort_keys=True)


def group_invalid(rows, scores, roots_first=None):
    """비교 묶음 안에서 입력·계측기·주입 지침·CLI·GPT 배너·채점표·arm 별 플러그인 트리가 같아야 한다(다수와 다르면 무효).
    C 트리가 B 트리와 같으면 C 무효(같은 트리끼리 비교) · 입력 저장소 경로가 겹치면 뒤 run 무효(재사용)."""
    out = {r["run_id"]: [] for r in rows}
    keys = {r["run_id"]: _key_fields(r, scores.get(r["run_id"])) for r in rows}
    for f in sorted({f for k in keys.values() for f in k}):
        pool = [r for r in rows if f in keys[r["run_id"]]]
        vals = collections.Counter(_ordered_json(keys[r["run_id"]][f]) for r in pool)
        if len(vals) <= 1:
            continue
        first = {}
        for r in sorted(pool, key=lambda r: r.get("order") or 0):
            first.setdefault(_ordered_json(keys[r["run_id"]][f]), r.get("order") or 0)
        ref = sorted(vals.items(), key=lambda kv: (-kv[1], first[kv[0]]))[0][0]
        for r in pool:
            if _ordered_json(keys[r["run_id"]][f]) != ref:
                tag = "input-hash" if f == "input-hash" else f"{f} 불일치"
                out[r["run_id"]].append(f"{tag} — 묶음 다수와 다르다" + (" (recollect 필요)" if f == "instrument" else ""))
    btrees = collections.Counter((r.get("plugin") or {}).get("tree_hash") for r in rows if r.get("arm") == "B")
    bref = btrees.most_common(1)[0][0] if btrees else None
    for r in rows:
        if r.get("arm") != "B" and bref and (r.get("plugin") or {}).get("tree_hash") == bref:
            out[r["run_id"]].append("C 가 B 와 같은 플러그인 트리다 — 같은 트리끼리 비교가 된다")
    for r in rows:   # ⛔ 재사용은 원장 **전체**에서 본다(다른 워크플로가 같은 저장소를 써도 오염이다)
        root = (r.get("input") or {}).get("root")
        first = (roots_first or {}).get(root)
        if root and first and first != r["run_id"]:
            out[r["run_id"]].append(f"fixture 저장소 재사용 — {first} 과 같은 경로")
    return out


def _mean(xs):
    return sum(xs) / len(xs)


def _sev(score, sev):
    return (score.get("by_severity") or {}).get(sev, 0)


def _exact(B, C, nb=2, nc=2):
    """정식 비교는 arm 별 유효 run 이 **정확히** 정해진 수여야 한다 — 부족은 무효 run 재실행, 초과는 골라 쓰지 않는다."""
    if len(B) != nb or len(C) != nc:
        return f"유효 run B={len(B)}(정확히 {nb}) C={len(C)}(정확히 {nc}) — 부족이면 무효 run 을 다시 재고, 초과면 비교 run 을 고정하라"
    return None


def _unchecked_note(B, C, scores):
    """채점기가 받은 특수 매핑 수 — 파일 대조 못 한 매핑(약칭 · fixture 밖 인용) · 같은 지적 문단의 다른 인용 파일로 받은
    매핑(§14). 전부 0 인 항목은 줄을 내지 않는다."""
    out = []
    for key, what in (("mapping_unchecked", "파일 대조 못 한 라벨 매핑(검증자 매핑을 받았다)"),
                      ("mapping_context", "같은 지적 문단의 다른 인용 파일로 받은 라벨 매핑")):
        un = [(r["run_id"], (scores.get(r["run_id"]) or {}).get(key) or 0) for r in B + C]
        if any(n for _, n in un):
            out.append(what + " " + " · ".join(f"{k} {n}" for k, n in un if n))
    return out


def crit_sc3(B, C, scores, c_runs=2):
    """critical·major 각각 max(0, mean(B) − mean(C)) ≤ N, N = |B1 − B2|."""
    bad = _exact(B, C, 2, c_runs)
    if bad:
        return False, [bad + " · 미완주는 0건이 아니라 무효"]
    lines, ok = [], True
    for sev in GATED:
        b = [_sev(scores[r["run_id"]], sev) for r in B]
        c = [_sev(scores[r["run_id"]], sev) for r in C]
        n = abs(b[0] - b[1])
        loss = max(0.0, _mean(b) - _mean(c))
        good = loss <= n
        ok &= good
        lines.append(f"{sev} B={b} C={c} N={n} loss={loss:g} {'≤' if good else '>'} N")
    return ok, lines + _unchecked_note(B, C, scores)


def crit_sc4(B, C, scores):
    """C run 마다 6축 각 1건 이상 + 검증 비율이 mean(B) − |B1 − B2| 이상."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    ok, lines = True, []
    for r in C:
        ax = scores[r["run_id"]].get("by_axis") or {}
        miss = [a for a in AXES6 if (ax.get(a) or 0) < 1]
        if miss:
            ok = False
            lines.append(f"{r['run_id']} 축 누락 {miss}")
    br = [scores[r["run_id"]].get("verified_ratio") for r in B]
    cr = [scores[r["run_id"]].get("verified_ratio") for r in C]
    if None in br or None in cr:
        return False, lines + [f"검증 비율 미판정 B={br} C={cr} — 후보 0 이거나 가린 검증자 판정이 빠졌다"]
    floor = _mean(br) - abs(br[0] - br[1])
    good = _mean(cr) >= floor
    ok &= good
    lines.append(f"검증 비율 B={br} C={cr} 하한={floor:.4f} {'통과' if good else '미달'}")
    return ok, lines + _unchecked_note(B, C, scores)


def crit_sc6(B, C):
    """median(B) − median(C) > max(|B1 − B2|, |C1 − C2|) — wall_total 기준."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    b = [r["wall"]["total_s"] for r in B]
    c = [r["wall"]["total_s"] for r in C]
    if None in b or None in c:
        return False, [f"wall_total 없음 B={b} C={c}"]
    gain, noise = statistics.median(b) - statistics.median(c), max(abs(b[0] - b[1]), abs(c[0] - c[1]))
    return gain > noise, [f"wall B={b} C={c} 감소={gain:g}s {'>' if gain > noise else '≤'} 잡음={noise:g}s"]


SC7_FIELDS = (("lead", "out_tok"), ("lead", "messages"), ("lead", "tool_errors"), ("lead", "followup_prompts"),
              ("wf", "out_tok"), ("wf", "turns"), ("wf", "so_retries"))


def crit_sc7(B, C):
    """Lead·워커 출력·메시지·도구 오류·재시도(워커)·후속 요청 필드 필수 + 필수 검증(B 공통 stage · 성공한 GPT 호출 수) 보존.
    성공한 GPT 호출 = 직접 호출(`gpt.ok`) + 런처 호출(`gpt.launcher_ok` — 감사 exit 0). ⛔ 런처를 빼면 GPT 리뷰를
    런처로 옮긴 후보가 검증을 잃은 것처럼 보인다(실측 review C 4 run: 직접 0 · 런처 1)."""
    ok, lines = True, []
    for r in B + C:
        miss = [f"{a}.{b}" for a, b in SC7_FIELDS if (r.get(a) or {}).get(b) is None]
        if miss:
            ok = False
            lines.append(f"{r['run_id']} 필드 없음 {miss}")
    bad = _exact(B, C)
    if bad:
        return False, lines + [bad]
    need = set.intersection(*[set(r["wf"].get("stages") or ()) for r in B])
    direct = lambda r: r["gpt"].get("ok") or 0
    launch = lambda r: r["gpt"].get("launcher_ok") or 0
    said = lambda r: f"{direct(r) + launch(r)}(직접 {direct(r)} + 런처 {launch(r)})"
    gmin = min(direct(r) + launch(r) for r in B)
    for r in C:
        lost = sorted(need - set(r["wf"].get("stages") or ()))
        if lost:
            ok = False
            lines.append(f"{r['run_id']} 필수 stage 누락 {lost}")
        if direct(r) + launch(r) < gmin:
            ok = False
            lines.append(f"{r['run_id']} 성공한 GPT 호출 {said(r)} < 기준 {gmin}")
    if ok:
        lines.append(f"필드 존재 · 필수 stage {sorted(need)} 보존 · 성공한 GPT 호출 ≥ {gmin} — "
                     + " | ".join(f"{r['run_id']} {said(r)}" for r in C))
    return ok, lines


def crit_crossover(B, C):
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    seq = sorted(B + C, key=lambda r: r["order"])
    orders, arms = [r["order"] for r in seq], [r["arm"] for r in seq]
    good = len(set(orders)) == len(orders) and all(x != y for x, y in zip(arms, arms[1:]))
    return good, [f"순서 {list(zip(orders, arms))} {'교차' if good else '⛔ 교차 아님'}"]


def crit_sc5(B, C, scores):
    """계획 완결성(SC-5) — 유효한 C run 마다 채점표 항목을 **전부** 덮는다: 절 6 · Q1~Q8 · 10배 부하 · 의존성 장애 · 롤백,
    제거 fixture 는 잔재 · 소비자까지(누락 0). 두 채점표 모두 절 · 질문마다 항목이 1개라 '각각' = '전부'다.
    기준선 대비가 아니라 절대 조건이다 — B 는 비교 묶음 확인(_exact)에만 쓴다."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    good, lines = True, []
    for r in C:
        s = scores.get(r["run_id"]) or {}
        if s.get("kind") != "plan" or not isinstance(s.get("items"), list):
            return False, [f"⛔ {r['run_id']}: 항목 목록이 있는 계획 점수가 아니다 — score 를 다시"]
        miss = sorted(set(s["items"]) - set(s.get("covered") or []))
        good &= not miss
        lines.append(f"{r['run_id']} {len(s['items']) - len(miss)}/{len(s['items'])}" + (f" ⛔누락 {miss}" if miss else ""))
    return good, lines


def crit_gpt_wf_wall(B, C):
    """S26 — 유효한 C run 마다 GPT 독립 플랜 wall 과 Workflow wall 이 둘 다 재졌는가(값을 줄에 남긴다).
    ⛔ 기준선(B)은 독립 플랜이 없는 트리라 비교 묶음 확인(_exact)에만 쓴다."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    good, lines = True, []
    for r in C:
        cp = r.get("critical") or {}
        ok = cp.get("gpt_plan_s") is not None and cp.get("wf_s") is not None
        good &= ok
        lines.append(f"{r['run_id']} GPT {cp.get('gpt_plan_s')}s · Workflow {cp.get('wf_s')}s" + ("" if ok else " ⛔ 측정 없음"))
    return good, lines


def crit_critical_path(B, C):
    """S26 — C run 마다 임계 경로(workflow · gpt)를 기록했는가. GPT 가 더 길면 '임계 경로 전환' 으로 적는다(통과 · 실패와 무관한 기록)."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    good, lines = True, []
    for r in C:
        pth = (r.get("critical") or {}).get("path")
        good &= pth in ("gpt", "workflow")
        lines.append(f"{r['run_id']} 임계 경로 {pth or '⛔ 미상'}" + (" ← 전환(GPT 독립 플랜이 Workflow 보다 길다)" if pth == "gpt" else ""))
    return good, lines


def crit_blind_labels(B, C, scores):
    """가린 검증 — 비교에 쓴 run 의 점수가 전부 blind-unpack 판정에서 왔고(blind_pack_sha), B · C 가 **한 꾸러미**에서
    판정됐다. arm 별로 따로 싼 꾸러미는 묶음 자체가 arm 을 드러낸다(experiment-log §5.10 §7 — 검증자는 어느 arm 의
    산출물인지 알 수 없어야 한다). 판정 전 · 미완 · 낡은 점수는 judge_rows 가 먼저 UNRUN 으로 거른다."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    packs = {r["run_id"]: (scores.get(r["run_id"]) or {}).get("blind_pack_sha") for r in B + C}
    none = sorted(rid for rid, p in packs.items() if not p)
    if none:
        return False, [f"⛔ 가린 판정이 아닌 점수 {none}"]
    uniq = sorted(set(packs.values()))
    good = len(uniq) == 1
    return good, [f"꾸러미 {len(uniq)}개" + ("" if good else f" — ⛔ B · C 가 다른 꾸러미에서 판정됐다 {uniq}")]


def _crit_invalid(c):
    """AC-1 · AC-4 · AC-5 · AC-7 · input-hash — run 무효 사유를 거른 뒤 비교에 쓴 run 이 정해진 수인가(사유 접두가 그 기준)."""
    def judge(vB, vC, scores, opts, inv):
        hit = [rid for rid, why in inv.items() if any(w.startswith(c) for w in why)]
        bad = _exact(vB, vC, 2, opts["runs"] if opts["phase"] == "release-smoke" else 2)
        good = bad is None
        return good, [f"비교에 쓴 run 의 {c} 무효 0 · 제외 {hit or '없음'}" + ("" if good else f" — ⛔ {bad}")]
    return judge


# 판정 표 — 기준 id → 판정 함수 `(유효 B, 유효 C, 점수, 판정 옵션, 무효 사유) → (통과, 출력 줄)`.
# ⛔ judge_rows 는 이 표만 거쳐 기준을 판정한다(F-335 ③). 표에 없는 기준은 judge_rows 입구에서 UNRUN 이다 — 받고 무시하지 않는다.
#    구현한 기준(SC-8 · AC-6 은 아직 없다)을 더할 때는 여기에 한 줄을 더한다. 출력 줄 형식 · 순서는 기존 판정과 같다.
CRITERIA = {
    "SC-3": lambda vB, vC, scores, opts, inv: crit_sc3(vB, vC, scores),
    "SC-3-smoke": lambda vB, vC, scores, opts, inv: crit_sc3(vB, vC, scores, c_runs=opts["runs"]),
    "SC-4": lambda vB, vC, scores, opts, inv: crit_sc4(vB, vC, scores),
    "SC-5": lambda vB, vC, scores, opts, inv: crit_sc5(vB, vC, scores),
    "SC-6": lambda vB, vC, scores, opts, inv: crit_sc6(vB, vC),
    "SC-7": lambda vB, vC, scores, opts, inv: crit_sc7(vB, vC),
    "AC-1": _crit_invalid("AC-1"),
    "AC-4": _crit_invalid("AC-4"),
    "AC-5": _crit_invalid("AC-5"),
    "AC-7": _crit_invalid("AC-7"),
    "crossover-order": lambda vB, vC, scores, opts, inv: crit_crossover(vB, vC),
    "input-hash": _crit_invalid("input-hash"),
    "blind-labels": lambda vB, vC, scores, opts, inv: crit_blind_labels(vB, vC, scores),
    "gpt-wf-wall": lambda vB, vC, scores, opts, inv: crit_gpt_wf_wall(vB, vC),
    "critical-path": lambda vB, vC, scores, opts, inv: crit_critical_path(vB, vC),
}
# ⛔ 구현한 기준만 판정한다. 나머지(SC-8·AC-6)는 **exit 2** — 받고 무시하면 그것이 AC-5 의 '빠른 성공'이다.
IMPLEMENTED = tuple(CRITERIA)


def select(runs, workflow, fixture, arm, phase, release=None):
    rows = [r for r in runs.values() if r.get("workflow") == workflow and r.get("fixture") == fixture
            and r.get("arm") == arm and r.get("phase") == phase and (release is None or r.get("release") == release)]
    return sorted(rows, key=lambda r: (r.get("order") or 0, r["run_id"]))


def judge_rows(runs, scores, opts, source_check=None):
    """→ (exit, 출력 줄). source_check(row) → 원천 대조 무효 사유(없으면 생략)."""
    out = []
    req = opts["require"]
    gp = [x for x in req if x in GPT_PASS_CRIT]
    if gp:
        return UNRUN, [f"UNRUN: {gp} 는 gpt-pass 행 기준이다 — `judge --require {','.join(gp)} --envs …` 로 따로 부른다(run 판정과 섞지 않는다)"]
    unknown = [x for x in req if x not in IMPLEMENTED and x != "baseline-runs"]
    if unknown:
        return UNRUN, [f"UNRUN: 미구현 기준 {unknown} — 구현 스텝(S25~S27)에서 추가한다. ⛔ 받고 무시하지 않는다"]
    if opts["phase"] == "baseline" and set(req) - {"baseline-runs"}:
        return UNRUN, [f"UNRUN: baseline phase 는 baseline-runs 만 판정한다 — 받은 기준 {req}. ⛔ 받고 무시하지 않는다"]
    for flag in ("envs", "options_on", "require_passed"):
        if opts.get(flag):
            return UNRUN, [f"UNRUN: --{flag.replace('_', '-')} 미구현 — ⛔ 받고 무시하지 않는다"]
    if not runs:
        return UNRUN, ["UNRUN: 원장에 run 행이 없다 — 측정 실패를 먼저 의심한다"]
    # ⛔ 기준선 행이 있는 워크플로만 보면 C 행만 있는 워크플로가 조용히 빠진다 — 전체 행에서 도출한다(v4.40.0 리뷰)
    wfs = opts["workflows"] or sorted({r["workflow"] for r in runs.values()})
    if not wfs:
        return UNRUN, ["UNRUN: 판정할 워크플로가 없다(baseline 행 0)"]
    worst = PASS
    removal_seen = False      # SC-5 — 제거 · 리팩터링 fixture(critical 항목이 있는 채점표)를 판정했는가
    roots_first = {}
    for r in sorted(runs.values(), key=lambda r: (r.get("order") or 0, r["run_id"])):
        root = (r.get("input") or {}).get("root")
        if root:
            roots_first.setdefault(root, r["run_id"])
    cphase = "release-smoke" if opts["phase"] == "release-smoke" else "change"
    # ⛔ 비교 묶음 = (워크플로, fixture). 워크플로만으로 묶으면 fixture 가 둘인 워크플로(fz-plan: feature·removal)의
    #    소수 쪽이 '입력 해시 불일치' 로 무효가 된다.
    groups = []
    for wf in wfs:
        fxs = sorted({r.get("fixture") for r in runs.values() if r.get("workflow") == wf and (
            r.get("phase") == "baseline" or (opts["phase"] != "baseline" and r.get("phase") == cphase))}, key=str)
        if not fxs:
            out.append(f"FAIL {wf}: 이 워크플로의 run 이 원장에 없다")
            worst = FAIL
        groups += [(wf, fx) for fx in fxs]
    for wf, fx in groups:
        label = f"{wf}[{fx}]"
        B = select(runs, wf, fx, "B", "baseline")
        C = [] if opts["phase"] == "baseline" else select(runs, wf, fx, opts["arm"], cphase, opts.get("release"))
        inv = {r["run_id"]: row_invalid(r, scores.get(r["run_id"]), dict(opts, plugin_sha=opts.get("plugin_sha") if r in B else None))
               for r in B + C}
        for rid, why in group_invalid(B + C, scores, roots_first).items():
            inv[rid] += why
        if source_check:
            for r in B + C:
                inv[r["run_id"]] += source_check(r)
        for r in B + C:
            if inv[r["run_id"]]:
                out.append(f"  INVALID {r['run_id']} — " + " · ".join(inv[r["run_id"]]))
        vB = [r for r in B if not inv[r["run_id"]]]
        vC = [r for r in C if not inv[r["run_id"]]]
        if opts["phase"] == "baseline":
            good = len(vB) >= opts["min_runs"]
            out.append(f"{'PASS' if good else 'FAIL'} baseline-runs {label}: 유효 {len(vB)}/{len(B)} (필요 {opts['min_runs']})"
                       + (" — " + ", ".join(r["run_id"] for r in vB) if vB else ""))
            worst = max(worst, PASS if good else FAIL)
            continue
        if {"SC-3", "SC-3-smoke", "SC-4", "SC-5", "blind-labels"} & set(req):
            cur_i = opts.get("instrument") or instrument_sha()
            unv = [r["run_id"] for r in vB + vC if not (scores.get(r["run_id"]) or {}).get("verified")
                   or (scores.get(r["run_id"]) or {}).get("artifacts_sha") != _artifact_shas(r)
                   or (scores.get(r["run_id"]) or {}).get("instrument_sha") != cur_i]
            if unv:
                out.append(f"UNRUN {label}: 가린 검증자 판정 없음·미완·낡음 {unv} — blind-pack → 검증자 → blind-unpack → score --verdicts")
                worst = UNRUN
                continue
        for c in req:
            crit = CRITERIA.get(c)
            if crit is None:
                good, lines = False, [f"판정기 없음 {c}"]
            else:
                good, lines = crit(vB, vC, scores, opts, inv)
            if c == "SC-5":
                removal_seen |= any(((scores.get(r["run_id"]) or {}).get("items_by_severity") or {}).get("critical", 0) > 0
                                    for r in vC)
            out.append(f"{'PASS' if good else 'FAIL'} {c} {label}: " + " | ".join(lines))
            worst = max(worst, PASS if good else FAIL)
    if "SC-5" in req and not removal_seen and opts["phase"] != "baseline":
        # ⛔ feature fixture 만으로 SC-5 를 통과시키지 않는다 — 기준의 '제거 · 리팩터링 fixture 잔재 · 소비자 누락 0' 이 조용히 빠진다
        out.append("UNRUN SC-5: 제거 · 리팩터링 fixture(잔재 · 소비자 항목이 있는 채점표)를 판정한 C run 이 없다")
        worst = max(worst, UNRUN)
    return worst, out


# ── 원천 대조 (I/O) — ⛔ 기록된 collect 인자로 행을 **다시 만들어** 판정 필드 전체를 대조한다 ───────────────
VERIFY_FIELDS = {
    "transcript": ("lead.model", "lead.effort", "lead.out_tok", "lead.messages", "lead.cli_versions", "lead.tool_errors",
                   "lead.followup_prompts", "plugin.roots", "plugin.sha", "plugin.tree_hash", "injected",
                   "wall.total_s", "wall.start", "wall.end", "wall.mtime_delta_s", "artifacts", "gpt.calls", "gpt.ok",
                   "gpt.failed", "gpt.unlinked", "gpt.banners", "gpt.models", "gpt.efforts", "gpt.efforts_default", "gpt.versions",
                   "plugin.dirty", "plugin.source", "plugin.source_tree_hash", "input.prompt_sha"),
    "wf-metrics": ("wf.agents", "wf.out_tok", "wf.turns", "wf.so_retries", "wf.advisor", "wf.models", "wf.efforts",
                   "wf.stages", "wf.stage2_ran", "wall.workflows", "complete.ok"),
    "start-state": ("state.start_hash", "state.pristine_hash", "state.leak", "state.problems"),
    "input-hash": ("input.hash", "input.commits", "input.root", "input.tree_hash"),
}


def _dig(o, dotted):
    for k in dotted.split("."):
        o = o.get(k) if isinstance(o, dict) else None
    return o


def verify_sources(row, kinds):
    args = row.get("collect_args")
    if not args:
        return ["원천 대조 불가 — collect_args 없음"]
    try:
        fresh = build_row(collect_spec_args(args), dry=True)   # CollectSpec 필드만 — 옛 행의 CLI 전역 키는 버린다
    except Exception as e:  # noqa: BLE001 — 재구성 실패는 무효 사유로 기록한다(통과 아님)
        return [f"원천 재구성 실패 {type(e).__name__}: {e}"]
    why = []
    for k in kinds:
        for f in VERIFY_FIELDS.get(k, ()):
            a, b = _dig(row, f), _dig(fresh, f)
            if a != b:
                why.append(f"원천 불일치 {f}: 행 {str(a)[:60]} · 원천 {str(b)[:60]}")
    if "instrument-sha" in kinds and row.get("instrument_sha") != instrument_sha():
        why.append(f"계측기 변경 — 행 {row.get('instrument_sha')} · 현재 {instrument_sha()} (recollect 필요)")
    return why


def _js(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def recollect_diff(old, new):
    """recollect 전후 → (바뀐 판정 필드 · 새로 생긴 무효 사유 · 악화). ⛔ 차이를 말하지 않으면 재수집 퇴화가 exit 0 으로 숨는다
    (실측 R-C C2: 사라진 heredoc 스크립트로 wall 3949→3765s · mtime Δ 184s 가 무효가 됐는데 한 줄 'complete=True' 뿐이었다).
    판정 필드 = VERIFY_FIELDS 전부 + complete.why. 악화 = 완주 True→아님, 또는 row_invalid(기본 model·effort)에 새 사유가 생겼다 —
    사유 문자열 비교라 이미 무효인 행의 수치만 바뀌어도 악화로 센다(안전 쪽)."""
    opts = {"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT}
    fields = sorted({f for fs in VERIFY_FIELDS.values() for f in fs} | {"complete.why"})
    changed = [f for f in fields if _js(_dig(old, f)) != _js(_dig(new, f))]
    before = row_invalid(old, None, opts)
    added = [w for w in row_invalid(new, None, opts) if w not in before]
    lost = (old.get("complete") or {}).get("ok") is True and (new.get("complete") or {}).get("ok") is not True
    return changed, added, bool(added or lost)


def _artifact_shas(row):
    return [x.get("sha256") for x in row.get("artifacts") or []]


def _read_texts(row):
    texts = []
    for pth in (row.get("sources") or {}).get("artifacts") or []:
        try:
            with open(pth, encoding="utf-8", errors="replace") as fh:
                texts.append(fh.read())
        except OSError:
            texts.append("")
    return texts
