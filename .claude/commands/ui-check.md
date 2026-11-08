---
description: Screenshot the app at phone and desktop widths in light and dark and report layout problems (Tester, fixes nothing)
allowed-tools: Bash(python scripts/ui_check.py:*), Bash(python3 scripts/ui_check.py:*), Bash(*/bin/python scripts/ui_check.py:*), Bash(ls:*), Read, Glob
---

Role: Tester. Report problems; fix nothing.

1. Run `.venv/bin/python scripts/ui_check.py <scratchpad>/ui_check` (plain `python` in CI and the cloud, where there is no venv) with the session scratchpad directory as the output directory (it must be outside the repo). Pass `--ids member=ID committee=ID ticker=ID` only if the owner gave ids.
2. Exit codes: 0 clean, 1 page-level overflow or a page that did not finish loading, 2 environment problem (Playwright missing, browsers missing, no `congress.db`, server did not start). On 2, report the message and stop.
3. Use Read on a few of the screenshots (at least one at 390 and one at 1280, light and dark) to judge what the script cannot: cut-off text, clipped controls, low contrast.
4. Report per view, width and theme: PASS or the issues found, combining the script's lines with what you saw in the images. Tap-target findings at 390 are advisory.
5. Do not change code, tests or settings.

Notes:
- Use the interpreter that has both playwright and streamlit: `.venv/bin/python` locally. Plain `python` on a Mac may be a global install that fails on streamlit or lacks playwright.
- macOS: there is no `/opt/pw-browsers`. Set `PLAYWRIGHT_BROWSERS_PATH` to a folder holding a chromium build (for example `PLAYWRIGHT_BROWSERS_PATH=/some/dir .venv/bin/python -m playwright install chromium`, only if the owner asks to install) and use the same variable when running the script.
- The playwright version must match the installed chromium build: run `ls /opt/pw-browsers` (for example playwright 1.56.0 for chromium-1194). Install nothing unless the owner asks.
- Only the default state is captured (USD, default volume basis, Settings expander closed). EUR, the other volume basis and the opened Settings expander at 390 are not checked.

Environment dependencies: the Python package `playwright` (not in `requirements.txt`) and browsers in `/opt/pw-browsers` (cloud) or in `PLAYWRIGHT_BROWSERS_PATH` (local). If either is missing, say so; do not install anything unless the owner asks.
