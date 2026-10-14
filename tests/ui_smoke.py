"""UI smoke test: drives the real Streamlit app headlessly (streamlit.testing AppTest) through every view.

Catches the class of bug where one view crashes for some members/tickers (e.g. an empty-frame edge case).
Needs streamlit installed and a congress.db in the repo root.   Run: python tests/ui_smoke.py
Exit code 1 and ::error annotations when any view raises.
"""
import random
import sqlite3
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
failures = []


def check(at, label):
    errs = [e.value for e in at.exception]
    if errs:
        failures.append(label)
        print(f"::error title=UI smoke: {label}::{str(errs[0])[:300]}")
    else:
        print("ok", label)


def fresh():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    return at


def main():
    con = sqlite3.connect(ROOT / "congress.db")
    random.seed(1)
    members = [r[0] for r in con.execute("SELECT DISTINCT bioguide_id FROM trades")]
    paper_only = [r[0] for r in con.execute(
        "SELECT DISTINCT bioguide_id FROM filings WHERE status='no_text' AND bioguide_id IS NOT NULL")]
    tickers = [r[0] for r in con.execute("SELECT DISTINCT ticker FROM trades WHERE ticker<>''")]
    committees = [r[0] for r in con.execute(
        "SELECT DISTINCT c.id FROM committees c JOIN memberships m ON m.committee_id=c.id "
        "JOIN trades t ON t.bioguide_id=m.bioguide_id WHERE c.parent_id IS NULL")]

    at = fresh()
    check(at, "Overview")
    # every sidebar option combination on the overview
    for radio in at.sidebar.radio:
        for opt in radio.options:
            if radio.label in ("Currency", "Volume basis"):
                radio.set_value(opt).run()
                check(at, f"Overview with {radio.label}={opt}")

    for page, key, ids in (("Member", "member_sel", members), ("Committee", "committee_sel", committees),
                           ("Ticker", "ticker_sel", tickers)):
        sample = ids if len(ids) <= 40 else random.sample(ids, 40)
        if page == "Member":
            sample = sample + paper_only[:5]
        at = fresh()
        at.sidebar.radio[0].set_value(page).run()
        check(at, f"{page} default")
        for item in sample:
            try:
                at.selectbox(key=key).set_value(item).run()
            except Exception as e:           # a paper-only member is not in the Member selectbox options? report, don't hide
                failures.append(f"{page}:{item}")
                print(f"::error title=UI smoke: {page} {item}::{type(e).__name__}: {str(e)[:200]}")
                continue
            check(at, f"{page} {item}")
        # the whole view again in EUR
        for radio in at.sidebar.radio:
            if radio.label == "Currency" and "EUR" in radio.options:
                radio.set_value("EUR").run()
                check(at, f"{page} in EUR")

    # shared links restore the view; a stale id falls back instead of crashing
    for view, ident in (("Ticker", tickers[0]), ("Member", members[0]), ("Committee", committees[0]),
                        ("Ticker", "NOT-A-TICKER"), ("Member", "ZZZZ"), ("Bogus", "x")):
        at = AppTest.from_file(APP, default_timeout=90)
        at.query_params["view"] = view
        at.query_params["id"] = ident
        at.run()
        check(at, f"shared link view={view} id={ident}")

    print(f"UI smoke finished: {len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
