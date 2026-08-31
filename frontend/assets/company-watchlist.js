(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", initialise);

  function initialise() {
    const store = window.SmallcapsWatchlist;
    const button = document.getElementById("company-watch-toggle");
    const ticker = pathTicker();
    if (!store || !button || !ticker) {
      if (button) button.hidden = true;
      return;
    }

    const sync = (tickers = store.read()) => {
      const watching = tickers.includes(ticker);
      button.setAttribute("aria-pressed", String(watching));
      button.setAttribute(
        "aria-label",
        `${watching ? "Remove" : "Add"} ${ticker} ${watching ? "from" : "to"} watchlist`,
      );
      button.textContent = watching ? "★ Watching" : "☆ Watch";
    };

    button.addEventListener("click", () => store.toggle(ticker));
    window.addEventListener(store.changeEvent, (event) => {
      sync(Array.isArray(event.detail?.tickers) ? event.detail.tickers : store.read());
    });
    sync();
  }

  function pathTicker() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts[0] !== "company" || !parts[1]) return "";
    return String(decodeURIComponent(parts[1]) || "")
      .trim()
      .toUpperCase()
      .replace(/\.L$/, "");
  }
})();
