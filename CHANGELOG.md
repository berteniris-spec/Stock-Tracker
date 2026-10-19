# Changelog

Newest first. Each entry lists what changed for the user and how it was verified
(see "Development loop" in the README).

## Mobile pass, step 4
- Phones (640px and narrower, Streamlit's column breakpoint; Python cannot read the viewport width, so both renderings are in the page at every width and CSS on the `st-key-*` container classes shows one). Above 640px the selectable dataframes and their "Tick the box..." captions are unchanged.
- Overview ranking tables (Most active members, Committees by trading volume, Top tickers) are lists of full-width buttons (keys `open_<table>_<i>`), label "N. Name (Party) · X trades · $4.5M" (U+00A0 before each "·"), chevron icon. The first 10 show; ranks 11 and up are in an expander "Show ranks 11 to N". Caption: "Tap a row to open that member. Volumes are estimated from the midpoint of each filed range." (lowest figure on the Filed minimum basis). A button's `on_click` sets `st.session_state['_goto']`, the existing click-through mechanism; shareable URLs are unchanged. Rows have a 3:1+ border (ink at 55%), names are markdown-escaped.
- Member trades, Committee members, Committee trades and Ticker trades show a compact wrapping `st.table` on phones (4-5 columns, at most 25 rows, caption "Showing the newest/top 25 of N ... Tick Show all columns above for every column and row."). A 44px "Show all columns" checkbox swaps in the full grid, with "Scroll sideways inside the table to see more columns." Sorting and row selection exist only in the full grid. Cell text 13.6px; words break only when they cannot fit; cell side padding is .1rem at 320px.
- Why a real table, not links or a narrower grid: the dataframe row-select checkbox is canvas-painted, 16px, and cannot be styled; `st.link_button` opens a new tab and session; a canvas grid with content-sized columns could not fit 4-5 columns in 288-358px; fixed widths or dropping or abbreviating columns would lose or alter facts (a Designer suggestion to drop Type from Committee trades was declined for that reason). A wrapping table is also better for screen readers.
- `LABELS['est_volume']` follows the volume basis ("Est. volume" / "Min. volume"). Buttons, download buttons and checkboxes get a 2px primary focus outline. CSV buttons and chart-data expanders are unchanged and byte-identical to main.
- `tests/ui_smoke.py`: list button counts (25/25/20), click-through of rows 0 and 10 of each list in USD and EUR, compact tables at most 25 rows, the U+00A0 separator, the basis caption.
- Trade-offs: phone pages are taller. At 390px, Overview with expanders closed is 3618px vs 2942px on main (+676px, +23%; 6177px with expanders open); Committee HSAP 3161px vs 2018px (+1143px). Websocket payload: Overview 82,102 vs 57,760 bytes, Committee HSAP 227,195 vs 208,494 bytes. Sorting and selection need "Show all columns" (or desktop).
- Risk: the CSS depends on Streamlit 1.66.0 internals (`st-key-*` container classes, `stLayoutWrapper` hidden via `:has()`, the `stTable` DOM, Styler white-space rules, the button inner span structure). After an upgrade the swap could fail (both renderings would show) or button alignment could break; re-run `/ui-check`.
- Verified (Tester, all eight checks passed, HEAD 41eab3d): unit tests; `tests/ui_smoke.py` 0 failures, 196 ok lines; `ui_check.py` twice, exit 0 and identical (1280 views PASS); AppTest on the real DB, an empty-trades DB, a sample-data DB and a sample-only DB, clicking rows 0, 10 and last of each list; Playwright at 320, 360, 390, 640, 641, 768, 1280, light and dark: exactly one rendering per width, list buttons at least 44px, list border contrast 4.56:1 light / 5.42:1 dark, focus ring 4.25:1 / 8.0:1, no page-level sideways scroll, no mid-word breaks at 320 and 390, tap a row from each list (one from an expander) and reload restores the URL, "Show all columns" reveals the full grid, desktop checkbox click-through works, Tab order has no hidden stops and Enter/Space activate list buttons, CSV byte-identical to main (Ticker MSFT 4763 bytes, Committee HSAP 59993, top_tickers 2048); steps 1-3 regressions pass. Designer review first failed (list border about 1.5:1, focus ring about 1.9:1, mid-word breaks like "Purcha/se", basis not visible next to the lists, no scroll hint after "Show all columns", caption order and wording, dangling "·"); all fixed.
- Not checked: the deployed app; Safari and Firefox (Chromium only); real touch input; expander rows on a real phone; EUR and Filed minimum in a browser beyond Overview and Member; Committee trades at 320 beyond the known inner scroll; the compact-table "Min. volume" header under Filed minimum (the smoke test does not assert it); screen readers.
- Seen, not fixed: below 360px the compact table wrapper can scroll inside its own box (Committee trades for HSSY, HLIG, HSGO scroll 5-9px at 320). At 360-640px the wrapper's overflow rule is overridden by Streamlit's own style (overflow auto), so a too-wide table would scroll in its box rather than fail visibly. The focus ring shows after mouse clicks on checkboxes.
- Design system statements now stale (owner to update): DataTable component README and preview, and the README Tables rule; see docs/CONTEXT.md.

## Mobile pass, step 3
- At 640px and narrower, metric strips are two per row (Overview strip 352px -> 144px high at 390px; MSFT 807px -> 379px). An odd last metric sits at the left. Desktop is unchanged. Streamlit stacks columns at its own 640px breakpoint; the CSS targets `stHorizontalBlock`/`stColumn` scoped with `:has(stMetric)`.
- Metric values use `clamp(1.5rem, 7vw, 2.25rem)` at that width (24px at 320, 27.3px at 390, 32px at 641, 36px above). There is a font step at 641-720px, where four-up columns are about 140px. Values wrap instead of truncating (for example "NYSE American").
- Metric labels are at most 18 characters: Est. volume / Min. volume (the same on every view), Committee-relevant, Members trading, Close (USD), Close (EUR), P/E, Fwd P/E, PEG.
- Member, Committee and Ticker volume metrics are compact via `short()`, like Overview. The exact figure stays in the tooltip and is now also in a visible caption under every metric strip: "Est. volume is the midpoint of each filed range. Exact: $X." or "Min. volume is the lowest figure in each filed range. Exact: ...". Overview adds ", summed over all trades". The caption adds about 63px to each view; the Ticker view has three captions in a row.
- Tooltip meaning that mattered moved into visible captions: a per-view n/a note for Committee-relevant, the ratios caption split in two (reference only, not advice; definitions of P/E, Fwd P/E, PEG and n/a), and a "No price found" caption.
- Latest filing on Overview shows the year only when the newest disclosure is not in the current year ("15 Oct 2025" vs "15 Oct").
- `tests/ui_smoke.py`: new `check_metrics` (labels at most 18 characters, values non-empty), `check_vol_label`, `check_vol_caption` and the per-view n/a captions.
- Risk: the CSS depends on Streamlit 1.66.0's DOM (`stHorizontalBlock`, `stColumn`, `stMetricValue` test ids, `:has()`, and `stMetricValue > stMarkdownContainer > p`). If it stops matching, metrics stack as before, but the wrap rule could stop and "NYSE American"-style values could truncate again. Re-run `/ui-check` after a Streamlit upgrade.
- Verified: unit tests and `tests/ui_smoke.py` pass. `ui_check.py` run twice: exit 0, no cut-off text, no page scroll. AppTest, 40 combinations (10 cases x USD/EUR x both bases): the exact figure matches an independent sqlite sum (USD 317,860,346 for Overview); the n/a note appears only where Committee-relevant is n/a; ratios captions only for non-ETFs; "No price found" only without a price; Latest filing year logic with a copy of the database shifted back a year; empty-trades database. Playwright, 256 loads at 320/390/640/641/768/900/1024/1280, light and dark, USD/EUR, both bases: two per row at 640 and below, zero truncation, no page scroll, one visible unclipped volume caption; font sizes and strip heights as above. Step 1 and 2 checks still pass (44px targets, no sidebar, Settings persistence, click-through, shared links). Designer review first failed (exact volume only in a tooltip, basis no longer visible, wrong n/a wording on Committee, overlong ratios caption); all fixed. Declined Designer suggestion: renaming Committee-relevant to Relevant trades (kept to match the table column and the checkbox).
- Not checked: the deployed app; a real phone or Safari (Chromium only); screen readers; pixel diffs beyond strip heights; Jan 1 of the current year for Latest filing; how the escaped `\$` in help text renders in the tooltip.
- Seen, not fixed: red delta text on its pink chip is about 3.9:1 in light (delta-down `#ff2b2b`; for the design system). On the first page load after a server start, one 641px measurement read 36px instead of 32px (cold-start race; re-measured fine).

## Mobile pass, step 2
- The sidebar is gone. The view switch (Overview, Member, Committee, Ticker) is a horizontal radio directly under the title. It wraps at 390px. Chosen over `st.segmented_control` because it works on every unpinned Streamlit version.
- Volume basis, Currency, the ECB rate caption, the price-freshness caption and "Refresh data from GitHub" are in a collapsed "Settings" expander. A refresh error shows under it in its own container. The settings persist across views.
- The help tooltips on Volume basis and Currency are now visible captions (the tooltips overflowed at 390px and the icon was 16px).
- CSS: radio options, buttons and download buttons are at least 44px high. Caption opacity is 1 (Streamlit fades captions to 0.6, about 3.4:1; now 10.5:1 light, 10.9:1 dark). The unselected radio ring is 4.6:1 light, 5.4:1 dark. Radio options have a keyboard focus ring (2px outline; `#4a70a9` 3.24:1 light, `#8fabd4` 4.83:1 dark). The refresh button is full width on phones and capped at 24rem above 640px.
- Risk: the radio rules match `label[data-testid="stRadioOption"]`, which is Streamlit 1.66.0's DOM (it exposes no theme CSS variables). A Streamlit upgrade could silently stop them matching.
- `tests/ui_smoke.py` finds controls by key (`page`, `currency`, `basis`, `refresh`) and asserts: no sidebar children, the Settings expander and refresh button exist, settings persist across views, and the `page` radio value follows shared links. `scripts/ui_check.py` dropped its sidebar-state logic, prints an advisory if a sidebar or toggle ever returns, and measures radio option labels as tap targets.
- Verified: unit tests and `tests/ui_smoke.py` pass (0 failures). `ui_check.py` run twice: exit 0, all 1280 views PASS, no page-level scroll at 390px, identical results. AppTest: settings persist across views; currency falls back to USD when the database has no EUR rate (also with a preset stale EUR); a simulated refresh failure (patched `urlopen`) shows "Refresh failed: ..." without crashing; shared links and unknown ids; all views in USD and EUR and both bases; empty-trades and sample-data databases. Playwright at 390 and 1280, light and dark: no sidebar nodes; view labels 44px and inside the viewport; click-through from each Overview table and from the view labels updates the URL; EUR persists across views; Settings stays open across changes; refresh button 324x44 at 390 and 384x44 at 1280; contrast and ring values as above; Tab order is title anchor, view radio (one tab stop, arrow keys change the selection), Settings, About, content; Space and Enter toggle Settings. Designer review first failed (caption contrast, tooltip overflow and 16px help icon, unselected ring 1.7:1, weak focus, desktop refresh width); all five were fixed and re-measured by the Tester (no separate second Designer pass).
- Not checked: the real Refresh network path (failure was simulated); the deployed app; real touch or mobile Safari (Chromium at 390px only); other narrow widths; the Filed minimum basis in a browser (AppTest only); `ui_check.py` does not open Settings. Other `help=` tooltips (metrics, columns) were not audited for overflow at 390px.
- Seen, not fixed: the focus ring stays on a radio after a mouse click (`:focus-within`, not `:focus-visible`; a Designer decision); about 30px gap between each Settings radio and its caption (Streamlit spacing); remaining small targets at 390px are Streamlit chrome (Deploy, Main menu, heading anchors, table toolbar icons, selectbox input and Open arrow).

## Mobile pass, step 1
- Ticker view, "Where can I buy it from the Netherlands?": the 4-column table is now eight collapsed expanders titled "NAME: status", each with the note and an "Open NAME" link button. A sibling expander "Show the brokers as a table" holds a real HTML table in a sideways-scrolling box. The page itself no longer scrolls sideways at 390px (the broker table was 429px wide).
- Top of every view: the paper-filing info box and its two expanders became one status caption, "**Coverage gap:** N paper filing(s) not imported (M member(s)). Details under About this data.", shown only when paper filings exist, plus one "About this data" expander (the bullets, the explanation and the missing-filings table).
- CSS: expander headers and link buttons have a 44px minimum height.
- Trade-off: on desktop, comparing brokers now needs a click, because the table sits in an expander.
- Only `app.py` changed.
- Verified: unit tests and `tests/ui_smoke.py` pass. `ui_check.py` run twice: all 1280 views PASS, no page-level scroll at 390px. AppTest for NVDA (USD and EUR), ETFs, a ticker with no price, an unknown id, an empty-trades database, and singular/plural caption cases (1 filing/1 member, 2/2, 0). Playwright: shared links and click-through from Top tickers work; the table expander causes no page scroll. Keyboard Tab reaches every expander header and link button with a visible focus ring. Light and dark screenshots show no breakage. Designer review first failed (tap targets 38/40px, table alternative lost, caption lead, plurals); all fixed and re-measured at 44px.
- Not checked: the deployed app; Member and Committee views in a browser beyond the `ui_check.py` defaults; EUR and the Filed minimum basis in a browser (AppTest only); the sidebar open at 390px; combinations such as 2 filings from 1 member; a true full-page capture (Streamlit scrolls an inner container).
- Seen, not fixed: in the broker table the Link column sits off to the right inside the scroller with no visual hint; the missing-filings links wrap to three lines at 390px; remaining small tap targets are Streamlit chrome (sidebar toggle 28x28, Deploy 57x28, Main menu 28x28, heading anchors 16x16) plus our "Refresh data from GitHub" button (26x480).

## Workflow commands and UI check
- Three Claude Code slash commands in `.claude/commands/`:
  - `/ship`: runs the tests, checks the docs, commits and pushes on a branch. It stops before any PR or merge.
  - `/resume`: read-only summary of `docs/CONTEXT.md`, the branch, open PRs and the next step.
  - `/ui-check`: runs `scripts/ui_check.py`, reads a few screenshots and reports. It fixes nothing.
- `scripts/ui_check.py` starts the app headless and uses Playwright with the preinstalled Chromium to screenshot Overview, Member, Committee and Ticker at 390px and 1280px, light and dark. It reports page-level sideways scroll (naming the widest element), overflowing elements and suspected cut-off text, and, at 390px only, tap targets under 44px (advisory). It waits for the page title and does a warm-up load first. Exit codes: 0 clean, 1 page-level overflow or the page did not finish loading, 2 environment problem.
- Playwright is not a repo dependency. The interpreter running the script must import both `playwright` and `streamlit`, and the Playwright version must match the installed Chromium build (1.56.0 for chromium-1194).
- Repo-wide behaviour change: `.claude/settings.json` now has a `permissions` block for everyone using Claude Code here. Allowed without asking: read-only git (`status`, `diff`, `log`, `branch --show-current`, `rev-parse`, `remote get-url`), `ls`, `python tests/test_*.py`, `python tests/ui_smoke.py`, Read, Glob, Grep. Ask first: `git add`, `git commit`, `git push`. Denied: `rm`, `mv`, `curl`, `wget`. The hooks block is unchanged.
- First finding from the script (app issue, not fixed): on the Ticker view at 390px the page scrolls sideways because the broker table (about 429px wide, no scroll container) overflows. Overview, Member and Committee at 390px show only advisory small tap targets (Refresh data button 26x480, sidebar toggle 28x28, Deploy 57x28, heading anchors 16x16).
- Verified: unit tests and `tests/ui_smoke.py` pass; `ui_check.py` run five times with identical output and the first screenshot never blank; the forced-failure path exits 1 and stops the server; the missing-Playwright and output-inside-repo paths exit 2.
- Not checked: the slash commands and permission rules in a live session; EUR, volume basis and the open sidebar at 390px in `ui_check.py`; the deployed app.
- Known limits: only the default state is captured (USD, default volume basis, sidebar as rendered at load). The 390px screenshots are viewport height because the page scrolls inside `stMain`. Tap-target counts are advisory.

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
