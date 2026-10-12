"""Daily closing prices (USD) for every ticker in the trades table, plus the ECB EUR/USD reference rate.

Prices: Yahoo Finance via the `yfinance` package, one batched download per 100 tickers (end-of-day closes, not live
quotes). The ECB publishes one euro foreign-exchange reference rate per working day (~16:00 CET); the app converts
USD to EUR with it. A failed fetch never deletes an older value: each price keeps its own `as_of` date, so the app
can show how stale it is.

Usage:  python prices.py [--limit N]
"""
import argparse
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

import db

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
CHUNK = 100


def yahoo_symbol(ticker):
    """Congress filings write class shares as BRK.B; Yahoo wants BRK-B."""
    return str(ticker).upper().replace(".", "-").strip()


def parse_ecb(xml_bytes):
    """-> (USD per 1 EUR, date string) from the ECB daily reference-rate XML."""
    root = ET.fromstring(xml_bytes)
    for cube in root.iter():
        if cube.tag.endswith("Cube") and cube.get("currency") == "USD":
            day = next((p.get("time") for p in root.iter() if p.tag.endswith("Cube") and p.get("time")), None)
            return float(cube.get("rate")), day
    raise ValueError("no USD rate in ECB response")


def fetch_ecb(get=requests.get):
    r = get(ECB_URL, timeout=30)
    r.raise_for_status()
    return parse_ecb(r.content)


def closes_from_frame(frame, symbols):
    """Pull [(date, close), ...] per symbol out of a yfinance download frame (multi- or single-index columns)."""
    out = {}
    multi = hasattr(frame.columns, "levels")
    for sym in symbols:
        try:
            col = frame[sym]["Close"] if multi else frame["Close"]
        except KeyError:
            continue
        col = col.dropna()
        if len(col):
            out[sym] = [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in col.items()]
    return out


def yahoo_download(symbols):
    """Default downloader: {symbol: [(date, close), ...]} for the last few trading days."""
    import yfinance as yf
    frame = yf.download(symbols, period="7d", interval="1d", group_by="ticker", auto_adjust=False,
                        progress=False, threads=True)
    if frame is None or frame.empty:
        return {}
    return closes_from_frame(frame, symbols)


def tickers_to_price(con, limit=None):
    rows = [r[0] for r in con.execute(
        "SELECT DISTINCT ticker FROM trades WHERE ticker IS NOT NULL AND ticker <> '' ORDER BY ticker")]
    return rows[:limit] if limit else rows


def update_prices(con, download=yahoo_download, limit=None, chunk=CHUNK):
    """Fetch and store the newest close for every traded ticker. Returns (priced, attempted)."""
    tickers = tickers_to_price(con, limit)
    now = datetime.now(timezone.utc).isoformat()
    priced = 0
    for i in range(0, len(tickers), chunk):
        batch = tickers[i:i + chunk]
        sym_to_ticker = {yahoo_symbol(t): t for t in batch}
        try:
            got = download(list(sym_to_ticker))
        except Exception as e:                       # one bad batch must not lose the rest
            print(f"  batch {i // chunk + 1} failed: {type(e).__name__}: {e}")
            continue
        with con:
            for sym, series in got.items():
                if not series:
                    continue
                as_of, price = series[-1]
                prev = series[-2][1] if len(series) > 1 else None
                con.execute(
                    "INSERT INTO ticker_price(ticker, price, prev_close, as_of, fetched_at, source) VALUES (?,?,?,?,?,'yahoo') "
                    "ON CONFLICT(ticker) DO UPDATE SET price=excluded.price, prev_close=excluded.prev_close, "
                    "as_of=excluded.as_of, fetched_at=excluded.fetched_at, source=excluded.source "
                    "WHERE excluded.as_of >= COALESCE(ticker_price.as_of, '')",
                    (sym_to_ticker[sym], price, prev, as_of, now))
                priced += 1
        time.sleep(1)
    return priced, len(tickers)


def update_fx(con, fetch=fetch_ecb):
    rate, day = fetch()
    with con:
        con.execute("INSERT INTO fx_rate(pair, rate, as_of, source) VALUES ('USD_PER_EUR', ?, ?, 'ecb') "
                    "ON CONFLICT(pair) DO UPDATE SET rate=excluded.rate, as_of=excluded.as_of, source=excluded.source",
                    (rate, day))
    return rate, day


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    con = db.connect()
    db.init_db(con)
    try:
        print("ECB rate (USD per EUR, date):", update_fx(con))
    except Exception as e:
        print(f"ECB rate failed ({type(e).__name__}: {e}); keeping the stored rate: {db.usd_per_eur(con)}")
    priced, attempted = update_prices(con, limit=args.limit)
    have, total, newest = db.price_freshness(con)
    print(f"priced {priced}/{attempted} tickers this run; {have}/{total} tickers have a price (newest close {newest})")
    if attempted and not priced:
        print("WARNING: no prices fetched; Yahoo may be blocking this host")
    missing = [r[0] for r in con.execute(
        "SELECT DISTINCT t.ticker FROM trades t LEFT JOIN ticker_price tp USING (ticker) "
        "WHERE t.ticker <> '' AND tp.ticker IS NULL ORDER BY 1 LIMIT 25")]
    print("no price (examples):", missing)


if __name__ == "__main__":
    main()
