"""Streamlit dashboard: congressional trades, committees and estimated volume.

Run:  streamlit run app.py
"""
import html
import os
import shutil
import urllib.request

import altair as alt
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
CURRENCY = "USD"                           # set from Settings below


def conv(x):
    """USD -> the selected display currency."""
    return x / RATE if CURRENCY == "EUR" and RATE else x


def sym():
    return "€" if CURRENCY == "EUR" and RATE else "$"


def usd(n):
    """Format a USD amount in the selected currency (name kept: it is called from many places)."""
    return f"{sym()}{int(conv(n)):,}" if n == n and n is not None else "n/a"


def short(n):
    """Compact money for headline numbers: $102M, $1.5B, €850K (exact figures stay in the tables)."""
    if n != n or n is None:
        return "n/a"
    v = conv(n)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            x = v / div
            return f"{sym()}{x:.1f}{suffix}" if x < 100 else f"{sym()}{x:.0f}{suffix}"
    return f"{sym()}{v:,.0f}"


LABELS = {"est_volume": st.column_config.NumberColumn("Volume"),
          "amount_est": st.column_config.NumberColumn("Est. amount"),
          "amount_min": st.column_config.NumberColumn("Min"),
          "amount_max": st.column_config.NumberColumn("Max"),
          "price": st.column_config.NumberColumn("Last close"),
          "exchange": "Exchange",
          "pe": st.column_config.NumberColumn("P/E", help="Trailing price/earnings (last 12 months). Blank = no positive earnings or no data."),
          "forward_pe": st.column_config.NumberColumn("Fwd P/E", help="Price / analysts' expected next-12-month earnings."),
          "peg": st.column_config.NumberColumn("PEG", help="P/E divided by expected earnings growth. Around 1 or below is often read as "
                                               "cheap relative to growth; definitions vary by data provider."),
          # plain-language headers instead of database column names
          "name": "Name", "member": "Member", "chamber": "Chamber", "party": "Party", "title": "Role",
          "as_of": "As of", "tx_date": "Trade date", "disclosure_date": "Disclosed", "ticker": "Ticker",
          "asset": "Asset", "tx_type": "Type", "owner": "Owner", "amount_label": "Amount range",
          "sector": "Sector", "trades": "Trades", "members": "Members",
          "committee_relevant": "Committee-relevant"}
MONEY_COLS = ("est_volume", "amount_est", "amount_min", "amount_max")
PRICE_COLS = ("price",)


def show(df, key=None, ids=None, goto=None, download=None):
    """Table with $ and thousands separators; the underlying numbers stay numeric so sorting works.

    With key/ids/goto the rows are clickable: selecting a row jumps to view `goto` with that row's id
    (`ids` is aligned with `df`'s rows; `goto` is (view name, session-state key of that view's selectbox)).
    """
    raw = df.copy()
    df = df.copy()
    if "title" in df:
        df["title"] = df["title"].fillna("")
    for c in MONEY_COLS + PRICE_COLS + ("pe", "forward_pe", "peg"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")      # all-missing columns arrive as None: show them blank, not "None"
    for c in MONEY_COLS + PRICE_COLS:
        if c in df.columns:
            df[c] = df[c].map(lambda v: conv(v) if v == v and v is not None else v)   # stays numeric: sorting still works
    fmt = {c: sym() + "{:,.0f}" for c in MONEY_COLS if c in df.columns}
    fmt.update({c: sym() + "{:,.2f}" for c in PRICE_COLS if c in df.columns})
    fmt.update({c: "{:,.1f}" for c in ("pe", "forward_pe") if c in df.columns})
    fmt.update({c: "{:,.2f}" for c in ("peg",) if c in df.columns})
    kwargs = dict(on_select="rerun", selection_mode="single-row", key=key) if key else {}
    event = st.dataframe(df.style.format(fmt, na_rep="") if fmt else df,
                         hide_index=True, column_config=LABELS, use_container_width=True, **kwargs)
    if download:       # a plain-file alternative to the canvas grid (works with screen readers and spreadsheets)
        st.download_button("Download as CSV (amounts in USD)", raw.to_csv(index=False).encode("utf-8"), file_name=f"{download}.csv",
                           mime="text/csv", key=f"dl_{download}")
    if key and ids is not None:
        rows = event.selection.rows
        if rows:
            st.session_state["_goto"] = (goto[0], goto[1], list(ids)[rows[0]])
            st.rerun()


def esc(s):
    """Escape dollar signs for markdown help/caption text (two $ in one string would render as LaTeX)."""
    return s.replace("$", "\\$")


NO_SECTORS_NOTE = {"Member": "Committee-relevant is n/a: none of this member's committees map to sectors, "
                             "so the sector heuristic does not apply.",
                   "Committee": "Committee-relevant is n/a: this committee does not map to sectors, "
                                "so the sector heuristic does not apply."}


def vol_caption(vol, scope=""):
    """Visible caption under a volume metric: the basis and the exact figure (tooltips are not reachable on touch)."""
    what = "the lowest figure in each filed range" if vol_label == "Min. volume" else "the midpoint of each filed range"
    st.caption(esc(f"{vol_label} is {what}{scope}. Exact: {usd(vol)}."))


def relevant_metric(col, df, sectors_known):
    col.metric("Committee-relevant", int(df["committee_relevant"].sum()) if sectors_known else "n/a")


st.markdown("""
<style>
/* captions: higher contrast and a slightly larger size than Streamlit's default light grey */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: rgba(0,0,0,.78) !important; font-size: .92rem !important; opacity: 1; }
@media (prefers-color-scheme: dark) {
  [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: rgba(239,236,227,.82) !important; }
}
/* tap targets: at least 44px tall for expander headers and link buttons */
[data-testid="stExpander"] summary, [data-testid="stLinkButton"] a { min-height: 44px; }
/* radio: the unselected ring was the 20% rule colour (1.7:1); about 55% ink gives at least 3:1 */
label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child { border-color: rgba(0,0,0,.55) !important; }
/* radio: visible keyboard focus */
label[data-testid="stRadioOption"]:focus-within { outline: 2px solid #4a70a9; outline-offset: 2px; }
@media (prefers-color-scheme: dark) {
  label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child { border-color: rgba(239,236,227,.55) !important; }
  label[data-testid="stRadioOption"]:focus-within { outline-color: #8fabd4; }
}
/* metric values wrap at spaces instead of being cut off with an ellipsis ("NYSE American", "ETF / fund") */
[data-testid="stMetric"] [data-testid="stMetricValue"] * { white-space: normal; overflow: visible; text-overflow: clip; overflow-wrap: break-word; }
/* just above the phone breakpoint the four-up columns are about 140px: a slightly smaller value keeps "$5,919.82" whole */
@media (min-width: 641px) and (max-width: 720px) {
  [data-testid="stMetricValue"], [data-testid="stMetricValue"] * { font-size: clamp(1.5rem, 5vw, 2.25rem); }
}
/* phone: metric strips two per row (Streamlit stacks columns one per row at 640px), values sized to fit */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] { flex: 0 0 calc(50% - .55rem); width: calc(50% - .55rem); min-width: 0; }
  [data-testid="stMetricValue"], [data-testid="stMetricValue"] * { font-size: clamp(1.5rem, 7vw, 2.25rem); }
}
/* refresh button: full width on a phone, capped on wider screens */
.st-key-refresh, .st-key-refresh [data-testid="stButton"], .st-key-refresh button { width: 100%; }
@media (min-width: 641px) { .st-key-refresh button { max-width: 24rem; } }
/* tap targets: buttons and each radio option (view switch, settings) at least 44px, wrapped rows spaced apart */
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button { min-height: 44px; }
label[data-testid="stRadioOption"] { min-height: 44px; align-items: center; }
[data-testid="stRadioGroup"] { row-gap: .25rem; }
</style>
""", unsafe_allow_html=True)
st.title("Congress trades")
VIEWS = ["Overview", "Member", "Committee", "Ticker"]
SELECT_KEYS = {"Member": "member_sel", "Committee": "committee_sel", "Ticker": "ticker_sel"}
if "page" not in st.session_state:        # first load of this session: restore the view from a shared link
    qp = st.query_params
    if qp.get("view") in VIEWS:
        st.session_state["page"] = qp["view"]
        if qp.get("view") in SELECT_KEYS and qp.get("id"):
            st.session_state[SELECT_KEYS[qp["view"]]] = qp["id"]


def sync_url(view, selected=None):
    """Mirror the current view (and selected item) into the URL so it can be bookmarked or shared."""
    params = {"view": view}
    if selected:
        params["id"] = str(selected)
    if dict(st.query_params) != params:
        st.query_params.from_dict(params)


# Click-through from a table row: set the target view and its selectbox BEFORE those widgets are created.
_goto = st.session_state.pop("_goto", None)
if _goto:
    st.session_state["page"], st.session_state[_goto[1]] = _goto[0], _goto[2]
page = st.radio("View", VIEWS, key="page", horizontal=True, label_visibility="collapsed")
with st.expander("Settings"):
    basis = st.radio(
        "Volume basis", ["Midpoint estimate", "Filed minimum"], key="basis", horizontal=True)
    st.caption("Filings give ranges, some very wide (\\$5M-\\$25M): the midpoint can overstate a trade; "
               "the filed minimum is a conservative lower bound.")
    currency_opts = ["USD", "EUR"] if RATE else ["USD"]
    if st.session_state.get("currency") not in (None, *currency_opts):
        st.session_state.pop("currency")     # e.g. EUR chosen, then a refresh left no stored rate
    CURRENCY = st.radio(
        "Currency", currency_opts, key="currency", horizontal=True)
    st.caption("Filings and prices are in US dollars. EUR uses the latest ECB reference rate for all amounts, "
               "including past trades.")
    if RATE:
        st.caption(f"ECB rate: €1 = ${RATE:.4f} ({RATE_DATE})")
    else:
        st.caption("No EUR rate stored yet; it is fetched by the nightly update.")
    have, total_t, newest = db.price_freshness(con)
    if newest:
        st.caption(f"Prices: end-of-day closes, newest {newest}; {have:,} of {total_t:,} tickers have one.")
    refresh = st.button("Refresh data from GitHub", key="refresh")
err_slot = st.container()                    # outside the collapsed expander, so a failure is visible
if refresh:
    try:
        download_db()
        st.rerun()
    except Exception as e:
        err_slot.error(f"Refresh failed: {e}")
db.set_basis("min" if basis == "Filed minimum" else "mid")
vol_label = "Min. volume" if basis == "Filed minimum" else "Est. volume"          # metric label (18 characters at most)
vol_full = "Volume (filed minimum)" if basis == "Filed minimum" else "Est. volume (midpoint)"   # full basis name for tooltips

if db.has_sample_data(con):
    st.warning("Sample data is loaded: the members marked *(fictional)* and their trades are invented demo rows. "
               "Run `python load_sample.py --purge` to remove them.")
known, total = db.sector_coverage(con)
paper = db.paper_filings(con)
if not paper.empty:
    n_members = paper["bioguide_id"].nunique()
    gap = (f"{len(paper)} paper filing{'s' if len(paper) != 1 else ''} not imported "
           f"({n_members} member{'s' if n_members != 1 else ''}).")
    st.caption(f"**Coverage gap:** {gap} Details under About this data.")
with st.expander("About this data"):
    st.markdown(
        "- **Volume** is estimated from disclosure ranges (midpoint by default; switch to the filed minimum in Settings).\n"
        "- **Filings lag trades** by up to 45 days, so a trade is old news by the time it is public.\n"
        "- **Committee data** is a current snapshot, not membership as of each trade date.\n"
        + (f"- **Sector** is known for {known:,} of {total:,} trades ({100 * known / total:.0f}%), from the FinanceDatabase "
           "classification; sectors are approximate and the committee-relevance flag only applies where a sector is known.\n" if total else ""))
    if not paper.empty:
        st.markdown("Some members may have traded more than shown. Filings not imported:")
        rows = "\n".join(f"| {r.member} | {r.year} | [Open filing {r.doc_id} (PDF)]({r.url}) |" for r in paper.itertuples())
        st.markdown("| Member | Year | Filing |\n|---|---|---|\n" + rows)

if page == "Overview":
    sync_url("Overview")
    stats = db.overview_stats(con)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Trades", f"{stats['trades']:,}")
    k2.metric("Members", f"{stats['members']:,}", help="Members of Congress with at least one imported trade.")
    k3.metric(vol_label, short(stats["volume"]), help=esc(f"{vol_full}. Exact: {usd(stats['volume'])}"))
    newest_d = pd.to_datetime(stats["newest"]) if stats["newest"] else None
    k4.metric("Latest filing", newest_d.strftime("%d %b" if newest_d.year == pd.Timestamp.today().year else "%d %b %Y") if newest_d is not None else "n/a",
              help=f"Newest disclosure date in the data: {stats['newest']}" if stats["newest"] else None)
    vol_caption(stats["volume"], ", summed over all trades")
    if True:
        st.subheader("Most active members")
        top_members = db.members_with_trades(con).head(25)
        st.caption("Tick the box at the start of a row to open that member.")
        show(top_members[["name", "party", "trades", "est_volume"]], key="ov_members",
             ids=top_members["bioguide_id"], goto=("Member", "member_sel"))
    if True:
        st.subheader("Committees by trading volume")
        top_committees = db.committees_with_trading(con).head(25)
        st.caption("Tick the box at the start of a row to open that committee.")
        show(top_committees[["name", "trades", "est_volume"]], key="ov_committees",
             ids=top_committees["id"], goto=("Committee", "committee_sel"))
    st.subheader("Monthly estimated volume")
    mv = db.monthly_volume(con)
    if not mv.empty:
        mv = mv.copy()
        mv["est_volume"] = mv["est_volume"].map(conv)
        cur = "EUR" if CURRENCY == "EUR" and RATE else "USD"
        types = ["Purchase", "Sale", "Sale (Partial)", "Exchange"]
        palette = ["#0072B2", "#D55E00", "#E69F00", "#7F7F7F"]      # colour-blind-safe (Okabe-Ito) hues
        chart = (alt.Chart(mv, title=f"Estimated trade volume per month ({cur}, by trade date)")
                 .mark_bar()
                 .encode(x=alt.X("month:O", title="Month", axis=alt.Axis(labelAngle=-45, labelOverlap="parity")),
                         y=alt.Y("est_volume:Q", title=f"Estimated volume ({cur})", axis=alt.Axis(format="~s")),
                         color=alt.Color("tx_type:N", title="Type", scale=alt.Scale(domain=types, range=palette)),
                         order=alt.Order("tx_type:N"),
                         tooltip=[alt.Tooltip("month:O", title="Month"), alt.Tooltip("tx_type:N", title="Type"),
                                  alt.Tooltip("est_volume:Q", title=f"Volume ({cur})", format=",.0f")])
                 .properties(height=320))
        st.altair_chart(chart, use_container_width=True)
        with st.expander("Show the chart data as a table"):
            table = (mv.pivot(index="month", columns="tx_type", values="est_volume").fillna(0)
                     .sort_index(ascending=False).reset_index().rename(columns={"month": "Month"}))
            st.dataframe(table.style.format({c: sym() + "{:,.0f}" for c in table.columns if c != "Month"}),
                         hide_index=True, use_container_width=True)
    st.subheader("Top tickers")
    top_t = db.top_tickers(con, 20)
    st.caption("Tick the box at the start of a row to open that ticker.")
    show(top_t, key="ov_tickers", ids=top_t["ticker"], goto=("Ticker", "ticker_sel"), download="top_tickers")

elif page == "Member":
    members = db.members_with_trades(con)
    only_paper = db.paper_only_members(con)
    if members.empty and only_paper.empty:
        st.info("No trades loaded yet.")
        st.stop()
    labels = {r.bioguide_id: f"{r.name} ({r.chamber}, {r.state or ''})" for r in members.itertuples()}
    labels.update({r.bioguide_id: f"{r.name} ({r.chamber}, {r.state or ''}) - paper filings only"
                   for r in only_paper.itertuples()})
    if st.session_state.get("member_sel") not in labels:      # e.g. a stale id from a shared link
        st.session_state.pop("member_sel", None)
    bid = st.selectbox("Member", list(labels), format_func=labels.get, key="member_sel")
    sync_url("Member", bid)
    mc = db.member_committees(con, bid)
    tr = db.member_trades(con, bid)
    mp = db.paper_filings(con, bid)
    if not mp.empty:
        st.warning(f"{len(mp)} paper filing(s) by this member are not imported, so the trades below may be "
                   "incomplete: " + ", ".join(f"[{r.doc_id}]({r.url})" for r in mp.itertuples()))
    a, b, c = st.columns(3)
    a.metric("Trades", len(tr))
    vol = db.volume_of(tr)
    b.metric(vol_label, short(vol), help=esc(f"{vol_full}. Exact: {usd(vol)}"))
    sectors_known = bool(db.member_sectors(con, bid))
    relevant_metric(c, tr, sectors_known)
    vol_caption(vol)
    if not sectors_known:
        st.caption(NO_SECTORS_NOTE["Member"])
    st.subheader("Committees")
    if mc.empty:
        st.info("No current committee assignments in the data for this member.")
    else:
        show(mc[["name", "title", "as_of"]])
    st.subheader("Trades")
    only_rel = st.checkbox("Only committee-relevant (sector heuristic)")
    show(tr[tr["committee_relevant"]] if only_rel else tr, download=f"trades_{bid}")

elif page == "Committee":
    ct = db.committees_with_trading(con)
    if ct.empty:
        st.info("No trades loaded yet.")
        st.stop()
    labels = dict(zip(ct["id"], ct["name"]))
    if st.session_state.get("committee_sel") not in labels:
        st.session_state.pop("committee_sel", None)
    cid = st.selectbox("Committee", list(labels), format_func=labels.get, key="committee_sel")
    sync_url("Committee", cid)
    cm = db.committee_members(con, cid)
    tr = db.committee_trades(con, cid)
    a, b, c = st.columns(3)
    a.metric("Members trading", int((cm["trades"] > 0).sum()))
    vol = db.volume_of(tr)
    b.metric(vol_label, short(vol), help=esc(f"{vol_full}. Exact: {usd(vol)}"))
    sectors_known = bool(db.committee_sectors(cid))
    relevant_metric(c, tr, sectors_known)
    vol_caption(vol)
    if not sectors_known:
        st.caption(NO_SECTORS_NOTE["Committee"])
    st.subheader("Members")
    only_traders = st.checkbox("Only members with trades", value=True)
    if only_traders:
        cm = cm[cm["trades"] > 0]
    show(cm[["name", "chamber", "party", "title", "trades", "est_volume"]])
    st.subheader("Trades by members of this committee")
    show(tr, download=f"committee_{cid}_trades")

else:
    tickers = db.all_tickers(con)
    if not tickers:
        st.info("No trades loaded yet.")
        st.stop()
    if st.session_state.get("ticker_sel") not in tickers:
        st.session_state.pop("ticker_sel", None)
    t = st.selectbox("Ticker", tickers, key="ticker_sel")
    sync_url("Ticker", t)
    prof = db.ticker_profile(con, t)
    df = db.ticker_summary(con, t)
    st.subheader(f"{t}" + (f" - {prof['name']}" if prof["name"] else ""))
    a, b, c, d = st.columns(4)
    if prof["price"] is not None:
        a.metric("Close (USD)", f"${prof['price']:,.2f}",
                 delta=f"{100 * (prof['price'] / prof['prev_close'] - 1):+.1f}% on the day" if prof["prev_close"] else None)
        b.metric("Close (EUR)", f"€{prof['price'] / RATE:,.2f}" if RATE else "n/a",
                 help="USD close converted at the latest ECB rate." if RATE else "No EUR rate stored yet.")
    else:
        a.metric("Close (USD)", "n/a")
        b.metric("Close (EUR)", "n/a")
    c.metric("Exchange", prof["exchange"] or "unknown")
    d.metric("Type", {"equity": "Stock", "etf": "ETF / fund"}.get(prof["kind"], "unknown"))
    if not prof["as_of"]:
        st.caption("No price found for this ticker (delisted, renamed, not a plain stock, or not fetched yet).")
    else:
        st.caption(f"Price is the end-of-day close on {prof['as_of']}, refreshed nightly; it is not a live quote. "
                   "Trades below were disclosed up to 45 days after they happened.")
    if prof["kind"] != "etf":
        a, b, c = st.columns(3)
        na = "n/a"
        a.metric("P/E", f"{prof['pe']:.1f}" if prof["pe"] else na)
        b.metric("Fwd P/E", f"{prof['forward_pe']:.1f}" if prof["forward_pe"] else na)
        c.metric("PEG", f"{prof['peg']:.2f}" if prof["peg"] else na)
        st.caption("Ratios come from Yahoo Finance, refreshed nightly, and are shown for reference: a low or high number is not "
                   "by itself a reason to buy or sell, and sectors differ widely (compare against similar companies).")
        st.caption("P/E is price over the last 12 months of earnings, Fwd P/E uses expected earnings for the next 12 months, "
                   "and PEG is P/E divided by expected earnings growth. n/a means no positive earnings, no growth figure or no data.")
    a, b = st.columns(2)
    a.metric("Trades", len(df))
    vol = db.volume_of(df)
    b.metric(vol_label, short(vol), help=esc(f"{vol_full}. Exact: {usd(vol)}"))
    vol_caption(vol)
    show(df, download=f"ticker_{t}_trades")

    st.subheader("Where can I buy it from the Netherlands?")
    verdict, per = brokers.availability(prof["kind"], prof["exchange_code"])
    st.write(verdict)
    if prof["kind"] == "etf":
        st.info(brokers.ETF_NOTE)
    for x in brokers.BROKERS:
        with st.expander(f"{x['name']}: {per[x['name']]}"):
            st.write(x["note"])
            st.link_button(f"Open {x['name']}", x["url"])
    with st.expander("Show the brokers as a table"):
        trs = "".join(f"<tr><td>{html.escape(x['name'])}</td><td>{html.escape(per[x['name']])}</td><td>{html.escape(x['note'])}</td>"
                      f"<td><a href=\"{html.escape(x['url'])}\">Open {html.escape(x['name'])}</a></td></tr>" for x in brokers.BROKERS)
        st.markdown('<div style="overflow-x: auto"><table><thead><tr><th>Broker</th><th>Can I buy it?</th><th>Notes</th><th>Link</th>'
                    f"</tr></thead><tbody>{trs}</tbody></table></div>", unsafe_allow_html=True)   # real HTML table: screen-reader friendly
    st.caption(f"Compiled by hand, last reviewed {brokers.REVIEWED}: broker offerings and fees change, so confirm on the "
               "broker's site. Pick a broker supervised in the EU (check the AFM register). Dutch residents should also file a "
               "W-8BEN with their broker so US dividends are withheld at 15% instead of 30%. This is information, not "
               "investment advice; because of the filing delay, a politician's trade is old news by the time it is public.")
