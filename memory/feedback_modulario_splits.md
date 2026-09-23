---
name: Split files when Modulario goes ORANGE/RED mid-edit
description: User wants extraction into sibling modules, not more LOC in already-warning files
type: feedback
---
When the `[Modulario]` block shows ORANGE or RED for the file you just edited, stop adding LOC to it. Extract the new code into a sibling module (factory/integration pattern) and import it back in a few lines.

**Why:** User called this out after `weekly_long_term_goals.js` went RED (401→421 LOC) mid-feature — they asked "Is it really necessary to keep things all in one file? Can't you see the NAC notifications?". They expect active response to the structural-health feedback, not continued growth of the warned file.

**How to apply:** On an ORANGE/RED status for the file currently being edited, pivot: create a new file (e.g. `<view>_<feature>_integration.js` or a shared factory in the relevant js/ folder) that owns the new state + controller + load + handlers, exporting a factory. The original file imports and wires it in a few lines. Applies even mid-feature — don't "finish first, split later".
