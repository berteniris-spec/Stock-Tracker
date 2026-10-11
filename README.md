# Congress trades (personal dashboard)

Joins congressional stock trades to committee membership and estimated volume.
SQLite + Streamlit, runs locally or on a free host.

## Run it locally

```bash
pip install -r requirements.txt
python ingest_committees.py     # members + committees (clones unitedstates/congress-legislators)
python load_sample.py           # optional: FICTIONAL demo trades so the app has data
streamlit run app.py
```

## Load real trades

`load_trades.py` takes a CSV with columns:

    bioguide_id, tx_date, ticker, tx_type, amount            (required)
    disclosure_date, asset, owner                            (optional)

`amount` is the filing's range text (`$1,001 - $15,000`, `Over $50,000,000`).

```bash
python load_trades.py trades.csv --source quiver
python load_sample.py --purge   # remove the fictional demo rows
```

Get the CSV from whichever source you choose (an API such as Quiver, or your own parser of the
House Clerk / Senate eFD filings) and map each member to their Bioguide ID. Names in the
`members` table come from congress-legislators, so you can match on name to find IDs.

## Import House trades (official data)

```bash
python house_importer.py --year 2026 --limit 25      # try a small batch first
python house_importer.py --debug <DocID> --year 2026   # inspect one filing's extracted text and parsed rows
```

Reads the House Clerk's yearly index, downloads each Periodic Transaction Report PDF, and parses the
trade table. Each filing is tracked in the `filings` table: `ok`, `partial` (parsed rows != "[XX]" markers
found, so the layout needs a look), `no_text` (scanned paper filing, no OCR), `unmatched_member`
(filer isn't a current member) or `fetch_failed`. House only; the Senate has no bulk download.
Run it from the **House import** GitHub Action if your own network blocks the Clerk's site.

Run the offline tests with `python tests/test_house_importer.py`.

## Notes and limits

- **Volume is an estimate.** Filings report ranges; the app uses the midpoint (floor for "Over $X").
- **Committee membership is a current snapshot** (`as_of` on each row), not membership at the trade date.
  Trades made before a member joined a committee still show against it.
- **"Committee-relevant"** is a coarse heuristic: `COMMITTEE_SECTORS` in `db.py` maps committees to
  sectors, and `ticker_sector` maps tickers to sectors (starter list in `db.py`; add your own rows).
  Unmapped tickers are never flagged. Treat flags as a place to look, not a conclusion.
- Filings lag trades by up to 45 days.

## Hosting

Push the repo to GitHub and deploy `app.py` on Streamlit Community Cloud. Refresh data with a
scheduled GitHub Action that runs the two ingest scripts and commits `congress.db`.
