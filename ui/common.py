from __future__ import annotations

import hmac
import html
import secrets
import traceback
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from product.formatting import format_price_change, impact_hex, impact_signal_label

LONDON = ZoneInfo("Europe/London")
_SCROLL_FLAG = "_smallcaps_scroll_to_top"

APP_CSS = """
<style>
:root {
  --sca-bg:#F7F7F5;
  --sca-surface:#FCFCFA;
  --sca-text:#171A1E;
  --sca-muted:#69727A;
  --sca-border:#D8DAD6;
  --sca-blue:#27648A;
  --sca-blue-soft:#EAF1F5;
}
html { color-scheme:light; }
html, body, [class*="css"] {
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
}
.stApp { background:var(--sca-bg); color:var(--sca-text); }
header[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none !important; }
.block-container { max-width:1120px; padding-top:1.75rem; padding-bottom:5rem; }
#MainMenu, footer { visibility:hidden; }
.sca-brand {
  display:flex;
  align-items:baseline;
  gap:.85rem;
  padding-bottom:1rem;
  border-bottom:1px solid var(--sca-border);
  margin-bottom:1.4rem;
}
.sca-brand-name { color:var(--sca-text); font-size:1.25rem; font-weight:700; letter-spacing:-.035em; }
.sca-brand-product { color:var(--sca-muted); font-size:.78rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; }
.sca-eyebrow,.sca-section-title { color:var(--sca-muted); font-size:.7rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
.sca-ticker,.sca-price,.sca-table .num,.sca-intel-value {
  font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  font-weight:600;
}
.sca-ticker { font-weight:700; letter-spacing:-.02em; }
.sca-feed-item { border-top:1px solid var(--sca-border); padding:1.15rem 0 .8rem; }
.sca-feed-item-low { padding:.75rem 0 .25rem; }
.sca-meta { display:flex; align-items:center; flex-wrap:wrap; gap:.45rem; color:var(--sca-muted); font-size:.78rem; }
.sca-meta-spacer { flex:1 1 auto; }
.sca-impact {
  display:inline-flex;
  align-items:center;
  gap:.38rem;
  color:var(--sca-text);
  font-size:.72rem;
  font-weight:700;
  letter-spacing:.055em;
  text-transform:uppercase;
  white-space:nowrap;
}
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
.sca-table-wrap { width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; }
.sca-table { width:100%; min-width:680px; border-collapse:collapse; font-size:.86rem; }
.sca-table th { color:var(--sca-muted); font-size:.68rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase; text-align:left; padding:.5rem .7rem; border-bottom:1px solid var(--sca-border); white-space:nowrap; }
.sca-table td { padding:.65rem .7rem; border-bottom:1px solid #E5E6E2; vertical-align:top; }
.sca-list { margin:0; padding-left:1.15rem; color:#2B3136; font-size:.9rem; line-height:1.6; }
.sca-company-banner { border-top:1px solid var(--sca-border); border-bottom:1px solid var(--sca-border); padding:1.2rem 0; margin-bottom:1.1rem; }
.sca-building { background:var(--sca-blue-soft); border-left:3px solid var(--sca-blue); color:#294451; padding:.85rem 1rem; font-size:.84rem; line-height:1.5; margin:.8rem 0 1.3rem; }
.sca-empty { border-top:1px solid var(--sca-border); padding:2rem 0; color:var(--sca-muted); font-size:.92rem; }
.sca-empty-title { color:var(--sca-text); font-size:1rem; font-weight:650; margin-bottom:.35rem; }
.sca-intel-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.7rem; margin:.15rem 0 1.4rem; }
.sca-intel-card { background:var(--sca-surface); border:1px solid var(--sca-border); padding:.9rem 1rem; min-height:82px; }
.sca-intel-value { color:var(--sca-text); font-size:1.18rem; line-height:1.2; }
.sca-intel-label { color:var(--sca-muted); font-size:.7rem; line-height:1.35; margin-top:.38rem; }
.sca-cell-note { color:var(--sca-muted); font-size:.68rem; line-height:1.35; margin-top:.18rem; font-weight:400; }
.sca-source-link { color:var(--sca-blue); text-decoration:none; font-size:.76rem; line-height:1.4; }
.sca-source-link:hover { text-decoration:underline; }
.sca-memory-row { display:flex; gap:1.2rem; justify-content:space-between; align-items:flex-start; padding:.85rem 0; border-bottom:1px solid #E5E6E2; }
.sca-memory-main { max-width:760px; }
.sca-memory-title { color:#2B3136; font-size:.9rem; line-height:1.55; }
.sca-memory-meta { color:var(--sca-muted); font-size:.72rem; line-height:1.45; margin-top:.3rem; }
.sca-memory-source { flex:0 0 260px; text-align:right; }
.sca-latest-card { background:var(--sca-surface); border:1px solid var(--sca-border); padding:1.05rem 1.15rem; margin:.25rem 0 1rem; }
.sca-beta-hero { max-width:780px; padding:1.5rem 0 .7rem; }
.sca-beta-title { color:var(--sca-text); font-size:clamp(2rem,5vw,3.25rem); line-height:1.03; letter-spacing:-.055em; margin:0 0 .8rem; }
.sca-beta-copy { color:#30363B; font-size:1rem; line-height:1.65; max-width:670px; }
.sca-beta-points { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.7rem; margin:1.2rem 0 1.3rem; }
.sca-beta-point { background:var(--sca-surface); border:1px solid var(--sca-border); padding:.8rem .9rem; color:#30363B; font-size:.82rem; line-height:1.45; }
.sca-footer { border-top:1px solid var(--sca-border); margin-top:2.25rem; padding-top:1rem; color:var(--sca-muted); font-size:.73rem; line-height:1.55; }
.sca-service-error { background:var(--sca-surface); border:1px solid var(--sca-border); border-left:3px solid var(--sca-blue); padding:1rem 1.1rem; max-width:720px; }
.sca-error-reference { color:var(--sca-muted); font-size:.72rem; margin-top:.55rem; }
.sca-job-success{color:#2E6E49}.sca-job-degraded{color:#9A681F}.sca-job-failed{color:#A33F48}.sca-job-running{color:var(--sca-blue)}
div[data-testid="stButton"]>button,div[data-testid="stLinkButton"]>a {
  border-radius:3px;
  border:1px solid #C9CCC8;
  background:transparent;
  color:var(--sca-text);
  min-height:2.1rem;
  font-size:.78rem;
  font-weight:600;
  box-shadow:none;
}
div[data-testid="stButton"]>button:hover,div[data-testid="stLinkButton"]>a:hover { border-color:var(--sca-blue); color:var(--sca-blue); background:#F4F7F8; }
div[data-testid="stButton"]>button:focus-visible,div[data-testid="stLinkButton"]>a:focus-visible,input:focus-visible { outline:2px solid var(--sca-blue); outline-offset:2px; }
div[data-baseweb="select"]>div,div[data-testid="stTextInput"] input,div[data-testid="stDateInput"] input,div[data-testid="stTextArea"] textarea {
  border-radius:3px;
  border-color:#C9CCC8;
  background:var(--sca-surface);
}
@media(max-width:760px){
  .block-container{padding-left:1rem;padding-right:1rem;padding-top:1rem}
  .sca-brand{margin-bottom:1rem}
  .sca-brand-product{font-size:.68rem}
  .sca-change-grid{grid-template-columns:1fr;gap:1rem}
  .sca-intel-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .sca-beta-points{grid-template-columns:1fr}
  .sca-memory-row{display:block}
  .sca-memory-source{text-align:left;margin-top:.45rem}
  .sca-meta-spacer{display:none}
  .st-key-analyst-note{padding:1.2rem 1rem;border-left:0;border-right:0}
  .sca-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
  .sca-fact{min-width:0}
  .sca-table-responsive{min-width:0;border-collapse:separate;table-layout:fixed}
  .sca-table-responsive thead{display:none}
  .sca-table-responsive,.sca-table-responsive tbody,.sca-table-responsive tr,.sca-table-responsive td{display:block;width:100%}
  .sca-table-responsive tr{border-top:1px solid var(--sca-border);padding:.55rem 0}
  .sca-table-responsive td{position:relative;border:0;padding:.3rem 0 .3rem 8.6rem;min-height:1.65rem;white-space:normal;overflow-wrap:anywhere;word-break:break-word}
  .sca-table-responsive td::before{content:attr(data-label);position:absolute;left:0;top:.32rem;width:8rem;color:var(--sca-muted);font-size:.65rem;font-weight:700;letter-spacing:.055em;text-transform:uppercase}
  .sca-table-responsive td.num{white-space:normal}
  .sca-table:not(.sca-table-responsive){min-width:620px}
  .sca-table.sca-table-responsive{min-width:0;table-layout:fixed}
}
</style>
"""


def inject_styles() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)
    consume_scroll_to_top()


def render_brand() -> None:
    st.markdown(
        '<div class="sca-brand"><span class="sca-brand-name">smallcaps.ai</span><span class="sca-brand-product">AIM Intelligence</span></div>',
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        '<div class="sca-footer">Smallcaps.ai can make mistakes. Check the original RNS before acting. This is research support, not personal investment advice.</div>',
        unsafe_allow_html=True,
    )


def render_service_error(*, reference: str = "") -> None:
    clean_reference = html.escape(str(reference or "").strip())
    reference_markup = (
        f'<div class="sca-error-reference">Reference: {clean_reference}</div>'
        if clean_reference
        else ""
    )
    render_brand()
    st.markdown(
        '<div class="sca-service-error"><strong>Smallcaps.ai is temporarily unavailable.</strong><br>'
        "We have logged the problem. No research has been deleted; please try again shortly."
        + reference_markup
        + "</div>",
        unsafe_allow_html=True,
    )
    render_footer()


def log_public_exception(exc: BaseException) -> str:
    """Best-effort logging that always returns a safe customer reference."""

    reference = f"WEB-{secrets.token_hex(4).upper()}"
    summary = " ".join(str(exc).split())[:500]
    try:
        print(
            f"[web][{reference}] {type(exc).__name__}: {summary}",
            flush=True,
        )
    except Exception:
        pass
    try:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    except Exception:
        pass
    return reference


def require_beta_access(password: str, *, enabled: bool) -> None:
    if not enabled:
        return
    if not password:
        st.error("Private beta access is not available yet.")
        st.stop()
    if st.session_state.get("beta_access_granted"):
        return
    render_brand()
    st.markdown(
        '<div class="sca-beta-hero"><div class="sca-eyebrow">Private beta</div><h1 class="sca-beta-title">Every AIM announcement.<br>Analysed in minutes.</h1><div class="sca-beta-copy">Smallcaps.ai shows what changed, why it matters and what an investor should watch next — with reported facts, calculations and our view kept separate.</div><div class="sca-beta-points"><div class="sca-beta-point"><strong>Read the change</strong><br>Skip routine wording and find the economic point.</div><div class="sca-beta-point"><strong>See the numbers</strong><br>Useful maths with the disclosed inputs shown.</div><div class="sca-beta-point"><strong>Check the source</strong><br>Every note links back to the original RNS.</div></div></div>',
        unsafe_allow_html=True,
    )
    with st.form("beta-access", clear_on_submit=True):
        supplied = st.text_input("Private beta access code", type="password")
        submitted = st.form_submit_button(
            "UNLOCK PRIVATE BETA",
            type="primary",
            use_container_width=True,
        )
    if submitted and hmac.compare_digest(supplied, password):
        st.session_state["beta_access_granted"] = True
        st.session_state[_SCROLL_FLAG] = True
        st.rerun()
    if submitted:
        st.error("That access code is not valid.")
    st.caption("AI-generated research support. Verify important information against the original RNS.")
    st.stop()


def safe_http_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def impact_badge(colour: str, level: str) -> str:
    clean_colour = str(colour or "").strip().lower()
    if clean_colour not in {"green", "amber", "red", "grey"}:
        clean_colour = "grey"
    signal = impact_signal_label(clean_colour, level)
    accessible = html.escape(signal.title(), quote=True)
    return (
        f'<span class="sca-impact" aria-label="{accessible}">'
        '<span class="sca-impact-dot" aria-hidden="true" style="background:'
        + impact_hex(clean_colour)
        + '"></span>'
        + html.escape(signal)
        + "</span>"
    )


def price_markup(price: dict[str, object] | None) -> str:
    if not price or price.get("daily_change_pct") is None:
        return ""
    return f'<span class="sca-price">{html.escape(format_price_change(price))}</span>'


def navigate(view: str, **params: str) -> None:
    st.session_state[_SCROLL_FLAG] = True
    st.query_params.clear()
    st.query_params["view"] = view
    for key, value in params.items():
        if value:
            st.query_params[key] = value
    st.rerun()


def consume_scroll_to_top() -> None:
    """Reset Streamlit's retained scroll position after internal navigation.

    Streamlit reruns preserve the browser scroll offset. Without this, opening an
    Analyst Note from a lower Feed card can land the investor halfway down the new
    page. The flag is consumed once so normal widget reruns do not jump to the top.
    """

    if not st.session_state.pop(_SCROLL_FLAG, False):
        return
    components.html(
        """
        <script>
        (() => {
          const p = window.parent;
          try { p.history.scrollRestoration = 'manual'; } catch (_) {}

          const reset = () => {
            try { p.scrollTo(0, 0); } catch (_) {}
            const candidates = [
              p.document.scrollingElement,
              p.document.documentElement,
              p.document.body,
              p.document.querySelector('[data-testid="stAppViewContainer"]'),
              p.document.querySelector('[data-testid="stMain"]'),
              p.document.querySelector('section[data-testid="stMain"]'),
              p.document.querySelector('section.main')
            ];
            candidates.forEach((el) => {
              if (!el) return;
              try { el.scrollTop = 0; el.scrollLeft = 0; } catch (_) {}
            });
          };

          let frame = 0;
          const settle = () => {
            reset();
            frame += 1;
            if (frame < 16) p.requestAnimationFrame(settle);
          };
          settle();
          [75, 150, 300, 450, 700].forEach((delay) => p.setTimeout(reset, delay));
        })();
        </script>
        """,
        height=0,
    )


def query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    return str(value[0]) if isinstance(value, list) and value else str(value)


def ensure_watchlist(default_tickers: tuple[str, ...]) -> set[str]:
    if "watchlist_tickers" not in st.session_state:
        st.session_state["watchlist_tickers"] = {
            ticker.upper() for ticker in default_tickers
        }
    return set(st.session_state["watchlist_tickers"])


def toggle_watchlist(ticker: str) -> None:
    current = set(st.session_state.get("watchlist_tickers", set()))
    clean = ticker.upper()
    current.remove(clean) if clean in current else current.add(clean)
    st.session_state["watchlist_tickers"] = current
    st.rerun()


def london_now() -> datetime:
    return datetime.now(LONDON)
