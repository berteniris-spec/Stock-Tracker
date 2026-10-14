# Changelog

Newest first. Each entry lists what changed for the user and how it was verified
(see "Development loop" in the README).

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
