#!/usr/bin/env python3
# lint:no-root-anchor — every input (prereg · runs · verdicts · log) is a path argument; the self-test writes only to a temp dir
"""GPT multi-angle measurement (E1) — metrics, the keep/defer/rollback decision, and the freeze check.

The decision function and its thresholds are fixed before the first measurement (plan S11): thresholds come only from an
approved prereg; the prereg's sha256 is frozen in experiment-log's GPT section. This script never changes a default — KEEP
is only the right to propose a promotion (separate plan, user approval).

usage:
  gpt_ab_decide.py decide --prereg P --log EXPERIMENT_LOG --runs RUNS.jsonl --verdicts JUDGED.json [--verdicts ...]
                          [--frame-arm A2|A3|A4] --out DECISION.json
  gpt_ab_decide.py verify-freeze --prereg P --log EXPERIMENT_LOG [--runs RUNS.jsonl]
  gpt_ab_decide.py --self-test

runs.jsonl (one arm run per line): task · arm (A0 · A2 · A3 · A4) · rep · exit · spawnAgent · spawnedRoles · childResults ·
  children [{model, effort}] · model · effort · cli · config_sha_normalized · config_sha_raw · tokens · candidates [ids] ·
  started (ISO with a zone) · prereg_sha256 · instrument_sha · merge_loss (task-level, optional) · critical_regressions
  (optional). spawnAgent / tokens '?' (S6: the rollout could not be read) or missing make the run unmeasured — never 0.
  A rerun of the same (task, arm, rep) is allowed once and only after a run that was not ok.
verdicts: gpt_merge --blind-unpack output (schema gpt-merge-judged/1) — one file per pack, several --verdicts are joined.
  Every candidate of an ok run needs a verdict {label: valid | FP | dup | craft, severity, canonical}. A dup counts for its
  canonical class when that class has a valid critical/major member, whichever copy the grader saw first.

Decision (Z-14): 0 INVALID — prereg or instrument SHA differs from the runs. Per task, arms whose model · effort · CLI ·
  normalized config differ make that task invalid (excluded, counted — DEVIATION: Z-14 0 names this INVALID). 1 n_valid <
  n_min -> DEFER. 2 ROLLBACK if meanΔ <= 0 or FP_F - FP_A0 > fp_rollback. 3 KEEP if meanΔ >= delta_keep · positive tasks
  >= ceil(positive_share x n_valid) · FP_F - FP_A0 <= fp_keep · median tokens_F <= tokens_ratio x A0 · failure_F <=
  fail_max · merge loss 0 · critical regressions 0. 4 otherwise DEFER. Δ(t,F) = mean_r |V(A0,r) ∪ V(F,r)| - |V(A0,1) ∪
  V(A0,2)| over verified critical/major. FP compares only the tasks that were compared. A threshold is a number or an
  exact fraction 'a/b' (2/3 is not 0.667 — ceil(0.667 x 6) is 5, ceil(2/3 x 6) is 4).
exit: 0 decided / freeze ok · 1 rejected input (unapproved or constant-noise prereg, freeze mismatch, bad runs, unknown or
  incomplete verdicts, more tasks than n_max) · 2 usage
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import sys
import tempfile
from fractions import Fraction

THRESH = ("delta_keep", "positive_share", "fp_keep", "fp_rollback", "tokens_ratio", "fail_max")
LENSES = {"fz-review-arch": "arch", "fz-review-quality": "quality"}
SEV = ("critical", "major")


class Bad(Exception):
    pass


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def num(v):
    """A threshold value: a number or an exact fraction string 'a/b'."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return Fraction(str(v))
    if isinstance(v, str) and re.fullmatch(r"\d+/[1-9]\d*", v):
        return Fraction(v)
    raise ValueError(v)


def load_prereg(p):
    d = json.load(open(p, encoding="utf-8"))
    for k in ("noise_floor", "noise", "N_noise"):
        if k in d or k in (d.get("thresholds") or {}):
            raise Bad(f"prereg sets a noise constant ({k}) — noise is measured per task (A0r1 vs A0r2), never a constant (SC-14)")
    th = d.get("thresholds") or {}
    out = {}
    for k in THRESH:
        v = th.get(k)
        try:
            if not isinstance(v, dict) or v.get("status") != "approved":
                raise ValueError(k)
            out[k] = num(v.get("value"))
        except ValueError:
            raise Bad(f"threshold {k} is not user-approved (status approved with a number or 'a/b') — no measurement before the freeze")
    if not isinstance(d.get("n_min"), int) or not isinstance(d.get("n_max"), int):
        raise Bad("prereg needs integer n_min and n_max")
    if not re.fullmatch(r"[0-9a-f]{7,40}", str(d.get("instrument_sha") or "")):
        raise Bad("prereg needs instrument_sha (the user's commit of the instruments) — without it the SHA guard compares nothing")
    return d, out


def load_verdicts(docs):
    """[gpt-merge-judged/1 docs] -> {candidate id: verdict}. An unknown shape is rejected, not read as 'no verdicts'."""
    out = {}
    for doc in docs:
        if not (isinstance(doc, dict) and doc.get("schema") == "gpt-merge-judged/1" and isinstance(doc.get("judged"), list)):
            raise Bad("verdicts must be gpt_merge --blind-unpack output (schema gpt-merge-judged/1)")
        for row in doc["judged"]:
            if not isinstance(row, dict) or not row.get("id") or not isinstance(row.get("verdict"), dict):
                raise Bad(f"a judged row without id or verdict: {str(row)[:80]}")
            if row["id"] in out:
                raise Bad(f"candidate {row['id']} judged twice across --verdicts files")
            out[row["id"]] = row["verdict"]
    return out


def run_state(r):
    """-> ok | failed | killed | unmeasured | contaminated | invalid-a4.
    failed/killed/invalid-a4 count toward the failure rate, never as zero findings; unmeasured is a gap of the instruments."""
    e = r.get("exit")
    if e != 0:
        return "failed" if isinstance(e, int) and 10 <= e <= 17 else "killed"
    sp, tok = r.get("spawnAgent"), r.get("tokens")
    if type(sp) is not int or type(tok) not in (int, float):
        return "unmeasured"
    if r["arm"] == "A4":
        roles = sorted(LENSES.get(x, "?") for x in (r.get("spawnedRoles") or []))
        kids = r.get("children") or []
        if roles != ["arch", "quality"] or r.get("childResults") != 2 or len(kids) != 2 or not all(k.get("model") and k.get("effort") for k in kids):
            return "invalid-a4"
        return "ok"
    return "contaminated" if sp > 0 else "ok"


def valid_classes(runs, verdicts):
    """Classes with a valid critical/major member among these runs' candidates. Per task — canonical labels (e.g. a merge's
    group id g1) restart in every pack, so a class of one task must not resolve a dup of another."""
    out = set()
    for r in runs:
        for cid in r.get("candidates") or []:
            v = verdicts[cid]
            if v.get("label") == "valid" and v.get("severity") in SEV:
                out.add(v.get("canonical") or cid)
    return out


def vset(r, verdicts, valid):
    out = set()
    for cid in r.get("candidates") or []:
        v = verdicts[cid]
        if v.get("label") == "valid" and v.get("severity") in SEV:
            out.add(v.get("canonical") or cid)
        elif v.get("label") == "dup" and v.get("canonical") in valid:
            out.add(v["canonical"])
    return out


def fp_rate(runs, verdicts):
    defect = [verdicts[c] for r in runs for c in (r.get("candidates") or [])]
    defect = [v for v in defect if v.get("label") != "craft"]
    return (sum(1 for v in defect if v.get("label") == "FP") / len(defect)) if defect else 0.0


def pick(rows):
    """One row per (task, arm, rep): a rerun is allowed once, after a run that was not ok (order by started)."""
    key = f"{rows[0]['task']}/{rows[0]['arm']}/{rows[0]['rep']}"
    if len(rows) > 2:
        raise Bad(f"{key}: {len(rows)} rows — one rerun at most")
    if len(rows) == 2:
        first, second = sorted(rows, key=lambda r: when(r.get("started"), f"{key} rerun started"))
        if run_state(first) == "ok":
            raise Bad(f"{key}: a rerun after an ok run — only a run that was not ok may be rerun")
        return [second, first]
    return rows


def compute(prereg_path, runs, verdicts, frame_arm="A2"):
    pre, th = load_prereg(prereg_path)
    psha = sha(prereg_path)
    for r in runs:
        if r.get("prereg_sha256") != psha or r.get("instrument_sha") != pre.get("instrument_sha"):
            return {"decision": "INVALID", "reason": f"run {r.get('task')}/{r.get('arm')}/{r.get('rep')}: prereg or instrument SHA differs"}, th, pre
    keyed = {}
    for r in runs:
        keyed.setdefault((r["task"], r["arm"], r["rep"]), []).append(r)
    tasks, excluded, states = {}, {}, {}
    for k, rows in sorted(keyed.items(), key=lambda kv: str(kv[0])):
        chosen = pick(rows)
        tasks.setdefault(k[0], []).append(chosen[0])
        for r in rows:
            states.setdefault(k[1], []).append(run_state(r))
    if len(tasks) > pre["n_max"]:
        raise Bad(f"{len(tasks)} tasks > n_max {pre['n_max']} — collecting past the preregistered maximum is optional stopping")
    missing = sorted({c for rs in tasks.values() for r in rs if run_state(r) == "ok" for c in (r.get("candidates") or []) if c not in verdicts})
    if missing:
        raise Bad(f"verdicts incomplete — {len(missing)} candidate(s) of ok runs not judged: {missing[:3]}")
    per = []
    for t, rs in sorted(tasks.items()):
        ok = [r for r in rs if run_state(r) == "ok"]
        valid = valid_classes(ok, verdicts)
        V = lambda r, valid=valid: vset(r, verdicts, valid)
        if len({(r.get("model"), r.get("effort"), r.get("cli"), r.get("config_sha_normalized")) for r in ok}) > 1:
            excluded[t] = "arm settings differ (model · effort · CLI · normalized config)"
            continue
        a0 = {r["rep"]: r for r in ok if r["arm"] == "A0"}
        fr = {r["rep"]: r for r in ok if r["arm"] == frame_arm}
        if set(a0) != {1, 2} or not fr or not set(fr) <= {1, 2}:
            excluded[t] = "missing A0r1 · A0r2 or frame runs"
            continue
        base = len(V(a0[1]) | V(a0[2]))
        delta = statistics.mean(len(V(a0[k]) | V(fr[k])) for k in sorted(fr)) - base
        per.append({"task": t, "delta": delta, "noise": (len(V(a0[1]) - V(a0[2])) + len(V(a0[2]) - V(a0[1]))) / 2,
                    "merge_loss": max(int(r.get("merge_loss") or 0) for r in rs), "critical_regressions": max(int(r.get("critical_regressions") or 0) for r in rs),
                    "tokens_a0": statistics.median([r["tokens"] for r in a0.values()]), "tokens_f": statistics.median([r["tokens"] for r in fr.values()])})
    compared = {p["task"] for p in per}
    fail = lambda arm: (sum(s in ("failed", "killed", "invalid-a4") for s in states.get(arm, [])) / len(states[arm])) if states.get(arm) else 0.0
    ok_runs = lambda arm: [r for t in compared for r in tasks[t] if r["arm"] == arm and run_state(r) == "ok"]
    m = {"n_valid": len(per), "per_task": per, "excluded": excluded, "frame_arm": frame_arm,
         "unmeasured": sum(s == "unmeasured" for ss in states.values() for s in ss),
         "mean_delta": statistics.mean(p["delta"] for p in per) if per else 0.0,
         "positive": sum(1 for p in per if p["delta"] > 0),
         "fp_diff": fp_rate(ok_runs(frame_arm), verdicts) - fp_rate(ok_runs("A0"), verdicts),
         "tokens_ratio": (statistics.median(p["tokens_f"] for p in per) / statistics.median(p["tokens_a0"] for p in per)) if per else 0.0,
         "fail_f": fail(frame_arm), "merge_loss": sum(p["merge_loss"] for p in per), "critical_regressions": sum(p["critical_regressions"] for p in per)}
    return m, th, pre


def decide_metrics(m, th, n_min):
    if m.get("decision") == "INVALID":
        return "INVALID", [m["reason"]]
    n = m["n_valid"]
    if n < n_min:
        return "DEFER", [f"n_valid {n} < n_min {n_min}"]
    if m["mean_delta"] <= 0 or m["fp_diff"] > th["fp_rollback"] + 1e-12:
        return "ROLLBACK", [f"meanΔ {m['mean_delta']:.3f} <= 0" if m["mean_delta"] <= 0 else f"FP diff {m['fp_diff']:.3f} > {float(th['fp_rollback'])}"]
    need = math.ceil(Fraction(th["positive_share"]) * n)
    checks = [("meanΔ", m["mean_delta"] >= th["delta_keep"] - 1e-12), (f"positive {m['positive']}/{n} >= {need}", m["positive"] >= need),
              ("FP diff", m["fp_diff"] <= th["fp_keep"] + 1e-12), ("tokens", m["tokens_ratio"] <= th["tokens_ratio"] + 1e-12),
              ("failure", m["fail_f"] <= th["fail_max"] + 1e-12), ("merge loss 0", m["merge_loss"] == 0),
              ("critical regressions 0", m["critical_regressions"] == 0)]
    miss = [name for name, ok in checks if not ok]
    if not miss:
        return "KEEP", ["all KEEP conditions met — a right to propose a promotion, not a default change"]
    reasons = [f"not met: {x}" for x in miss]
    if m["merge_loss"]:
        reasons.append("merge lost candidates — report it as a defect of gpt_merge")
    return "DEFER", reasons


def when(s, what):
    """An aware datetime — a time without a zone is not comparable with the freeze time."""
    try:
        t = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        raise Bad(f"{what}: not an ISO time — {s!r}")
    if t.tzinfo is None:
        raise Bad(f"{what}: time without a zone — {s!r} (write Z or an offset)")
    return t


def verify_freeze(prereg_path, log_path, runs=None):
    """The prereg is frozen in the experiment-log GPT section (approved_by user · time · sha256 · instrument commit) and
    no E1 run started before the freeze."""
    text = open(log_path, encoding="utf-8").read()
    psha = sha(prereg_path)
    rows = re.findall(r"(?m)^\|\s*([0-9a-f]{64})\s*\|\s*user\s*\|\s*(\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})?)\s*\|\s*([0-9a-f]{7,40})\s*\|", text)
    hit = [r for r in rows if r[0] == psha]
    if not hit:
        raise Bad(f"no freeze row for prereg {psha[:12]} (approved_by user · time · instrument commit) in {log_path}")
    frozen = when(hit[-1][1], "freeze row")
    pre = json.load(open(prereg_path, encoding="utf-8"))
    ins = str(pre.get("instrument_sha") or "")
    if not ins or not (ins.startswith(hit[-1][2]) or hit[-1][2].startswith(ins)):
        raise Bad("the freeze row's instrument commit differs from the prereg's instrument_sha (or the prereg has none)")
    for r in runs or []:
        if when(r.get("started"), f"run {r.get('task')}/{r.get('arm')} started") < frozen:
            raise Bad(f"run {r.get('task')}/{r.get('arm')} started {r.get('started')} before the freeze {hit[-1][1]}")
    return {"prereg_sha256": psha, "frozen_at": hit[-1][1], "instrument": hit[-1][2]}


def read_runs(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    ap = argparse.ArgumentParser(prog="gpt_ab_decide.py", description="GPT multi-angle E1 decision and freeze check")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("decide")
    for k in ("--prereg", "--log", "--runs", "--out"):
        d.add_argument(k, required=True)
    d.add_argument("--verdicts", required=True, action="append")
    d.add_argument("--frame-arm", default="A2", choices=("A2", "A3", "A4"))
    f = sub.add_parser("verify-freeze")
    f.add_argument("--prereg", required=True)
    f.add_argument("--log", required=True)
    f.add_argument("--runs")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        if a.cmd == "decide":
            load_prereg(a.prereg)
            runs = read_runs(a.runs)
            verify_freeze(a.prereg, a.log, runs)
            verdicts = load_verdicts([json.load(open(p, encoding="utf-8")) for p in a.verdicts])
            m, th, pre = compute(a.prereg, runs, verdicts, a.frame_arm)
            dec, why = decide_metrics(m, th, pre["n_min"])
            json.dump({"decision": dec, "reasons": why, "metrics": m, "thresholds": {k: pre["thresholds"][k]["value"] for k in THRESH},
                       "prereg_sha256": sha(a.prereg)}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"GPT-AB-DECISION {dec} ({a.frame_arm}) — {'; '.join(why)}")
            return 0
        if a.cmd == "verify-freeze":
            r = verify_freeze(a.prereg, a.log, read_runs(a.runs) if a.runs else None)
            print(f"GPT-AB-FREEZE-OK prereg {r['prereg_sha256'][:12]} frozen {r['frozen_at']} instrument {r['instrument']}")
            return 0
    except Bad as e:
        print(f"GPT-AB-REJECT: {e}", file=sys.stderr)
        return 1
    ap.print_usage(sys.stderr)
    return 2


def self_test():
    bad, n = [], 0

    def cell(cid, ok, note=""):
        nonlocal n
        n += 1
        print(f"{'PASS' if ok else 'FAIL'}  [{cid}] {note}")
        if not ok:
            bad.append(cid)

    def rejects(fn):
        try:
            fn()
        except Bad:
            return True
        return False
    th = {"delta_keep": 1.0, "positive_share": 2 / 3, "fp_keep": 0.15, "fp_rollback": 0.30, "tokens_ratio": 1.5, "fail_max": 0.10}

    def M(n=6, delta=1.0, pos=4, fp=0.15, tok=1.5, fail=0.10, loss=0, crit=0):
        return {"n_valid": n, "mean_delta": delta, "positive": pos, "fp_diff": fp, "tokens_ratio": tok, "fail_f": fail, "merge_loss": loss, "critical_regressions": crit}
    for cid, m, want in (("z14-n5-defer", M(n=5, delta=3), "DEFER"), ("z14-keep", M(), "KEEP"), ("z14-delta-0.99", M(delta=0.99), "DEFER"),
                         ("z14-positive-3of6", M(pos=3), "DEFER"), ("z14-fp-0.151", M(fp=0.151), "DEFER"), ("z14-fp-0.30", M(fp=0.30), "DEFER"),
                         ("z14-fp-0.301-rollback", M(fp=0.301), "ROLLBACK"), ("z14-delta-0-rollback", M(delta=0), "ROLLBACK"),
                         ("z14-tokens-1.51", M(tok=1.51), "DEFER"), ("z14-fail-0.11", M(fail=0.11), "DEFER")):
        got = decide_metrics(m, th, 6)[0]
        cell(cid, got == want, f"{got} (want {want})")
    d, why = decide_metrics(M(loss=1), th, 6)
    cell("z14-merge-loss", d == "DEFER" and any("defect" in w for w in why), f"{d} · {why[-1]}")
    exact = dict(th, positive_share=Fraction(2, 3))
    got = [decide_metrics(M(n=k, pos=p), exact, 6)[0] for k, p in ((6, 4), (9, 6), (12, 8))]
    lose = decide_metrics(M(n=6, pos=4), dict(th, positive_share=num(0.667)), 6)[0]
    cell("two-thirds-exact", got == ["KEEP"] * 3 and num("2/3") == Fraction(2, 3) and lose == "DEFER",
         f"2/3 at n=6·9·12 -> {got} · 0.667 at n=6 needs 5 -> {lose}")

    t = tempfile.mkdtemp(prefix="fz-gptab-st.")
    approved = {k: {"value": v, "status": "approved"} for k, v in th.items()}
    approved["positive_share"]["value"] = "2/3"
    pre = {"n_min": 6, "n_max": 12, "instrument_sha": "abc1234", "thresholds": approved}
    pp = os.path.join(t, "prereg.json")
    json.dump(pre, open(pp, "w"))
    psha = sha(pp)
    base = {"model": "m", "effort": "xhigh", "cli": "cli 0.159.2", "config_sha_normalized": "c", "tokens": 100,
            "prereg_sha256": psha, "instrument_sha": "abc1234", "exit": 0, "spawnAgent": 0, "candidates": []}
    run = lambda **kw: dict(base, **kw)
    m, _, _ = compute(pp, [run(task="t", arm="A0", rep=1, prereg_sha256="0" * 64)], {})
    cell("z14-prereg-hash-invalid", decide_metrics(m, th, 6)[0] == "INVALID", str(m.get("reason"))[:60])
    json.dump(dict(pre, noise_floor=5), open(os.path.join(t, "noise.json"), "w"))
    rc = main(["decide", "--prereg", os.path.join(t, "noise.json"), "--log", os.devnull, "--runs", os.devnull, "--verdicts", pp,
               "--out", os.path.join(t, "o.json")])
    cell("z14-noise-const-reject", rc == 1, f"exit {rc}")
    json.dump(dict(pre, instrument_sha=None), open(os.path.join(t, "noins.json"), "w"))
    cell("instrument-sha-required", rejects(lambda: load_prereg(os.path.join(t, "noins.json"))), "no instrument_sha -> reject")

    kid = {"model": "m", "effort": "xhigh"}
    a4 = lambda roles, cr=2, kids=2: run(task="t", arm="A4", rep=1, spawnAgent=len(roles), spawnedRoles=roles, childResults=cr, children=[kid] * kids)
    cell("a4-valid", run_state(a4(["fz-review-quality", "fz-review-arch"])) == "ok")
    cell("a4-singleton", run_state(a4(["fz-review-arch"], cr=1, kids=1)) == "invalid-a4")
    cell("a4-duplicate", run_state(a4(["fz-review-arch", "fz-review-arch"])) == "invalid-a4")
    cell("a4-child-fail", run_state(a4(["fz-review-arch", "fz-review-quality"], cr=1)) == "invalid-a4")
    cell("spawn-contaminated", run_state(run(task="t", arm="A2", rep=1, spawnAgent=1)) == "contaminated")
    cell("killed-not-zero", run_state(run(task="t", arm="A2", rep=1, exit=137)) == "killed" and run_state(run(task="t", arm="A2", rep=1, exit=12)) == "failed")
    nospawn = {k: v for k, v in run(task="t", arm="A2", rep=1).items() if k != "spawnAgent"}
    um = [run_state(x) for x in (run(task="t", arm="A2", rep=1, spawnAgent="?"), nospawn, run(task="t", arm="A2", rep=1, tokens="?"))]
    cell("unknown-not-zero", um == ["unmeasured"] * 3, f"'?' spawn · missing spawn · '?' tokens -> {um}")

    v = {"x1": {"label": "valid", "severity": "major", "canonical": "c1"}, "x2": {"label": "valid", "severity": "major", "canonical": "c2"}}
    task = lambda t_, cfg="c": [run(task=t_, arm="A0", rep=1, candidates=["x1"]), run(task=t_, arm="A0", rep=2, candidates=["x1"]),
                                run(task=t_, arm="A2", rep=1, candidates=["x1", "x2"], config_sha_normalized=cfg),
                                run(task=t_, arm="A2", rep=2, candidates=["x2"])]
    m, _, _ = compute(pp, task("t1") + task("t2", cfg="other"), v)
    cell("arm-config-mismatch", m["n_valid"] == 1 and "t2" in m["excluded"] and m["per_task"][0]["delta"] == 1, f"excluded={m['excluded']}")
    # the decider compares config_sha_normalized, not the raw hash (P-16) — the normalized value is produced by the S12 runner
    m, _, _ = compute(pp, [dict(r, config_sha_raw=f"raw{i}") for i, r in enumerate(task("t3"))], v)
    cell("config-hash-normalized", m["n_valid"] == 1, "raw hashes differ, normalized equal -> comparable")
    fpv = dict(v, f1={"label": "FP", "severity": "minor"})
    m, _, _ = compute(pp, task("t1") + [dict(r, candidates=["f1"]) if r["arm"] == "A2" else r for r in task("t2", cfg="other")], fpv)
    cell("fp-compared-tasks-only", m["fp_diff"] == 0.0 and "t2" in m["excluded"], f"FP of excluded t2 left out -> fp_diff {m['fp_diff']}")
    m, _, _ = compute(pp, [dict(r, tokens="?") if r["arm"] == "A2" and r["rep"] == 2 else r for r in task("t4")], v)
    cell("unknown-no-traceback", m["unmeasured"] == 1 and m["n_valid"] == 1, f"unmeasured={m['unmeasured']} n_valid={m['n_valid']}")
    a3 = [dict(r, arm="A3") if r["arm"] == "A2" else r for r in task("t5")]
    m, _, _ = compute(pp, a3, v, frame_arm="A3")
    cell("frame-arm-a3", m["n_valid"] == 1 and m["frame_arm"] == "A3", f"n_valid={m['n_valid']}")
    T1, T2 = "2026-10-21T00:00:00Z", "2026-10-21T01:00:00Z"
    stamped = lambda rs, ts=T2: [dict(r, started=ts) for r in rs]
    rerun = stamped(task("t6")) + [run(task="t6", arm="A2", rep=2, exit=12, started=T1)]
    m, _, _ = compute(pp, rerun, v)
    after_ok = stamped(task("t7"), T1) + [run(task="t7", arm="A2", rep=2, exit=12, started=T2)]
    cell("rerun-rows", m["n_valid"] == 1 and rejects(lambda: compute(pp, task("t7") + [run(task="t7", arm="A2", rep=2, candidates=["x1"])], v))
         and rejects(lambda: compute(pp, rerun + [run(task="t6", arm="A2", rep=2, exit=13)], v)) and rejects(lambda: compute(pp, after_ok, v)),
         "failed then ok kept · two ok rejected · two reruns rejected · rerun after ok rejected")
    cell("n-max", rejects(lambda: compute(pp, [r for i in range(13) for r in task(f"n{i}")], v)), "13 tasks > n_max 12 -> reject")
    cell("verdicts-complete", rejects(lambda: compute(pp, task("t8"), {"x1": v["x1"]})), "x2 not judged -> reject")
    vd = {"x1": {"label": "valid", "severity": "major", "canonical": "c1"}, "x2": {"label": "dup", "canonical": "c1"},
          "y1": {"label": "dup", "canonical": "c1"}, "y2": {"label": "valid", "severity": "major", "canonical": "c1"}}
    order = lambda first, second: [run(task="t9", arm="A0", rep=1, candidates=[first]), run(task="t9", arm="A0", rep=2, candidates=[first]),
                                   run(task="t9", arm="A2", rep=1, candidates=[second]), run(task="t9", arm="A2", rep=2, candidates=[second])]
    m1, _, _ = compute(pp, order("x1", "x2"), vd)
    m2, _, _ = compute(pp, order("y1", "y2"), vd)
    cell("dup-order-free", m1["per_task"][0]["delta"] == m2["per_task"][0]["delta"] == 0, "valid first or dup first -> same Δ")
    # another task's valid 'c9' must not resolve this task's dup of 'c9' (canonical labels restart per pack)
    vx = {"x1": v["x1"], "d9": {"label": "dup", "canonical": "c9"}, "z9": {"label": "valid", "severity": "major", "canonical": "c9"}}
    own = [run(task="ta", arm="A0", rep=1, candidates=["x1"]), run(task="ta", arm="A0", rep=2, candidates=["x1"]),
           run(task="ta", arm="A2", rep=1, candidates=["x1", "d9"]), run(task="ta", arm="A2", rep=2, candidates=["x1"])]
    other = [run(task="tb", arm="A0", rep=1, candidates=["z9"])]
    m, _, _ = compute(pp, own + other, vx)
    cell("canonical-per-task", m["per_task"][0]["delta"] == 0, f"Δ={m['per_task'][0]['delta']} (a foreign class would make it 0.5)")
    judged = {"schema": "gpt-merge-judged/1", "judged": [{"id": k, "provenance": {}, "verdict": x} for k, x in v.items()]}
    cell("verdicts-shape", load_verdicts([judged]) == v and rejects(lambda: load_verdicts([v])) and rejects(lambda: load_verdicts([judged, judged])),
         "judged/1 read · plain dict rejected · same id twice rejected")

    log = os.path.join(t, "log.md")
    open(log, "w").write("## GPT 다각도 원장 프로토콜\n\n| prereg_sha256 | approved_by | time | instrument |\n|---|---|---|---|\n"
                         f"| {psha} | user | 2026-10-20T00:00:00Z | abc1234 |\n")
    ok1 = verify_freeze(pp, log, [run(task="t", arm="A0", rep=1, started="2026-10-21T00:00:00Z")])["prereg_sha256"] == psha
    early = rejects(lambda: verify_freeze(pp, log, [run(task="t", arm="A0", rep=1, started="2026-10-19T00:00:00Z")]))
    zone = rejects(lambda: verify_freeze(pp, log, [run(task="t", arm="A0", rep=1, started="2026-10-20T08:00:00+09:00")]))
    nozone = rejects(lambda: verify_freeze(pp, log, [run(task="t", arm="A0", rep=1, started="2026-10-21T00:00:00")]))
    open(log, "w").write("## GPT 다각도 원장 프로토콜\n\n(no freeze row)\n")
    norow = rejects(lambda: verify_freeze(pp, log))
    cell("verify-freeze", ok1 and early and zone and nozone and norow,
         f"ok={ok1} early={early} +09:00-early={zone} no-zone={nozone} no-row={norow}")
    shutil.rmtree(t, ignore_errors=True)
    print(f"self-test gpt_ab_decide: {'OK' if not bad else 'FAIL'} ({n} checks, {len(bad)} failed)")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
