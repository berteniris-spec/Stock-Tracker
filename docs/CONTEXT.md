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
- Volume is a midpoint estimate of filed ranges; committee membership is a current snapshot, not as of the trade date.

## Open work
- Mobile and readability pass (proposed, not started): controls out of the sidebar, shorter top of page, two-up metrics, narrower tables, tabs on the Ticker view, quarterly chart labels, phone-width screenshots in the smoke test.
- Workflow tooling ideas not done: slash commands `/ship`, `/resume`, `/ui-check`; a Claude PR review GitHub Action; scheduled data-health checks; a Playwright MCP server; a permissions allowlist.
- Hooks are untested in a live Claude Code session (see Known limits).
- Senate trades (no bulk download; CSV load only).
- OCR for scanned paper filings (`no_text`); review `partial` filings; former members' filings (`unmatched_member`) are skipped.
- Full screen-reader and keyboard audit.
- Check the deployed app's data grids and chart in both themes after the palette change.

## Known limits
Filings lag trades by up to 45 days. Sector is unknown for trades with no ticker. Unmapped tickers are never flagged committee-relevant. EUR uses one latest rate for all dates.

Hooks: not yet seen firing in a live session; `${CLAUDE_PROJECT_DIR}` expansion, a fresh container install and the 120s test timeout are unchecked. The Bash guard has false positives (`cp congress.db /tmp/x`, `>` in SQL) and a false negative (Python writing the file). The stop hook runs the full unit tests (15s or more) whenever any `.py` file is uncommitted, and its CHANGELOG warning fires on any uncommitted code change.
