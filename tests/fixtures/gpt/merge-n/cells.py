#!/usr/bin/env python3
"""merge-n fixture — scripts/gpt_merge.py through its CLI: multiset kept, groups, contested · unlocated · minority, stale and
head-mismatch rejects, unavailable arms, order invariance, channel namespaces, blind pack round trip, and the review_merge
inflow guard (XE-26). Cell lines: `PASS  [<id>] <text>` / `FAIL  [<id>] <text>`. exit 0 all pass · 1 a cell failed · 3 setup.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.realpath(os.path.join(HERE, "..", "..", "..", ".."))
GM = os.path.join(R, "scripts", "gpt_merge.py")
RMG = os.path.join(R, "scripts", "review_merge.py")
FAILED = []
DIFF = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n-x = 1\n+x = 2\n y = 3\n-z = 4\n+z = 5\n")


def check(cid, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  [{cid}] {detail}"[:400])
    if not ok:
        FAILED.append(cid)


def issue(i, sev="major", line="1", axis="logic", ev="`x = 2`"):
    return {"id": i, "severity": sev, "file": "a.py", "line_range": line, "discoveryAxis": axis, "title": f"t {i}", "detail": "d", "evidence": ev}


class W:
    def __init__(self):
        self.t = tempfile.mkdtemp(prefix="fz-merge-n.")
        self.diff = os.path.join(self.t, "d.patch")
        open(self.diff, "w").write(DIFF)
        self.sha = hashlib.sha256(DIFF.encode()).hexdigest()
        self.n = 0

    def doc(self, issues, craft=None):
        self.n += 1
        p = os.path.join(self.t, f"in{self.n}.json")
        json.dump({"verdict": "needs_work", "issues": issues, "craft": craft or []}, open(p, "w"))
        return p

    def label(self, run, frame="-", kind="independent-review", sha=None):
        return f"{kind},{frame},{run},sess-{run},-,{sha or self.sha}"

    def merge(self, pairs, unavailable=()):
        self.n += 1
        out = os.path.join(self.t, f"m{self.n}.json")
        argv = [sys.executable, GM, "--diff", self.diff, "--out", out]
        for p, l in pairs:
            argv += ["--in", p, "--label", l]
        for l, r in unavailable:
            argv += ["--unavailable", l, r]
        rc = subprocess.run(argv, capture_output=True, text=True).returncode
        return rc, (json.load(open(out)) if os.path.exists(out) else None), out


def cells(w):
    rc, m, _ = w.merge([(w.doc([issue("I-1")]), w.label("r1"))])
    check("one", rc == 0 and len(m["candidates"]) == 1 and len(m["groups"]) == 1, f"rc={rc}")

    a, b, c = w.doc([issue("I-1")]), w.doc([issue("I-7", line="1-2")]), w.doc([issue("I-3", line="1")])
    rc, m, _ = w.merge([(a, w.label("r1")), (b, w.label("r2", "falsify")), (c, w.label("r3", "repro"))])
    g = m["groups"] if m else []
    check("n3-one-group", rc == 0 and len(g) == 1 and len(g[0]["members"]) == 3 and len(g[0]["sources"]) == 3, f"groups={len(g)}")
    check("true-duplicate", rc == 0 and len(g) == 1 and not g[0]["minority"], "two frames at one place -> one group, not minority")

    rc, m, _ = w.merge([(w.doc([issue("I-1", "major")]), w.label("r1")), (w.doc([issue("I-1", "minor")]), w.label("r2"))])
    g = m["groups"][0] if m else {}
    sev = sorted(x["severity"] for x in m["candidates"]) if m else []
    check("contested", rc == 0 and g.get("contested") is True and g.get("severity") is None and sev == ["major", "minor"], f"sev={sev}")

    rc, m, _ = w.merge([(w.doc([issue("I-1"), issue("I-2", line="")]), w.label("r1"))])
    un = [g for g in m["groups"] if g["unlocated"]] if m else []
    check("unlocated", rc == 0 and len(un) == 1 and un[0]["members"] == ["gpt:independent-review:-:r1:defect:I-2"], f"unlocated={len(un)}")

    rc, m, out = w.merge([(w.doc([issue("I-1")]), w.label("r1", sha="0" * 64))])
    check("stale-reject", rc == 1 and not os.path.exists(out), f"rc={rc}")

    d1 = w.doc([issue("I-1")])
    rc, m, out = w.merge([(d1, w.label("r1") + ":head-A"), (w.doc([issue("I-1")]), w.label("r2") + ":head-B")])
    check("head-mismatch-reject", rc == 1 and not os.path.exists(out), f"rc={rc}")

    rc, m, _ = w.merge([(w.doc([issue("I-1")]), w.label("r1")), (w.doc([issue("I-4")]), w.label("r2"))],
                       unavailable=[(w.label("r3", "falsify"), "exit 12 — usage limit")])
    check("unavailable-recorded", rc == 0 and m["summary"]["unavailable"] == 1 and m["unavailable"][0]["reason"] == "exit 12 — usage limit"
          and m["unavailable"][0]["label"]["frame"] == "falsify" and m["summary"]["inputs"] == 2, f"rc={rc}")

    p1 = w.doc([issue("I-1"), issue("I-5", line="3", ev="`z = 5`")])
    p2 = w.doc([issue("I-6", line="3", ev="`z = 5`"), issue("I-8", line="")])
    l1, l2 = w.label("r1"), w.label("r2", "falsify")
    _, m1, _ = w.merge([(p1, l1), (p2, l2)])
    _, m2, _ = w.merge([(p2, l2), (p1, l1)])
    norm = lambda m: sorted(sorted(g["members"]) for g in m["groups"])
    check("order-invariant", m1 and m2 and norm(m1) == norm(m2), f"groups={len(m1['groups']) if m1 else None}")

    d = w.doc([issue("I-1")], craft=[{"id": "I-1", "craftAxis": "naming", "severity": "minor", "file": "a.py", "line_range": "1",
                                     "title": "c", "detail": "d", "evidence": "`x = 2`"}])
    rc, m, _ = w.merge([(d, w.label("r1"))])
    ids = sorted(x["id"] for x in m["candidates"]) if m else []
    check("channel-namespace", ids == ["gpt:independent-review:-:r1:craft:I-1", "gpt:independent-review:-:r1:defect:I-1"]
          and len(m["groups"]) == 2 and all(x["originalId"] == "I-1" for x in m["candidates"]), f"ids={ids}")

    mix = [(w.doc([issue("I-1"), issue("I-2", line=""), issue("I-3", line="3", ev="`z = 5`")]), w.label("r1")),
           (w.doc([issue("I-1", "minor"), issue("I-9", ev="`nowhere`")]), w.label("r2", "falsify"))]
    rc, m, mp = w.merge(mix)
    want = sorted(f"gpt:independent-review:{l.split(',')[1]}:{l.split(',')[2]}:defect:{i['id']}"
                  for p, l in mix for i in json.load(open(p))["issues"])
    got = sorted(x["id"] for x in m["candidates"])
    in_groups = sorted(x for g in m["groups"] for x in g["members"])
    check("multiset-equal", rc == 0 and want == got == in_groups, f"in={len(want)} out={len(got)} grouped={len(in_groups)}")
    keys = {"call_kind", "frame", "run", "session", "lens", "inputs_sha", "source"}
    check("provenance-fields", all(set(x["provenance"]) == keys and x["provenance"]["session"].startswith("sess-") for x in m["candidates"]),
          str(sorted(m["candidates"][0]["provenance"])))

    bd = os.path.join(w.t, "blind")
    rc1 = subprocess.run([sys.executable, GM, "--blind-pack", mp, "--out-dir", bd, "--seed", "7"], capture_output=True, text=True).returncode
    pack = json.load(open(os.path.join(bd, "pack.json")))["candidates"]
    leak = [r for r in pack if any(k in r for k in ("id", "provenance", "frame", "run"))]
    holds = [x for x in m["candidates"] if x["hold"]]
    key = json.load(open(os.path.join(bd, "key.json")))["key"]
    check("hold-in-blind", bool(holds) and all(h["id"] in key.values() for h in holds) and not leak, f"holds={len(holds)} leak={len(leak)}")
    verdicts = {r["bid"]: {"label": "valid", "severity": "major"} for r in pack}
    vp = os.path.join(w.t, "v.json")
    json.dump(verdicts, open(vp, "w"))
    jp = os.path.join(w.t, "judged.json")
    rc2 = subprocess.run([sys.executable, GM, "--blind-unpack", bd, "--verdicts", vp, "--out", jp], capture_output=True, text=True).returncode
    judged = json.load(open(jp))["judged"] if os.path.exists(jp) else []
    json.dump(dict(list(verdicts.items())[1:]), open(vp, "w"))
    rc3 = subprocess.run([sys.executable, GM, "--blind-unpack", bd, "--verdicts", vp, "--out", jp + ".2"], capture_output=True, text=True).returncode
    check("blind-roundtrip", rc1 == rc2 == 0 and sorted(j["id"] for j in judged) == got and all(j["provenance"] for j in judged) and rc3 == 1,
          f"pack={rc1} unpack={rc2} incomplete={rc3}")

    check("pack-group", all(r.get("group") for r in pack), "every pack row carries its location group id (no label, no source)")

    def audited(doc, frame=None, snap="aa"):
        a = {"exit": 0, "isolationApplied": True, "frame": frame, "inputs": {"diff.patch": w.sha, "snapshot/s/": snap}}
        json.dump(a, open(doc[:-5] + ".audit.json", "w"))
        return doc
    rc, _, _ = w.merge([(audited(w.doc([issue("I-1")]), frame="falsify"), w.label("r1"))])
    check("audit-frame", rc == 1, f"label frame '-' vs audit falsify -> rc={rc}")
    rc, _, _ = w.merge([(audited(w.doc([issue("I-1")])), w.label("r1")), (audited(w.doc([issue("I-2")]), snap="bb"), w.label("r2"))])
    rc2, _, _ = w.merge([(audited(w.doc([issue("I-1")])), w.label("r1")), (audited(w.doc([issue("I-2")])), w.label("r2"))])
    check("audit-inputs", rc == 1 and rc2 == 0, f"snapshot hashes differ -> rc={rc} · same -> rc={rc2}")
    hd = w.doc([issue("I-1")])
    a = {"exit": 0, "isolationApplied": True, "frame": None, "inputs": {"diff.patch": w.sha, "head/": "h" * 64}}
    json.dump(a, open(hd[:-5] + ".audit.json", "w"))
    rc, _, _ = w.merge([(hd, w.label("r1"))])
    rc2, _, _ = w.merge([(hd, w.label("r1", sha=w.sha + ":" + "h" * 64))])
    check("audit-head", rc == 1 and rc2 == 0, f"audit has head/, label omits it -> rc={rc} · label carries it -> rc={rc2}")

    # S12 order (plan): merge -> blind-pack -> grade -> blind-unpack -> decide, through the CLIs
    arms = [("A0", 1, "-", [issue("I-1")]), ("A0", 2, "-", [issue("I-1")]),
            ("A2", 1, "falsify", [issue("I-1"), issue("I-3", line="3", ev="`z = 5`")]), ("A2", 2, "falsify", [issue("I-3", line="3", ev="`z = 5`")])]
    pairs = [(w.doc(iss), w.label(f"{arm.lower()}r{rep}", fr)) for arm, rep, fr, iss in arms]
    rc, cm, cmp_ = w.merge(pairs)
    cd = os.path.join(w.t, "chain")
    subprocess.run([sys.executable, GM, "--blind-pack", cmp_, "--out-dir", cd, "--seed", "3"], capture_output=True, text=True)
    cpack = json.load(open(os.path.join(cd, "pack.json")))["candidates"]
    cv = os.path.join(w.t, "cv.json")
    json.dump({r["bid"]: {"label": "valid", "severity": "major", "canonical": r["group"]} for r in cpack}, open(cv, "w"))
    cj = os.path.join(w.t, "cj.json")
    subprocess.run([sys.executable, GM, "--blind-unpack", cd, "--verdicts", cv, "--out", cj], capture_output=True, text=True)
    th = {k: {"value": v, "status": "approved"} for k, v in (("delta_keep", 1), ("positive_share", "2/3"), ("fp_keep", 0.15),
                                                           ("fp_rollback", 0.3), ("tokens_ratio", 1.5), ("fail_max", 0.1))}
    pp = os.path.join(w.t, "prereg.json")
    json.dump({"n_min": 1, "n_max": 12, "instrument_sha": "abc1234", "thresholds": th}, open(pp, "w"))
    psha = hashlib.sha256(open(pp, "rb").read()).hexdigest()
    log = os.path.join(w.t, "log.md")
    open(log, "w").write(f"| prereg_sha256 | approved_by | time | instrument |\n|---|---|---|---|\n| {psha} | user | 2026-10-20T00:00:00Z | abc1234 |\n")
    runs = os.path.join(w.t, "runs.jsonl")
    with open(runs, "w") as fh:
        for (arm, rep, fr, _), (_, lab) in zip(arms, pairs):
            run = lab.split(",")[2]
            ids = [c["id"] for c in cm["candidates"] if c["provenance"]["run"] == run]
            fh.write(json.dumps({"task": "t", "arm": arm, "rep": rep, "exit": 0, "spawnAgent": 0, "tokens": 100, "model": "m", "effort": "xhigh",
                                 "cli": "c", "config_sha_normalized": "n", "candidates": ids, "started": "2026-10-21T00:00:00Z",
                                 "prereg_sha256": psha, "instrument_sha": "abc1234"}) + "\n")
    out = os.path.join(w.t, "decision.json")
    dec = subprocess.run([sys.executable, os.path.join(R, "scripts", "gpt_ab_decide.py"), "decide", "--prereg", pp, "--log", log, "--runs", runs,
                          "--verdicts", cj, "--out", out], capture_output=True, text=True)
    d = json.load(open(out)) if os.path.exists(out) else {}
    check("unpack-decide-chain", rc == 0 and dec.returncode == 0 and d.get("decision") == "KEEP" and d["metrics"]["mean_delta"] == 1,
          f"decide rc={dec.returncode} {d.get('decision')} meanΔ={(d.get('metrics') or {}).get('mean_delta')} {dec.stderr.strip()[:120]}")

    cl = os.path.join(w.t, "claude.json")
    json.dump({"issues": []}, open(cl, "w"))
    ok_gpt = w.doc([issue("I-1")])
    base = [sys.executable, RMG, "--claude", cl, "--diff", w.diff, "--gpt"]
    pos = subprocess.run(base + [ok_gpt], capture_output=True, text=True).returncode
    neg = subprocess.run(base + [mp], capture_output=True, text=True)
    check("review-merge-rejects", pos == 0 and neg.returncode != 0, f"plain GPT input rc={pos} · gpt_merge output rc={neg.returncode}")


def main():
    w = W()
    try:
        cells(w)
    except Exception as e:   # noqa: BLE001 — a crash is a setup failure, not a verdict
        print(f"SETUP merge-n: {type(e).__name__}: {e}")
        return 3
    finally:
        shutil.rmtree(w.t, ignore_errors=True)
    print("merge-n: 전건 통과" if not FAILED else f"merge-n: FAIL {FAILED}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
