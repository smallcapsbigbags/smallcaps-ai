from __future__ import annotations

import hmac

import streamlit as st

from ui.common import _SCROLL_FLAG, render_brand

BETA_CSS = """
<style>
.sca-beta-simple {
  max-width:680px;
  padding:3.3rem 0 .85rem;
}
.sca-beta-kicker {
  color:var(--sca-muted);
  font-size:.68rem;
  font-weight:760;
  letter-spacing:.11em;
  text-transform:uppercase;
}
.sca-beta-simple-title {
  color:var(--sca-text);
  font-size:clamp(2.25rem,6vw,4rem);
  font-weight:760;
  letter-spacing:-.06em;
  line-height:1.01;
  margin:.5rem 0 .85rem;
  max-width:650px;
}
.sca-beta-simple-copy {
  color:#30373C;
  font-size:1.03rem;
  line-height:1.62;
  max-width:620px;
}
.st-key-beta-access-shell {
  max-width:620px;
  margin:.35rem 0 0;
}
.st-key-beta-access-shell [data-testid="stForm"] {
  border:0 !important;
  padding:0 !important;
}
.st-key-beta-access-shell input {
  min-height:2.85rem !important;
  border-radius:5px !important;
}
.st-key-beta-access-shell [data-testid="stFormSubmitButton"] button {
  min-height:2.85rem !important;
  background:var(--sca-text) !important;
  border-color:var(--sca-text) !important;
  border-radius:5px !important;
  color:#fff !important;
  font-weight:700 !important;
}
.st-key-beta-access-shell [data-testid="stFormSubmitButton"] button:hover {
  background:#2A3035 !important;
  border-color:#2A3035 !important;
  color:#fff !important;
}
.sca-beta-disclaimer {
  color:var(--sca-muted);
  font-size:.72rem;
  line-height:1.5;
  margin-top:.7rem;
  max-width:620px;
}
@media(max-width:760px){
  .sca-beta-simple{padding:2rem 0 .65rem}
  .sca-beta-simple-title{font-size:2.45rem;line-height:1.02}
  .sca-beta-simple-copy{font-size:.98rem;line-height:1.58}
  .st-key-beta-access-shell input,
  .st-key-beta-access-shell [data-testid="stFormSubmitButton"] button{min-height:2.95rem !important}
}
</style>
"""


def require_beta_access(password: str, *, enabled: bool) -> None:
    if not enabled:
        return
    if not password:
        st.error("Private beta access is not available yet.")
        st.stop()
    if st.session_state.get("beta_access_granted"):
        return

    st.markdown(BETA_CSS, unsafe_allow_html=True)
    render_brand()
    st.markdown(
        '<div class="sca-beta-simple">'
        '<div class="sca-beta-kicker">Private beta</div>'
        '<h1 class="sca-beta-simple-title">Know what changed.<br>See the evidence.</h1>'
        '<div class="sca-beta-simple-copy">Every AIM announcement analysed in minutes, '
        'with reported facts and Smallcaps.ai judgement kept separate.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.container(key="beta-access-shell"):
        with st.form("beta-access", clear_on_submit=True):
            supplied = st.text_input("Private beta access code", type="password")
            submitted = st.form_submit_button(
                "Enter Smallcaps.ai",
                type="primary",
                use_container_width=True,
            )

    if submitted and hmac.compare_digest(supplied, password):
        st.session_state["beta_access_granted"] = True
        st.session_state[_SCROLL_FLAG] = True
        st.rerun()
    if submitted:
        st.error("That access code is not valid.")

    st.markdown(
        '<div class="sca-beta-disclaimer">AI-assisted research. Verify important '
        'information against the original RNS.</div>',
        unsafe_allow_html=True,
    )
    st.stop()
