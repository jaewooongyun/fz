#!/bin/sh
# fz-compact guard, a classic PreCompact hook. It is meant to keep the engine from making a model summary of a
# compaction fz-compact queued (custom_instructions exactly fz-compact:resume or fz-compact:idle:<digits>) that
# the fz-compact session.compact hook did not answer: a hook ahead of it passed the event by (a seated
# cc-plugin-sec-default does), or that hook failed and was skipped.
# A plugin's classic hook sits in core, after the hooks modules, so this script is expected to run only when
# core compacts; when the fz-compact hook answers, core does not run and neither does this script.
# The marker shapes copy register.ts (MARKER, IDLE_MARKER, RESUME_MARKER and the digits markerOf accepts), and
# tests/guard_test.sh fails when those lines change. Unlike register.ts, it does not require trigger manual and
# does not drop trailing space.
# Exit 2 blocks, and the stderr line is the skip notice. Every other input exits 0. There is no set -e: any
# other nonzero exit would count as a failed hook, which lets core summarize.
input=$(cat)
if printf '%s' "$input" | grep -Eq '"custom_instructions" *: *"fz-compact:(resume|idle:[0-9]+)"'; then
  printf '%s\n' 'fz-compact: skipped a compaction fz-compact queued but its hook did not answer, so the session is not summarized' >&2
  exit 2
fi
exit 0
