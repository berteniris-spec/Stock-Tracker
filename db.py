"""SQLite schema, amount parsing and query helpers (no Streamlit imports here)."""
import re
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).with_name("congress.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    bioguide_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    chamber     TEXT,            -- 'Senate' or 'House'
    state       TEXT,
    party       TEXT,
    last_name   TEXT,
    first_name  TEXT,
    district    INTEGER,         -- House district (0 = at-large); NULL for senators
    source      TEXT NOT NULL DEFAULT 'congress-legislators'  -- 'sample' for fictional demo rows
);
CREATE TABLE IF NOT EXISTS committees (
    id        TEXT PRIMARY KEY,  -- thomas_id, subcommittees are parent||sub id
    name      TEXT NOT NULL,
    chamber   TEXT,
    parent_id TEXT REFERENCES committees(id)
);
CREATE TABLE IF NOT EXISTS memberships (
    bioguide_id  TEXT NOT NULL REFERENCES members(bioguide_id),
    committee_id TEXT NOT NULL REFERENCES committees(id),
    title        TEXT,
    rank         INTEGER,
    as_of        TEXT NOT NULL,  -- date the membership snapshot was taken
    PRIMARY KEY (bioguide_id, committee_id)
);
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bioguide_id     TEXT NOT NULL REFERENCES members(bioguide_id),
    tx_date         TEXT,
    disclosure_date TEXT,
    ticker          TEXT,
    asset           TEXT,
    tx_type         TEXT,        -- Purchase / Sale / Sale (Partial) / Exchange
    owner           TEXT,        -- Self / Spouse / Joint / Dependent Child
    amount_label    TEXT,
    amount_min      INTEGER,
    amount_max      INTEGER,     -- NULL for open-ended ranges ("Over $X")
    amount_est      INTEGER,     -- midpoint, or the floor for open-ended ranges
    source          TEXT NOT NULL DEFAULT 'import',
    doc_id          TEXT,        -- source filing id (House Clerk DocID), when known
    UNIQUE (bioguide_id, tx_date, ticker, asset, tx_type, amount_label, owner)
);
CREATE TABLE IF NOT EXISTS filings (
    doc_id      TEXT PRIMARY KEY,
    year        INTEGER,
    bioguide_id TEXT,
    filer       TEXT,
    status      TEXT NOT NULL,   -- ok | partial | no_text | unmatched_member | fetch_failed
    rows_parsed INTEGER,
    markers     INTEGER,         -- "[XX]" asset-type markers found; should equal rows_parsed
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ticker_sector (
    ticker     TEXT PRIMARY KEY,
    sector     TEXT NOT NULL,
    industry   TEXT,                          -- free text from the classification source
    source     TEXT DEFAULT 'default',        -- default | override | financedatabase | fd-etf | fd-miss
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS ticker_info (
    ticker        TEXT PRIMARY KEY,
    name          TEXT,
    kind          TEXT,                       -- equity | etf | NULL when the classification source doesn't know it
    exchange_code TEXT,                       -- Yahoo-style venue code: NMS, NYQ, ASE, PCX, BTS, PNK
    exchange      TEXT,                       -- display name: Nasdaq, NYSE, ...
    updated_at    TEXT
);
CREATE TABLE IF NOT EXISTS ticker_price (
    ticker     TEXT PRIMARY KEY,
    price      REAL,                          -- last close, USD
    prev_close REAL,
    as_of      TEXT,                          -- market date of the close
    fetched_at TEXT,
    source     TEXT
);
CREATE TABLE IF NOT EXISTS ticker_valuation (
    ticker     TEXT PRIMARY KEY,
    pe         REAL,                          -- trailing P/E (NULL when earnings are negative or unknown)
    forward_pe REAL,
    peg        REAL,
    fetched_at TEXT,
    source     TEXT
);
CREATE TABLE IF NOT EXISTS fx_rate (
    pair       TEXT PRIMARY KEY,              -- 'USD_PER_EUR'
    rate       REAL,
    as_of      TEXT,
    source     TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_member ON trades(bioguide_id);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
"""

# Sectors each committee plausibly oversees. Deliberately coarse: edit freely.
# Used only for the "committee-relevant" flag, which is a heuristic, not a finding.
COMMITTEE_SECTORS = {
    "SSAS": ["Defense & Aerospace"], "HSAS": ["Defense & Aerospace"],
    "SSBK": ["Financials", "Real Estate"], "HSBA": ["Financials", "Real Estate"],
    "SSEG": ["Energy", "Utilities"],
    "SSEV": ["Energy", "Utilities", "Materials"],
    "SSHR": ["Healthcare"], "SPAG": ["Healthcare"],
    "HSIF": ["Healthcare", "Energy", "Technology", "Communication Services"],
    "SSCM": ["Technology", "Communication Services", "Transportation"],
    "HSPW": ["Transportation", "Industrials"],
    "HSSY": ["Technology", "Defense & Aerospace"],
    "SSAF": ["Agriculture", "Consumer Staples"], "HSAG": ["Agriculture", "Consumer Staples"],
    "HSII": ["Energy", "Materials"],
    "SSFI": ["Financials", "Healthcare"], "HSWM": ["Financials", "Healthcare"],
    "HSHM": ["Technology", "Defense & Aerospace"],
    "HSZS": ["Technology", "Defense & Aerospace"],
    "HSJU": ["Technology", "Communication Services"], "SSJU": ["Technology", "Communication Services"],  # antitrust
    "HSVR": ["Healthcare"], "SSVA": ["Healthcare"],
    "HLIG": ["Defense & Aerospace", "Technology"], "SLIN": ["Defense & Aerospace", "Technology"],
    "HSFA": ["Defense & Aerospace"], "SSFR": ["Defense & Aerospace"],
    "SSGA": ["Technology", "Defense & Aerospace"],
    "JSEC": ["Financials"],
    # Deliberately unmapped (jurisdiction spans everything or is procedural): Appropriations, Budget, Rules,
    # Ethics, House Administration, Oversight, Education, Small Business, Indian Affairs.
}

# 2026-era starter map for common tickers. Add your own in sectors.csv (ticker,sector).
DEFAULT_SECTORS = {
    "LMT": "Defense & Aerospace", "RTX": "Defense & Aerospace", "NOC": "Defense & Aerospace",
    "GD": "Defense & Aerospace", "BA": "Defense & Aerospace",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "V": "Financials", "BRK.B": "Financials",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "NEE": "Utilities", "DUK": "Utilities",
    "PFE": "Healthcare", "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "MRK": "Healthcare",
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AMD": "Technology",
    "GOOGL": "Communication Services", "META": "Communication Services",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "KO": "Consumer Staples", "PG": "Consumer Staples", "ADM": "Agriculture", "DE": "Agriculture",
    "UPS": "Transportation", "DAL": "Transportation",
}

_NUM = re.compile(r"\d[\d,]*")


def parse_amount(label):
    """'$1,001 - $15,000' -> (1001, 15000, 8000); 'Over $50,000,000' -> (50000000, None, 50000000)."""
    if not label:
        return None, None, None
    nums = [int(n.replace(",", "")) for n in _NUM.findall(re.sub(r"(?<=\d)\.\d+", "", str(label)))]
    if not nums:
        return None, None, None
    if "over" in str(label).lower():
        return nums[0], None, nums[0]
    if len(nums) == 1:                       # an exact amount, e.g. "$707.21"
        return nums[0], nums[0], nums[0]
    lo, hi = nums[0], nums[1]
    return lo, hi, (lo + hi) // 2


def connect(path=DB_PATH):
    con = sqlite3.connect(path, check_same_thread=False)  # Streamlit reruns on different threads
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def _migrate(con):
    """Add columns introduced after a database was first created."""
    def cols(t):
        return {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
    for col, typ in (("last_name", "TEXT"), ("first_name", "TEXT"), ("district", "INTEGER")):
        if col not in cols("members"):
            con.execute(f"ALTER TABLE members ADD COLUMN {col} {typ}")
    if "doc_id" not in cols("trades"):
        con.execute("ALTER TABLE trades ADD COLUMN doc_id TEXT")
    for col, typ in (("industry", "TEXT"), ("source", "TEXT DEFAULT 'default'"), ("updated_at", "TEXT")):
        if col not in cols("ticker_sector"):
            con.execute(f"ALTER TABLE ticker_sector ADD COLUMN {col} {typ}")


def init_db(con):
    con.executescript(SCHEMA)
    _migrate(con)
    con.executemany(
        "INSERT OR IGNORE INTO ticker_sector(ticker, sector, source) VALUES (?, ?, 'default')",
        DEFAULT_SECTORS.items(),
    )
    con.commit()


def insert_trade(con, bioguide_id, tx_date, ticker, tx_type, amount_label, *,
                 disclosure_date=None, asset="", owner="Self", source="import", doc_id=None):
    """Insert one trade, estimating volume from the range. Returns 1 if added, 0 if a duplicate."""
    lo, hi, est = parse_amount(amount_label)
    cur = con.execute(
        "INSERT OR IGNORE INTO trades(bioguide_id, tx_date, disclosure_date, ticker, asset, tx_type, owner, "
        "amount_label, amount_min, amount_max, amount_est, source, doc_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (bioguide_id, tx_date, disclosure_date, (ticker or "").upper(), asset or "", tx_type, owner or "Self",
         amount_label, lo, hi, est, source, doc_id))
    return cur.rowcount


# ---------- volume basis ----------
# Filings give ranges, some very wide ($5M-$25M). "mid" counts the midpoint (floor for open-ended
# "Over $X"); "min" counts the filed minimum, a conservative lower bound.
_BASIS = {"mode": "mid"}


def set_basis(mode):
    assert mode in ("mid", "min")
    _BASIS["mode"] = mode


def _est(alias="t"):
    """SQL expression for a trade's volume under the current basis."""
    col = "amount_est" if _BASIS["mode"] == "mid" else "amount_min"
    return f"{alias}.{col}" if alias else col


def volume_of(df):
    """Sum a trades DataFrame's volume under the current basis."""
    return df["amount_est" if _BASIS["mode"] == "mid" else "amount_min"].sum()


# ---------- queries (return DataFrames) ----------

def _df(con, sql, params=()):
    return pd.read_sql_query(sql, con, params=params)


def has_sample_data(con):
    return con.execute("SELECT 1 FROM members WHERE source='sample' LIMIT 1").fetchone() is not None


def members_with_trades(con):
    return _df(con, f"""
        SELECT m.bioguide_id, m.name, m.chamber, m.state, m.party, m.source,
               COUNT(t.id) AS trades, COALESCE(SUM({_est()}), 0) AS est_volume
        FROM members m JOIN trades t USING (bioguide_id)
        GROUP BY m.bioguide_id ORDER BY est_volume DESC""")


def member_committees(con, bioguide_id):
    return _df(con, """
        SELECT c.id, c.name, c.chamber, ms.title, ms.as_of,
               (c.parent_id IS NOT NULL) AS is_sub
        FROM memberships ms JOIN committees c ON c.id = ms.committee_id
        WHERE ms.bioguide_id = ? ORDER BY is_sub, c.name""", (bioguide_id,))


def committee_sectors(committee_id):
    """Sectors a committee is mapped to (empty = no mapping, so the relevance flag doesn't apply)."""
    return COMMITTEE_SECTORS.get(committee_id[:4], [])


def member_sectors(con, bioguide_id):
    return _member_sectors(con, bioguide_id)


def _member_sectors(con, bioguide_id):
    ids = [r[0] for r in con.execute(
        "SELECT committee_id FROM memberships WHERE bioguide_id=?", (bioguide_id,))]
    out = set()
    for cid in ids:
        out.update(COMMITTEE_SECTORS.get(cid[:4], []))
    return out


def member_trades(con, bioguide_id):
    df = _df(con, """
        SELECT t.tx_date, t.disclosure_date, t.ticker, t.asset, t.tx_type, t.owner,
               t.amount_label, t.amount_min, t.amount_max, t.amount_est,
               ts.sector, ti.exchange, tp.price, tv.pe, tv.forward_pe, tv.peg
        FROM trades t LEFT JOIN ticker_sector ts USING (ticker)
        LEFT JOIN ticker_info ti USING (ticker) LEFT JOIN ticker_price tp USING (ticker)
        LEFT JOIN ticker_valuation tv USING (ticker)
        WHERE t.bioguide_id = ? ORDER BY t.tx_date DESC""", (bioguide_id,))
    sectors = _member_sectors(con, bioguide_id)
    df["committee_relevant"] = df["sector"].isin(sectors)
    return df


def committee_members(con, committee_id):
    return _df(con, f"""
        SELECT m.bioguide_id, m.name, m.chamber, m.party, ms.title,
               COUNT(t.id) AS trades, COALESCE(SUM({_est()}), 0) AS est_volume
        FROM memberships ms JOIN members m USING (bioguide_id)
        LEFT JOIN trades t USING (bioguide_id)
        WHERE ms.committee_id = ?
        GROUP BY m.bioguide_id ORDER BY est_volume DESC""", (committee_id,))


def committee_trades(con, committee_id):
    df = _df(con, """
        SELECT m.name AS member, t.tx_date, t.ticker, t.asset, t.tx_type,
               t.amount_label, t.amount_min, t.amount_max, t.amount_est, ts.sector,
               ti.exchange, tp.price, tv.pe, tv.forward_pe, tv.peg
        FROM memberships ms JOIN members m USING (bioguide_id)
        JOIN trades t USING (bioguide_id)
        LEFT JOIN ticker_sector ts USING (ticker)
        LEFT JOIN ticker_info ti USING (ticker) LEFT JOIN ticker_price tp USING (ticker)
        LEFT JOIN ticker_valuation tv USING (ticker)
        WHERE ms.committee_id = ? ORDER BY t.tx_date DESC""", (committee_id,))
    sectors = set(COMMITTEE_SECTORS.get(committee_id[:4], []))
    df["committee_relevant"] = df["sector"].isin(sectors)
    return df


def committees_with_trading(con):
    return _df(con, f"""
        SELECT c.id, c.name, c.chamber,
               COUNT(DISTINCT ms.bioguide_id) AS members,
               COUNT(t.id) AS trades, COALESCE(SUM({_est()}), 0) AS est_volume
        FROM committees c JOIN memberships ms ON ms.committee_id = c.id
        JOIN trades t ON t.bioguide_id = ms.bioguide_id
        WHERE c.parent_id IS NULL
        GROUP BY c.id ORDER BY est_volume DESC""")


def ticker_summary(con, ticker):
    return _df(con, """
        SELECT m.name AS member, m.chamber, t.tx_date, t.tx_type, t.amount_label, t.amount_min, t.amount_max, t.amount_est
        FROM trades t JOIN members m USING (bioguide_id)
        WHERE t.ticker = ? ORDER BY t.tx_date DESC""", (ticker,))


def top_tickers(con, limit=15):
    return _df(con, f"""
        SELECT t.ticker, ti.name, COALESCE(ts.sector, 'Unmapped') AS sector, ti.exchange, tp.price, tv.pe, tv.forward_pe, tv.peg,
               COUNT(*) AS trades, COUNT(DISTINCT t.bioguide_id) AS members,
               COALESCE(SUM({_est()}), 0) AS est_volume
        FROM trades t LEFT JOIN ticker_sector ts USING (ticker)
        LEFT JOIN ticker_info ti USING (ticker) LEFT JOIN ticker_price tp USING (ticker)
        LEFT JOIN ticker_valuation tv USING (ticker)
        WHERE t.ticker IS NOT NULL AND t.ticker <> ''
        GROUP BY t.ticker ORDER BY est_volume DESC LIMIT ?""", (limit,))


def monthly_volume(con):
    return _df(con, f"""
        SELECT substr(tx_date, 1, 7) AS month, tx_type,
               COALESCE(SUM({_est(None)}), 0) AS est_volume
        FROM trades WHERE tx_date IS NOT NULL AND tx_date <= COALESCE(disclosure_date, tx_date)
        GROUP BY month, tx_type ORDER BY month""")


def paper_filings(con, bioguide_id=None):
    """Paper (scanned) filings that couldn't be imported, with a link to each original PDF."""
    cols = ["doc_id", "year", "bioguide_id", "member", "url"]
    sql = ("SELECT f.doc_id, f.year, f.bioguide_id, m.name AS member FROM filings f "
           "JOIN members m USING (bioguide_id) WHERE f.status = 'no_text'")
    params = ()
    if bioguide_id:
        sql += " AND f.bioguide_id = ?"
        params = (bioguide_id,)
    try:
        df = _df(con, sql + " ORDER BY m.name, f.year DESC, f.doc_id", params)
    except Exception:                      # older database without a filings table
        return pd.DataFrame(columns=cols)
    base = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/"
    # built row by row: vectorised string concatenation fails on empty frames with pandas 3 / pyarrow strings
    df["url"] = [f"{base}{y}/{d}.pdf" for y, d in zip(df["year"], df["doc_id"])]
    return df[cols]


def paper_only_members(con):
    """Members with paper filings but no imported trades: absent from the trade tables, so list them."""
    try:
        return _df(con, """
            SELECT bioguide_id, name, chamber, state FROM members
            WHERE bioguide_id IN (SELECT bioguide_id FROM filings WHERE status = 'no_text')
              AND bioguide_id NOT IN (SELECT bioguide_id FROM trades)""")
    except Exception:
        return pd.DataFrame(columns=["bioguide_id", "name", "chamber", "state"])


def sector_coverage(con):
    """(trades with a known sector, total trades) - funds count as known, misses/unmapped do not."""
    row = con.execute("""
        SELECT SUM(CASE WHEN ts.sector IS NOT NULL AND ts.sector NOT IN ('Unclassified') THEN 1 ELSE 0 END), COUNT(*)
        FROM trades t LEFT JOIN ticker_sector ts USING (ticker)""").fetchone()
    return (row[0] or 0), row[1]


def all_tickers(con):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT ticker FROM trades WHERE ticker IS NOT NULL AND ticker <> '' ORDER BY ticker")]


def ticker_profile(con, ticker):
    """Name, kind, exchange and last close for one ticker (all None when unknown)."""
    row = con.execute("""
        SELECT ti.name, ti.kind, ti.exchange_code, ti.exchange, ts.sector,
               tp.price, tp.prev_close, tp.as_of, tv.pe, tv.forward_pe, tv.peg
        FROM (SELECT ? AS ticker) q
        LEFT JOIN ticker_info ti USING (ticker) LEFT JOIN ticker_sector ts USING (ticker)
        LEFT JOIN ticker_price tp USING (ticker) LEFT JOIN ticker_valuation tv USING (ticker)""", (ticker,)).fetchone()
    keys = ("name", "kind", "exchange_code", "exchange", "sector", "price", "prev_close", "as_of",
            "pe", "forward_pe", "peg")
    return dict(zip(keys, tuple(row)))


def usd_per_eur(con):
    """(rate, as_of) of the stored ECB reference rate, or (None, None)."""
    row = con.execute("SELECT rate, as_of FROM fx_rate WHERE pair = 'USD_PER_EUR'").fetchone()
    return (row[0], row[1]) if row else (None, None)


def price_freshness(con):
    """(tickers with a price, tickers in trades, newest price date)."""
    row = con.execute("""
        SELECT COUNT(DISTINCT tp.ticker), COUNT(DISTINCT t.ticker), MAX(tp.as_of)
        FROM trades t LEFT JOIN ticker_price tp USING (ticker)
        WHERE t.ticker IS NOT NULL AND t.ticker <> ''""").fetchone()
    return tuple(row)


def overview_stats(con):
    """Headline numbers for the Overview: trades, members with trades, estimated volume, newest disclosure date."""
    row = con.execute(f"""
        SELECT COUNT(*), COUNT(DISTINCT t.bioguide_id), COALESCE(SUM({_est()}), 0),
               MAX(CASE WHEN t.disclosure_date <= date('now') THEN t.disclosure_date END)
        FROM trades t""").fetchone()
    return {"trades": row[0], "members": row[1], "volume": row[2], "newest": row[3]}
