# Changelog

Newest first. Each entry lists what changed for the user and how it was verified
(see "Development loop" in the README).

## Session hooks and CLAUDE.md
- `.claude/settings.json` registers three Claude Code hooks (scripts in `.claude/hooks/`):
  - `session_start.sh` (cloud sessions only): installs `requirements.txt` plus reportlab, fetches `congress.db` from the `data` branch if it is missing or older than 12 hours, and prints the top of `docs/CONTEXT.md`. It never fails the session.
  - `guard_paths.py`: asks for confirmation before edits to `congress.db`, `.github/workflows/` and `.streamlit/config.toml`, with a best-effort check on Bash commands.
  - `on_stop.py`: runs the unit tests when a `.py` file changed and blocks the stop (exit 2) if they fail; warns when code changed without a `CHANGELOG.md` entry.
- Added `CLAUDE.md`, which points to `AGENTS.md` and `docs/CONTEXT.md`. `.gitignore` now ignores `.claude/settings.local.json` and `.claude/.cache/`.
- Verified: hooks run in a throwaway copy (fresh cloud fetch; repeat run in 0.02s; failed fetch keeps the existing database; local mode silent; guard allow and ask cases; stop hook pass, fail and warning cases), unit tests, and `tests/ui_smoke.py` (0 failures).
- Not checked: a live Claude Code session triggering the hooks, `${CLAUDE_PROJECT_DIR}` expansion in the harness, a truly fresh container install, the 120s test timeout.
- Known limits: the Bash guard has false positives (`cp congress.db /tmp/x`, `>` inside SQL) and a false negative (Python writing the file). The stop hook runs the full unit tests (about 15s or more) whenever any `.py` file is uncommitted, and the CHANGELOG warning fires on any uncommitted code change.

## Agents and project context
- Added `AGENTS.md` (Planner, Builder, Designer, Tester, Documenter and their hand-offs), subagent files in `.claude/agents/`, and `docs/CONTEXT.md` for resuming after a session clear.
- Verified: documentation only; no code changed.

## Colour palette
- App theme set in `.streamlit/config.toml` from the Color Hunt palette (cream, blue, deep blue, black), with a derived dark theme; caption colours in `app.py` follow it. Chart series keep their colour-blind-safe colours.
- Verified: unit tests and the UI smoke test (0 failures). Not checked: the deployed app's data grids in both themes.

## UX round 3: accessibility
- Captions: higher contrast and slightly larger text (light and dark mode).
- "Download as CSV" under the main tables (member, committee and ticker trades, top tickers): a plain-file alternative to
  Streamlit's canvas-drawn grids, which screen readers can't read well. Amounts in the file are in USD.
- Broker table and the missing-paper-filings list are now real HTML tables with descriptive link text ("Open DEGIRO",
  "Open filing 9116249 (PDF)") instead of repeated "open".
- Chart data available as a table (round 2); colour is never the only signal (price change carries a +/- sign).
- Known limits: Streamlit draws data grids on a canvas and gives limited control over keyboard focus after a view change;
  a full screen-reader and keyboard audit is still to do.

## UX round 2: navigation and charts
- Shareable links: the URL now carries the view and the selected member / committee / ticker (`?view=Ticker&id=NVDA`);
  opening such a link restores that page, and an unknown id falls back safely.
- Monthly volume chart rebuilt: title, axis labels with units, compact axis numbers ($50M), colour-blind-safe colours,
  tooltips, and a "show as a table" alternative. Follows the USD/EUR switch.
- Headline volume shown compactly ($102M) with the exact figure in its tooltip.
- Clearer "tick the box to open" hint on clickable tables; overview tables stacked full width and headline labels shortened so nothing is cut off.
- Not done: moving the View switch from the sidebar to top tabs (Streamlit can't select a tab from code, which the row
  click-through needs).
- Verified: unit tests, UI smoke test (now including shared links), live check.

## UX round 1: readability
- Overview: headline numbers strip (trades, members, volume, newest disclosure); the two overview tables show only the key
  columns so nothing is cut off; explanatory text moved into a "How to read this data" expander; one-line coverage notice.
- Plain-language column headers everywhere (Trade date, Amount range, Role, ...).
- Empty state for members without committee assignments.
- Verified: unit tests, UI smoke test in CI, live check of the deployed app.

## Earlier
- Click-through from Overview rows to the Member / Committee / Ticker views; Name column in Top tickers.
- P/E, forward P/E and PEG per ticker.
- Prices (nightly close), EUR conversion (ECB rate), exchange per ticker, Dutch broker availability.
- Fix: Member view crashed for members without paper filings (pandas 3 empty-frame string concat).
- Contentsquare tag and consent banner added, then removed again.
