"""kinds-resolve behaviour cells — run by `capture.py cells` (see run.sh). Each cell prints PASS / FAIL.

Covers plan S2 보강[verify] (a)-(h), the R1-R4 choice variants (Z-05), exit 10-17 pass-through (Z-11), same / different --out
concurrency (XE-04), lock lifetime and cleanup ownership (P-09 · P-13 · P-17 · R-04), TERM / INT forwarding, the verify-cross
environment, and a discrimination cell (a registry change must change the captured argv).
"""
import json
import os
import shutil
import signal
import subprocess
import time

import capture
from capture import Env, R, REVIEW_OK

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f" — {detail}"))
    if not cond:
        fails.append(name)


def gate(env, kd, args, extra=None, shim_output=None, rollouts=None, cwd=None):
    p, entry, cli = env.run(kd, '"$GC" ' + args + "\n", extra=extra, shim_output=shim_output, rollouts=rollouts, cwd=cwd)
    return p, env.norm(entry), env.norm(cli)


def cflags(cli):
    """The `-c key=…` values the CLI received (first call)."""
    a = cli[0] if cli else []
    return [a[i + 1] for i in range(len(a) - 1) if a[i] == "-c"]


def tagged_alive(tag):
    return subprocess.run(["pgrep", "-f", rf"fz-shim\[{tag}\]"], capture_output=True).returncode == 0


def main():
    tag0 = f"kr-{os.getpid()}"
    env = Env()
    try:
        cells(env, tag0)
    finally:
        env.close()
    discrimination()
    registry_damage()
    print("kinds-resolve cells:", "전건 통과" if not fails else f"FAIL {len(fails)}: {fails}")
    return 0 if not fails else 1


def cells(env, tag0):
    T = env.T
    # (a) XE-01 — config has review_model and the session chose config: review-family argv carries no model / review_model
    with open(f"{env.H}/.codex/config.toml", "w") as f:
        f.write('model = "m-s0"\nmodel_reasoning_effort = "medium"\nreview_model = "m-review"\n')
    for kind, args in (("review", '--base main'), ("check", ''), ("final", '--base main')):
        kd = env.kdir(f"a-{kind}")
        p, entry, cli = gate(env, kd, f'{kind} --cd "$GIT_ROOT" --out "$K/o.md" {args}')
        bad = [c for c in cflags(cli) if c.startswith(("model=", "review_model=", "model_reasoning_effort="))]
        check(f"(a) {kind}: config + review_model -> no model / review_model in argv", p.returncode == 0 and not bad, f"rc={p.returncode} {bad}")

    # (b) explicit --model / --effort pass through untouched; policy flags are refused before any adapter runs
    kd = env.kdir("b-pass", "verify")
    p, entry, cli = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt" --model m-x --effort high', shim_output=REVIEW_OK)
    e = entry[0] if entry else []
    check("(b) --model/--effort reach the wrapper verbatim", e[e.index("--model") + 1:e.index("--model") + 2] == ["m-x"] and e[e.index("--effort") + 1:e.index("--effort") + 2] == ["high"] if "--model" in e and "--effort" in e else False, str(e))
    check("(b) R1 flags -> -c model / effort", 'model="m-x"' in cflags(cli) and "model_reasoning_effort=high" in cflags(cli), str(cflags(cli)))
    kd = env.kdir("b-rev")
    p, entry, cli = gate(env, kd, 'review --cd "$GIT_ROOT" --out "$K/o.md" --base main --model m-x')
    check("(b) R5 review + --model -> review_model too", 'review_model="m-x"' in cflags(cli), str(cflags(cli)))
    for flag in ("-p x", "--profile x", "--ignore-user-config", "--config-permissions", "-c k=v", "--schema s.json", "--inject-skill s", "--ephemeral"):
        kd = env.kdir("b-ref-" + flag.split()[0].strip("-"), "verify")
        p, entry, cli = gate(env, kd, f'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt" {flag}')
        check(f"(b) {flag.split()[0]} refused 10 · adapter not run", p.returncode == 10 and not entry and not cli, f"rc={p.returncode} entry={len(entry)}")

    # (c) usage 10 · registry / dependency 11 · never 0 / 1 / 2 for the gate's own failures
    kd = env.kdir("c")
    for name, args, want in (("no kind", "", 10), ("unknown kind", "nope --cd x", 10), ("missing input", 'verify --cd "$GIT_ROOT" --out "$K/o"', 10),
                             ("out parent missing", 'verify --cd "$GIT_ROOT" --out "$K/nodir/o" --prompt-file "$K/run.sh"', 10),
                             ("experimental without flag", 'review-repro --cd "$GIT_ROOT" --out "$K/o" --prompt-file "$K/run.sh"', 10),
                             ("--experimental on stable", 'check --cd "$GIT_ROOT" --out "$K/o" --experimental', 10)):
        p, entry, cli = gate(env, kd, args)
        check(f"(c) {name} -> {want}", p.returncode == want and not cli, f"rc={p.returncode} {p.stderr.strip()[-120:]}")
    p, _, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/nodir/o" --prompt-file "$K/run.sh"')
    check("(c) out parent missing says so (not 'running')", "parent folder" in p.stderr and "실행 중" not in p.stderr, p.stderr[-160:])
    nopy = f"{T}/nopy"
    os.makedirs(nopy)
    for tool in ("bash", "dirname", "mktemp", "rm", "perl", "cat", "basename"):
        w = shutil.which(tool)
        if w:
            os.symlink(w, f"{nopy}/{tool}")
    p = subprocess.run(["/bin/bash", env.GC, "check", "--cd", env.REPO, "--out", f"{kd}/o"], env={"PATH": nopy, "HOME": env.H}, capture_output=True, text=True)
    check("(c) python3 missing -> 11", p.returncode == 11, f"rc={p.returncode} {p.stderr[-120:]}")

    # (d) cleanup only by the lock owner; the --session-file input survives (same file and symlink alias)
    kd = env.kdir("d", "final")
    for f in ("o.json", "o.json.session"):
        open(f"{kd}/{f}", "w").write("STALE\n")
    p, _, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p_deep.txt" --schema x')
    check("(d) refused call removes stale OUT and OUT.session", p.returncode == 10 and not os.path.exists(f"{kd}/o.json") and not os.path.exists(f"{kd}/o.json.session"))
    open(f"{kd}/f.md", "w").write("STALE\n"); open(f"{kd}/f.md.session", "w").write("11111111-2222-3333-4444-555555555555\n")
    p, _, _ = gate(env, kd, 'final-deep --cd "$GIT_ROOT" --out "$K/f.md" --prompt-file "$K/p_deep.txt" --session-file "$K/f.md.session" --schema x')
    check("(d) OUT.session == --session-file is kept", p.returncode == 10 and not os.path.exists(f"{kd}/f.md") and os.path.isfile(f"{kd}/f.md.session"))
    open(f"{kd}/real.session", "w").write("11111111-2222-3333-4444-555555555555\n"); os.symlink(f"{kd}/real.session", f"{kd}/g.md.session")
    p, _, _ = gate(env, kd, 'final-deep --cd "$GIT_ROOT" --out "$K/g.md" --prompt-file "$K/p_deep.txt" --session-file "$K/real.session" --schema x')
    check("(d) symlink alias of --session-file is kept", p.returncode == 10 and os.path.islink(f"{kd}/g.md.session") and os.path.isfile(f"{kd}/real.session"))
    os.makedirs(f"{kd}/h.md.lock"); open(f"{kd}/h.md", "w").write("OTHER RUN\n")
    p, _, _ = gate(env, kd, 'check --cd "$GIT_ROOT" --out "$K/h.md" --schema x')
    check("(d) not the lock owner -> nothing removed", p.returncode == 10 and open(f"{kd}/h.md").read() == "OTHER RUN\n")
    shutil.rmtree(f"{kd}/h.md.lock")

    # (e) XE-04 same --out at once -> second 10, CLI not called; lock released -> a later call on that --out succeeds (P-13)
    kd = env.kdir("e", "verify")
    first = subprocess.Popen(["bash", "-c", 'exec "$GC" verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"'], cwd=env.REPO,
                             env=env.env(kd, {"FZ_SHIM_SLEEP": "3", "FZ_SHIM_TAG": f"{tag0}-e"}, REVIEW_OK), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(80):                 # wait for the first call to hold the lock — a fixed sleep flakes under load
        if os.path.isdir(f"{kd}/o.json.lock"):
            break
        time.sleep(0.1)
    kd2 = env.kdir("e2", "verify")
    p = subprocess.run(["bash", "-c", f'exec "$GC" verify --cd "$GIT_ROOT" --out "{kd}/o.json" --prompt-file "$K/p.txt"'], cwd=env.REPO,
                       env=env.env(kd2, None, REVIEW_OK), capture_output=True, text=True)
    check("(e) same --out concurrently -> 10 · CLI not called", p.returncode == 10 and not env.cli(kd2) and "실행 중" in p.stderr, f"rc={p.returncode}")
    first.communicate(timeout=60)
    check("(e) first call finishes 0", first.returncode == 0, f"rc={first.returncode}")
    check("(e) lock released after the call", not os.path.exists(f"{kd}/o.json.lock"))
    p, _, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"', shim_output=REVIEW_OK)
    check("(e) same --out again after the end -> 0", p.returncode == 0, f"rc={p.returncode}")
    kv, kg = env.kdir("e-v", "verify"), env.kdir("e-g", "verify-gates")
    pv = subprocess.Popen(["bash", "-c", 'exec "$GC" verify --cd "$GIT_ROOT" --out "$K/verify.json" --prompt-file "$K/p.txt"'], cwd=env.REPO,
                          env=env.env(kv, None, REVIEW_OK), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pg = subprocess.Popen(["bash", "-c", 'exec "$GC" verify-gates --cd "$GIT_ROOT" --out "$K/gv.json" --prompt-file "$K/prompt.txt"'], cwd=env.REPO,
                          env=env.env(kg), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pv.communicate(timeout=60); pg.communicate(timeout=60)
    check("(e) verify ∥ verify-gates (different --out) both run (0 · 14)", (pv.returncode, pg.returncode) == (0, 14), f"{pv.returncode},{pg.returncode}")

    # (f) XE-05 Tier 1 follows the caller's cwd
    proj = f"{T}/proj"
    os.makedirs(proj)
    os.makedirs(f"{env.H}/.codex/skills/my-arch")
    open(f"{env.H}/.codex/skills/my-arch/SKILL.md", "w").write("---\nname: my-arch\n---\nMY ARCH\n")
    open(f"{proj}/CLAUDE.md", "w").write("# p\n## GPT Skills\n| role | skill |\n|---|---|\n| architect | my-arch |\n")
    kd = env.kdir("f", "verify")
    p, entry, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"', shim_output=REVIEW_OK, cwd=proj)
    e = entry[0] if entry else []
    check("(f) cwd with a GPT Skills table -> Tier 1 skill", e[-1:] == ["<H>/.codex/skills/my-arch/SKILL.md"], str(e[-2:]))
    p, entry, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o2.json" --prompt-file "$K/p.txt"', shim_output=REVIEW_OK)
    e = entry[-1] if entry else []
    check("(f) another cwd -> bundled skill", e[-1:] == ["<R>/gpt-skills/fz-architect/SKILL.md"], str(e[-2:]))
    shutil.rmtree(f"{env.H}/.codex/skills")

    # (g) XE-06 fixer is exec + inject (not a review-mode check)
    kd = env.kdir("g", "fix-suggest")
    p, entry, _ = gate(env, kd, 'fix-suggest --cd "$GIT_ROOT" --out "$K/fix.md" --prompt-file "$K/p.txt"')
    e = entry[0] if entry else []
    check("(g) fix-suggest -> exec + --inject-skill fz-fixer", e[1:2] == ["exec"] and e[-2:] == ["--inject-skill", "<R>/gpt-skills/fz-fixer/SKILL.md"], str(e))

    # (h) check_gpt_surface is unchanged by the gate (it still PASSes on this tree)
    p = subprocess.run(["python3", os.path.join(R, "scripts", "check_gpt_surface.py")], capture_output=True, text=True, cwd=R)
    check("(h) check_gpt_surface PASS", p.returncode == 0, p.stdout[-200:] + p.stderr[-200:])

    # R1-R4 (Z-05): through the gate == direct wrapper call, for each choice state
    with open(f"{env.H}/.codex/config.toml", "w") as f:
        f.write('model = "m-s0"\nmodel_reasoning_effort = "medium"\n')
    cdir = f"{T}/choice"
    os.makedirs(cdir)
    for name, choice, flags, want in (("R1 flags", None, "--model m-f --effort low", ['model="m-f"', "model_reasoning_effort=low"]),
                                      ("R2 session choice", "model=m-sel\neffort=high\n", "", ['model="m-sel"', "model_reasoning_effort=high"]),
                                      ("R3 no choice", None, "", []),
                                      ("R4 sentinel config", "model=config\neffort=config\n", "", [])):
        sid = "kr-" + name.split()[0]
        if choice:
            open(f"{cdir}/{sid}", "w").write(choice)
        extra = {"FZ_GPT_CHOICE_DIR": cdir, "CLAUDE_CODE_SESSION_ID": sid}
        kd = env.kdir(f"r-{sid}", "verify")
        p, entry, cli = gate(env, kd, f'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt" {flags}', extra=extra, shim_output=REVIEW_OK)
        kd2 = env.kdir(f"r-{sid}-direct", "verify")
        direct = " ".join(f"'{a}'" for a in (entry[0][1:] if entry else [])).replace("<W>", T).replace("<R>", env.PX)
        p2, _, cli2 = env.run(kd2, f'bash "$FZ_PLUGIN_ROOT/scripts/gpt-exec.sh" {direct}\n', extra=extra, shim_output=REVIEW_OK)
        got = [c for c in cflags(cli) if c.startswith(("model=", "model_reasoning_effort="))]
        check(f"{name}: gate argv == direct wrapper argv · {want or 'no model/effort'}", p.returncode == 0 and env.norm(cli) == env.norm(cli2) and got == want,
              f"rc={p.returncode} got={got}")

    # exit codes 10-17 pass through untouched (Z-11)
    kd = env.kdir("x12", "verify")
    p, _, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"', extra={"FZ_SHIM_EXIT": "1"})
    check("exit 12 (CLI failed) passes through", p.returncode == 12, f"rc={p.returncode}")
    kd = env.kdir("x13", "verify")
    p, _, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"', shim_output="")
    check("exit 13 (empty output) passes through", p.returncode == 13, f"rc={p.returncode}")
    kd = env.kdir("x14", "validate")
    p, _, _ = gate(env, kd, 'validate --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"')
    check("exit 14 (contract) passes through", p.returncode == 14, f"rc={p.returncode}")
    open(f"{cdir}/kr-bad", "w").write("garbage\n")
    kd = env.kdir("x11", "verify")
    p, _, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"', extra={"FZ_GPT_CHOICE_DIR": cdir, "CLAUDE_CODE_SESSION_ID": "kr-bad"})
    check("exit 11 (wrapper: unreadable choice) passes through", p.returncode == 11, f"rc={p.returncode}")
    rej = json.dumps({"status": "rejected", "reason": "claude_plan_detected", "approach": "-", "affectedFiles": {"new": 0, "modified": 0}, "steps": [],
                      "riskMatrix": [], "stressTest": [], "implicationRegister": [], "divergencePoints": [],
                      "projectRules": {"axes": {a: None for a in ("architecturePattern", "uiStack", "dependencyDirection", "naming", "placement", "conventions")},
                                       "rules": [], "conflicts": [], "gaps": []}})
    kd = env.kdir("x17", "independent-plan")
    p, _, _ = gate(env, kd, 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id x --out-dir "$K/out"', shim_output=rej,
                   rollouts=[env.rollout(f"{kd}/r.jsonl", "cat requirement.md")])
    check("exit 17 (planner rejected) passes through", p.returncode == 17, f"rc={p.returncode}")
    kd = env.kdir("x15", "independent-plan")
    p, _, _ = gate(env, kd, 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id x --out-dir "$K/out"', shim_output=capture.shim_body("PLAN_OK"),
                   rollouts=[env.rollout(f"{kd}/r.jsonl", "cat ~/.claude/projects/p/notes.md")])
    check("exit 15 (contaminated) passes through", p.returncode == 15, f"rc={p.returncode}")
    kd = env.kdir("x16", "independent-plan")
    p, _, _ = gate(env, kd, 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id x --out-dir "$K/out" --timeout 2 --experimental',
                   extra={"FZ_SHIM_SLEEP": "29", "FZ_SHIM_TAG": f"{tag0}-x16"}, shim_output=capture.shim_body("PLAN_OK"),
                   rollouts=[env.rollout(f"{kd}/r.jsonl", "cat requirement.md")])
    time.sleep(1)
    check("exit 16 (launcher timeout) passes through · no orphan", p.returncode == 16 and not tagged_alive(f"{tag0}-x16"), f"rc={p.returncode}")
    os.makedirs(f"{kd}/out2/gpt-y.json.lock")
    p, _, _ = gate(env, kd, 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id y --out-dir "$K/out2"', shim_output=capture.shim_body("PLAN_OK"))
    check("exit 10 (launcher: same --out running) passes through · launcher owns that lock", p.returncode == 10, f"rc={p.returncode}")

    # verify-cross: the adapter sees the isolated CODEX_HOME, the caller's HOME, and the isolation home is cleaned up after
    kd = capture.prepare(env, "verify-cross")
    p, entry, _ = gate(env, kd, 'verify-cross --audit "$K/audit.json" --cd "$GIT_ROOT" --out "$K/cross.json" --prompt-file "$K/p_verify.txt" --prompt-out "$K/p_cross.txt"',
                       extra={"FZ_SHIM_ENV_CAPTURE": f"{kd}/env.txt"}, shim_output=REVIEW_OK)
    seen = open(f"{kd}/env.txt").read() if os.path.exists(f"{kd}/env.txt") else ""
    check("verify-cross: adapter CODEX_HOME = audit iso/gpt-home · HOME unchanged", f"CODEX_HOME={kd}/fz-gpt-iso.S0CAPT/gpt-home" in seen and f"HOME={env.H}" in seen, seen)
    check("verify-cross: isolation home removed after the call (E3)", not os.path.exists(f"{kd}/fz-gpt-iso.S0CAPT"))
    # --out reuses the planner's output: <OUT>.session IS the audit session — the gate keeps it (the wrapper reads it, then rotates it)
    kd = env.kdir("vc-out-alias", "verify-cross")
    os.makedirs(f"{kd}/fz-gpt-iso.ALIASS/gpt-home")
    with open(f"{kd}/audit5.json", "w") as f:
        json.dump({"iso": f"{kd}/fz-gpt-iso.ALIASS", "sessionFile": f"{kd}/prev.json.session"}, f)
    p, entry, cli = gate(env, kd, 'verify-cross --audit "$K/audit5.json" --cd "$GIT_ROOT" --out "$K/prev.json" --prompt-file "$K/p_verify.txt" --prompt-out "$K/p_cross.txt"',
                         shim_output=REVIEW_OK)
    check("verify-cross --out = planner output: the audit session survives the gate's cleanup -> exit 0 · CLI resumed", p.returncode == 0 and bool(cli),
          f"rc={p.returncode} stderr={p.stderr[-200:] if p.stderr else ''}")
    kd = env.kdir("vc-nosession", "verify-cross")      # fresh dir — the entry log and capture dir accumulate per dir
    with open(f"{kd}/audit2.json", "w") as f:
        json.dump({"iso": None, "sessionFile": None}, f)
    p, entry, cli = gate(env, kd, 'verify-cross --audit "$K/audit2.json" --cd "$GIT_ROOT" --out "$K/c2.json" --prompt-file "$K/p_verify.txt" --prompt-out "$K/pc2.txt"')
    check("verify-cross: audit without a session -> 10 · nothing run", p.returncode == 10 and not entry and not cli, f"rc={p.returncode}")
    # a refused call keeps an isolation home it does not consume — only verify-cross takes --audit
    kd = env.kdir("vc-foreign-audit", "verify")
    iso = f"{kd}/fz-gpt-iso.FOREIG"
    os.makedirs(f"{iso}/gpt-home")
    with open(f"{kd}/audit3.json", "w") as f:
        json.dump({"iso": iso, "sessionFile": f"{kd}/s"}, f)
    p, entry, cli = gate(env, kd, 'verify --audit "$K/audit3.json" --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"')
    check("--audit on a kind that does not take it -> 10 · nothing run · its iso kept", p.returncode == 10 and not entry and not cli and os.path.isdir(iso),
          f"rc={p.returncode} iso={os.path.isdir(iso)}")
    # a composition failure still ends the verify-cross session (E3) — every exit of the call removes the iso
    kd = env.kdir("vc-compose-fail", "verify-cross")
    iso = f"{kd}/fz-gpt-iso.CMPFAI"
    os.makedirs(f"{iso}/gpt-home")
    with open(f"{kd}/audit4.json", "w") as f:
        json.dump({"iso": iso, "sessionFile": f"{kd}/s"}, f)
    p, entry, cli = gate(env, kd, 'verify-cross --audit "$K/audit4.json" --cd "$GIT_ROOT" --out "$K/c4.json" --prompt-file "$K/missing.txt" --prompt-out "$K/pc4.txt"')
    check("verify-cross: composition failure -> 11 · CLI not called · iso removed (E3)", p.returncode == 11 and not cli and not os.path.exists(iso),
          f"rc={p.returncode} iso={os.path.exists(iso)}")
    # --prompt-out on --out: the wrapper would erase the composed prompt before reading it
    kd = env.kdir("vc-prompt-clash", "verify-cross")
    p, entry, cli = gate(env, kd, 'verify-cross --audit "$K/audit.json" --cd "$GIT_ROOT" --out "$K/same.json" --prompt-file "$K/p_verify.txt" --prompt-out "$K/same.json"')
    check("verify-cross: --prompt-out == --out -> 10 · nothing run", p.returncode == 10 and not entry and not cli, f"rc={p.returncode}")
    # an adapter pre-gate failure does not leave the previous run's OUT to be read as this run's result (IR-06)
    kd = env.kdir("stale-out")
    with open(f"{kd}/o.txt", "w") as f:
        f.write("OLD RESULT\n")
    p, entry, cli = gate(env, kd, 'review --cd "$GIT_ROOT" --out "$K/o.txt" --uncommitted --expected-branch fz-no-such-branch')
    check("adapter pre-gate failure (branch mismatch) -> 11 · old OUT removed · CLI not called", p.returncode == 11 and not cli and not os.path.exists(f"{kd}/o.txt"),
          f"rc={p.returncode} old_out={os.path.exists(f'{kd}/o.txt')}")
    # availability-probe (fz-review error table): exec · --ephemeral · no role label
    kd = env.kdir("probe", "verify")
    p, entry, cli = gate(env, kd, 'availability-probe --cd "$GIT_ROOT" --out "$K/probe.txt" --prompt-file "$K/p.txt"')
    check("availability-probe: exit 0 · --ephemeral · no role skill", p.returncode == 0 and "--ephemeral" in str(entry) and "--gpt-skill" not in str(entry) and "--inject-skill" not in str(entry),
          f"rc={p.returncode} entry={str(entry)[:200]}")

    # signals (P-13 · R-04): TERM / INT to the gate end the adapter group, release the lock, exit 128+N
    for sig, want, kind in ((signal.SIGTERM, 143, "verify"), (signal.SIGINT, 130, "verify"), (signal.SIGTERM, 143, "independent-plan")):
        tag = f"{tag0}-sig{int(sig)}{kind[:3]}"
        kd = env.kdir(f"s-{tag}", kind)
        args = ('verify --cd "$GIT_ROOT" --out "$K/o.json" --prompt-file "$K/p.txt"' if kind == "verify"
                else 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id s --out-dir "$K/out"')
        rolls = [env.rollout(f"{kd}/r.jsonl", "cat requirement.md")] if kind != "verify" else None
        # INT is ignored on entry when this fixture runs as a background job, and bash cannot trap a signal ignored on entry —
        # restore the default in the child so the cell measures the gate, not how the fixture was launched
        pr = subprocess.Popen(["bash", "-c", 'exec "$GC" ' + args], cwd=env.REPO, env=env.env(kd, {"FZ_SHIM_SLEEP": "30", "FZ_SHIM_TAG": tag}, REVIEW_OK, rolls),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
        for _ in range(40):
            if tagged_alive(tag):
                break
            time.sleep(0.25)
        started = tagged_alive(tag)
        pr.send_signal(sig)
        try:
            pr.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            pr.kill(); pr.communicate()
        time.sleep(4)
        lock = f"{kd}/o.json.lock" if kind == "verify" else f"{kd}/out/gpt-s.json.lock"
        check(f"{signal.Signals(sig).name} during {kind}: exit {want} · adapter group gone · lock released",
              started and pr.returncode == want and not tagged_alive(tag) and not os.path.exists(lock),
              f"started={started} rc={pr.returncode} alive={tagged_alive(tag)} lock={os.path.exists(lock)}")
        subprocess.run(["pkill", "-KILL", "-f", rf"fz-shim\[{tag}\]"], capture_output=True)
    kd = env.kdir("s-recall", "independent-plan")
    p, _, _ = gate(env, kd, 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id s --out-dir "$K/out"', shim_output=capture.shim_body("PLAN_OK"),
                   rollouts=[env.rollout(f"{kd}/r.jsonl", "cat requirement.md")])
    p2, _, _ = gate(env, kd, 'independent-plan --requirement "$K/requirement.md" --arm gpt --run-id s --out-dir "$K/out"', shim_output=capture.shim_body("PLAN_OK"),
                    rollouts=[env.rollout(f"{kd}/r.jsonl", "cat requirement.md")])
    check("independent kind: call · same call again after the end -> 0 · 0", (p.returncode, p2.returncode) == (0, 0), f"{p.returncode},{p2.returncode}")


def discrimination():
    """The golden comparison must be able to fail: a registry change that moves one flag changes the captured argv."""
    reg = json.load(open(os.path.join(R, "scripts", "gpt-kinds.json"), encoding="utf-8"))
    reg["kinds"]["check"]["fixed_args"] = ["--uncommitted"]          # drop --ephemeral
    reg["kinds"]["verify"]["schema"] = "schemas/gpt_peer_review_schema.json"
    reg["kinds"]["review-repro"]["status"] = "stable"
    env = Env(json.dumps(reg))
    try:
        kd = env.kdir("check")
        p, entry, _ = gate(env, kd, 'check --cd "$GIT_ROOT" --out "$K/check.md"')
        gold = json.load(open(os.path.join(capture.HERE, "golden", "check.json"), encoding="utf-8"))
        check("discrimination: registry change (check fixed_args) changes argv vs golden", entry != gold["entry_argv"], str(entry))
        kd = env.kdir("verify")
        p, entry, _ = gate(env, kd, 'verify --cd "$GIT_ROOT" --out "$K/verify.json" --prompt-file "$K/p.txt"')
        check("discrimination: registry change (verify schema) changes argv", "<R>/schemas/gpt_peer_review_schema.json" in (entry[0] if entry else []), str(entry))
        kd = env.kdir("rf", "verify")
        os.makedirs(f"{kd}/repro-review", exist_ok=True)   # a frame kind writes into its own folder (XE-24)
        p, entry, _ = gate(env, kd, 'review-repro --cd "$GIT_ROOT" --out "$K/repro-review/o.json" --prompt-file "$K/p.txt"')
        check("experimental gate is registry-driven (status stable in a proxy copy -> runs)", p.returncode != 10 and bool(entry), f"rc={p.returncode}")
    finally:
        env.close()


def registry_damage():
    env = Env("{not json")
    try:
        kd = env.kdir("broken")
        p, entry, cli = gate(env, kd, 'check --cd "$GIT_ROOT" --out "$K/o.md"')
        check("registry damaged -> 11 · nothing run", p.returncode == 11 and not entry and not cli, f"rc={p.returncode}")
    finally:
        env.close()
    reg = json.load(open(os.path.join(R, "scripts", "gpt-kinds.json"), encoding="utf-8"))
    reg["kinds"]["check"]["inputs"] = "not-an-object"
    env = Env(json.dumps(reg))
    try:
        kd = env.kdir("exc")
        p, entry, cli = gate(env, kd, 'check --cd "$GIT_ROOT" --out "$K/o.md"')
        check("resolver internal error -> 11 (not 1)", p.returncode == 11 and not entry, f"rc={p.returncode} {p.stderr[-120:]}")
    finally:
        env.close()
