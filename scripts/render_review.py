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
  site  필수 path · start · end   선택 side(RIGHT · LEFT, 기본 RIGHT) · pick · note(조각 설명) · quote(diff 밖일 때 인용할 코드)

모드
  --review FILE --diff FILE --out-dir DIR   review-report.md · pr-comments.md · render-preview.json · payload.json(pr.headSha 가 있을 때만)
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


def report(r: dict, plans: list) -> str:
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
    if r.get("severityNote"):
        lines += ["## Severity 보정 근거", "", r["severityNote"].strip(), ""]
    lines += strength_lines(r)
    return "\n".join(lines).rstrip() + "\n"


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


def curated_report(r: dict, plans: list, info: dict) -> str:
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
    replies = [x for x in ex if x.get("code") == "E5" and str(x.get("reply") or "").strip()]
    if replies:   # ⛔ 본문은 넣지 않는다 — 리포트가 payload.body 로 게시되면 답글 초안이 새 리뷰에 실린다(초안은 pr-comments.md 끝 · 로컬)
        lines += [f"답글 초안 {len(replies)}건 — pr-comments.md 끝(게시 payload 밖 · 기존 스레드에 따로 단다)", ""]
    if r.get("severityNote"):
        lines += ["## Severity 보정 근거", "", r["severityNote"].strip(), ""]
    lines += strength_lines(r)
    return "\n".join(lines).rstrip() + "\n"


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


def render(review, diff_text: str, curation: dict | None = None) -> dict:
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
    rep = curated_report(review, plans, curation or {}) if "excluded" in review else report(review, plans)
    comments, rows = inline(us)
    pr = review.get("pr") or {}
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
        except Exception as e:   # ⛔ 예외도 fail() 로 — 이전 실행의 payload · 리포트가 지금 리뷰로 남으면 게시된다
            return fail(UNRUN, f"UNRUN: 코멘트 가치 검사 예외 — {type(e).__name__}: {e}")
        for w in warn:
            print(f"WARN {w}", file=sys.stderr)
        if code:
            return fail(REJECT if code == ccw.VIOLATION else UNRUN,
                        ("REJECT" if code == ccw.VIOLATION else "UNRUN") + ": 코멘트 가치 검사 — " + " · ".join(bad[:5]))
    try:
        out = render(review, diff_text, curation)
    except InputError as e:
        return fail(UNRUN, f"UNRUN: {e}")
    except Reject as e:
        return fail(REJECT, f"REJECT: {e}")
    d.mkdir(parents=True, exist_ok=True)
    (d / "review-report.md").write_text(out["review-report.md"], encoding="utf-8")
    (d / "pr-comments.md").write_text(out["pr-comments.md"], encoding="utf-8")
    (d / "render-preview.json").write_text(json.dumps(out["preview"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if out["payload"]:
        (d / "payload.json").write_text(json.dumps(out["payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        (d / "payload.json").unlink(missing_ok=True)   # ⛔ 이전 실행의 payload 가 남아 게시되면 지금 리뷰와 다른 내용이 올라간다
    p = out["preview"]
    print(f"렌더 — 이슈 {p['issues']}건 · 인라인 {len(p['inline'])}건(파일 {len(p['byFile'])}) · 리포트만 {len(p['reportOnly'])}건 · "
          f"event {p['event']} · payload {'있음' if out['payload'] else '없음(pr.headSha 없음)'}")
    print("확인 필요 — " + " · ".join(p["reasons"]) if p["confirmRequired"] else "확인 게이트 해당 없음")
    print(f"→ {d}/  " + " · ".join(f for f in OUTPUTS if (d / f).exists()))
    return OK


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
         "sites": [{"path": "src/a.swift", "start": 11, "end": 12}]},
        {"id": "Q1", "severity": "minor", "what": "한 줄 지적", "sites": [{"path": "src/b.swift", "start": 2, "end": 2, "note": "조각 설명"}]},
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

    tests = [t_ids, t_anchor, t_lines, t_body, t_na, t_pick, t_event, t_split, t_carry, t_nodiff, t_empty, t_nopr, t_det, t_limit, t_cli,
             t_example, t_curated, t_s8]
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
             "comment": "nil 이 들어오면 11행 guard 에서 빈 배열이 반환돼 목록이 비어 보입니다.\n이전 목록을 유지하는 쪽은 어떨지 확인 부탁드립니다.",
             "sites": [{"path": "src/a.swift", "start": 11, "end": 12}]},
            {"id": "Q1", "kind": "intent-question", "severity": "suggestion", "origin": "regression",
             "what": "12행 재시도 횟수 3 이 의도한 값인지", "evidence": ["src/a.swift:12@abc1234"], "base_evidence": "src/a.swift:12@0123456",
             "refute": "반박 시도 — 요구사항 문서에 값이 없다", "comment": "12행 재시도 3회가 기획 값인지 여쭙습니다.",
             "sites": [{"path": "src/a.swift", "start": 12, "end": 12}]}],
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
