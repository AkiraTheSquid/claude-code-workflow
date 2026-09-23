---
name: feedback-skip-permission-for-dev-installs
description: "Don't ask permission for routine dev-env installs/configs while testing; just install + report"
metadata: 
  node_type: memory
  type: feedback
---

When mid-task and you discover a missing dev-env dependency that's blocking the work (e.g. backend grader missing torch), don't pause to ask "should I install?" — just install, pin to requirements, and continue. Same for similar low-risk dev-env actions: pip installs of expected deps, restarting a dev server, adding a missing config line.

**Why:** User explicitly said "you can just skip asking me for permissions" on 2026-05-24 after I asked whether to install torch CPU into the backend venv to unblock E2E grader testing. Asking creates friction when the answer is obviously yes.

**How to apply:** Routine = install matches what the code already expects (e.g. RUNTIME_CONTRACT.md said backend was supposed to have torch), is reversible (`pip uninstall`), and stays in dev env. Still confirm for: prod deploys, dependency changes that swap a library family (numpy → jax), anything touching shared infrastructure, anything >1GB unless clearly needed. See also [[feedback_apply_obvious_fixes]] — same spirit.
