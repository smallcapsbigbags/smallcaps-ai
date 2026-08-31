(() => {
  "use strict";

  const PAGE_SIZE = 50;
  const API_LIMIT = 250;
  const KEY_NEWS_THRESHOLD = 3;
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
    requestedDate: "",
    journeyOpen: "",
    pendingReveal: false,
    detailCache: new Map(),
    expanded: new Set(),
  };

  const controls = {};

  document.addEventListener("DOMContentLoaded", initialise);

  async function initialise() {
    cacheControls();
    bindControls();

    try {
      const request = readJourneyRequest();
      state.requestedDate = request.date;
      state.journeyOpen = request.open;
      state.pendingReveal = Boolean(request.open);

      const result = request.date
        ? await loadMarketDay(request.date)
        : await loadLatestMarketDay();
      state.rows = result.items;
      state.activeDate = result.date;

      if (state.journeyOpen && state.rows.some((row) => row.source_id === state.journeyOpen)) {
        state.expanded.add(state.journeyOpen);
        const journeyRow = state.rows.find((row) => row.source_id === state.journeyOpen);
        if (Number(journeyRow?.impact?.score || 0) < KEY_NEWS_THRESHOLD) state.showAll = true;
      }

      populateFilterOptions();
      controls.activeDay.textContent = formatLongDate(result.date);
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
      state.showAll = false;
      state.page = 0;
      controls.material.setAttribute("aria-pressed", "false");
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

  function readJourneyRequest() {
    const params = new URLSearchParams(window.location.search);
    const requestedDate = clean(params.get("date"));
    const requestedOpen = clean(params.get("open")).slice(0, 180);
    if (requestedDate && !validIsoDate(requestedDate)) {
      throw new Error("The requested market day must use YYYY-MM-DD.");
    }
    return { date: requestedDate, open: requestedOpen };
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

  async function fetchPage(params) {
    const query = new URLSearchParams({ limit: String(API_LIMIT), sort: "latest" });
    Object.entries(params).forEach(([key, value]) => query.set(key, value));
    const response = await fetch(`/api/v1/monitoring?${query.toString()}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.error?.message || "Company news is unavailable.");
    }
    if (payload.schema_version !== MONITORING_SCHEMA) {
      throw new Error("The company-news data contract is incompatible.");
    }
    return payload;
  }

  function populateFilterOptions() {
    const companies = uniqueBy(
      state.rows
        .map((row) => ({ value: row.ticker, label: `${row.ticker} · ${row.company}` }))
        .sort((a, b) => a.label.localeCompare(b.label)),
      (item) => item.value,
    );
    const types = [...new Set(state.rows.map((row) => clean(row.rns_type)).filter(Boolean))]
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
    controls.feedMode.textContent = state.showAll ? "All News" : "Key News";
    controls.feedCount.textContent = state.showAll
      ? `${state.filtered.length} updates · ${keyCount} key`
      : `${keyCount} material · ${state.filtered.length} updates`;

    if (state.journeyOpen && !state.rows.some((row) => row.source_id === state.journeyOpen)) {
      controls.resultStatus.textContent = "Requested announcement is not available on this market day";
    } else {
      controls.resultStatus.textContent = `${state.visible.length} shown`;
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

    const head = element("div", "news-row-head");
    const companyLink = element("a", "company-research-link");
    companyLink.href = `/company/${encodeURIComponent(row.ticker)}`;
    companyLink.setAttribute("aria-label", `Open ${row.ticker} company research`);
    companyLink.append(
      element("span", "ticker", row.ticker),
      element("span", "company-name", row.company),
    );

    const meta = element("div", "news-meta");
    meta.append(
      buildImpactScale(row),
      element("span", `signal-pill signal-${slug(row.signal)}`, SIGNAL_LABELS[row.signal] || "Neutral"),
      element("span", "type-pill", clean(row.rns_type) || "Company news"),
      element("span", "news-time", formatTime(row.published_at)),
    );
    head.append(companyLink, meta);

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
      element("p", "news-take", compactWords(row.ai_view || row.what_changed, 45)),
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
    const reaction = row.market_reaction || {};
    const previous = Number(reaction.previous_close);
    const change = Number(reaction.change_pct);
    const hasPrevious = Number.isFinite(previous);
    const hasChange = reaction.status === "available" && Number.isFinite(change);

    const price = element("span", "price-line");
    if (hasPrevious) price.append(element("span", "", `PRE ${formatPrice(previous, reaction.currency)}`));
    if (hasPrevious && hasChange) price.append(element("span", "dot-separator", "·"));
    if (hasChange) {
      price.append(element(
        "span",
        change > 0 ? "day-positive" : change < 0 ? "day-negative" : "day-flat",
        `DAY ${formatSigned(change)}%`,
      ));
    }
    if (!hasPrevious && !hasChange) price.append(element("span", "", "PRICE PENDING"));
    footer.append(price);

    if (row.outlook && row.outlook !== "N/A") {
      footer.append(element("span", "dot-separator", "·"));
      footer.append(element("span", "outlook-inline", `GUIDANCE ${clean(row.outlook)}`));
    }
    return footer;
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
      if (detail.schema_version !== MONITORING_SCHEMA) throw new Error("The company-news detail contract is incompatible.");
      state.detailCache.set(row.source_id, detail);
      renderDetail(detail, container);
    } catch (error) {
      container.replaceChildren(element("div", "detail-error", error.message || "Company news detail is unavailable."));
    }
  }

  function renderDetail(detail, container) {
    const research = detail.research || {};
    const inner = element("div", "expanded-inner");
    const top = element("div", "expanded-topline");
    top.append(element("p", "", "COMPANY NEWS DETAIL"));

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

    const grid = element("div", "expanded-grid");
    const first = element("div", "expanded-column");
    first.append(
      researchBlock("TAKE", [
        element("p", "research-verdict", research.verdict || detail.rns_title),
        element("p", "", compactWords(research.takeaway || detail.ai_view, 45)),
      ]),
      buildFactBlock(research.evidence || []),
    );

    const second = element("div", "expanded-column");
    second.append(
      buildWhatChangedBlock(research.what_changed || {}),
      researchBlock("READ-THROUGH", [element("p", "", research.analyst_view || detail.ai_view)]),
      buildListBlock("WHAT TO WATCH", research.watch_items || []),
    );

    const third = element("div", "expanded-column");
    third.append(
      buildGuidanceBlock(research.guidance_events || []),
      buildListBlock("SUPPORTS THE CASE", research.supports_case || []),
      buildListBlock("CHALLENGES THE CASE", research.challenges_case || []),
      buildDisclosureBlock(research.disclosure || {}, research.provenance || {}),
    );

    grid.append(first, second, third);
    inner.append(top, grid);
    container.replaceChildren(inner);
  }

  function researchBlock(title, children) {
    const block = element("section", "research-block");
    block.append(element("h3", "", title));
    children.filter(Boolean).forEach((child) => block.append(child));
    return block;
  }

  function buildFactBlock(facts) {
    const usable = facts.filter((fact) => clean(fact.label) || clean(fact.value));
    if (!usable.length) return buildListBlock("MATERIAL FACTS", ["No structured material facts available."]);
    const table = element("table", "fact-table");
    const body = document.createElement("tbody");
    usable.forEach((fact) => {
      const row = document.createElement("tr");
      const label = document.createElement("th");
      label.scope = "row";
      label.textContent = fact.label || fact.metric || "Reported fact";
      const value = document.createElement("td");
      value.textContent = fact.value || "Not disclosed";
      const notes = [
        fact.previous_value ? `Previous: ${fact.previous_value}` : "",
        fact.period || fact.as_of_date || "",
        fact.basis && fact.basis !== "reported" ? fact.basis : "",
      ].filter(Boolean);
      if (notes.length) value.append(element("span", "fact-note", notes.join(" · ")));
      row.append(label, value);
      body.append(row);
    });
    table.append(body);
    return researchBlock("MATERIAL FACTS", [table]);
  }

  function buildWhatChangedBlock(change) {
    const stack = element("div", "change-stack");
    const baseline = change.coverage_status === "building";
    [
      [baseline ? "BASELINE" : "BEFORE", baseline ? change.today : change.before],
      [baseline ? "" : "TODAY", baseline ? "" : change.today],
      ["READ-THROUGH", change.read_through],
    ].forEach(([label, value]) => {
      if (!clean(value)) return;
      const item = element("div", "change-item");
      if (label) item.append(element("span", "", label));
      item.append(element("strong", "", value));
      stack.append(item);
    });
    return researchBlock(baseline ? "CURRENT BASELINE" : "WHAT CHANGED", [stack]);
  }

  function buildListBlock(title, values) {
    const items = values.map(clean).filter(Boolean);
    if (!items.length) return document.createDocumentFragment();
    const list = element("ul", "research-list");
    items.forEach((item) => list.append(element("li", "", item)));
    return researchBlock(title, [list]);
  }

  function buildGuidanceBlock(events) {
    if (!events.length) return document.createDocumentFragment();
    return buildListBlock("GUIDANCE", events.map((event) => {
      const metric = event.metric || "Guidance";
      const period = event.period ? ` · ${event.period}` : "";
      const value = event.value ? `: ${event.value}` : "";
      return `${metric}${period}${value} (${clean(event.status).toUpperCase()})`;
    }));
  }

  function buildDisclosureBlock(disclosure, provenance) {
    const items = [];
    (disclosure.missing_items || []).forEach((item) => items.push(`Not disclosed: ${item}`));
    if (disclosure.management_language_mismatch) items.push(disclosure.management_language_mismatch);
    (provenance.source_warnings || []).forEach((warning) => items.push(`Source warning: ${warning}`));
    if (!items.length && disclosure.status === "complete") return document.createDocumentFragment();
    if (!items.length && disclosure.note) items.push(disclosure.note);
    const block = buildListBlock("DISCLOSURE GAPS / SOURCE WARNINGS", items);
    if (block instanceof HTMLElement) block.classList.add("research-warning");
    return block;
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

    if (!state.rows.length && state.requestedDate) {
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
        element("h2", "", "No company news matches these filters."),
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
      element("h2", "", "Company news is temporarily unavailable."),
      element("p", "", error?.message || "Please refresh the page shortly."),
    );
    block.append(wrap);
    controls.rows.append(block);
    controls.feedCount.textContent = "Live feed unavailable";
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
    if (state.activeDate) url.searchParams.set("date", state.activeDate);
    if (sourceId) url.searchParams.set("open", sourceId);
    else url.searchParams.delete("open");
    const query = url.searchParams.toString();
    window.history.replaceState(
      { marketDay: state.activeDate, open: sourceId || null },
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
