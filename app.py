"""Streamlit dashboard: congressional trades, committees and estimated volume.

Run:  streamlit run app.py
"""
import os
import shutil
import urllib.request

import streamlit as st

import db

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


con = db.connect()  # a fresh connection per run: cheap for SQLite, and never stale after a data refresh


def usd(n):
    return f"${int(n):,}" if n == n and n is not None else "n/a"


MONEY = {"est_volume": st.column_config.NumberColumn("Est. volume", format="$%d"),
         "amount_est": st.column_config.NumberColumn("Est. amount", format="$%d"),
         "amount_min": st.column_config.NumberColumn("Min", format="$%d"),
         "amount_max": st.column_config.NumberColumn("Max", format="$%d")}

st.title("Congress trades")
if db.has_sample_data(con):
    st.warning("Sample data is loaded: the members marked *(fictional)* and their trades are invented demo rows. "
               "Run `python load_sample.py --purge` to remove them.")
st.caption("Volume is estimated from disclosure ranges (midpoint by default; switch to the filed minimum in the sidebar). "
           "Filings can lag trades by up to 45 days. Committee data is a current snapshot, "
           "not membership as of each trade date.")

page = st.sidebar.radio("View", ["Overview", "Member", "Committee", "Ticker"])
basis = st.sidebar.radio(
    "Volume basis", ["Midpoint estimate", "Filed minimum"],
    help="Filings give ranges, some very wide ($5M-$25M). The midpoint can overstate a trade; "
         "the filed minimum is a conservative lower bound.")
db.set_basis("min" if basis == "Filed minimum" else "mid")
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
        st.dataframe(db.members_with_trades(con)[["name", "chamber", "party", "trades", "est_volume"]].head(25),
                     hide_index=True, column_config=MONEY, use_container_width=True)
    with c2:
        st.subheader("Committees by trading volume")
        st.dataframe(db.committees_with_trading(con)[["name", "members", "trades", "est_volume"]].head(25),
                     hide_index=True, column_config=MONEY, use_container_width=True)
    st.subheader("Monthly estimated volume")
    mv = db.monthly_volume(con)
    if not mv.empty:
        st.bar_chart(mv.pivot(index="month", columns="tx_type", values="est_volume").fillna(0))
    st.subheader("Top tickers")
    st.dataframe(db.top_tickers(con, 20), hide_index=True, column_config=MONEY, use_container_width=True)

elif page == "Member":
    members = db.members_with_trades(con)
    if members.empty:
        st.info("No trades loaded yet.")
        st.stop()
    labels = {r.bioguide_id: f"{r.name} ({r.chamber}, {r.state or ''})" for r in members.itertuples()}
    bid = st.selectbox("Member", list(labels), format_func=labels.get)
    mc = db.member_committees(con, bid)
    tr = db.member_trades(con, bid)
    a, b, c = st.columns(3)
    a.metric("Trades", len(tr))
    b.metric("Est. volume", usd(db.volume_of(tr)))
    c.metric("Committee-relevant trades", int(tr["committee_relevant"].sum()))
    st.subheader("Committees")
    st.dataframe(mc[["name", "title", "as_of"]], hide_index=True, use_container_width=True)
    st.subheader("Trades")
    only_rel = st.checkbox("Only committee-relevant (sector heuristic)")
    st.dataframe(tr[tr["committee_relevant"]] if only_rel else tr, hide_index=True,
                 column_config=MONEY, use_container_width=True)

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
    b.metric("Est. volume", usd(db.volume_of(tr)))
    c.metric("Committee-relevant trades", int(tr["committee_relevant"].sum()))
    st.subheader("Members")
    st.dataframe(cm[["name", "chamber", "party", "title", "trades", "est_volume"]], hide_index=True,
                 column_config=MONEY, use_container_width=True)
    st.subheader("Trades by members of this committee")
    st.dataframe(tr, hide_index=True, column_config=MONEY, use_container_width=True)

else:
    tickers = db.all_tickers(con)
    if not tickers:
        st.info("No trades loaded yet.")
        st.stop()
    t = st.selectbox("Ticker", tickers)
    df = db.ticker_summary(con, t)
    a, b = st.columns(2)
    a.metric("Trades", len(df))
    b.metric("Est. volume", usd(db.volume_of(df)))
    st.dataframe(df, hide_index=True, column_config=MONEY, use_container_width=True)
