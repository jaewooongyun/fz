Frame: execution reproduction (code review).

For each suspected defect, try to reproduce it with commands or tests that write nothing to disk. Mark a defect as
reproduced only when you include the exact command and its output.

- The sandbox is read-only. A write attempt fails with "Operation not permitted" (EPERM). That is the environment,
  not a defect of the change: do not report it, and do not count a test you could not run as passing or failing.
  Say it was not runnable.
- Report only correctness defects and requirement impact. No style, naming or refactoring notes.
