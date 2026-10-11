"""Offline tests for house_importer (synthetic fixtures, no network).  Run: python tests/test_house_importer.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import house_importer as hi

INDEX_XML = b"""<?xml version="1.0"?><FinancialDisclosure>
<Member><Prefix>Hon.</Prefix><Last>Example</Last><First>Erin</First><Suffix/><FilingType>P</FilingType><StateDst>CA11</StateDst><Year>2026</Year><FilingDate>3/2/2026</FilingDate><DocID>1000001</DocID></Member>
<Member><Prefix>Hon.</Prefix><Last>Example</Last><First>Erin</First><Suffix/><FilingType>A</FilingType><StateDst>CA11</StateDst><Year>2026</Year><FilingDate>5/15/2026</FilingDate><DocID>1000002</DocID></Member>
<Member><Prefix>Hon.</Prefix><Last>Former</Last><First>Fred</First><Suffix/><FilingType>P</FilingType><StateDst>CA11</StateDst><Year>2026</Year><FilingDate>1/9/2026</FilingDate><DocID>1000003</DocID></Member>
<Member><Prefix>Hon.</Prefix><Last>De La Cruz</Last><First>Ana</First><Suffix/><FilingType>P</FilingType><StateDst>TX00</StateDst><Year>2026</Year><FilingDate>2/2/2026</FilingDate><DocID>1000004</DocID></Member>
</FinancialDisclosure>"""

# Mirrors the structure of real House PTR text layers (seen via the workflow's debug mode):
# head line = [owner] asset-start, type, 2 dates, amount; next line = asset-continuation (TICKER) [XX].
PTR_LINES = [
    "Filing ID #1000001",
    "P\x00\x00\x00 T\x00\x00\x00 R\x00\x00",
    "Clerk of the House of Representatives \u2022 Legislative Resource Center \u2022 Washington, DC 20515",
    "Name: Hon. Erin Example",
    "State/District: CA11",
    "ID Owner Asset Transaction Date Notification Amount Cap.",
    "Type Date Gains >",
    "$200?",
    "SP Lockheed Martin Corporation Common P 01/15/2026 01/20/2026 $15,001 -",
    "Stock (LMT) [ST] $50,000",
    "F\x00\x00 S\x00\x00: New",
    "S\x00\x00 O\x00: Example Brokerage > Growth Account",
    "D: Sold per plan. SP and JT are not owners here: T \u2013 37 shares sold @ $27.64/share",
    "Amazon.com, Inc. - Common Stock S (partial) 03/16/2026 03/16/2026 $1,001 - $15,000",
    "(AMZN) [ST]",
    "F S: New",
    "Berkshire Hathaway Inc. New S (partial) 03/16/2026 03/16/2026 $1,001 - $15,000",
    "Common Stock (BRK.B) [ST]",
    "F S: New",
    "ID Owner Asset Transaction Date Notification Amount Cap.",
    "Type Date Gains >",
    "$200?",
    "S O: Example Brokerage",
    "DIA - State Street SPDR Dow Jones S (partial) 03/16/2026 03/16/2026 $1,001 - $15,000",
    "Indust Avg ETF Trust NYSEARCA:",
    "DIA [OT]",
    "F S: New",
    "L: US",
    "JT Vanguard 500 Index Fund E 02/11/2026 02/12/2026 $100,001 - $250,000",
    "[MF]",
    "F S: New",
    "DC Treasury Bond 2031 S 03/01/2026 03/05/2026 Over $1,000,000",
    "[GS]",
    "F S: New",
    "Microsoft Corporation (MSFT) [ST] P 03/09/2026 03/12/2026 $1,001 - $15,000",
    "F S: New",
    "* For the complete list of asset type abbreviations, please visit https://fd.house.gov/reference/asset-type-codes.aspx.",
    "I CERTIFY that the statements I have made on the attached Periodic Transaction Report are true.",
]


def make_pdf(path, lines):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for ln in lines:
        c.setFont("Helvetica", 8)
        c.drawString(30, y, ln)
        y -= 12
    c.save()


def test_amounts():
    assert db.parse_amount("$1,001 - $15,000") == (1001, 15000, 8000)
    assert db.parse_amount("Over $1,000,000") == (1000000, None, 1000000)


def test_parse_text():
    rows, markers = hi.parse_ptr_text("\n".join(PTR_LINES))
    assert markers == 7 and len(rows) == 7, (markers, len(rows))
    r = rows
    # wrapped amount, owner code, asset continued on the next line
    assert (r[0]["ticker"], r[0]["owner"], r[0]["tx_type"], r[0]["amount"]) == ("LMT", "Spouse", "Purchase", "$15,001 - $50,000")
    assert r[0]["asset"] == "Lockheed Martin Corporation Common Stock", r[0]["asset"]
    assert r[0]["tx_date"] == "2026-01-15" and r[0]["disclosure_date"] == "2026-01-20"
    # ticker on the following line, partial sale
    assert (r[1]["ticker"], r[1]["owner"], r[1]["tx_type"], r[1]["asset"]) == ("AMZN", "Self", "Sale (Partial)", "Amazon.com, Inc. - Common Stock")
    assert (r[2]["ticker"], r[2]["asset"]) == ("BRK.B", "Berkshire Hathaway Inc. New Common Stock")
    # page-break header between rows, no parenthesised ticker, [OT]
    assert (r[3]["ticker"], r[3]["asset_type"]) == ("", "OT") and r[3]["asset"].startswith("DIA - State Street")
    assert (r[4]["owner"], r[4]["tx_type"], r[4]["amount"], r[4]["asset_type"]) == ("Joint", "Exchange", "$100,001 - $250,000", "MF")
    assert (r[5]["owner"], r[5]["amount"]) == ("Dependent Child", "Over $1,000,000")
    # inline layout: ticker + marker before the type, no owner
    assert (r[6]["ticker"], r[6]["asset"], r[6]["owner"], r[6]["tx_type"]) == ("MSFT", "Microsoft Corporation", "Self", "Purchase")
    print("  rows:", [(x["ticker"] or x["asset"][:14], x["owner"], x["tx_type"]) for x in r])


def test_inline_variants():
    rows, markers = hi.parse_ptr_text(
        "AT&T Inc. (T) [ST] S (partial) 03/16/2026 03/16/2026 $1,001 - $15,000\nF S: New\n"
        "Invesco QQQ [OT] S (partial) 03/16/2026 03/16/2026 $1,001 - $15,000\nF S: New\n"
        "SP Costco Wholesale Corporation (COST) [ST] P 04/01/2026 04/02/2026 $15,001 -\n$50,000\nF S: New")
    assert markers == 3 and len(rows) == 3
    assert [(r["ticker"], r["asset"], r["owner"]) for r in rows] == [
        ("T", "AT&T Inc.", "Self"), ("", "Invesco QQQ", "Self"), ("COST", "Costco Wholesale Corporation", "Spouse")]
    assert rows[2]["amount"] == "$15,001 - $50,000"


def test_real_world_amount_variants():
    txt = "\n".join([
        "SP U.S. Treasury Note due 2/28/2029 P 12/15/2025 12/16/2025 Spouse/DC Over",
        "[GS] $1,000,000",
        "F S: New",
        "  Capital Partners I LP (GLAS P 03/03/2026 03/30/2026 $707.21",
        "Funds LP) [HN]",
        "F S: New",
        "SP Premier Access Fund [OT] P 03/25/2026 03/31/2026 $50,001 -",
        "$100,000",
        "F S: New",
        " JT Tempus AI Class A Common P 01/16/2026 01/20/2026 $50,001 -",
        "Stock (TEM) [ST] $100,000",
        "F S: New",
    ])
    rows, markers = hi.parse_ptr_text(txt)
    assert markers == 4 and len(rows) == 4, (markers, len(rows), rows)
    assert [r["amount"] for r in rows] == ["Over $1,000,000", "$707.21", "$50,001 - $100,000", "$50,001 - $100,000"]
    assert [r["ticker"] for r in rows] == ["", "", "", "TEM"]
    assert rows[0]["owner"] == "Spouse" and rows[2]["asset"] == "Premier Access Fund" and rows[3]["owner"] == "Joint"
    assert hi.unparsed_markers(txt) == []                       # positions line up, even with leading spaces
    assert db.parse_amount("$707.21") == (707, 707, 707)
    assert db.parse_amount("Over $1,000,000") == (1000000, None, 1000000)


def test_volume_basis():
    with tempfile.TemporaryDirectory() as d:
        con = db.connect(Path(d) / "t.db")
        db.init_db(con)
        con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,source) VALUES ('X1','X','House','CA','D','congress-legislators')")
        for lbl in ("$5,000,001 - $25,000,000", "$1,001 - $15,000", "Over $1,000,000"):
            db.insert_trade(con, "X1", "2026-01-01", "AAA", "Purchase", lbl, asset=lbl)
        db.set_basis("mid")
        assert db.members_with_trades(con).est_volume[0] == 15000000 + 8000 + 1000000
        db.set_basis("min")
        assert db.members_with_trades(con).est_volume[0] == 5000001 + 1001 + 1000000
        assert db.volume_of(db.ticker_summary(con, "AAA")) == 5000001 + 1001 + 1000000
        db.set_basis("mid")


def test_unparsed_markers():
    txt = "Foo Corp (FOO) [ST] P 01/01/2026 01/02/2026 $1,001 - $15,000\nF S: New\nMystery row [ST] with no head line"
    rows, markers = hi.parse_ptr_text(txt)
    assert len(rows) == 1 and markers == 2
    snips = hi.unparsed_markers(txt)
    assert len(snips) == 1 and "Mystery row" in snips[0]


def test_pdf_roundtrip():
    try:
        import reportlab  # noqa: F401  (only needed to build the fixture PDF)
    except ImportError:
        print("  skipped: reportlab not installed")
        return
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.pdf"
        make_pdf(p, PTR_LINES)
        rows, markers = hi.parse_ptr_text(hi.extract_text(p))
        assert len(rows) == markers == 7


def test_index_and_matching():
    recs = list(hi.parse_index_xml(INDEX_XML))
    assert [r["doc_id"] for r in recs] == ["1000001", "1000003", "1000004"]  # amendments (A) excluded
    assert recs[2]["district"] == 0 and recs[2]["state"] == "TX"
    with tempfile.TemporaryDirectory() as d:
        con = db.connect(Path(d) / "t.db")
        db.init_db(con)
        con.executemany(
            "INSERT INTO members(bioguide_id,name,chamber,state,party,last_name,first_name,district,source) "
            "VALUES (?,?,?,?,?,?,?,?,'congress-legislators')",
            [("E000001", "Erin Example", "House", "CA", "D", "Example", "Erin", 11),
             ("D000001", "Ana De La Cruz", "House", "TX", "R", "De La Cruz", "Ana", 0)])
        assert hi.match_member(con, recs[0]) == "E000001"
        assert hi.match_member(con, recs[1]) is None          # former member in the same district
        assert hi.match_member(con, recs[2]) == "D000001"     # at-large district, multi-word surname
        con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,last_name,first_name,district,source) "
                    "VALUES ('S000001','Linda T. Sánchez','House','CA','D','Sánchez','Linda',38,'congress-legislators'),"
                    "('M000001','Rich McCormick','House','GA','R','McCormick','Rich',7,'congress-legislators')")
        accent = {"last": "Sanchez", "first": "Linda T.", "state": "CA", "district": 38}
        assert hi.match_member(con, accent) == "S000001"       # accents ignored
        stale = {"last": "Dr McCormick", "first": "Richard Dean Dr", "state": "GA", "district": 6}
        assert hi.match_member(con, stale) == "M000001"        # stale district -> state + last + first-name prefix
        other = {"last": "McCormick", "first": "Zed", "state": "GA", "district": 6}
        assert hi.match_member(con, other) is None             # different first name: refuse to guess
        # insert + dedupe
        rows, _ = hi.parse_ptr_text("\n".join(PTR_LINES))
        ins = lambda: sum(db.insert_trade(con, "E000001", r["tx_date"], r["ticker"], r["tx_type"], r["amount"],
                                          asset=r["asset"], owner=r["owner"], doc_id="1000001") for r in rows)
        assert ins() == 7 and ins() == 0
        assert con.execute("SELECT SUM(amount_est) FROM trades").fetchone()[0] == 32500 + 8000 + 8000 + 8000 + 175000 + 1000000 + 8000


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
