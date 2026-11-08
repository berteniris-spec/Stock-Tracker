"""Screenshot the app at phone and desktop widths in light and dark, and report layout problems.

Usage: python scripts/ui_check.py [OUTPUT_DIR] [--ids Member=ID Committee=ID Ticker=ID]

Needs the `playwright` package and a Chromium in PLAYWRIGHT_BROWSERS_PATH (default /opt/pw-browsers).
Neither is in requirements.txt. Read-only: it never writes to congress.db. The interpreter that runs
this script must import both playwright and streamlit (it starts the app with the same interpreter),
and the playwright version must match the installed chromium build.
Limit: only the default state is captured (USD, default volume basis). The Settings expander is not
opened, and EUR and the Filed minimum basis are not captured. A sidebar or its toggle still in the
page is reported as an advisory line and never changes the exit code.
Overview only: at 390 every ranking list button must be 44px tall and inside the viewport and no ranking table may
show; at 1280 the ranking tables show and the lists do not. A failure there exits 1 like page-level overflow.
Ticker only: each tab (Trades, Price, Brokers) is clicked and measured like the page; every tab must be 44px tall and
inside the viewport at 390, the page must not scroll sideways at 320 (an extra 320 light shot), the Trades tab must show
the phone table at 640 and narrower and the grid above, and the 390 page height is reported per tab. Failures there exit 1.
Exit codes: 0 clean, 1 page-level overflow, a ranking failure or did not finish loading, 2 environment problem.
"""
import argparse
import os
import sqlite3
import subprocess
import socket
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "congress.db"
VIEWS = ["Overview", "Member", "Committee", "Ticker"]
WIDTHS = [390, 1280]
HEIGHT = 900
THEMES = ["light", "dark"]

# Runs in the page. Returns the layout findings for the current rendering.
JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const sel = (el) => {
    let s = el.tagName.toLowerCase();
    const t = el.getAttribute('data-testid');
    const role = el.getAttribute('role');
    if (t) s += '[data-testid="' + t + '"]';
    else if (role) s += '[role="' + role + '"]';
    else if (el.id) s += '#' + el.id;
    return s;
  };
  const snip = (el) => (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const visible = (el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const scrollable = (el) => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const t = p.getAttribute && p.getAttribute('data-testid');
      if (t === 'stDataFrame' || t === 'stTable' || t === 'stDataFrameResizable') return true;
      const ox = getComputedStyle(p).overflowX;
      if ((ox === 'auto' || ox === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
    }
    return false;
  };
  const main = document.querySelector('[data-testid="stMain"]') || document.querySelector('[data-testid="stAppViewContainer"]');
  const pageScroll = document.documentElement.scrollWidth > vw + 1 || (main && main.scrollWidth > main.clientWidth + 1);
  const overflow = [], cut = [], small = [];
  let widest = null, widestRight = vw + 1;
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > widestRight && getComputedStyle(el).position !== 'fixed') {
      widestRight = r.right;
      widest = sel(el) + " '" + snip(el) + "' right=" + Math.round(r.right) + ' > ' + vw;
    }
    if ((r.right > vw + 1 || r.left < -1) && !scrollable(el) && getComputedStyle(el).position !== 'fixed')
      overflow.push(sel(el) + ' "' + snip(el) + '"');
    if (r.width < 4 || r.height < 4 || el.closest('[aria-hidden="true"]') ||
        el.closest('a[data-testid="stSkipToContent"]')) continue;
    const cs = getComputedStyle(el);
    if ((cs.overflowX === 'hidden' || cs.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 &&
        (el.innerText || '').trim() && !el.closest('[data-testid="stDataFrame"]'))
      cut.push(sel(el) + ' "' + snip(el) + '"');
    if (el.matches('a[href], button, input, select, textarea, [role="button"], [role="tab"], [role="radio"], [role="checkbox"], label[data-testid="stRadioOption"]') &&
        !el.matches('input[type="radio"], input[type="checkbox"]') &&
        !el.closest('[data-testid="stTooltipIcon"]') &&
        (r.width < 44 || r.height < 44))
      small.push(sel(el) + ' "' + snip(el) + '" ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  const uniq = (a) => [...new Set(a)];
  return {pageScroll: !!pageScroll, overflow: uniq(overflow), cut: uniq(cut), small: uniq(small), sidebar: document.querySelectorAll('[data-testid="stSidebar"], [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"]').length > 0, widest: widest, vw: vw};
}
"""


# Overview only: the three ranking tables have a table rendering (desktop) and a list of buttons (phone), and CSS shows one.
RANK_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const shown = (el) => { const r = el.getBoundingClientRect(); return el.checkVisibility({checkVisibilityCSS: true}) && r.width > 0 && r.height > 0; };
  const label = (el) => (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 30);
  const buttons = [...document.querySelectorAll('[class*="st-key-open_ov"] button')];
  const list = buttons.filter(shown);
  const grids = [...document.querySelectorAll('[class*="st-key-tbl_ov_"] [data-testid="stDataFrame"]')];
  return {
    buttons: buttons.length, listShown: list.length, grids: grids.length, gridsShown: grids.filter(shown).length,
    short: list.filter((b) => b.getBoundingClientRect().height < 43.5).map((b) => label(b) + ' ' + Math.round(b.getBoundingClientRect().height) + 'px'),
    outside: list.filter((b) => { const r = b.getBoundingClientRect(); return r.left < -1 || r.right > vw + 1; }).map(label),
  };
}
"""


def ranking_findings(page, width):
    """Problems with the Overview ranking tables at this width (empty list = fine)."""
    if width <= 640:  # open the "Show ranks 11 to N" expanders so those rows are measured too
        for summary in page.query_selector_all('[class*="st-key-ph_ov_"] summary'):
            summary.click()
        page.wait_for_timeout(500)
    r = page.evaluate(RANK_JS)
    if not r["grids"]:  # empty ranking tables: no list and nothing to swap
        return []
    out = []
    if width <= 640:
        if not r["buttons"]:
            out.append("no list buttons")
        if r["short"]:
            out.append(f"{len(r['short'])} list buttons under 44px: " + "; ".join(r["short"][:3]))
        if r["outside"]:
            out.append("list buttons outside the viewport: " + "; ".join(r["outside"][:3]))
        if r["gridsShown"]:
            out.append(f"{r['gridsShown']} ranking tables still visible")
    else:
        if r["gridsShown"] != r["grids"]:
            out.append(f"only {r['gridsShown']} of {r['grids']} ranking tables visible")
        if r["listShown"]:
            out.append(f"{r['listShown']} list buttons visible")
    return out


TAB_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const shown = (el) => { const r = el.getBoundingClientRect(); return el.checkVisibility({checkVisibilityCSS: true}) && r.width > 0 && r.height > 0; };
  const main = document.querySelector('[data-testid="stMain"]');
  const tabs = [...document.querySelectorAll('[role="tab"]')].map((t) => { const r = t.getBoundingClientRect();
    return {name: t.innerText.trim(), h: Math.round(r.height), inside: r.left >= -1 && r.right <= vw + 1}; });
  const ph = document.querySelector('[class*="st-key-ph_ticker_trades"]'), grid = document.querySelector('[class*="st-key-tbl_ticker_trades"]');
  return {tabs: tabs, height: main ? main.scrollHeight : 0, ph: ph ? shown(ph) : null, grid: grid ? shown(grid) : null,
          panels: [...document.querySelectorAll('[role="tabpanel"]')].filter(shown).length};
}
"""


def ticker_tab_findings(page, width):
    """Click each Ticker tab and measure it. Returns (problems that fail the run, advisory lines, page layout findings per tab)."""
    bad, notes, layouts = [], [], []
    names = [t.inner_text().strip() for t in page.query_selector_all('[role="tab"]')]
    if names != ["Trades", "Price", "Brokers"]:
        return [f"tabs are {names}, expected Trades, Price, Brokers"], notes, layouts
    heights = []
    for name in names:
        page.locator('[role="tab"]', has_text=name).click()
        page.wait_for_timeout(600)
        if name == "Brokers":  # open every broker expander so their content is measured too
            for summary in page.query_selector_all('[role="tabpanel"] summary'):
                summary.click()
            page.wait_for_timeout(500)
        r = page.evaluate(TAB_JS)
        layouts.append((name, page.evaluate(JS)))
        heights.append(f"{name} {r['height']}px")
        if r["panels"] != 1:
            bad.append(f"{name}: {r['panels']} tab panels visible")
        if width <= 390:
            small = [f"{t['name']} {t['h']}px" for t in r["tabs"] if t["h"] < 44]
            if small:
                bad.append(f"{name}: tabs under 44px tall: " + ", ".join(small))
            if not all(t["inside"] for t in r["tabs"]):
                bad.append(f"{name}: a tab is outside the viewport")
        if name == "Trades" and r["ph"] is not None:
            if width <= 640 and (not r["ph"] or r["grid"]):
                bad.append(f"Trades: phone table shown={r['ph']}, grid shown={r['grid']} (want phone table only)")
            if width > 640 and (r["ph"] or not r["grid"]):
                bad.append(f"Trades: phone table shown={r['ph']}, grid shown={r['grid']} (want grid only)")
    page.locator('[role="tab"]', has_text="Trades").click()    # back to Trades: the grid must paint again after Price
    page.wait_for_timeout(800)
    notes.append("page height per tab: " + ", ".join(heights))
    return bad, notes, layouts


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pick_ids():
    """Most active member, committee and ticker, read-only."""
    ids = {}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        queries = {
            "Member": "SELECT bioguide_id FROM trades GROUP BY bioguide_id ORDER BY COUNT(*) DESC LIMIT 1",
            "Committee": "SELECT committee_id FROM memberships GROUP BY committee_id ORDER BY COUNT(*) DESC LIMIT 1",
            "Ticker": "SELECT ticker FROM trades WHERE ticker IS NOT NULL AND ticker <> '' "
                      "GROUP BY ticker ORDER BY COUNT(*) DESC LIMIT 1",
        }
        for view, q in queries.items():
            try:
                row = con.execute(q).fetchone()
            except sqlite3.Error:
                row = None
            if row and row[0]:
                ids[view] = row[0]
    finally:
        con.close()
    return ids


def wait_healthy(port, proc, timeout=60):
    url = f"http://127.0.0.1:{port}/_stcore/health"
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(1)
    return False


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("outdir", nargs="?", help="output directory (default: a new temp dir); must be outside the repo")
    ap.add_argument("--ids", nargs="*", default=[], metavar="VIEW=ID",
                    help="override picked ids, e.g. Member=A000360 Ticker=NVDA")
    return ap.parse_args()


def main():
    args = parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed for this interpreter (pip install playwright; browsers expected in "
              f"{os.environ['PLAYWRIGHT_BROWSERS_PATH']}). The interpreter running this script must import "
              "both playwright and streamlit. Not added to requirements.txt.", file=sys.stderr)
        return 2
    if not DB.exists():
        print("congress.db not found; refusing to run (fetch it first).", file=sys.stderr)
        return 2

    out = Path(args.outdir).resolve() if args.outdir else Path(tempfile.mkdtemp(prefix="ui_check_")).resolve()
    if out == ROOT or ROOT in out.parents:
        print(f"Output dir {out} is inside the repo; choose a path outside it.", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)

    ids = pick_ids()
    for item in args.ids:
        view, _, val = item.partition("=")
        match = next((v for v in VIEWS if v.lower() == view.lower()), None)
        if not match or not val:
            print(f"Bad --ids entry {item!r}; use VIEW=ID with VIEW one of {VIEWS[1:]}.", file=sys.stderr)
            return 2
        ids[match] = val

    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
         "--server.port", str(port), "--browser.gatherUsageStats", "false"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    overflow_found = False
    try:
        if not wait_healthy(port, proc):
            print("Streamlit did not become healthy within 60s.", file=sys.stderr)
            return 2
        base = f"http://127.0.0.1:{port}/"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    warm_up(browser, base)
                    for view in VIEWS:
                        if view != "Overview" and view not in ids:
                            print(f"{view}: skipped (no id found in congress.db; use --ids)")
                            continue
                        query = {"view": view}
                        if view != "Overview":
                            query["id"] = ids[view]
                        url = base + "?" + urllib.parse.urlencode(query)
                        for width in WIDTHS:
                            for theme in THEMES:
                                overflow_found |= shoot(browser, url, view, width, theme, out)
                        if view == "Ticker":   # the tab bar must not scroll the page at the narrowest phone width
                            overflow_found |= shoot(browser, url, view, 320, "light", out)
                finally:
                    browser.close()
        except Exception as e:  # missing browser, launch failure, etc.
            print(f"Browser problem: {type(e).__name__}: {e}. Check that the playwright version matches "
                  f"the chromium build in $PLAYWRIGHT_BROWSERS_PATH (ls it).", file=sys.stderr)
            return 2
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print(f"Screenshots in {out}")
    return 1 if overflow_found else 0


SKELETON = '[data-testid="stSkeleton"], [data-testid="stStatusWidget"]'
# The page title (st.title) is rendered on every view; a cold start can show only the empty shell.
CONTENT = '[data-testid="stMain"] h1'
HAS_CONTENT = f"() => {{ const e = document.querySelector('{CONTENT}'); return !!e && e.innerText.trim().length > 0; }}"


def warm_up(browser, base):
    """Load the app once in a throwaway context so the first real shot does not hit a cold start."""
    ctx = browser.new_context(viewport={"width": 1280, "height": HEIGHT})
    try:
        page = ctx.new_page()
        page.goto(base + "?view=Overview", wait_until="domcontentloaded")
        wait_ready(page)
    except Exception as e:
        print(f"warm-up failed ({type(e).__name__}: {e}); continuing", file=sys.stderr)
    finally:
        ctx.close()


def wait_ready(page):
    """Wait until the page has finished loading and its size is stable. Raises on timeout."""
    page.wait_for_selector('[data-testid="stMain"]', state="visible", timeout=30000)
    page.wait_for_function(HAS_CONTENT, timeout=30000)
    page.wait_for_function(f"() => !document.querySelector('{SKELETON}')", timeout=30000)
    last = None
    for _ in range(40):  # about 10s
        cur = page.evaluate("() => [document.documentElement.scrollHeight, document.documentElement.scrollWidth]")
        if cur == last:
            break
        last = cur
        page.wait_for_timeout(250)
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass


def shoot(browser, url, view, width, theme, out):
    from playwright.sync_api import TimeoutError as PWTimeout
    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, color_scheme=theme)
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded")
        wait_ready(page)  # raises PWTimeout if the content never appears
        path = out / f"{view.lower()}_{width}_{theme}.png"
        page.screenshot(path=str(path), full_page=True)
        r = page.evaluate(JS)
        rank = ranking_findings(page, width) if view == "Overview" else []
        tabs_bad, tabs_notes, tab_layouts = ticker_tab_findings(page, width) if view == "Ticker" else ([], [], [])
        if page.query_selector(SKELETON) or not page.evaluate(HAS_CONTENT):  # loading restarted or content vanished
            print(f"{view} {width} {theme}: ISSUES did not finish loading")
            return True
    except PWTimeout:
        print(f"{view} {width} {theme}: ISSUES did not finish loading")
        return True
    except Exception as e:
        print(f"{view} {width} {theme}: ISSUES could not render ({type(e).__name__}: {e})")
        return False
    finally:
        ctx.close()
    parts = []
    if r["pageScroll"]:
        if r["widest"]:
            parts.append(f"page-level horizontal scroll (widest: {r['widest']})")
        else:
            parts.append("page-level horizontal scroll (no element exceeds the viewport)")
    if r["overflow"]:
        parts.append("overflowing viewport: " + "; ".join(r["overflow"][:5]))
    if r["cut"]:
        parts.append("suspected cut-off text: " + "; ".join(r["cut"][:5]))
    if width == 390 and r["small"]:
        parts.append(f"advisory, {len(r['small'])} targets under 44x44: "
                     + "; ".join(r["small"][:5]))
    if rank:
        parts.append("ranking tables: " + "; ".join(rank))
    if tabs_bad:
        parts.append("ticker tabs: " + "; ".join(tabs_bad))
    tab_scroll = False
    for name, tl in tab_layouts:    # the same page-level measurements, per tab
        if tl["pageScroll"]:
            tab_scroll = True
            parts.append(f"{name} tab: page-level horizontal scroll (widest: {tl['widest']})")
        if tl["overflow"]:
            parts.append(f"{name} tab overflowing viewport: " + "; ".join(tl["overflow"][:5]))
        if tl["cut"]:
            parts.append(f"{name} tab suspected cut-off text: " + "; ".join(tl["cut"][:5]))
        extra = [x for x in tl["small"] if x not in r["small"] and not x.startswith("button#react-aria")]   # the page chrome is listed above
        if width == 390 and extra:
            parts.append(f"advisory, {name} tab {len(extra)} more targets under 44x44: " + "; ".join(extra[:5]))
    parts.extend("advisory, " + n for n in tabs_notes)
    if r["sidebar"]:
        parts.append("advisory, sidebar or toggle still present")
    print(f"{view} {width} {theme}: {'ISSUES ' + ' | '.join(parts) if parts else 'PASS'}  {path}")
    return bool(r["pageScroll"]) or bool(rank) or bool(tabs_bad) or tab_scroll


if __name__ == "__main__":
    sys.exit(main())
