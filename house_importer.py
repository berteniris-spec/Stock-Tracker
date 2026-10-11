"""Import House Periodic Transaction Reports (PTRs) from the Clerk's public disclosure site.

Usage:
    python house_importer.py --year 2026 [--limit 50] [--refresh-index]
    python house_importer.py --debug 20012345 --year 2026     # show extracted text + parsed rows for one filing

Pipeline: yearly index (zip/XML) -> keep PTRs (FilingType "P") -> match filer to a current member
(state + district + last name) -> download the PDF -> extract text -> parse trade rows -> insert.

Notes
- House only. The Senate eFD site has no bulk download and its terms are a separate question.
- Filings by former members are skipped (status `unmatched_member`): the members table holds current
  members only.
- Scanned/paper filings have no text layer and are recorded as `no_text` (no OCR is attempted).
- Parsing PDF tables is best-effort. Each filing records how many "[XX]" asset-type markers it contains
  vs. how many rows were parsed; a mismatch is stored as `partial` so you can see which filings to inspect.
- Downloads are cached under .cache/house/ and requests are rate-limited.
"""
import argparse
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

import db

BASE = "https://disclosures-clerk.house.gov/public_disc"
CACHE = Path(__file__).with_name(".cache") / "house"
HEADERS = {"User-Agent": "stock-tracker personal research script (non-commercial)"}
DELAY = 0.5  # seconds between requests

TX_TYPES = {"P": "Purchase", "S": "Sale", "E": "Exchange", "S (partial)": "Sale (Partial)"}
OWNERS = {"SP": "Spouse", "DC": "Dependent Child", "JT": "Joint"}

_DATE = r"\d{1,2}/\d{1,2}/\d{4}"
ROW = re.compile(
    r"\[(?P<atype>[A-Z]{2})\]\s+"
    r"(?P<ttype>S\s*\(partial\)|P|S|E)\s+"
    rf"(?P<tx>{_DATE})\s+(?P<notif>{_DATE})\s+"
    r"(?P<amount>\$[\d,]+\s*-\s*\$[\d,]+|Over\s+\$[\d,]+)")
MARKER = re.compile(r"\[[A-Z]{2}\]")
TICKER_AT_END = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*$")
OWNER_TAIL = re.compile(r"(?:^|\n)(SP|DC|JT) ([^:]*)$")   # owner code must start a line


# ---------- pure parsing helpers (unit-tested without network) ----------

def iso(d):
    return datetime.strptime(d, "%m/%d/%Y").date().isoformat()


def parse_ptr_text(text):
    """Return (rows, marker_count). Each row is a dict of trade fields."""
    flat = re.sub(r"[ \t]+", " ", text)              # collapse spaces but keep line breaks:
    flat = re.sub(r" ?\n ?", "\n", flat)             # owner codes are only trusted at the start of a line
    rows, prev_end = [], 0
    for m in ROW.finditer(flat):
        seg = flat[prev_end:m.start()].strip()
        prev_end = m.end()
        seg = seg.split("$200?")[-1].strip()          # drop the table header on the first row
        tm = TICKER_AT_END.search(seg)
        ticker = tm.group(1) if tm else ""
        head = seg[:tm.start()].strip() if tm else seg
        om = OWNER_TAIL.search(head)
        if om:
            owner, asset = OWNERS[om.group(1)], om.group(2)
        else:
            owner = "Self"
            asset = head.splitlines()[-1] if head else ""   # best effort: last line, past any F S:/D:/C: lines
        asset = asset.replace("\n", " ")
        ttype = re.sub(r"\s+", " ", m.group("ttype")).replace("( ", "(")
        rows.append({
            "ticker": ticker,
            "asset": asset.strip()[-80:].strip(),
            "owner": owner,
            "asset_type": m.group("atype"),
            "tx_type": TX_TYPES.get(ttype, ttype),
            "tx_date": iso(m.group("tx")),
            "disclosure_date": iso(m.group("notif")),
            "amount": re.sub(r"\s+", " ", m.group("amount")),
        })
    return rows, len(MARKER.findall(flat))


def parse_index_xml(xml_bytes):
    """Yield PTR filings from a Clerk yearly index XML."""
    root = ET.fromstring(xml_bytes)
    for el in root.iter("Member"):
        g = lambda tag: (el.findtext(tag) or "").strip()
        if g("FilingType") != "P":
            continue
        sd = g("StateDst")
        m = re.fullmatch(r"([A-Z]{2})(\d{2})", sd)
        yield {"doc_id": g("DocID"), "last": g("Last"), "first": g("First"), "suffix": g("Suffix"),
               "state": m.group(1) if m else sd[:2], "district": int(m.group(2)) if m else None,
               "year": g("Year"), "filed": g("FilingDate")}


def _norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def match_member(con, rec):
    """Match a filing to a current House member by state + district + last name."""
    rows = con.execute(
        "SELECT bioguide_id, last_name FROM members "
        "WHERE chamber='House' AND state=? AND district=? AND source='congress-legislators'",
        (rec["state"], rec["district"])).fetchall()
    want = _norm(rec["last"])
    hits = [r["bioguide_id"] for r in rows
            if _norm(r["last_name"]) == want or want.endswith(_norm(r["last_name"]))
            or _norm(r["last_name"]).endswith(want)]
    return hits[0] if len(hits) == 1 else None


# ---------- network + files ----------

def _get(url, dest, force=False):
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(DELAY)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def load_index(year, refresh=False):
    z = _get(f"{BASE}/financial-pdfs/{year}FD.zip", CACHE / f"{year}FD.zip", force=refresh)
    with zipfile.ZipFile(z) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
        return list(parse_index_xml(zf.read(name)))


def extract_text(pdf_path):
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def record_filing(con, rec, status, bioguide=None, parsed=None, markers=None):
    con.execute(
        "INSERT INTO filings(doc_id, year, bioguide_id, filer, status, rows_parsed, markers) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(doc_id) DO UPDATE SET status=excluded.status, bioguide_id=excluded.bioguide_id, "
        "rows_parsed=excluded.rows_parsed, markers=excluded.markers, updated_at=CURRENT_TIMESTAMP",
        (rec["doc_id"], int(rec["year"] or 0), bioguide, f'{rec["first"]} {rec["last"]}', status, parsed, markers))


def process_filing(con, rec, year):
    bid = match_member(con, rec)
    if not bid:
        record_filing(con, rec, "unmatched_member")
        return "unmatched_member", 0
    pdf = CACHE / str(year) / f'{rec["doc_id"]}.pdf'
    try:
        _get(f"{BASE}/ptr-pdfs/{year}/{rec['doc_id']}.pdf", pdf)
    except requests.RequestException as e:
        print(f"  fetch failed {rec['doc_id']}: {e}", file=sys.stderr)
        record_filing(con, rec, "fetch_failed", bid)
        return "fetch_failed", 0
    text = extract_text(pdf)
    if len(text.strip()) < 40:
        record_filing(con, rec, "no_text", bid, 0, 0)
        return "no_text", 0
    rows, markers = parse_ptr_text(text)
    added = sum(db.insert_trade(
        con, bid, r["tx_date"], r["ticker"], r["tx_type"], r["amount"], disclosure_date=r["disclosure_date"],
        asset=r["asset"], owner=r["owner"], source="house-clerk", doc_id=rec["doc_id"]) for r in rows)
    status = "ok" if rows and len(rows) == markers else "partial"
    record_filing(con, rec, status, bid, len(rows), markers)
    return status, added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=datetime.now().year)
    ap.add_argument("--limit", type=int, help="process at most N new filings (for testing)")
    ap.add_argument("--refresh-index", action="store_true")
    ap.add_argument("--debug", metavar="DOC_ID", help="print extracted text and parsed rows for one filing")
    args = ap.parse_args()

    if args.debug:
        pdf = _get(f"{BASE}/ptr-pdfs/{args.year}/{args.debug}.pdf", CACHE / str(args.year) / f"{args.debug}.pdf")
        text = extract_text(pdf)
        print(text)
        rows, markers = parse_ptr_text(text)
        print(f"\n--- parsed {len(rows)} rows, {markers} markers ---")
        for r in rows:
            print(r)
        return

    con = db.connect()
    db.init_db(con)
    if not con.execute("SELECT 1 FROM members WHERE chamber='House' LIMIT 1").fetchone():
        sys.exit("No House members in the database. Run ingest_committees.py first.")

    index = load_index(args.year, args.refresh_index)
    done = {r[0] for r in con.execute("SELECT doc_id FROM filings WHERE status IN ('ok','no_text','unmatched_member')")}
    todo = [r for r in index if r["doc_id"] not in done]
    print(f"{args.year}: {len(index)} PTRs in index, {len(todo)} to process")
    if args.limit:
        todo = todo[:args.limit]

    tally, added = {}, 0
    for i, rec in enumerate(todo, 1):
        with con:
            status, n = process_filing(con, rec, args.year)
        tally[status] = tally.get(status, 0) + 1
        added += n
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} done, {added} trades added so far")
    print(f"finished: {added} trades added; filings by status: {tally}")


if __name__ == "__main__":
    main()
