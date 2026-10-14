#!/usr/bin/env python3
# diff-parse: hunk-state — hunk 텍스트와 경로 의미는 review_merge.hunk_text · diff_anchors 를 그대로 쓴다(여기서 다시 짜지 않는다)
"""N-way GPT merge — several GPT runs (call kinds · frames · repeats) over the same inputs into one candidate list with provenance.

It groups, it does not judge: the input candidate multiset equals the output candidate multiset. No majority vote drops a
candidate, no severity is raised, a reproduction claim is not promoted to 'reproduced' (the Lead or a blind grader decides).
review_merge.py (Claude x GPT) is not changed and does not accept this output (no issues/findings array — XE-26).

usage:
  gpt_merge.py --diff DIFF (--in FILE --label KIND,FRAME,RUN,SESSION,LENS,INPUTS_SHA)... [--unavailable LABEL REASON]... [--out FILE]
      LABEL fields come from the run's audit · call row · OUT path, never from the model's output (EC-44).
      INPUTS_SHA = sha256(diff.patch)[:head-tree-hash] — every input must carry the same value (P-07), its diff part must be
      sha256(--diff) (stale otherwise). FRAME / LENS '-' when none. A run with a launcher audit is held to it: the label frame
      and head must match the audit, and every audited run must record the same input hashes (diff · base · head · snapshots).
  gpt_merge.py --blind-pack MERGED --out-dir DIR [--seed N]   DIR/pack.json (normalized, shuffled, labels removed; the location
      group id stays — a hint for the grader's canonical classes, not a source) + DIR/key.json
  gpt_merge.py --blind-unpack DIR --verdicts FILE --out FILE  joins blind verdicts back to candidate ids and provenance
  gpt_merge.py --self-test

candidate id = gpt:<kind>:<frame>:<run>:<channel>:<id> (P-15 · XE-25) · originalId kept · channel defect | craft.
groups: same resolved file · same axis · overlapping line spans (union-find); a candidate without a location is its own group
(unlocated — left out of frame-unique counts, XE-28). contested = one group, several severities (values kept, group severity
null). minority = one source (kind · frame · run) only. evidence re-check uses review_merge's quote test; a failed check
marks hold — but evidence with a command and its output goes to the repro channel and is not demoted (XE-27).
exit: 0 ok · 1 reject (stale · head mismatch · contaminated · audit not passed · contract violation · duplicate id ·
      blind verdicts incomplete) · 2 nothing to merge / unknown shape / usage
"""
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


class Reject(Exception):
    pass


class Unknown(Exception):
    pass


def _review_merge():
    spec = importlib.util.spec_from_file_location("review_merge", os.path.join(HERE, "review_merge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RM = _review_merge()
REPRO_RE = re.compile(r"(?m)^\$ \S.*\n(?!\$ )\S")      # a shell command line followed by an output line


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def parse_label(s):
    parts = s.split(",")
    if len(parts) != 6 or not all(parts):
        raise Reject(f"--label needs 6 comma-separated fields KIND,FRAME,RUN,SESSION,LENS,INPUTS_SHA — got {s!r}")
    return dict(zip(("call_kind", "frame", "run", "session", "lens", "inputs_sha"), parts))


def sidecars(path, diff_sha, label):
    """A launcher run leaves its verdict next to the output — refuse what it refused, and hold the hand-made label to what
    the audit recorded (frame · head). -> the audit's input hashes, or None when the run has no audit."""
    stem = path[:-5] if path.endswith(".json") else path
    if os.path.exists(stem + ".contaminated"):
        raise Reject(f"{path}: contaminated run ({stem}.contaminated)")
    if not os.path.exists(stem + ".audit.json"):
        return None
    a = json.load(open(stem + ".audit.json", encoding="utf-8"))
    if a.get("exit") != 0 or a.get("isolationApplied") is not True:
        raise Reject(f"{path}: launcher audit did not pass — exit {a.get('exit')} · isolation {a.get('isolationApplied')}")
    inputs = a.get("inputs") or {}
    want = inputs.get("diff.patch")
    if want and want != diff_sha:
        raise Reject(f"{path}: stale — the run saw diff {want[:12]}, the merge got {diff_sha[:12]}")
    if (a.get("frame") or "-") != label["frame"]:
        raise Reject(f"{path}: label frame {label['frame']!r} but the audit says {a.get('frame') or '-'!r}")
    head = label["inputs_sha"].split(":", 1)[1] if ":" in label["inputs_sha"] else None
    if inputs.get("head/") and head != inputs["head/"]:
        raise Reject(f"{path}: label head {str(head)[:12]} but the audit's head/ tree is {inputs['head/'][:12]} — a label must carry the head the run saw")
    return inputs


def candidates_of(doc, label, src):
    if not isinstance(doc, dict) or not isinstance(doc.get("issues"), list):
        raise Unknown(f"{src}: no issues array — an unknown shape is not merged as zero candidates")
    craft = doc.get("craft") or []
    if not isinstance(craft, list):
        raise Unknown(f"{src}: craft is not an array")
    out, seen = [], set()
    for channel, items in (("defect", doc["issues"]), ("craft", craft)):
        for it in items:
            if not isinstance(it, dict) or not it.get("id"):
                raise Reject(f"{src}: a {channel} item without an id")
            if channel == "craft" and not it.get("craftAxis"):
                raise Reject(f"{src}: craft item {it['id']} without craftAxis")
            if (channel, it["id"]) in seen:
                raise Reject(f"{src}: duplicate id {it['id']} in the {channel} channel")
            seen.add((channel, it["id"]))
            L = label
            c = {"id": f"gpt:{L['call_kind']}:{L['frame']}:{L['run']}:{channel}:{it['id']}", "originalId": it["id"], "channel": channel,
                 "provenance": dict(label, source=os.path.abspath(src)),
                 "severity": it.get("severity"), "file": RM.gpt_path(it.get("file")), "line_range": it.get("line_range"),
                 "axis": it.get("craftAxis") if channel == "craft" else it.get("discoveryAxis"),
                 "title": it.get("title"), "detail": it.get("detail"), "evidence": it.get("evidence")}
            out.append(c)
    return out


def group(cands):
    """union-find: same file · same channel/axis · overlapping line spans. No location -> its own group."""
    parent = list(range(len(cands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    loc = [(c["file"], c["channel"], c["axis"], RM.spans(c["line_range"])) if c["file"] and RM.spans(c["line_range"]) else None for c in cands]
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = loc[i], loc[j]
            if a and b and a[:3] == b[:3] and any(x0 <= y1 and y0 <= x1 for x0, x1 in a[3] for y0, y1 in b[3]):
                parent[find(i)] = find(j)
    by = {}
    for i in range(len(cands)):
        by.setdefault(find(i), []).append(i)
    groups = []
    for n, idx in enumerate(sorted(by.values(), key=lambda v: sorted(cands[k]["id"] for k in v))):
        mem = sorted(idx, key=lambda k: cands[k]["id"])
        sev = sorted({str(cands[k]["severity"]) for k in mem})
        srcs = sorted({(cands[k]["provenance"]["call_kind"], cands[k]["provenance"]["frame"], cands[k]["provenance"]["run"]) for k in mem})
        groups.append({"gid": f"g{n + 1}", "members": [cands[k]["id"] for k in mem], "channel": cands[mem[0]]["channel"],
                       "unlocated": loc[mem[0]] is None, "contested": len(sev) > 1,
                       "severity": None if len(sev) > 1 else cands[mem[0]]["severity"],
                       "minority": len(srcs) == 1, "sources": [list(s) for s in srcs]})
    return groups


def merge(diff, ins, unavailable):
    if not ins and not unavailable:
        raise Unknown("nothing to merge — no --in and no --unavailable")
    diff_sha = sha256_file(diff)
    texts = RM.hunk_text(open(diff, encoding="utf-8", errors="replace").read())
    labels = [parse_label(l) for _, l in ins]
    for L in labels:
        if L["inputs_sha"].split(":", 1)[0] != diff_sha:
            raise Reject(f"stale — run {L['run']} saw inputs {L['inputs_sha'][:12]}, the merge diff is {diff_sha[:12]}")
    if len({L["inputs_sha"] for L in labels}) > 1:
        raise Reject("inputs differ between runs (same diff, different head?) — runs over different inputs are not merged (P-07)")
    cands, verdicts, audited = [], [], {}
    for (path, _), L in zip(ins, labels):
        seen = sidecars(path, diff_sha, L)
        if seen is not None:
            audited[path] = json.dumps(seen, sort_keys=True)
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise Unknown(f"{path}: unreadable: {e}")
        cs = candidates_of(doc, L, path)
        cands += cs
        verdicts.append({"run": L["run"], "call_kind": L["call_kind"], "frame": L["frame"], "verdict": doc.get("verdict")})
    if len(set(audited.values())) > 1:
        raise Reject("the audits record different inputs (diff · base · head · snapshots) — runs over different inputs are not merged (P-07)")
    ids = [c["id"] for c in cands]
    if len(ids) != len(set(ids)):
        raise Reject("two inputs share a label (same kind · frame · run) — candidate ids would collide")
    for c in cands:
        why = RM.resolve_file(c, texts)
        ok, note = RM.evidence_check(c, texts, why)
        c["evidenceVerified"], c["evidenceNote"] = ok, note
        c["reproClaimed"] = bool(REPRO_RE.search(str(c.get("evidence") or "")))
        c["hold"] = ok is False and not c["reproClaimed"]
    groups = group(cands)
    assert sorted(ids) == sorted(m for g in groups for m in g["members"]), "multiset broken"
    un = [{"label": parse_label(l), "reason": r} for l, r in unavailable]
    return {"schema": "gpt-merge/1", "diffSha256": diff_sha, "candidates": cands, "groups": groups, "verdicts": verdicts,
            "unavailable": un,
            "summary": {"inputs": len(ins), "unavailable": len(un), "candidatesIn": len(ids), "candidatesOut": len(cands),
                        "groups": len(groups), "contested": sum(g["contested"] for g in groups),
                        "unlocated": sum(g["unlocated"] for g in groups), "minority": sum(g["minority"] for g in groups),
                        "hold": sum(c["hold"] for c in cands), "reproClaimed": sum(c["reproClaimed"] for c in cands)}}


def blind_pack(merged, out_dir, seed=None):
    m = json.load(open(merged, encoding="utf-8"))
    rnd = random.Random(seed)
    rows, key = [], {}
    gid = {cid: g["gid"] for g in m["groups"] for cid in g["members"]}
    for c in m["candidates"]:
        bid = "b" + hashlib.sha256(f"{rnd.random()}:{c['id']}".encode()).hexdigest()[:10]
        key[bid] = c["id"]
        rows.append({"bid": bid, "group": gid[c["id"]], "file": c["file"], "line_range": c["line_range"], "channel": c["channel"],
                     "claim": " — ".join(str(x) for x in (c.get("title"), c.get("detail")) if x), "evidence": c.get("evidence")})
    rnd.shuffle(rows)
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"schema": "gpt-merge-blind/1", "candidates": rows}, open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"merged": os.path.abspath(merged), "key": key}, open(os.path.join(out_dir, "key.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(rows)


def blind_unpack(d, verdicts_path, out):
    key = json.load(open(os.path.join(d, "key.json"), encoding="utf-8"))
    m = json.load(open(key["merged"], encoding="utf-8"))
    v = json.load(open(verdicts_path, encoding="utf-8"))
    missing = sorted(set(key["key"]) - set(v))
    if missing:
        raise Reject(f"blind verdicts incomplete — {len(missing)} candidate(s) not judged: {missing[:3]}")
    by_id = {c["id"]: c for c in m["candidates"]}
    rows = [{"id": cid, "provenance": by_id[cid]["provenance"], "verdict": v[bid]} for bid, cid in key["key"].items()]
    json.dump({"schema": "gpt-merge-judged/1", "judged": sorted(rows, key=lambda r: r["id"])}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(rows)


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    try:
        if argv[:1] == ["--blind-pack"]:
            a = dict(zip(argv[::2], argv[1::2]))
            n = blind_pack(a["--blind-pack"], a["--out-dir"], int(a["--seed"]) if "--seed" in a else None)
            print(f"GPT-MERGE-BLIND packed={n}")
            return 0
        if argv[:1] == ["--blind-unpack"]:
            a = dict(zip(argv[::2], argv[1::2]))
            n = blind_unpack(a["--blind-unpack"], a["--verdicts"], a["--out"])
            print(f"GPT-MERGE-UNPACK judged={n}")
            return 0
        diff, out, ins, un, i = None, None, [], [], 0
        while i < len(argv):
            t = argv[i]
            if t == "--diff":
                diff, i = argv[i + 1], i + 2
            elif t == "--out":
                out, i = argv[i + 1], i + 2
            elif t == "--in" and i + 3 < len(argv) and argv[i + 2] == "--label":
                ins.append((argv[i + 1], argv[i + 3]))
                i += 4
            elif t == "--unavailable":
                un.append((argv[i + 1], argv[i + 2]))
                i += 3
            else:
                print(f"GPT-MERGE-USAGE: unexpected {t!r} (--in FILE must be followed by --label …)", file=sys.stderr)
                return 2
        if not diff:
            print("GPT-MERGE-USAGE: --diff is required", file=sys.stderr)
            return 2
        res = merge(diff, ins, un)
    except Reject as e:
        print(f"GPT-MERGE-REJECT: {e}", file=sys.stderr)
        return 1
    except (Unknown, KeyError, IndexError) as e:
        print(f"GPT-MERGE-UNKNOWN: {e}", file=sys.stderr)
        return 2
    text = json.dumps(res, ensure_ascii=False, indent=1)
    if out:
        open(out, "w", encoding="utf-8").write(text)
    else:
        print(text)
    s = res["summary"]
    print(f"GPT-MERGE-OK inputs={s['inputs']} unavailable={s['unavailable']} candidates={s['candidatesOut']} groups={s['groups']} "
          f"contested={s['contested']} unlocated={s['unlocated']}", file=sys.stderr)
    return 0


def self_test():
    """Pure checks on the merge rules (the CLI cells live in tests/fixtures/gpt/merge-n)."""
    n, bad = 0, []

    def expect(name, ok):
        nonlocal n
        n += 1
        if not ok:
            bad.append(name)
    t = tempfile.mkdtemp(prefix="fz-gptmerge-st.")
    diff = os.path.join(t, "d.patch")
    open(diff, "w").write("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n-x = 1\n+x = 2\n y = 3\n")
    sha = sha256_file(diff)

    def run(name, issues, craft=None, verdict="needs_work"):
        p = os.path.join(t, name + ".json")
        json.dump({"verdict": verdict, "issues": issues, "craft": craft or []}, open(p, "w"))
        return p
    iss = lambda i, sev, line="1", ev="`x = 2`": {"id": i, "severity": sev, "file": "a.py", "line_range": line, "discoveryAxis": "logic",
                                                     "title": "t", "detail": "d", "evidence": ev}
    a = run("a", [iss("I-1", "major")])
    b = run("b", [iss("I-1", "minor")])
    lab = lambda run_, frame="-": f"review,{frame},{run_},s,-,{sha}"
    r = merge(diff, [(a, lab("r1")), (b, lab("r2", "falsify"))], [])
    expect("multiset kept", r["summary"]["candidatesIn"] == r["summary"]["candidatesOut"] == 2)
    expect("same place -> one group", len(r["groups"]) == 1)
    expect("contested keeps values", r["groups"][0]["contested"] and r["groups"][0]["severity"] is None
           and sorted(c["severity"] for c in r["candidates"]) == ["major", "minor"])
    expect("namespaced ids", {c["id"] for c in r["candidates"]} == {"gpt:review:-:r1:defect:I-1", "gpt:review:falsify:r2:defect:I-1"})
    expect("evidence verified", all(c["evidenceVerified"] for c in r["candidates"]))
    u = run("u", [iss("I-9", "major", line="")])
    r = merge(diff, [(u, lab("r3"))], [])
    expect("unlocated own group", r["groups"][0]["unlocated"] is True)
    h = run("h", [iss("I-2", "major", ev="`nowhere in the diff`")])
    rp = run("rp", [iss("I-3", "major", ev="$ python3 -c 'print(1)'\n1")])
    r = merge(diff, [(h, lab("r4")), (rp, lab("r5"))], [])
    c = {x["originalId"]: x for x in r["candidates"]}
    expect("unverified quote -> hold", c["I-2"]["hold"] is True)
    expect("repro evidence not demoted", c["I-3"]["reproClaimed"] is True and c["I-3"]["hold"] is False)
    for name, fn in (("stale", lambda: merge(diff, [(a, "review,-,r1,s,-," + "0" * 64)], [])),
                     ("head mismatch", lambda: merge(diff, [(a, lab("r1") + ":h1"), (b, lab("r2") + ":h2")], [])),
                     ("same label twice", lambda: merge(diff, [(a, lab("r1")), (b, lab("r1"))], [])),
                     ("craft without axis", lambda: merge(diff, [(run("cx", [], [{"id": "C-1"}]), lab("r6"))], []))):
        try:
            fn()
            expect(f"reject {name}", False)
        except Reject:
            expect(f"reject {name}", True)
    for name, fn in (("nothing", lambda: merge(diff, [], [])),
                     ("unknown shape", lambda: merge(diff, [(run("x", None), lab("r7"))], []))):
        try:
            fn()
            expect(f"unknown {name}", False)
        except Unknown:
            expect(f"unknown {name}", True)
    r = merge(diff, [(a, lab("r1"))], [("review,falsify,r9,-,-," + sha, "exit 12 — quota")])
    expect("unavailable recorded", r["summary"]["unavailable"] == 1 and r["unavailable"][0]["reason"].startswith("exit 12"))
    print(f"self-test gpt_merge: {'OK' if not bad else 'FAIL'} ({n} checks, {len(bad)} failed){'' if not bad else ' ' + str(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
