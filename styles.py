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
[class*="st-key-ph_ov_"], [class*="st-key-ph_ov_"] [data-testid="stVerticalBlock"] { gap: .35rem; }
[class*="st-key-open_ov_"], [class*="st-key-open_ov_"] [data-testid="stButton"], [class*="st-key-open_ov_"] button { width: 100%; }
[class*="st-key-open_ov_"] button { justify-content: flex-start; text-align: left; height: auto; min-height: 44px; padding-top: .4rem; padding-bottom: .4rem; }
[class*="st-key-open_ov_"] button, [class*="st-key-open_ov_"] button * { white-space: normal; overflow-wrap: anywhere; text-align: left; }
[class*="st-key-open_ov_"] button > div, [class*="st-key-open_ov_"] button > div > span { width: 100%; justify-content: space-between; }
[class*="st-key-open_ov_"] [data-testid="stMarkdownContainer"] { flex: 1 1 auto; min-width: 0; }
@media (max-width: 640px) and (prefers-color-scheme: dark) { [class*="st-key-ph_"] td { border-color: rgba(239,236,227,.2) !important; } }
/* 320px: five columns need tighter cell padding to fit without breaking words */
@media (max-width: 359px) { [class*="st-key-ph_"] th, [class*="st-key-ph_"] td { padding-left: .1rem !important; padding-right: .1rem !important; } }
/* 320px safety net: a table that is still too wide scrolls inside its own box (visible overflow stays at 360-640 so it shows up as a failure) */
@media (max-width: 359px) { [class*="st-key-ph_"] [data-testid="stTable"] > div { overflow-x: auto; } }
/* list rows: the boundary is ink at 55% (the rule colour was about 1.5:1) */
[class*="st-key-open_ov_"] button { border-color: rgba(0,0,0,.55); }
/* keyboard focus: the same ring as the radios on buttons and checkboxes (Streamlit's own glow is about 1.9:1) */
[data-testid="stButton"] button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible,
[data-testid="stCheckbox"] label:has(input:focus-visible) { outline: 2px solid #4a70a9; outline-offset: 2px; }
@media (prefers-color-scheme: dark) {
  [class*="st-key-open_ov_"] button { border-color: rgba(239,236,227,.55); }
  [data-testid="stButton"] button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible,
  [data-testid="stCheckbox"] label:has(input:focus-visible) { outline-color: #8fabd4; }
}
/* logo above the page title: 48px high on a phone, 64px above (the 169x144 file is 2x sharp at both) */
.st-key-brand img { max-width: 100%; height: 48px; width: auto !important; object-fit: contain; }
/* no hover toolbar (fullscreen button) on the logo */
.st-key-brand [data-testid="stElementToolbar"] { display: none; }
@media (min-width: 641px) { .st-key-brand img { height: 64px; } }
/* checkboxes: 44px rows ("Show all columns", "Only ...") */
[data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }
label[data-testid="stRadioOption"] { min-height: 44px; align-items: center; }
[data-testid="stRadioGroup"] { row-gap: .25rem; }
</style>
"""
