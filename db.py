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
    UNIQUE (bioguide_id, tx_date, ticker, tx_type, amount_label, owner)
);
CREATE TABLE IF NOT EXISTS ticker_sector (
    ticker TEXT PRIMARY KEY,
    sector TEXT NOT NULL
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
    nums = [int(n.replace(",", "")) for n in _NUM.findall(str(label))]
    if not nums:
        return None, None, None
    if "over" in str(label).lower() or len(nums) == 1:
        return nums[0], None, nums[0]
    lo, hi = nums[0], nums[1]
    return lo, hi, (lo + hi) // 2


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(con):
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT OR IGNORE INTO ticker_sector(ticker, sector) VALUES (?, ?)",
        DEFAULT_SECTORS.items(),
    )
    con.commit()


# ---------- queries (return DataFrames) ----------

def _df(con, sql, params=()):
    return pd.read_sql_query(sql, con, params=params)


def has_sample_data(con):
    return con.execute("SELECT 1 FROM members WHERE source='sample' LIMIT 1").fetchone() is not None


def members_with_trades(con):
    return _df(con, """
        SELECT m.bioguide_id, m.name, m.chamber, m.state, m.party, m.source,
               COUNT(t.id) AS trades, COALESCE(SUM(t.amount_est), 0) AS est_volume
        FROM members m JOIN trades t USING (bioguide_id)
        GROUP BY m.bioguide_id ORDER BY est_volume DESC""")


def member_committees(con, bioguide_id):
    return _df(con, """
        SELECT c.id, c.name, c.chamber, ms.title, ms.as_of,
               (c.parent_id IS NOT NULL) AS is_sub
        FROM memberships ms JOIN committees c ON c.id = ms.committee_id
        WHERE ms.bioguide_id = ? ORDER BY is_sub, c.name""", (bioguide_id,))


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
               ts.sector
        FROM trades t LEFT JOIN ticker_sector ts USING (ticker)
        WHERE t.bioguide_id = ? ORDER BY t.tx_date DESC""", (bioguide_id,))
    sectors = _member_sectors(con, bioguide_id)
    df["committee_relevant"] = df["sector"].isin(sectors)
    return df


def committee_members(con, committee_id):
    return _df(con, """
        SELECT m.bioguide_id, m.name, m.chamber, m.party, ms.title,
               COUNT(t.id) AS trades, COALESCE(SUM(t.amount_est), 0) AS est_volume
        FROM memberships ms JOIN members m USING (bioguide_id)
        LEFT JOIN trades t USING (bioguide_id)
        WHERE ms.committee_id = ?
        GROUP BY m.bioguide_id ORDER BY est_volume DESC""", (committee_id,))


def committee_trades(con, committee_id):
    df = _df(con, """
        SELECT m.name AS member, t.tx_date, t.ticker, t.asset, t.tx_type,
               t.amount_label, t.amount_est, ts.sector
        FROM memberships ms JOIN members m USING (bioguide_id)
        JOIN trades t USING (bioguide_id)
        LEFT JOIN ticker_sector ts USING (ticker)
        WHERE ms.committee_id = ? ORDER BY t.tx_date DESC""", (committee_id,))
    sectors = set(COMMITTEE_SECTORS.get(committee_id[:4], []))
    df["committee_relevant"] = df["sector"].isin(sectors)
    return df


def committees_with_trading(con):
    return _df(con, """
        SELECT c.id, c.name, c.chamber,
               COUNT(DISTINCT ms.bioguide_id) AS members,
               COUNT(t.id) AS trades, COALESCE(SUM(t.amount_est), 0) AS est_volume
        FROM committees c JOIN memberships ms ON ms.committee_id = c.id
        JOIN trades t ON t.bioguide_id = ms.bioguide_id
        WHERE c.parent_id IS NULL
        GROUP BY c.id ORDER BY est_volume DESC""")


def ticker_summary(con, ticker):
    return _df(con, """
        SELECT m.name AS member, m.chamber, t.tx_date, t.tx_type, t.amount_label, t.amount_est
        FROM trades t JOIN members m USING (bioguide_id)
        WHERE t.ticker = ? ORDER BY t.tx_date DESC""", (ticker,))


def top_tickers(con, limit=15):
    return _df(con, """
        SELECT t.ticker, COALESCE(ts.sector, 'Unmapped') AS sector,
               COUNT(*) AS trades, COUNT(DISTINCT t.bioguide_id) AS members,
               COALESCE(SUM(t.amount_est), 0) AS est_volume
        FROM trades t LEFT JOIN ticker_sector ts USING (ticker)
        WHERE t.ticker IS NOT NULL AND t.ticker <> ''
        GROUP BY t.ticker ORDER BY est_volume DESC LIMIT ?""", (limit,))


def monthly_volume(con):
    return _df(con, """
        SELECT substr(tx_date, 1, 7) AS month, tx_type,
               COALESCE(SUM(amount_est), 0) AS est_volume
        FROM trades WHERE tx_date IS NOT NULL
        GROUP BY month, tx_type ORDER BY month""")


def all_tickers(con):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT ticker FROM trades WHERE ticker IS NOT NULL AND ticker <> '' ORDER BY ticker")]
