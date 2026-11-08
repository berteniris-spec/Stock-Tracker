"""UI smoke test: drives the real Streamlit app headlessly (streamlit.testing AppTest) through every view.

Catches the class of bug where one view crashes for some members/tickers (e.g. an empty-frame edge case).
Needs streamlit installed and a congress.db in the repo root.   Run: python tests/ui_smoke.py
Exit code 1 and ::error annotations when any view raises.
"""
import random
import re
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


def check_metrics(at, label):
    """Every metric: label of 18 characters at most (two per row on a phone) and a non-empty value."""
    if not len(at.metric):
        failures.append(f"{label} metrics")
        print(f"::error title=UI smoke: {label} metrics::no metrics rendered")
    for m in at.metric:
        if len(m.label) > 18 or not str(m.value).strip():
            failures.append(f"{label} metric {m.label}")
            print(f"::error title=UI smoke: {label} metric::label {m.label!r} ({len(m.label)} chars) or empty value {m.value!r}")
    print("ok", label, "metrics:", ", ".join(f"{m.label}={m.value}" for m in at.metric))


def check_vol_label(at, label):
    """The volume metric carries the short basis name, the same on every view."""
    want = "Min. volume" if at.radio(key="basis").value == "Filed minimum" else "Est. volume"
    vols = [m for m in at.metric if m.label in ("Est. volume", "Min. volume")]
    if not vols or any(m.label != want for m in vols):
        failures.append(f"{label} volume label")
        print(f"::error title=UI smoke: {label} volume label::expected {want!r}, got {[m.label for m in at.metric]}")
    else:
        print("ok", label, "volume label", want)


def check_vol_caption(at, label):
    """A visible caption names the basis and the exact figure (tooltips are not reachable on touch)."""
    want = "Min. volume is" if at.radio(key="basis").value == "Filed minimum" else "Est. volume is"
    if not any(str(c.value).startswith(want) and "Exact: " in str(c.value) for c in at.caption):
        failures.append(f"{label} volume caption")
        print(f"::error title=UI smoke: {label} volume caption::no caption starting {want!r} with 'Exact: '")
    else:
        print("ok", label, "volume caption")


def check_compact_table(at, label):
    """Compact tables: at most 25 rows; the volume header follows the basis; a truncated table says so under itself."""
    check_compact_table_rows(at, label)
    if "Committee" in label:
        vol = "Min. volume" if at.radio(key="basis").value == "Filed minimum" else "Est. volume"
        if not any(vol in list(t.value.columns) for t in at.table):
            failures.append(f"{label} volume header")
            print(f"::error title=UI smoke: {label} volume header::no compact table with a {vol!r} column")
        long = [len(t.value) for t in at.table if len(t.value) == 25]
        shown = any(str(c.value).startswith("Showing the") and "Tick Show all columns above for every column and row." in str(c.value) for c in at.caption)
        if bool(long) and not shown:
            failures.append(f"{label} truncation caption")
            print(f"::error title=UI smoke: {label} truncation caption::a table is capped at 25 rows but no 'Showing the ...' caption")


def check_compact_table_rows(at, label):
    """The phone rendering of the trade tables is a real st.table (it wraps; canvas columns clipped at 390px)."""
    if len(at.table) and all(len(t.value) <= 25 for t in at.table):
        print("ok", label, f"{len(at.table)} compact table(s), at most 25 rows each")
    else:
        failures.append(f"{label} compact table")
        print(f"::error title=UI smoke: {label} compact table::expected st.table(s) of at most 25 rows, got {[len(t.value) for t in at.table]}")


def check_ticker_tabs(at, label, expect_etf=None, expect_price=None):
    """Ticker view: three tabs; AppTest renders every tab's content, so each tab's elements are looked up by tab."""
    bad = []
    tabs = {t.label: t for t in at.tabs}
    if list(tabs) != ["Trades", "Price", "Brokers"]:
        print(f"::error title=UI smoke: {label} tabs::tabs are {[t.label for t in at.tabs]}")
        failures.append(f"{label} tabs")
        return
    tr, pr, br = tabs["Trades"], tabs["Price"], tabs["Brokers"]
    want = "Min. volume" if at.radio(key="basis").value == "Filed minimum" else "Est. volume"
    if [m.label for m in tr.metric] != ["Trades", want]:
        bad.append(f"Trades metrics {[m.label for m in tr.metric]}")
    if not any(str(c.value).startswith(f"{want} is") and "Exact: " in str(c.value) for c in tr.caption):
        bad.append("Trades volume caption")
    if not any("Trades were disclosed up to 45 days after they happened." in str(c.value) for c in tr.caption):
        bad.append("45-day caption not in Trades")
    pl = [m.label for m in pr.metric]
    etf = [m.value for m in pr.metric if m.label == "Type"] == ["ETF / fund"]
    if pl[:4] != ["Close (USD)", "Close (EUR)", "Exchange", "Type"]:
        bad.append(f"Price metrics {pl}")
    if etf != (pl[4:] == []) or (not etf and pl[4:] != ["P/E", "Fwd P/E", "PEG"]):
        bad.append(f"Price ratios {pl[4:]} for etf={etf}")
    if expect_etf is not None and etf != expect_etf:
        bad.append(f"expected etf={expect_etf}")
    no_price = any(str(c.value).startswith("No price found") for c in pr.caption)
    if expect_price is not None and no_price == expect_price:
        bad.append(f"expected a price={expect_price}, no-price caption shown={no_price}")
    if not no_price and not any(str(c.value).startswith("Price is the end-of-day close on") for c in pr.caption):
        bad.append("price caption")
    if len(br.expander) != 9 or "Show the brokers as a table" not in [e.label for e in br.expander]:
        bad.append(f"Brokers expanders {[e.label for e in br.expander]}")
    if not any("On a narrow screen, scroll sideways inside the table to see the Link column." in str(c.value) for c in br.caption):
        bad.append("scroll-hint caption")
    advice = "This is information, not investment advice."
    if sum(str(c.value) == advice for c in at.caption) <= sum(str(c.value) == advice for tab in (tr, pr, br) for c in tab.caption):
        bad.append("advice caption missing outside the tabs")
    if any("Trades below" in str(c.value) for c in at.caption):
        bad.append("'Trades below' caption still present")
    if "tab" in at.query_params:
        bad.append("tab in the URL")
    if bad:
        failures.append(f"{label} ticker tabs")
        print(f"::error title=UI smoke: {label} ticker tabs::{'; '.join(bad[:4])}")
    else:
        print("ok", label, "ticker tabs")


def has_caption(at, text):
    return any(text in str(c.value) for c in at.caption)


def overview_rows():
    """(button key prefix, view, select key, expected ids, expected names) of the three Overview lists, from the database.

    Computed right after a run: the volume basis (a module-level setting in db, set by the app) decides the order.
    """
    import db
    c = db.connect()
    m = db.members_with_trades(c).head(25)
    cm = db.committees_with_trading(c).head(25)
    t = db.top_tickers(c, 20)
    return (("open_ov_members_", "Member", "member_sel", list(m["bioguide_id"]), list(m["name"])),
            ("open_ov_committees_", "Committee", "committee_sel", list(cm["id"]), list(cm["name"])),
            ("open_ov_tickers_", "Ticker", "ticker_sel", list(t["ticker"]), list(t["ticker"])))


def open_buttons(at, prefix):
    return {b.key: b for b in at.button if (b.key or "").startswith(prefix)}


def check_open_buttons(at, label):
    """The phone lists: one button per ranking row (25, tickers 20, or fewer), rank first, name in the label, every $ escaped."""
    for prefix, view, _, ids, names in overview_rows():
        found = open_buttons(at, prefix)
        bad = []
        if len(found) != len(ids):
            bad.append(f"{len(found)} buttons, expected {len(ids)}")
        for i, name in enumerate(names):
            b = found.get(f"{prefix}{i}")
            if b is None:
                continue
            text = str(b.label)
            if not text.startswith(f"{i + 1}. ") or str(name).replace("\\", "") not in text.replace("\\", ""):
                bad.append(f"row {i}: {text!r}")
            if re.search(r"(?<!\\)\$", text):
                bad.append(f"row {i}: unescaped $ in {text!r}")
        noun = view.lower()
        want = ("Tap a row to open that %s. Volumes are estimated from %s of each filed range."
                % (noun, "the lowest figure" if at.radio(key="basis").value == "Filed minimum" else "the midpoint"))
        if not has_caption(at, want):
            bad.append(f"phone caption {want!r} missing")
        if any(" \u00b7 " in str(b.label) or "\u00a0\u00b7" not in str(b.label) for b in found.values()):
            bad.append("separator is not attached to the previous part by U+00A0")
        if bad:
            failures.append(f"{label} {prefix}")
            print(f"::error title=UI smoke: {label} {prefix}::{'; '.join(bad[:3])}")
        else:
            print("ok", label, f"{len(found)} {prefix}* buttons")


def check_click_through(currency):
    """Tapping a list row opens that member / committee / ticker: view, selectbox and URL all follow (rank 1 and rank 11)."""
    for prefix, view, sel, _, _ in overview_rows():
        for i in (0, 10):
            at = fresh()
            if currency != "USD":
                at.radio(key="currency").set_value(currency).run()
            _, _, _, ids, _ = next(r for r in overview_rows() if r[0] == prefix)
            if i >= len(ids):
                print(f"note: {prefix} has only {len(ids)} rows; row {i} not clicked")
                continue
            at.button(key=f"{prefix}{i}").click().run()
            qp = at.query_params
            ok = (not at.exception and at.radio(key="page").value == view and at.selectbox(key=sel).value == ids[i]
                  and qp.get("view") == view and qp.get("id") == str(ids[i]))
            if not ok:
                failures.append(f"click {prefix}{i} {currency}")
                print(f"::error title=UI smoke: click {prefix}{i} {currency}::page={at.radio(key='page').value} "
                      f"{sel}={at.selectbox(key=sel).value if at.selectbox(key=sel) else None} want {view}/{ids[i]}; query {dict(qp)}")
            else:
                print("ok", f"click {prefix}{i} in {currency} opens {view} {ids[i]}")


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
    check_metrics(at, "Overview")
    check_vol_label(at, "Overview")
    check_vol_caption(at, "Overview")
    check_open_buttons(at, "Overview")
    lf = [m.value for m in at.metric if m.label == "Latest filing"]
    if lf and (lf[0] == "n/a" or len(lf[0].split()) in (2, 3)):
        print("ok Latest filing", lf[0])
    else:
        failures.append("latest filing")
        print(f"::error title=UI smoke: latest filing::unexpected value {lf}")
    # no sidebar any more: the controls live in a Settings expander under the title
    if len(at.sidebar) == 0:
        print("ok no sidebar children")
    else:
        failures.append("sidebar")
        print("::error title=UI smoke: sidebar::the sidebar is not empty")
    if any(e.label == "Settings" for e in at.expander) and at.button(key="refresh") is not None:
        print("ok Settings expander and refresh button")   # the refresh button is not clicked: it would download the database
    else:
        failures.append("settings")
        print("::error title=UI smoke: settings::Settings expander or refresh button missing")
    # every option combination on the overview (re-fetch the radio after each run)
    for key, label in (("currency", "Currency"), ("basis", "Volume basis")):
        for opt in at.radio(key=key).options:
            at.radio(key=key).set_value(opt).run()
            check(at, f"Overview with {label}={opt}")
            check_metrics(at, f"Overview with {label}={opt}")
            check_vol_label(at, f"Overview with {label}={opt}")
            check_open_buttons(at, f"Overview with {label}={opt}")

    for currency in ("USD", "EUR"):
        check_click_through(currency)

    # settings survive a view change
    at = fresh()
    at.radio(key="currency").set_value("EUR").run()
    basis_before = at.radio(key="basis").value
    at.radio(key="page").set_value("Ticker").run()
    at.radio(key="page").set_value("Overview").run()
    if at.radio(key="currency").value == "EUR" and at.radio(key="basis").value == basis_before:
        print("ok settings persist across views")
    else:
        failures.append("persistence")
        print("::error title=UI smoke: persistence::currency or basis changed after switching views")

    for page, key, ids in (("Member", "member_sel", members), ("Committee", "committee_sel", committees),
                           ("Ticker", "ticker_sel", tickers)):
        sample = ids if len(ids) <= 40 else random.sample(ids, 40)
        if page == "Member":
            sample = sample + paper_only[:5]
        at = fresh()
        at.radio(key="page").set_value(page).run()
        check(at, f"{page} default")
        check_metrics(at, f"{page} default")
        check_vol_label(at, f"{page} default")
        check_vol_caption(at, f"{page} default")
        check_compact_table(at, f"{page} default")
        if page == "Ticker":
            check_ticker_tabs(at, f"{page} default")
        at.radio(key="basis").set_value("Filed minimum").run()
        check_metrics(at, f"{page} Filed minimum")
        check_vol_label(at, f"{page} Filed minimum")
        check_vol_caption(at, f"{page} Filed minimum")
        check_compact_table(at, f"{page} Filed minimum")      # Committee: the compact table's header reads "Min. volume"
        if page == "Ticker":
            check_ticker_tabs(at, f"{page} Filed minimum")
        at.radio(key="basis").set_value("Midpoint estimate").run()
        for item in sample:
            try:
                at.selectbox(key=key).set_value(item).run()
            except Exception as e:           # a paper-only member is not in the Member selectbox options? report, don't hide
                failures.append(f"{page}:{item}")
                print(f"::error title=UI smoke: {page} {item}::{type(e).__name__}: {str(e)[:200]}")
                continue
            check(at, f"{page} {item}")
        # the whole view again in EUR
        if "EUR" in at.radio(key="currency").options:
            at.radio(key="currency").set_value("EUR").run()
            check(at, f"{page} in EUR")

    # Ticker tabs for an ETF, a ticker with no price, and a plain stock, in USD and EUR; the data has no ticker without trades
    import db
    tcon = db.connect()
    prof = {t: db.ticker_profile(tcon, t) for t in tickers}
    picks = {"ETF": next((t for t in tickers if prof[t]["kind"] == "etf"), None),
             "no-price": next((t for t in tickers if not prof[t]["as_of"]), None),
             "stock": next((t for t in tickers if prof[t]["kind"] == "equity" and prof[t]["as_of"]), None)}
    for kind, pick in picks.items():
        if pick is None:
            print(f"note: no {kind} ticker in this data; its tabs were not checked")
            continue
        for currency in ("USD", "EUR"):
            at = fresh()
            at.radio(key="page").set_value("Ticker").run()
            at.selectbox(key="ticker_sel").set_value(pick).run()
            if currency != "USD":
                at.radio(key="currency").set_value(currency).run()
            check(at, f"Ticker tabs {kind} {pick} {currency}")
            check_ticker_tabs(at, f"{kind} {pick} {currency}", expect_etf=(kind == "ETF"), expect_price=(kind != "no-price"))
    print("note: the data has no ticker with zero trades (tickers come from trades); that case was not checked")

    # members and committees with no sector mapping show the visible n/a note; mapped ones do not
    notes = {"Member": "Committee-relevant is n/a: none of this member's committees map to sectors, "
                       "so the sector heuristic does not apply.",
             "Committee": "Committee-relevant is n/a: this committee does not map to sectors, "
                          "so the sector heuristic does not apply."}
    for page, key, ids, mapped in (("Member", "member_sel", members, lambda i: db.member_sectors(con, i)),
                                   ("Committee", "committee_sel", committees, db.committee_sectors)):
        for want_note in (True, False):
            pick = next((i for i in ids if bool(mapped(i)) != want_note), None)
            if pick is None:
                print(f"note: no {page} {'without' if want_note else 'with'} a sector mapping in this data; caption not checked")
                continue
            at = fresh()
            at.radio(key="page").set_value(page).run()
            at.selectbox(key=key).set_value(pick).run()
            note = notes[page]
            rel = [m for m in at.metric if m.label == "Committee-relevant"]
            if has_caption(at, note) != want_note or (want_note and (not rel or rel[0].value != "n/a")):
                failures.append(f"{page} sector note {pick}")
                print(f"::error title=UI smoke: {page} sector note::{pick}: caption shown={has_caption(at, note)}, expected {want_note}")
            else:
                print(f"ok {page} {pick} n/a caption {'shown' if want_note else 'absent'}")

    # shared links restore the view; a stale id falls back instead of crashing
    for view, ident in (("Ticker", tickers[0]), ("Member", members[0]), ("Committee", committees[0]),
                        ("Ticker", "NOT-A-TICKER"), ("Member", "ZZZZ"), ("Bogus", "x")):
        at = AppTest.from_file(APP, default_timeout=90)
        at.query_params["view"] = view
        at.query_params["id"] = ident
        at.run()
        check(at, f"shared link view={view} id={ident}")
        want = view if view in ("Overview", "Member", "Committee", "Ticker") else "Overview"
        if at.radio(key="page").value != want:
            failures.append(f"shared link view={view}")
            print(f"::error title=UI smoke: shared link view={view}::view is {at.radio(key='page').value}, expected {want}")

    print(f"UI smoke finished: {len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
