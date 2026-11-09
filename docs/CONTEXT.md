# Project context

Read this first after a session clear (`/resume` summarises it). Keep it under about 50 lines; history belongs in `CHANGELOG.md`. Last updated: 2026-11-09.

## What this is
Congress trades: a personal Streamlit dashboard joining US congressional stock trades to committee membership and estimated volume. SQLite, runs locally or on Streamlit Community Cloud from `main`. Public repo, no secrets, non-commercial.

## Current state
`main` has the mobile pass (steps 1 to 7), the redesign, table links, the Ticker health check and price history. No PRs are open. Details per change are in `CHANGELOG.md`.

## How it fits together
- `app.py`: the Streamlit app. Views Overview, Member, Committee, Ticker; view and id live in the URL (`?view=Ticker&id=NVDA`). Clicks go through `_goto` in session state. `styles.py`: the page CSS. `fundamentals.py`: health-check zones, headlines and range-bar HTML.
- `db.py` schema and queries; `house_importer.py`; `ingest_committees.py`; `enrich_sectors.py`; `prices.py`; `brokers.py`; `load_trades.py`, `load_sample.py`. They stay at the repo root because the nightly workflow runs them by path.
- Data: the nightly `House import` workflow rebuilds `congress.db` (prices, valuation, `ticker_fundamentals`, `ticker_price_history`) and force-pushes it to the `data` branch; the app downloads it on first start. `congress.db` is git-ignored (about 20 MB with history).
- CI (`ci.yml`) runs `tests/test_*.py` and `tests/ui_smoke.py`. Tests: `scripts/test.sh [--smoke]`. UI check: `.venv/bin/python scripts/ui_check.py <dir>`.

## Workflow
Roles and the loop: `AGENTS.md` (size the loop to the change). Commands: `/ship`, `/resume`, `/ui-check`. Commits and pushes run without prompts; force-push and branch deletion are denied. `guard_paths.py` asks only for real writes to `congress.db`, workflows, `config.toml` and schema edits in `db.py`. Commit straight to `main` after tests pass; PRs only when the owner asks.

## Design
- Design system: https://claude.ai/artifact/FKb1gTaSePVdEYWRPffmuA (private). Theme in `.streamlit/config.toml` (light: cream `#f4f2ec`, primary `#1f3a5f`; dark derived). Chart colours are Okabe-Ito; zones and trade types never rely on colour alone.
- Top bar: 40px logo and title, Settings popover (basis, currency, refresh). Pill view switch (`page` radio), search box (`search`), metric cards.
- Copy: plain-language, sentence case, `n/a` in metrics and blank in tables for missing values, compact headline amounts with exact figures in a visible caption.

## Decisions that still bind
- No approval gates between agents; they stop only for the cases in `AGENTS.md`.
- No sidebar. Meaningful help text is a visible caption, not only a tooltip.
- Metric labels 18 characters or fewer (`check_metrics`); strips two per row at 640px and narrower.
- Phone tables swap at 640px (`st-key-ph_*` / `st-key-tbl_*`). Rankings are one list of button rows at every width (`rank_*`).
- Tables link onward by clicking a cell (no checkbox column) plus an "Open … from this table" picker (works on a phone).
- Ticker view: `st.tabs(["Trades", "Price", "Brokers"])`, no tab in the URL.
- Health check zones say lower, typical or higher, never good or bad; analyst views are worded as opinion.
- Volume is a midpoint estimate of filed ranges; committee membership is a current snapshot.
- Risk: `styles.py` targets Streamlit 1.66.x DOM. After any Streamlit upgrade run `/ui-check`. `requirements.txt` pins `streamlit>=1.66.1,<1.67`.

## Open work
- Real-phone review of the redesign, health check and price chart (dark theme was reviewed on 2026-11-09 in Chromium); owner decides whether to rename the Price tab "Price and ratios".
- Small: focus ring after mouse clicks; delta-down red on pink about 3.9:1; Brokers tab long at 320px.
- Next feature idea: returns after each trade versus SPY (needs SPY history and adjusted closes); cluster-buying signals.
- Owner: a square favicon mark; design-system updates (SVG trace, `Logo.md`, Tabs pattern).
- Data: Senate trades (CSV only); OCR for scanned filings; review `partial` filings; 25 tickers have no price or history (delisted or renamed).
- Full screen-reader and keyboard audit; check the deployed app.

## Known limits
Filings lag trades by up to 45 days. Sector is unknown for trades with no ticker. EUR uses one latest rate for all dates. Yahoo figures can be missing or odd for a ticker. UI work was checked in Chromium only: not Safari, Firefox, real touch, screen readers or the deployed app.

## Next step
Check the redesign on a real phone (open the deployed app after "Refresh data"); then the small items under Open work.
