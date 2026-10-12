"""Which brokers a Dutch retail investor can use to buy a US-listed ticker.

Static, hand-maintained knowledge, NOT live data: broker product lists and fees change. Availability for a given
ticker is inferred from where it is listed (and whether it is a fund), then checked against what each broker is known
to offer. Always confirm on the broker's own site before relying on it. Last reviewed: 2026-10.
"""

REVIEWED = "October 2026"
LISTED_US = {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BTS"}     # Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe
OTC = {"PNK"}

# us_listed: "full" = the whole US exchange universe is tradable; "curated" = a selected list (large/mid caps mostly)
# otc: Yes | Limited | No (typically)
BROKERS = [
    {"name": "DEGIRO", "url": "https://www.degiro.nl", "us_listed": "full", "otc": "No",
     "note": "Dutch broker, widely used by Dutch retail. Pays attention to FX conversion cost (AutoFX)."},
    {"name": "Interactive Brokers (IBKR)", "url": "https://www.interactivebrokers.ie", "us_listed": "full", "otc": "Limited",
     "note": "Widest access, low costs ($0.005/share, min $1 on US stocks per BrokerChooser); more complex platform."},
    {"name": "LYNX", "url": "https://www.lynxbroker.nl", "us_listed": "full", "otc": "Limited",
     "note": "Dutch-language broker built on IBKR's platform; higher per-trade minimum than IBKR direct."},
    {"name": "Saxo", "url": "https://www.home.saxo/nl-nl", "us_listed": "full", "otc": "Limited",
     "note": "Percentage commission (about 0.08%, $1 min per BrokerChooser); good platform, costlier for small trades."},
    {"name": "Trading 212", "url": "https://www.trading212.com", "us_listed": "curated", "otc": "No",
     "note": "Commission-free real shares, ~0.15% FX fee (BrokerChooser); fractional shares; a curated universe, so some smaller US names are missing."},
    {"name": "eToro", "url": "https://www.etoro.com", "us_listed": "curated", "otc": "Limited",
     "note": "Social/copy trading app; real shares for the common US names; FX fee is higher (0.15-0.75% by tier)."},
    {"name": "Bux", "url": "https://getbux.com/nl", "us_listed": "curated", "otc": "No",
     "note": "Dutch app, simple interface; limited universe of US stocks."},
    {"name": "Trade Republic", "url": "https://traderepublic.com/nl-nl", "us_listed": "curated", "otc": "No",
     "note": "Mobile-first; US stocks trade via a German partner venue rather than directly on NYSE/Nasdaq."},
]

ETF_NOTE = ("US-domiciled ETFs/funds are generally NOT sold to EU retail investors (no PRIIPs KID document). "
            "Look for a UCITS ETF with similar exposure instead.")


def availability(kind, exchange_code):
    """-> (overall verdict, {broker name: status}) for one ticker."""
    names = [b["name"] for b in BROKERS]
    if kind == "etf":
        return "Fund/ETF: usually not available to EU retail", {n: "Usually not (no KID)" for n in names}
    if exchange_code in LISTED_US:
        return "Listed on a major US exchange: widely available", {
            b["name"]: "Yes" if b["us_listed"] == "full" else "Likely (curated list: check)" for b in BROKERS}
    if exchange_code in OTC:
        return "OTC / pink-sheet stock: few EU brokers offer it", {b["name"]: b["otc"] for b in BROKERS}
    return "Exchange unknown: check with your broker", {b["name"]: "Check" for b in BROKERS}
