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


if __name__ == "__main__":
    test_paper_filings_empty_and_filled()
    print("ok test_paper_filings_empty_and_filled")
