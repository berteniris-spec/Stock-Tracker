"""Cookie-consent banner that gates the Contentsquare analytics tag (GDPR / ePrivacy).

The tag is never loaded until the visitor presses Accept. The choice is kept in the browser's localStorage
(key `cs_consent`: "granted" | "denied"); a small "Cookie settings" button stays on screen so consent can be
withdrawn as easily as it was given. Withdrawing deletes Contentsquare's cookies (best effort) and reloads the page.

Streamlit gives apps no control over the page <head>, so the banner is injected into the host page from a
zero-height component iframe (same origin as the app).
"""
import json
import re

import streamlit.components.v1 as components

TAG_ID_RE = re.compile(r"^[0-9a-zA-Z]{8,32}$")

_TEMPLATE = r"""
<script>
(function () {
  var TAG_ID = __TAG_ID__;
  var KEY = "cs_consent";
  var P = window.parent, D = P.document;

  function get() { try { return P.localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { P.localStorage.setItem(KEY, v); } catch (e) {} }

  function loadTag() {                       // <script defer src=".../uxa/TAG.js">, added only after consent
    if (P._csLoaded) return;
    P._csLoaded = true;
    var s = D.createElement("script");
    s.defer = true;
    s.src = "https://t.contentsquare.net/uxa/" + TAG_ID + ".js";
    D.head.appendChild(s);
  }

  function clearCookies() {                  // best effort: first-party cookies the tag set
    D.cookie.split(";").forEach(function (c) {
      var n = c.split("=")[0].trim();
      if (n.indexOf("_cs") === 0) {
        D.cookie = n + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
        D.cookie = n + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=." + P.location.hostname;
      }
    });
  }

  function el(tag, props, text) {
    var e = D.createElement(tag);
    for (var k in props) e.setAttribute(k, props[k]);
    if (text) e.textContent = text;
    return e;
  }

  function injectStyle() {
    if (D.getElementById("cs-consent-style")) return;
    var st = el("style", {id: "cs-consent-style"});
    st.textContent =
      "#cs-consent-banner{position:fixed;left:16px;right:16px;bottom:16px;max-width:640px;margin:0 auto;z-index:1000000;" +
      "background:#fff;color:#1f2430;border:1px solid #d5d9e0;border-radius:12px;padding:16px 18px;" +
      "box-shadow:0 8px 30px rgba(0,0,0,.18);font:14px/1.45 'Source Sans Pro',system-ui,sans-serif}" +
      "#cs-consent-banner h2{margin:0 0 6px;font-size:16px;font-weight:600;color:inherit}" +
      "#cs-consent-banner p{margin:0 0 12px}" +
      "#cs-consent-banner .cs-row{display:flex;gap:8px;flex-wrap:wrap}" +
      "#cs-consent-banner button,#cs-consent-settings{font:inherit;cursor:pointer;border-radius:8px;padding:8px 16px;border:1px solid #1f2430}" +
      "#cs-consent-banner .cs-yes{background:#1f2430;color:#fff}" +
      "#cs-consent-banner .cs-no{background:#fff;color:#1f2430}" +
      "#cs-consent-settings{position:fixed;left:12px;bottom:12px;z-index:999999;background:#fff;color:#1f2430;" +
      "border-color:#d5d9e0;padding:4px 10px;font-size:12px;opacity:.85}" +
      "@media (prefers-color-scheme: dark){#cs-consent-banner,#cs-consent-settings,#cs-consent-banner .cs-no{background:#1b1f2a;color:#e8eaf0;border-color:#3a4052}" +
      "#cs-consent-banner .cs-yes{background:#e8eaf0;color:#1b1f2a;border-color:#e8eaf0}}";
    D.head.appendChild(st);
  }

  function removeBanner() {
    var b = D.getElementById("cs-consent-banner"); if (b) b.remove();
  }

  function showSettingsButton() {
    if (D.getElementById("cs-consent-settings")) return;
    var b = el("button", {id: "cs-consent-settings", type: "button"}, "Cookie settings");
    b.addEventListener("click", function () { showBanner(); });
    D.body.appendChild(b);
  }

  function showBanner() {
    removeBanner();
    var cur = get();
    var box = el("div", {id: "cs-consent-banner", role: "dialog", "aria-label": "Cookie consent"});
    box.appendChild(el("h2", {}, "Analytics cookies"));
    box.appendChild(el("p", {},
      "This app can use Contentsquare to record anonymised usage, such as clicks, scrolling and pages viewed, so it can be " +
      "improved. It sets cookies and sends this data to Contentsquare. Nothing is loaded unless you accept, and the app " +
      "works the same either way. You can change your choice at any time with the Cookie settings button."));
    var row = el("div", {"class": "cs-row"});
    var yes = el("button", {type: "button", "class": "cs-yes"}, "Accept");
    var no = el("button", {type: "button", "class": "cs-no"}, "Decline");
    yes.addEventListener("click", function () {
      set("granted"); removeBanner(); loadTag();
    });
    no.addEventListener("click", function () {
      var wasGranted = (cur === "granted" || P._csLoaded);
      set("denied"); removeBanner();
      if (wasGranted) { clearCookies(); P.location.reload(); }   // the tag can't be unloaded: reload without it
    });
    row.appendChild(yes); row.appendChild(no); box.appendChild(row);
    D.body.appendChild(box);
  }

  injectStyle();
  showSettingsButton();
  var choice = get();
  if (choice === "granted") loadTag();
  else if (choice !== "denied") showBanner();
})();
</script>
"""


def render_consent_banner(tag_id):
    """Show the banner (first visit) and load the Contentsquare tag only if the visitor has accepted."""
    if not TAG_ID_RE.match(tag_id or ""):
        raise ValueError("invalid Contentsquare tag id")
    components.html(_TEMPLATE.replace("__TAG_ID__", json.dumps(tag_id)), height=0)
