"""Offline tests for enrich_sectors (fake SEC responses, no network).  Run: python tests/test_enrich_sectors.py"""
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import enrich_sectors as es

TICKERS = {"0": {"cik_str": 1, "ticker": "LMTX", "title": "Lockheed"}, "1": {"cik_str": 2, "ticker": "BRKX-B", "title": "Berkshire"},
           "2": {"cik_str": 3, "ticker": "NVDX", "title": "Nvidia"}, "3": {"cik_str": 4, "ticker": "WEIRD", "title": "Odd Co"},
           "4": {"cik_str": 5, "ticker": "AAPL", "title": "Apple"}}
FUNDS = {"fields": ["cik", "seriesId", "classId", "symbol"], "data": [[9, "S1", "C1", "SPY"], [9, "S2", "C2", "QQQ"]]}
SUBS = {1: {"sic": "3760", "sicDescription": "Guided Missiles & Space Vehicles"},
        2: {"sic": "6331", "sicDescription": "Fire, Marine & Casualty Insurance"},
        3: {"sic": "3674", "sicDescription": "Semiconductors"},
        4: {"sic": "", "sicDescription": ""},
        5: {"sic": "3571", "sicDescription": "Electronic Computers"}}
calls = []


def fake_fetch(url):
    calls.append(url)
    if url == es.TICKERS_URL:
        return TICKERS
    if url == es.FUNDS_URL:
        return FUNDS
    cik = int(url.split("CIK")[1].split(".")[0])
    return SUBS[cik]


def test_sic_mapping():
    cases = {3760: "Defense & Aerospace", 3724: "Defense & Aerospace", 3812: "Defense & Aerospace",
             3721: "Defense & Aerospace", 3571: "Technology", 7372: "Technology", 3674: "Technology",
             2911: "Energy", 1311: "Energy", 6022: "Financials", 6331: "Financials", 6798: "Real Estate",
             2834: "Healthcare", 6324: "Healthcare", 8062: "Healthcare", 4911: "Utilities", 4512: "Transportation",
             5961: "Consumer Discretionary", 3711: "Consumer Discretionary", 2086: "Consumer Staples",
             4813: "Communication Services", 7389: "Industrials", 100: "Agriculture", 9999: "Other"}
    for sic, want in cases.items():
        assert es.sic_to_sector(sic) == want, (sic, es.sic_to_sector(sic), want)
    assert es.sic_to_sector(None) == "Other"


def _con(d):
    con = db.connect(Path(d) / "t.db")
    db.init_db(con)
    con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,source) VALUES ('X1','X','House','CA','D','congress-legislators')")
    for tk in ("LMTX", "BRKX.B", "NVDX", "WEIRD", "SPY", "NOPE", "AAPL", "XOM", ""):   # XOM, AAPL are in the starter map
        db.insert_trade(con, "X1", "2026-01-01", tk, "Purchase", "$1,001 - $15,000", asset=tk or "no ticker")
    return con


def test_enrich_flow():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)
        assert "XOM" not in es.pending(con) and "" not in es.pending(con)      # starter map entries + blanks skipped
        n, tally = es.enrich(con, fake_fetch)
        assert tally == {"sec": 4, "sec-fund": 1, "sec-miss": 1, "error": 0}, tally
        get = lambda t: tuple(con.execute("select sector, source, sic from ticker_sector where ticker=?", (t,)).fetchone())
        assert get("LMTX") == ("Defense & Aerospace", "sec", 3760)
        assert get("BRKX.B") == ("Financials", "sec", 6331)                    # BRKX.B looked up as BRKX-B
        assert get("NVDX") == ("Technology", "sec", 3674)
        assert get("WEIRD") == ("Other", "sec", None)                         # blank SIC -> Other
        assert get("SPY") == ("Fund / ETF", "sec-fund", None)
        assert get("NOPE") == ("Unclassified", "sec-miss", None)
        assert get("AAPL")[1] == "default"                                    # starter map never overwritten
        known, total = db.sector_coverage(con)
        assert (known, total) == (7, 9), (known, total)                       # unknown: the "NOPE" miss and the blank ticker
        # second run: nothing new to do
        calls.clear()
        n2, _ = es.enrich(con, fake_fetch)
        assert n2 == 0 and all(c in (es.TICKERS_URL, es.FUNDS_URL) for c in calls)


def test_miss_retry_and_errors():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)
        es.enrich(con, fake_fetch)
        old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        con.execute("UPDATE ticker_sector SET updated_at=? WHERE ticker='NOPE'", (old,))
        assert es.pending(con) == ["NOPE"]                                    # stale miss is retried

        def flaky(url):
            if "CIK0000000001" in url:
                raise RuntimeError("boom")
            return fake_fetch(url)
        con.execute("DELETE FROM ticker_sector WHERE ticker='LMTX'")
        n, tally = es.enrich(con, flaky)
        assert tally["error"] == 1 and con.execute("select 1 from ticker_sector where ticker='LMTX'").fetchone() is None


def test_circuit_breaker():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)

        def blocked(url):
            if url in (es.TICKERS_URL, es.FUNDS_URL):
                return fake_fetch(url)
            raise RuntimeError("HTTP 403 Request Rate Threshold Exceeded")
        # add more SEC-resolvable tickers so the streak can trip
        for tk in ("A1", "A2", "A3", "A4", "A5"):
            TICKERS[tk] = {"cik_str": 1, "ticker": tk, "title": tk}
            db.insert_trade(con, "X1", "2026-01-02", tk, "Purchase", "$1,001 - $15,000", asset=tk)
        n, tally = es.enrich(con, blocked)
        assert tally.get("aborted") is True and tally["error"] == es.MAX_CONSECUTIVE_ERRORS, tally
        for tk in ("A1", "A2", "A3", "A4", "A5"):
            del TICKERS[tk]


def test_overrides():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)
        csv_path = Path(d) / "sectors.csv"
        csv_path.write_text("ticker,sector\nlmtx,Industrials\nAAPL,Communication Services\n")
        assert es.apply_overrides(con, csv_path) == 2
        es.enrich(con, fake_fetch)
        assert con.execute("select sector, source from ticker_sector where ticker='LMTX'").fetchone()[:] == ("Industrials", "override")
        assert con.execute("select sector from ticker_sector where ticker='AAPL'").fetchone()[0] == "Communication Services"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
