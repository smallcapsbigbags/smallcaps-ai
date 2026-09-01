(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const tagline = document.getElementById("feed-tagline");
    if (!tagline) return;

    const watchlist = new URLSearchParams(window.location.search).get("watchlist") === "1";
    const copy = watchlist
      ? "What changed. What needs attention."
      : "What changed across AIM.";

    const render = () => {
      if (tagline.textContent !== copy) tagline.textContent = copy;
    };

    render();
    new MutationObserver(render).observe(tagline, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  });
})();
