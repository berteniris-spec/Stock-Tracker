# Project context

Read this first after a session clear. Keep it under about 50 lines; history belongs in `CHANGELOG.md`. Last updated: 2026-11-09 (redesign).

## What this is
Congress trades: a personal Streamlit dashboard joining US congressional stock trades to committee membership and estimated volume. SQLite, runs locally or on Streamlit Community Cloud from `main`. Public repo, no secrets, non-commercial.

## Current state
- `main` has the mobile pass steps 1 to 7, the logo (PR #13) and the venv instructions. No PRs are open.
- The workflow changes (PR #14, merged) are: `scripts/test.sh`, wider permissions, a size-the-loop table in `AGENTS.md`, shorter agent briefs, this shorter file, and `styles.py` (CSS moved out of `app.py`).

## How it fits together
- `app.py`: the Streamlit app. Views Overview, Member, Committee, Ticker; view and id live in the URL (`?view=Ticker&id=NVDA`). Row clicks go through `_goto` in session state. `styles.py`: the page CSS.
- `db.py` schema and queries; `house_importer.py` House PDFs; `ingest_committees.py`; `enrich_sectors.py`; `prices.py`; `brokers.py`; `load_trades.py`, `load_sample.py`. These stay at the repo root because the nightly workflow runs them by path.
- Data: the nightly `House import` workflow rebuilds `congress.db` and force-pushes it to the `data` branch; the app downloads it on first start. `congress.db` is git-ignored.
- CI (`ci.yml`) fetches the database and runs `tests/test_*.py` and `tests/ui_smoke.py`. `scripts/wait_ci.sh` waits for a run.
- Tests: `scripts/test.sh [--smoke]`. UI check: `.venv/bin/python scripts/ui_check.py <dir>` (Playwright, not a repo dependency; version must match the Chromium build).

## Workflow
Roles and the loop are in `AGENTS.md` (size the loop to the change). Slash commands: `/ship`, `/resume`, `/ui-check`. Hooks in `.claude/settings.json`: cloud session start installs and fetches the database; the path guard asks before editing protected paths; the stop hook runs `scripts/test.sh` when a `.py` file changed. Hooks, commands and permissions have not been seen in a live session. Commit straight to `main` after tests pass (owner's choice, 2026-11-08); PRs only when the owner asks.

## Design
- Design system: https://claude.ai/artifact/FKb1gTaSePVdEYWRPffmuA (private). Theme in `.streamlit/config.toml` (cream `#efece3`, blue `#8fabd4`, deep blue `#4a70a9`; dark derived). Chart colours are Okabe-Ito.
- Logo: PNG (the SVG is an incomplete trace), full colour on both themes, above the h1, not a link, 48px high at 640px and narrower, 64px wider.
- Copy: plain-language, sentence case, `n/a` in metrics and blank in tables for missing values, compact headline amounts (`$102M`) with exact figures in tooltips and a visible caption.

## Decisions that still bind
- No approval gates between agents; they stop only for the cases in `AGENTS.md`.
- No sidebar. View switch is a horizontal `st.radio` (key `page`); Settings expander holds basis, currency and Refresh. Help text that carries meaning is a visible caption, not a tooltip.
- Metric strips are two per row at 640px and narrower; labels 18 characters or fewer (`check_metrics` enforces it).
- Phone tables swap at 640px: both renderings are in the page and CSS shows one (`st-key-ph_*` / `st-key-tbl_*`). Rankings are button rows; trade and member tables are a wrapping `st.table` (max 25 rows) with a "Show all columns" checkbox.
- Ticker view uses plain `st.tabs(["Trades", "Price", "Brokers"])`: no tab in the URL, so a shared link opens Trades.
- Brokers are collapsed expanders plus a table in an expander.
- Volume is a midpoint estimate of filed ranges; committee membership is a current snapshot.
- Risk: `styles.py` targets Streamlit 1.66.x DOM (`stRadioOption`, `stMetricValue`, `stLayoutWrapper`, `stTable`, `[role="tab"]`, `st-key-*`, `st.image`). After any Streamlit upgrade run `/ui-check`. `requirements.txt` pins `streamlit>=1.66.1,<1.67`; bump it deliberately.

## Redesign (2026-11-09)
Top bar plus Settings popover, pill nav (`page` radio), search (`search`), card metrics, lighter theme (`config.toml` changed with the owner's OK), clickable ranking rows (`rank_*` containers, `open_ov_*` buttons) at all widths, party dot + word, ▲/▼ trade types, net-buying and sector charts, Member and Committee headers. The old desktop ranking tables and the `ph_ov_` swap are gone. Dark theme not yet reviewed visually.

## Health check (2026-11-09)
Ticker Price tab: four cards from `fundamentals.py` (zones, headlines, range-bar HTML) over `ticker_fundamentals` (new table, filled by `prices.update_fundamentals` nightly). Sector medians via `db.sector_medians`. Needs one nightly run to have real data; check the workflow log line "health metrics stored for N/M stocks" and that Yahoo field scaling (`debtToEquity` percent, `trailingAnnualDividendYield` fraction) is right.

## Open work
- Mobile pass: steps 1 to 7 done; no step 8 is defined.
- Owner decides whether to rename the Price tab to "Price and ratios".
- Small: focus ring after mouse clicks (`:focus-within` vs `:focus-visible`); dataframe `help=` for P/E and PEG in `LABELS`; delta-down red on pink is about 3.9:1; Brokers tab is long at 320px.
- Owner: a square mark for a favicon; design system updates (SVG trace, `Logo.md`, Tabs pattern, README metric strips and Tables rule).
- Ideas: Claude PR review Action; scheduled data-health checks; Playwright MCP server.
- Data: Senate trades (CSV only); OCR for scanned filings; review `partial` filings; former members' filings are skipped.
- Full screen-reader and keyboard audit; check the deployed app's grids and chart in both themes.

## Known limits
Filings lag trades by up to 45 days. Sector is unknown for trades with no ticker. Unmapped tickers are never flagged committee-relevant. EUR uses one latest rate for all dates. UI work was checked in Chromium only (see `CHANGELOG.md` for what each step covered and skipped): not Safari, Firefox, real touch, screen readers or the deployed app. `ui_check.py` captures only the default state (USD, default basis, Settings closed).

## Next step
Review the redesign in dark theme and on a real phone; then the small items under Open work.
