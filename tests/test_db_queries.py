"""Query edge cases.  Run: python tests/test_db_queries.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db


def test_paper_filings_empty_and_filled():
    con = db.connect(Path(tempfile.mkdtemp()) / "t.db")
    db.init_db(con)
    con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,source) VALUES ('X1','X','House','CA','D','congress-legislators')")
    assert db.paper_filings(con).empty and db.paper_filings(con, "X1").empty     # no filings: must not raise
    assert list(db.paper_filings(con).columns) == ["doc_id", "year", "bioguide_id", "member", "url"]
    con.execute("INSERT INTO filings(doc_id, year, bioguide_id, filer, status) VALUES ('123', 2026, 'X1', 'X', 'no_text')")
    df = db.paper_filings(con, "X1")
    assert df.url.iloc[0] == "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/123.pdf"
    assert db.paper_filings(con, "NOPE").empty


def test_top_tickers_has_name_after_ticker():
    con = db.connect(Path(tempfile.mkdtemp()) / "t.db")
    db.init_db(con)
    con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,source) VALUES ('X1','X','House','CA','D','congress-legislators')")
    db.insert_trade(con, "X1", "2026-01-01", "ZZZ", "Purchase", "$1,001 - $15,000", asset="Zed Corp")
    con.execute("INSERT INTO ticker_info(ticker, name, kind) VALUES ('ZZZ', 'Zed Corporation', 'equity')")
    df = db.top_tickers(con, 5)
    assert list(df.columns[:2]) == ["ticker", "name"] and df.name.iloc[0] == "Zed Corporation"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
