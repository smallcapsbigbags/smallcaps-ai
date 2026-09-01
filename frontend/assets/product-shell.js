(() => {
  "use strict";

  const PRODUCT_SURFACES = new Set(["news", "watchlist", "company"]);
  const COMPANY_CONTEXTS = new Set(["news", "watchlist"]);

  document.addEventListener("DOMContentLoaded", initialise);

  function initialise() {
    const body = document.body;
    if (!body?.classList.contains("product-page")) return;

    const surface = detectSurface();
    body.dataset.productSurface = surface;
    syncNavigation(surface);
    syncProductStatus();
    syncWatchlistCount();
    initialiseCompanySearch(surface);

    if (surface === "watchlist") configureWatchlistHero();
    if (surface === "company") {
      configureCompanyContext();
      normaliseCurrentEvidence(document);
    } else {
      decorateCompanyLinks(document, surface);
    }

    const observer = new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) return;
          if (surface === "company") {
            rewriteCompanyNewsLinks(node);
            normaliseCurrentEvidence(node);
          } else {
            decorateCompanyLinks(node, surface);
          }
        });
      });
    });
    observer.observe(body, { childList: true, subtree: true });
  }

  function detectSurface() {
    if (document.body.classList.contains("company-intelligence-page")) return "company";
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
    observeWatchlistCounts(counts);

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
    window.requestAnimationFrame(() => render());
  }

  function observeWatchlistCounts(counts) {
    counts.forEach((node) => {
      if (node.dataset.watchCountObserved === "true") return;
      node.dataset.watchCountObserved = "true";

      const normalise = () => {
        if (node.hidden && clean(node.textContent) === "0") node.textContent = "";
      };
      new MutationObserver(normalise).observe(node, {
        attributes: true,
        attributeFilter: ["hidden"],
        characterData: true,
        childList: true,
        subtree: true,
      });
      normalise();
    });
  }

  function configureWatchlistHero() {
    setText("page-eyebrow", "WATCHLIST");
    setText("page-title", "Your companies.");
    setText("feed-tagline", "What changed. What needs attention.");
    document.title = "Watchlist · Smallcaps.ai";
  }

  function initialiseCompanySearch(surface) {
    const input = document.querySelector("[data-company-search-input]");
    const options = document.querySelector("[data-company-search-options]");
    const status = document.querySelector("[data-company-search-status]");
    if (!(input instanceof HTMLInputElement)) return;

    const catalogue = new Map();
    let optionSignature = "";
    let refreshQueued = false;

    const addCompany = (tickerValue, nameValue = "") => {
      const ticker = normaliseTicker(tickerValue);
      if (!ticker) return;
      const name = clean(nameValue);
      const existing = catalogue.get(ticker) || "";
      if (!existing || (name && !/loading/i.test(name))) catalogue.set(ticker, name);
    };

    const refresh = () => {
      refreshQueued = false;

      document.querySelectorAll("a.company-research-link").forEach((link) => {
        addCompany(
          link.querySelector(".ticker")?.textContent,
          link.querySelector(".company-name")?.textContent,
        );
      });

      document.querySelectorAll("#company-filter option[value]").forEach((option) => {
        if (!(option instanceof HTMLOptionElement) || !option.value) return;
        const label = clean(option.textContent).replace(/^\S+\s*[·-]\s*/, "");
        addCompany(option.value, label);
      });

      addCompany(
        document.getElementById("company-ticker")?.textContent,
        document.getElementById("company-name")?.textContent,
      );

      if (!(options instanceof HTMLDataListElement)) return;
      const entries = [...catalogue.entries()].sort(([left], [right]) => left.localeCompare(right));
      const signature = JSON.stringify(entries);
      if (signature === optionSignature) return;
      optionSignature = signature;
      options.replaceChildren(
        ...entries.map(([ticker, name]) => {
          const option = document.createElement("option");
          option.value = ticker;
          if (name) option.label = name;
          return option;
        }),
      );
    };

    const scheduleRefresh = () => {
      if (refreshQueued) return;
      refreshQueued = true;
      window.requestAnimationFrame(refresh);
    };

    const resolveCompany = (rawValue, allowTickerFallback) => {
      const value = clean(rawValue);
      const lower = value.toLowerCase();
      if (!value) return null;

      for (const [ticker, name] of catalogue.entries()) {
        if (ticker.toLowerCase() === lower || clean(name).toLowerCase() === lower) {
          return ticker;
        }
      }

      const selected = value.match(/^([A-Za-z0-9.-]{1,12})\s*[·-]/)?.[1];
      if (selected) return normaliseTicker(selected);
      return allowTickerFallback ? normaliseTicker(value) : "";
    };

    const openCompany = () => {
      refresh();
      const allowTickerFallback = surface === "company" || input.dataset.newsFilter !== "true";
      const ticker = resolveCompany(input.value, allowTickerFallback);
      if (!ticker) {
        if (status) status.textContent = "Keep typing or choose a company ticker.";
        return false;
      }

      const context = surface === "watchlist" ? "watchlist" : companyContext();
      const query = new URLSearchParams({ from: context });
      window.location.assign(`/company/${encodeURIComponent(ticker)}?${query.toString()}`);
      return true;
    };

    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.isComposing) return;
      if (openCompany()) event.preventDefault();
    });
    input.addEventListener("input", () => {
      if (status) status.textContent = "";
    });

    const observed = document.getElementById("sheet-rows")
      || document.getElementById("company-research")
      || document.body;
    new MutationObserver(scheduleRefresh).observe(observed, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    refresh();
  }

  function decorateCompanyLinks(root, surface) {
    if (!["news", "watchlist"].includes(surface)) return;
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
    let label = "← Back to News";

    if (context === "watchlist") {
      const next = new URLSearchParams({ watchlist: "1" });
      if (sourceId) next.set("open", sourceId);
      href = `/rns?${next.toString()}`;
      label = "← Back to Watchlist";
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
        anchor.textContent = anchor.classList.contains("company-action")
          ? "Open in Watchlist →"
          : "Open announcement in Watchlist →";
      }
    });
  }

  function normaliseCurrentEvidence(root) {
    const sourceId = clean(new URLSearchParams(window.location.search).get("open")).slice(0, 180);
    if (!sourceId) return;

    detailsWithin(root).forEach((details) => {
      const card = details.closest("[data-source-id]");
      if (clean(card?.dataset.sourceId) !== sourceId) return;
      if (details.open) details.open = false;
    });
  }

  function detailsWithin(root) {
    const details = [];
    if (
      root instanceof HTMLDetailsElement
      && root.classList.contains("company-current-evidence")
    ) {
      details.push(root);
    }
    if (root instanceof Document || root instanceof Element) {
      root.querySelectorAll("details.company-current-evidence").forEach((node) => details.push(node));
    }
    return details;
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

  function normaliseTicker(value) {
    const ticker = clean(value).toUpperCase();
    return /^[A-Z0-9.-]{1,12}$/.test(ticker) ? ticker : "";
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
