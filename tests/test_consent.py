"""Offline checks for consent.py.  Run: python tests/test_consent.py  (skips if streamlit isn't installed)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import consent
except ModuleNotFoundError:
    print("skip: streamlit not installed")
    raise SystemExit(0)

sent = []
consent.components.html = lambda html, height=0: sent.append(html)
consent.render_consent_banner("506730812ef03")
html = sent[0]
assert '"506730812ef03"' in html and "__TAG_ID__" not in html
assert "https://t.contentsquare.net/uxa/" in html and "s.defer = true" in html
assert html.index("function loadTag") < html.index('choice === "granted"')       # only called from the consent paths
assert html.count("loadTag()") == 2                                              # on stored consent, and on Accept
for bad in ('x"; alert(1); "', "", None):
    try:
        consent.render_consent_banner(bad)
        raise AssertionError("accepted a bad tag id")
    except ValueError:
        pass
print("ok test_consent")
