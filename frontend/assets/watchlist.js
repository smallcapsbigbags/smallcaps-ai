(() => {
  "use strict";

  const STORAGE_KEY = "smallcaps-ai-watchlist-v1";
  const CHANGE_EVENT = "smallcaps:watchlist-change";
  const MAX_TICKERS = 100;

  function clean(value) {
    return String(value ?? "").trim();
  }

  function normalise(value) {
    return clean(value)
      .toUpperCase()
      .replace(/\.L$/, "")
      .replace(/[^A-Z0-9.-]/g, "")
      .slice(0, 24);
  }

  function normaliseList(values) {
    const output = [];
    (Array.isArray(values) ? values : []).forEach((value) => {
      const ticker = normalise(value);
      if (ticker && !output.includes(ticker)) output.push(ticker);
    });
    return output.slice(0, MAX_TICKERS);
  }

  function read() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return normaliseList(JSON.parse(raw));
    } catch (_error) {
      return [];
    }
  }

  function dispatch(tickers) {
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, {
      detail: { tickers: [...tickers] },
    }));
  }

  function write(values) {
    const tickers = normaliseList(values);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers));
    } catch (_error) {
      return read();
    }
    dispatch(tickers);
    return tickers;
  }

  function has(value) {
    const ticker = normalise(value);
    return Boolean(ticker) && read().includes(ticker);
  }

  function toggle(value) {
    const ticker = normalise(value);
    if (!ticker) return read();
    const current = read();
    const next = current.includes(ticker)
      ? current.filter((item) => item !== ticker)
      : [...current, ticker];
    return write(next);
  }

  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) return;
    dispatch(read());
  });

  window.SmallcapsWatchlist = Object.freeze({
    storageKey: STORAGE_KEY,
    changeEvent: CHANGE_EVENT,
    maxTickers: MAX_TICKERS,
    normalise,
    read,
    write,
    has,
    toggle,
  });
})();
