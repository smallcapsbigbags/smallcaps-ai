(() => {
  "use strict";

  const PRODUCT_SURFACES = new Set(["news", "watchlist", "daily", "company"]);
  const COMPANY_CONTEXTS = new Set(["news", "watchlist", "daily"]);
  const DAILY_STATES = new Set(["early_read", "morning_note", "aim_close"]);

  document.addEventListener("DOMContentLoaded", initialise);

  function initialise() {
    const body = document.body;
    if (!body?.classList.contains("product-page")) return;

    const surface = detectSurface();
    body.dataset.productSurface = surface;
    syncNavigation(surface);
    syncProductStatus();
    syncWatchlistCount();

    if (surface === "watchlist") configureWatchlistHero();
    if (surface === "company") configureCompanyContext();
    else decorateCompanyLinks(document, surface);

    const observer = new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) return;
          if (surface === "company") rewriteCompanyNewsLinks(node);
          else decorateCompanyLinks(node, surface);
        });
      });
    });
    observer.observe(body, { childList: true, subtree: true });
  }

  function detectSurface() {
    if (document.body.classList.contains("company-intelligence-page")) return "company";
    if (document.body.classList.contains("daily-body")) return "daily";
    if (new URLSearchParams(window.location.search).get("watchlist") === "1") {
      return "watchlist";
    }
    return "news";
  }

  function syncNavigation(surface) {
    const activeSurface = surface === "company" ? companyContext() : surface;
    document.querySelectorAll("[data-product-nav]").forEach((link) => {
      const active = link.dataset.productNav === activeSurface;
      link.classList.toggle("nav-link-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function syncProductStatus() {
    document.querySelectorAll("[data-product-status]").forEach((node) => {
      node.textContent = "AIM live";
    });
  }

  function syncWatchlistCount() {
    const store = window.SmallcapsWatchlist;
    const links = [...document.querySelectorAll('[data-product-nav="watchlist"]')];
    const counts = [...document.querySelectorAll("[data-watchlist-count]")];
    if (!store) {
      counts.forEach((node) => {
        node.textContent = "";
        node.hidden = true;
      });
      return;
    }

    const render = (tickers = store.read()) => {
      const total = Array.isArray(tickers) ? tickers.length : 0;
      counts.forEach((node) => {
        node.textContent = total ? String(total) : "";
        node.hidden = total === 0;
      });
      links.forEach((link) => {
        link.setAttribute(
          "aria-label",
          total ? `Watchlist, ${total} compan${total === 1 ? "y" : "ies"}` : "Watchlist",
        );
      });
    };

    window.addEventListener(store.changeEvent, (event) => {
      render(Array.isArray(event.detail?.tickers) ? event.detail.tickers : store.read());
    });
    render();
  }

  function configureWatchlistHero() {
    setText("page-eyebrow", "PERSONAL COMPANY NEWS");
    setText("page-title", "Your watchlist.");
    setText(
      "feed-tagline",
      "Every update from the AIM companies you follow, in one place.",
    );
    document.title = "Your watchlist · Smallcaps.ai";
  }

  function decorateCompanyLinks(root, surface) {
    if (!["news", "watchlist", "daily"].includes(surface)) return;
    anchorsWithin(root).forEach((anchor) => {
      let url;
      try {
        url = new URL(anchor.getAttribute("href") || "", window.location.origin);
      } catch (_error) {
        return;
      }
      if (url.origin !== window.location.origin || !url.pathname.startsWith("/company/")) {
        return;
      }

      url.searchParams.set("from", surface);
      const sourceId = clean(anchor.closest("[data-source-id]")?.dataset.sourceId).slice(0, 180);
      if (sourceId) url.searchParams.set("open", sourceId);

      const current = new URLSearchParams(window.location.search);
      if (surface === "news") {
        const date = clean(current.get("date"));
        if (validIsoDate(date)) url.searchParams.set("date", date);
      }
      if (surface === "daily") {
        const state = clean(current.get("state"));
        const date = clean(current.get("date"));
        if (DAILY_STATES.has(state)) url.searchParams.set("daily_state", state);
        if (validIsoDate(date)) url.searchParams.set("daily_date", date);
      }

      anchor.href = `${url.pathname}${url.search}`;
      anchor.dataset.productContext = surface;
    });
  }

  function configureCompanyContext() {
    const context = companyContext();
    syncNavigation("company");
    const link = document.getElementById("company-context-link");
    if (!link) return;

    const params = new URLSearchParams(window.location.search);
    const sourceId = clean(params.get("open")).slice(0, 180);
    let href = "/rns";
    let label = "← Back to Company News";

    if (context === "watchlist") {
      const next = new URLSearchParams({ watchlist: "1" });
      if (sourceId) next.set("open", sourceId);
      href = `/rns?${next.toString()}`;
      label = "← Back to Watchlist";
    } else if (context === "daily") {
      const next = new URLSearchParams();
      const state = clean(params.get("daily_state"));
      const date = clean(params.get("daily_date"));
      if (DAILY_STATES.has(state)) next.set("state", state);
      if (validIsoDate(date)) next.set("date", date);
      href = next.toString() ? `/?${next.toString()}` : "/";
      label = "← Back to The AIM Daily";
    } else {
      const next = new URLSearchParams();
      const date = clean(params.get("date"));
      if (validIsoDate(date)) next.set("date", date);
      if (sourceId) next.set("open", sourceId);
      href = next.toString() ? `/rns?${next.toString()}` : "/rns";
    }

    if (link.getAttribute("href") !== href) link.setAttribute("href", href);
    if (link.textContent !== label) link.textContent = label;
    link.dataset.companyContext = context;
    rewriteCompanyNewsLinks(document);
  }

  function rewriteCompanyNewsLinks(root) {
    if (companyContext() !== "watchlist") return;
    anchorsWithin(root).forEach((anchor) => {
      let url;
      try {
        url = new URL(anchor.getAttribute("href") || "", window.location.origin);
      } catch (_error) {
        return;
      }
      if (url.origin !== window.location.origin || url.pathname !== "/rns") return;
      const sourceId = clean(url.searchParams.get("open")).slice(0, 180);
      if (!sourceId) return;
      const next = new URLSearchParams({ watchlist: "1", open: sourceId });
      const href = `/rns?${next.toString()}`;
      if (anchor.getAttribute("href") !== href) anchor.setAttribute("href", href);
      if (anchor.textContent?.trim() === "Open in News →") {
        anchor.textContent = "Open in Watchlist →";
      }
    });
  }

  function companyContext() {
    const value = clean(new URLSearchParams(window.location.search).get("from")).toLowerCase();
    return COMPANY_CONTEXTS.has(value) ? value : "news";
  }

  function anchorsWithin(root) {
    const anchors = [];
    if (root instanceof HTMLAnchorElement) anchors.push(root);
    if (root instanceof Document || root instanceof Element) {
      root.querySelectorAll("a[href]").forEach((anchor) => anchors.push(anchor));
    }
    return anchors;
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node && node.textContent !== value) node.textContent = value;
  }

  function validIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }

  window.SmallcapsProductShell = Object.freeze({
    surfaces: [...PRODUCT_SURFACES],
    detectSurface,
    companyContext,
  });
})();
