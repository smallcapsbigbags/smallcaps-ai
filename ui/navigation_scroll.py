from __future__ import annotations

import streamlit as st


_LAST_VIEW_SIGNATURE = "_smallcaps_last_view_signature"


def reset_scroll_on_view_change(
    view: str,
    *,
    source_id: str = "",
    ticker: str = "",
) -> None:
    """Reliably start a newly selected Streamlit view at the top.

    Streamlit preserves the scroll position of its internal ``stMain`` container
    across reruns. A single early reset is not sufficient because the framework
    can restore that position again while the replacement view is mounting. This
    helper runs only when the logical destination changes, then holds every known
    scroll container at zero through the short render/restore window.
    """

    clean_view = str(view or "feed").strip().lower() or "feed"
    clean_source_id = str(source_id or "").strip()
    clean_ticker = str(ticker or "").strip().upper()
    signature = "|".join((clean_view, clean_source_id, clean_ticker))

    if st.session_state.get(_LAST_VIEW_SIGNATURE) == signature:
        return
    st.session_state[_LAST_VIEW_SIGNATURE] = signature

    st.iframe(
        """
        <script>
        (() => {
          const p = window.parent;
          const startedAt = Date.now();
          const holdForMs = 2400;
          let intervalId = null;
          let mutationObserver = null;
          let resizeObserver = null;

          try { p.history.scrollRestoration = 'manual'; } catch (_) {}

          const candidates = () => [
            p.document.scrollingElement,
            p.document.documentElement,
            p.document.body,
            p.document.querySelector('[data-testid="stAppViewContainer"]'),
            p.document.querySelector('[data-testid="stMain"]'),
            p.document.querySelector('section[data-testid="stMain"]'),
            p.document.querySelector('section.main')
          ].filter(Boolean);

          const reset = () => {
            try { p.scrollTo({ top: 0, left: 0, behavior: 'auto' }); } catch (_) {
              try { p.scrollTo(0, 0); } catch (_) {}
            }
            candidates().forEach((el) => {
              try {
                el.scrollTop = 0;
                el.scrollLeft = 0;
                if (typeof el.scrollTo === 'function') {
                  el.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                }
              } catch (_) {}
            });
          };

          const finish = () => {
            reset();
            if (intervalId !== null) p.clearInterval(intervalId);
            try { mutationObserver?.disconnect(); } catch (_) {}
            try { resizeObserver?.disconnect(); } catch (_) {}
          };

          reset();

          try {
            mutationObserver = new p.MutationObserver(reset);
            mutationObserver.observe(p.document.documentElement, {
              childList: true,
              subtree: true,
              attributes: true
            });
          } catch (_) {}

          try {
            resizeObserver = new p.ResizeObserver(reset);
            candidates().forEach((el) => resizeObserver.observe(el));
          } catch (_) {}

          intervalId = p.setInterval(() => {
            reset();
            if (Date.now() - startedAt >= holdForMs) finish();
          }, 40);

          let frame = 0;
          const settle = () => {
            reset();
            frame += 1;
            if (frame < 150 && Date.now() - startedAt < holdForMs) {
              p.requestAnimationFrame(settle);
            }
          };
          p.requestAnimationFrame(settle);

          [80, 160, 320, 640, 960, 1280, 1600, 2000, 2400]
            .forEach((delay) => p.setTimeout(reset, delay));
          p.setTimeout(finish, holdForMs + 80);
        })();
        </script>
        """,
        width=1,
        height=1,
        tab_index=-1,
    )
