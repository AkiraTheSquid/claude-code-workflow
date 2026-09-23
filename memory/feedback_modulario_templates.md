---
name: Fill Modulario README/watch.py templates in place, never overwrite
description: When filling Modulario-generated README.md or watch.py templates, always Read-then-Edit the stubs; never use Write to replace the whole file
type: feedback
---
When a folder has an unfilled Modulario template (`README.md` with `<!-- modulario:template -->` or `watch.py` with `# modulario:template` on line 1), fill it by **reading the file and editing the stub sections in place**. Do not use `Write` to replace the whole file, even if the replacement content looks complete.

**Why:** Modulario owns these files. The marker comment on line 1 is a state flag it watches; the stub functions in `watch.py` are a contract (`check_imports` / `check_public_api` / `check_invariants`) that the runner expects. Using `Write` to overwrite with fresh content:
1. Bypasses the read-first guardrail, so the first attempt fails with "File has not been read yet."
2. Treats the template as scratch paper instead of a scaffold — semantically "destroys" it even when the replacement looks similar.
3. Can race with Modulario's auto-regeneration: if a session resumes or analysis re-runs, Modulario sees a missing/unfilled script and writes a blank template over your work.

This bit me on 2026-04-14 in Delta-Note when filling 7 `watch.py` files for `app_modules/` subfolders. The user corrected me: *"the reason you keep getting errors is that modulario automatically fills the watcher and readme.md files if they don't already exist. you need to fill in what's there manually, modifying the templates rather than destroying them."*

**How to apply:**
- **watch.py:** `Read` the template → `Edit` each stub function body (replace `pass  # e.g. ...` with real assertions) → `Edit` line 1 to remove `# modulario:template` → leave the `if __name__ == '__main__':` runner block untouched.
- **README.md:** `Read` the template → `Edit` each section (`Purpose`, `Owns`, `Does NOT own`, `Key Files`, etc.) to replace placeholder bullets with real content → `Edit` line 1 to remove `<!-- modulario:template -->`.
- Preserve the section/function skeleton Modulario generated. Add helpers (e.g. `_pyside_available()`) around the stubs, not in place of them.
- If a check needs to import the parent package and that package pulls in heavy deps (PySide6, psycopg2), guard the check with a `_<dep>_available()` helper and return early when the dep is missing — `mod watch` runs in a minimal environment.
- For pure-Python files that can't be imported in isolation (e.g. a module with `@dataclass` + `from __future__ import annotations`, which requires `sys.modules[__module__]`), fall back to `open()` + text-grep for required symbols instead of `exec()`/`importlib.util`.
