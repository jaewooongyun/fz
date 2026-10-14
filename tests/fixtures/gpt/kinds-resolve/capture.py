#!/usr/bin/env python3
"""kinds-resolve fixture — every GPT call kind goes through scripts/gpt-call.sh against the fake CLI (../_shim/codex).

usage: capture.py golden OUT_DIR    write OUT_DIR/<kind>.json — the same shape and path tokens as golden/ (the S0 baseline
                                    capture of the hand-assembled recipes at bf318a7). run.sh diffs the two.
       capture.py cells             behaviour cells (PASS / FAIL lines) — exit 0 when all pass

Hermetic: the fake CLI is first on PATH, HOME is a temp home, the plugin root is a proxy whose gpt-exec.sh /
gpt_independent.sh are stubs that log their argv and then run the real script. Path tokens: <W> temp work · <R> plugin
root (real or proxy) · <ISO> launcher isolation dir · <H> temp home. The caller inputs (prompt files, requirement, diff)
are the files the S0 recipes wrote, kept under inputs/<kind>/.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.realpath(os.path.join(HERE, "..", "..", "..", ".."))
SHIM = os.path.join(R, "tests", "fixtures", "gpt", "_shim", "codex")
ARM = os.path.join(R, "tests", "fixtures", "gpt", "independent-arm")
ISO_RE = re.compile(r"/[^\s\"'\n]*?/fz-gpt-iso\.[A-Za-z0-9]{6}")
REVIEW_OK = json.dumps({"schemaVersion": "1.1", "review_id": "s0", "timestamp": "2026-10-12T00:00:00Z", "review_type": "plan_validation",
                        "issues": [], "summary": {"total_issues": 0, "by_severity": {"critical": 0, "major": 0, "minor": 0, "suggestion": 0}, "by_category": ""},
                        "verdict": "approved", "overall_feedback": "ok", "strengths": []})


class Env:
    """One temp world: fake CLI, proxy plugin root, fixed repo, temp home."""

    def __init__(self, registry_text=None):
        self.T = os.path.realpath(tempfile.mkdtemp(prefix="fz-kinds-resolve."))
        T = self.T
        os.makedirs(f"{T}/bin")
        with open(f"{T}/bin/codex", "w") as f:
            f.write('#!/bin/bash\nif [ "${1:-}" = "--version" ]; then exec "$SHIM_REAL" "$@"; fi\n'
                    'n=$(ls "$CAPDIR" 2>/dev/null | wc -l | tr -d " "); export FZ_SHIM_CAPTURE="$CAPDIR/$(printf %02d "$n").json"\n'
                    'exec "$SHIM_REAL" "$@"\n')
        os.chmod(f"{T}/bin/codex", 0o755)
        self.PX = PX = f"{T}/proxy"
        os.makedirs(f"{PX}/scripts")
        for name in os.listdir(R):
            if name != "scripts":
                os.symlink(os.path.join(R, name), os.path.join(PX, name))
        for name in os.listdir(os.path.join(R, "scripts")):
            if name in ("gpt-exec.sh", "gpt_independent.sh"):
                with open(f"{PX}/scripts/{name}", "w") as f:
                    f.write("#!/bin/bash\n"
                            "python3 -c 'import json,os,sys; open(os.environ[\"FZ_ENTRY_LOG\"],\"a\",encoding=\"utf-8\").write("
                            "json.dumps(sys.argv[1:],ensure_ascii=False)+\"\\n\")' " + name + ' "$@"\n'
                            f'exec bash "{R}/scripts/{name}" "$@"\n')
                os.chmod(f"{PX}/scripts/{name}", 0o755)
            elif name == "gpt-kinds.json" and registry_text is not None:
                with open(f"{PX}/scripts/{name}", "w", encoding="utf-8") as f:
                    f.write(registry_text)
            else:
                os.symlink(os.path.join(R, "scripts", name), f"{PX}/scripts/{name}")
        self.GC = f"{PX}/scripts/gpt-call.sh"
        self.REPO = REPO = f"{T}/repo"
        os.makedirs(f"{REPO}/src")
        with open(f"{REPO}/src/a.ts", "w") as f:
            f.write("a\n")
        g = lambda *a: subprocess.run(["git", "-C", REPO, *a], check=True, capture_output=True)
        g("init", "-q", "-b", "main"); g("config", "user.email", "s0@example.invalid"); g("config", "user.name", "s0")
        g("add", "-A"); g("commit", "-q", "-m", "base")
        with open(f"{REPO}/src/a.ts", "w") as f:
            f.write("b\n")
        self.H = H = f"{T}/home"
        os.makedirs(f"{H}/.codex")
        with open(f"{H}/.codex/auth.json", "w") as f:
            f.write('{"fake":"auth"}\n')
        with open(f"{H}/.codex/config.toml", "w") as f:
            f.write('model = "m-s0"\nmodel_reasoning_effort = "medium"\n')
        self.HREAL = os.path.realpath(H)

    def close(self):
        shutil.rmtree(self.T, ignore_errors=True)

    def kdir(self, name, inputs=None):
        kd = f"{self.T}/k/{name}"
        os.makedirs(f"{kd}/cap", exist_ok=True)
        src = os.path.join(HERE, "inputs", inputs or name)
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                for fn in files:
                    rel = os.path.relpath(os.path.join(root, fn), src)
                    os.makedirs(os.path.dirname(f"{kd}/{rel}"), exist_ok=True)
                    shutil.copy(os.path.join(root, fn), f"{kd}/{rel}")
        return kd

    def env(self, kd, extra=None, shim_output=None, rollouts=None):
        e = {k: v for k, v in os.environ.items() if k not in ("CODEX_HOME", "FZ_GPT_CHOICE_DIR", "CLAUDE_CODE_SESSION_ID", "FZ_SHIM_CAPTURE")}
        e.update({"HOME": self.H, "PATH": f"{self.T}/bin:{e['PATH']}", "SHIM_REAL": SHIM, "CAPDIR": f"{kd}/cap", "FZ_ENTRY_LOG": f"{kd}/entry.jsonl",
                  "FZ_PLUGIN_ROOT": self.PX, "GC": self.GC, "K": kd, "GIT_ROOT": self.REPO, "FZ_TELEMETRY_DIR": f"{kd}/tel",
                  "FZ_SHIM_OUTPUT": shim_output if shim_output is not None else "ok"})
        if rollouts:
            e["FZ_SHIM_ROLLOUT"] = ",".join(rollouts)
        e.update(extra or {})
        return e

    def run(self, kd, script, extra=None, shim_output=None, rollouts=None, cwd=None, timeout=300):
        with open(f"{kd}/run.sh", "w", encoding="utf-8") as f:
            f.write(script)
        p = subprocess.run(["bash", f"{kd}/run.sh"], cwd=cwd or self.REPO, env=self.env(kd, extra, shim_output, rollouts),
                           capture_output=True, text=True, timeout=timeout)
        return p, self.entry(kd), self.cli(kd)

    def entry(self, kd):
        p = f"{kd}/entry.jsonl"
        return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []

    def cli(self, kd):
        return [json.load(open(f"{kd}/cap/{f}", encoding="utf-8")) for f in sorted(os.listdir(f"{kd}/cap"))]

    def norm(self, x):
        if isinstance(x, list):
            return [self.norm(i) for i in x]
        s = ISO_RE.sub("<ISO>", x)
        for a, b in ((self.PX, "<R>"), (R, "<R>"), (self.HREAL, "<H>"), (self.T, "<W>")):
            s = s.replace(a, b)
        return s

    def rollout(self, path, cmd):
        rows = [{"type": "session_meta", "payload": {"id": "s0"}},
                {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": [
                    {"path": {"type": "path", "path": self.HREAL}, "access": "deny"}, {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]}}}},
                {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": f"tools.exec_command({{cmd:{json.dumps(cmd)}}})"}}]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(r) for r in rows) + "\n")
        return path


GC_CALL = '"$GC" '
# kind -> (input dir, recipe, shim output, rollout command or None). The recipe is what a caller writes after S4: kind + inputs.
RECIPES = {
    "review": ("review", GC_CALL + 'review --cd "$GIT_ROOT" --out "$K/review.md" --base main\n', None, None),
    "check": ("check", GC_CALL + 'check --cd "$GIT_ROOT" --out "$K/check.md"\n', None, None),
    "verify": ("verify", GC_CALL + 'verify --cd "$GIT_ROOT" --out "$K/verify.json" --prompt-file "$K/p.txt"\n', REVIEW_OK, None),
    "verify-gates": ("verify-gates", GC_CALL + 'verify-gates --cd "$GIT_ROOT" --out "$K/gv.json" --prompt-file "$K/prompt.txt"\n', None, None),
    "validate": ("validate", GC_CALL + 'validate --cd "$GIT_ROOT" --out "$K/val.json" --prompt-file "$K/p.txt"\n', None, None),
    "search": ("search", GC_CALL + 'search --cd "$GIT_ROOT" --out "$K/search.md" --prompt-file "$K/p.txt"\n', None, None),
    "fix-suggest": ("fix-suggest", GC_CALL + 'fix-suggest --cd "$GIT_ROOT" --out "$K/fix.md" --prompt-file "$K/p.txt"\n', None, None),
    "final": ("final", GC_CALL + 'final --cd "$GIT_ROOT" --out "$K/final.md" --base main --title "[TICKET] PR 전 최종 리뷰"\n'
              + GC_CALL + 'final-deep --cd "$GIT_ROOT" --out "$K/final-deep.md" --prompt-file "$K/p_deep.txt" --session-file "$K/final.md.session"\n', None, None),
    "final-da": ("final-da", GC_CALL + 'final-da --cd "$GIT_ROOT" --out "$K/da.json" --prompt-file "$K/p.txt"\n', None, None),
    "adversarial": ("adversarial", GC_CALL + 'adversarial --cd "$GIT_ROOT" --out "$K/adv.md" --prompt-file "$K/p.txt"\n', None, None),
    "drift": ("drift", GC_CALL + 'drift --cd "$GIT_ROOT" --out "$K/drift.md" --prompt-file "$K/p.txt"\n', None, None),
    "plan": ("plan", GC_CALL + 'plan --cd "$GIT_ROOT" --out "$K/plan.md" --prompt-file "$K/p.txt"\n', None, None),
    "peer-challenger": ("peer-challenger", GC_CALL + 'peer-challenger --cd "$K" --out "$K/gpt-challenger-result.json" --prompt-file "$K/gpt-challenger-prompt.txt"\n', None, None),
    "modernize-verify": ("modernize-verify", 'mkdir -p "$K/verify"\n' + GC_CALL + 'modernize-verify --cd "$K" --out "$K/verify/gpt-verify-v1-result.json" --prompt-file "$K/verify-prompt.txt"\n', REVIEW_OK, None),
    "openai-docs": ("openai-docs", GC_CALL + 'openai-docs --cd "$K" --out "$K/docs.md" --prompt-file "$K/p.txt"\n', None, None),
    "verify-cross": ("verify-cross", GC_CALL + 'verify-cross --audit "$K/audit.json" --cd "$GIT_ROOT" --out "$K/cross.json" --prompt-file "$K/p_verify.txt" --prompt-out "$K/p_cross.txt"\n', REVIEW_OK, None),
    "micro-eval": ("micro-eval", GC_CALL + 'micro-eval --cd "$GIT_ROOT" --out "$K/micro.md" --prompt-file "$K/p.txt"\n', None, None),
    "sprint-contract": ("sprint-contract", GC_CALL + 'sprint-contract --cd "$GIT_ROOT" --out "$K/sc.yaml" --prompt-file "$K/task.txt"\n', None, None),
    "peer-da": ("peer-da", GC_CALL + 'peer-da --cd "$K" --out "$K/gpt-da-result.json" --prompt-file "$K/p.txt"\n', None, None),
    "independent-plan": ("independent-plan", GC_CALL + 'independent-plan --requirement "$K/requirement.md" --repo "$GIT_ROOT" --deny "$K" --keep-iso --arm gpt --run-id s0 --out-dir "$K/plan/gpt-independent"\n'
                         'ISO="$(python3 -c \'import json,sys; print(json.load(open(sys.argv[1])).get("iso") or "")\' "$K/plan/gpt-independent/gpt-s0.audit.json")"\n'
                         '[ -n "$ISO" ] && "${FZ_PLUGIN_ROOT}/scripts/gpt_independent.sh" cleanup --iso "$ISO" >/dev/null\n', "PLAN_OK", "cat requirement.md"),
    "independent-review": ("independent-review", GC_CALL + 'independent-review --diff "$K/diff.patch" --base "$K/base" --head "$K/head" --deny "$K" --arm gpt --run-id s0 --out-dir "$K/gpt-independent"\n',
                           "REVIEW_IND_OK", "cat diff.patch"),
}


def shim_body(tag):
    if tag == "PLAN_OK":
        return open(f"{ARM}/sample-plan-ok.json", encoding="utf-8").read()
    if tag == "REVIEW_IND_OK":
        return open(f"{ARM}/sample-review-ok.json", encoding="utf-8").read()
    return tag


def prepare(env, kind):
    """Create the kind's work dir with its inputs (and the verify-cross audit / isolation home)."""
    kd = env.kdir(kind, RECIPES[kind][0])
    if kind == "verify-cross":
        iso = f"{kd}/fz-gpt-iso.S0CAPT"
        os.makedirs(f"{iso}/gpt-home", exist_ok=True)
        with open(f"{kd}/audit.json", "w") as f:
            json.dump({"iso": iso, "sessionFile": f"{kd}/prev.json.session"}, f)
    return kd


def golden(out):
    env = Env()
    try:
        os.makedirs(out, exist_ok=True)
        for kind, (_, script, body, roll) in RECIPES.items():
            kd = prepare(env, kind)
            rolls = [env.rollout(f"{kd}/r.jsonl", roll)] if roll else None
            p, entry, cli = env.run(kd, script, shim_output=shim_body(body) if body else None, rollouts=rolls)
            with open(f"{kd}/stdout.txt", "w") as f:
                f.write(p.stdout + "\n--stderr--\n" + p.stderr)
            parts = [(kind, entry, cli)] if kind != "final" else [("final", entry[0:1], cli[0:1]), ("final-deep", entry[1:2], cli[1:2])]
            for k2, e2, c2 in parts:
                rec = {"entry_argv": env.norm(e2), "cli_argv": env.norm(c2), "exit": p.returncode}
                with open(f"{out}/{k2}.json", "w", encoding="utf-8") as f:
                    json.dump(rec, f, ensure_ascii=False, indent=1)
            print(f"{kind:20s} exit={p.returncode:3d} entry={len(entry)} cli={len(cli)}")
    finally:
        env.close()


if __name__ == "__main__":
    if sys.argv[1:2] == ["golden"] and len(sys.argv) == 3:
        golden(sys.argv[2])
    elif sys.argv[1:2] == ["cells"]:
        import cells   # noqa: E402 — behaviour cells live next to this file
        sys.exit(cells.main())
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
