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

## Sectors

`python enrich_sectors.py` fills a sector for every ticker from the FinanceDatabase CSVs (GICS-style, US venues),
mapped to the coarse buckets in `db.py`. It only fills gaps: `sectors.csv` (`ticker,sector`) overrides win, then the
starter map in `db.py`, then the lookup. The nightly workflow runs it. (The SEC's SIC codes would also work, but
sec.gov blocks GitHub-hosted runners, so they aren't used.) Trades with no ticker (notes, annuities, LP interests)
can't be classified this way.

## Notes and limits

- **Volume is an estimate.** Filings report ranges; the app uses the midpoint (floor for "Over $X").
- **Committee membership is a current snapshot** (`as_of` on each row), not membership at the trade date.
  Trades made before a member joined a committee still show against it.
- **"Committee-relevant"** is a coarse heuristic: `COMMITTEE_SECTORS` in `db.py` maps committees to
  sectors, and `ticker_sector` maps tickers to sectors (see Sectors).
  Unmapped tickers are never flagged. Treat flags as a place to look, not a conclusion.
- Filings lag trades by up to 45 days.

## Hosting and data refresh

- The **House import** workflow runs nightly (and on demand from the Actions tab). It restores the previous
  database, refreshes committees, imports only new filings, and force-pushes `congress.db` to the `data`
  branch (a single commit, so history doesn't grow). Run it with a `year` to backfill an earlier year.
- The app downloads the database from that branch on first start (`DB_URL` overrides the location), and the
  collapsed **Settings** section (under the view switch) has a **Refresh data from GitHub** button. A local `congress.db` is never overwritten unless you press it.
- Deploy `app.py` on Streamlit Community Cloud from this repo's `main` branch; no secrets are needed because
  the repo is public.
- The underlying filings are public records. Keep use non-commercial (the Clerk's terms bar commercial and
  fundraising use) and don't hammer the site: the importer rate-limits and caches.


## Development loop

Every change goes through the same cycle: **build, test, document**.

1. **Build** the change on `main` (small commits).
2. **Test** locally with `for t in tests/test_*.py; do python $t; done` (offline unit tests). Pushing triggers the
   `CI` workflow, which also runs `tests/ui_smoke.py`: it drives the real Streamlit app headlessly through every view
   and many members, committees and tickers, in USD and EUR, and fails on any exception.
   `scripts/wait_ci.sh` waits for the run and prints the result.
3. **Check live**: reload the deployed app and look at the changed views (Streamlit Cloud redeploys on push; press
   "Refresh data from GitHub" for new data).
4. **Document**: add an entry to `CHANGELOG.md` (what changed, how it was verified) and update this README if behaviour
   or setup changed.

In Claude Code, `/ship` runs the tests, checks the docs, then commits and pushes on a branch (it stops before a PR or
merge), `/resume` summarises the project state read-only, and `/ui-check` runs `python scripts/ui_check.py` and reviews
the screenshots. The script screenshots the four views at 390px and 1280px in light and dark and reports sideways
scroll, overflow and small tap targets (exit 0 clean, 1 overflow or load failure, 2 environment problem). Playwright is
not in `requirements.txt`: the Python that runs the script must import both `playwright` and `streamlit`, and the
Playwright version must match the installed Chromium (1.56.0 for chromium-1194). `.claude/settings.json` also sets
permissions: read-only git, `ls` and the tests run without asking; `git add`, `commit` and `push` ask; `rm`, `mv`,
`curl` and `wget` are denied.

For Claude Code, `CLAUDE.md` points to `AGENTS.md` and `docs/CONTEXT.md`, and three hooks in `.claude/settings.json`
help: a cloud session start installs dependencies and fetches `congress.db`; edits to the database, workflows and
theme ask for confirmation; and stopping runs the unit tests when a `.py` file changed and warns if `CHANGELOG.md`
was not updated.

The nightly `House import` workflow refreshes the data; CI never changes data.
