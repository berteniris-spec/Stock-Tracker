"""Offline tests for prices.py and brokers.py.  Run: python tests/test_prices.py"""
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brokers
import db
import prices

ECB = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
<Cube><Cube time="2026-10-09"><Cube currency="USD" rate="1.1584"/><Cube currency="JPY" rate="170.1"/></Cube></Cube>
</gesmes:Envelope>"""


def _con(d):
    con = db.connect(Path(d) / "t.db")
    db.init_db(con)
    con.execute("INSERT INTO members(bioguide_id,name,chamber,state,party,source) VALUES ('X1','X','House','CA','D','congress-legislators')")
    for tk in ("AAPL", "BRK.B", "NOPE", ""):
        db.insert_trade(con, "X1", "2026-01-01", tk, "Purchase", "$1,001 - $15,000", asset=tk or "none")
    return con


def test_ecb():
    assert prices.parse_ecb(ECB) == (1.1584, "2026-10-09")
    con = _con(tempfile.mkdtemp())
    assert prices.update_fx(con, lambda: (1.1584, "2026-10-09")) == (1.1584, "2026-10-09")
    assert db.usd_per_eur(con) == (1.1584, "2026-10-09")


def test_frame_parsing():
    idx = pd.to_datetime(["2026-10-08", "2026-10-09"])
    cols = pd.MultiIndex.from_product([["AAPL", "BRK-B"], ["Close", "Volume"]])
    frame = pd.DataFrame([[10.0, 1, 20.0, 1], [11.0, 1, float("nan"), 1]], index=idx, columns=cols)
    got = prices.closes_from_frame(frame, ["AAPL", "BRK-B", "GONE"])
    assert got["AAPL"] == [("2026-10-08", 10.0), ("2026-10-09", 11.0)]
    assert got["BRK-B"] == [("2026-10-08", 20.0)]                  # NaN days dropped
    assert "GONE" not in got
    single = pd.DataFrame({"Close": [5.0, 6.0]}, index=idx)
    assert prices.closes_from_frame(single, ["AAPL"])["AAPL"][-1] == ("2026-10-09", 6.0)


def test_update_prices():
    con = _con(tempfile.mkdtemp())
    calls = []

    def dl(symbols):
        calls.append(symbols)
        return {"AAPL": [("2026-10-08", 99.0), ("2026-10-09", 100.0)], "BRK-B": [("2026-10-09", 500.0)]}

    assert prices.update_prices(con, dl) == (2, 3)                 # AAPL, BRK.B, NOPE (blank ticker skipped)
    assert calls[0] == ["AAPL", "BRK-B", "NOPE"]                   # dots converted for Yahoo
    row = con.execute("select price, prev_close, as_of from ticker_price where ticker='AAPL'").fetchone()
    assert tuple(row) == (100.0, 99.0, "2026-10-09")
    assert con.execute("select price from ticker_price where ticker='BRK.B'").fetchone()[0] == 500.0   # stored under the congress ticker
    # an older close never replaces a newer one; a failed run keeps what we had
    prices.update_prices(con, lambda s: {"AAPL": [("2026-10-01", 1.0)]})
    assert con.execute("select price from ticker_price where ticker='AAPL'").fetchone()[0] == 100.0
    prices.update_prices(con, lambda s: 1 / 0)
    assert db.price_freshness(con) == (2, 3, "2026-10-09")
    prof = db.ticker_profile(con, "AAPL")
    assert prof["price"] == 100.0 and prof["as_of"] == "2026-10-09" and prof["exchange"] is None
    assert db.ticker_profile(con, "ZZZ")["price"] is None


def test_brokers():
    verdict, per = brokers.availability("equity", "NMS")
    assert per["DEGIRO"] == "Yes" and per["Trading 212"].startswith("Likely")
    assert set(per) == {b["name"] for b in brokers.BROKERS}
    assert brokers.availability("equity", "PNK")[1]["DEGIRO"] == "No"
    assert brokers.availability("etf", "PCX")[1]["DEGIRO"].startswith("Usually not")
    assert brokers.availability(None, None)[1]["DEGIRO"] == "Check"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
