"""Unit tests for fundamentals.py and the fundamentals fetch/store/median code."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db
import fundamentals as fd
import prices


def test_zones_and_format():
    assert fd.zone("pe", 10) == 0 and fd.zone("pe", 20) == 1 and fd.zone("pe", 40) == 2 and fd.zone("pe", None) is None
    assert fd.zone("free_cash_flow", -1) == 0 and fd.zone("free_cash_flow", 5) == 1
    assert fd.word("debt_to_equity", 2.0) == "High" and fd.word("beta", 1.0) == "Market-like"
    assert fd.fmt("profit_margin", 0.256) == "25.6%" and fd.fmt("pe", None) == "n/a" and fd.fmt("debt_to_equity", 1.5) == "1.50"
    assert fd.money(2.4e12) == "$2.4T" and fd.money(-1.2e9) == "-$1.2B" and fd.money(45e6) == "$45.0M"
    assert fd.market_cap_size(3e11) == "Large company" and fd.market_cap_size(5e8) == "Small company"
    assert fd.range_position(100, 200, 150) == 0.5 and fd.range_position(None, 200, 150) is None


def test_bars_and_text():
    html = fd.bar_html("pe", 30, 22)
    assert 'role="img"' in html and "rb-mark" in html and "rb-tick" in html and "higher" in html
    assert fd.bar_html("pe", None) == "" and fd.bar_html("free_cash_flow", 5) == ""
    assert "sector median 22.0 (12 stocks)" in fd.context_text("pe", 30, (22.0, 12))
    assert fd.context_text("pe", None) == "No data from the provider."
    vals = {"pe": 40, "forward_pe": 30, "price_to_sales": 9}
    h = fd.headline("value", vals)
    assert h.startswith("Priced above typical levels") and "grow" in h
    assert fd.headline("safety", {}) == "" and "ositive free cash flow" in fd.headline("safety", {"free_cash_flow": 1e9})
    a = fd.analyst_text(2.0, 30, 120, 100)
    assert "positive" in a and "+20%" in a and "Opinions" in a and fd.analyst_text(None, None, None, None) == ""


def test_fetch_store_and_medians():
    con = db.connect(Path(tempfile.mkdtemp()) / "t.db")
    db.init_db(con)
    for i in range(6):
        t = f"T{i}"
        con.execute("INSERT INTO ticker_sector(ticker, sector) VALUES (?, 'Technology') ON CONFLICT(ticker) DO UPDATE SET sector='Technology'", (t,))
        con.execute("INSERT INTO ticker_valuation(ticker, pe) VALUES (?, ?)", (t, 10.0 + i))
        con.execute("INSERT INTO ticker_fundamentals(ticker, profit_margin) VALUES (?, ?)", (t, 0.1 * i))
    con.commit()
    med = db.sector_medians(con, "Technology")
    assert med["pe"] == (12.5, 6) and abs(med["profit_margin"][0] - 0.25) < 1e-9
    assert db.sector_medians(con, "Unmapped") == {} and db.sector_medians(con, "Rare") == {}
    assert db.ticker_fundamentals(con, "T1")["profit_margin"] == 0.1 and db.ticker_fundamentals(con, "NOPE")["beta"] is None
    prices._INFO["AAPL"] = {"profitMargins": 0.25, "debtToEquity": 150, "beta": 1.2, "marketCap": 3e12, "recommendationMean": 2.0,
                            "numberOfAnalystOpinions": 40, "trailingAnnualDividendYield": 0.005, "freeCashflow": -5}
    v = dict(zip(db.FUNDAMENTAL_KEYS, prices.yahoo_fundamentals("AAPL")))
    assert v["profit_margin"] == 0.25 and v["debt_to_equity"] == 1.5 and v["free_cash_flow"] == -5 and v["analyst_count"] == 40
    assert v["roe"] is None and v["beta"] == 1.2 and v["market_cap"] == 3e12
    prices._INFO.clear()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
