"""Streamlit dashboard: congressional trades, committees and estimated volume.

Run:  streamlit run app.py
"""
import os
import shutil
import urllib.request

import pandas as pd
import streamlit as st

import importlib

import brokers
import db

# Streamlit keeps imported modules alive between redeploys; reload so a new db.py/brokers.py is picked up without a reboot.
importlib.reload(db)
importlib.reload(brokers)

# The nightly GitHub Action publishes the database to the `data` branch; the app fetches it from there.
DB_URL = os.environ.get("DB_URL", "https://raw.githubusercontent.com/berteniris-spec/Stock-Tracker/data/congress.db")


def download_db(url=DB_URL):
    tmp = db.DB_PATH.with_suffix(".tmp")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, db.DB_PATH)


st.set_page_config(page_title="Congress Trades", layout="wide")

if not db.DB_PATH.exists():  # first start on a fresh host: fetch the published database
    try:
        download_db()
    except Exception as e:
        st.error(f"No local database and the published one could not be fetched ({e}). "
                 "Run `python ingest_committees.py` and `python house_importer.py` locally, or set DB_URL.")
        st.stop()


con = db.connect()
con.executescript(db.SCHEMA)  # a database published before newer tables existed still works
# a fresh connection per run: cheap for SQLite, and never stale after a data refresh


RATE, RATE_DATE = db.usd_per_eur(con)      # USD per 1 EUR (ECB reference rate)
CURRENCY = "USD"                           # set from the sidebar below


def conv(x):
    """USD -> the selected display currency."""
    return x / RATE if CURRENCY == "EUR" and RATE else x


def sym():
    return "€" if CURRENCY == "EUR" and RATE else "$"


def usd(n):
    """Format a USD amount in the selected currency (name kept: it is called from many places)."""
    return f"{sym()}{int(conv(n)):,}" if n == n and n is not None else "n/a"


LABELS = {"est_volume": st.column_config.NumberColumn("Volume"),
          "amount_est": st.column_config.NumberColumn("Est. amount"),
          "amount_min": st.column_config.NumberColumn("Min"),
          "amount_max": st.column_config.NumberColumn("Max"),
          "price": st.column_config.NumberColumn("Last close"),
          "exchange": "Exchange"}
MONEY_COLS = ("est_volume", "amount_est", "amount_min", "amount_max")
PRICE_COLS = ("price",)


def show(df):
    """Table with $ and thousands separators; the underlying numbers stay numeric so sorting works."""
    df = df.copy()
    if "title" in df:
        df["title"] = df["title"].fillna("")
    for c in MONEY_COLS + PRICE_COLS:
        if c in df.columns:
            df[c] = df[c].map(lambda v: conv(v) if v == v and v is not None else v)   # stays numeric: sorting still works
    fmt = {c: sym() + "{:,.0f}" for c in MONEY_COLS if c in df.columns}
    fmt.update({c: sym() + "{:,.2f}" for c in PRICE_COLS if c in df.columns})
    st.dataframe(df.style.format(fmt, na_rep="") if fmt else df,
                 hide_index=True, column_config=LABELS, use_container_width=True)


def relevant_metric(col, df, sectors_known):
    if sectors_known:
        col.metric("Committee-relevant trades", int(df["committee_relevant"].sum()))
    else:
        col.metric("Committee-relevant trades", "n/a", help="No sector mapping for this committee: its "
                   "jurisdiction is broad or procedural, so the heuristic doesn't apply.")


st.title("Congress trades")
if db.has_sample_data(con):
    st.warning("Sample data is loaded: the members marked *(fictional)* and their trades are invented demo rows. "
               "Run `python load_sample.py --purge` to remove them.")
st.caption("Volume is estimated from disclosure ranges (midpoint by default; switch to the filed minimum in the sidebar). "
           "Filings can lag trades by up to 45 days. Committee data is a current snapshot, "
           "not membership as of each trade date.")

known, total = db.sector_coverage(con)
if total:
    st.caption(f"Sector is known for {known:,} of {total:,} trades ({100 * known / total:.0f}%). Sectors come from the FinanceDatabase classification "
               "and are approximate; the committee-relevance flag only applies where a sector is known.")

paper = db.paper_filings(con)
if not paper.empty:
    st.info(f"**Coverage gap:** {len(paper)} paper filings from {paper['bioguide_id'].nunique()} members are not "
            "imported (scanned forms with handwritten or ticked-box entries can't be read reliably). "
            "A member with no trades listed here may still have traded.")
    with st.expander("Which filings are missing?"):
        st.dataframe(paper[["member", "year", "doc_id", "url"]], hide_index=True, use_container_width=True,
                     column_config={"url": st.column_config.LinkColumn("Original filing", display_text="open PDF"),
                                    "doc_id": "Filing ID", "year": "Year", "member": "Member"})

page = st.sidebar.radio("View", ["Overview", "Member", "Committee", "Ticker"])
basis = st.sidebar.radio(
    "Volume basis", ["Midpoint estimate", "Filed minimum"],
    help="Filings give ranges, some very wide ($5M-$25M). The midpoint can overstate a trade; "
         "the filed minimum is a conservative lower bound.")
db.set_basis("min" if basis == "Filed minimum" else "mid")
vol_label = "Volume (filed minimum)" if basis == "Filed minimum" else "Est. volume (midpoint)"
CURRENCY = st.sidebar.radio(
    "Currency", ["USD", "EUR"] if RATE else ["USD"],
    help="Filings and prices are in US dollars. EUR uses the latest ECB reference rate for ALL amounts, "
         "including past trades (not the rate on the trade date).")
if RATE:
    st.sidebar.caption(f"ECB rate: €1 = ${RATE:.4f} ({RATE_DATE})")
else:
    st.sidebar.caption("No EUR rate stored yet; it is fetched by the nightly update.")
have, total_t, newest = db.price_freshness(con)
if newest:
    st.sidebar.caption(f"Prices: end-of-day closes, newest {newest}; {have:,} of {total_t:,} tickers have one.")
if st.sidebar.button("Refresh data from GitHub"):
    try:
        download_db()
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Refresh failed: {e}")

if page == "Overview":
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Most active members")
        show(db.members_with_trades(con)[["name", "chamber", "party", "trades", "est_volume"]].head(25))
    with c2:
        st.subheader("Committees by trading volume")
        show(db.committees_with_trading(con)[["name", "members", "trades", "est_volume"]].head(25))
    st.subheader("Monthly estimated volume")
    mv = db.monthly_volume(con)
    if not mv.empty:
        st.bar_chart(mv.pivot(index="month", columns="tx_type", values="est_volume").fillna(0))
    st.subheader("Top tickers")
    show(db.top_tickers(con, 20))

elif page == "Member":
    members = db.members_with_trades(con)
    only_paper = db.paper_only_members(con)
    if members.empty and only_paper.empty:
        st.info("No trades loaded yet.")
        st.stop()
    labels = {r.bioguide_id: f"{r.name} ({r.chamber}, {r.state or ''})" for r in members.itertuples()}
    labels.update({r.bioguide_id: f"{r.name} ({r.chamber}, {r.state or ''}) - paper filings only"
                   for r in only_paper.itertuples()})
    bid = st.selectbox("Member", list(labels), format_func=labels.get)
    mc = db.member_committees(con, bid)
    tr = db.member_trades(con, bid)
    mp = db.paper_filings(con, bid)
    if not mp.empty:
        st.warning(f"{len(mp)} paper filing(s) by this member are not imported, so the trades below may be "
                   "incomplete: " + ", ".join(f"[{r.doc_id}]({r.url})" for r in mp.itertuples()))
    a, b, c = st.columns(3)
    a.metric("Trades", len(tr))
    b.metric(vol_label, usd(db.volume_of(tr)))
    relevant_metric(c, tr, bool(db.member_sectors(con, bid)))
    st.subheader("Committees")
    show(mc[["name", "title", "as_of"]])
    st.subheader("Trades")
    only_rel = st.checkbox("Only committee-relevant (sector heuristic)")
    show(tr[tr["committee_relevant"]] if only_rel else tr)

elif page == "Committee":
    ct = db.committees_with_trading(con)
    if ct.empty:
        st.info("No trades loaded yet.")
        st.stop()
    labels = dict(zip(ct["id"], ct["name"]))
    cid = st.selectbox("Committee", list(labels), format_func=labels.get)
    cm = db.committee_members(con, cid)
    tr = db.committee_trades(con, cid)
    a, b, c = st.columns(3)
    a.metric("Members with trades", int((cm["trades"] > 0).sum()))
    b.metric(vol_label, usd(db.volume_of(tr)))
    relevant_metric(c, tr, bool(db.committee_sectors(cid)))
    st.subheader("Members")
    only_traders = st.checkbox("Only members with trades", value=True)
    if only_traders:
        cm = cm[cm["trades"] > 0]
    show(cm[["name", "chamber", "party", "title", "trades", "est_volume"]])
    st.subheader("Trades by members of this committee")
    show(tr)

else:
    tickers = db.all_tickers(con)
    if not tickers:
        st.info("No trades loaded yet.")
        st.stop()
    t = st.selectbox("Ticker", tickers)
    prof = db.ticker_profile(con, t)
    df = db.ticker_summary(con, t)
    st.subheader(f"{t}" + (f" - {prof['name']}" if prof["name"] else ""))
    a, b, c, d = st.columns(4)
    if prof["price"] is not None:
        a.metric("Last close", f"${prof['price']:,.2f}",
                 delta=f"{100 * (prof['price'] / prof['prev_close'] - 1):+.1f}% on the day" if prof["prev_close"] else None)
        b.metric("Last close (EUR)", f"€{prof['price'] / RATE:,.2f}" if RATE else "n/a",
                 help="USD close converted at the latest ECB rate." if RATE else "No EUR rate stored yet.")
    else:
        a.metric("Last close", "n/a", help="No price found for this ticker (delisted, renamed, not a plain stock, or not fetched yet).")
        b.metric("Last close (EUR)", "n/a")
    c.metric("Exchange", prof["exchange"] or "unknown")
    d.metric("Type", {"equity": "Stock", "etf": "ETF / fund"}.get(prof["kind"], "unknown"))
    if prof["as_of"]:
        st.caption(f"Price is the end-of-day close on {prof['as_of']}, refreshed nightly; it is not a live quote. "
                   "Trades below were disclosed up to 45 days after they happened.")
    a, b = st.columns(2)
    a.metric("Trades", len(df))
    b.metric(vol_label, usd(db.volume_of(df)))
    show(df)

    st.subheader("Where can I buy it from the Netherlands?")
    verdict, per = brokers.availability(prof["kind"], prof["exchange_code"])
    st.write(verdict)
    if prof["kind"] == "etf":
        st.info(brokers.ETF_NOTE)
    bt = pd.DataFrame([{"Broker": x["name"], "Can I buy it?": per[x["name"]], "Site": x["url"], "Notes": x["note"]}
                       for x in brokers.BROKERS])
    st.dataframe(bt, hide_index=True, use_container_width=True,
                 column_config={"Site": st.column_config.LinkColumn("Site", display_text="open"),
                                "Notes": st.column_config.TextColumn("Notes", width="large")})
    st.caption(f"Compiled by hand, last reviewed {brokers.REVIEWED}: broker offerings and fees change, so confirm on the "
               "broker's site. Pick a broker supervised in the EU (check the AFM register). Dutch residents should also file a "
               "W-8BEN with their broker so US dividends are withheld at 15% instead of 30%. This is information, not "
               "investment advice; because of the filing delay, a politician's trade is old news by the time it is public.")
