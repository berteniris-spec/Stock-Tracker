"""Load FICTIONAL demo data so the dashboard has something to show.

Creates four made-up members ("Sample ... (fictional)") assigned to real committees,
plus invented trades. Nothing here is attributed to a real person.
Remove it with:  python load_sample.py --purge
"""
import random
import sys

import db

FICTIONAL = [
    ("SAMPLE-S1", "Sample Senator One (fictional)", "Senate", "XX", "Independent", ["SSAS", "SSEG"]),
    ("SAMPLE-S2", "Sample Senator Two (fictional)", "Senate", "XX", "Independent", ["SSBK", "SSFI"]),
    ("SAMPLE-H1", "Sample Representative One (fictional)", "House", "XX", "Independent", ["HSAS", "HSHM"]),
    ("SAMPLE-H2", "Sample Representative Two (fictional)", "House", "XX", "Independent", ["HSIF", "HSBA"]),
]
RANGES = ["$1,001 - $15,000", "$15,001 - $50,000", "$50,001 - $100,000",
          "$100,001 - $250,000", "$250,001 - $500,000", "$500,001 - $1,000,000"]
TICKERS = ["LMT", "RTX", "NOC", "XOM", "CVX", "JPM", "GS", "PFE", "UNH", "NVDA", "AAPL", "MSFT", "NEE", "AMZN"]


def purge(con):
    with con:
        con.execute("DELETE FROM trades WHERE bioguide_id LIKE 'SAMPLE-%'")
        con.execute("DELETE FROM memberships WHERE bioguide_id LIKE 'SAMPLE-%'")
        con.execute("DELETE FROM members WHERE source='sample'")
    print("sample data removed")


def main():
    con = db.connect()
    db.init_db(con)
    if "--purge" in sys.argv:
        return purge(con)
    rng = random.Random(7)
    committees = {r[0] for r in con.execute("SELECT id FROM committees")}
    if not committees:
        sys.exit("Run ingest_committees.py first so the committees exist.")
    with con:
        for bid, name, chamber, state, party, cids in FICTIONAL:
            con.execute("INSERT OR REPLACE INTO members(bioguide_id, name, chamber, state, party, source) "
                        "VALUES (?,?,?,?,?,'sample')",
                        (bid, name, chamber, state, party))
            for cid in cids:
                if cid in committees:
                    con.execute("INSERT OR REPLACE INTO memberships VALUES (?,?,?,?,date('now'))",
                                (bid, cid, "Member", None))
            for _ in range(25):
                t = rng.choice(TICKERS)
                lbl = rng.choice(RANGES)
                lo, hi, est = db.parse_amount(lbl)
                day = f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}"
                con.execute(
                    "INSERT OR IGNORE INTO trades(bioguide_id, tx_date, disclosure_date, ticker, asset, tx_type, "
                    "owner, amount_label, amount_min, amount_max, amount_est, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,'sample')",
                    (bid, day, day, t, t + " (sample)", rng.choice(["Purchase", "Sale"]),
                     rng.choice(["Self", "Spouse", "Joint"]), lbl, lo, hi, est))
    print("sample data loaded:", con.execute("SELECT COUNT(*) FROM trades WHERE source='sample'").fetchone()[0], "trades")


if __name__ == "__main__":
    main()
