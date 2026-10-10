#!/usr/bin/env python3
# diff-parse: not-a-diff — 게시 payload(JSON)와 GitHub 응답(JSON)의 필드만 대조한다. diff 줄을 읽지 않는다.
"""인라인 리뷰 착지 검증 (F-150 · F-256 · F-282) — 방금 게시한 리뷰의 코멘트가 payload 대로 달렸는지 **판정만** 한다.

정본 절차는 `modules/peer-review-inline-anchoring.md` § 3 의 7) 착지 검증이다. 이 스크립트는 그 절차의 실행체다.

  1. id 수집   `gh api --paginate repos/{owner}/{repo}/pulls/{N}/reviews/{review_id}/comments --jq '.[].id'`
               ⛔ 이 하위 컬렉션은 id 를 모으는 데만 쓴다 — 응답이 `line`·`side`·`start_*` 를 null 로 주고
               `position`·`diff_hunk` 만 채울 수 있다(실측 3회). 그 null 을 불일치로 읽으면 정상 게시를 지운다
  2. 개별 조회  id 마다 `gh api repos/{owner}/{repo}/pulls/comments/{id}` — 필드 대조는 이 값으로만 한다
  3. 짝 맞춤    payload 코멘트와 조회 코멘트를 본문으로 맞춘다(렌더 경로 본문에는 `<!-- fz-review:ID -->` 표지가 있어 이슈 id 도 함께 적는다)
  4. 판정      payload 항목마다 넷 중 하나
       OK          payload 에 넣은 앵커 필드(path · line · side, 다중 라인이면 start_line · start_side)가 조회 값과 모두 같다
       MISMATCH    그 필드가 모두 non-null 인데 하나라도 다르다 — 다른 파일 · 다른 줄로 확정
       UNVERIFIED  그 필드 중 null(또는 응답에 없음)이 있다 · 개별 조회 실패 · 짝을 확정하지 못했다 ·
                   head 가 움직였는데 응답 original_commit_id 가 payload commit_id 와 다르다(게시 시점 위치를 모른다)
       MISSING     이 리뷰의 id 를 전부 조회했는데 본문이 같은 코멘트가 없다
     단일 줄 코멘트는 start_* 를 보내지 않으므로 응답의 start_* null 은 판정에 들어가지 않는다(명시 null 도 안 보낸 것으로 센다).
     POST 와 조회 사이 PR head 가 움직이면 두 경우다 — payload 최상위 commit_id(게시 시점 head)로 가른다
       outdated   line 이 null 이고 original_line 만 남는다 → 위 null 규칙으로 UNVERIFIED
       이월       새 head 로 옮겨지며 line 이 다시 매겨지고 commit_id 가 전진한다 → 응답 original_commit_id == payload commit_id
                  일 때만 line · start_line 을 original_line · original_start_line 과, path · side · start_side 는 현재 값과 대조한다.
                  아니면 UNVERIFIED. [미검증: 실 GitHub 가 이월 코멘트의 line 을 다시 매기는지 — 실 API UNRUN]
       payload 에 commit_id 가 없으면 이월을 가르지 못해 현재 값으로 대조한다(이유에 그렇게 적는다)
     짝 맞춤은 2단계다 — ① 본문이 같고 판정 OK 인 짝을 최대 일대일 매칭(증가 경로)으로 먼저 정하고 ② 남은 항목만 남은 같은 본문 코멘트에 맞춘다
       (①을 순서대로 고르면 응답 순서에 따라 정상 착지끼리 짝을 잘못 가져가 UNVERIFIED 가 생긴다 — 같은 본문의 단일 줄 · 다중 줄)

⛔ 이 스크립트는 삭제 · 재게시를 하지 않는다. UNVERIFIED 는 삭제 · 재게시 대상이 아니다. MISMATCH · MISSING 의 삭제 · 재게시는
   사용자에게 보이고 확인받은 뒤 Lead 가 한다(출력의 confirmBeforeDelete 는 MISMATCH id 만 담는다).

usage: verify_landing.py --payload payload.json --pr N --review-id ID [--repo OWNER/REPO]
  --repo 기본값 `{owner}/{repo}` — gh 가 현재 폴더의 저장소로 채운다(GH_REPO 가 있으면 그 값)
출력: stdout = 판정 JSON(reviewId · ids · counts · items · unpaired · confirmBeforeDelete) · stderr 마지막 줄 = `verify_landing: …` 요약
exit: 0 전건 OK · 1 OK 아닌 항목이 있다(MISMATCH · UNVERIFIED · MISSING · 짝 없는 코멘트) ·
      2 판정 불가(gh 부재 · 하위 컬렉션 조회 실패 · payload 읽기 실패 · review id 비정상 — ⛔ 통과 아님 · 실 API 를 못 부르면 UNRUN)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys

OK, NOT_OK, UNRUN = 0, 1, 2
VERDICTS = ("OK", "MISMATCH", "UNVERIFIED", "MISSING")
ANCHOR_KEYS = ("path", "line", "side", "start_line", "start_side")
MARK_RE = re.compile(r"<!-- fz-review:([A-Za-z0-9:_.\-]+) -->")   # scripts/render_review.py MARK 와 같은 표지


def unrun(msg: str):
    print(f"verify_landing: UNRUN — {msg} (⛔ 통과 아님)", file=sys.stderr)
    sys.exit(UNRUN)


def gh(args: list) -> tuple:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def norm(body) -> str:
    return "\n".join(line.rstrip() for line in str(body or "").replace("\r\n", "\n").split("\n")).strip()


def judge(want: dict, got: dict, sent_commit) -> tuple:
    """payload 항목 하나와 개별 조회 응답 하나 → (판정, 이유). sent_commit = payload 최상위 commit_id(게시 시점 head · 없으면 None)."""
    keys = [k for k in ANCHOR_KEYS if want.get(k) is not None]   # 값을 넣은 필드만 보낸 것으로 센다 — 명시 null 은 안 보낸 것
    nulls = [k for k in keys if got.get(k) is None]
    if nulls:
        why = "필수 필드 null: " + ",".join(nulls)
        if "line" in nulls and got.get("original_line") is not None:
            why += f" · original_line={got['original_line']} — POST 와 조회 사이 PR head 가 움직였을 수 있다"
        if got.get("position") is not None or got.get("diff_hunk"):
            why += " · position/diff_hunk 는 있다(응답 형태 문제일 수 있다)"
        return "UNVERIFIED", why + " — ⛔ 삭제 · 재게시 금지"
    cur, note = got, ""
    if sent_commit is None:
        note = "payload commit_id 없음 — 이월 판별 불가 · 현재 값으로 대조"
    elif got.get("commit_id") != sent_commit:
        # head 이동 뒤 이월된 코멘트는 line 이 새 head 기준으로 다시 매겨진다 — 그 값을 게시값과 비교하면 정상 게시가 '확정 불일치' 가 된다
        if got.get("original_commit_id") != sent_commit:
            return "UNVERIFIED", (f"head 이동 — 게시 시점 위치를 확인할 수 없다(commit_id {got.get('commit_id')!r} · "
                                  f"original_commit_id {got.get('original_commit_id')!r} ≠ payload {sent_commit!r}) — ⛔ 삭제 · 재게시 금지")
        cur = dict(got, line=got.get("original_line"), start_line=got.get("original_start_line"))
        onulls = [k for k in keys if cur.get(k) is None]
        if onulls:
            return "UNVERIFIED", "head 이동 — original_* null: " + ",".join(onulls) + " — ⛔ 삭제 · 재게시 금지"
        note = "head 이동 — original_* 로 대조"
    diffs = [f"{k} 기대 {want[k]!r} · 실제 {cur[k]!r}" for k in keys if cur[k] != want[k]]
    if diffs:
        return "MISMATCH", "; ".join(diffs) + (f" ({note})" if note else "") + " — 삭제 · 재게시는 사용자 확인 뒤"
    return "OK", note


def main() -> int:
    ap = argparse.ArgumentParser(description="인라인 리뷰 착지 검증 — 판정만 한다(삭제 · 재게시 없음)")
    ap.add_argument("--payload", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--review-id", required=True)
    ap.add_argument("--repo", default="{owner}/{repo}")
    a = ap.parse_args()

    try:
        payload = json.load(open(a.payload, encoding="utf-8"))
        wants = payload["comments"]
        if not isinstance(wants, list) or not all(isinstance(w, dict) for w in wants):
            raise ValueError("comments 가 객체 배열이 아니다")
    except (OSError, ValueError, KeyError, TypeError) as e:
        unrun(f"payload 읽기 실패 {a.payload}: {type(e).__name__}: {e}")
    if not str(a.review_id).strip().isdigit():
        unrun(f"review id 가 숫자가 아니다: {a.review_id!r} — POST 응답에서 잡았는가")
    if shutil.which("gh") is None:
        unrun("gh 부재 — 실 API 를 부를 수 없다")

    sent = payload.get("commit_id") or None
    base = f"repos/{a.repo}/pulls"
    rc, out, err = gh(["api", "--paginate", f"{base}/{a.pr}/reviews/{a.review_id}/comments", "--jq", ".[].id"])
    if rc != 0:
        unrun(f"하위 컬렉션 조회 실패(exit {rc}): {(err.strip().splitlines() or [''])[-1]}")
    ids = [x.strip() for x in out.splitlines() if x.strip()]

    fetched, unfetched = [], {}
    for cid in ids:
        rc, out, err = gh(["api", f"{base}/comments/{cid}"])
        try:
            obj = json.loads(out) if rc == 0 else None
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            fetched.append(obj)
        else:
            unfetched[cid] = f"개별 조회 실패(exit {rc}): {(err.strip().splitlines() or [''])[-1]}"

    # 1차 — 짝을 모두 정한 뒤 2차에서 판정한다(짝 없는 항목의 MISSING · UNVERIFIED 는 남은 코멘트를 다 알아야 가른다)
    #   짝 맞춤 ① 본문이 같고 판정 OK 인 짝을 최대 일대일 매칭(증가 경로)으로 정한다 — 응답 순서 · 키 부분집합과 무관하게 OK 짝 수가 최대
    #          ② 남은 항목만 남은 같은 본문 코멘트에 payload 순서로 맞춘다
    same = [[k for k, o in enumerate(fetched) if norm(o.get("body")) == norm(w.get("body"))] for w in wants]
    ok = [[k for k in same[i] if judge(w, fetched[k], sent)[0] == "OK"] for i, w in enumerate(wants)]
    owner = {}   # 코멘트 색인 → payload 색인

    def augment(i, seen):
        for k in ok[i]:
            if k not in seen:
                seen.add(k)
                if k not in owner or augment(owner[k], seen):
                    owner[k] = i
                    return True
        return False

    for i in range(len(wants)):
        augment(i, set())
    used, pair = set(owner), [None] * len(wants)
    for k, i in owner.items():
        pair[i] = k
    for i in range(len(wants)):
        if pair[i] is None:
            k = next((k for k in same[i] if k not in used), None)
            if k is not None:
                used.add(k)
                pair[i] = k
    items = []
    for i, (w, k) in enumerate(zip(wants, pair)):
        marks = MARK_RE.findall(str(w.get("body") or ""))
        item = {"index": i, "issue": marks[0] if marks else None,
                "want": {key: w[key] for key in ANCHOR_KEYS if key in w}, "id": None, "got": None}
        if k is not None:
            got = fetched[k]
            item["id"] = got.get("id")
            item["got"] = {key: got.get(key) for key in ANCHOR_KEYS + ("original_line", "original_start_line", "subject_type",
                                                                      "commit_id", "original_commit_id")}
            item["verdict"], item["reason"] = judge(w, got, sent)
        elif not ids:
            item["verdict"], item["reason"] = "UNVERIFIED", "하위 컬렉션이 id 0건 — 측정 실패를 먼저 의심한다(리뷰 id · 반영 지연)"
        elif unfetched or len(used) < len(fetched):
            item["verdict"] = "UNVERIFIED"
            item["reason"] = f"짝을 확정하지 못했다 — 조회 실패 id {len(unfetched)}건 · 본문이 다른 코멘트가 남아 있다"
        else:
            item["verdict"], item["reason"] = "MISSING", f"이 리뷰의 코멘트 {len(ids)}건을 모두 조회했는데 본문이 같은 코멘트가 없다"
        items.append(item)
    # 짝을 못 찾은 코멘트는 이 리뷰에 있지만 payload 와 맞지 않는다 — 판정에서 빼지 않고 함께 보고한다
    unpaired = [{"id": fetched[k].get("id"), "reason": "payload 와 본문이 같은 항목이 없다"} for k in range(len(fetched)) if k not in used]
    unpaired += [{"id": int(cid) if cid.isdigit() else cid, "reason": why} for cid, why in unfetched.items()]

    counts = {v: sum(1 for it in items if it["verdict"] == v) for v in VERDICTS}
    report = {"reviewId": str(a.review_id), "ids": ids, "counts": counts, "items": items, "unpaired": unpaired,
              "confirmBeforeDelete": [it["id"] for it in items if it["verdict"] == "MISMATCH"]}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("verify_landing: " + " · ".join(f"{v} {counts[v]}" for v in VERDICTS) + f" · 짝 없음 {len(unpaired)}"
          + " — ⛔ 이 스크립트는 삭제 · 재게시하지 않는다(UNVERIFIED 는 금지 · MISMATCH · MISSING 은 사용자 확인 뒤)", file=sys.stderr)
    return OK if counts["OK"] == len(items) and not unpaired else NOT_OK


if __name__ == "__main__":
    sys.exit(main())
