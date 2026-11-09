"""Page CSS for app.py. Matches Streamlit 1.66.x DOM; re-run /ui-check after a Streamlit upgrade."""

CSS = """
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
/* links: primary is 4.25:1 on cream, too low for small text; link is 5.1:1 */
[data-testid="stMarkdownContainer"] a { color: #3f6399; }
@media (prefers-color-scheme: dark) {
  label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child { border-color: rgba(239,236,227,.55) !important; }
  label[data-testid="stRadioOption"]:focus-within { outline-color: #8fabd4; }
  [data-testid="stMarkdownContainer"] a { color: #8fabd4; }
}
/* tabs (Ticker view): 44px tall, selected = bold plus underline, readable unselected text, visible keyboard focus; matched by role, not Streamlit's hashed classes */
[role="tablist"] { overflow-x: auto; }
[role="tab"] { min-height: 44px; padding: .5rem .9rem; color: rgba(0,0,0,.78); }
[role="tab"], [role="tab"] * { font-size: 1rem; }
[role="tab"][aria-selected="true"] { color: #000; font-weight: 700; box-shadow: inset 0 -3px 0 #4a70a9; }
[role="tab"][aria-selected="true"] * { font-weight: 700; color: inherit; }
[role="tab"]:focus-visible { outline: 2px solid #4a70a9; outline-offset: 2px; }
[role="tab"] .react-aria-SelectionIndicator { display: none; }
@media (prefers-color-scheme: dark) {
  [role="tab"] { color: rgba(239,236,227,.82); }
  [role="tab"][aria-selected="true"] { color: #efece3; box-shadow: inset 0 -3px 0 #8fabd4; }
  [role="tab"]:focus-visible { outline-color: #8fabd4; }
}
/* broker table links (Ticker, Brokers tab): at least 44x44 to tap */
.broker-table td a { display: inline-block; min-height: 44px; min-width: 44px; padding: .6rem .25rem; box-sizing: border-box; }
/* paper filing links ("Open filing N (PDF)"): at least 44px high to tap */
.st-key-paper_filings td a { display: inline-block; min-height: 44px; line-height: 44px; }
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
/* tables on a phone: each ranking / wide table has a desktop and a phone rendering in the page; CSS shows one at Streamlit's 640px breakpoint */
@media (min-width: 641px) {
  [class*="st-key-ph_"], [data-testid="stLayoutWrapper"]:has(> [class*="st-key-ph_"]) { display: none; }
}
@media (max-width: 640px) {
  [class*="st-key-tbl_"], [data-testid="stLayoutWrapper"]:has(> [class*="st-key-tbl_"]) { display: none; }
  /* compact phone tables: the table wraps to the container width; no sideways scroll, so a too-wide table shows up as page overflow */
  [class*="st-key-ph_"] [data-testid="stTable"] > div { overflow-x: visible; }
  [class*="st-key-ph_"] table { width: 100%; table-layout: auto; font-size: .85rem; }
  [class*="st-key-ph_"] th, [class*="st-key-ph_"] td { padding: .35rem .3rem !important; white-space: normal; }
  [class*="st-key-ph_"] th *, [class*="st-key-ph_"] td * { overflow-wrap: break-word !important; }
  [class*="st-key-ph_"] td * { white-space: inherit !important; }        /* so the per-column nowrap set on the td applies */
  [class*="st-key-ph_"] td { border-color: rgba(0,0,0,.2) !important; }
  [class*="st-key-ph_"] th { text-align: left; font-weight: 600; color: inherit; border-bottom: 2px solid currentColor; }
}
/* ranking lists: full-width rows that wrap, left-aligned, 44px at least */
[class*="st-key-rank_ov_"], [class*="st-key-rank_ov_"] [data-testid="stVerticalBlock"] { gap: .35rem; }
[class*="st-key-open_ov_"], [class*="st-key-open_ov_"] [data-testid="stButton"], [class*="st-key-open_ov_"] button { width: 100%; }
[class*="st-key-open_ov_"] button { justify-content: flex-start; text-align: left; height: auto; min-height: 44px; padding-top: .4rem; padding-bottom: .4rem; }
[class*="st-key-open_ov_"] button, [class*="st-key-open_ov_"] button * { white-space: normal; overflow-wrap: anywhere; text-align: left; }
[class*="st-key-open_ov_"] button > div, [class*="st-key-open_ov_"] button > div > span { width: 100%; justify-content: space-between; }
[class*="st-key-open_ov_"] [data-testid="stMarkdownContainer"] { flex: 1 1 auto; min-width: 0; }
@media (max-width: 640px) and (prefers-color-scheme: dark) { [class*="st-key-ph_"] td { border-color: rgba(239,236,227,.2) !important; } }
/* 320px: five columns need tighter cell padding to fit without breaking words */
@media (max-width: 359px) { [class*="st-key-ph_"] th, [class*="st-key-ph_"] td { padding-left: .1rem !important; padding-right: .1rem !important; }
  [class*="st-key-ph_"] table { font-size: .78rem; } }
/* 320px safety net: a table that is still too wide scrolls inside its own box (visible overflow stays at 360-640 so it shows up as a failure) */
@media (max-width: 359px) { [class*="st-key-ph_"] [data-testid="stTable"] > div { overflow-x: auto; } }
/* list rows: the boundary is ink at 55% (the rule colour was about 1.5:1) */
[class*="st-key-open_ov_"] button { border-color: rgba(0,0,0,.18); background: rgba(255,255,255,.7); border-radius: 12px; }
[class*="st-key-open_ov_"] button:hover { border-color: #1f3a5f; background: #fff; }
/* keyboard focus: the same ring as the radios on buttons and checkboxes (Streamlit's own glow is about 1.9:1) */
[data-testid="stButton"] button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible,
[data-testid="stCheckbox"] label:has(input:focus-visible) { outline: 2px solid #4a70a9; outline-offset: 2px; }
@media (prefers-color-scheme: dark) {
  [class*="st-key-open_ov_"] button { border-color: rgba(239,236,227,.25); background: rgba(255,255,255,.05); }
  [class*="st-key-open_ov_"] button:hover { border-color: #8fabd4; background: rgba(255,255,255,.09); }
  [data-testid="stButton"] button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible,
  [data-testid="stCheckbox"] label:has(input:focus-visible) { outline-color: #8fabd4; }
}
/* redesign: one compact top bar (logo, title, settings), pill navigation, card metrics, quiet chrome */
[data-testid="stMainBlockContainer"] { padding-top: 4rem; max-width: 1200px; }
[data-testid="stAppDeployButton"] { display: none; }
[data-testid="stPopoverButton"] { min-height: 44px; }
[data-testid="stMarkdownContainer"]:has(.stMarkdownBadge), [data-testid="stMarkdownContainer"]:has(.stMarkdownBadge) p { overflow: visible; white-space: normal; text-overflow: clip; }
.st-key-topbar { justify-content: space-between; flex-wrap: nowrap; margin-bottom: .25rem; }
.st-key-brand { gap: .6rem; flex: 1 1 0 !important; width: auto !important; min-width: 0; flex-wrap: nowrap !important; }
.stMarkdownBadge { white-space: normal !important; display: inline-block !important; max-width: 100%; overflow: visible !important; text-overflow: clip !important; }
.st-key-brand img { height: 40px; width: auto !important; object-fit: contain; }
.st-key-brand [data-testid="stElementToolbar"] { display: none; }
.st-key-brand h1 { font-size: 1.4rem; font-weight: 700; padding: 0; letter-spacing: -.01em; line-height: 1.2; }
[data-testid="stHeading"] a { display: none; }
.st-key-settings_slot { flex: 0 0 auto; width: auto; margin-left: auto; }
h2, [data-testid="stHeading"] h2 { font-size: 1.2rem; font-weight: 650; letter-spacing: -.01em; padding-top: .75rem; }
/* view switch as pills: the radio dot is hidden, the selected option is filled */
label[data-testid="stRadioOption"] { border: 1px solid rgba(0,0,0,.25); border-radius: 999px; padding: 0 1rem; background: transparent; display: inline-flex; align-items: center; justify-content: center; }
label[data-testid="stRadioOption"][data-selected="true"] { background: #1f3a5f; border-color: #1f3a5f; }
label[data-testid="stRadioOption"][data-selected="true"], label[data-testid="stRadioOption"][data-selected="true"] * { color: #fff !important; font-weight: 600; }
label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) { display: none !important; }
label[data-testid="stRadioOption"] p { margin: 0; line-height: 1.2; }
label[data-testid="stRadioOption"] > div { align-items: center; }
/* range bars (Ticker health check): three neutral zones, a marker for the value, a tick for the sector median */
.rb { margin: -.25rem 0 .35rem; }
.rb-track { position: relative; display: flex; height: 10px; border-radius: 5px; overflow: visible; }
.rb-z { display: block; height: 100%; }
.rb-z0 { background: rgba(31,58,95,.14); border-radius: 5px 0 0 5px; }
.rb-z1 { background: rgba(31,58,95,.30); }
.rb-z2 { background: rgba(31,58,95,.14); border-radius: 0 5px 5px 0; }
.rb-mark { position: absolute; top: -4px; width: 4px; height: 18px; margin-left: -2px; border-radius: 2px; background: #1f3a5f; box-shadow: 0 0 0 2px #f4f2ec; }
.rb-tick { position: absolute; top: -2px; width: 2px; height: 14px; margin-left: -1px; background: rgba(0,0,0,.55); }
@media (prefers-color-scheme: dark) {
  .rb-z0, .rb-z2 { background: rgba(143,171,212,.18); } .rb-z1 { background: rgba(143,171,212,.38); }
  .rb-mark { background: #8fabd4; box-shadow: 0 0 0 2px #0d1219; } .rb-tick { background: rgba(239,236,227,.7); }
}
[class*="st-key-fund_"] { background: rgba(255,255,255,.45); border-radius: 12px; }
@media (prefers-color-scheme: dark) { [class*="st-key-fund_"] { background: rgba(255,255,255,.04); } }
[class*="st-key-fund_"] [data-testid="stMetric"] { background: transparent; border: 0; padding: .25rem 0; }
/* metrics as cards */
[data-testid="stMetric"] { background: rgba(255,255,255,.7); border: 1px solid rgba(0,0,0,.12); border-radius: 12px; padding: .85rem 1rem; }
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * { white-space: normal; overflow: visible; text-overflow: clip; overflow-wrap: anywhere; }
@media (max-width: 359px) { [data-testid="stMetric"] { padding: .7rem .6rem; } [data-testid="stMetricDelta"] { flex-wrap: wrap; font-size: .8rem; } }
/* inputs and expanders on the quiet surface */
[data-baseweb="select"] > div { background: #fff; border: 1px solid rgba(0,0,0,.25); }
[data-testid="stExpander"] details { background: rgba(255,255,255,.55); border-radius: 12px; }
@media (prefers-color-scheme: dark) {
  label[data-testid="stRadioOption"] { border-color: rgba(239,236,227,.35); }
  label[data-testid="stRadioOption"][data-selected="true"] { background: #8fabd4; border-color: #8fabd4; }
  label[data-testid="stRadioOption"][data-selected="true"], label[data-testid="stRadioOption"][data-selected="true"] * { color: #0d1219 !important; }
  [data-testid="stMetric"] { background: rgba(255,255,255,.05); border-color: rgba(239,236,227,.18); }
  [data-baseweb="select"] > div { background: #14202f; border-color: rgba(239,236,227,.35); }
  [data-testid="stExpander"] details { background: rgba(255,255,255,.04); }
}
/* checkboxes: 44px rows ("Show all columns", "Only ...") */
[data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }
label[data-testid="stRadioOption"] { min-height: 44px; align-items: center; }
[data-testid="stRadioGroup"] { row-gap: .25rem; }
</style>
"""
