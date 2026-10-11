"""Import trades from a CSV into the database.

Usage:
    python load_trades.py trades.csv [--source NAME]

Required columns: bioguide_id, tx_date, ticker, tx_type, amount
Optional columns: disclosure_date, asset, owner

`amount` is the filing's range text, e.g. "$1,001 - $15,000" or "Over $50,000,000".
Volume is estimated from the range midpoint (or the floor for open-ended ranges).
Re-importing the same file is safe: duplicate rows are ignored.
Unknown bioguide_ids are reported and skipped.
"""
import argparse
import csv
import sys

import db

REQUIRED = {"bioguide_id", "tx_date", "ticker", "tx_type", "amount"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--source", default="import")
    args = ap.parse_args()

    con = db.connect()
    db.init_db(con)
    known = {r[0] for r in con.execute("SELECT bioguide_id FROM members")}

    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"CSV is missing columns: {sorted(missing)}")
        added = dupes = unknown = 0
        unknown_ids = set()
        with con:
            for row in reader:
                bid = row["bioguide_id"].strip()
                if bid not in known:
                    unknown += 1
                    unknown_ids.add(bid)
                    continue
                n = db.insert_trade(
                    con, bid, row["tx_date"].strip(), row["ticker"].strip(), row["tx_type"].strip(),
                    row["amount"].strip(), disclosure_date=(row.get("disclosure_date") or "").strip() or None,
                    asset=(row.get("asset") or "").strip(), owner=(row.get("owner") or "Self").strip(),
                    source=args.source)
                added += n
                dupes += 1 - n
    print(f"added={added} duplicates={dupes} skipped_unknown_member={unknown}")
    if unknown_ids:
        print("unknown ids:", ", ".join(sorted(unknown_ids)[:10]))


if __name__ == "__main__":
    main()
