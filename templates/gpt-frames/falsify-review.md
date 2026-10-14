Frame: falsification (code review).

Beyond the default review, actively try to break this change: find an input, state or ordering under which the
change's own checks still pass but the stated requirement or an existing behaviour fails. A concrete counterexample
beats a general concern.

- Report only correctness defects and requirement impact. No style, naming or refactoring notes.
- For each issue give the triggering input / state / order, the expected versus the actual outcome, and quote the
  diff line it hits.
- You may confirm read-only (read files, run commands that write nothing). Do not write files.
- If nothing breaks, say so. Do not lower the bar to produce findings.
