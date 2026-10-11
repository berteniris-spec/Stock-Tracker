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


LABELS = {"est_volume": st.column_config.NumberColumn("Volume"),
          "amount_est": st.column_config.NumberColumn("Est. amount"),
          "amount_min": st.column_config.NumberColumn("Min"),
          "amount_max": st.column_config.NumberColumn("Max")}
MONEY_COLS = ("est_volume", "amount_est", "amount_min", "amount_max")


def show(df):
    """Table with $ and thousands separators; the underlying numbers stay numeric so sorting works."""
    df = df.copy()
    if "title" in df:
        df["title"] = df["title"].fillna("")
    fmt = {c: "${:,.0f}" for c in MONEY_COLS if c in df.columns}
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
    st.caption(f"Sector is known for {known:,} of {total:,} trades ({100 * known / total:.0f}%). Sectors come from SEC "
               "SIC codes and are approximate; the committee-relevance flag only applies where a sector is known.")

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
    df = db.ticker_summary(con, t)
    a, b = st.columns(2)
    a.metric("Trades", len(df))
    b.metric(vol_label, usd(db.volume_of(df)))
    show(df)
