#!/usr/bin/env python3
"""frames fixture — experimental frames, launcher policy from the resolver (R-06 · SC-2), explicit independent inputs (D6).

Reuses the kinds-resolve capture world (fake CLI, proxy plugin root, fixed repo, temp home, path normalization) so the
default prompts are compared to the same golden the gate argv is pinned to. No real GPT CLI, no network.
Every run gets a fresh work dir — entry logs and CLI captures accumulate per dir.
Cell lines: `PASS  [<id>] <text>` / `FAIL  [<id>] <text>`. exit 0 all pass · 1 a cell failed · 3 setup failed.
"""
import hashlib
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kinds-resolve"))
import capture  # noqa: E402

R = capture.R
sys.path.insert(0, os.path.join(R, "scripts"))
import gpt_kinds  # noqa: E402

FAILED = []
SEQ = itertools.count()
GOLD = {k: json.load(open(os.path.join(HERE, "..", "kinds-resolve", "golden", f"independent-{k}.json"), encoding="utf-8"))
        for k in ("review", "plan")}
FRAME = {n: open(os.path.join(R, "templates", "gpt-frames", f"{n}.md"), encoding="utf-8").read()
         for n in ("falsify-review", "repro-review", "falsify-plan")}
REC = capture.RECIPES
NO_SPAWN = gpt_kinds.SPAWN_LINES["forbid-prompt"]
REVIEW_OK = capture.shim_body("REVIEW_IND_OK")


def check(cid, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  [{cid}] {detail}"[:400])
    if not ok:
        FAILED.append(cid)


def kd(env, inputs):
    return env.kdir(f"{inputs}-{next(SEQ)}", inputs)


def review(extra=""):
    """The kinds-resolve independent-review recipe line with extra caller inputs appended."""
    return REC["independent-review"][1].rstrip("\n") + extra + "\n"


def rollouts_with_child(env, d):
    """A root rollout (isolation applied) with one child result, plus the child's own rollout carrying a copy of that
    message — childResults must count it once."""
    root = env.rollout(f"{d}/r.jsonl", "cat diff.patch")
    msg = {"type": "response_item", "payload": {"type": "agent_message", "recipient": "/root", "author": "/root/a1"}}
    with open(root, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg) + "\n")
    with open(f"{d}/kid.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "session_meta", "payload": {"id": "kid", "parent_thread_id": "s0"}}) + "\n" + json.dumps(msg) + "\n")
    return [root, f"{d}/kid.jsonl"]


def run_review(env, extra=""):
    d = kd(env, "independent-review")
    p, entry, cli = env.run(d, review(extra), shim_output=REVIEW_OK, rollouts=rollouts_with_child(env, d))
    return d, p, entry, cli


def tree_hash(d):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(d)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(os.path.relpath(p, d).encode() + b"\0" + hashlib.sha256(open(p, "rb").read()).digest())
    return h.hexdigest()


def read(p):
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def defaults_and_frames(env):
    d, p, _, cli = run_review(env)
    dflt = env.norm(cli[0][-1]) if cli else ""
    check("default-prompt-review", dflt == GOLD["review"]["cli_argv"][0][-1] and "## Frame" not in dflt, f"rc={p.returncode}")
    a = json.load(open(f"{d}/gpt-independent/gpt-s0.audit.json", encoding="utf-8"))
    ok = a["inputs"].get("base/") == tree_hash(f"{d}/base") and a["inputs"].get("head/") == tree_hash(f"{d}/head")
    check("audit-tree-hash", ok, f"inputs={sorted(a['inputs'])}")
    db, _, _, _ = run_review(env)
    b = json.load(open(f"{db}/gpt-independent/gpt-s0.audit.json", encoding="utf-8"))
    ps, pb = a.get("promptSha256") or {}, b.get("promptSha256") or {}
    hexes = [x for x in (ps.get("raw"), ps.get("normalized"), pb.get("normalized")) if isinstance(x, str) and len(x) == 64]
    check("audit-prompt-hash", len(hexes) == 3 and ps["normalized"] == pb["normalized"], f"raw+normalized recorded · two runs normalized equal={ps.get('normalized') == pb.get('normalized')}")
    # snapshot links are hashed as links: a dangling link does not kill the audit, an outside target's content does not leak in
    snap, outside = os.path.join(d, "snaplinks"), os.path.join(d, "outside.txt")
    os.makedirs(snap, exist_ok=True)
    open(os.path.join(snap, "real.txt"), "w").write("x\n")
    open(outside, "w").write("one\n")
    os.symlink(outside, os.path.join(snap, "out-link"))
    os.symlink(os.path.join(d, "nowhere"), os.path.join(snap, "dangling"))
    got = []
    for body in ("one\n", "two\n"):
        open(outside, "w").write(body)
        ds, ps_, _, _ = run_review(env, f" --snapshot {snap}")
        au = read(f"{ds}/gpt-independent/gpt-s0.audit.json")
        got.append((ps_.returncode, (json.loads(au).get("inputs") or {}).get("snapshot/snaplinks/") if au else None))
    check("audit-symlink", got[0][1] and got[0] == got[1] and got[0][0] == p.returncode, f"runs={got} default rc={p.returncode}")
    d2 = kd(env, "independent-plan")
    p2, _, cli2 = env.run(d2, REC["independent-plan"][1], shim_output=capture.shim_body("PLAN_OK"),
                          rollouts=[env.rollout(f"{d2}/r.jsonl", "cat requirement.md")])
    pp = env.norm(cli2[0][-1]) if cli2 else ""
    check("default-prompt-plan", pp == GOLD["plan"]["cli_argv"][0][-1] and "## Frame" not in pp, f"rc={p2.returncode}")
    for name, fname, cid in (("falsify", "falsify-review", "frame-falsify-review"), ("repro", "repro-review", "frame-repro-review")):
        d, p, _, cli = run_review(env, f" --frame {name} --experimental")
        got = env.norm(cli[0][-1]) if cli else ""
        want = GOLD["review"]["cli_argv"][0][-1] + f"\n\n## Frame — {name}\n" + FRAME[fname].rstrip("\n")
        extra = ("Operation not permitted" in FRAME[fname]) if name == "repro" else True
        check(cid, got == want and extra, f"rc={p.returncode} · len {len(got)} vs {len(want)}")
        if name == "falsify":
            a = json.load(open(f"{d}/gpt-independent/gpt-s0.audit.json", encoding="utf-8"))
            sha = hashlib.sha256(FRAME[fname].encode()).hexdigest()
            check("frame-audit-fields", a.get("frame") == "falsify" and a.get("frameSha256") == sha and a.get("childResults") == 1,
                  f"frame={a.get('frame')} sha_ok={a.get('frameSha256') == sha} childResults={a.get('childResults')}")
            i_ns, i_fr = got.find(NO_SPAWN), got.find("## Frame")
            check("frame-keeps-nospawn", got.count(NO_SPAWN) == 1 and -1 < i_ns < i_fr, f"no-spawn at {i_ns} · frame at {i_fr}")


def refusals(env):
    def refused(cid, script, launcher_runs=False, note=""):
        d = kd(env, "independent-review")
        p, entry, cli = env.run(d, script, shim_output=REVIEW_OK)
        ok = p.returncode == 10 and not cli and (bool(entry) if launcher_runs else not entry)
        check(cid, ok, f"rc={p.returncode} entry={len(entry)} cli={len(cli)} {note}")
    refused("frame-bad-10", review(" --frame nope --experimental"), launcher_runs=True, note="(the launcher asks the resolver)")
    refused("explicit-inputs-unknown-10", review(" --bogus x"))
    refused("frame-needs-experimental", review(" --frame falsify"))
    d = kd(env, "independent-review")
    p, entry, _ = env.run(d, review(" --timeout 60"))
    d2 = kd(env, "independent-review")
    p2, entry2, _ = env.run(d2, review(" --timeout 60 --experimental"), shim_output=REVIEW_OK)
    ok = p.returncode == 10 and not entry and p2.returncode != 10 and bool(entry2) and entry2[0][-2:] == ["--timeout", "60"]
    check("timeout-needs-experimental", ok, f"without={p.returncode} with={p2.returncode} tail={entry2[0][-2:] if entry2 else None}")
    d3 = kd(env, "independent-plan")
    p3, e3, _ = env.run(d3, REC["independent-plan"][1].split("\n")[0] + " --frame falsify --experimental\n")
    d4 = kd(env, "independent-plan")
    direct = ('"${FZ_PLUGIN_ROOT}/scripts/gpt_independent.sh" plan --requirement "$K/requirement.md" --arm gpt --run-id d '
              '--out-dir "$K/o" --frame falsify\n')
    p4, _, c4 = env.run(d4, direct)
    check("frame-plan-mode-10", p3.returncode == 10 and not e3 and p4.returncode == 10 and not c4, f"gate={p3.returncode} direct={p4.returncode}")


def wrapper_frames(env):
    d = kd(env, "verify")
    os.makedirs(f"{d}/falsify-review")
    call = capture.GC_CALL + 'review-falsify --cd "$GIT_ROOT" --out "$K/falsify-review/o.json" --prompt-file "$K/p.txt"'
    p, entry, _ = env.run(d, call + "\n")
    check("experimental-gate-10", p.returncode == 10 and not entry, f"rc={p.returncode}")
    d = kd(env, "verify")
    os.makedirs(f"{d}/falsify-review")
    p, entry, _ = env.run(d, call + " --experimental\n")
    a = entry[-1] if entry else []
    bad = [x for x in ("--sandbox", "-c", "--model", "--effort", "--config-permissions") if x in a]
    comp = read(f"{d}/falsify-review/o.json.frame-prompt.txt")
    check("experimental-no-policy-flags", bool(a) and a[0] == "gpt-exec.sh" and not bad and comp.startswith(FRAME["falsify-review"]),
          f"adapter={a[:2]} policy_flags={bad} frame_first={comp.startswith(FRAME['falsify-review'])}")
    d = kd(env, "verify")
    p, entry, _ = env.run(d, capture.GC_CALL + 'verify-falsify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt" --experimental\n')
    outside = p.returncode == 10 and not entry
    d = kd(env, "verify")
    os.makedirs(f"{d}/falsify-plan")
    p2, entry2, _ = env.run(d, capture.GC_CALL + 'verify-falsify --cd "$GIT_ROOT" --out "$K/falsify-plan/o.json" --prompt-file "$K/p.txt" --experimental\n')
    check("verify-falsify-own-outdir", outside and p2.returncode != 10 and bool(entry2), f"outside={p.returncode} inside={p2.returncode}")
    comp = read(f"{d}/falsify-plan/o.json.frame-prompt.txt")
    adapters = [e[0] for e in entry2 if e]
    check("verify-falsify-not-launcher", adapters == ["gpt-exec.sh"] and comp.startswith(FRAME["falsify-plan"]), f"adapters={adapters}")


def registry_driven():
    reg = json.load(open(os.path.join(R, "scripts", "gpt-kinds.json"), encoding="utf-8"))
    reg["kinds"]["independent-review"].update(role="architect", schema="schemas/gpt_review_schema.json")
    env = capture.Env(registry_text=json.dumps(reg, ensure_ascii=False))
    try:
        # judged on what the CLI received — the launcher runs from the real tree, so its wrapper call is not in the proxy entry log
        def follows(cli, role="architect", schema="gpt_review_schema.json"):
            a = cli[-1] if cli else []
            return (bool(a) and "--output-schema" in a and a[a.index("--output-schema") + 1].endswith("/schemas/" + schema)
                    and f"[fz-gpt-skill-injected] fz-{role} (" in a[-1])
        d = kd(env, "independent-review")
        _, _, cli = env.run(d, review(), shim_output=REVIEW_OK)
        # direct launcher call: it asks a resolver itself — its own tree's without the env channel, the given one with it
        direct = '"${FZ_PLUGIN_ROOT}/scripts/gpt_independent.sh" review --diff "$K/diff.patch" --arm gpt --run-id d --out-dir "$K/o"\n'
        d2 = kd(env, "independent-review")
        _, _, cli2 = env.run(d2, direct, shim_output=REVIEW_OK)
        d3 = kd(env, "independent-review")
        _, _, cli3 = env.run(d3, 'FZ_GPT_POLICY_ROOT="$FZ_PLUGIN_ROOT" ' + direct, shim_output=REVIEW_OK)
        g_ok, d_ok = follows(cli), follows(cli3)
        own = follows(cli2, "reviewer", "gpt_independent_review_schema.json")
        check("registry-propagates", g_ok and d_ok and own, f"gate={g_ok} direct+env={d_ok} direct-own-tree={own}")
    finally:
        env.close()
    reg = json.load(open(os.path.join(R, "scripts", "gpt-kinds.json"), encoding="utf-8"))
    reg["kinds"]["independent-review"]["spawn"] = "lenses-optin"
    env = capture.Env(registry_text=json.dumps(reg, ensure_ascii=False))
    try:
        d = kd(env, "independent-review")
        _, _, cli = env.run(d, review(), shim_output=REVIEW_OK)
        pr = cli[0][-1] if cli else ""
        lens = gpt_kinds.SPAWN_LINES["lenses-optin"]
        check("spawn-sentence-from-registry", lens in pr and f"\n{NO_SPAWN}\n" not in pr, f"lens line present={lens in pr}")
    finally:
        env.close()


def main():
    try:
        env = capture.Env()
        try:
            defaults_and_frames(env)
            refusals(env)
            wrapper_frames(env)
        finally:
            env.close()
        registry_driven()
    except Exception as e:   # noqa: BLE001 — a crash is a setup failure, not a verdict
        print(f"SETUP frames: {type(e).__name__}: {e}")
        return 3
    print("frames: 전건 통과" if not FAILED else f"frames: FAIL {FAILED}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
