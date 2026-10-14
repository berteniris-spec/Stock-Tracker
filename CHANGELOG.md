# Changelog

Newest first. Each entry lists what changed for the user and how it was verified
(see "Development loop" in the README).

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
