---
description: Screenshot the app at phone and desktop widths in light and dark and report layout problems (Tester, fixes nothing)
allowed-tools: Bash(python scripts/ui_check.py:*), Bash(ls:*), Read, Glob
---

Role: Tester. Report problems; fix nothing.

1. Run `python scripts/ui_check.py <scratchpad>/ui_check` with the session scratchpad directory as the output directory (it must be outside the repo). Pass `--ids member=ID committee=ID ticker=ID` only if the owner gave ids.
2. Exit codes: 0 no page-level overflow, 1 page-level overflow, 2 environment problem (Playwright missing, browsers missing, no `congress.db`, server did not start). On 2, report the message and stop.
3. Use Read on a few of the screenshots (at least one at 390 and one at 1280, light and dark) to judge what the script cannot: cut-off text, clipped controls, low contrast.
4. Report per view, width and theme: PASS or the issues found, combining the script's lines with what you saw in the images. Tap-target findings at 390 are advisory.
5. Do not change code, tests or settings.

Environment dependencies: the Python package `playwright` (not in `requirements.txt`) and browsers in `/opt/pw-browsers`. If either is missing, say so; do not install anything unless the owner asks.
