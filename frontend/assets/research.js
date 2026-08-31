(() => {
  "use strict";

  const PAGE_SIZE = 50;
  const API_LIMIT = 250;
  const KEY_NEWS_THRESHOLD = 3;
  const WATCHLIST_RANGE_DAYS = 365;
  const WATCHLIST_MAX_ROWS = 1000;
  const LONDON = "Europe/London";
  const MONITORING_SCHEMA = "scbb-monitoring-v1";
  const SIGNAL_LABELS = {
    GREEN: "Positive",
    AMBER: "Mixed",
    RED: "Negative",
    "NO COLOUR": "Neutral",
  };

  const state = {
    rows: [],
    filtered: [],
    visible: [],
    page: 0,
    showAll: false,
    activeDate: "",
    rangeFrom: "",
    requestedDate: "",
    journeyOpen: "",
    pendingReveal: false,
    watchlistOnly: false,
    watchlist: new Set(),
    watchlistTruncated: false,
    detailCache: new Map(),
    expanded: new Set(),
  };

  const controls = {};

  document.addEventListener("DOMContentLoaded", initialise);

  async function initialise() {
    cacheControls();
    bindControls();
    bindWatchlist();

    try {
      const request = readJourneyRequest();
      state.requestedDate = request.date;
      state.journeyOpen = request.open;
      state.pendingReveal = Boolean(request.open);
      state.watchlistOnly = request.watchlistOnly;
      state.watchlist = new Set(readWatchlist());
      state.showAll = state.watchlistOnly;

      applyModeChrome();
      const result = state.watchlistOnly
        ? await loadWatchlistFeed()
        : request.date
          ? await loadMarketDay(request.date)
          : await loadLatestMarketDay();

      state.rows = result.items;
      state.activeDate = result.date;
      state.rangeFrom = result.from || "";
      state.watchlistTruncated = Boolean(result.truncated);

      if (state.journeyOpen && state.rows.some((row) => row.source_id === state.journeyOpen)) {
        state.expanded.add(state.journeyOpen);
        const requested = state.rows.find((row) => row.source_id === state.journeyOpen);
        if (Number(requested?.impact?.score || 0) < KEY_NEWS_THRESHOLD) state.showAll = true;
      }

      populateFilterOptions();
      updatePeriodLabel();
      updateWatchlistNav();
      applyFilters();
    } catch (error) {
      renderError(error);
    }
  }

  function cacheControls() {
    controls.rows = document.getElementById("sheet-rows");
    controls.feedCount = document.getElementById("feed-count");
    controls.feedMode = document.getElementById("feed-mode");
    controls.activeDay = document.getElementById("active-day");
    controls.periodLabel = document.getElementById("period-label");
    controls.pageEyebrow = document.getElementById("page-eyebrow");
    controls.feedTagline = document.getElementById("feed-tagline");
    controls.newsNav = document.getElementById("news-nav-link");
    controls.watchlistNav = document.getElementById("watchlist-nav-link");
    controls.watchlistNavCount = document.getElementById("watchlist-nav-count");
    controls.resultStatus = document.getElementById("result-status");
    controls.pageStatus = document.getElementById("page-status");
    controls.pagination = document.querySelector(".pagination");
    controls.previous = document.getElementById("previous-page");
    controls.next = document.getElementById("next-page");
    controls.search = document.getElementById("search-filter");
    controls.company = document.getElementById("company-filter");
    controls.type = document.getElementById("type-filter");
    controls.signal = document.getElementById("signal-filter");
    controls.impact = document.getElementById("impact-filter");
    controls.sort = document.getElementById("sort-filter");
    controls.material = document.getElementById("material-toggle");
    controls.reset = document.getElementById("reset-filters");
    controls.filtersToggle = document.getElementById("filters-toggle");
    controls.filterPanel = document.getElementById("filter-panel");
    controls.filterCount = document.getElementById("filter-count");
  }

  function bindControls() {
    const reapply = () => {
      state.page = 0;
      clearJourneyOpen();
      applyFilters();
    };

    controls.search.addEventListener("input", reapply);
    controls.company.addEventListener("change", reapply);
    controls.type.addEventListener("change", reapply);
    controls.signal.addEventListener("change", reapply);
    controls.impact.addEventListener("change", reapply);
    controls.sort.addEventListener("change", reapply);

    controls.filtersToggle.addEventListener("click", () => {
      const opening = controls.filterPanel.hidden;
      controls.filterPanel.hidden = !opening;
      controls.filtersToggle.setAttribute("aria-expanded", String(opening));
    });

    controls.material.addEventListener("click", () => {
      state.showAll = !state.showAll;
      state.page = 0;
      controls.material.setAttribute("aria-pressed", String(state.showAll));
      clearJourneyOpen();
      applyFilters();
    });

    controls.reset.addEventListener("click", () => {
      controls.search.value = "";
      controls.company.value = "";
      controls.type.value = "";
      controls.signal.value = "";
      controls.impact.value = "0";
      controls.sort.value = "latest";
      state.showAll = state.watchlistOnly;
      state.page = 0;
      controls.material.setAttribute("aria-pressed", String(state.showAll));
      clearJourneyOpen();
      applyFilters();
    });

    controls.previous.addEventListener("click", () => {
      if (state.page > 0) {
        state.page -= 1;
        renderRows();
        scrollToSheet();
      }
    });

    controls.next.addEventListener("click", () => {
      const pages = Math.max(1, Math.ceil(state.visible.length / PAGE_SIZE));
      if (state.page < pages - 1) {
        state.page += 1;
        renderRows();
        scrollToSheet();
      }
    });
  }

  function bindWatchlist() {
    const store = window.SmallcapsWatchlist;
    if (!store) return;
    window.addEventListener(store.changeEvent, (event) => {
      const next = Array.isArray(event.detail?.tickers) ? event.detail.tickers : store.read();
      const previous = new Set(state.watchlist);
      state.watchlist = new Set(next);
      updateWatchlistNav();

      if (state.watchlistOnly) {
        const addedTicker = next.some((ticker) => !previous.has(ticker));
        if (addedTicker) {
          void reloadWatchlistFeed();
          return;
        }
        state.page = 0;
        applyFilters();
        return;
      }
      renderRows();
    });
  }

  function readWatchlist() {
    return window.SmallcapsWatchlist ? window.SmallcapsWatchlist.read() : [];
  }

  function isWatched(ticker) {
    const cleanTicker = window.SmallcapsWatchlist
      ? window.SmallcapsWatchlist.normalise(ticker)
      : clean(ticker).toUpperCase();
    return state.watchlist.has(cleanTicker);
  }

  function readJourneyRequest() {
    const params = new URLSearchParams(window.location.search);
    const requestedDate = clean(params.get("date"));
    const requestedOpen = clean(params.get("open")).slice(0, 180);
    const watchlistOnly = params.get("watchlist") === "1";
    if (requestedDate && !validIsoDate(requestedDate)) {
      throw new Error("The requested market day must use YYYY-MM-DD.");
    }
    return {
      date: watchlistOnly ? "" : requestedDate,
      open: requestedOpen,
      watchlistOnly,
    };
  }

  async function loadMarketDay(date) {
    const payload = await fetchPage({ date });
    return { date, items: Array.isArray(payload.items) ? payload.items : [] };
  }

  async function loadLatestMarketDay() {
    const today = londonDateKey(new Date());
    const todayPayload = await fetchPage({ date: today });
    if (todayPayload.items && todayPayload.items.length) {
      return { date: today, items: todayPayload.items };
    }

    const from = addDays(today, -31);
    const recent = await fetchPage({ date_from: from, date_to: today });
    const items = Array.isArray(recent.items) ? recent.items : [];
    if (!items.length) return { date: today, items: [] };

    const latest = items
      .map((item) => londonDateKey(new Date(item.published_at)))
      .sort()
      .at(-1);
    return {
      date: latest,
      items: items.filter((item) => londonDateKey(new Date(item.published_at)) === latest),
    };
  }

  async function loadWatchlistFeed() {
    const today = londonDateKey(new Date());
    const from = addDays(today, -WATCHLIST_RANGE_DAYS);
    const tickers = [...state.watchlist].sort();
    if (!tickers.length) return { date: today, from, items: [], truncated: false };

    const result = await fetchAllPages({
      date_from: from,
      date_to: today,
      ticker: tickers,
    });
    return { date: today, from, items: result.items, truncated: result.truncated };
  }

  async function reloadWatchlistFeed() {
    controls.rows.replaceChildren(element("div", "detail-loading", "Refreshing watchlist…"));
    controls.feedCount.textContent = "Refreshing watchlist…";
    try {
      const result = await loadWatchlistFeed();
      state.rows = result.items;
      state.activeDate = result.date;
      state.rangeFrom = result.from;
      state.watchlistTruncated = result.truncated;
      state.expanded.clear();
      state.detailCache.clear();
      populateFilterOptions();
      updatePeriodLabel();
      applyFilters();
    } catch (error) {
      renderError(error);
    }
  }

  async function fetchAllPages(params) {
    const items = [];
    let offset = 0;
    let truncated = false;

    while (items.length < WATCHLIST_MAX_ROWS) {
      const payload = await fetchPage({ ...params, offset });
      const pageItems = Array.isArray(payload.items) ? payload.items : [];
      items.push(...pageItems);
      if (!payload.has_more || !pageItems.length) break;
      offset += pageItems.length;
      if (items.length >= WATCHLIST_MAX_ROWS) {
        truncated = true;
        break;
      }
    }

    return {
      items: items.slice(0, WATCHLIST_MAX_ROWS),
      truncated,
    };
  }

  async function fetchPage(params) {
    const query = new URLSearchParams({ limit: String(API_LIMIT), sort: "latest" });
    Object.entries(params).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => {
          const cleanItem = clean(item);
          if (cleanItem) query.append(key, cleanItem);
        });
        return;
      }
      if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
    });

    const response = await fetch(`/api/v1/monitoring?${query.toString()}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.error?.message || "Company news is unavailable.");
    if (payload.schema_version !== MONITORING_SCHEMA) {
      throw new Error("The company-news data contract is incompatible.");
    }
    return payload;
  }

  function applyModeChrome() {
    if (state.watchlistOnly) {
      controls.pageEyebrow.textContent = "WATCHLIST";
      controls.feedTagline.textContent = "All updates from companies you follow.";
      controls.periodLabel.textContent = "Coverage";
      setNavActive(controls.watchlistNav, true);
      setNavActive(controls.newsNav, false);
      return;
    }

    controls.pageEyebrow.textContent = "AIM COMPANY NEWS";
    controls.feedTagline.textContent = "Every material AIM announcement, reduced to what changed.";
    controls.periodLabel.textContent = "Market day";
    setNavActive(controls.newsNav, true);
    setNavActive(controls.watchlistNav, false);
  }

  function setNavActive(link, active) {
    if (!link) return;
    link.classList.toggle("nav-link-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }

  function updatePeriodLabel() {
    if (!controls.activeDay) return;
    if (state.watchlistOnly) {
      controls.activeDay.textContent = state.rangeFrom
        ? `${formatShortDate(state.rangeFrom)} – ${formatShortDate(state.activeDate)}`
        : "Last 12 months";
      return;
    }
    controls.activeDay.textContent = formatLongDate(state.activeDate);
  }

  function updateWatchlistNav() {
    if (!controls.watchlistNavCount) return;
    const count = state.watchlist.size;
    controls.watchlistNavCount.hidden = count === 0;
    controls.watchlistNavCount.textContent = String(count);
    controls.watchlistNav?.setAttribute(
      "aria-label",
      count ? `Watchlist, ${count} compan${count === 1 ? "y" : "ies"}` : "Watchlist",
    );
  }

  function populateFilterOptions() {
    const companies = uniqueBy(
      state.rows
        .filter((row) => !state.watchlistOnly || isWatched(row.ticker))
        .map((row) => ({ value: row.ticker, label: `${row.ticker} · ${row.company}` }))
        .sort((a, b) => a.label.localeCompare(b.label)),
      (item) => item.value,
    );
    const types = [...new Set(
      state.rows
        .filter((row) => !state.watchlistOnly || isWatched(row.ticker))
        .map((row) => clean(row.rns_type))
        .filter(Boolean),
    )]
      .sort((a, b) => a.localeCompare(b))
      .map((value) => ({ value, label: value }));
    fillSelect(controls.company, companies, "All companies");
    fillSelect(controls.type, types, "All types");
  }

  function fillSelect(select, options, firstLabel) {
    const current = select.value;
    select.replaceChildren(new Option(firstLabel, ""));
    options.forEach((item) => select.add(new Option(item.label, item.value)));
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  }

  function applyFilters() {
    const search = clean(controls.search.value).toLowerCase();
    const ticker = controls.company.value;
    const type = controls.type.value;
    const signal = controls.signal.value;
    const minimumImpact = Number(controls.impact.value || 0);

    let rows = state.rows.filter((row) => {
      if (state.watchlistOnly && !isWatched(row.ticker)) return false;
      if (ticker && row.ticker !== ticker) return false;
      if (type && row.rns_type !== type) return false;
      if (signal && row.signal !== signal) return false;
      if (Number(row.impact?.score || 0) < minimumImpact) return false;
      if (search) {
        const haystack = [
          row.ticker,
          row.company,
          row.rns_title,
          row.rns_type,
          row.takeaway,
          row.what_changed,
          row.ai_view,
          row.outlook,
        ].join(" ").toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });

    rows = [...rows].sort((a, b) => compareRows(a, b, controls.sort.value));
    state.filtered = rows;

    const keyRows = rows.filter((row) => Number(row.impact?.score || 0) >= KEY_NEWS_THRESHOLD);
    const requested = state.journeyOpen
      ? rows.find((row) => row.source_id === state.journeyOpen)
      : null;
    if (requested && Number(requested.impact?.score || 0) < KEY_NEWS_THRESHOLD) state.showAll = true;
    state.visible = state.showAll ? rows : keyRows;

    if (state.journeyOpen) {
      const requestedIndex = state.visible.findIndex((row) => row.source_id === state.journeyOpen);
      if (requestedIndex >= 0) state.page = Math.floor(requestedIndex / PAGE_SIZE);
    }

    const maxPage = Math.max(0, Math.ceil(state.visible.length / PAGE_SIZE) - 1);
    state.page = Math.min(state.page, maxPage);
    renderRows();
    updateSummary(keyRows.length);
    updateFilterCount();
    if (state.pendingReveal) window.requestAnimationFrame(revealJourneyRow);
  }

  function compareRows(a, b, sort) {
    if (sort === "impact") {
      return Number(b.impact?.score || 0) - Number(a.impact?.score || 0)
        || new Date(b.published_at) - new Date(a.published_at);
    }
    if (sort === "company") {
      return clean(a.company).localeCompare(clean(b.company))
        || new Date(b.published_at) - new Date(a.published_at);
    }
    return new Date(b.published_at) - new Date(a.published_at)
      || Number(b.impact?.score || 0) - Number(a.impact?.score || 0);
  }

  function updateSummary(keyCount) {
    const otherCount = Math.max(0, state.filtered.length - keyCount);

    if (state.watchlistOnly) {
      controls.feedMode.textContent = state.showAll ? "Watchlist" : "Watchlist · Key News";
      controls.feedCount.textContent = `${state.filtered.length} updates · ${keyCount} key`;
      const companies = state.watchlist.size;
      controls.resultStatus.textContent = state.watchlistTruncated
        ? `${companies} compan${companies === 1 ? "y" : "ies"} · latest ${WATCHLIST_MAX_ROWS} updates`
        : `${companies} compan${companies === 1 ? "y" : "ies"} · saved on this browser`;
    } else {
      controls.feedMode.textContent = state.showAll ? "All News" : "Key News";
      controls.feedCount.textContent = state.showAll
        ? `${state.filtered.length} updates · ${keyCount} key`
        : `${keyCount} material · ${state.filtered.length} updates`;

      if (state.journeyOpen && !state.rows.some((row) => row.source_id === state.journeyOpen)) {
        controls.resultStatus.textContent = "Requested announcement is not available on this market day";
      } else {
        controls.resultStatus.textContent = `${state.visible.length} shown`;
      }
    }

    controls.material.hidden = otherCount === 0;
    controls.material.setAttribute("aria-pressed", String(state.showAll));
    controls.material.textContent = state.showAll
      ? "Show key news only"
      : `Show ${otherCount} other update${otherCount === 1 ? "" : "s"}`;
  }

  function updateFilterCount() {
    const count = [
      controls.company.value,
      controls.type.value,
      controls.signal.value,
      controls.impact.value !== "0" ? controls.impact.value : "",
      controls.sort.value !== "latest" ? controls.sort.value : "",
    ].filter(Boolean).length;
    controls.filterCount.hidden = count === 0;
    controls.filterCount.textContent = String(count);
  }

  function renderRows() {
    controls.rows.replaceChildren();
    if (!state.visible.length) {
      controls.rows.append(emptyState());
      updatePagination();
      return;
    }

    const start = state.page * PAGE_SIZE;
    state.visible.slice(start, start + PAGE_SIZE).forEach((row) => controls.rows.append(buildRow(row)));
    updatePagination();
  }

  function buildRow(row) {
    const article = element("article", "monitor-row");
    article.dataset.sourceId = row.source_id;
    article.dataset.signal = row.signal || "NO COLOUR";
    article.dataset.expanded = String(state.expanded.has(row.source_id));
    article.dataset.watched = String(isWatched(row.ticker));

    const head = element("div", "news-row-head");
    const companyWrap = element("div", "news-company");
    companyWrap.append(buildWatchToggle(row));

    const companyLink = element("a", "company-research-link");
    companyLink.href = `/company/${encodeURIComponent(row.ticker)}`;
    companyLink.setAttribute("aria-label", `Open ${row.ticker} company research`);
    companyLink.append(
      element("span", "ticker", row.ticker),
      element("span", "company-name", row.company),
    );
    companyWrap.append(companyLink);

    const meta = element("div", "news-meta");
    meta.append(
      buildImpactScale(row),
      element("span", `signal-pill signal-${slug(row.signal)}`, SIGNAL_LABELS[row.signal] || "Neutral"),
      element("span", "type-pill", clean(row.rns_type) || "Company news"),
      element(
        "span",
        state.watchlistOnly ? "news-time news-time-watchlist" : "news-time",
        state.watchlistOnly
          ? `${formatShortDate(row.published_at)} · ${formatTime(row.published_at)}`
          : formatTime(row.published_at),
      ),
    );
    head.append(companyWrap, meta);

    const toggle = element("button", "row-toggle");
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", String(state.expanded.has(row.source_id)));
    toggle.setAttribute("aria-controls", detailId(row.source_id));
    toggle.setAttribute(
      "aria-label",
      `${state.expanded.has(row.source_id) ? "Collapse" : "Open"} ${row.ticker}: ${row.rns_title}`,
    );
    toggle.append(
      element("h2", "news-headline", clean(row.rns_title) || "Company update"),
      element("p", "news-take", compactWords(row.takeaway || row.ai_view || row.what_changed, 45)),
      buildNewsFooter(row),
    );
    toggle.addEventListener("click", () => toggleRow(row, article));

    const chevronWrap = element("span", "row-chevron");
    chevronWrap.append(chevron());

    const detail = element("div", "expanded-research");
    detail.id = detailId(row.source_id);
    detail.hidden = !state.expanded.has(row.source_id);

    article.append(head, toggle, chevronWrap, detail);
    if (state.expanded.has(row.source_id)) void ensureDetail(row, detail);
    return article;
  }

  function buildWatchToggle(row) {
    const watched = isWatched(row.ticker);
    const button = element("button", "watch-toggle", watched ? "★" : "☆");
    button.type = "button";
    button.setAttribute("aria-pressed", String(watched));
    button.setAttribute(
      "aria-label",
      `${watched ? "Remove" : "Add"} ${row.ticker} ${watched ? "from" : "to"} watchlist`,
    );
    button.title = watched ? "Remove from watchlist" : "Add to watchlist";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      window.SmallcapsWatchlist?.toggle(row.ticker);
    });
    return button;
  }

  function buildImpactScale(row) {
    const score = Math.max(1, Math.min(5, Number(row.impact?.score || 1)));
    const wrap = element("span", "impact-scale");
    wrap.setAttribute("aria-label", `Materiality ${score} out of 5`);
    for (let index = 1; index <= 5; index += 1) {
      wrap.append(element("i", `impact-dot${index <= score ? " filled" : ""}`));
    }
    wrap.append(element("span", "impact-label", `${score}/5`));
    return wrap;
  }

  function buildNewsFooter(row) {
    const footer = element("div", "news-footer");
    footer.append(buildPriceLine(row.market_reaction || {}));
    if (row.outlook && row.outlook !== "N/A") {
      footer.append(element("span", "dot-separator", "·"));
      footer.append(element("span", "outlook-inline", `GUIDANCE ${clean(row.outlook)}`));
    }
    return footer;
  }

  function buildPriceLine(reaction) {
    const previous = optionalNumber(reaction.previous_close);
    const change = optionalNumber(reaction.change_pct);
    const hasPrevious = previous !== null;
    const hasChange = reaction.status === "available" && change !== null;
    const line = element("span", "price-line");
    if (hasPrevious) line.append(element("span", "", `PRE ${formatPrice(previous, reaction.currency)}`));
    if (hasPrevious && hasChange) line.append(element("span", "dot-separator", "·"));
    if (hasChange) {
      line.append(element(
        "span",
        change > 0 ? "day-positive" : change < 0 ? "day-negative" : "day-flat",
        `DAY ${formatSigned(change)}%`,
      ));
    }
    if (!hasPrevious && !hasChange) line.append(element("span", "", "PRICE PENDING"));
    return line;
  }

  function toggleRow(row, article) {
    const detail = article.querySelector(".expanded-research");
    const button = article.querySelector(".row-toggle");
    const expanding = !state.expanded.has(row.source_id);
    if (expanding) {
      state.expanded.add(row.source_id);
      state.journeyOpen = row.source_id;
      article.dataset.expanded = "true";
      detail.hidden = false;
      button.setAttribute("aria-expanded", "true");
      button.setAttribute("aria-label", `Collapse ${row.ticker}: ${row.rns_title}`);
      writeJourneyUrl(row.source_id);
      void ensureDetail(row, detail);
    } else {
      state.expanded.delete(row.source_id);
      article.dataset.expanded = "false";
      detail.hidden = true;
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-label", `Open ${row.ticker}: ${row.rns_title}`);
      if (state.journeyOpen === row.source_id) {
        state.journeyOpen = "";
        writeJourneyUrl("");
      }
    }
  }

  async function ensureDetail(row, container) {
    if (state.detailCache.has(row.source_id)) {
      renderDetail(state.detailCache.get(row.source_id), container);
      return;
    }
    container.replaceChildren(element("div", "detail-loading", "Loading material facts…"));
    try {
      const response = await fetch(row.detail_url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const detail = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(detail?.error?.message || "Company news detail is unavailable.");
      if (detail.schema_version !== MONITORING_SCHEMA) {
        throw new Error("The company-news detail contract is incompatible.");
      }
      state.detailCache.set(row.source_id, detail);
      renderDetail(detail, container);
    } catch (error) {
      container.replaceChildren(element("div", "detail-error", error.message || "Company news detail is unavailable."));
    }
  }

  function renderDetail(detail, container) {
    const research = detail.research || {};
    const facts = Array.isArray(research.evidence) ? research.evidence : [];
    const inner = element("div", "expanded-inner forensic-detail");

    const top = element("div", "expanded-topline");
    top.append(element("p", "", "EVIDENCE"));
    const actions = element("div", "expanded-top-actions");
    const ticker = clean(detail.ticker);
    if (ticker) {
      const company = element("a", "company-inline-link", "COMPANY →");
      company.href = `/company/${encodeURIComponent(ticker)}`;
      company.setAttribute("aria-label", `Open ${ticker} company research`);
      actions.append(company);
    }
    const source = safeExternalLink(
      detail.original_source_url || research.provenance?.source_urls?.[0],
      "SOURCE ↗",
      "source-link",
    );
    if (source) actions.append(source);
    if (actions.children.length) top.append(actions);

    const take = researchBlock("TAKE", [
      element("p", "forensic-take", compactWords(research.takeaway || detail.takeaway || detail.ai_view, 45)),
    ]);

    const grid = element("div", "forensic-grid");
    const primary = element("div", "forensic-primary");
    primary.append(buildFactBlock(facts));

    const side = element("div", "forensic-side");
    side.append(
      buildWhatChangedBlock(research.what_changed || {}),
      buildMarketReactionBlock(detail.market_reaction || {}),
      buildGuidanceBlock(research.guidance_events || []),
      buildNotDisclosedBlock(facts, research.disclosure || {}),
      buildSourceChecksBlock(research.disclosure || {}, research.provenance || {}),
    );

    grid.append(primary, side);
    inner.append(top, take, grid);
    container.replaceChildren(inner);
  }

  function researchBlock(title, children) {
    const block = element("section", "research-block");
    block.append(element("h3", "", title));
    children.filter(Boolean).forEach((child) => block.append(child));
    return block;
  }

  function buildFactBlock(facts) {
    const usable = facts.filter((fact) => {
      const basis = clean(fact.basis).toLowerCase();
      return basis !== "not-disclosed"
        && basis !== "source-warning"
        && (clean(fact.label) || clean(fact.value));
    });
    if (!usable.length) {
      return buildListBlock("MATERIAL FACTS", ["No structured material facts available."]);
    }

    const table = element("table", "fact-table forensic-fact-table");
    const body = document.createElement("tbody");
    usable.forEach((fact) => {
      const row = document.createElement("tr");
      const label = document.createElement("th");
      label.scope = "row";
      label.textContent = fact.label || fact.metric || "Reported fact";

      const value = document.createElement("td");
      value.append(element("strong", "fact-value", fact.value || "—"));

      const meta = [];
      if (clean(fact.basis)) meta.push(clean(fact.basis).toUpperCase());
      if (clean(fact.period)) meta.push(clean(fact.period));
      if (clean(fact.as_of_date) && clean(fact.as_of_date) !== clean(fact.period)) meta.push(clean(fact.as_of_date));
      if (clean(fact.previous_value)) meta.push(`Previous ${clean(fact.previous_value)}`);
      else if (clean(fact.comparator)) meta.push(`Comparator ${clean(fact.comparator)}`);
      if (meta.length) value.append(element("span", "fact-note", meta.join(" · ")));
      if (clean(fact.note)) value.append(element("span", "fact-method", clean(fact.note)));

      row.append(label, value);
      body.append(row);
    });
    table.append(body);
    return researchBlock("MATERIAL FACTS", [table]);
  }

  function buildWhatChangedBlock(change) {
    const baseline = change.coverage_status === "building";
    const stack = element("div", "change-stack");
    const values = baseline
      ? [["BASELINE", change.today]]
      : [["BEFORE", change.before], ["TODAY", change.today]];

    values.forEach(([label, value]) => {
      if (!clean(value)) return;
      const item = element("div", "change-item");
      item.append(element("span", "", label));
      item.append(element("strong", "", clean(value)));
      stack.append(item);
    });

    if (!stack.children.length) return document.createDocumentFragment();
    return researchBlock(baseline ? "CURRENT BASELINE" : "WHAT CHANGED", [stack]);
  }

  function buildMarketReactionBlock(reaction) {
    const previous = optionalNumber(reaction.previous_close);
    const change = optionalNumber(reaction.change_pct);
    const hasPrevious = previous !== null;
    const hasChange = reaction.status === "available" && change !== null;
    const grid = element("div", "market-reaction-grid");

    const pre = element("div", "market-reaction-cell");
    pre.append(
      element("span", "", "PRE"),
      element("strong", "", hasPrevious ? formatPrice(previous, reaction.currency) : "Pending"),
    );
    grid.append(pre);

    const day = element("div", "market-reaction-cell");
    const dayValue = hasChange ? `${formatSigned(change)}%` : "Pending";
    day.append(
      element("span", "", "DAY"),
      element(
        "strong",
        hasChange ? (change > 0 ? "day-positive" : change < 0 ? "day-negative" : "day-flat") : "",
        dayValue,
      ),
    );
    grid.append(day);

    const phase = clean(reaction.phase);
    if (hasChange && phase) {
      grid.append(element("p", "market-reaction-note", phase === "close" ? "Official close" : "Live session"));
    }
    return researchBlock("MARKET REACTION", [grid]);
  }

  function buildGuidanceBlock(events) {
    const usable = events.filter((event) => clean(event.metric) || clean(event.value) || clean(event.status));
    if (!usable.length) return document.createDocumentFragment();
    const list = element("ul", "research-list guidance-list");
    usable.forEach((event) => {
      const parts = [clean(event.metric) || "Guidance"];
      if (clean(event.period)) parts.push(clean(event.period));
      if (clean(event.value)) parts.push(clean(event.value));
      if (clean(event.status)) parts.push(clean(event.status).toUpperCase());
      if (clean(event.previous_value)) parts.push(`Previous ${clean(event.previous_value)}`);
      list.append(element("li", "", parts.join(" · ")));
    });
    return researchBlock("GUIDANCE", [list]);
  }

  function buildNotDisclosedBlock(facts, disclosure) {
    const items = [];
    facts.forEach((fact) => {
      if (clean(fact.basis).toLowerCase() !== "not-disclosed") return;
      items.push(clean(fact.label || fact.metric || "Material item"));
    });
    (disclosure.missing_items || []).forEach((item) => items.push(clean(item)));
    return buildListBlock("NOT DISCLOSED", uniqueStrings(items));
  }

  function buildSourceChecksBlock(disclosure, provenance) {
    const items = [];
    if (clean(disclosure.management_language_mismatch)) {
      items.push(clean(disclosure.management_language_mismatch));
    }
    (provenance.source_warnings || []).forEach((warning) => {
      if (clean(warning)) items.push(clean(warning));
    });
    if (!items.length && disclosure.status === "insufficient" && clean(disclosure.note)) {
      items.push(clean(disclosure.note));
    }
    const block = buildListBlock("SOURCE CHECKS", uniqueStrings(items));
    if (block instanceof HTMLElement) block.classList.add("research-warning");
    return block;
  }

  function buildListBlock(title, values) {
    const items = values.map(clean).filter(Boolean);
    if (!items.length) return document.createDocumentFragment();
    const list = element("ul", "research-list");
    items.forEach((item) => list.append(element("li", "", item)));
    return researchBlock(title, [list]);
  }

  function updatePagination() {
    const pages = Math.max(1, Math.ceil(state.visible.length / PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    controls.pagination.hidden = pages <= 1;
    controls.previous.disabled = state.page === 0;
    controls.next.disabled = state.page >= pages - 1;
    controls.pageStatus.textContent = `Page ${state.page + 1} of ${pages}`;
  }

  function emptyState() {
    const block = element("div", "empty-state");
    const wrap = element("div");
    const hasFilteredOthers = !state.showAll && state.filtered.length > 0;

    if (state.watchlistOnly && state.watchlist.size === 0) {
      wrap.append(
        element("h2", "", "Your watchlist is empty."),
        element("p", "", "Star a company in News to build one combined feed."),
      );
      const browse = element("a", "empty-state-action", "Browse company news →");
      browse.href = "/rns";
      wrap.append(browse);
    } else if (state.watchlistOnly && !state.rows.length) {
      wrap.append(
        element("h2", "", "No watchlist updates in the last 12 months."),
        element("p", "", "Your watched companies have no publishable Company News in this coverage window."),
      );
    } else if (!state.rows.length && state.requestedDate) {
      wrap.append(
        element("h2", "", `No publishable company news on ${formatLongDate(state.requestedDate)}.`),
        element("p", "", "This dated link does not currently resolve to a public record."),
      );
      const latest = element("a", "empty-state-action", "Return to latest market day →");
      latest.href = "/rns";
      wrap.append(latest);
    } else if (hasFilteredOthers) {
      wrap.append(
        element("h2", "", "No Key News matches these filters."),
        element("p", "", "Other lower-materiality updates are available below."),
      );
    } else {
      wrap.append(
        element("h2", "", state.watchlistOnly ? "No watchlist updates match these filters." : "No company news matches these filters."),
        element("p", "", "Reset the filters or broaden your search."),
      );
    }
    block.append(wrap);
    return block;
  }

  function renderError(error) {
    controls.rows.replaceChildren();
    const block = element("div", "error-state");
    const wrap = element("div");
    wrap.append(
      element("h2", "", state.watchlistOnly ? "Watchlist is temporarily unavailable." : "Company news is temporarily unavailable."),
      element("p", "", error?.message || "Please refresh the page shortly."),
    );
    block.append(wrap);
    controls.rows.append(block);
    controls.feedCount.textContent = state.watchlistOnly ? "Watchlist unavailable" : "Live feed unavailable";
    controls.resultStatus.textContent = "Publication-safe data could not be loaded";
  }

  function revealJourneyRow() {
    state.pendingReveal = false;
    if (!state.journeyOpen) return;
    const article = [...controls.rows.querySelectorAll("article.monitor-row")]
      .find((row) => row.dataset.sourceId === state.journeyOpen);
    if (!article) return;
    article.classList.add("journey-target");
    article.scrollIntoView({ block: "center" });
    article.querySelector(".row-toggle")?.focus({ preventScroll: true });
    window.setTimeout(() => article.classList.remove("journey-target"), 1800);
  }

  function clearJourneyOpen() {
    state.pendingReveal = false;
    state.journeyOpen = "";
    writeJourneyUrl("");
  }

  function writeJourneyUrl(sourceId) {
    const url = new URL(window.location.href);
    if (state.watchlistOnly) {
      url.searchParams.set("watchlist", "1");
      url.searchParams.delete("date");
    } else {
      url.searchParams.delete("watchlist");
      if (state.activeDate) url.searchParams.set("date", state.activeDate);
    }
    if (sourceId) url.searchParams.set("open", sourceId);
    else url.searchParams.delete("open");
    const query = url.searchParams.toString();
    window.history.replaceState(
      { marketDay: state.watchlistOnly ? null : state.activeDate, watchlist: state.watchlistOnly, open: sourceId || null },
      "",
      `${url.pathname}${query ? `?${query}` : ""}${url.hash}`,
    );
  }

  function safeExternalLink(value, label, className) {
    const cleanValue = clean(value);
    if (!cleanValue) return null;
    try {
      const url = new URL(cleanValue, window.location.origin);
      if (!["http:", "https:"].includes(url.protocol)) return null;
      const link = element("a", className, label);
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      return link;
    } catch (_error) {
      return null;
    }
  }

  function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null && text !== "") node.textContent = String(text);
    return node;
  }

  function chevron() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 10 10");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M2 1.5 7 5 2 8.5");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.4");
    svg.append(path);
    return svg;
  }

  function detailId(sourceId) {
    return `detail-${String(sourceId).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  }

  function uniqueBy(items, key) {
    const seen = new Set();
    return items.filter((item) => {
      const value = key(item);
      if (seen.has(value)) return false;
      seen.add(value);
      return true;
    });
  }

  function uniqueStrings(values) {
    return [...new Set(values.map(clean).filter(Boolean))];
  }

  function compactWords(value, limit) {
    const text = clean(value);
    const words = text.split(" ").filter(Boolean);
    if (words.length <= limit) return text;
    return `${words.slice(0, limit).join(" ").replace(/[,:;\-]+$/, "")}…`;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }

  function slug(value) {
    return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function optionalNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function validIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  }

  function londonDateKey(value) {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: LONDON,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(value);
    const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${map.year}-${map.month}-${map.day}`;
  }

  function addDays(iso, days) {
    const value = new Date(`${iso}T12:00:00Z`);
    value.setUTCDate(value.getUTCDate() + days);
    return value.toISOString().slice(0, 10);
  }

  function formatLongDate(iso) {
    if (!iso) return "—";
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(`${iso}T12:00:00Z`));
  }

  function formatShortDate(value) {
    if (!value) return "—";
    const date = /^\d{4}-\d{2}-\d{2}$/.test(String(value))
      ? new Date(`${value}T12:00:00Z`)
      : new Date(value);
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      day: "numeric",
      month: "short",
      year: "2-digit",
    }).format(date);
  }

  function formatTime(value) {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  }

  function formatSigned(value) {
    return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
  }

  function formatPrice(value, currency = "GBp") {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    if (currency === "GBp") return `${number.toFixed(number >= 100 ? 1 : 2)}p`;
    return `${currency || ""} ${number.toFixed(2)}`.trim();
  }

  function scrollToSheet() {
    document.getElementById("monitoring-sheet")?.scrollIntoView({ block: "start" });
  }
})();
