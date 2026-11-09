#!/usr/bin/env python3
# diff-parse: not-a-diff — 줄 앵커는 skills/fz-peer-review/scripts/diff_anchors.py 가 계산한다. 이 파일은 diff 줄을 직접 읽지 않고,
#   self-test 의 합성 diff 는 그 스크립트에 넘기는 입력일 뿐이다.
"""리뷰 산출물 단일 출처 렌더러 (S20b) — review JSON 하나에서 review-report.md · pr-comments.md · 게시 payload 를 만든다.

Lead 는 판정과 문장만 JSON 에 쓴다. 두 문서와 payload 를 따로 쓰면 같은 이슈를 세 번 옮겨 적게 되고(peer-review 호출당 Bash 인자의
31.5% — review-report 18.1% · pr-comments 13.4%), 셋이 어긋나도 아무도 모른다. 줄 앵커는 diff_anchors.py 로만 계산한다 —
인라인 python 으로 다시 짜지 않는다. 게시 규칙의 정본은 `modules/peer-review-inline-anchoring.md` 이고 여기서 옮긴 것은 이렇다.

  payload     top-level body = review-report.md 전문 · 다중 라인은 start_line·start_side·line·side 넷 · 단일 줄은 line·side 만
  구간 선택    겹치는 hunk 가 여럿이면 고르지 않는다 — site 에 pick(diff_anchors 후보 번호, 0부터)이 없으면 거부한다
  앵커 불가    diff 밖 지점은 같은 코멘트 본문에 `path:start-end` 와 함께 인용한다. 인라인 자리가 하나도 없는 이슈는
              body(리포트 전문)에만 남고 미리보기의 reportOnly 에 적힌다
  다지점      지점 3개 이상은 [k/N] 으로 나눠 각 지점에 단다(순서 = sites 순서 = Lead 가 정한 인과 순서). 앵커 불가 조각은
              같은 이슈의 첫 인라인 조각에 인용한다. 2개면 나누지 않고 한 코멘트에서 다른 지점을 가리킨다
  확인 게이트  (a) event ≠ COMMENT (b) 앵커 불가 지점 (c) Lead 가 구간을 골랐다 — render-preview.json 의 reasons.
              게시와 사용자 승인은 Lead 절차 그대로다

입력 (review JSON)
  필수  verdict(최종 판정 문장) · issues(배열 — 0건도 유효)
  선택  pr{number, headSha} · event(COMMENT · REQUEST_CHANGES · APPROVE, 기본 COMMENT) · matrix(Confidence Matrix 마크다운) ·
        severityNote(보정 근거) · strengths(배열)
  issue 필수 id · severity(critical · major · minor · suggestion) · what(WHY 포함) · sites
        선택 origin · confidence · foundBy · suggestion · comment(PR 코멘트 톤 — 없으면 what + suggestion)
  site  필수 path · start · end   선택 side(RIGHT · LEFT, 기본 RIGHT) · pick · note(조각 설명) · quote(diff 밖일 때 인용할 코드) ·
        expect(그 줄에 있어야 할 코드 조각 — ⛔ payload 를 만들 때 인라인 코멘트 **전건**에 필수 · F-069 아래)
  issue 선택 axis(발견 축 — code_quality · structure · correctness · runtime_safety · direction · other)
  review 선택 costLog(review.json 폴더 기준 cost-log.json 상대 경로 — `## 실측 비용` 절 · 파일이 없으면 UNRUN)
  판정 한계(round 2 S9 — 키가 없으면 옛 바이트 그대로)
    issue 선택 alternatives[{label, description, pros?, cons?}] · recommended(그 label 중 하나) — 외부 렌즈(GPT)가 낸 대안을 **원문**
              그대로 옮긴다(F-115 — 자기 말로 요약하면 추천 해법이 사라졌다). recommended 가 label 에 없으면 입력 불가(재서술 차단)
    review 선택 axisCoverage — review_merge.py 병합 행({axis, status, claude[], gpt[]}) 또는 {axis, status, note} · `## 축 판정` 표.
              gap 은 '판정 안 함'으로 그린다 — 위반 없음(none)과 섞지 않는다(F-514 · F-559)
              unverifiedPremises[{claim, why?, howToMeasure?, affects?, lens?}] — 렌즈의 재지 않은 전제 · `## 재지 않은 전제`(F-448)
              dismissed[{id, what, reason}] — Lead 가 판단으로 뺀 관찰 · `## Lead 기각 — 의도 확인 후보` · synthesized-issues.json 에
              disposition exclude + disposition_reason(F-517 — 기각이 산출물에 흔적 없이 사라졌다). 큐레이션 excluded 의 reason 도 같은 칸에 싣는다

게시 대상 줄 검증(Gate 4.5 · F-069) — payload 를 만들면(pr.headSha) 앵커가 붙는 코멘트 **전건**(minor · suggestion 포함)의 site 에
  expect 가 있어야 하고, 그 문구가 앵커 구간의 diff 줄 중 하나에 들어 있어야 한다. 앵커 가능 판정은 줄이 hunk 안인지만 본다 —
  엉뚱한 줄도 hunk 안이면 anchorable 이다. 없거나 어긋나면 거부(exit 1).
파생 산출물(F-201) — out-dir 에 synthesized-issues.json 이 있으면 렌더한 판정으로 disposition(include · question · exclude:<코드> · exclude)과
  최종 severity 를 다시 쓴다(바뀐 값의 처음 값은 `*_initial` 로 보존) · review-index.md 의 렌더 블록(`<!-- fz-render:begin -->`)을
  다시 쓴다(대상 head · 판정 · 이슈 목록 — 인덱스 파일이 있을 때만 · 렌더러가 새로 만들지 않는다). 재평가로 review.json 을 고치고
  다시 렌더하면 넷이 함께 바뀐다.

모드
  --review FILE --diff FILE --out-dir DIR   review-report.md · pr-comments.md · render-preview.json · payload.json(pr.headSha 가 있을 때만)
  --head-sha SHA   게시 직전 다시 읽은 대상 head(`gh pr view N --json headRefOid`) — review 의 pr.headSha · target.sha 와 다르면
              거부(exit 1 · F-068 — 리뷰 중 force-push 로 대상이 바뀌면 이미 무효인 코멘트를 게시한다)
  --lang ko   리포트 산문(verdict · what · suggestion · comment · strengths · severityNote)의 한글 비율이 30% 밖이면 거부(F-020)
  --example   위 형식의 최소 review JSON 을 stdout 으로 — Lead 가 형식을 이 코드에서 다시 읽지 않게 한다(self-test example-roundtrip 이
              같은 객체를 검증 · 렌더한다)
  --require-curation   `excluded` 키가 없는 review 를 거부한다(exit 1) — fz-peer-review 기본 경로(Curate)가 이 플래그로 렌더한다.
              `--no-curate` 일 때만 뺀다 · fz-review `--render` 같은 옛 직접 렌더는 플래그 없이 그대로다
  --example-curated-dir DIR   큐레이션한 묶음 예시(review.json · merged.json · synthesized-issues.json)를 DIR 에 쓴다 — GPT 전용 후보 포함

큐레이션(review 에 `excluded` 키가 있을 때) — 렌더 **전에** scripts/check_comment_worthy.py 의 계약을 돌린다. 위반이면 exit 1 · 판정 불가면 2 ·
  둘 다 파일을 쓰지 않는다. 통과하면 리포트는 ① 이번 PR 버그 ② 구조·품질 제안(non-blocking) ③ 의도 확인 질문 → ④ 참고(E4) → 제외 후보 표 →
  기존 스레드 대조 줄 → 답글 초안(E5 reply) 순이고, pr-comments.md 끝에 답글 초안을 붙인다(payload 밖 — 기존 스레드 답글은 따로 단다).
  추가 키: target{kind, ref, sha}(gather 의 target.json) · candidates(후보 원본 상대 경로) · issue.kind · evidence · repro · measure · refute · covers ·
  distinctFrom · gptPass(independent · challenger · none) · excluded[{id, what, code E1~E8, reason, covers?, duplicateOf?, reply?, refute?}] — 계약 정본은 check_comment_worthy.py 머리말
  --self-test

exit: 0=렌더 · 1=거부(구간 선택 필요 · 후보 밖 pick · body 상한 초과) · 2=입력 불가(⛔ 통과 아님 — 빈 JSON · 필수 키 없음)
실패하면 어떤 파일도 쓰지 않는다 — 반쪽 산출물이 게시로 흘러가면 엉뚱한 줄에 코멘트가 달린다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANCHORS = ROOT / "skills" / "fz-peer-review" / "scripts" / "diff_anchors.py"
OK, REJECT, UNRUN = 0, 1, 2
SEVERITIES = ("critical", "major", "minor", "suggestion")
EVENTS = ("COMMENT", "REQUEST_CHANGES", "APPROVE")
BODY_LIMIT = 65536                        # GitHub 리뷰 body 상한 — 넘기면 게시가 거부된다
ID_RE = re.compile(r"^[A-Za-z0-9:_.\-]+$")
MARK = "<!-- fz-review:{} -->"             # 세 산출물 대조 · 게시 뒤 착지 검증에서 코멘트와 이슈의 짝을 맞춘다(렌더링에 안 보인다)
MARK_RE = re.compile(r"<!-- fz-review:([A-Za-z0-9:_.\-]+) -->")
OUTPUTS = ("review-report.md", "pr-comments.md", "render-preview.json", "payload.json")
AXES = ("code_quality", "structure", "correctness", "runtime_safety", "direction", "other")   # peer-review.js discoveryAxis 와 같은 이름
LANG_MIN = 0.3                            # --lang ko — 한글 / (한글 + 라틴 글자). 식별자를 백틱 없이 섞어도 넘고, 영어 산문은 0 근처다
INDEX_BEGIN, INDEX_END = "<!-- fz-render:begin -->", "<!-- fz-render:end -->"
STATUS_KO = {"finding": "발견", "found": "발견", "gap": "판정 안 함", "none": "위반 없음", "not_applicable": "해당 없음"}   # Claude · GPT 두 어휘(F-559)


class InputError(Exception):
    """입력 불가 — exit 2."""


class Reject(Exception):
    """Lead 결정이 필요한 계약 위반 — exit 1."""


def anchors_module():
    if not ANCHORS.is_file():
        raise InputError(f"diff_anchors.py 가 없다 — {ANCHORS}")
    spec = importlib.util.spec_from_file_location("diff_anchors", ANCHORS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate(r) -> None:
    if not isinstance(r, dict) or not r:
        raise InputError("빈 JSON — verdict 와 issues 가 있는 객체여야 한다")
    if not isinstance(r.get("verdict"), str) or not r["verdict"].strip():
        raise InputError("verdict(최종 판정 문장)가 없다")
    if not isinstance(r.get("issues"), list):
        raise InputError("issues 배열이 없다")
    if "launchSmoke" in r and (not isinstance(r["launchSmoke"], str) or not r["launchSmoke"].strip()):
        raise InputError("launchSmoke 는 launch-smoke.md 첫 줄(문자열)이다 — 비우려면 키를 빼라")
    if r.get("event", "COMMENT") not in EVENTS:
        raise InputError(f"event 는 {' · '.join(EVENTS)} 중 하나다 — {r.get('event')!r}")
    seen = set()
    for i in r["issues"]:
        iid = i.get("id") if isinstance(i, dict) else None
        if not isinstance(iid, str) or not ID_RE.match(iid):
            raise InputError(f"issue id 가 없거나 형식 밖이다(영숫자 · : _ . -) — {iid!r}")
        if iid in seen:
            raise InputError(f"issue id 중복 — {iid}")
        seen.add(iid)
        if i.get("severity") not in SEVERITIES:
            raise InputError(f"{iid}: severity 는 {' · '.join(SEVERITIES)} 중 하나다")
        if not isinstance(i.get("what"), str) or not i["what"].strip():
            raise InputError(f"{iid}: what 이 없다")
        sites = i.get("sites")
        if not isinstance(sites, list) or not sites:
            raise InputError(f"{iid}: sites 가 비었다 — 지점이 하나는 있어야 한다")
        for s in sites:
            if not isinstance(s, dict) or not isinstance(s.get("path"), str) or not s["path"]:
                raise InputError(f"{iid}: site 에 path 가 없다")
            if not (is_int(s.get("start")) and is_int(s.get("end")) and 1 <= s["start"] <= s["end"]):
                raise InputError(f"{iid}: site 의 start·end 는 1 이상 정수이고 start ≤ end 다 — {s}")
            if s.get("side", "RIGHT") not in ("RIGHT", "LEFT"):
                raise InputError(f"{iid}: side 는 RIGHT · LEFT 다")
            if "pick" in s and not is_int(s["pick"]):
                raise InputError(f"{iid}: pick 은 후보 번호(0부터)다")
            if "expect" in s and not (isinstance(s["expect"], str) and s["expect"].strip()):
                raise InputError(f"{iid}: expect 는 그 줄에 있어야 할 코드 조각(빈 문자열 아님)이다")
        if "axis" in i and i["axis"] not in AXES:
            raise InputError(f"{iid}: axis 는 {' · '.join(AXES)} 중 하나다 — {i['axis']!r}")
        alts = i.get("alternatives")
        if alts is not None and (not isinstance(alts, list) or not alts
                                 or any(not isinstance(a, dict) or not isinstance(a.get("label"), str) or not a["label"].strip() for a in alts)):
            raise InputError(f"{iid}: alternatives 는 label 이 있는 객체 배열이다(외부 렌즈 원문 — F-115)")
        if "recommended" in i and i["recommended"] is not None:
            labels = [a["label"].strip() for a in alts or []]
            if not isinstance(i["recommended"], str) or i["recommended"].strip() not in labels:
                raise InputError(f"{iid}: recommended 는 alternatives 의 label 중 하나 그대로다 — {i['recommended']!r} ∉ {labels}(재서술하지 않는다 · F-115)")
    for key, need in (("unverifiedPremises", ("claim",)), ("axisCoverage", ("axis", "status")), ("dismissed", ("id", "what", "reason"))):
        if key not in r:
            continue
        if not isinstance(r[key], list) or any(not isinstance(x, dict) or any(not isinstance(x.get(k), str) or not x[k].strip() for k in need)
                                               for x in r[key]):
            raise InputError(f"{key} 는 {' · '.join(need)} 문자열을 가진 객체 배열이다")
    if "costLog" in r and not (isinstance(r["costLog"], str) and r["costLog"].strip()):
        raise InputError("costLog 는 cost-log.json 상대 경로(문자열)다")


def loc(path: str, s: dict) -> str:
    return f"{path}:{s['start']}" if s["start"] == s["end"] else f"{path}:{s['start']}-{s['end']}"


def choose(iid: str, x: dict) -> dict:
    """앵커로 쓸 후보 — 겹치는 hunk 가 여럿이면 Lead 의 pick 없이는 고르지 않는다."""
    c = x["cands"]
    if len(c) > 1 and "pick" not in x["site"]:
        opts = " · ".join(f"{k}={a['start_line']}-{a['line']}" for k, a in enumerate(c))
        raise Reject(f"{iid}: `{x['loc']}` 가 hunk {len(c)}개에 걸친다 — site.pick 으로 후보를 고른다({opts})")
    k = x["site"].get("pick", 0)
    if not 0 <= k < len(c):
        raise Reject(f"{iid}: pick {k} 은 후보 {len(c)}개 밖이다 — `{x['loc']}`")
    return c[k]


def quote(x: dict) -> str:
    q = x["site"].get("quote")
    return f"관련 코드가 이 PR 의 diff 밖이라 인용합니다 — `{x['loc']}`" + (f"\n\n```\n{q.rstrip()}\n```" if q else "")


def units(i: dict, xs: list) -> list:
    """이슈 → 코멘트 단위. pr-comments.md 와 payload 가 이 결과 하나를 쓴다."""
    iid = i["id"]
    text = (i.get("comment") or i["what"] + (f"\n\n{i['suggestion']}" if i.get("suggestion") else "")).strip()
    n = len(xs)
    if n >= 3:
        out = []
        for k, x in enumerate(xs, 1):
            note = x["site"].get("note")
            head = text + (f"\n\n{note}" if note else "") if k == 1 else (note or f"전체 논지는 [1/{n}] `{xs[0]['loc']}` 에 있습니다.")
            refs = " · ".join(f"[{j}/{n}] `{y['loc']}`" for j, y in enumerate(xs, 1) if j != k)
            out.append({"id": iid, "part": f"{k}/{n}", "at": x, "site": k - 1,
                        "anchor": choose(iid, x) if x["cands"] else None, "body": f"[{k}/{n}] {head}\n\n→ {refs}"})
        return out
    at = next((x for x in xs if x["cands"]), xs[0])
    body = text
    for x in xs:
        if x is not at:
            note = f" — {x['site']['note']}" if x["site"].get("note") else ""
            body += "\n\n" + (f"다른 지점: `{x['loc']}`{note}" if x["cands"] else quote(x))
    return [{"id": iid, "part": None, "at": at, "site": xs.index(at),
             "anchor": choose(iid, at) if at["cands"] else None, "body": body}]


def comment(a: dict, body: str) -> dict:
    c = {"path": a["path"]}
    if a["start_line"] != a["line"]:
        c.update(start_line=a["start_line"], start_side=a["side"])   # ⛔ 짝이 빠지면 HTTP 422 로 리뷰 전체가 게시되지 않는다
    c.update(line=a["line"], side=a["side"], body=body)
    return c


def inline(us: list) -> tuple:
    """인라인 코멘트와 미리보기 행 — 앵커 불가 [k/N] 조각은 같은 이슈의 첫 인라인 조각에 인용한다."""
    comments, rows = [], []
    for iid in dict.fromkeys(u["id"] for u in us):
        group = [u for u in us if u["id"] == iid]
        placed = [u for u in group if u["anchor"]]
        carried = [u for u in group if not u["anchor"] and u["part"]]
        for k, u in enumerate(placed):
            body = u["body"]
            if k == 0:   # ⛔ 조각 본문째 옮긴다 — 첫 지점이 앵커 불가면 이슈의 논지(what · suggestion)가 그 조각 본문에만 있다
                body += "".join(f"\n\n{c['body']}\n\n{quote(c['at'])}" for c in carried)
            comments.append(comment(u["anchor"], MARK.format(iid) + "\n" + body))
            a = u["anchor"]
            rows.append({"id": iid, "part": u["part"], "site": u["site"], "path": a["path"],
                         "start_line": a["start_line"], "line": a["line"], "side": a["side"]})
    return comments, rows


def report(r: dict, plans: list, cost: dict | None = None) -> str:
    pr = r.get("pr") or {}
    lines = [f"# PR #{pr['number']} 리뷰" if pr.get("number") is not None else "# 리뷰 보고서", "",
             f"**판정**: {r['verdict'].strip()}", ""]
    if r.get("launchSmoke"):   # launch_smoke.py 요약 줄 — 리포트 · payload body 에 같이 실린다(손으로 리포트를 고치지 않는다 · F-366)
        lines += [r["launchSmoke"].strip(), ""]
    if r.get("matrix"):
        lines += ["## Confidence Matrix", "", r["matrix"].strip(), ""]
    counts = " · ".join(f"{s} {c}" for s in SEVERITIES if (c := sum(p["issue"]["severity"] == s for p in plans)))
    lines += [f"## 이슈 {len(plans)}건" + (f" — {counts}" if counts else ""), ""]
    if not plans:
        lines += ["이슈 없음 — 0건도 유효한 결과다.", ""]
    for p in plans:
        i = p["issue"]
        where = " · ".join(f"`{x['loc']}`" for x in p["sites"])
        found = i.get("foundBy")
        found = " · ".join(found) if isinstance(found, list) else (found or "—")
        conf = i.get("confidence")
        lines += [MARK.format(i["id"]), f"### [{i['severity']}] {i['id']}", "",
                  "| File:line | Origin | Confidence | Found-by |", "|---|---|---|---|",
                  f"| {where} | {i.get('origin') or '—'} | {'—' if conf is None else conf} | {found} |", "",
                  f"**What** — {i['what'].strip()}", ""]
        if i.get("suggestion"):
            lines += [f"**Suggestion** — {i['suggestion'].strip()}", ""]
        lines += alt_lines(i)
    if r.get("severityNote"):
        lines += ["## Severity 보정 근거", "", r["severityNote"].strip(), ""]
    lines += strength_lines(r) + judgment_lines(r) + axes_lines(r, plans) + cost_lines(cost, r.get("costLog"))
    return "\n".join(lines).rstrip() + "\n"


def alt_lines(i: dict) -> list:
    """외부 렌즈의 대안 · 추천을 원문 그대로(F-115). 없으면 빈 목록 — 옛 바이트 그대로."""
    if not i.get("alternatives"):
        return []
    out = ["**대안** (외부 렌즈 원문)", ""]
    for a in i["alternatives"]:
        pc = " · ".join(f"{k} {'; '.join(map(str, a[f]))}" for k, f in (("장점", "pros"), ("단점", "cons")) if a.get(f))
        out.append(f"- {a['label'].strip()} — {str(a.get('description') or '').strip()}" + (f" ({pc})" if pc else ""))
    return out + ([""] + [f"**추천** — {i['recommended'].strip()}"] if i.get("recommended") else []) + [""]


def premise_lines(r: dict) -> list:
    """`## 재지 않은 전제` — 렌즈가 확인하지 않고 기댄 전제(F-448). 참 · 거짓에 따라 위 판정이 바뀐다."""
    ps = r.get("unverifiedPremises") or []
    if not ps:
        return []
    out = [f"## 재지 않은 전제 {len(ps)}건", "", "판정이 기댔지만 코드로 확인하지 않은 전제다 — 참 · 거짓에 따라 위 판정이 바뀔 수 있다.", ""]
    for x in ps:
        tail = [f"못 잰 이유: {_cell(x.get('why'))}" if x.get("why") else "", f"판별: {_cell(x.get('howToMeasure'))}" if x.get("howToMeasure") else "",
                f"기댄 판정: {', '.join(map(str, x['affects']))}" if x.get("affects") else "", f"렌즈: {x['lens']}" if x.get("lens") else ""]
        out.append(f"- {_cell(x['claim'])}" + (" — " + " · ".join(s for s in tail if s) if any(tail) else ""))
    return out + [""]


def coverage_lines(r: dict) -> list:
    """`## 축 판정` — axisCoverage(병합 행 또는 한쪽 행). gap 은 '판정 안 함'(F-514) · 모르는 값도 판정 안 함으로 보인다."""
    rows = r.get("axisCoverage") or []
    if not rows:
        return []
    out = ["## 축 판정", "", "| 축 | 판정 | 근거 |", "|---|---|---|"]
    for row in rows:
        st = row["status"]
        notes = [str(row["note"])] if row.get("note") else []
        for side in ("claude", "gpt"):
            notes += [f"{side} {x.get('status')}: {x.get('note') or '—'}" for x in row.get(side) or [] if isinstance(x, dict)]
        if not notes and ("claude" in row or "gpt" in row):
            notes = ["어느 입력도 이 축을 보지 않았다"]
        out.append(f"| {_cell(row['axis'])} | {STATUS_KO.get(st, f'{st}(모르는 값 — 판정 안 함으로 본다)')} | {_cell(' / '.join(notes))} |")
    return out + [""]


def dismissed_lines(r: dict) -> list:
    """`## Lead 기각 — 의도 확인 후보` — Lead 가 판단으로 뺀 관찰을 사유와 함께 남긴다(F-517)."""
    ds = r.get("dismissed") or []
    if not ds:
        return []
    out = [f"## Lead 기각 — 의도 확인 후보 {len(ds)}건", "",
           "Lead 가 판단으로 뺀 관찰이다 — 근거가 관례 · 추정이면 작성자 의도에 따라 뒤집힐 수 있다.", ""]
    return out + [f"- `{x['id']}` — {_cell(x['what'])} · 기각 사유: {_cell(x['reason'])}" for x in ds] + [""]


def judgment_lines(r: dict) -> list:
    return premise_lines(r) + coverage_lines(r) + dismissed_lines(r)


def axes_lines(r: dict, plans: list) -> list:
    """`## 발견 축 집계` — issue.axis 로 센다(없으면 other). 0건 축도 행을 남긴다(0 이 관측인지 미탐색인지 — tiers.md Tier 1 Deliver).

    큐레이션 리뷰는 항상 · 비큐레이션은 axis 가 하나라도 있을 때만 — 옛 렌더 바이트를 바꾸지 않는다(F-212).
    """
    if "excluded" not in r and not any("axis" in p["issue"] for p in plans):
        return []
    n = {a: 0 for a in AXES}
    for p in plans:
        n[p["issue"].get("axis", "other")] += 1
    return (["## 발견 축 집계", "", "| 축 | 건수 | 비고 |", "|---|---:|---|"]
            + [f"| {a} | {n[a]} | {'어디에도 안 맞은 것 · axis 없음 포함' if a == 'other' else ''} |" for a in AXES] + [""])


def cost_lines(cost: dict | None, rel: str | None) -> list:
    """`## 실측 비용` — review.costLog 가 가리키는 cost-log.json(tiers.md § 비용 로깅 형식 2)에서 그린다(F-212)."""
    if cost is None:
        return []
    tier = cost.get("tier") if isinstance(cost.get("tier"), dict) else {}
    tok = cost.get("tokens") if isinstance(cost.get("tokens"), dict) else {}
    iss = cost.get("issues") if isinstance(cost.get("issues"), dict) else {}
    ms = cost.get("duration_ms")
    dur = f"{int(ms) // 60000}분 {int(ms) % 60000 // 1000}초" if isinstance(ms, (int, float)) else "—"
    ph = cost.get("phases_ms") if isinstance(cost.get("phases_ms"), dict) else {}
    phases = " / ".join(f"{k} {int(v) // 1000}초" for k, v in ph.items() if isinstance(v, (int, float)))
    return ["## 실측 비용", "",
            f"- Tier: {tier.get('selected', '—')}",
            f"- Total tokens: {tok.get('total', '—')} (method {tok.get('method', '—')})",
            f"- Duration: {dur}" + (f"  ← 구간 {phases}" if phases else "  ← ⚠️ 구간 분해 없음(phases_ms)"),
            "- 이슈 발견 수: " + " / ".join(f"{s} {iss.get(s, 0)}" for s in SEVERITIES),
            f"- cost-log.json: {rel}", ""]


def strength_lines(r: dict) -> list:
    """강점 블록 — strengthGaps 가 있으면 그 강점이 못 막는 시나리오를 바로 아래 적는다(F-117 · F-517). 없으면 종전 바이트 그대로."""
    if not r.get("strengths"):
        return []
    gaps = {g["claim"].strip(): str(g.get("uncovered") or "").strip()
            for g in r.get("strengthGaps") or [] if isinstance(g, dict) and isinstance(g.get("claim"), str)}
    out = ["## 긍정적 측면", ""]
    for s in r["strengths"]:
        out.append(f"- {s}")
        if gaps.get(str(s).strip()):
            out.append(f"  - 못 막는 시나리오 — {gaps[str(s).strip()]}")
    return out + [""]


CURATED = (("bug",), "① 이번 PR 버그"), (("structure", "quality"), "② 구조·품질 제안 (non-blocking)"), (("intent-question",), "③ 의도 확인 질문")


def _cell(v) -> str:
    return str(v or "—").replace("|", "\\|").replace("\n", " ").strip()


def curated_report(r: dict, plans: list, info: dict, cost: dict | None = None) -> str:
    pr = r.get("pr") or {}
    lines = [f"# PR #{pr['number']} 리뷰" if pr.get("number") is not None else "# 리뷰 보고서", "",
             f"**판정**: {r['verdict'].strip()}", ""]
    if r.get("launchSmoke"):
        lines += [r["launchSmoke"].strip(), ""]
    if r.get("matrix"):
        lines += ["## Confidence Matrix", "", r["matrix"].strip(), ""]
    groups = [[p for p in plans if p["issue"].get("kind") in kinds] for kinds, _ in CURATED]
    lines += [f"## 코멘트 {len(plans)}건 — " + " · ".join(f"{t.split()[0]} {len(g)}" for (_, t), g in zip(CURATED, groups)), ""]
    if not plans:
        lines += ["코멘트할 것 없음 — 후보는 모두 아래 표로 처분했다.", ""]
    for (_, title), g in zip(CURATED, groups):
        if not g:
            continue
        lines += [f"### {title}", ""]
        for p in g:
            i = p["issue"]
            where = " · ".join(f"`{x['loc']}`" for x in p["sites"])
            found = i.get("foundBy")
            found = " · ".join(found) if isinstance(found, list) else (found or "—")
            conf = i.get("confidence")
            lines += [MARK.format(i["id"]), f"#### [{i['severity']}] {i['id']}", "",
                      "| File:line | Origin | Confidence | Found-by |", "|---|---|---|---|",
                      f"| {where} | {i.get('origin') or '—'} | {'—' if conf is None else conf} | {found} |", "",
                      f"**What** — {i['what'].strip()}", ""]
            if i.get("suggestion"):
                lines += [f"**Suggestion** — {i['suggestion'].strip()}", ""]
            lines += alt_lines(i)
            rp = i.get("repro") if isinstance(i.get("repro"), dict) else None
            if rp:
                lines += [f"**재현** — {rp.get('status')} · {str(rp.get('how') or '').strip()}", ""]
            if i.get("measure"):
                lines += [f"**측정** — {str(i['measure']).strip()}", ""]
            if i.get("refute"):
                lines += [f"**반박 시도** — {str(i['refute']).strip()}", ""]
    ex = [x for x in r.get("excluded") or [] if isinstance(x, dict)]
    e4 = [x for x in ex if x.get("code") == "E4"]
    if e4:
        lines += ["## ④ 참고 — 원래 있던 문제 (E4 · 이번 PR 과 무관 · 별 티켓 제안)", ""]
        lines += [f"- `{x['id']}` — {_cell(x.get('what'))} · {_cell(x.get('reason'))}" for x in e4] + [""]
    lines += [f"## 제외 후보 {len(ex)}건", "", "| id | 한 줄 | 코드 | 근거 |", "|---|---|---|---|"]
    lines += [f"| `{x['id']}` | {_cell(x.get('what'))} | {x.get('code')} | {_cell(x.get('reason'))}"
              + (f" (+{len(x['covers'])} 묶음)" if x.get("covers") else "") + " |" for x in ex]
    lines += ["", "## 기존 스레드 대조", "", info.get("thread_line") or "—", ""]
    if info.get("symbol_check"):   # 제안 코드 식별자를 대조하지 못했다 — 검증 통과로 읽히지 않게 리포트에 남긴다(F-063 리뷰)
        lines += ["## 제안 식별자 대조", "", info["symbol_check"], ""]
    replies = [x for x in ex if x.get("code") == "E5" and str(x.get("reply") or "").strip()]
    if replies:   # ⛔ 본문은 넣지 않는다 — 리포트가 payload.body 로 게시되면 답글 초안이 새 리뷰에 실린다(초안은 pr-comments.md 끝 · 로컬)
        lines += [f"답글 초안 {len(replies)}건 — pr-comments.md 끝(게시 payload 밖 · 기존 스레드에 따로 단다)", ""]
    if r.get("severityNote"):
        lines += ["## Severity 보정 근거", "", r["severityNote"].strip(), ""]
    lines += strength_lines(r) + judgment_lines(r) + axes_lines(r, plans) + cost_lines(cost, r.get("costLog"))
    return "\n".join(lines).rstrip() + "\n"


def check_posted_lines(us: list, texts: dict) -> None:
    """게시 대상 인라인 코멘트 전건의 줄 대조(Gate 4.5 · F-069) — site.expect 가 앵커 구간의 diff 줄 중 하나에 있어야 한다."""
    for u in us:
        a = u["anchor"]
        if not a:
            continue
        s = u["at"]["site"]
        where = f"{u['id']}{' [' + u['part'] + ']' if u['part'] else ''} `{u['at']['loc']}`"
        want = s.get("expect")
        if not want:
            raise Reject(f"{where}: 게시 코멘트에 expect(그 줄에 있어야 할 코드 조각)가 없다 — Gate 4.5 는 severity 와 무관하게 게시 전건이다")
        side = texts.get(a["path"], {}).get("new" if a["side"] == "RIGHT" else "old", {})
        got = [side.get(n, "") for n in range(a["start_line"], a["line"] + 1)]
        if not any(want.strip() in g for g in got):
            raise Reject(f"{where}: expect {want.strip()[:40]!r} 가 앵커 줄 {a['start_line']}-{a['line']} 에 없다 — 지금 그 줄: "
                         f"{(got[0].strip() if got else '')[:60]!r} (줄 번호를 git show 로 다시 잰다)")


def pr_comments(r: dict, us: list) -> str:
    pr = r.get("pr") or {}
    lines = [f"# PR #{pr['number']} 코멘트 (복사용)" if pr.get("number") is not None else "# 리뷰 코멘트 (복사용)", ""]
    seen = set()
    for u in us:
        if u["id"] not in seen:
            seen.add(u["id"])
            lines.append(MARK.format(u["id"]))
        part = f" [{u['part']}]" if u["part"] else ""
        body = u["body"] if u["anchor"] else u["body"] + "\n\n" + quote(u["at"])
        lines += [f"## {u['id']}{part} · `{u['at']['loc']}`", "", body, ""]
    replies = [x for x in r.get("excluded") or [] if isinstance(x, dict) and x.get("code") == "E5" and str(x.get("reply") or "").strip()]
    if replies:   # 기존 스레드 답글 — 게시 payload 밖이다(새 코멘트가 아니라 그 스레드에 단다)
        lines += ["## 답글 초안 (기존 스레드 — payload 밖)", ""]
        lines += [f"- 스레드 {x.get('duplicateOf')}: {str(x['reply']).strip()}" for x in replies] + [""]
    return "\n".join(lines).rstrip() + "\n"


def render(review, diff_text: str, curation: dict | None = None, cost: dict | None = None) -> dict:
    validate(review)
    if not re.search(r"^diff --git ", diff_text, re.M):
        raise InputError("diff 에 `diff --git` 헤더가 없다 — 파일 경계를 가를 수 없어 모든 지점이 앵커 불가로 조용히 떨어진다(git diff 출력만 받는다)")
    da = anchors_module()
    files = da.parse_hunks(diff_text)
    plans = []
    for i in review["issues"]:
        xs = []
        for s in i["sites"]:
            res = da.compute(files, [{"path": s["path"], "start": s["start"], "end": s["end"], "side": s.get("side", "RIGHT")}])
            cands, na = res["anchorable"], (res["non_anchorable"] or [None])[0]
            path = cands[0]["path"] if cands else na["path"]
            xs.append({"site": s, "cands": cands, "na": na, "path": path, "loc": loc(path, s)})
        plans.append({"issue": i, "sites": xs})
    plans.sort(key=lambda p: SEVERITIES.index(p["issue"]["severity"]))   # 안정 정렬 — 같은 severity 는 JSON 순서
    us = [u for p in plans for u in units(p["issue"], p["sites"])]
    rep = curated_report(review, plans, curation or {}, cost) if "excluded" in review else report(review, plans, cost)
    comments, rows = inline(us)
    pr = review.get("pr") or {}
    if pr.get("headSha"):
        check_posted_lines(us, da.line_texts(diff_text))
    event = review.get("event", "COMMENT")
    payload = None
    if pr.get("headSha"):
        if len(rep) > BODY_LIMIT:
            raise Reject(f"body {len(rep):,}자 > {BODY_LIMIT:,}자 — Matrix 만 남기고 이슈 상세를 인라인에 맡겨야 한다(앵커 모듈 §4)")
        payload = {"commit_id": pr["headSha"], "event": event, "body": rep, "comments": comments}
    na = [{"id": p["issue"]["id"], "loc": x["loc"], "side": x["site"].get("side", "RIGHT"), "reason": x["na"]["reason"]}
          for p in plans for x in p["sites"] if not x["cands"]]
    picked = [{"id": u["id"], "loc": u["at"]["loc"], "pick": u["at"]["site"].get("pick", 0),
               "candidates": [[a["start_line"], a["line"]] for a in u["at"]["cands"]]}
              for u in us if u["anchor"] and len(u["at"]["cands"]) > 1]
    reasons = []
    if event != "COMMENT":
        reasons.append(f"(a) event {event} — 머지를 막거나 승인하는 행위다")
    if na:
        reasons.append(f"(b) 앵커 불가 지점 {len(na)}곳 — 본문 인용이나 리포트로만 남는다")
    if picked:
        reasons.append(f"(c) 겹치는 hunk 에서 Lead 가 구간을 골랐다 {len(picked)}곳")
    by_file = {}
    for c in comments:
        by_file[c["path"]] = by_file.get(c["path"], 0) + 1
    placed = {row["id"] for row in rows}
    preview = {"event": event, "issues": len(plans), "inline": rows, "byFile": by_file, "nonAnchorable": na,
               "reportOnly": [p["issue"]["id"] for p in plans if p["issue"]["id"] not in placed],
               "picked": picked, "confirmRequired": bool(reasons), "reasons": reasons,
               "payload": "payload.json" if payload else None}
    return {"review-report.md": rep, "pr-comments.md": pr_comments(review, us), "payload": payload, "preview": preview}


def run_render(a) -> int:
    d = Path(a.out_dir)

    def fail(code: int, msg: str) -> int:
        for f in OUTPUTS:
            (d / f).unlink(missing_ok=True)   # ⛔ 실패한 렌더 뒤에 이전 실행의 산출물이 남으면 지금 리뷰로 오인해 게시한다
        print(msg, file=sys.stderr)
        return code

    try:
        review = json.loads(Path(a.review).read_text(encoding="utf-8"))
        diff_text = Path(a.diff).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as e:
        return fail(UNRUN, f"UNRUN: 입력을 읽지 못했다 — {e}")
    curated = isinstance(review, dict) and "excluded" in review
    if getattr(a, "require_curation", False) and not curated:
        return fail(REJECT, "REJECT: --require-curation — excluded 키가 없다(Curate 를 건너뛴 리뷰다 · --no-curate 면 이 플래그 없이 렌더한다)")
    curation = None
    if curated:
        try:
            validate(review)   # 공통 계약 먼저 — 깨진 site 가 큐레이션 검사 안에서 예외로 터지지 않게
        except InputError as e:
            return fail(UNRUN, f"UNRUN: {e}")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import check_comment_worthy as ccw   # 렌더 전에 코멘트 가치 계약 — 위반 · 판정 불가면 파일을 쓰지 않는다
        try:
            code, bad, warn, curation = ccw.check_review(review, Path(a.review).resolve().parent)
        except Exception as e:   # noqa: BLE001 — 예외도 fail() 로 — 이전 실행의 payload · 리포트가 지금 리뷰로 남으면 게시된다
            return fail(UNRUN, f"UNRUN: 코멘트 가치 검사 예외 — {type(e).__name__}: {e}")
        for w in warn:
            print(f"WARN {w}", file=sys.stderr)
        if code:
            return fail(REJECT if code == ccw.VIOLATION else UNRUN,
                        ("REJECT" if code == ccw.VIOLATION else "UNRUN") + ": 코멘트 가치 검사 — " + " · ".join(bad[:5]))
    want = getattr(a, "head_sha", None)
    if want is not None:          # ⛔ 넘긴 빈 값(`"$(gh pr view …)"` 조회 실패)은 생략이 아니다 — 대조를 건너뛰면 아무 head 에나 게시된다
        want = want.strip()
        sides = [(k, v) for k, v in ((("pr.headSha", (review.get("pr") or {}).get("headSha")),
                                      ("target.sha", (review.get("target") or {}).get("sha"))) if isinstance(review, dict) else ())
                 if isinstance(v, str) and v.strip()]
        # 채워진 칸 전부와 맞아야 한다 — Curate 는 target.sha 로 근거를 대조했다. pr.headSha 만 새 head 로 바뀌면 옛 근거가 새 head 에 게시된다
        off = [f"{k} {v[:12]}" for k, v in sides if min(len(want), len(v)) < 7 or want[:min(len(want), len(v))] != v[:min(len(want), len(v))]]
        if not want:
            return fail(REJECT, "REJECT: --head-sha 가 비었다 — 지금 head 조회가 실패했다(빈 값은 대조 생략이 아니다 · F-068)")
        if not sides or off:
            return fail(REJECT, f"REJECT: 게시 직전 head {want[:12]} ≠ 리뷰 대상 {' · '.join(off) or '(review 에 pr.headSha · target.sha 없음)'} — "
                                "리뷰 중 대상이 바뀌었다(force-push 등). `git log --oneline 대상..지금` 으로 차이를 먼저 보고 다시 리뷰한다(F-068)")
    cost = None
    if isinstance(review, dict) and isinstance(review.get("costLog"), str):
        cp = Path(a.review).resolve().parent / review["costLog"]
        try:
            cost = json.loads(cp.read_text(encoding="utf-8"))
            if not isinstance(cost, dict):
                raise ValueError("객체가 아니다")
        except (OSError, ValueError) as e:
            return fail(UNRUN, f"UNRUN: costLog {cp} 를 읽지 못했다 — {e} · `## 실측 비용` 절을 그릴 수 없다(⛔ 통과 아님 · F-212)")
    try:
        out = render(review, diff_text, curation, cost)
    except InputError as e:
        return fail(UNRUN, f"UNRUN: {e}")
    except Reject as e:
        return fail(REJECT, f"REJECT: {e}")
    if getattr(a, "lang", None) == "ko":
        ratio = hangul_ratio(review)
        if ratio < LANG_MIN:
            return fail(REJECT, f"REJECT: --lang ko 인데 리포트 산문의 한글 비율 {ratio:.0%} < {LANG_MIN:.0%} — 사용자 대면 산출물은 프로젝트 언어로 쓴다"
                                "(에이전트 지시 언어와 별개 축이다 · F-020)")
    try:
        synth = synth_update(d / "synthesized-issues.json", review)
    except (OSError, ValueError) as e:
        return fail(UNRUN, f"UNRUN: synthesized-issues.json 을 읽지 못했다 — {e} (파생 산출물을 맞출 수 없다 · F-201)")
    d.mkdir(parents=True, exist_ok=True)
    (d / "review-report.md").write_text(out["review-report.md"], encoding="utf-8")
    (d / "pr-comments.md").write_text(out["pr-comments.md"], encoding="utf-8")
    (d / "render-preview.json").write_text(json.dumps(out["preview"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if out["payload"]:
        (d / "payload.json").write_text(json.dumps(out["payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        (d / "payload.json").unlink(missing_ok=True)   # ⛔ 이전 실행의 payload 가 남아 게시되면 지금 리뷰와 다른 내용이 올라간다
    if synth is not None:
        _atomic(d / "synthesized-issues.json", json.dumps(synth, ensure_ascii=False, indent=2) + "\n")
    if (d / "review-index.md").is_file():   # Lead 가 Synthesize CHECKPOINT 에서 만든 인덱스만 고친다 — 없으면 만들지 않는다(산출물 집합 그대로)
        _atomic(d / "review-index.md", index_text(d / "review-index.md", review, out["preview"]))
    p = out["preview"]
    print(f"렌더 — 이슈 {p['issues']}건 · 인라인 {len(p['inline'])}건(파일 {len(p['byFile'])}) · 리포트만 {len(p['reportOnly'])}건 · "
          f"event {p['event']} · payload {'있음' if out['payload'] else '없음(pr.headSha 없음)'}")
    print("확인 필요 — " + " · ".join(p["reasons"]) if p["confirmRequired"] else "확인 게이트 해당 없음")
    print(f"→ {d}/  " + " · ".join(f for f in OUTPUTS if (d / f).exists()))
    return OK


CODE_SPAN = re.compile(r"`[^`]*`|https?://\S+")


def hangul_ratio(r: dict) -> float:
    """Lead 가 쓴 산문 칸의 한글 비율 — 한글 / (한글 + 라틴 글자). 백틱 코드 · URL 은 뺀다. 산문이 없으면 1.0(판정할 것 없음)."""
    parts = [r.get("verdict"), r.get("severityNote")] + list(r.get("strengths") or [])
    for i in r.get("issues") or []:
        parts += [i.get("what"), i.get("suggestion"), i.get("comment")]
    text = CODE_SPAN.sub(" ", " ".join(p for p in parts if isinstance(p, str)))
    ko = sum("\uac00" <= ch <= "\ud7a3" for ch in text)
    en = sum(ch.isascii() and ch.isalpha() for ch in text)
    return 1.0 if ko + en == 0 else ko / (ko + en)


SYN_FINAL = ("severity_final", "finalSeverity", "effectiveSeverity")


def synth_update(path: Path, r: dict):
    """synthesized-issues.json 을 렌더한 판정에 맞춘 새 객체(없으면 None) — 같은 id · covers 묶음 · excluded 를 본다(F-201)."""
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("issues") if isinstance(data, dict) and isinstance(data.get("issues"), list) else \
        data.get("candidates") if isinstance(data, dict) and isinstance(data.get("candidates"), list) else None
    if items is None:
        raise ValueError("issues[] · candidates[] 가 없다")
    want = {}
    for i in r.get("issues") or []:
        disp = "question" if i.get("kind") == "intent-question" else "include"
        for k in [i["id"]] + [c for c in i.get("covers") or [] if isinstance(c, str)]:
            want[k] = (disp, i["severity"], None)
    for x in r.get("excluded") or []:          # 묶음 카드는 covers 의 후보까지 같은 처분 — 리포트가 묶음 전체를 뺀다
        if isinstance(x, dict) and isinstance(x.get("id"), str):
            for k in [x["id"]] + [c for c in x.get("covers") or [] if isinstance(c, str)]:
                want.setdefault(k, (f"exclude:{x.get('code')}", None, x.get("reason")))
    for x in r.get("dismissed") or []:   # Lead 기각 — 사유와 함께 남긴다(F-517)
        want.setdefault(x["id"], ("exclude", None, x["reason"]))
    for it in items:
        if not isinstance(it, dict) or it.get("id") not in want:
            continue
        disp, sev, why = want[it["id"]]
        if it.get("disposition") not in (None, disp):
            it.setdefault("disposition_initial", it["disposition"])
        it["disposition"] = disp
        if why:
            it["disposition_reason"] = why
        if sev:
            key = next((k for k in SYN_FINAL if k in it), None)
            if key is None and any(k in it for k in ("severity_raw", "rawSeverity")):
                key = "severity"     # 원본 칸을 따로 적은 Lead 모양에서는 `severity` 가 최종 칸이다(check_synthesized.normalize 와 같은 규칙)
            now = it.get(key) if key else it.get("severity")
            if now != sev:
                if now is not None:
                    it.setdefault("severity_initial", now)
                it[key or "severity_final"] = sev
    return data


def index_text(path: Path, r: dict, preview: dict) -> str:
    """review-index.md — 렌더 블록만 새로 쓰고 Lead 가 쓴 나머지(Phase · Artifacts)는 그대로 둔다(F-201 · F-068 대상 head)."""
    pr = r.get("pr") or {}
    head = pr.get("headSha") or (r.get("target") or {}).get("sha") or "—"
    rows = [f"- {i['id']} [{i['severity']}]" for i in sorted(r["issues"], key=lambda i: SEVERITIES.index(i["severity"]))]
    block = "\n".join([INDEX_BEGIN, "## 렌더 결과 (render_review.py — 다시 렌더하면 이 블록을 덮는다)", "",
                       f"- 대상 head: {head}", f"- 판정: {r['verdict'].strip()}",
                       f"- 이슈 {len(rows)}건 · 제외 {len(r.get('excluded') or [])}건 · 인라인 {len(preview['inline'])}건",
                       *rows, INDEX_END])
    old = path.read_text(encoding="utf-8")
    b, e = old.find(INDEX_BEGIN), old.find(INDEX_END)
    if b >= 0 and e > b:
        return old[:b] + block + old[e + len(INDEX_END):]
    return old.rstrip("\n") + "\n\n" + block + "\n"


def _atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ── self-test ──────────────────────────────────────────────────────────────
SELF_DIFF = """diff --git a/src/a.swift b/src/a.swift
--- a/src/a.swift
+++ b/src/a.swift
@@ -10,3 +10,5 @@
 l10
+l11
+l12
 l13
 l14
@@ -30,2 +32,3 @@
 l32
+l33
 l34
diff --git a/src/b.swift b/src/b.swift
--- a/src/b.swift
+++ b/src/b.swift
@@ -1,2 +1,3 @@
 k1
+k2
 k3
"""

# --example 이 내는 최소 review JSON — 지점은 SELF_DIFF 의 앵커 가능한 줄이라 self-test 가 이 객체를 그대로 렌더한다
EXAMPLE = {
    "verdict": "코멘트 수준 — 머지를 막을 결함은 없다",
    "event": "COMMENT",
    "pr": {"number": 7, "headSha": "abc123"},
    "strengths": ["변경 범위가 요구사항과 맞는다"],
    "issues": [
        {"id": "A1", "severity": "major", "origin": "regression", "confidence": 90, "foundBy": ["arch", "gpt"],
         "what": "무엇이 왜 문제인지(WHY 포함)", "suggestion": "어떻게 고칠지",
         "comment": "PR 코멘트 톤 본문 — 없으면 what + suggestion 을 쓴다",
         "sites": [{"path": "src/a.swift", "start": 11, "end": 12, "expect": "l11"}]},
        {"id": "Q1", "severity": "minor", "what": "한 줄 지적", "sites": [{"path": "src/b.swift", "start": 2, "end": 2, "note": "조각 설명", "expect": "k2"}]},
    ],
}


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" — {detail}"))

    def site(path, start, end, **kw):
        kw.setdefault("expect", "k" if path.endswith("b.swift") else "l")   # F-069 — 셀이 따로 재지 않는 자리는 줄 접두 글자
        return dict(path=path, start=start, end=end, **kw)

    def review(issues, **kw):
        return {"pr": {"number": 7, "headSha": "abc123"}, "verdict": "코멘트 수준", "strengths": ["s1"], "issues": issues, **kw}

    base = [{"id": "A1", "severity": "major", "origin": "regression", "confidence": 90, "foundBy": ["arch", "gpt"],
             "what": "w1", "suggestion": "g1", "comment": "c1", "sites": [site("src/a.swift", 11, 12)]},
            {"id": "Q1", "severity": "minor", "what": "w2", "sites": [site("a.swift", 33, 33)]},
            {"id": "S1", "severity": "suggestion", "what": "w3", "sites": [site("src/a.swift", 20, 25, quote="let x = 1")]}]

    def ids_of(out):
        rep = set(MARK_RE.findall(out["review-report.md"]))
        com = set(MARK_RE.findall(out["pr-comments.md"]))
        pay = {m for c in out["payload"]["comments"] for m in MARK_RE.findall(c["body"])} | set(out["preview"]["reportOnly"])
        return rep, com, pay

    def by_id(out, iid):
        return [c for c in out["payload"]["comments"] if MARK.format(iid) in c["body"]]

    tmp = Path(tempfile.mkdtemp(prefix="render-review-"))
    diff = tmp / "d.patch"
    diff.write_text(SELF_DIFF, encoding="utf-8")

    def cli_anchor(s):
        t = [{"path": s["path"], "start": s["start"], "end": s["end"], "side": s.get("side", "RIGHT")}]
        r = subprocess.run([sys.executable, str(ANCHORS), "--diff", str(diff), "--targets", json.dumps(t)], capture_output=True, text=True)
        return json.loads(r.stdout)["anchorable"] if r.returncode == 0 else None

    def main_exit(obj, out_dir, raw=None):
        f = tmp / f"in-{out_dir}.json"
        f.write_text(raw if raw is not None else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--review", str(f), "--diff", str(diff), "--out-dir", str(tmp / out_dir)],
                           capture_output=True, text=True)
        return r.returncode, sorted(p.name for p in (tmp / out_dir).glob("*")) if (tmp / out_dir).exists() else []

    tests = []

    def t_ids():
        rep, com, pay = ids_of(render(review(base), SELF_DIFF))
        case("id-sets — 리포트 · 코멘트 · payload(인라인 ∪ reportOnly) 의 이슈 id 집합이 같다",
             rep == com == pay == {"A1", "Q1", "S1"}, (rep, com, pay))

    def t_anchor():
        out = render(review(base), SELF_DIFF)
        got = [(c["path"], c.get("start_line", c["line"]), c["line"], c["side"]) for c in out["payload"]["comments"]]
        want = []
        for row in out["preview"]["inline"]:
            s = next(i for i in base if i["id"] == row["id"])["sites"][row["site"]]
            a = cli_anchor(s)[s.get("pick", 0)]
            want.append((a["path"], a["start_line"], a["line"], a["side"]))
        case("anchors — 인라인 앵커가 diff_anchors.py CLI 결과와 같다(basename 은 diff 경로로 풀린다)",
             got == want and got[1][0] == "src/a.swift", (got, want))

    def t_lines():
        out = render(review(base), SELF_DIFF)
        a1, q1 = by_id(out, "A1")[0], by_id(out, "Q1")[0]
        case("multi-line — 다중 라인은 start_line · start_side · line · side 넷",
             (a1.get("start_line"), a1.get("start_side"), a1["line"], a1["side"]) == (11, "RIGHT", 12, "RIGHT"), a1)
        case("single-line — 단일 줄은 line · side 만(start_* 생략)", "start_line" not in q1 and "start_side" not in q1 and q1["line"] == 33, q1)

    def t_body():
        out = render(review(base), SELF_DIFF)
        case("body — top-level body 는 review-report.md 전문", out["payload"]["body"] == out["review-report.md"])
        sm = "launch smoke — SMOKE PASS · exit 0 · expect 일치 · HEAD abc1234"
        out = render({**review(base), "launchSmoke": sm}, SELF_DIFF)
        rl = out["review-report.md"].splitlines()
        case("launch-smoke — launchSmoke 줄이 판정 바로 뒤 · payload body 에도 같이",
             sm in rl and rl.index(sm) == next(k for k, x in enumerate(rl) if x.startswith("**판정**")) + 2
             and out["payload"]["body"] == out["review-report.md"])
        try:
            render({**review(base), "launchSmoke": 1}, SELF_DIFF)
            case("launch-smoke-type — 문자열이 아니면 거부", False)
        except InputError:
            case("launch-smoke-type — 문자열이 아니면 거부", True)

    def t_na():
        out = render(review(base), SELF_DIFF)
        p = out["preview"]
        case("non-anchorable — diff 밖 지점은 인라인 없이 리포트에만 · 코멘트 문서엔 인용 · 게이트 (b)",
             p["reportOnly"] == ["S1"] and not by_id(out, "S1") and any(r.startswith("(b)") for r in p["reasons"])
             and "let x = 1" in out["pr-comments.md"] and "src/a.swift:20-25" in out["review-report.md"], p)

    def t_pick():
        over = [{"id": "C1", "severity": "major", "what": "w", "sites": [site("src/a.swift", 12, 33)]}]
        try:
            render(review(over), SELF_DIFF)
            refused = False
        except Reject:
            refused = True
        over[0]["sites"][0]["pick"] = 1
        out = render(review(over), SELF_DIFF)
        c = by_id(out, "C1")[0]
        case("overlap-pick — 겹치는 hunk 가 여럿이면 pick 없이 거부 · pick 이 있으면 그 구간과 게이트 (c)",
             refused and (c.get("start_line"), c["line"]) == (32, 33) and any(r.startswith("(c)") for r in out["preview"]["reasons"]),
             (refused, c))
        over[0]["sites"][0]["pick"] = 2
        try:
            render(review(over), SELF_DIFF)
            ok = False
        except Reject:
            ok = True
        case("pick-range — 후보 밖 pick 은 거부", ok)

    def t_event():
        out = render(review(base, event="REQUEST_CHANGES"), SELF_DIFF)
        case("event — COMMENT 밖이면 게이트 (a)", any(r.startswith("(a)") for r in out["preview"]["reasons"])
             and out["payload"]["event"] == "REQUEST_CHANGES")

    def t_split():
        three = {"id": "M1", "severity": "major", "what": "w", "sites": [site("src/a.swift", 11, 12), site("src/a.swift", 33, 33), site("src/b.swift", 2, 2)]}
        two = {"id": "T1", "severity": "minor", "what": "w", "sites": [site("src/a.swift", 11, 12), site("src/b.swift", 2, 2)]}
        out = render(review([three, two]), SELF_DIFF)
        m, t = by_id(out, "M1"), by_id(out, "T1")
        heads = [c["body"].split("\n", 1)[1].split(" ", 1)[0] for c in m]
        case("split — 지점 3개 이상은 [k/N] 코멘트 N개 · 2개는 한 코멘트가 다른 지점을 가리킨다",
             heads == ["[1/3]", "[2/3]", "[3/3]"] and len(t) == 1 and "다른 지점: `src/b.swift:2`" in t[0]["body"], (heads, t))

    def t_carry():
        three = {"id": "M2", "severity": "major", "what": "w", "sites": [site("src/a.swift", 11, 12), site("src/a.swift", 20, 25), site("src/b.swift", 2, 2)]}
        out = render(review([three]), SELF_DIFF)
        m = by_id(out, "M2")
        case("carry — 앵커 불가 조각은 같은 이슈 첫 인라인 조각에 인용한다",
             len(m) == 2 and "[2/3] 전체 논지는" in m[0]["body"] and "관련 코드가 이 PR 의 diff 밖이라" in m[0]["body"]
             and "src/a.swift:20-25" in m[0]["body"], m)
        first_out = {"id": "M3", "severity": "major", "what": "w", "comment": "논지 본문",
                     "sites": [site("src/a.swift", 20, 25), site("src/a.swift", 11, 12), site("src/b.swift", 2, 2)]}
        m = by_id(render(review([first_out]), SELF_DIFF), "M3")
        case("carry-first — 첫 지점이 앵커 불가여도 논지 본문이 인라인 코멘트에 남는다(인용만 옮기면 본문이 사라진다)",
             len(m) == 2 and "논지 본문" in m[0]["body"], m)

    def t_nodiff():
        try:
            render(review(base), "변경 요약만 있고 diff 헤더가 없다\n@@ -1 +1 @@\n-a\n+b\n")
            refused = False
        except InputError:
            refused = True
        case("no-diff-header — `diff --git` 헤더가 없으면 입력 불가(전부 앵커 불가로 떨어뜨려 exit 0 하지 않는다)", refused)

    def t_empty():
        try:
            render({}, SELF_DIFF)
            refused = False
        except InputError:
            refused = True
        case("empty — 빈 JSON 은 입력 불가", refused)

    def t_nopr():
        r = review(base)
        del r["pr"]
        out = render(r, SELF_DIFF)
        case("no-pr — pr.headSha 가 없으면 payload 를 만들지 않는다(리포트 · 코멘트는 만든다)",
             out["payload"] is None and out["preview"]["payload"] is None and "### [major] A1" in out["review-report.md"])

    def t_det():
        a = render(review(base), SELF_DIFF)
        b = render(json.loads(json.dumps(review(base))), SELF_DIFF)
        case("deterministic — 같은 입력은 같은 산출물", a == b)

    def t_limit():
        big = [dict(base[0], what="x" * (BODY_LIMIT + 1))]
        try:
            render(review(big), SELF_DIFF)
            ok = False
        except Reject:
            ok = True
        case("body-limit — body 가 65,536자를 넘으면 거부", ok)

    def t_cli():
        rc_ok, files_ok = main_exit(review(base), "ok")
        rc_empty, files_empty = main_exit(None, "empty", raw="{}")
        rc_blank, files_blank = main_exit(None, "blank", raw="")
        over = [{"id": "C1", "severity": "major", "what": "w", "sites": [site("src/a.swift", 12, 33)]}]
        rc_rej, files_rej = main_exit(review(over), "rej")
        case("cli-exit — 정상 0 · 거부 1 · 빈 JSON 2 · 빈 파일 2 · 실패하면 파일 0개",
             (rc_ok, rc_rej, rc_empty, rc_blank) == (0, 1, 2, 2) and files_ok == sorted(OUTPUTS)
             and files_rej == files_empty == files_blank == [], (rc_ok, rc_rej, rc_empty, rc_blank, files_ok))
        r = review(base)
        del r["pr"]
        f = tmp / "in-ok.json"
        f.write_text(json.dumps(r), encoding="utf-8")
        subprocess.run([sys.executable, __file__, "--review", str(f), "--diff", str(diff), "--out-dir", str(tmp / "ok")], capture_output=True)
        case("stale-payload — headSha 없는 재실행은 이전 payload.json 을 지운다", not (tmp / "ok" / "payload.json").exists())
        rc1, files1 = main_exit(review(base), "same")
        rc2, files2 = main_exit(review(over), "same")
        case("stale-on-failure — 같은 out-dir 에서 실패하면 이전 실행의 산출물 넷을 지운다",
             (rc1, rc2) == (0, 1) and files1 == sorted(OUTPUTS) and files2 == [], (rc1, rc2, files1, files2))

    def t_example():
        r = subprocess.run([sys.executable, __file__, "--example"], capture_output=True, text=True)
        cli = json.loads(r.stdout) if r.returncode == 0 else None
        rep, com, pay = ids_of(render(EXAMPLE, SELF_DIFF))   # render 가 validate 를 먼저 부른다
        want = {i["id"] for i in EXAMPLE["issues"]}
        case("example-roundtrip — --example 출력이 예시 객체와 같고 검증 · 렌더를 통과한다(세 산출물의 이슈 id 일치)",
             cli == EXAMPLE and rep == com == pay == want, (r.returncode, rep, com, pay))

    def t_curated():
        ex = tmp / "curated"
        subprocess.run([sys.executable, __file__, "--example-curated-dir", str(ex)], capture_output=True, text=True)
        args = ["--review", str(ex / "review.json"), "--diff", str(diff), "--require-curation"]
        r = subprocess.run([sys.executable, __file__, *args, "--out-dir", str(tmp / "cur-ok")], capture_output=True, text=True)
        rep = (tmp / "cur-ok" / "review-report.md").read_text(encoding="utf-8") if r.returncode == 0 else ""
        case("curated-report — 예시 묶음이 계약을 통과하고 ① · ③ · 제외 표 · 스레드 대조 줄을 그린다(옛 report 경로는 그대로)",
             r.returncode == 0 and "### ① 이번 PR 버그" in rep and "### ③ 의도 확인 질문" in rep and "## 제외 후보 2건" in rep
             and "## ④ 참고" in rep and "## 기존 스레드 대조" in rep, (r.returncode, r.stderr[-200:]))
        bad = json.loads((ex / "review.json").read_text(encoding="utf-8"))
        bad["issues"][0].pop("evidence")
        (ex / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--review", str(ex / "bad.json"), "--diff", str(diff), "--out-dir", str(tmp / "cur-bad")],
                           capture_output=True, text=True)
        case("curated-violation — 계약 위반이면 exit 1 · 파일 0", r.returncode == 1 and not any((tmp / "cur-bad").glob("*")), (r.returncode, r.stderr[-200:]))
        f = tmp / "uncur.json"
        f.write_text(json.dumps(review(base), ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--review", str(f), "--diff", str(diff), "--out-dir", str(tmp / "uncur"), "--require-curation"],
                           capture_output=True, text=True)
        case("require-curation — excluded 없는 review 는 exit 1 · 파일 0", r.returncode == 1 and not any((tmp / "uncur").glob("*")), r.returncode)
        rep5 = json.loads((ex / "review.json").read_text(encoding="utf-8"))
        rep5["excluded"].append({"id": "T1", "what": "같은 지적", "code": "E5", "reason": "기존 스레드", "duplicateOf": "77", "reply": "REPLY-DRAFT-MARK"})
        (ex / "e5.json").write_text(json.dumps(rep5, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--review", str(ex / "e5.json"), "--diff", str(diff), "--out-dir", str(tmp / "cur-e5")], capture_output=True, text=True)
        pay = json.loads((tmp / "cur-e5" / "payload.json").read_text(encoding="utf-8")) if r.returncode == 0 else {}
        com = (tmp / "cur-e5" / "pr-comments.md").read_text(encoding="utf-8") if r.returncode == 0 else ""
        case("e5-reply-outside-payload — 답글 초안은 payload.body 에 없고 pr-comments.md 끝에만",
             r.returncode == 0 and "REPLY-DRAFT-MARK" not in pay.get("body", "") and "REPLY-DRAFT-MARK" in com, (r.returncode, r.stderr[-200:]))
        br = json.loads((ex / "review.json").read_text(encoding="utf-8"))
        br.pop("pr")
        br["target"] = {"kind": "branch", "ref": "feature/curate", "sha": br["target"]["sha"]}
        (ex / "branch.json").write_text(json.dumps(br, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--review", str(ex / "branch.json"), "--diff", str(diff), "--out-dir", str(tmp / "cur-br"), "--require-curation"],
                           capture_output=True, text=True)
        case("curated-branch-target — 브랜치 대상(pr 없음 · target.kind branch)은 렌더하고 payload 를 만들지 않는다",
             r.returncode == 0 and (tmp / "cur-br" / "review-report.md").exists() and not (tmp / "cur-br" / "payload.json").exists(), (r.returncode, r.stderr[-200:]))
        broken = json.loads((ex / "review.json").read_text(encoding="utf-8"))
        broken["issues"][0]["sites"][0]["end"] = None
        (ex / "broken.json").write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--review", str(ex / "broken.json"), "--diff", str(diff), "--out-dir", str(tmp / "cur-ok")], capture_output=True, text=True)
        case("curated-broken-site — 깨진 site 는 UNRUN · 이전 산출물을 지운다", r.returncode == 2 and not any((tmp / "cur-ok").glob("*")), (r.returncode, r.stderr[-200:]))

    def t_s8():
        # F-117 · F-517 — 강점 블록 · F-037 — 렌더 경로의 base 대조(check_review 가 review.json 폴더의 base-sha.txt 를 읽는다)
        ex = tmp / "s8"
        subprocess.run([sys.executable, __file__, "--example-curated-dir", str(ex)], capture_output=True, text=True)
        args = ["--review", str(ex / "review.json"), "--diff", str(diff), "--require-curation"]
        r = subprocess.run([sys.executable, __file__, *args, "--out-dir", str(tmp / "s8-ok")], capture_output=True, text=True)
        rep = (tmp / "s8-ok" / "review-report.md").read_text(encoding="utf-8") if r.returncode == 0 else ""
        un = render(review(base, strengthGaps=[{"claim": "s1", "uncovered": "U1"}]), SELF_DIFF)["review-report.md"]
        case("strength-gaps-rendered — 두 렌더러가 강점 바로 아래 못 막는 시나리오를 그린다",
             "- 변경 범위가 요구사항과 맞는다\n  - 못 막는 시나리오 — 목록이 빈 채로" in rep and "- s1\n  - 못 막는 시나리오 — U1" in un, (r.returncode, r.stderr[-200:]))
        plain = render(review(base), SELF_DIFF)["review-report.md"]
        case("uncurated-strings-unchanged — strengthGaps 없는 비큐레이션 리포트는 종전 강점 블록 그대로", plain.endswith("## 긍정적 측면\n\n- s1\n")
             and "못 막는" not in plain, plain[-80:])
        (ex / "base-sha.txt").write_text("feedfacecafe0000000000000000000000000000\n", encoding="utf-8")
        r1 = subprocess.run([sys.executable, __file__, *args, "--out-dir", str(tmp / "s8-sha")], capture_output=True, text=True)
        (ex / "base-sha.txt").write_text(CURATED_BASE_SHA + "\n", encoding="utf-8")
        both = json.loads((ex / "review.json").read_text(encoding="utf-8"))
        both["meta"]["base_sha"] = "2222222222222222"
        for i in both["issues"]:
            i["base_evidence"] = i["base_evidence"].rsplit("@", 1)[0] + "@2222222"
        (ex / "both.json").write_text(json.dumps(both, ensure_ascii=False), encoding="utf-8")
        r2 = subprocess.run([sys.executable, __file__, "--review", str(ex / "both.json"), "--diff", str(diff), "--require-curation",
                             "--out-dir", str(tmp / "s8-both")], capture_output=True, text=True)
        case("render-rejects-base-sha-mismatch — base-sha.txt 와 다른 근거 · meta 와 근거를 함께 바꾼 입력은 exit 1 · 파일 0",
             r1.returncode == 1 and r2.returncode == 1 and not any((tmp / "s8-sha").glob("*")) and not any((tmp / "s8-both").glob("*")),
             (r1.returncode, r2.returncode, r1.stderr[-160:]))

    def cli_run(rv, out, *extra):
        f = tmp / f"{out}.json"
        f.write_text(json.dumps(rv, ensure_ascii=False), encoding="utf-8")
        return subprocess.run([sys.executable, __file__, "--review", str(f), "--diff", str(diff), "--out-dir", str(tmp / out), *extra],
                              capture_output=True, text=True)

    def files_in(out):
        return sorted(q.name for q in (tmp / out).glob("*")) if (tmp / out).is_dir() else []

    def t_round2():
        # F-212 — 발견 축 집계 · 실측 비용(규칙끼리 충돌: tiers.md 는 두 절을 요구하는데 렌더 경로에 받을 키가 없었다)
        ax = json.loads(json.dumps(base))
        ax[0]["axis"] = "correctness"
        rep = render(review(ax), SELF_DIFF)["review-report.md"]
        case("f212-axes-section — axis 가 있으면 발견 축 집계 표(0건 축 행 유지 · axis 없음 = other)",
             "## 발견 축 집계" in rep and "| correctness | 1 |" in rep and "| direction | 0 |" in rep and "| other | 2 |" in rep, rep[-300:])
        plain = render(review(base), SELF_DIFF)["review-report.md"]
        case("f212-axes-absent-unchanged — axis 없는 비큐레이션 리포트는 표를 넣지 않는다(옛 바이트)", "발견 축 집계" not in plain, plain[-120:])
        (tmp / "cost-log.json").write_text(json.dumps({"tier": {"selected": 1}, "tokens": {"total": 41000, "method": "actual"},
                                                       "duration_ms": 125000, "phases_ms": {"gather": 30000, "analyze": 60000},
                                                       "issues": {"major": 1, "minor": 1}}), encoding="utf-8")
        r = cli_run(review(base, costLog="cost-log.json"), "cost-ok")
        rep = (tmp / "cost-ok" / "review-report.md").read_text(encoding="utf-8") if r.returncode == 0 else ""
        case("f212-cost-section — costLog 가 가리키는 cost-log.json 으로 실측 비용 절을 그린다",
             r.returncode == 0 and "## 실측 비용" in rep and "- Tier: 1" in rep and "- Total tokens: 41000" in rep and "2분 5초" in rep,
             (r.returncode, r.stderr[-200:]))
        r = cli_run(review(base, costLog="no-such-cost-log.json"), "cost-miss")
        case("f212-cost-log-missing-unrun — costLog 파일이 없으면 UNRUN(exit 2) · 파일 0", r.returncode == 2 and files_in("cost-miss") == [],
             (r.returncode, r.stderr[-200:]))
        # F-201 — 재평가 뒤 파생 산출물(인덱스 · 구조화 JSON)도 같은 판정으로
        d = tmp / "reeval"
        d.mkdir()
        (d / "review-index.md").write_text("# review-index\n\n- Phase: Deliver\n", encoding="utf-8")
        (d / "synthesized-issues.json").write_text(json.dumps({"issues": [{"id": "A1", "severity": "major", "disposition": "include"},
                                                                          {"id": "Z9", "severity": "minor", "disposition": "include"}]}),
                                                   encoding="utf-8")
        r1 = cli_run(review(base), "reeval")
        down = json.loads(json.dumps(base))
        down[0]["severity"] = "minor"
        r2 = cli_run(review(down), "reeval")
        idx = (d / "review-index.md").read_text(encoding="utf-8")
        case("f201-index-rerendered — 재평가 렌더가 review-index.md 렌더 블록을 덮는다(Lead 줄 유지 · 블록 하나 · 대상 head)",
             (r1.returncode, r2.returncode) == (0, 0) and idx.count(INDEX_BEGIN) == 1 and "- A1 [minor]" in idx and "- A1 [major]" not in idx
             and "- Phase: Deliver" in idx and "- 대상 head: abc123" in idx, (r1.returncode, r2.returncode, idx[-300:]))
        syn = json.loads((d / "synthesized-issues.json").read_text(encoding="utf-8"))
        a1, z9 = (next(x for x in syn["issues"] if x["id"] == k) for k in ("A1", "Z9"))
        ccode = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "check_synthesized.py"), str(d / "synthesized-issues.json")],
                               capture_output=True, text=True).returncode
        case("f201-synthesized-rerendered — synthesized-issues.json 의 최종 severity 를 렌더 판정으로 다시 쓰고 처음 값을 보존한다(남의 id 무변경 · 계약 통과)",
             a1.get("severity_final") == "minor" and a1.get("severity_initial") == "major" and z9 == {"id": "Z9", "severity": "minor", "disposition": "include"}
             and not any(d.glob(".*.tmp")) and ccode == 0, (a1, z9, ccode))
        # F-068 — 게시 직전 head 대조
        rv = review(base)
        rv["pr"] = {"number": 7, "headSha": "abc1234def"}
        r = cli_run(rv, "head-bad", "--head-sha", "deadbeef00")
        case("f068-head-mismatch-refused — --head-sha 가 리뷰 대상 sha 와 다르면 exit 1 · 파일 0",
             r.returncode == 1 and "≠" in r.stderr and files_in("head-bad") == [], (r.returncode, r.stderr[-200:]))
        r = cli_run(rv, "head-ok", "--head-sha", "abc1234def0000000000")
        case("f068-head-match-ok — 같은 head(접두 일치)는 렌더한다", r.returncode == 0, (r.returncode, r.stderr[-200:]))
        r = cli_run(rv, "head-empty", "--head-sha", "")
        case("f068-empty-head-refused — 넘긴 빈 --head-sha(조회 실패)는 생략이 아니라 거부 · 파일 0",
             r.returncode == 1 and "비었다" in r.stderr and files_in("head-empty") == [], (r.returncode, r.stderr[-200:]))
        rt = review(base, target={"kind": "pr", "ref": "pr-7", "sha": "aaaaaaa1111"})
        rt["pr"] = {"number": 7, "headSha": "bbbbbbb2222"}
        r = cli_run(rt, "head-target", "--head-sha", "bbbbbbb2222")
        case("f068-target-sha-also-checked — pr.headSha 만 새 head 와 맞고 target.sha(근거 대조 head)가 다르면 거부",
             r.returncode == 1 and "target.sha aaaaaaa1111" in r.stderr and files_in("head-target") == [], (r.returncode, r.stderr[-200:]))
        # F-069 — 게시 코멘트 전건 줄 대조(minor · suggestion 포함)
        def rejected(rs):
            try:
                render(review(rs), SELF_DIFF)
                return ""
            except Reject as e:
                return str(e)
        wrong = json.loads(json.dumps(base))
        wrong[1]["sites"][0]["expect"] = "zzz"
        miss = json.loads(json.dumps(base))
        del miss[1]["sites"][0]["expect"]
        case("f069-all-posted-anchored — 게시 코멘트(minor 포함)의 expect 가 앵커 줄에 없거나 빠지면 거부",
             "Q1" in rejected(wrong) and "Q1" in rejected(miss), (rejected(wrong)[:120], rejected(miss)[:120]))
        quoted = json.loads(json.dumps(base))
        del quoted[2]["sites"][0]["expect"]
        nopr = review(miss)
        del nopr["pr"]
        case("f069-unposted-no-check — 앵커 불가 지점(인용) · payload 없는 렌더는 expect 를 요구하지 않는다",
             rejected(quoted) == "" and render(nopr, SELF_DIFF)["payload"] is None, rejected(quoted)[:120])
        # F-020 — 사용자 대면 산출물 언어
        en = review(json.loads(json.dumps(base)), verdict="Comment level only - nothing blocks the merge", strengths=["Scope matches the requirement"])
        for i in en["issues"]:
            i["what"] = "The new guard returns an empty array when the input is nil"
            i.pop("comment", None)
            i.pop("suggestion", None)
        r = cli_run(en, "lang-en", "--lang", "ko")
        case("f020-report-language-mismatch — --lang ko 인데 리포트 산문이 영어면 exit 1 · 파일 0",
             r.returncode == 1 and "한글 비율" in r.stderr and files_in("lang-en") == [], (r.returncode, r.stderr[-200:]))
        r = cli_run(review(base), "lang-ko", "--lang", "ko")
        case("f020-korean-report-ok — 한국어 산문(식별자 섞임)은 통과", r.returncode == 0, (r.returncode, r.stderr[-200:]))

    def t_judgment():
        # F-514 · F-559 — 병합 axisCoverage 의 gap 행
        merged = [{"axis": "architecture", "status": "gap", "claude": [{"status": "none", "note": "레이어 위반 없음"}],
                   "gpt": [{"status": "gap", "note": "지침의 의존 방향이 서로 반대라 판정하지 않았다"}]},
                  {"axis": "naming", "status": "none", "claude": [{"status": "none", "note": "규칙 준수"}], "gpt": []},
                  {"axis": "placement", "status": "gap", "claude": [], "gpt": []}]
        rep = render(review(base, axisCoverage=merged), SELF_DIFF)["review-report.md"]
        case("f514-gap-row-rendered — 병합 axisCoverage 의 gap 행을 '판정 안 함' 으로 · 양쪽 근거 · 아무도 안 본 축도 행으로 그린다",
             "## 축 판정" in rep and "| architecture | 판정 안 함 | claude none: 레이어 위반 없음 / gpt gap: 지침의 의존 방향이 서로 반대라 판정하지 않았다 |" in rep
             and "| naming | 위반 없음 |" in rep and "| placement | 판정 안 함 | 어느 입력도 이 축을 보지 않았다 |" in rep, rep[-500:])
        plain = render(review(base), SELF_DIFF)["review-report.md"]
        case("f514-no-coverage-unchanged — 판정 한계 키가 없으면 옛 바이트(세 절 모두 없음)",
             not any(h in plain for h in ("## 축 판정", "## 재지 않은 전제", "## Lead 기각", "**대안**")), plain[-200:])
        # F-448 — 재지 않은 전제
        prem = [{"claim": "27.1 SDK 에서도 같은 접힘 알림이 온다", "why": "렌즈는 27.0 SDK 코드만 읽었다", "howToMeasure": "27.1 시뮬에서 접힘 로그",
                 "affects": ["A1"], "lens": "arch"}]
        rep = render(review(base, unverifiedPremises=prem), SELF_DIFF)["review-report.md"]
        case("f448-premises-rendered — unverifiedPremises 를 `## 재지 않은 전제` 절로 · 이유 · 판별 방법 · 기댄 판정이 함께 실린다",
             "## 재지 않은 전제 1건" in rep and "- 27.1 SDK 에서도 같은 접힘 알림이 온다 — 못 잰 이유: 렌즈는 27.0 SDK 코드만 읽었다 · 판별: 27.1 시뮬에서 접힘 로그 · 기댄 판정: A1 · 렌즈: arch" in rep,
             rep[-400:])
        # F-115 — 외부 렌즈 대안 · 추천 원문 이송
        alt = json.loads(json.dumps(base))
        alt[0]["alternatives"] = [{"label": "A: 현재 만료 방식", "description": "그대로 둔다", "pros": ["변경 없음"], "cons": ["누수"]},
                                  {"label": "B: 범위 기반 정리", "description": "화면 범위를 벗어나면 지운다", "pros": [], "cons": []}]
        alt[0]["recommended"] = "B: 범위 기반 정리"
        rep = render(review(alt), SELF_DIFF)["review-report.md"]
        case("f115-alternatives-rendered — 이슈 아래 대안 label · 설명 · 장단점과 추천 label 을 원문 그대로 싣는다",
             "**대안** (외부 렌즈 원문)" in rep and "- A: 현재 만료 방식 — 그대로 둔다 (장점 변경 없음 · 단점 누수)" in rep
             and "- B: 범위 기반 정리 — 화면 범위를 벗어나면 지운다" in rep and "**추천** — B: 범위 기반 정리" in rep, rep[:900])
        para = json.loads(json.dumps(alt))
        para[0]["recommended"] = "범위 정리 방식"
        try:
            render(review(para), SELF_DIFF)
            got = "통과"
        except InputError as e:
            got = str(e)
        case("f115-recommended-must-match-label — 추천을 label 아닌 말로 바꿔 쓰면 입력 불가(재서술 차단)", "recommended" in got and got != "통과", got)
        # F-517 — Lead 기각 관찰
        dis = [{"id": "L9", "what": "클릭 로그가 노출 로그와 같은 키로 두 번 나간다", "reason": "기존 노출 파이프라인 관례와 같다"}]
        rep = render(review(base, dismissed=dis), SELF_DIFF)["review-report.md"]
        d = tmp / "dismiss"
        d.mkdir()
        (d / "synthesized-issues.json").write_text(json.dumps({"issues": [{"id": "L9", "severity": "minor", "disposition": "include"},
                                                                          {"id": "Z8", "severity": "minor", "disposition": "include"}]}),
                                                   encoding="utf-8")
        r = cli_run(review(base, dismissed=dis), "dismiss")
        syn = json.loads((d / "synthesized-issues.json").read_text(encoding="utf-8"))
        l9, z8 = (next(x for x in syn["issues"] if x["id"] == k) for k in ("L9", "Z8"))
        case("f517-dismissal-rendered — dismissed 를 리포트 `## Lead 기각 — 의도 확인 후보` 절과 synthesized disposition exclude + disposition_reason 으로 남긴다",
             "## Lead 기각 — 의도 확인 후보 1건" in rep and "- `L9` — 클릭 로그가 노출 로그와 같은 키로 두 번 나간다 · 기각 사유: 기존 노출 파이프라인 관례와 같다" in rep
             and r.returncode == 0 and l9.get("disposition") == "exclude" and l9.get("disposition_reason") == "기존 노출 파이프라인 관례와 같다"
             and l9.get("disposition_initial") == "include" and z8 == {"id": "Z8", "severity": "minor", "disposition": "include"},
             (r.returncode, r.stderr[-200:], l9, z8))

    def t_synth_sync():
        # F-201 — 파생 산출물 동기화: Lead 별칭 모양(severity_raw + severity=최종) · 묶음 excluded 카드의 covers
        d = tmp / "synth-sync"
        d.mkdir()
        f = d / "synthesized-issues.json"
        f.write_text(json.dumps({"issues": [{"id": "A1", "severity_raw": "major", "severity": "minor", "disposition": "include"},
                                            {"id": "E1", "severity": "minor", "disposition": "include"},
                                            {"id": "C1", "severity": "minor", "disposition": "include"},
                                            {"id": "C2", "severity": "minor", "disposition": "include"}]}), encoding="utf-8")
        syn = synth_update(f, {"issues": [{"id": "A1", "severity": "suggestion"}],
                               "excluded": [{"id": "E1", "code": "E3", "reason": "같은 뿌리", "covers": ["C1", "C2"]}]})
        f.write_text(json.dumps(syn, ensure_ascii=False), encoding="utf-8")
        a1 = syn["issues"][0]
        ccode = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "check_synthesized.py"), str(f)],
                               capture_output=True, text=True)
        case("f201-lead-alias-final-kept — severity_raw 를 적은 Lead 모양은 severity(최종)를 고치고 severity_final 을 새로 만들지 않는다(계약 통과)",
             a1.get("severity") == "suggestion" and a1.get("severity_raw") == "major" and "severity_final" not in a1
             and a1.get("severity_initial") == "minor" and ccode.returncode == 0, (a1, ccode.stdout[-200:]))
        disp = {x["id"]: (x.get("disposition"), x.get("disposition_reason")) for x in syn["issues"][1:]}
        case("f201-excluded-covers-propagated — 묶음 excluded 카드의 covers 후보도 같은 처분 · 사유",
             all(v == ("exclude:E3", "같은 뿌리") for v in disp.values()), disp)
        unv = curated_report({"verdict": "v", "excluded": []}, [], {"thread_line": "t", "symbol_check": "제안 식별자 X 미검증"})
        ok_ = curated_report({"verdict": "v", "excluded": []}, [], {"thread_line": "t"})
        case("f063-unverified-symbols-in-report — 대조 못 한 제안 식별자는 리포트에 미검증으로 남는다",
             "## 제안 식별자 대조" in unv and "미검증" in unv and "제안 식별자 대조" not in ok_, unv[-200:])

    tests = [t_ids, t_anchor, t_lines, t_body, t_na, t_pick, t_event, t_split, t_carry, t_nodiff, t_empty, t_nopr, t_det, t_limit, t_cli,
             t_example, t_curated, t_s8, t_round2, t_judgment, t_synth_sync]
    try:
        for t in tests:
            try:
                t()
            except Exception as e:   # ⛔ 케이스 안의 예외는 FAIL 로 센다 — 크래시로 끝나면 몇 건이 안 돌았는지 모른다
                case(f"{t.__name__} — 예외", False, repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else REJECT


CURATED_SHA = "abc1234def5678"
CURATED_BASE_SHA = "0123456789abcdef0123456789abcdef01234567"   # 예시 base-sha.txt — gather 가 base/ 를 뜬 커밋
# --example-curated-dir — SELF_DIFF · 게이트 합성 patch 의 앵커 가능한 줄(src/a.swift 11-12)만 쓴다. GPT 전용 후보(gpt:G2)는 E2 로 제외
EXAMPLE_CURATED = {
    "review.json": {
        "verdict": "코멘트 1건 · 질문 1건 — 머지를 막을 결함은 없다", "event": "COMMENT",
        "pr": {"number": 7, "headSha": CURATED_SHA}, "target": {"kind": "pr", "ref": "pr-7", "sha": CURATED_SHA},
        "meta": {"base_sha": CURATED_BASE_SHA},
        "candidates": ["merged.json", "synthesized-issues.json"],
        "issues": [
            {"id": "A1", "kind": "bug", "severity": "major", "origin": "regression", "confidence": 90, "foundBy": ["claude", "gpt"],
             "covers": ["claude:C1", "gpt:G1", "S1"], "what": "nil 이면 목록이 비어 보인다(WHY — 새 guard 가 빈 배열을 반환한다)",
             "suggestion": "nil 일 때 이전 목록을 유지한다", "evidence": ["src/a.swift:11-12@abc1234"], "base_evidence": "src/a.swift:11@0123456",
             "repro": {"status": "code-determined", "how": "nil 입력 → 11행 guard → 빈 배열"}, "symptom_screen": "목록 화면",
             "symptom_reach": "탭 진입 → 목록 로드 실패", "refute": "반박 시도 — 호출부 1곳이 nil 을 걸러내는지 확인했으나 거르지 않는다",
             "base_quote": "return items", "chain": [{"step": "nil 입력", "grade": "code"}, {"step": "11행 guard 가 빈 배열을 반환", "grade": "code"}],
             "severity_basis": {"kind": "output-change", "note": "목록이 빈 화면으로 바뀐다"},
             "comment": "nil 이 들어오면 11행 guard 에서 빈 배열이 반환돼 목록이 비어 보입니다.\n이전 목록을 유지하는 쪽은 어떨지 확인 부탁드립니다.",
             "sites": [{"path": "src/a.swift", "start": 11, "end": 12, "expect": "l11"}]},
            {"id": "Q1", "kind": "intent-question", "severity": "suggestion", "origin": "regression",
             "what": "12행 재시도 횟수 3 이 의도한 값인지", "evidence": ["src/a.swift:12@abc1234"], "base_evidence": "src/a.swift:12@0123456",
             "base_quote": "let retry = 2",
             "refute": "반박 시도 — 요구사항 문서에 값이 없다", "comment": "12행 재시도 3회가 기획 값인지 여쭙습니다.",
             "sites": [{"path": "src/a.swift", "start": 12, "end": 12, "expect": "l12"}]}],
        "excluded": [
            {"id": "claude:C2", "what": "base 에도 있던 강제 언래핑", "code": "E4", "reason": "base 같은 줄 — 이번 PR 무관"},
            {"id": "gpt:G2", "what": "SDK 콜백이 메인 스레드라는 가정", "code": "E2", "reason": "SDK 내부 동작 가정 — 근거 없음"}],
        "strengths": ["변경 범위가 요구사항과 맞는다"],
        "strengthGaps": [{"claim": "변경 범위가 요구사항과 맞는다", "uncovered": "목록이 빈 채로 캐시되는 재진입 경로는 이 범위가 막지 않는다"}],
    },
    "merged.json": {
        "schemaVersion": 1, "inputs": {"claude": 2, "gpt": 2, "gptVerdicts": 0, "gptUnavailable": None, "evidenceChecked": True},
        "candidates": [
            {"id": "claude:C1", "source": "claude", "lens": "arch", "file": "src/a.swift", "line_range": "11-12", "severity": "major",
             "origin": "regression", "evidence": "src/a.swift:11", "effectiveSeverity": "major", "foundBy": ["claude"]},
            {"id": "claude:C2", "source": "claude", "lens": "quality", "file": "src/a.swift", "line_range": "13", "severity": "minor",
             "origin": "pre-existing", "evidence": "src/a.swift:13", "effectiveSeverity": "suggestion", "foundBy": ["claude"]},
            {"id": "gpt:G1", "source": "gpt", "lens": None, "file": "src/a.swift", "line_range": "11", "severity": "major",
             "origin": "regression", "evidence": "src/a.swift:11", "effectiveSeverity": "major", "foundBy": ["gpt"]},
            {"id": "gpt:G2", "source": "gpt", "lens": None, "file": "src/a.swift", "line_range": "12", "severity": "minor",
             "origin": "regression", "evidence": "src/a.swift:12", "effectiveSeverity": "minor", "foundBy": ["gpt"]}],
        "summary": {"candidatesIn": 4, "candidatesOut": 4},
    },
    "synthesized-issues.json": {"issues": [{"id": "S1", "severity": "major", "found_by": ["claude", "gpt"], "file": "src/a.swift",
                                            "line": "11-12", "symptom_screen": "목록 화면", "symptom_reach": "탭 진입 → 목록 로드 실패"}]},
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--review")
    ap.add_argument("--diff")
    ap.add_argument("--out-dir")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--example", action="store_true")
    ap.add_argument("--require-curation", action="store_true")
    ap.add_argument("--example-curated-dir", metavar="DIR")
    ap.add_argument("--head-sha", metavar="SHA")
    ap.add_argument("--lang", choices=("ko",))
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return OK
    if a.example_curated_dir:
        d = Path(a.example_curated_dir)
        d.mkdir(parents=True, exist_ok=True)
        for name, obj in EXAMPLE_CURATED.items():
            (d / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (d / "base-sha.txt").write_text(CURATED_BASE_SHA + "\n", encoding="utf-8")   # gather 산출물 자리 — regression 근거 대조 기준
        print(f"→ {d}/  " + " · ".join(EXAMPLE_CURATED))
        return OK
    if not (a.review and a.diff and a.out_dir):
        print("UNRUN: --review · --diff · --out-dir 가 모두 필요하다 (또는 --self-test)", file=sys.stderr)
        return UNRUN
    return run_render(a)


if __name__ == "__main__":
    sys.exit(main())
