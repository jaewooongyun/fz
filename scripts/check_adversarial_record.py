#!/usr/bin/env python3
# lint:no-root-anchor — 판정 루트는 --root 인자로 받는다(파일 위치로 플러그인 루트를 추론하지 않는다)
"""적대 재검토 기록 판정 — 고친 검사기를 믿기 전에 GPT 적대 재검토를 받았는가(F-329 · guides/harness-engineering.md §5.6).

기록(JSON)은 셋 다 맞아야 통과한다.
  1. verdict 가 approved · pass 다 — rejected · needs_revision 은 거부한다
  2. critical · major 지적이 0 이다 — status · resolution 값으로 면제하지 않는다(고쳤으면 고친 파일로 다시 재검토 받은 기록을 쓴다)
  3. targets 의 경로 집합이 --target 집합과 같고, 각 sha 가 지금 트리 파일의 git blob sha 와 같다 — 낡은 기록 · 다른 파일 기록을 거부한다
GPT 판정 스키마는 targets 를 내지 못한다. 그래서 Lead 가 GPT 출력에서 이 기록을 쓰고 source 에 원 출력 경로를 남긴다.

`--policy reachable-fail-open`(원장이 명시해야 한다 — 기본은 위 엄격 판정): 적대 라운드가 정해 둔 예산 안에서 수렴하지 않아 사용자가
기준을 바꾼 게이트용이다. 2 를 「도달 가능한 fail-open 0」 으로 바꾼다 — critical · major 지적마다 description 앞머리의
`[reach:normal|crafted][dir:fail-open|over-reject]` 표지(검토자가 단다)를 읽어 normal + fail-open 만 막는다. 표지가 없거나 틀리면 막는다.
표지는 Lead 가 아니라 검토자의 것이어야 한다 — 기록의 지적(id · severity · description)이 source 원 출력의 지적과 같아야 한다.
verdict 는 rejected 만 막는다.

`--policy dispositioned`(F-582 — 보편 계약을 fixture 로 잰 적대 라운드는 수렴하지 않는다): 라운드를 다시 돌리지 않고 지적마다 처분으로
닫는다. 기록 · source 대조와 verdict 는 reachable-fail-open 과 같고, 2 를 「critical · major 마다 처분 한 행」 으로 바꾼다.
  fixed → ref 의 셀이 전부 --cell-out(같은 CHECK 가 방금 돌린 self-test 출력)에서 PASS 이고 --removal 표에서 caught
  limit → ref `경로::문구` 의 문구가 --root 아래 그 문서에 있다(측정 근거를 적은 한계)
경계 표(--boundary)는 --contract 프롬프트의 계약 항목(줄머리 `C1.` …)을 하나도 빠짐없이 covered(셀 · fixed 와 같은 근거) 또는
limit 으로 덮어야 한다 — 오라클이 계약보다 좁은 자리를 숨기지 않는다.
대상 집합은 3 과 같게 대조하지만 sha 는 지금 트리와 대조하지 않는다 — 기록은 고치기 전 판을 본 것이고, 고친 판은 셀 · 제거 probe 가
지금 트리에서 잰다(고친 diff 의 재검토는 원장이 따로 요구한다).

사용: check_adversarial_record.py RECORD --root DIR --target REL [--target REL …] [--policy strict|reachable-fail-open|dispositioned]
      [--dispositions TSV --boundary TSV --contract PROMPT --cell-out FILE … --removal TSV …]
      (exit 0 통과 · 1 거부 — 읽지 못한 기록 포함 · 2 사용법 오류)
      check_adversarial_record.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import tempfile

OK_VERDICTS = {"approved", "pass"}
BLOCKING = {"critical", "major"}
REACH_TAG = re.compile(r"^\s*\[reach:(normal|crafted)\]\s*\[dir:(fail-open|over-reject)\]")


def blob_sha(path: pathlib.Path) -> str:
    """git 의 blob 해시 — `git hash-object` 와 같은 값(git 없이 잰다)."""
    b = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def _issue_key(it) -> tuple:
    return (str(it.get("id")), str(it.get("severity") or "").lower(), str(it.get("description") or "")) if isinstance(it, dict) else ("?",)


DISP_HEAD = "id\tdisposition\tref\tnote"
BOUND_HEAD = "item\tstatus\tref"
REMOVAL_HEAD = "cell\tremoved\tresult"


def _tsv(path, head):
    """머리 줄이 head 인 TSV 의 행 — 못 읽거나 머리가 다르면 None."""
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, TypeError):
        return None
    return [x.split("\t") for x in lines[1:] if x.strip()] if lines and lines[0] == head else None


def load_evidence(root: pathlib.Path, dispositions, boundary, contract, cell_outs, removals) -> dict:
    """정책 dispositioned 의 근거 — 처분 표 · 경계 표 · 계약 항목 · self-test 출력 · 제거 probe 결과. 못 읽은 것은 errors 로 남긴다."""
    ev = {"root": root, "disp": _tsv(dispositions, DISP_HEAD), "bound": _tsv(boundary, BOUND_HEAD), "out": "", "caught": {}, "errors": []}
    try:
        ev["items"] = re.findall(r"(?m)^(C\d+)\.\s", pathlib.Path(contract).read_text(encoding="utf-8"))
    except (OSError, TypeError):
        ev["items"] = []
    for f in cell_outs or []:
        try:
            ev["out"] += pathlib.Path(f).read_text(encoding="utf-8", errors="replace") + "\n"
        except OSError:
            ev["errors"].append(f"self-test 출력 {f} 를 읽지 못했다")
    for f in removals or []:
        rows = _tsv(f, REMOVAL_HEAD)
        if rows is None:
            ev["errors"].append(f"제거 probe 표 {f} 를 읽지 못했다(머리 cell·removed·result)")
        for r in rows or []:
            ev["caught"][r[0]] = r[-1]
    return ev


def _ref_ok(kind: str, ref: str, ev: dict):
    """처분 · 경계 행의 근거가 서는가 — 못 서면 사유, 서면 None."""
    if kind in ("fixed", "covered"):
        cells = [c.strip() for c in ref.split(",") if c.strip()]
        if not cells:
            return "셀 이름이 없다"
        nopass = [c for c in cells if not re.search(rf"(?m)^(?:PASS|  ok) +{re.escape(c)}(?: |$)|^{re.escape(c)}: PASS$", ev["out"])]
        if nopass:
            return f"self-test 출력에 PASS 가 없다 {nopass}"
        uncaught = [c for c in cells if ev["caught"].get(c) != "caught"]
        if uncaught:
            return f"제거 probe 가 잡지 못했다(또는 행이 없다) {uncaught}"
        return None
    if kind == "limit":
        path, sep, needle = ref.partition("::")
        if not sep or not path.strip() or not needle.strip():
            return "한계 근거는 `경로::문구` 꼴이다"
        try:
            text = (ev["root"] / path).read_text(encoding="utf-8")
        except OSError:
            return f"한계 문서 {path} 를 읽지 못했다"
        return None if needle in text else f"한계 문서 {path} 에 그 문구가 없다"
    return f"모르는 처분 {kind!r}"


def _dispositions(issues: list, ev: dict) -> list:
    """정책 dispositioned — critical · major 마다 처분 한 행 · 경계 표가 계약 항목 전부를 덮는다."""
    probs = list(ev["errors"])
    blocking = [str(it.get("id")) for it in issues if isinstance(it, dict) and str(it.get("severity") or "").lower() in BLOCKING]
    rows = ev["disp"]
    if rows is None:
        probs.append("처분 표를 읽지 못했다(머리 id·disposition·ref·note)")
        rows = []
    seen = {}
    for r in rows:
        if len(r) != 4 or not all(x.strip() for x in r[:3]):
            probs.append(f"처분 행 꼴이 틀렸다 {r[:1]}")
        elif r[0] in seen:
            probs.append(f"처분 {r[0]} 이 두 번 있다")
        else:
            seen[r[0]] = r
    undisposed = [i for i in blocking if i not in seen]
    if undisposed:
        probs.append(f"처분 없는 critical/major {undisposed}")
    stray = [i for i in seen if i not in blocking]
    if stray:
        probs.append(f"기록의 critical/major 가 아닌 처분 {stray}")
    for i in blocking:
        if i in seen:
            why = _ref_ok(seen[i][1], seen[i][2], ev) if seen[i][1] in ("fixed", "limit") else f"처분은 fixed · limit 뿐이다({seen[i][1]!r})"
            if why:
                probs.append(f"처분 {i}({seen[i][1]}) — {why}")
    items = ev["items"]
    if not items:
        probs.append("계약 항목(줄머리 `C1.` …)을 --contract 에서 찾지 못했다")
    if ev["bound"] is None:
        probs.append("경계 표를 읽지 못했다(머리 item·status·ref)")
    have = set()
    for r in ev["bound"] or []:
        if len(r) != 3 or not all(x.strip() for x in r):
            probs.append(f"경계 행 꼴이 틀렸다 {r[:1]}")
        elif r[0] not in items:
            probs.append(f"경계 표의 {r[0]} 는 계약에 없다")
        else:
            why = _ref_ok(r[1], r[2], ev) if r[1] in ("covered", "limit") else f"경계 상태는 covered · limit 뿐이다({r[1]!r})"
            if why:
                probs.append(f"경계 {r[0]}({r[1]}) — {why}")
            else:
                have.add(r[0])
    uncovered = [x for x in items if x not in have]
    if uncovered:
        probs.append(f"경계 표가 덮지 않은 계약 항목 {uncovered}")
    return probs


def judge(rec, root: pathlib.Path, targets, policy: str = "strict", record_dir: pathlib.Path | None = None, ev: dict | None = None) -> list:
    """거부 사유 목록 — 비면 통과. 정책 dispositioned 는 `ev`(load_evidence)가 필요하다."""
    if not isinstance(rec, dict):
        return ["기록이 JSON 객체가 아니다"]
    probs = []
    disp = policy == "dispositioned"
    reach = policy == "reachable-fail-open" or disp
    if rec.get("verdict") not in OK_VERDICTS and not (reach and rec.get("verdict") == "needs_revision"):
        probs.append(f"verdict {rec.get('verdict')!r} — approved · pass 만 통과한다" + (" · 정책 reachable-fail-open 은 needs_revision 도" if reach else ""))
    issues = rec.get("issues")
    if not isinstance(issues, list):
        probs.append("issues 배열이 없다(지적이 없으면 빈 배열)")
        issues = []
    for k, it in enumerate(issues):
        if not isinstance(it, dict):
            probs.append(f"issues[{k}] 가 객체가 아니다")
            continue
        sev = str(it.get("severity") or "").lower()
        if sev in BLOCKING and not reach:
            probs.append(f"{sev} 지적 {it.get('id', k)} — 고친 뒤 다시 재검토 받은 기록이어야 한다(resolution 으로 면제하지 않는다)")
        elif sev in BLOCKING and not disp:
            m = REACH_TAG.match(str(it.get("description") or ""))
            if m is None:
                probs.append(f"{sev} 지적 {it.get('id', k)} — 도달성 · 방향 표지([reach:…][dir:…])가 없다")
            elif m.groups() == ("normal", "fail-open"):
                probs.append(f"{sev} 지적 {it.get('id', k)} — 도달 가능한 fail-open 이다(정책이 막는 유일한 꼴)")
    if reach:                # 표지는 검토자의 것이어야 한다 — 기록의 지적이 원 출력의 지적과 같은가
        src = rec.get("source")
        sp = pathlib.Path(src) if isinstance(src, str) and src else None
        if sp is not None and not sp.is_absolute():
            sp = (record_dir or pathlib.Path(".")) / sp
        try:
            orig = json.loads(sp.read_text(encoding="utf-8")) if sp is not None else None
        except (OSError, ValueError):
            orig = None
        if not isinstance(orig, dict) or not isinstance(orig.get("issues"), list):
            probs.append("source 원 출력을 읽지 못했다 — 표지가 검토자의 것인지 대조할 수 없다")
        elif [_issue_key(x) for x in orig["issues"]] != [_issue_key(x) for x in issues] or orig.get("verdict") != rec.get("verdict"):
            probs.append("기록의 지적 · verdict 가 source 원 출력과 다르다(표지 · 심각도 · 문구를 바꾸지 않는다)")
    got = {}
    ts = rec.get("targets")
    if not isinstance(ts, list) or not ts:
        probs.append("targets 배열이 없다 — 무엇을 재검토했는지 묶이지 않은 기록이다")
        ts = []
    for k, t in enumerate(ts):
        if not (isinstance(t, dict) and isinstance(t.get("path"), str) and isinstance(t.get("sha"), str)):
            probs.append(f"targets[{k}] 에 path · sha 가 없다")
        elif t["path"] in got:
            probs.append(f"targets 에 {t['path']} 가 두 번 있다")
        else:
            got[t["path"]] = t["sha"].lower()
    want = set(targets)
    miss, extra = sorted(want - set(got)), sorted(set(got) - want)
    if miss:     # F-317 — 지정 대상 일부만 덮은 재검토는 나머지 파일을 본 적이 없다
        probs.append(f"대상 집합이 다르다 — 빠짐 {miss}")
    if extra:    # 지정 밖 파일을 함께 적으면 목록이 정본(--list-instruments 등)과 갈린 것이다
        probs.append(f"대상 집합이 다르다 — 뜻밖 {extra}")
    for rel in sorted(want & set(got)):
        f = root / rel
        if not f.is_file():
            probs.append(f"{rel} 이 트리에 없다")
        elif disp:
            if not re.fullmatch(r"[0-9a-f]{40}", got[rel]):
                probs.append(f"{rel} 의 sha 꼴이 틀렸다(git blob 40자)")   # 재검토한 판의 sha — 지금 트리와 대조하지 않는다(고친 판은 셀이 잰다)
        elif blob_sha(f) != got[rel]:
            probs.append(f"{rel} 해시 불일치 — 기록 {got[rel][:12]} · 지금 {blob_sha(f)[:12]}(재검토 뒤 파일이 바뀌었다)")
    if disp:
        probs += _dispositions([x for x in issues if isinstance(x, dict)], ev) if ev is not None else \
            ["정책 dispositioned 는 --dispositions · --boundary · --contract · --cell-out · --removal 이 필요하다"]
    return probs


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        (root / "a.py").write_text("x = 1\n", encoding="utf-8")
        (root / "b.py").write_text("y = 2\n", encoding="utf-8")
        sha = blob_sha(root / "a.py")
        good = {"verdict": "approved", "targets": [{"path": "a.py", "sha": sha}], "issues": [{"id": "I2", "severity": "minor"}]}
        bad = {
            "rejected": dict(good, verdict="rejected"),
            "major-with-resolution": dict(good, issues=[{"id": "I1", "severity": "major", "status": "fixed", "resolution": "고침"}]),
            "critical": dict(good, issues=[{"id": "I1", "severity": "critical"}]),
            "file-missing": dict(good, targets=[{"path": "gone.py", "sha": sha}]),
            "stale-sha": dict(good, targets=[{"path": "a.py", "sha": blob_sha(root / "b.py")}]),
            "missing-target": dict(good, targets=[]),
            "extra-target": dict(good, targets=[{"path": "a.py", "sha": sha}, {"path": "b.py", "sha": blob_sha(root / "b.py")}]),
            "no-issues-key": {k: v for k, v in good.items() if k != "issues"},
        }
        got = {k: judge(v, root, ["gone.py" if k == "file-missing" else "a.py"]) for k, v in bad.items()}
        ok_good = judge(good, root, ["a.py"])
        case("r3-f329-adversarial-record — 판정기가 rejected · major(resolution 포함) · 해시 불일치 · 대상 누락 · 없는 파일 기록을 거부하고 닫힌 기록만 통과시킨다",
             ok_good == [] and all(got.values()), {"good": ok_good, **{k: bool(v) for k, v in got.items()}})
        sb = blob_sha(root / "b.py")
        both = dict(good, targets=[{"path": "a.py", "sha": sha}, {"path": "b.py", "sha": sb}])
        extra = judge(both, root, ["a.py"])
        case("r3-adv-target-set-exact — 지정 대상과 정확히 같은 집합만 통과 · 지정 밖 파일을 함께 적은 기록은 거부",
             judge(both, root, ["a.py", "b.py"]) == [] and any("뜻밖" in x and "b.py" in x for x in extra), extra)
        part = judge(good, root, ["a.py", "b.py"])
        case("r3-f317-partial-target-coverage-fails — 지정 대상 일부만 덮은 기록은 실패(나머지 파일을 재검토하지 않았다)",
             any("빠짐" in x and "b.py" in x for x in part), part)
        rec = root / "rec.json"
        rec.write_text(json.dumps(good), encoding="utf-8")
        broken = root / "broken.json"
        broken.write_text('{"verdict": "approved", ', encoding="utf-8")
        rc = [main([str(rec), "--root", t, "--target", "a.py"]), main([str(rec), "--root", t, "--target", "b.py"]),
              main([str(broken), "--root", t, "--target", "a.py"]), main([str(root / "none.json"), "--root", t, "--target", "a.py"])]
        case("adversarial-record-cli-exit — 통과 0 · 거부 1 · 깨진 JSON · 없는 기록도 traceback 없이 1", rc == [0, 1, 1, 1], rc)
        # 정책 reachable-fail-open — 표지(검토자)로 도달 가능한 fail-open 만 막는다 · 표지 없음 · 원 출력과 다른 기록 · rejected 는 막는다
        def tagged(reach_, dir_, sev="major"):
            return {"id": "I1", "severity": sev, "description": f"[reach:{reach_}][dir:{dir_}] x"}
        src = root / "src.json"

        def pol(issues, verdict="needs_revision", source_issues=None):
            src.write_text(json.dumps({"verdict": verdict, "issues": issues if source_issues is None else source_issues}), encoding="utf-8")
            r = dict(good, verdict=verdict, issues=issues, source="src.json")
            return judge(r, root, ["a.py"], "reachable-fail-open", root)
        res = {"crafted-open": pol([tagged("crafted", "fail-open")]), "normal-over": pol([tagged("normal", "over-reject")]),
               "normal-open": pol([tagged("normal", "fail-open")]), "no-tag": pol([{"id": "I1", "severity": "major", "description": "x"}]),
               "relabeled": pol([tagged("crafted", "fail-open")], source_issues=[tagged("normal", "fail-open")]),
               "rejected": pol([tagged("crafted", "fail-open")], verdict="rejected"),
               "strict-default": judge(dict(good, verdict="needs_revision", issues=[tagged("crafted", "fail-open")]), root, ["a.py"])}
        case("r3-s1-adv-policy-reachable — 정책 reachable-fail-open: 도달 불가 · 과잉 거부 major 는 통과 · 도달 가능 fail-open · 표지 없음 · "
             "원 출력과 다른 표지 · rejected 는 거부 · 기본 정책은 그대로 major 를 거부",
             res["crafted-open"] == [] and res["normal-over"] == [] and all(res[k] for k in ("normal-open", "no-tag", "relabeled", "rejected", "strict-default")),
             {k: len(v) for k, v in res.items()})
        # 정책 dispositioned — 지적마다 처분(fixed = 셀 PASS + 제거 잡힘 · limit = 한계 문구) · 경계 표가 계약 항목 전부를 덮는다
        (root / "limits.md").write_text("## 한계\n- LIMIT-TEXT-X 측정 근거 35/101\n", encoding="utf-8")
        (root / "contract.md").write_text("C1. 하나\n  C9. 들여 쓴 것은 항목이 아니다\nC2. 둘\n", encoding="utf-8")
        (root / "o0").write_text("PASS cell-a — x\n  ok   cell-b\ncell-c: PASS\nFAIL cell-d — y\nPASS cell-e — z\n", encoding="utf-8")
        (root / "rm.tsv").write_text(REMOVAL_HEAD + "\ncell-a\tr\tcaught\ncell-b\tr\tcaught\ncell-c\tr\tcaught\ncell-d\tr\tcaught\ncell-e\tr\tnot-caught\n",
                                     encoding="utf-8")
        majors = [tagged("crafted", "fail-open"), dict(tagged("normal", "fail-open"), id="I2"), {"id": "I3", "severity": "minor"}]
        D_OK = [("I1", "fixed", "cell-a,cell-b"), ("I2", "limit", "limits.md::LIMIT-TEXT-X")]
        B_OK = [("C1", "covered", "cell-c"), ("C2", "limit", "limits.md::LIMIT-TEXT-X")]

        def dis(drows=D_OK, brows=B_OK, verdict="needs_revision", targets=None, source_issues=None, contract="contract.md"):
            (root / "d.tsv").write_text("\n".join([DISP_HEAD] + ["\t".join(r) + "\tn" for r in drows]) + "\n", encoding="utf-8")
            (root / "b.tsv").write_text("\n".join([BOUND_HEAD] + ["\t".join(r) for r in brows]) + "\n", encoding="utf-8")
            src.write_text(json.dumps({"verdict": verdict, "issues": majors if source_issues is None else source_issues}), encoding="utf-8")
            r = dict(good, verdict=verdict, issues=majors, source="src.json", targets=[{"path": "a.py", "sha": blob_sha(root / "b.py")}])
            ev = load_evidence(root, root / "d.tsv", root / "b.tsv", root / contract, [root / "o0"], [root / "rm.tsv"])
            return judge(r, root, targets or ["a.py"], "dispositioned", root, ev)
        base_ok = dis()
        case("r3-adv-dispositioned-every-major — critical/major 마다 처분 한 행(빠짐 · 기록 밖 처분 거부) · 표지 · 지금 sha 는 따지지 않는다 · "
             "원 출력과 다른 기록 · rejected · 대상 집합 다름 · 근거 없는 호출은 거부",
             base_ok == [] and all((dis(drows=D_OK[:1]), dis(drows=D_OK + [("I9", "limit", "limits.md::LIMIT-TEXT-X")]),
                                    dis(drows=D_OK + [("I3", "limit", "limits.md::LIMIT-TEXT-X")]), dis(verdict="rejected"),
                                    dis(source_issues=majors[:2]), dis(targets=["a.py", "b.py"]),
                                    judge(dict(good, verdict="needs_revision", issues=majors), root, ["a.py"], "dispositioned"))),
             base_ok)
        nopass = [dis(drows=[("I1", "fixed", "cell-a,cell-d"), D_OK[1]]), dis(drows=[("I1", "fixed", "cell-zz"), D_OK[1]])]
        case("r3-adv-dispositioned-cell-pass — fixed 의 셀은 같은 CHECK 의 self-test 출력에서 PASS 여야 한다(FAIL · 없는 셀 거부)",
             all(any("PASS 가 없다" in x for x in p) for p in nopass), nopass)
        unc = dis(drows=[("I1", "fixed", "cell-a,cell-e"), D_OK[1]])
        case("r3-adv-dispositioned-removal-caught — fixed 의 셀은 제거 probe 가 잡아야 한다(not-caught 거부)",
             any("제거 probe" in x and "cell-e" in x for x in unc), unc)
        lim = [dis(drows=[D_OK[0], ("I2", "limit", "limits.md::없는 문구")]), dis(drows=[D_OK[0], ("I2", "limit", "limits.md")]),
               dis(drows=[D_OK[0], ("I2", "limit", "none.md::LIMIT-TEXT-X")])]
        case("r3-adv-dispositioned-limit-text — limit 은 한계 문서에 그 문구가 있어야 한다(없는 문구 · 꼴 틀림 · 없는 문서 거부)",
             all(lim), lim)
        bnd = [dis(brows=B_OK[:1]), dis(brows=B_OK + [("C9", "covered", "cell-c")]), dis(brows=[("C1", "covered", "cell-d"), B_OK[1]]),
               dis(contract="limits.md")]
        case("r3-adv-dispositioned-boundary — 경계 표가 계약 항목(줄머리 C1. …)을 전부 덮어야 한다(빠짐 · 계약 밖 항목 · 근거 없는 covered · 항목 없는 계약 거부)",
             all(any("경계" in x or "계약" in x for x in p) for p in bnd), bnd)
    print(f"check_adversarial_record self-test {sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("record", nargs="?")
    ap.add_argument("--root", default=".")
    ap.add_argument("--target", action="append", default=[])
    ap.add_argument("--policy", choices=("strict", "reachable-fail-open", "dispositioned"), default="strict")
    ap.add_argument("--dispositions")
    ap.add_argument("--boundary")
    ap.add_argument("--contract")
    ap.add_argument("--cell-out", action="append", default=[])
    ap.add_argument("--removal", action="append", default=[])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.record or not a.target:
        ap.error("RECORD 와 --target 하나 이상이 필요하다")
    if a.policy == "dispositioned" and not (a.dispositions and a.boundary and a.contract and a.cell_out and a.removal):
        ap.error("정책 dispositioned 는 --dispositions · --boundary · --contract · --cell-out · --removal 이 필요하다")
    try:
        rec = json.loads(pathlib.Path(a.record).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"REJECT 기록을 읽지 못했다 {a.record}: {type(e).__name__}")   # 못 읽은 기록은 통과가 아니다
        return 1
    ev = load_evidence(pathlib.Path(a.root), a.dispositions, a.boundary, a.contract, a.cell_out, a.removal) if a.policy == "dispositioned" else None
    probs = judge(rec, pathlib.Path(a.root), a.target, a.policy, pathlib.Path(a.record).resolve().parent, ev)
    for p in probs:
        print(f"REJECT {p}")
    if not probs:
        print(f"OK 적대 재검토 기록 — 대상 {len(a.target)} · "
              + ("해시 일치 · 열린 critical/major 0" if a.policy == "strict" else
                 "해시 일치 · 도달 가능한 fail-open 0(정책 reachable-fail-open · 표지는 원 출력과 같다)" if a.policy == "reachable-fail-open" else
                 f"critical/major {len(ev['disp'] or [])} 처분(셀 PASS · 제거 잡힘 · 한계 문구) · 계약 항목 {len(ev['items'])} 경계 덮음"))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
