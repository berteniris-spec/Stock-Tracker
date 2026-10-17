# Project context

Read this first after a session clear. Keep it short and true; the Documenter refreshes it after every change. Last updated: 2026-10-17.

## What this is
Congress trades: a personal Streamlit dashboard that joins US congressional stock trades to committee membership and estimated volume. SQLite database, runs locally or on Streamlit Community Cloud from the `main` branch. Public repo, no secrets. Keep use non-commercial.

## How it fits together
- `app.py`: the Streamlit app. Views: Overview, Member, Committee, Ticker. The view and selected id live in the URL (`?view=Ticker&id=NVDA`). Table rows open other views through `_goto` in session state.
- `db.py`: schema and all queries. `house_importer.py`: House Clerk PDF import. `ingest_committees.py`: members and committees. `enrich_sectors.py`: sectors from FinanceDatabase. `prices.py`: closes, ratios and the ECB EUR rate. `brokers.py`: Dutch broker availability. `load_trades.py`, `load_sample.py`: CSV load and fictional demo rows.
- Data: the nightly `House import` workflow rebuilds `congress.db` and force-pushes it to the `data` branch. The app downloads it on first start; the sidebar button refreshes it. `congress.db` is git-ignored.
- CI (`ci.yml`): fetches the database, runs `tests/test_*.py` and `tests/ui_smoke.py`. `scripts/wait_ci.sh` waits for a run.

## Workflow
Roles and the loop are in `AGENTS.md` (Planner, Builder, Designer, Tester, Documenter; subagents in `.claude/agents/`). Dev loop: build, test, document (see `README.md`). Branch off `main`; open a PR only when the owner asks; merge only when the owner says.

Slash commands (`.claude/commands/`): `/ship` (tests, doc check, commit and push on a branch; stops before PR or merge), `/resume` (read-only summary of context, branch, open PRs, next step), `/ui-check` (runs the script below, reads a few screenshots, fixes nothing).

`scripts/ui_check.py`: starts the app headless and screenshots Overview, Member, Committee and Ticker at 390px and 1280px, light and dark, with Playwright and the preinstalled Chromium. Reports page-level sideways scroll (names the widest element), overflowing elements, cut-off text suspects and, at 390 only, tap targets under 44px (advisory). Exit 0 clean, 1 page-level overflow or load failure, 2 environment problem. Playwright is not a repo dependency: the interpreter must import `playwright` and `streamlit`, and the Playwright version must match the Chromium build (1.56.0 for chromium-1194).

Permissions in `.claude/settings.json` (applies to everyone using Claude Code here): allow read-only git, `ls`, `python tests/test_*.py`, `python tests/ui_smoke.py`, Read, Glob, Grep; ask for `git add`, `commit`, `push`; deny `rm`, `mv`, `curl`, `wget`.

`CLAUDE.md` points Claude Code to `AGENTS.md` and this file. Hooks in `.claude/settings.json` (scripts in `.claude/hooks/`):
- `session_start.sh`: cloud sessions only; installs requirements plus reportlab, fetches `congress.db` from the `data` branch if missing or over 12 hours old, prints the top of this file. Never fails the session.
- `guard_paths.py`: asks before edits to `congress.db`, `.github/workflows/`, `.streamlit/config.toml`; best-effort Bash check.
- `on_stop.py`: runs unit tests when a `.py` file changed and blocks the stop on failure; warns when code changed without a CHANGELOG entry.

## Design
- Design system: https://claude.ai/artifact/FKb1gTaSePVdEYWRPffmuA (private; tokens, README, components Metric, Notice, DataTable, VolumeChart).
- Theme in `.streamlit/config.toml`, from Color Hunt: cream `#efece3`, blue `#8fabd4`, deep blue `#4a70a9`, black. A dark theme is derived. Deep blue is 4.3:1 on cream: controls and large text only.
- Chart series use the colour-blind-safe Okabe-Ito colours, not the palette.
- Copy: plain-language headers, sentence case, `n/a` in metrics and blank in tables for missing values, compact headline amounts (`$102M`) with exact figures in tooltips.

## Decisions
- No approval gates between agents; they stop only for the cases in `AGENTS.md`.
- Hooks guard and verify instead of adding approval gates: the stop hook enforces passing tests, the path guard asks only for the database, workflows and theme (the "When to stop" cases). They are best-effort and must never break a session start.
- Streamlit cannot select a tab from code, so the view switch stays a widget, not top tabs.
- Broker list uses collapsed expanders (phone width) plus a table in an expander for comparison. Cost: on desktop, comparing brokers takes a click. Chosen so the page never scrolls sideways at 390px while keeping a real table for screen readers and comparison.
- The paper-filing notice is one status caption plus one "About this data" expander, to shorten the top of every view.
- Volume is a midpoint estimate of filed ranges; committee membership is a current snapshot, not as of the trade date.

- `ui_check.py` reports and fixes nothing; it exits 1 only for page-level overflow or a failed load, so small tap targets never fail it. Playwright stays out of `requirements.txt` so CI and the cloud install are unchanged.
- Permissions: routine read-only and test commands need no prompt; anything that records or publishes (`git add/commit/push`) asks; destructive or network shell tools are denied.

## Open work
- Mobile and readability pass, on branch `claude/mobile-pass-1` (uncommitted when written). Re-run `/ui-check` after each step.
  - Step 1 DONE: Ticker broker overflow fixed (eight expanders plus a table alternative in a scroll box); top of page shortened to one coverage caption and one "About this data" expander; 44px expander headers and link buttons. Page-level scroll at 390 is now zero in all 1280 views.
  - Step 2: move the controls out of the sidebar. Also update `tests/ui_smoke.py` (drives `at.sidebar.radio`) and `scripts/ui_check.py`.
  - Step 3: two-up metrics. Step 4: narrower tables. Step 5: tabs on the Ticker view. Step 6: chart polish (quarterly labels). Step 7: readability.
  - Small items from step 1: add a visual hint that the broker table's Link column scrolls off to the right; make "Refresh data from GitHub" a 44px target (26x480 now, ours); missing-filings links wrap to three lines at 390. The rest of the small targets are Streamlit chrome (sidebar toggle 28x28, Deploy 57x28, Main menu 28x28, heading anchors 16x16) and are not ours to fix.
  - Design system README still says "use a real table for short lists with links"; it needs the new pattern recorded (expanders for phone width plus a table alternative).
- Workflow tooling ideas left for the owner to decide: a Claude PR review GitHub Action (needs a workflow file and an API-key secret); scheduled data-health checks (an unattended external task); a Playwright MCP server (runs a third-party package at session start).
- Hooks, slash commands and the permission rules are untested in a live Claude Code session (see Known limits).
- Senate trades (no bulk download; CSV load only).
- OCR for scanned paper filings (`no_text`); review `partial` filings; former members' filings (`unmatched_member`) are skipped.
- Full screen-reader and keyboard audit.
- Check the deployed app's data grids and chart in both themes after the palette change.

## Known limits
Filings lag trades by up to 45 days. Sector is unknown for trades with no ticker. Unmapped tickers are never flagged committee-relevant. EUR uses one latest rate for all dates.

`ui_check.py` captures only the default state (USD, default volume basis, sidebar as rendered at load); EUR, volume basis and the open sidebar at 390 are not checked. The 390 screenshots are viewport height (the page scrolls inside `stMain`). Tap-target counts are advisory. Mobile step 1 was checked in a browser only on the default state: EUR and the Filed minimum basis were AppTest only, and the open sidebar at 390 and the deployed app were not checked. The slash commands and permission rules have not been seen working in a live session.

Hooks: not yet seen firing in a live session; `${CLAUDE_PROJECT_DIR}` expansion, a fresh container install and the 120s test timeout are unchecked. The Bash guard has false positives (`cp congress.db /tmp/x`, `>` in SQL) and a false negative (Python writing the file). The stop hook runs the full unit tests (15s or more) whenever any `.py` file is uncommitted, and its CHANGELOG warning fires on any uncommitted code change.
