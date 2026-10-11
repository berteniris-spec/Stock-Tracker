"""Fill ticker -> sector from SEC data.

For each ticker in the trades table that has no sector yet: look up its CIK in the SEC's company ticker
list, fetch the company's SIC code from data.sec.gov, and map the SIC code to one of the coarse sector
buckets used by the committee-relevance flag. Mutual funds/ETFs are labelled "Fund / ETF".

Precedence: sectors.csv overrides (ticker,sector) > the starter map in db.py > SEC lookup. Existing
entries are never overwritten, so a lookup only ever fills gaps. Tickers the SEC doesn't know are stored
as "Unclassified" and retried after 30 days.

Usage:  python enrich_sectors.py [--limit N]
SEC asks for a descriptive User-Agent and at most 10 requests/second; this script sleeps between calls.
SIC codes are an old, coarse classification (e.g. Alphabet and Visa don't land where GICS puts them),
so treat sectors as a heuristic.
"""
import argparse
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import db

# SEC fair-access policy: declare who you are, with a contact address. A noreply address is used here.
UA = {"User-Agent": "stock-tracker personal research berteniris-spec@users.noreply.github.com"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FUNDS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
DELAY = 0.15
RETRY_MISS_DAYS = 30

# (low, high, sector), first match wins: specific codes before their broad ranges.
SIC_RULES = [
    (6324, 6324, "Healthcare"),                               # hospital & medical service plans
    (3812, 3812, "Defense & Aerospace"), (3720, 3729, "Defense & Aerospace"),
    (3730, 3732, "Defense & Aerospace"), (3760, 3769, "Defense & Aerospace"),
    (3480, 3489, "Defense & Aerospace"), (3795, 3795, "Defense & Aerospace"),
    (2834, 2836, "Healthcare"), (8000, 8099, "Healthcare"), (3840, 3851, "Healthcare"),
    (5122, 5122, "Healthcare"), (8731, 8734, "Healthcare"), (2830, 2833, "Healthcare"),
    (2840, 2844, "Consumer Staples"), (5912, 5912, "Consumer Staples"),
    (4812, 4813, "Communication Services"), (4822, 4841, "Communication Services"),
    (4899, 4899, "Communication Services"), (4832, 4833, "Communication Services"),
    (2700, 2799, "Communication Services"), (7310, 7319, "Communication Services"),
    (7800, 7899, "Communication Services"),
    (7370, 7379, "Technology"), (3570, 3579, "Technology"), (3660, 3669, "Technology"),
    (3670, 3679, "Technology"), (3820, 3829, "Technology"), (3860, 3879, "Technology"),
    (3576, 3577, "Technology"),
    (6798, 6798, "Real Estate"), (6500, 6599, "Real Estate"),
    (6000, 6799, "Financials"),
    (100, 999, "Agriculture"),
    (1300, 1399, "Energy"), (1200, 1299, "Energy"), (2900, 2999, "Energy"), (4600, 4699, "Energy"),
    (1000, 1199, "Materials"), (1400, 1499, "Materials"), (2600, 2699, "Materials"),
    (2800, 2899, "Materials"), (3000, 3099, "Materials"), (3200, 3399, "Materials"),
    (4950, 4959, "Industrials"), (4900, 4999, "Utilities"),
    (4000, 4799, "Transportation"),
    (3711, 3716, "Consumer Discretionary"),
    (2000, 2199, "Consumer Staples"), (5400, 5499, "Consumer Staples"), (5140, 5149, "Consumer Staples"),
    (2200, 2599, "Consumer Discretionary"), (3100, 3199, "Consumer Discretionary"),
    (3750, 3799, "Consumer Discretionary"), (3900, 3999, "Consumer Discretionary"),
    (5500, 5999, "Consumer Discretionary"), (7000, 7099, "Consumer Discretionary"),
    (7200, 7299, "Consumer Discretionary"), (7500, 7599, "Consumer Discretionary"),
    (7900, 7999, "Consumer Discretionary"), (8200, 8299, "Consumer Discretionary"),
    (1500, 1799, "Industrials"), (3400, 3699, "Industrials"), (3700, 3749, "Industrials"),
    (3800, 3899, "Industrials"), (5000, 5399, "Industrials"), (7300, 7399, "Industrials"),
    (8700, 8799, "Industrials"),
]


def sic_to_sector(sic):
    if sic is None:
        return "Other"
    for lo, hi, sector in SIC_RULES:
        if lo <= sic <= hi:
            return sector
    return "Other"


def fetch_json(url):
    time.sleep(DELAY)
    r = requests.get(url, headers=UA, timeout=30)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:300]!r}")
    return r.json()


def _norm(t):
    return t.upper().replace(".", "-").strip()


def load_sec_maps(fetch=fetch_json):
    companies = {_norm(v["ticker"]): int(v["cik_str"]) for v in fetch(TICKERS_URL).values()}
    mf = fetch(FUNDS_URL)
    sym = mf["fields"].index("symbol")
    funds = {_norm(row[sym]) for row in mf["data"] if row[sym]}
    return companies, funds


def pending(con, retry_after_days=RETRY_MISS_DAYS):
    """Tickers in trades that still need a sector."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retry_after_days)).isoformat()
    rows = con.execute("""
        SELECT DISTINCT t.ticker FROM trades t LEFT JOIN ticker_sector ts USING (ticker)
        WHERE t.ticker <> '' AND (ts.ticker IS NULL OR (ts.source = 'sec-miss' AND ts.updated_at < ?))
        ORDER BY t.ticker""", (cutoff,)).fetchall()
    return [r[0] for r in rows]


def _save(con, ticker, sector, source, sic=None, desc=None):
    con.execute(
        "INSERT INTO ticker_sector(ticker, sector, sic, sic_description, source, updated_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(ticker) DO UPDATE SET sector=excluded.sector, sic=excluded.sic, "
        "sic_description=excluded.sic_description, source=excluded.source, updated_at=excluded.updated_at",
        (ticker, sector, sic, desc, source, datetime.now(timezone.utc).isoformat()))


def apply_overrides(con, path=Path(__file__).with_name("sectors.csv")):
    if not path.exists():
        return 0
    n = 0
    with open(path, newline="", encoding="utf-8-sig") as f, con:
        for row in csv.DictReader(f):
            if row.get("ticker") and row.get("sector"):
                _save(con, row["ticker"].strip().upper(), row["sector"].strip(), "override")
                n += 1
    return n


def enrich(con, fetch=fetch_json, limit=None):
    companies, funds = load_sec_maps(fetch)
    todo = pending(con)
    if limit:
        todo = todo[:limit]
    tally = {"sec": 0, "sec-fund": 0, "sec-miss": 0, "error": 0}
    for i, ticker in enumerate(todo, 1):
        key = _norm(ticker)
        try:
            if key in companies:
                sub = fetch(SUBMISSIONS_URL.format(cik=companies[key]))
                sic = int(sub["sic"]) if str(sub.get("sic") or "").isdigit() else None
                with con:
                    _save(con, ticker, sic_to_sector(sic), "sec", sic, sub.get("sicDescription"))
                tally["sec"] += 1
            elif key in funds:
                with con:
                    _save(con, ticker, "Fund / ETF", "sec-fund")
                tally["sec-fund"] += 1
            else:
                with con:
                    _save(con, ticker, "Unclassified", "sec-miss")
                tally["sec-miss"] += 1
        except Exception as e:                       # leave the ticker unset so the next run retries it
            tally["error"] += 1
            print(f"  {ticker}: {e}")
        if i % 100 == 0:
            print(f"  {i}/{len(todo)} tickers done")
    return len(todo), tally


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    con = db.connect()
    db.init_db(con)
    print(f"overrides applied: {apply_overrides(con)}")
    n, tally = enrich(con, limit=args.limit)
    known, total = db.sector_coverage(con)
    print(f"looked up {n} tickers: {tally}")
    print(f"sector known for {known}/{total} trades ({100 * known / max(total, 1):.0f}%)")
    print("by sector:", [tuple(r) for r in con.execute(
        "SELECT sector, COUNT(*) FROM trades t JOIN ticker_sector USING (ticker) GROUP BY 1 ORDER BY 2 DESC")])
    print("unclassified examples:", [r[0] for r in con.execute(
        "SELECT t.ticker FROM trades t JOIN ticker_sector ts USING (ticker) "
        "WHERE ts.sector='Unclassified' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 15")])


if __name__ == "__main__":
    main()
