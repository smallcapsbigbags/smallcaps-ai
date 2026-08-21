from __future__ import annotations

import hmac
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from product.formatting import format_price_change, impact_hex

LONDON = ZoneInfo("Europe/London")

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@500;600;700&display=swap');
:root { --sca-bg:#F7F7F5; --sca-surface:#FCFCFA; --sca-text:#171A1E; --sca-muted:#69727A; --sca-border:#D8DAD6; --sca-blue:#27648A; --sca-blue-soft:#EAF1F5; }
html, body, [class*="css"] { font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.stApp { background:var(--sca-bg); color:var(--sca-text); }
header[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:1120px; padding-top:1.75rem; padding-bottom:5rem; }
#MainMenu, footer { visibility:hidden; }
.sca-brand { display:flex; align-items:baseline; gap:.85rem; padding-bottom:1rem; border-bottom:1px solid var(--sca-border); margin-bottom:1.4rem; }
.sca-brand-name { color:var(--sca-text); font-size:1.25rem; font-weight:700; letter-spacing:-.035em; }
.sca-brand-product { color:var(--sca-muted); font-size:.78rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; }
.sca-eyebrow,.sca-section-title { color:var(--sca-muted); font-size:.7rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
.sca-ticker,.sca-price,.sca-fact-value,.sca-table .num { font-family:"Roboto Mono",ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:600; }
.sca-ticker { font-weight:700; letter-spacing:-.02em; }
.sca-feed-item { border-top:1px solid var(--sca-border); padding:1.15rem 0 .8rem; }
.sca-feed-item-low { padding:.75rem 0 .25rem; }
.sca-meta { display:flex; align-items:center; flex-wrap:wrap; gap:.45rem; color:var(--sca-muted); font-size:.78rem; }
.sca-meta-spacer { flex:1 1 auto; }
.sca-impact { display:inline-flex; align-items:center; gap:.38rem; color:var(--sca-text); font-size:.72rem; font-weight:700; letter-spacing:.055em; text-transform:uppercase; white-space:nowrap; }
.sca-impact-dot { width:.58rem; height:.58rem; border-radius:50%; display:inline-block; }
.sca-price { color:var(--sca-text); font-size:.8rem; white-space:nowrap; }
.sca-headline { color:var(--sca-text); font-size:1.12rem; font-weight:650; line-height:1.3; letter-spacing:-.02em; margin:.75rem 0 .4rem; }
.sca-headline-critical { font-size:1.3rem; }
.sca-takeaway { color:#30363B; font-size:.92rem; line-height:1.55; max-width:850px; margin:0 0 .7rem; }
.sca-facts { display:flex; flex-wrap:wrap; gap:.5rem 1.1rem; margin-top:.7rem; }
.sca-fact { min-width:130px; }
.sca-fact-value { color:var(--sca-text); font-size:.96rem; }
.sca-fact-label { color:var(--sca-muted); font-size:.7rem; margin-top:.1rem; }
.sca-summary { color:var(--sca-text); font-size:.88rem; margin:.45rem 0 1.1rem; }
.st-key-analyst-note { background:var(--sca-surface); border:1px solid var(--sca-border); padding:2rem clamp(1.1rem,4vw,3.25rem); margin-top:.7rem; }
.sca-note-title { font-size:clamp(1.75rem,4vw,2.55rem); line-height:1.12; letter-spacing:-.045em; margin:1.1rem 0 1rem; max-width:900px; }
.sca-section { border-top:1px solid var(--sca-border); padding-top:1.3rem; margin-top:1.6rem; }
.sca-section-title { margin-bottom:.7rem; }
.sca-body { color:#2B3136; font-size:.98rem; line-height:1.68; max-width:900px; }
.sca-analyst-view { border-left:3px solid var(--sca-blue); padding:.15rem 0 .15rem 1rem; color:#22282D; font-size:1.02rem; line-height:1.65; }
.sca-change-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1.35rem; }
.sca-change-label { color:var(--sca-muted); font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; margin-bottom:.35rem; }
.sca-change-text { color:#2B3136; font-size:.9rem; line-height:1.55; }
.sca-table { width:100%; border-collapse:collapse; font-size:.86rem; }
.sca-table th { color:var(--sca-muted); font-size:.68rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase; text-align:left; padding:.5rem .7rem; border-bottom:1px solid var(--sca-border); }
.sca-table td { padding:.65rem .7rem; border-bottom:1px solid #E5E6E2; vertical-align:top; }
.sca-list { margin:0; padding-left:1.15rem; color:#2B3136; font-size:.9rem; line-height:1.6; }
.sca-company-banner { border-top:1px solid var(--sca-border); border-bottom:1px solid var(--sca-border); padding:1.2rem 0; margin-bottom:1.1rem; }
.sca-building { background:var(--sca-blue-soft); border-left:3px solid var(--sca-blue); color:#294451; padding:.85rem 1rem; font-size:.84rem; line-height:1.5; margin:.8rem 0 1.3rem; }
.sca-empty { border-top:1px solid var(--sca-border); padding:2rem 0; color:var(--sca-muted); font-size:.92rem; }
.sca-job-success{color:#2E6E49}.sca-job-degraded{color:#9A681F}.sca-job-failed{color:#A33F48}.sca-job-running{color:var(--sca-blue)}
div[data-testid="stButton"]>button,div[data-testid="stLinkButton"]>a { border-radius:3px; border:1px solid #C9CCC8; background:transparent; color:var(--sca-text); min-height:2.1rem; font-size:.78rem; font-weight:600; box-shadow:none; }
div[data-testid="stButton"]>button:hover,div[data-testid="stLinkButton"]>a:hover { border-color:var(--sca-blue); color:var(--sca-blue); background:#F4F7F8; }
div[data-baseweb="select"]>div,div[data-testid="stTextInput"] input,div[data-testid="stDateInput"] input,div[data-testid="stTextArea"] textarea { border-radius:3px; border-color:#C9CCC8; background:var(--sca-surface); }
@media(max-width:760px){.block-container{padding-left:1rem;padding-right:1rem}.sca-change-grid{grid-template-columns:1fr;gap:1rem}.sca-meta-spacer{display:none}.st-key-analyst-note{padding:1.2rem 1rem;border-left:0;border-right:0}}
</style>
"""


def inject_styles() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown('<div class="sca-brand"><span class="sca-brand-name">smallcaps.ai</span><span class="sca-brand-product">AIM Intelligence</span></div>', unsafe_allow_html=True)


def require_beta_access(password: str, *, enabled: bool) -> None:
    if not enabled:
        return
    if not password:
        st.error("Private beta is enabled but APP_BETA_PASSWORD is not configured.")
        st.stop()
    if st.session_state.get("beta_access_granted"):
        return
    render_brand()
    st.markdown("## Private beta")
    st.caption("Enter the private beta access code.")
    with st.form("beta-access", clear_on_submit=True):
        supplied = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("UNLOCK")
    if submitted and hmac.compare_digest(supplied, password):
        st.session_state["beta_access_granted"] = True
        st.rerun()
    if submitted:
        st.error("That access code is not valid.")
    st.stop()


def impact_badge(colour: str, level: str) -> str:
    return '<span class="sca-impact"><span class="sca-impact-dot" style="background:' + impact_hex(colour) + '"></span>IMPACT ' + html.escape(level.upper()) + '</span>'


def price_markup(price: dict[str, object] | None) -> str:
    return f'<span class="sca-price">{html.escape(format_price_change(price))}</span>'


def navigate(view: str, **params: str) -> None:
    st.query_params.clear()
    st.query_params["view"] = view
    for key, value in params.items():
        if value:
            st.query_params[key] = value
    st.rerun()


def query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    return str(value[0]) if isinstance(value, list) and value else str(value)


def ensure_watchlist(default_tickers: tuple[str, ...]) -> set[str]:
    if "watchlist_tickers" not in st.session_state:
        st.session_state["watchlist_tickers"] = {ticker.upper() for ticker in default_tickers}
    return set(st.session_state["watchlist_tickers"])


def toggle_watchlist(ticker: str) -> None:
    current = set(st.session_state.get("watchlist_tickers", set()))
    clean = ticker.upper()
    current.remove(clean) if clean in current else current.add(clean)
    st.session_state["watchlist_tickers"] = current
    st.rerun()


def london_now() -> datetime:
    return datetime.now(LONDON)
