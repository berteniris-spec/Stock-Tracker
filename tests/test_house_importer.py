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

# Lines as a text-layer PTR is expected to extract (best guess at the real layout).
PTR_LINES = [
    "Periodic Transaction Report",
    "Filing ID #1000001",
    "Name: Hon. Erin Example  Status: Member  State/District: CA11",
    "T Transactions",
    "ID Owner Asset Transaction Type Date Notification Date Amount Cap. Gains > $200?",
    "SP Lockheed Martin Corporation (LMT) [ST] P 01/15/2026 01/20/2026 $1,001 - $15,000",
    "F S: New",
    "D: Purchased shares in brokerage account",
    "Apple Inc. (AAPL) [ST] S (partial) 02/03/2026 02/10/2026 $15,001 - $50,000",
    "F S: New",
    "JT Vanguard 500 Index Fund [MF] E 02/11/2026 02/12/2026 $100,001 -",
    "$250,000",
    "F S: New",
    "DC Treasury Bond 2031 [GS] S 03/01/2026 03/05/2026 Over $1,000,000",
    "F S: New",
    "C: Comment that mentions SP and JT but is not a row",
    "Microsoft Corporation (MSFT) [ST] P 03/09/2026 03/12/2026 $1,001 - $15,000",
    "F S: New",
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
    assert markers == 5 and len(rows) == 5, (markers, len(rows))
    r = rows
    assert (r[0]["ticker"], r[0]["owner"], r[0]["tx_type"], r[0]["amount"]) == ("LMT", "Spouse", "Purchase", "$1,001 - $15,000")
    assert r[0]["tx_date"] == "2026-01-15" and r[0]["disclosure_date"] == "2026-01-20"
    assert (r[1]["ticker"], r[1]["owner"], r[1]["tx_type"]) == ("AAPL", "Self", "Sale (Partial)")
    assert r[1]["asset"] == "Apple Inc.", r[1]["asset"]
    assert r[0]["asset"] == "Lockheed Martin Corporation", r[0]["asset"]
    assert (r[2]["ticker"], r[2]["owner"], r[2]["tx_type"], r[2]["amount"]) == ("", "Joint", "Exchange", "$100,001 - $250,000")
    assert r[3]["owner"] == "Dependent Child" and r[3]["amount"] == "Over $1,000,000"
    assert (r[4]["ticker"], r[4]["owner"]) == ("MSFT", "Self")
    print("  rows:", [(x["ticker"] or x["asset"][:18], x["owner"], x["tx_type"]) for x in r])


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
        assert len(rows) == markers == 5


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
        # insert + dedupe
        rows, _ = hi.parse_ptr_text("\n".join(PTR_LINES))
        ins = lambda: sum(db.insert_trade(con, "E000001", r["tx_date"], r["ticker"], r["tx_type"], r["amount"],
                                          asset=r["asset"], owner=r["owner"], doc_id="1000001") for r in rows)
        assert ins() == 5 and ins() == 0
        assert con.execute("SELECT SUM(amount_est) FROM trades").fetchone()[0] == 8000 + 32500 + 175000 + 1000000 + 8000


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
