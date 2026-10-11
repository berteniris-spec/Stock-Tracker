"""Offline tests for enrich_sectors (fake CSV downloads, no network).  Run: python tests/test_enrich_sectors.py"""
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import enrich_sectors as es

HDR = "symbol,name,sector,industry_group,industry,market_cap,delisted\n"
FILES = {
    "equities/NMS": HDR + "\n".join([
        "NVDX,Nvidia-like,Information Technology,Semiconductors,Semiconductors,Mega Cap,False",
        "UNHX,Insurer-like,Health Care,Health Care Equipment & Providers,Health Care Providers,Large Cap,False",
        "DUP,Dup (delisted),Energy,Energy,Oil & Gas,Small Cap,True",
        "DUP,Dup (live),Consumer Staples,Food,Food Products,Micro Cap,False",
        "NOSEC,No sector co,,,,Small Cap,False",
    ]) + "\n",
    "equities/NYQ": HDR + "\n".join([
        "LMTX,Defense-like,Industrials,Industrial Goods,Aerospace & Defense,Mega Cap,False",
        "DALX,Airline-like,Industrials,Transport & Logistics,Airlines,Large Cap,False",
        "BRKX-B,Berkshire-like,Financials,Insurance,Insurance,Mega Cap,False",
        "DUP,Dup on NYSE (loses to NMS),Utilities,Utilities,Electric,Mega Cap,False",
        "JPMX,Bank-like,Financials,Banking,Banks,Mega Cap,False",
    ]) + "\n",
    "etfs/NMS": "symbol,name\nQQQX,Some ETF\nNVDX,Same symbol as an equity\n",
}


def fake_fetch(url):
    key = url.split("/database/")[1].removesuffix(".csv")
    return FILES[key].encode() if key in FILES else None        # anything else is a 404


def _con(d, extra=()):
    con = db.connect(Path(d) / "t.db")
    db.init_db(con)
    con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,source) VALUES ('X1','X','House','CA','D','congress-legislators')")
    for tk in ("LMTX", "BRKX.B", "NVDX", "UNHX", "DALX", "DUP", "QQQX", "NOSEC", "NOPE", "AAPL", "XOM", "", *extra):  # AAPL, XOM: starter map
        db.insert_trade(con, "X1", "2026-01-01", tk, "Purchase", "$1,001 - $15,000", asset=tk or "no ticker")
    return con


def test_fd_sector_mapping():
    assert es.fd_sector("Industrials", "Industrial Goods", "Aerospace & Defense") == "Defense & Aerospace"
    assert es.fd_sector("Industrials", "Transport & Logistics", "Airlines") == "Transportation"
    assert es.fd_sector("Health Care", "x", "y") == "Healthcare"
    assert es.fd_sector("Information Technology", "x", "y") == "Technology"
    assert es.fd_sector("Financials", "x", "y") == "Financials"
    assert es.fd_sector(float("nan"), float("nan"), float("nan")) is None
    assert es.fd_sector("Mystery", "x", "y") is None


def test_enrich_flow():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)
        assert set(es.pending(con)) == {"LMTX", "BRKX.B", "NVDX", "UNHX", "DALX", "DUP", "QQQX", "NOSEC", "NOPE"}
        n, tally = es.enrich(con, fake_fetch)
        assert tally == {"classified": 6, "etf": 1, "miss": 2}, tally
        get = lambda t: tuple(con.execute("select sector, source from ticker_sector where ticker=?", (t,)).fetchone())
        assert get("LMTX") == ("Defense & Aerospace", "financedatabase")
        assert get("DALX") == ("Transportation", "financedatabase")
        assert get("UNHX") == ("Healthcare", "financedatabase")
        assert get("NVDX") == ("Technology", "financedatabase")        # equity wins over a same-symbol ETF row
        assert get("BRKX.B") == ("Financials", "financedatabase")      # BRKX.B matches BRKX-B
        assert get("DUP") == ("Consumer Staples", "financedatabase")   # NMS beats NYQ; live row beats delisted row
        assert get("QQQX") == ("Fund / ETF", "fd-etf")
        assert get("NOSEC") == ("Unclassified", "fd-miss")             # found, but no usable sector
        assert get("NOPE") == ("Unclassified", "fd-miss")
        assert get("AAPL")[1] == "default"                             # starter map never overwritten
        assert con.execute("select industry from ticker_sector where ticker='LMTX'").fetchone()[0] == "Industrial Goods / Aerospace & Defense"
        assert db.sector_coverage(con) == (9, 12)                      # unknown: NOSEC, NOPE, and the blank ticker
        assert es.enrich(con, lambda u: 1 / 0)[0] == 0                 # nothing pending -> nothing downloaded


def test_miss_retry_and_missing_files():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)
        es.enrich(con, fake_fetch)
        con.execute("UPDATE ticker_sector SET updated_at=? WHERE ticker='NOPE'",
                    ((datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),))
        assert es.pending(con) == ["NOPE"]                             # stale miss is retried, fresh one (NOSEC) is not
        FILES["equities/NYQ"] += "NOPE,Appeared later,Energy,Energy,Oil & Gas,Large Cap,False\n"
        n, tally = es.enrich(con, fake_fetch)
        assert tally["classified"] == 1
        assert con.execute("select sector from ticker_sector where ticker='NOPE'").fetchone()[0] == "Energy"


def test_overrides():
    with tempfile.TemporaryDirectory() as d:
        con = _con(d)
        p = Path(d) / "sectors.csv"
        p.write_text("ticker,sector\nlmtx,Industrials\nAAPL,Communication Services\n")
        assert es.apply_overrides(con, p) == 2
        es.enrich(con, fake_fetch)
        assert con.execute("select sector, source from ticker_sector where ticker='LMTX'").fetchone()[:] == ("Industrials", "override")
        assert con.execute("select sector from ticker_sector where ticker='AAPL'").fetchone()[0] == "Communication Services"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
