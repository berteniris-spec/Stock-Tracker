"""Stock health metrics: formatting, plain-language zones, headlines and the range-bar HTML for the Ticker page.

Pure functions, no Streamlit. Zones are rough, widely used reading guides (not recommendations): they say whether a
number is lower than, typical for, or higher than usual, never "good" or "bad".
"""
import html

# key: label, number format, zone cut-offs (low|typical|high), a display scale for the bar, the words for each zone,
# the tooltip, and the card it belongs to. "typical" text is shown next to the bar.
SPEC = {
    "pe": dict(label="P/E", fmt="x", cuts=(15, 25), scale=(0, 50), words=("Lower", "Typical", "Higher"),
               card="value", sector=True,
               help="Price-to-earnings: the share price divided by the profit per share over the last 12 months. Roughly how many "
                    "years of today's profit you pay for. Higher means the market expects growth (or the stock is expensive); lower "
                    "means cheaper or slower growth. The long-run US market average is about 15 to 20."),
    "forward_pe": dict(label="Fwd P/E", fmt="x", cuts=(15, 25), scale=(0, 50), words=("Lower", "Typical", "Higher"),
                       card="value", sector=True,
                       help="Forward P/E: the same ratio using the profit analysts expect over the next 12 months. Lower than the "
                            "P/E means analysts expect profits to grow; higher means they expect them to fall."),
    "peg": dict(label="PEG", fmt="n2", cuts=(1, 2), scale=(0, 4), words=("Low", "Typical", "High"), card="value", sector=True,
                help="PEG: the P/E divided by expected yearly profit growth, so fast growers are not penalised for a high P/E. "
                     "Around 1 is often read as fairly priced for its growth, well below 1 as cheap, above 2 as expensive. "
                     "Definitions vary by provider and it needs a growth estimate, so it is often missing."),
    "price_to_sales": dict(label="Price / sales", fmt="x", cuts=(2, 6), scale=(0, 12), words=("Low", "Typical", "High"),
                           card="value", sector=True,
                           help="Market value divided by the last 12 months of revenue. Useful when a company has no profit yet. "
                                "Below 2 is low, above 6 is high for most industries; software runs higher, retail lower."),
    "price_to_book": dict(label="Price / book", fmt="x", cuts=(1.5, 4), scale=(0, 8), words=("Low", "Typical", "High"),
                          card="value", sector=True,
                          help="Share price divided by the company's net assets (book value) per share. Below 1 means the market "
                               "values it at less than its accounting net worth. Not meaningful for asset-light companies."),
    "dividend_yield": dict(label="Dividend yield", fmt="pct", cuts=(0.02, 0.04), scale=(0, 0.08), words=("Low", "Moderate", "High"),
                           card="value", sector=False,
                           help="Yearly dividend divided by the share price: the cash paid to shareholders each year. Zero means no "
                                "dividend, common for growth companies. A very high yield can signal that the price has fallen."),
    "profit_margin": dict(label="Profit margin", fmt="pct", cuts=(0.05, 0.20), scale=(-0.1, 0.4), words=("Thin", "Typical", "Wide"),
                          card="profit", sector=True,
                          help="Share of each dollar of revenue left as profit after all costs. 10% means 10 cents of profit per "
                               "dollar sold. Margins differ a lot by industry (supermarkets thin, software wide), so compare with peers."),
    "roe": dict(label="Return on equity", fmt="pct", cuts=(0.08, 0.20), scale=(-0.1, 0.4), words=("Low", "Typical", "High"),
                card="profit", sector=True,
                help="Return on equity: yearly profit divided by shareholders' equity. How much profit the company makes from the "
                     "money invested in it. Above about 15% is usually read as strong; very high values can come from heavy debt."),
    "revenue_growth": dict(label="Revenue growth", fmt="pct", cuts=(0.0, 0.10), scale=(-0.2, 0.4), words=("Shrinking", "Steady", "Fast"),
                           card="profit", sector=True,
                           help="How much quarterly revenue grew compared with the same quarter a year earlier."),
    "earnings_growth": dict(label="Earnings growth", fmt="pct", cuts=(0.0, 0.10), scale=(-0.3, 0.6), words=("Falling", "Steady", "Fast"),
                            card="profit", sector=True,
                            help="How much quarterly profit grew compared with the same quarter a year earlier. Can swing a lot "
                                 "from small bases."),
    "debt_to_equity": dict(label="Debt / equity", fmt="n2", cuts=(0.5, 1.5), scale=(0, 3), words=("Low", "Moderate", "High"),
                           card="safety", sector=True,
                           help="Total debt divided by shareholders' equity. 1.0 means the company owes as much as it is worth to "
                                "its owners. Higher means more borrowed money, so more risk if profits fall. Banks and utilities "
                                "normally carry far more than other sectors."),
    "current_ratio": dict(label="Current ratio", fmt="n2", cuts=(1, 2), scale=(0, 4), words=("Tight", "Adequate", "Comfortable"),
                          card="safety", sector=True,
                          help="Cash and other short-term assets divided by bills due within a year. Below 1 means short-term "
                               "bills exceed short-term assets; above 2 is comfortable."),
    "free_cash_flow": dict(label="Free cash flow", fmt="usd", cuts=(0, None), scale=None, words=("Negative", "Positive", "Positive"),
                           card="safety", sector=False,
                           help="Cash the business generated in the last 12 months after running costs and investment in "
                                "equipment. Positive means it funds itself; negative means it is spending more than it earns."),
    "beta": dict(label="Beta", fmt="n2", cuts=(0.8, 1.2), scale=(0, 2.5), words=("Calmer", "Market-like", "Swings more"),
                 card="risk", sector=False,
                 help="How much the stock has moved compared with the overall market. 1.0 moves with the market; 1.5 tends to "
                      "move 50% more (up and down); below 1 is calmer. Based on past prices, so it is not a forecast."),
}

CARDS = [("value", "How is it priced?"), ("profit", "Is it profitable and growing?"),
         ("safety", "Can it handle trouble?"), ("risk", "How big and how volatile?")]


def fmt(key, v):
    """Format one metric value; "n/a" for a missing one."""
    if v is None or v != v:
        return "n/a"
    kind = SPEC[key]["fmt"]
    if kind == "pct":
        return f"{v * 100:.1f}%"
    if kind == "x":
        return f"{v:.1f}"
    if kind == "n2":
        return f"{v:.2f}"
    if kind == "usd":
        return money(v)
    return str(v)


def money(v, symbol="$"):
    """Compact money: $2.4T, $310B, $45M, -$1.2B."""
    if v is None or v != v:
        return "n/a"
    sign = "-" if v < 0 else ""
    v = abs(v)
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= div:
            x = v / div
            return f"{sign}{symbol}{x:.1f}{suffix}" if x < 100 else f"{sign}{symbol}{x:.0f}{suffix}"
    return f"{sign}{symbol}{v:,.0f}"


def zone(key, v):
    """0, 1 or 2 (lower / typical / higher than usual), or None when the value is missing."""
    if v is None or v != v:
        return None
    lo, hi = SPEC[key]["cuts"]
    if hi is None:                      # a single cut-off (free cash flow): below it is zone 0, otherwise 1
        return 0 if v < lo else 1
    return 0 if v < lo else (1 if v <= hi else 2)


def word(key, v):
    z = zone(key, v)
    return None if z is None else SPEC[key]["words"][z]


def typical_text(key):
    """The range written out for the caption, e.g. "typical 15 to 25"."""
    s = SPEC[key]
    if s["cuts"][1] is None:
        return ""
    lo, hi = s["cuts"]
    f = (lambda x: f"{x * 100:.0f}%") if s["fmt"] == "pct" else (lambda x: f"{x:g}")
    return f"typical {f(lo)} to {f(hi)}"


def market_cap_size(v):
    if v is None or v != v:
        return None
    return "Large company" if v >= 10e9 else ("Mid-size company" if v >= 2e9 else "Small company")


def range_position(low, high, price):
    """Where the price sits between the 52-week low and high, 0 to 1 (None when unknown)."""
    if None in (low, high, price) or high <= low:
        return None
    return min(1.0, max(0.0, (price - low) / (high - low)))


def bar_html(key, v, sector_median=None):
    """A three-zone track with a marker at the value (and a tick at the sector median). Neutral colours, words not colours."""
    s = SPEC[key]
    if v is None or v != v or not s.get("scale"):
        return ""
    lo, hi = s["scale"]
    pos = lambda x: 100 * min(1.0, max(0.0, (x - lo) / (hi - lo)))
    c1, c2 = pos(s["cuts"][0]), pos(s["cuts"][1])
    w = word(key, v)
    label = f"{s['label']} {fmt(key, v)}: {w.lower()} ({typical_text(key)})"
    tick = ""
    if sector_median is not None:
        tick = f'<span class="rb-tick" style="left:{pos(sector_median):.1f}%" title="Sector median {html.escape(fmt(key, sector_median))}"></span>'
    return (f'<div class="rb" role="img" aria-label="{html.escape(label)}"><div class="rb-track">'
            f'<span class="rb-z rb-z0" style="width:{c1:.1f}%"></span><span class="rb-z rb-z1" style="width:{c2 - c1:.1f}%"></span>'
            f'<span class="rb-z rb-z2" style="width:{100 - c2:.1f}%"></span>{tick}'
            f'<span class="rb-mark" style="left:{pos(v):.1f}%"></span></div></div>')


def context_text(key, v, median=None):
    """The visible line under a metric: the zone word, the typical range, the sector median."""
    w = word(key, v)
    if w is None:
        return "No data from the provider."
    parts = [w]
    t = typical_text(key)
    if t:
        parts.append(t)
    if median is not None:
        parts.append(f"sector median {fmt(key, median[0])} ({median[1]} stocks)")
    return " · ".join(parts)


def headline(card, vals, size=None):
    """One factual sentence per card, built from the zones. Empty when there is too little data."""
    z = lambda k: zone(k, vals.get(k))
    out = []
    if card == "value":
        zs = [z(k) for k in ("pe", "forward_pe", "price_to_sales") if z(k) is not None]
        if not zs:
            return ""
        avg = sum(zs) / len(zs)
        out.append("Priced above typical levels" if avg > 1.2 else ("Priced below typical levels" if avg < 0.8 else "Priced around typical levels"))
        pe, fpe = vals.get("pe"), vals.get("forward_pe")
        if pe and fpe:
            out.append("analysts expect profit to grow" if fpe < pe * 0.9 else ("analysts expect profit to shrink" if fpe > pe * 1.1 else ""))
    elif card == "profit":
        m, g = z("profit_margin"), z("revenue_growth")
        if m is None and g is None:
            return ""
        if m is not None:
            out.append({0: "Thin profit margin", 1: "Typical profit margin", 2: "Wide profit margin"}[m])
        if g is not None:
            out.append({0: "revenue is shrinking", 1: "revenue is growing steadily", 2: "revenue is growing fast"}[g])
    elif card == "safety":
        d, c, f = z("debt_to_equity"), z("current_ratio"), z("free_cash_flow")
        if d is None and c is None and f is None:
            return ""
        if d is not None:
            out.append({0: "Low debt", 1: "Moderate debt", 2: "High debt"}[d])
        if c is not None:
            out.append({0: "tight short-term cash", 1: "adequate short-term cash", 2: "comfortable short-term cash"}[c])
        if f is not None:
            out.append("positive free cash flow" if f else "negative free cash flow")
    elif card == "risk":
        b = z("beta")
        if size is None and b is None:
            return ""
        if size:
            out.append(size)
        if b is not None:
            out.append({0: "calmer than the market", 1: "moves with the market", 2: "swings more than the market"}[b])
    out = [o for o in out if o]
    if not out:
        return ""
    text = ", ".join(out)
    return text[0].upper() + text[1:] + "."


def analyst_text(mean, count, target, price):
    """Others' opinion, worded as such: consensus lean and the target vs the last close."""
    if mean is None:
        return ""
    lean = "positive" if mean <= 2.2 else ("negative" if mean >= 3.8 else ("mildly positive" if mean < 2.8 else ("mildly negative" if mean > 3.2 else "neutral")))
    s = f"Analysts' consensus is {lean} ({mean:.1f} on a 1 to 5 scale, 1 = strong buy, 5 = sell"
    s += f", {count} analysts)" if count else ")"
    if target and price:
        s += f"; their average price target is {100 * (target / price - 1):+.0f}% from the last close"
    return s + ". Opinions, not facts, and often wrong."


def range_bar_html(pos, label):
    """52-week range: one neutral track with a marker at the price's position (0 = at the low, 1 = at the high)."""
    if pos is None:
        return ""
    return (f'<div class="rb" role="img" aria-label="{html.escape(label)}"><div class="rb-track">'
            f'<span class="rb-z rb-z1" style="width:100%"></span><span class="rb-mark" style="left:{100 * pos:.1f}%"></span></div></div>')
