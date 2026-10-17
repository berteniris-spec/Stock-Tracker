"""Screenshot the app at phone and desktop widths in light and dark, and report layout problems.

Usage: python scripts/ui_check.py [OUTPUT_DIR] [--ids Member=ID Committee=ID Ticker=ID]

Needs the `playwright` package and a Chromium in PLAYWRIGHT_BROWSERS_PATH (default /opt/pw-browsers).
Neither is in requirements.txt. Read-only: it never writes to congress.db.
Exit codes: 0 no page-level horizontal overflow, 1 overflow found, 2 environment problem.
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
    if (t) s += '[data-testid="' + t + '"]';
    else if (el.id) s += '#' + el.id;
    else if (el.className && typeof el.className === 'string')
      s += '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.');
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
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 1 || r.left < -1) && !scrollable(el) && getComputedStyle(el).position !== 'fixed')
      overflow.push(sel(el) + ' "' + snip(el) + '"');
    const cs = getComputedStyle(el);
    if ((cs.overflowX === 'hidden' || cs.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 &&
        (el.innerText || '').trim() && !el.closest('[data-testid="stDataFrame"]'))
      cut.push(sel(el) + ' "' + snip(el) + '"');
    if (el.matches('a[href], button, input, select, textarea, [role="button"], [role="tab"], [role="radio"], [role="checkbox"]') &&
        (r.width < 44 || r.height < 44))
      small.push(sel(el) + ' "' + snip(el) + '" ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  const uniq = (a) => [...new Set(a)];
  return {pageScroll: !!pageScroll, overflow: uniq(overflow), cut: uniq(cut), small: uniq(small)};
}
"""


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
        print("playwright is not installed (pip install playwright; browsers expected in "
              f"{os.environ['PLAYWRIGHT_BROWSERS_PATH']}). Not added to requirements.txt.", file=sys.stderr)
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
                finally:
                    browser.close()
        except Exception as e:  # missing browser, launch failure, etc.
            print(f"Browser problem: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print(f"Screenshots in {out}")
    return 1 if overflow_found else 0


def shoot(browser, url, view, width, theme, out):
    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, color_scheme=theme)
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=30000)
        try:
            page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        path = out / f"{view.lower()}_{width}_{theme}.png"
        page.screenshot(path=str(path), full_page=True)
        r = page.evaluate(JS)
    except Exception as e:
        print(f"{view} {width} {theme}: ISSUES could not render ({type(e).__name__}: {e})")
        return False
    finally:
        ctx.close()
    parts = []
    if r["pageScroll"]:
        parts.append("page-level horizontal scroll")
    if r["overflow"]:
        parts.append("overflowing viewport: " + "; ".join(r["overflow"][:5]))
    if r["cut"]:
        parts.append("suspected cut-off text: " + "; ".join(r["cut"][:5]))
    if width == 390 and r["small"]:
        parts.append(f"advisory, {len(r['small'])} targets under 44x44: " + "; ".join(r["small"][:5]))
    print(f"{view} {width} {theme}: {'ISSUES ' + ' | '.join(parts) if parts else 'PASS'}  {path}")
    return bool(r["pageScroll"])


if __name__ == "__main__":
    sys.exit(main())
