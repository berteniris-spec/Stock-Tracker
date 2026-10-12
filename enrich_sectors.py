"""Fill ticker -> sector from the FinanceDatabase project (GICS-style sectors for ~30k US-listed tickers).

Data comes from the CSVs in github.com/JerBouma/FinanceDatabase (raw.githubusercontent.com), US venues only.
Each ticker in the trades table that has no sector yet is looked up, and its sector/industry is mapped to the
coarse buckets used by the committee-relevance flag ("Aerospace & Defense" industry -> "Defense & Aerospace",
airline/freight/rail industries -> "Transportation", ETFs -> "Fund / ETF").

Precedence: sectors.csv overrides (ticker,sector) > the starter map in db.py > this lookup. Existing entries are
never overwritten, so a run only fills gaps. Tickers not found are stored as "Unclassified" and retried after
30 days. The files are only downloaded when there is something to look up.

Why not the SEC's SIC codes? They'd be a fine source, but sec.gov answers GitHub-hosted runners with
"Request Rate Threshold Exceeded" (shared IPs), so that route doesn't work from the nightly workflow.

Usage:  python enrich_sectors.py [--limit N]
Sectors are a heuristic: classification systems disagree at the edges (payments firms, conglomerates, ADRs).
"""
import argparse
import csv
import io
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

import db

FD_BASE = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/main/database"
EXCHANGES = ["NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS", "PNK"]     # US venues, in priority order
RETRY_MISS_DAYS = 30
CAP_RANK = {"Mega Cap": 5, "Large Cap": 4, "Mid Cap": 3, "Small Cap": 2, "Micro Cap": 1, "Nano Cap": 0}

SECTOR_MAP = {
    "Financials": "Financials", "Health Care": "Healthcare", "Information Technology": "Technology",
    "Industrials": "Industrials", "Consumer Discretionary": "Consumer Discretionary", "Energy": "Energy",
    "Materials": "Materials", "Communication Services": "Communication Services",
    "Consumer Staples": "Consumer Staples", "Real Estate": "Real Estate", "Utilities": "Utilities",
}


EXCHANGE_NAMES = {"NMS": "Nasdaq", "NGM": "Nasdaq", "NCM": "Nasdaq", "NYQ": "NYSE", "ASE": "NYSE American",
                  "PCX": "NYSE Arca", "BTS": "Cboe BZX", "PNK": "OTC (Pink)"}


def fd_sector(sector, industry_group, industry):
    """Map a FinanceDatabase classification to this app's sector buckets."""
    if isinstance(industry, str) and industry.strip() == "Aerospace & Defense":
        return "Defense & Aerospace"
    if isinstance(industry_group, str) and industry_group.strip() == "Transport & Logistics":
        return "Transportation"
    if isinstance(sector, str) and sector in SECTOR_MAP:
        return SECTOR_MAP[sector]
    return None


def http_get(url, tries=3):
    """Fetch bytes; None if the file doesn't exist (404). Retries transient server errors."""
    for attempt in range(tries):
        r = requests.get(url, timeout=120)
        if r.status_code == 404:
            return None
        if r.status_code >= 500 and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        r.raise_for_status()
        return r.content


def _norm(t):
    return str(t).upper().replace(".", "-").strip()


def load_classification(fetch=http_get, exchanges=EXCHANGES):
    """Return ({ticker: (bucket, industry text, venue code, name)}, {etf ticker: (venue code, name)})."""
    equities, etfs = {}, {}
    for ex in exchanges:
        raw = fetch(f"{FD_BASE}/equities/{ex}.csv")
        if raw is None:
            print(f"  equities/{ex}.csv not found, skipping")
            continue
        df = pd.read_csv(io.BytesIO(raw), low_memory=False,
                         usecols=lambda c: c in ("symbol", "name", "sector", "industry_group", "industry", "market_cap", "delisted"))
        df = df[df["symbol"].notna()].copy()
        df["_live"] = (~df["delisted"].fillna(False).astype(bool)).astype(int) if "delisted" in df else 1
        df["_cap"] = df["market_cap"].map(CAP_RANK).fillna(-1) if "market_cap" in df else -1
        df = df.sort_values(["_live", "_cap"], ascending=False).drop_duplicates("symbol")   # best row per symbol
        for row in df.itertuples():
            key = _norm(row.symbol)
            if key not in equities:                  # earlier venues win
                bucket = fd_sector(row.sector, row.industry_group, row.industry)
                text = " / ".join(str(x) for x in (row.industry_group, row.industry) if isinstance(x, str))
                equities[key] = (bucket, text or None, ex, row.name if isinstance(row.name, str) else None)
    for ex in exchanges:
        raw = fetch(f"{FD_BASE}/etfs/{ex}.csv")
        if raw is not None:
            df = pd.read_csv(io.BytesIO(raw), low_memory=False,
                             usecols=lambda c: c in ("symbol", "name")).dropna(subset=["symbol"])
            for row in df.itertuples():
                nm = getattr(row, "name", None)
                etfs.setdefault(_norm(row.symbol), (ex, nm if isinstance(nm, str) else None))
    return equities, etfs


def pending(con, retry_after_days=RETRY_MISS_DAYS):
    """Tickers that still need a sector or exchange info (misses are retried after a while)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retry_after_days)).isoformat()
    rows = con.execute("""
        SELECT DISTINCT t.ticker FROM trades t
        LEFT JOIN ticker_sector ts USING (ticker) LEFT JOIN ticker_info ti USING (ticker)
        WHERE t.ticker <> '' AND (ts.ticker IS NULL OR (ts.source = 'fd-miss' AND ts.updated_at < ?)
                                  OR ti.ticker IS NULL OR (ti.kind IS NULL AND ti.updated_at < ?))
        ORDER BY t.ticker""", (cutoff, cutoff)).fetchall()
    return [r[0] for r in rows]


def _save_info(con, ticker, kind, code, name):
    con.execute(
        "INSERT INTO ticker_info(ticker, name, kind, exchange_code, exchange, updated_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(ticker) DO UPDATE SET name=excluded.name, kind=excluded.kind, exchange_code=excluded.exchange_code, "
        "exchange=excluded.exchange, updated_at=excluded.updated_at",
        (ticker, name, kind, code, EXCHANGE_NAMES.get(code), datetime.now(timezone.utc).isoformat()))


def _save(con, ticker, sector, source, industry=None):
    con.execute(
        "INSERT INTO ticker_sector(ticker, sector, industry, source, updated_at) VALUES (?,?,?,?,?) "
        "ON CONFLICT(ticker) DO UPDATE SET sector=excluded.sector, industry=excluded.industry, "
        "source=excluded.source, updated_at=excluded.updated_at",
        (ticker, sector, industry, source, datetime.now(timezone.utc).isoformat()))


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


def enrich(con, fetch=http_get, limit=None):
    todo = pending(con)
    if limit:
        todo = todo[:limit]
    tally = {"classified": 0, "etf": 0, "miss": 0}
    if not todo:
        return 0, tally
    equities, etfs = load_classification(fetch)
    print(f"  classification loaded: {len(equities):,} equities, {len(etfs):,} ETFs")
    with con:
        for ticker in todo:
            key = _norm(ticker)
            hit = equities.get(key)
            row = con.execute("SELECT source FROM ticker_sector WHERE ticker = ?", (ticker,)).fetchone()
            sector_open = row is None or row[0] == "fd-miss"      # never overwrite default/override/classified rows
            if hit:
                _save_info(con, ticker, "equity", hit[2], hit[3])
            elif key in etfs:
                _save_info(con, ticker, "etf", *etfs[key])
            else:
                _save_info(con, ticker, None, None, None)
            if not sector_open:
                continue
            if hit and hit[0]:
                _save(con, ticker, hit[0], "financedatabase", hit[1])
                tally["classified"] += 1
            elif key in etfs and not hit:
                _save(con, ticker, "Fund / ETF", "fd-etf")
                tally["etf"] += 1
            else:                                    # unknown, or known without a usable sector
                _save(con, ticker, "Unclassified", "fd-miss", hit[1] if hit else None)
                tally["miss"] += 1
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
