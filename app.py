"""Streamlit dashboard: congressional trades, committees and estimated volume.

Run:  streamlit run app.py
"""
import html
import os
import re
import shutil
import urllib.request
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import importlib

import brokers
import db
import fundamentals as fd
import styles

# Streamlit keeps imported modules alive between redeploys; reload so a new db.py/brokers.py is picked up without a reboot.
importlib.reload(db)
importlib.reload(fd)
importlib.reload(brokers)
importlib.reload(styles)

LOGO = Path(__file__).parent / "assets" / "stocktrader-logo.png"

# The nightly GitHub Action publishes the database to the `data` branch; the app fetches it from there.
DB_URL = os.environ.get("DB_URL", "https://raw.githubusercontent.com/berteniris-spec/Stock-Tracker/data/congress.db")


def download_db(url=DB_URL):
    tmp = db.DB_PATH.with_suffix(".tmp")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, db.DB_PATH)


st.set_page_config(page_title="Congress Trades", page_icon=str(LOGO.with_name("favicon.png")), layout="wide")

if not db.DB_PATH.exists():  # first start on a fresh host: fetch the published database
    try:
        download_db()
    except Exception as e:
        st.error(f"**Database unavailable:** no local database and the published one could not be fetched ({e}). "
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


def csv_button(raw, download):
    """A plain-file alternative to the canvas grid (works with screen readers and spreadsheets)."""
    st.download_button("Download as CSV (amounts in USD)", raw.to_csv(index=False).encode("utf-8"), file_name=f"{download}.csv",
                       mime="text/csv", key=f"dl_{download}")


PHONE_ROWS = 25


def phone_table(df, cols, fmt):
    """Compact phone table: `cols` of the first PHONE_ROWS rows as a real HTML table, so long text wraps instead of clipping.

    `df` is already converted to the display currency and `fmt` is show()'s number format. st.table ignores column_config,
    so the headers come from LABELS. Callers pass trades newest first and members by volume, so the cap keeps the top rows.
    """
    cols = [c for c in cols if c in df.columns]
    label = {c: (LABELS.get(c) if isinstance(LABELS.get(c), str) else (LABELS.get(c) or {}).get("label")) or c for c in cols}
    view = df[cols].head(PHONE_ROWS).rename(columns=label)

    def cell(v, f=None):              # st.table renders each cell as markdown, so escape $ * _ and the like
        return "" if pd.isna(v) else md_esc(f.format(v) if f else v)

    styled = view.style.format({label[c]: (lambda v, f=fmt.get(c): cell(v, f)) for c in cols}).hide(axis="index")
    numeric = [label[c] for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if numeric:
        styled = styled.set_properties(subset=numeric, **{"text-align": "right"})
    keep = [label[c] for c in cols if c in ("tx_date", "ticker", "party") or label[c] in numeric]   # dates, tickers, parties and amounts never break; names and types wrap at spaces
    if keep:
        styled = styled.set_properties(subset=keep, **{"white-space": "nowrap"})
    st.table(styled)
    if len(df) > PHONE_ROWS:
        trades = "tx_date" in cols
        st.caption(f"Showing the {'newest' if trades else 'top'} {PHONE_ROWS} of {len(df):,} {'trades' if trades else 'members'}. "
                   "Tick Show all columns above for every column and row.")


VALID_IDS = None


def valid_ids():
    """{view: set of ids} the view's selectbox can show, so a link never lands on a missing option."""
    global VALID_IDS
    if VALID_IDS is None:
        VALID_IDS = {}
        for view, ident in search_options().values():
            VALID_IDS.setdefault(view, set()).add(ident)
    return VALID_IDS


def _targets(links, i):
    """(link, id, text) for each link of row i whose id exists in the target view."""
    return [(l, l["ids"][i], l["texts"][i]) for l in links
            if _has(l["ids"][i]) and l["ids"][i] in valid_ids().get(l["view"], set())]


def link_row(event, links):
    """After a row is selected in a table: open its only link, or offer one button per link (member and ticker)."""
    sel = event.selection if event is not None else None
    rows = list(sel.rows) if sel is not None and sel.rows else [c[0] for c in (sel.cells if sel is not None else [])]
    if not rows:
        return
    targets = _targets(links, rows[0])
    if not targets:
        st.caption("This row has no page of its own (for example a subcommittee).")
    if len(targets) == 1:
        l, ident, _ = targets[0]
        st.session_state["_goto"] = (l["view"], l["key"], ident)
        st.rerun()
    for l, ident, text in targets:
        st.button(f"Open {l['noun']}: {text}", key=f"go_{l['name']}_{l['noun']}", icon=":material/arrow_forward:",
                  on_click=_open, args=(l["view"], l["key"], ident))


def _go_select(skey, view, key, options):
    ident = options.get(st.session_state.get(skey))
    if ident is not None:
        st.session_state["_goto"] = (view, key, ident)
    st.session_state[skey] = None


def open_from_table(links):
    """Keyboard- and phone-friendly alternative to clicking a row: pick any member, committee or ticker in this table."""
    boxes = []
    for l in links:
        seen = {}
        for ident, text in zip(l["ids"], l["texts"]):
            if _has(ident) and ident in valid_ids().get(l["view"], set()) and str(text) not in seen:
                seen[str(text)] = ident
        if seen:
            boxes.append((l, seen))
    if not boxes:
        return
    st.caption("Click any cell to open that row's " + " or ".join(l["noun"] for l, _ in boxes) + ", or use the picker below.")
    with st.expander("Open a " + " or ".join(l["noun"] for l, _ in boxes) + " from this table"):
        for l, seen in boxes:
            skey = f"goto_{l['name']}_{l['noun']}"
            st.selectbox(f"Open {l['noun']}", list(seen)[:300], index=None, key=skey, placeholder=f"Choose a {l['noun']}",
                         on_change=_go_select, args=(skey, l["view"], l["key"], seen))


def show(df, key=None, ids=None, goto=None, download=None, phone_cols=None, name=None, desktop_only=False, links=None):
    """Table with $ and thousands separators; the underlying numbers stay numeric so sorting works.

    With key/ids/goto the rows are clickable: selecting a row jumps to view `goto` with that row's id
    (`ids` is aligned with `df`'s rows; `goto` is (view name, session-state key of that view's selectbox)).
    With `name` and `phone_cols` the full table sits in a container that CSS hides at 640px and narrower, where a
    second container shows `phone_cols` only as a wrapping st.table of the first 25 rows (canvas columns cannot
    wrap and clipped at 358px), with a "Show all columns" checkbox that switches to the full grid (both containers
    are in the page at every width, so resizing needs no rerun). With `name` and `desktop_only` the table is hidden at phone width and the
    caller draws the phone rendering. An empty table is never swapped.
    """
    links = [dict(l, name=name, texts=list(df[l["col"]]), ids=list(df[l["idcol"]] if l.get("idcol") else df[l["col"]]))
             for l in (links or []) if l["col"] in df.columns]            # per row, aligned with df
    hide = {l["idcol"] for l in links if l.get("idcol")}
    df = df.drop(columns=[c for c in hide if c in df.columns])          # id columns drive the links; they are not shown or exported
    raw = df.copy()
    df = df.copy()
    if "title" in df:
        df["title"] = df["title"].fillna("")
    if "tx_type" in df:       # a symbol as well as the words: type is never colour alone
        df["tx_type"] = df["tx_type"].map(lambda v: {"Purchase": "▲ Purchase", "Sale": "▼ Sale", "Sale (Partial)": "▼ Sale (Partial)"}.get(v, v))
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
    if links and name and not key:
        key = f"sel_{name}"
        kwargs = dict(on_select="rerun", selection_mode="single-cell", key=key)     # no checkbox column: click any cell
    styled = df.style.format(fmt, na_rep="") if fmt else df

    def grid(**kw):
        return st.dataframe(styled, hide_index=True, column_config=LABELS, use_container_width=True, **kw)

    if name and not df.empty and (phone_cols or desktop_only):
        with st.container(key=f"tbl_{name}"):
            event = grid(**kwargs)
        if phone_cols:
            with st.container(key=f"ph_{name}"):
                if st.checkbox("Show all columns", key=f"allcols_{name}"):
                    grid()
                    st.caption("Scroll sideways inside the table to see more columns.")
                else:
                    phone_table(df, phone_cols, fmt)
    else:
        event = grid(**kwargs)
    if download:
        csv_button(raw, download)
    if key and ids is not None:
        rows = event.selection.rows
        if rows:
            st.session_state["_goto"] = (goto[0], goto[1], list(ids)[rows[0]])
            st.rerun()
    if links:
        link_row(event, links)
        open_from_table(links)


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


def md_esc(s):
    """Escape text for a markdown label: dollar signs (esc) plus the characters that start emphasis, links or code."""
    return esc(re.sub(r"([\\`*_\[\]])", r"\\\1", str(s)))


def _open(view, select_key, ident):
    """Button callback: the same hand-off as selecting a table row; the `_goto` pop below switches the view."""
    st.session_state["_goto"] = (view, select_key, ident)


def _has(x):
    return x is not None and x == x and str(x).strip() != ""


def n_trades(n):
    return f"{int(n):,} trade{'s' if int(n) != 1 else ''}"


PARTY_DOT = {"Republican": ":red[●]", "Democrat": ":blue[●]"}


def party_label(party):
    """Party as a coloured dot plus the word, so colour is never the only signal."""
    return f"{PARTY_DOT.get(str(party), ':gray[●]')} {md_esc(party)}"


def ranking(name, df, cols, ids, goto, noun, label, download=None):
    """Overview ranking: a list of full-width buttons (click or tap a row to open it), the same at every width.

    `label(row)` is the text after the rank, already markdown-escaped. Ranks 11 and up sit in an expander.
    """
    if df.empty:                                  # nothing to rank: just the empty table, no captions or list
        show(df[cols], key=name, ids=ids, goto=goto, download=download)
        return
    ids = list(ids)
    with st.container(key=f"rank_{name}"):
        st.caption(f"Click or tap a row to open that {noun}. Volumes are estimated from "
                   f"{'the lowest figure' if vol_label == 'Min. volume' else 'the midpoint'} of each filed range.")
        slot = st.container()
        for i, row in enumerate(df.itertuples()):
            if i == 10:
                slot = st.expander(f"Show ranks 11 to {len(df)}")
            with slot:
                text, args = f"{i + 1}. {label(row)}", dict(key=f"open_{name}_{i}", on_click=_open, args=(goto[0], goto[1], ids[i]))
                try:
                    st.button(text, icon=":material/chevron_right:", icon_position="right", **args)
                except TypeError:                 # an older Streamlit without icon_position
                    st.button(text, **args)
    if download:
        csv_button(df[cols], download)


st.markdown(styles.CSS, unsafe_allow_html=True)
with st.container(key="topbar", horizontal=True, vertical_alignment="center"):
    with st.container(key="brand", horizontal=True, vertical_alignment="center"):
        if LOGO.exists():   # a missing file must not break the app
            st.image(str(LOGO), width=40, alt="StockTrader logo")
        st.title("Congress trades")
    settings_slot = st.container(key="settings_slot")
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


@st.cache_data(ttl=600, show_spinner=False)
def search_options():
    """{label: (view, id)} for the global search: members, committees and tickers that have trades."""
    c = db.connect()
    opts = {}
    for r in db.members_with_trades(c).itertuples():
        opts[f"{r.name} · member"] = ("Member", r.bioguide_id)
    for r in db.committees_with_trading(c).itertuples():
        opts[f"{r.name} · committee"] = ("Committee", r.id)
    for t in db.all_tickers(c):
        opts[f"{t} · ticker"] = ("Ticker", t)
    return opts


def _search_go():
    hit = search_options().get(st.session_state.get("search"))
    if hit:
        st.session_state["_goto"] = (hit[0], SELECT_KEYS[hit[0]], hit[1])
    st.session_state["search"] = None


st.selectbox("Search", list(search_options()), index=None, key="search", on_change=_search_go,
             placeholder="Search a member, committee or ticker", label_visibility="collapsed")
with settings_slot, st.popover("Settings", icon=":material/tune:"):
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
        err_slot.error(f"**Refresh failed:** {e}")
db.set_basis("min" if basis == "Filed minimum" else "mid")
vol_label = "Min. volume" if basis == "Filed minimum" else "Est. volume"          # metric label (18 characters at most)
LABELS["est_volume"] = st.column_config.NumberColumn(vol_label)       # grid and compact-table header follow the basis
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
    st.markdown(f":orange-badge[:material/info: Coverage gap: {gap}]", help="Details under About this data, at the bottom of the page.")

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
    mem = db.members_with_trades(con).merge(db.member_activity(con), on="bioguide_id", how="left").fillna({"buys": 0, "sells": 0, "recent": 0})
    rank_by = st.radio("Rank members by", ["Estimated volume", "Number of trades", "Last 90 days"], key="rank_by", horizontal=True)
    titles = {"Estimated volume": "Biggest estimated volume", "Number of trades": "Most trades", "Last 90 days": "Traded in the last 90 days"}
    st.subheader(titles[rank_by])
    if rank_by == "Number of trades":
        top_members = mem.sort_values(["trades", "est_volume"], ascending=False, kind="stable").head(25)
    elif rank_by == "Last 90 days":
        top_members = mem[mem["recent"] > 0].sort_values(["recent", "est_volume"], ascending=False, kind="stable").head(25)
    else:
        top_members = mem.head(25)                                  # already ordered by estimated volume

    def buy_bar(r):
        """Five blocks for the buy share of purchases and sales, with the numbers, so the split reads without colour."""
        n = int(r.buys + r.sells)
        if not n:
            return ""
        filled = round(5 * r.buys / n)
        return f"{'▮' * filled}{'▯' * (5 - filled)} {int(r.buys)} buy, {int(r.sells)} sell"

    def member_label(r):
        extra = f"{int(r.recent)} in 90 days" if rank_by == "Last 90 days" else buy_bar(r)
        return "\u00a0· ".join(x for x in (
            md_esc(r.name) + (f" ({party_label(r.party)})" if _has(r.party) else "") if _has(r.name) else "",
            n_trades(r.trades), md_esc(short(r.est_volume)), md_esc(extra)) if x)

    if not top_members.empty:
        st.caption("Each dot is a member: further right means more trades, higher means more estimated volume (both scales are "
                   "logarithmic, so each step is ten times more). A dot far up and left is a few very large filed ranges; "
                   "down and right is many small trades. Click a dot to open that member.")
        cmp = mem.assign(volume=mem["est_volume"].map(conv), party_name=mem["party"].map(lambda p: p if _has(p) else "Other"))
        cmp = cmp[(cmp["trades"] > 0) & (cmp["volume"] > 0)]
        pdom = ["Democrat", "Republican", "Other"]
        pick = alt.selection_point(name="pick", fields=["bioguide_id"], on="click", empty=False)
        cur_m = "EUR" if CURRENCY == "EUR" and RATE else "USD"
        scatter = (alt.Chart(cmp).mark_point(filled=True, size=90, opacity=.85, stroke="#ffffff", strokeWidth=.8)
                   .encode(x=alt.X("trades:Q", title="Number of trades (log scale)", scale=alt.Scale(type="log", domain=[cmp["trades"].min() * 0.8, cmp["trades"].max() * 1.3]),
                                   axis=alt.Axis(format="~s", grid=False)),
                           y=alt.Y("volume:Q", title=f"Estimated volume ({cur_m}, log scale)",
                                   scale=alt.Scale(type="log", domain=[cmp["volume"].min() * 0.6, cmp["volume"].max() * 1.6]),
                                   axis=alt.Axis(format="~s", gridOpacity=.35)),
                           color=alt.Color("party_name:N", title="Party", scale=alt.Scale(domain=pdom, range=["#0072B2", "#D55E00", "#7F7F7F"]),
                                           legend=alt.Legend(orient="bottom", columns=3)),
                           shape=alt.Shape("party_name:N", title="Party", scale=alt.Scale(domain=pdom, range=["circle", "square", "diamond"]),
                                           legend=alt.Legend(orient="bottom", columns=3)),
                           tooltip=[alt.Tooltip("name:N", title="Member"), alt.Tooltip("party_name:N", title="Party"),
                                    alt.Tooltip("trades:Q", title="Trades", format=","), alt.Tooltip("buys:Q", title="Purchases"),
                                    alt.Tooltip("sells:Q", title="Sales"), alt.Tooltip("volume:Q", title=f"Volume ({cur_m})", format=",.0f")])
                   .add_params(pick).properties(height=340, padding={"top": 8, "left": 5, "right": 5, "bottom": 5}))
        event = st.altair_chart(scatter, use_container_width=True, on_select="rerun", key="member_scatter", selection_mode="pick")
        try:
            chosen = (event.selection.get("pick") or [])
        except Exception:
            chosen = []
        if chosen and chosen[0].get("bioguide_id") in set(mem["bioguide_id"]):
            st.session_state["_goto"] = ("Member", "member_sel", chosen[0]["bioguide_id"])
            st.rerun()
        with st.expander("Show the chart data as a table"):
            st.dataframe(cmp[["name", "party_name", "trades", "buys", "sells", "recent", "volume"]]
                         .rename(columns={"name": "Member", "party_name": "Party", "trades": "Trades", "buys": "Purchases", "sells": "Sales",
                                          "recent": "Last 90 days", "volume": f"Volume ({cur_m})"})
                         .sort_values("Trades", ascending=False).style.format({f"Volume ({cur_m})": sym() + "{:,.0f}"}),
                         hide_index=True, use_container_width=True)
    ranking("ov_members", top_members, ["name", "party", "trades", "est_volume"], top_members["bioguide_id"],
            ("Member", "member_sel"), "member", member_label)
    st.subheader("Committees by trading volume")
    top_committees = db.committees_with_trading(con).head(25)
    ranking("ov_committees", top_committees, ["name", "trades", "est_volume"], top_committees["id"],
            ("Committee", "committee_sel"), "committee",
            lambda r: "\u00a0· ".join(x for x in (md_esc(r.name) if _has(r.name) else "", n_trades(r.trades), md_esc(short(r.est_volume))) if x))
    st.subheader("Monthly estimated volume")
    mv = db.monthly_volume(con)
    if not mv.empty:
        mv = mv.copy()
        mv["est_volume"] = mv["est_volume"].map(conv)
        cur = "EUR" if CURRENCY == "EUR" and RATE else "USD"
        types = ["Purchase", "Sale", "Sale (Partial)", "Exchange"]
        palette = ["#0072B2", "#D55E00", "#E69F00", "#7F7F7F"]      # colour-blind-safe (Okabe-Ito) hues
        try:
            is_light = st.context.theme.type != "dark"
        except Exception:
            is_light = True
        # Label only the first month of each quarter ("Q1 2024"); the other bars stay unlabelled but keep their tooltips.
        QUARTER_LABEL = ("(slice(datum.value, 5, 7) == '01' || slice(datum.value, 5, 7) == '04' || "
                         "slice(datum.value, 5, 7) == '07' || slice(datum.value, 5, 7) == '10') ? "
                         "'Q' + (floor((toNumber(slice(datum.value, 5, 7)) - 1) / 3) + 1) + ' ' + slice(datum.value, 0, 4) : ''")
        bar_outline = {"stroke": "rgba(0,0,0,0.6)", "strokeWidth": 1} if is_light else {}   # chart-partial is only 1.9:1 on cream
        chart = (alt.Chart(mv, title=["Estimated trade volume per month", f"({cur}, by trade date)"])
                 .mark_bar(**bar_outline)
                 .encode(x=alt.X("month:O", title="Quarter (first month shown)", axis=alt.Axis(labelAngle=-45, labelOverlap=False, ticks=False,
                                                                       labelExpr=QUARTER_LABEL)),
                         y=alt.Y("est_volume:Q", title=f"Estimated volume ({cur})", axis=alt.Axis(format="~s")),
                         color=alt.Color("tx_type:N", title="Type", scale=alt.Scale(domain=types, range=palette),
                                         legend=alt.Legend(orient="bottom", columns=2)),
                         order=alt.Order("tx_type:N"),
                         tooltip=[alt.Tooltip("month:O", title="Month"), alt.Tooltip("tx_type:N", title="Type"),
                                  alt.Tooltip("est_volume:Q", title=f"Volume ({cur})", format=",.0f")])
                 .properties(height=380, padding={"top": 8, "left": 5, "right": 5, "bottom": 5}))
        st.altair_chart(chart, use_container_width=True)
        with st.expander("Show the chart data as a table"):
            table = (mv.pivot(index="month", columns="tx_type", values="est_volume").fillna(0)
                     .sort_index(ascending=False).reset_index().rename(columns={"month": "Month"}))
            st.dataframe(table.style.format({c: sym() + "{:,.0f}" for c in table.columns if c != "Month"}),
                         hide_index=True, use_container_width=True)
    st.subheader("Net buying per month")
    st.caption("Purchases minus sales, by trade date. Above zero means members bought more than they sold that month.")
    if not mv.empty:
        net = mv.assign(sign=mv["tx_type"].map(lambda v: 1 if v == "Purchase" else (-1 if v.startswith("Sale") else 0)))
        net = net[net["sign"] != 0].assign(net=lambda d: d["est_volume"] * d["sign"]).groupby("month", as_index=False)["net"].sum()
        net["direction"] = net["net"].map(lambda v: "Net buying" if v >= 0 else "Net selling")
        nchart = (alt.Chart(net).mark_bar()
                  .encode(x=alt.X("month:O", title="Quarter (first month shown)", axis=alt.Axis(labelAngle=-45, labelOverlap=False, ticks=False, labelExpr=QUARTER_LABEL)),
                          y=alt.Y("net:Q", title=f"Net volume ({cur})", axis=alt.Axis(format="~s")),
                          color=alt.Color("direction:N", title="", scale=alt.Scale(domain=["Net buying", "Net selling"], range=["#0072B2", "#D55E00"]),
                                          legend=alt.Legend(orient="bottom")),
                          tooltip=[alt.Tooltip("month:O", title="Month"), alt.Tooltip("net:Q", title=f"Net ({cur})", format=",.0f")])
                  .properties(height=300, padding={"top": 8, "left": 5, "right": 5, "bottom": 5}))
        st.altair_chart(nchart, use_container_width=True)
    st.subheader("Volume by sector")
    sv = db.sector_volume(con)
    if not sv.empty:
        sv = sv.copy()
        sv["est_volume"] = sv["est_volume"].map(conv)
        schart = (alt.Chart(sv.head(12)).mark_bar(color="#1f3a5f")
                  .encode(y=alt.Y("sector:N", sort="-x", title=None), x=alt.X("est_volume:Q", title=f"Estimated volume ({cur})", axis=alt.Axis(format="~s")),
                          tooltip=[alt.Tooltip("sector:N", title="Sector"), alt.Tooltip("trades:Q", title="Trades", format=","),
                                   alt.Tooltip("est_volume:Q", title=f"Volume ({cur})", format=",.0f")])
                  .properties(height=max(120, 28 * min(len(sv), 12)), padding={"top": 8, "left": 5, "right": 5, "bottom": 5}))
        st.altair_chart(schart, use_container_width=True)
        with st.expander("Show the sector data as a table"):
            st.dataframe(sv.rename(columns={"sector": "Sector", "trades": "Trades", "est_volume": "Volume"}).style.format({"Volume": sym() + "{:,.0f}"}),
                         hide_index=True, use_container_width=True)
    st.subheader("Top tickers")
    top_t = db.top_tickers(con, 20)
    ranking("ov_tickers", top_t, list(top_t.columns), top_t["ticker"], ("Ticker", "ticker_sel"), "ticker",
            lambda r: "\u00a0· ".join(x for x in (md_esc(r.ticker), md_esc(r.name) if _has(r.name) else "",
                                             n_trades(r.trades), md_esc(short(r.est_volume))) if x),
            download="top_tickers")

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
    both = pd.concat([members, only_paper]).drop_duplicates("bioguide_id").set_index("bioguide_id")
    info = both.loc[bid] if bid in both.index else None
    if info is not None:
        pcolor = {"Republican": "red", "Democrat": "blue"}.get(str(info.get("party")), "gray")
        chips = [f":{pcolor}-badge[{info.get('party') if _has(info.get('party')) else 'Party n/a'}]", f":gray-badge[{info.get('chamber')} · {info.get('state') or 'n/a'}]"]
        top = [n for n in mc["name"] if ":" not in n]          # full committees; subcommittees stay in the Committees table
        chips += [f":gray-badge[{md_esc(n.replace('House Committee on ', '').replace('Senate Committee on ', ''))}]" for n in top[:3]]
        if len(mc) > min(len(top), 3):
            chips.append(f":gray-badge[+{len(mc) - min(len(top), 3)} more below]")
        st.subheader(md_esc(info["name"]))
        st.markdown(" ".join(chips))
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
        show(mc[["id", "name", "title", "as_of"]], name="member_committees",
             links=[dict(col="name", idcol="id", view="Committee", key="committee_sel", noun="committee")])
    st.subheader("Trades")
    only_rel = st.checkbox("Only committee-relevant (sector heuristic)")
    show(tr[tr["committee_relevant"]] if only_rel else tr, download=f"trades_{bid}",
         phone_cols=["tx_date", "ticker", "tx_type", "amount_est"], name="member_trades",
         links=[dict(col="ticker", view="Ticker", key="ticker_sel", noun="ticker")])

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
    st.subheader(md_esc(labels[cid]))
    st.markdown(f":gray-badge[{len(cm)} members] :gray-badge[{int((cm['trades'] > 0).sum())} with trades]")
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
    show(cm[["bioguide_id", "name", "chamber", "party", "title", "trades", "est_volume"]],
         phone_cols=["name", "party", "trades", "est_volume"], name="committee_members",
         links=[dict(col="name", idcol="bioguide_id", view="Member", key="member_sel", noun="member")])
    st.subheader("Trades by members of this committee")
    show(tr, download=f"committee_{cid}_trades",
         phone_cols=["member", "tx_date", "ticker", "tx_type", "amount_est"], name="committee_trades",
         links=[dict(col="member", idcol="bioguide_id", view="Member", key="member_sel", noun="member"),
                dict(col="ticker", view="Ticker", key="ticker_sel", noun="ticker")])

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
    st.caption("This is information, not investment advice.")
    tab_trades, tab_price, tab_brokers = st.tabs(["Trades", "Price", "Brokers"])
    with tab_trades:
        a, b = st.columns(2)
        a.metric("Trades", len(df))
        vol = db.volume_of(df)
        b.metric(vol_label, short(vol), help=esc(f"{vol_full}. Exact: {usd(vol)}"))
        vol_caption(vol)
        st.caption("Trades were disclosed up to 45 days after they happened.")
        show(df, download=f"ticker_{t}_trades", phone_cols=["member", "tx_date", "tx_type", "amount_est"], name="ticker_trades",
             links=[dict(col="member", idcol="bioguide_id", view="Member", key="member_sel", noun="member")])

    with tab_price:
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
            st.caption(f"Price is the end-of-day close on {prof['as_of']}, refreshed nightly; it is not a live quote.")
        hist = db.price_history(con, t)
        if not hist.empty:
            st.subheader("Price history")
            st.caption("Daily closes. Each marker is a day a member traded this stock: a triangle up for a purchase, a triangle down "
                       "for a sale, a diamond for an exchange. Hover a marker for who and how much.")
            cur = "EUR" if CURRENCY == "EUR" and RATE else "USD"
            line = hist.assign(close=hist["close"].map(conv))
            tr = df.assign(date=pd.to_datetime(df["tx_date"], errors="coerce")).dropna(subset=["date"]).sort_values("date")
            marks = pd.merge_asof(tr, line.sort_values("date")[["date", "close"]], on="date", direction="backward",
                                  tolerance=pd.Timedelta(days=5)).dropna(subset=["close"])
            types = ["Purchase", "Sale", "Sale (Partial)", "Exchange"]
            palette = ["#0072B2", "#D55E00", "#E69F00", "#7F7F7F"]
            try:
                light = st.context.theme.type != "dark"
            except Exception:
                light = True
            base = alt.Chart(line).mark_line(color="#1f3a5f" if light else "#8fabd4", strokeWidth=1.5).encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y", tickCount=6, labelOverlap=True, labelAngle=-30)),
                y=alt.Y("close:Q", title=f"Close ({cur})", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("close:Q", title=f"Close ({cur})", format=",.2f")])
            layers = [base]
            if not marks.empty:
                layers.append(alt.Chart(marks).mark_point(filled=True, size=110, opacity=.9, stroke="#ffffff", strokeWidth=.8).encode(
                    x="date:T", y="close:Q",
                    color=alt.Color("tx_type:N", title="Type", scale=alt.Scale(domain=types, range=palette), legend=alt.Legend(orient="bottom", columns=2)),
                    shape=alt.Shape("tx_type:N", title="Type", scale=alt.Scale(domain=types, range=["triangle-up", "triangle-down", "triangle-down", "diamond"]),
                                    legend=alt.Legend(orient="bottom", columns=2)),
                    tooltip=[alt.Tooltip("member:N", title="Member"), alt.Tooltip("tx_date:N", title="Trade date"),
                             alt.Tooltip("tx_type:N", title="Type"), alt.Tooltip("amount_label:N", title="Amount range")]))
            st.altair_chart(alt.layer(*layers).properties(height=340, padding={"top": 8, "left": 5, "right": 5, "bottom": 5}),
                            use_container_width=True)
            dropped = len(tr) - len(marks)
            st.caption(f"Closes from {hist['date'].min():%d %b %Y} to {hist['date'].max():%d %b %Y}."
                       + (f" {dropped} of {len(tr)} trades are not marked: they are before the first stored close or on days with no close." if dropped else ""))
            with st.expander("Show the closes as a table"):
                st.dataframe(line.sort_values("date", ascending=False).assign(date=lambda d: d["date"].dt.strftime("%Y-%m-%d"))
                             .rename(columns={"date": "Date", "close": f"Close ({cur})"}).style.format({f"Close ({cur})": "{:,.2f}"}),
                             hide_index=True, use_container_width=True)
        else:
            st.caption("No price history stored for this ticker yet; it is filled by the nightly update.")
        if prof["kind"] != "etf":
            fund = db.ticker_fundamentals(con, t)
            vals = {"pe": prof["pe"], "forward_pe": prof["forward_pe"], "peg": prof["peg"], **fund}
            meds = db.sector_medians(con, prof["sector"])
            have = any(fund[k] is not None for k in db.FUNDAMENTAL_KEYS)
            st.subheader("Health check")
            st.caption("Each number has a plain-language reading and a typical range. Ranges are rough guides, not verdicts: "
                       "industries differ, so compare with the sector median where it is shown. On each bar the thick marker is this stock, "
                       "the darker middle is the typical range, and the thin line is the sector median. Company figures are in US dollars.")
            if not have:
                st.caption("The health metrics (margins, debt, growth and more) are not loaded for this stock yet; "
                           "they are fetched nightly.")
            size = fd.market_cap_size(fund["market_cap"])
            for card, title in fd.CARDS:
                keys = [k for k, sp in fd.SPEC.items() if sp["card"] == card]
                with st.container(border=True, key=f"fund_{card}"):
                    st.markdown(f"**{title}**")
                    line = fd.headline(card, vals, size)
                    if line:
                        st.markdown(line)
                    for i in range(0, len(keys), 3):
                        cols = st.columns(3)
                        for col, k in zip(cols, keys[i:i + 3]):
                            v, med = vals.get(k), meds.get(k)
                            col.metric(fd.SPEC[k]["label"], fd.fmt(k, v), help=fd.SPEC[k]["help"])
                            if v is not None:
                                col.markdown(fd.bar_html(k, v, med[0] if med else None), unsafe_allow_html=True)
                            col.caption(esc(fd.context_text(k, v, med)))
                    if card == "risk":
                        cols = st.columns(3)
                        cols[0].metric("Market cap", fd.money(fund["market_cap"]), help="Total value of all the company's shares "
                                       "(share price times shares outstanding). Large is above $10B, mid-size $2B to $10B, small below $2B. "
                                       "Smaller companies tend to swing more.")
                        cols[0].caption(size or "No data from the provider.")
                        lo, hi = fund["week52_low"], fund["week52_high"]
                        pos = fd.range_position(lo, hi, prof["price"])
                        cols[1].metric("52-week range", esc(f"${lo:,.0f} to ${hi:,.0f}") if lo and hi else "n/a",
                                       help="The lowest and highest share price over the last year. The marker shows where the last close "
                                            "sits between them: far left is near the yearly low, far right near the yearly high.")
                        if pos is not None:
                            cols[1].markdown(fd.range_bar_html(pos, f"Last close is {100 * pos:.0f}% of the way from the 52-week low to the high"),
                                             unsafe_allow_html=True)
                            cols[1].caption(f"Last close is {100 * pos:.0f}% of the way from the yearly low to the high.")
                        text = fd.analyst_text(fund["analyst_mean"], fund["analyst_count"], fund["target_price"], prof["price"])
                        if text:
                            st.caption(esc(text))
            st.caption("Ratios and company figures come from Yahoo Finance, refreshed nightly, and are shown for reference: a number "
                       "inside or outside its typical range is not by itself a reason to buy or sell. Missing means the provider has no "
                       "figure (for example no positive earnings).")
    with tab_brokers:
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
            st.caption("On a narrow screen, scroll sideways inside the table to see the Link column.")
            trs = "".join(f"<tr><td>{html.escape(x['name'])}</td><td>{html.escape(per[x['name']])}</td><td>{html.escape(x['note'])}</td>"
                          f"<td><a href=\"{html.escape(x['url'])}\">Open {html.escape(x['name'])}</a></td></tr>" for x in brokers.BROKERS)
            st.markdown('<div class="broker-table" style="overflow-x: auto"><table><thead><tr><th>Broker</th><th>Can I buy it?</th><th>Notes</th><th>Link</th>'
                        f"</tr></thead><tbody>{trs}</tbody></table></div>", unsafe_allow_html=True)   # real HTML table: screen-reader friendly
        st.caption(f"Compiled by hand, last reviewed {brokers.REVIEWED}: broker offerings and fees change, so confirm on the "
                   "broker's site. Pick a broker supervised in the EU (check the AFM register). Dutch residents should also file a "
                   "W-8BEN with their broker so US dividends are withheld at 15% instead of 30%. This is information, not "
                   "investment advice; because of the filing delay, a politician's trade is old news by the time it is public.")


with st.expander("About this data"):
    st.markdown(
        "- **Volume** is estimated from disclosure ranges (midpoint by default; switch to the filed minimum in Settings).\n"
        "- **Filings lag trades** by up to 45 days, so a trade is old news by the time it is public.\n"
        "- **Committee data** is a current snapshot, not membership as of each trade date.\n"
        + (f"- **Sector** is known for {known:,} of {total:,} trades ({100 * known / total:.0f}%), from the FinanceDatabase "
           "classification; sectors are approximate and the committee-relevance flag only applies where a sector is known.\n" if total else ""))
    if not paper.empty:
        with st.container(key="paper_filings"):
            st.markdown("Some members may have traded more than shown. Filings not imported:")
            rows = "\n".join(f"| {r.member} | {r.year} | [Open filing {r.doc_id} (PDF)]({r.url}) |" for r in paper.itertuples())
            st.markdown("| Member | Year | Filing |\n|---|---|---|\n" + rows)

