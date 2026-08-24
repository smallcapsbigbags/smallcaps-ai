(() => {
  "use strict";

  const PAGE_SIZE = 50;
  const API_LIMIT = 250;
  const LONDON = "Europe/London";
  const MONITORING_SCHEMA = "scbb-monitoring-v1";
  const IMPACT_NAMES = {
    1: "ROUTINE",
    2: "MINOR",
    3: "MATERIAL",
    4: "HIGH",
    5: "CRITICAL",
  };

  const state = {
    rows: [],
    filtered: [],
    page: 0,
    materialOnly: false,
    groupByCompany: false,
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
      document.body.dataset.marketDayMode = request.date ? "requested" : "latest";

      if (state.journeyOpen && state.rows.some((row) => row.source_id === state.journeyOpen)) {
        state.expanded.add(state.journeyOpen);
      }

      populateFilterOptions();
      applyFilters();
      controls.activeDay.textContent = formatLongDate(result.date);
    } catch (error) {
      renderError(error);
    }
  }

  function cacheControls() {
    controls.rows = document.getElementById("sheet-rows");
    controls.feedCount = document.getElementById("feed-count");
    controls.activeDay = document.getElementById("active-day");
    controls.resultStatus = document.getElementById("result-status");
    controls.pageStatus = document.getElementById("page-status");
    controls.previous = document.getElementById("previous-page");
    controls.next = document.getElementById("next-page");
    controls.search = document.getElementById("search-filter");
    controls.company = document.getElementById("company-filter");
    controls.type = document.getElementById("type-filter");
    controls.signal = document.getElementById("signal-filter");
    controls.impact = document.getElementById("impact-filter");
    controls.sort = document.getElementById("sort-filter");
    controls.material = document.getElementById("material-toggle");
    controls.group = document.getElementById("group-toggle");
    controls.reset = document.getElementById("reset-filters");
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
    controls.impact.addEventListener("change", () => {
      state.materialOnly = false;
      controls.material.setAttribute("aria-pressed", "false");
      reapply();
    });
    controls.sort.addEventListener("change", reapply);

    controls.material.addEventListener("click", () => {
      state.materialOnly = !state.materialOnly;
      controls.material.setAttribute("aria-pressed", String(state.materialOnly));
      state.page = 0;
      clearJourneyOpen();
      applyFilters();
    });

    controls.group.addEventListener("click", () => {
      state.groupByCompany = !state.groupByCompany;
      controls.group.setAttribute("aria-pressed", String(state.groupByCompany));
      state.page = 0;
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
      state.materialOnly = false;
      state.groupByCompany = false;
      controls.material.setAttribute("aria-pressed", "false");
      controls.group.setAttribute("aria-pressed", "false");
      state.page = 0;
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
      const pages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
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
    return {
      date,
      items: Array.isArray(payload.items) ? payload.items : [],
    };
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
    if (!items.length) {
      return { date: today, items: [] };
    }

    const latest = items
      .map((item) => londonDateKey(new Date(item.published_at)))
      .sort()
      .at(-1);
    return {
      date: latest,
      items: items.filter(
        (item) => londonDateKey(new Date(item.published_at)) === latest,
      ),
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
      const message = payload?.error?.message || "Monitoring data is unavailable.";
      throw new Error(message);
    }
    if (payload.schema_version !== MONITORING_SCHEMA) {
      throw new Error("The monitoring-sheet data contract is incompatible.");
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

    fillSelect(controls.company, companies, "ALL COMPANIES");
    fillSelect(controls.type, types, "ALL TYPES");
  }

  function fillSelect(select, options, firstLabel) {
    const current = select.value;
    select.replaceChildren(new Option(firstLabel, ""));
    options.forEach((item) => select.add(new Option(item.label, item.value)));
    if ([...select.options].some((option) => option.value === current)) {
      select.value = current;
    }
  }

  function applyFilters() {
    const search = clean(controls.search.value).toLowerCase();
    const ticker = controls.company.value;
    const type = controls.type.value;
    const signal = controls.signal.value;
    const selectedImpact = Number(controls.impact.value || 0);
    const minimumImpact = state.materialOnly ? Math.max(3, selectedImpact) : selectedImpact;

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
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });

    const sort = state.groupByCompany ? "company" : controls.sort.value;
    rows = [...rows].sort((a, b) => compareRows(a, b, sort));
    state.filtered = rows;

    if (state.journeyOpen) {
      const requestedIndex = rows.findIndex((row) => row.source_id === state.journeyOpen);
      if (requestedIndex >= 0) {
        state.page = Math.floor(requestedIndex / PAGE_SIZE);
      }
    }

    const maxPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1);
    state.page = Math.min(state.page, maxPage);
    renderRows();
    updateSummary();

    if (state.pendingReveal) {
      window.requestAnimationFrame(revealJourneyRow);
    }
  }

  function compareRows(a, b, sort) {
    if (sort === "impact") {
      return (
        Number(b.impact?.score || 0) - Number(a.impact?.score || 0) ||
        new Date(b.published_at) - new Date(a.published_at)
      );
    }
    if (sort === "company") {
      return (
        clean(a.company).localeCompare(clean(b.company)) ||
        new Date(b.published_at) - new Date(a.published_at)
      );
    }
    return (
      new Date(b.published_at) - new Date(a.published_at) ||
      Number(b.impact?.score || 0) - Number(a.impact?.score || 0)
    );
  }

  function updateSummary() {
    const companyCount = new Set(state.rows.map((row) => row.ticker)).size;
    controls.feedCount.textContent = `${state.rows.length} announcements · ${companyCount} companies`;

    if (state.journeyOpen && !state.rows.some((row) => row.source_id === state.journeyOpen)) {
      controls.resultStatus.textContent = "The requested announcement is not available on this market day";
      return;
    }
    controls.resultStatus.textContent = `${state.filtered.length} of ${state.rows.length} announcements shown`;
  }

  function renderRows() {
    controls.rows.replaceChildren();
    if (!state.filtered.length) {
      controls.rows.append(emptyState());
      updatePagination();
      return;
    }

    const start = state.page * PAGE_SIZE;
    const pageRows = state.filtered.slice(start, start + PAGE_SIZE);
    pageRows.forEach((row) => controls.rows.append(buildRow(row)));
    updatePagination();
  }

  function buildRow(row) {
    const article = element("article", "monitor-row");
    article.dataset.sourceId = row.source_id;
    article.dataset.expanded = String(state.expanded.has(row.source_id));

    const grid = element("div", "monitor-row-grid");
    grid.append(
      buildCompanyCell(row),
      buildTextCell("what-changed-cell", row.what_changed),
      buildTextCell("ai-view-cell", row.ai_view),
      buildOutlookCell(row),
      buildMarketCell(row),
      buildBalanceSheetCell(row),
      buildImpactCell(row),
    );
    article.append(grid);

    const detail = element("div", "expanded-research");
    detail.id = detailId(row.source_id);
    detail.hidden = !state.expanded.has(row.source_id);
    article.append(detail);

    if (state.expanded.has(row.source_id)) {
      void ensureDetail(row, detail);
    }
    return article;
  }

  function buildCompanyCell(row) {
    const cell = element("div", "monitor-cell company-cell");
    const toggle = element("button", "row-toggle");
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", String(state.expanded.has(row.source_id)));
    toggle.setAttribute("aria-controls", detailId(row.source_id));
    toggle.setAttribute(
      "aria-label",
      `${state.expanded.has(row.source_id) ? "Collapse" : "Expand"} ${row.ticker} ${row.rns_title}`,
    );
    toggle.append(chevron());
    toggle.addEventListener("click", () => toggleRow(row, cell.closest("article")));

    const tickerLine = element("div", "ticker-line");
    const companyLink = element("a", "company-research-link");
    companyLink.href = `/company/${encodeURIComponent(row.ticker)}`;
    companyLink.setAttribute("aria-label", `Open ${row.ticker} Company Intelligence`);
    companyLink.append(
      element("span", "ticker", row.ticker),
      element("span", "company-name", row.company),
    );
    tickerLine.append(companyLink);

    const title = element("p", "rns-title", row.rns_title);
    const meta = element(
      "p",
      "rns-meta",
      `${formatTime(row.published_at)} · ${clean(row.rns_type) || "RNS"}`,
    );
    const signal = element(
      "span",
      `signal signal-${slug(row.signal)}`,
      row.signal,
    );
    cell.append(toggle, tickerLine, title, meta, signal);
    return cell;
  }

  function buildTextCell(className, text) {
    const cell = element("div", `monitor-cell ${className}`);
    cell.append(element("p", "cell-copy", clean(text) || "Not disclosed"));
    return cell;
  }

  function buildOutlookCell(row) {
    const cell = element("div", "monitor-cell outlook-cell");
    const label = element("span", "outlook-label", row.outlook || "N/A");
    label.dataset.outlook = row.outlook || "N/A";
    const context = row.outlook === "N/A" ? "No guidance event" : "Guidance status";
    cell.append(label, element("span", "cell-subline", context));
    return cell;
  }

  function buildMarketCell(row) {
    const cell = element("div", "monitor-cell market-cell");
    const reaction = row.market_reaction || {};
    const change = Number(reaction.change_pct);
    const available = reaction.status === "available" && Number.isFinite(change);
    const move = element(
      "span",
      `market-move ${available ? (change > 0 ? "positive" : change < 0 ? "negative" : "pending") : "pending"}`,
      available ? `${change > 0 ? "↑" : change < 0 ? "↓" : "→"} ${formatSigned(change)}%` : "—%",
    );
    const close = reaction.close_price ?? reaction.latest_price;
    const context = available && close != null
      ? `${reaction.phase === "close" ? "RNS-day close" : "Latest"} ${formatPrice(close, reaction.currency)}`
      : "Pricing pending";
    cell.append(move, element("span", "cell-subline", context));
    return cell;
  }

  function buildBalanceSheetCell(row) {
    const balance = row.balance_sheet || {};
    const status = balance.status || "not-disclosed";
    const cell = element("div", "monitor-cell balance-sheet-cell");
    cell.dataset.balanceStatus = status;
    cell.append(element("span", "balance-value", balance.value || "Not disclosed"));

    let context = "Not disclosed";
    const dated = balance.as_of_date || balance.source_published_at || balance.period;
    if (status === "current") {
      context = dated ? `Reported ${formatContextDate(dated)}` : "Reported in this RNS";
    } else if (status === "carried") {
      context = dated ? `Last reported ${formatContextDate(dated)}` : "Carried from latest disclosure";
    }
    cell.append(element("span", "cell-subline", context));
    return cell;
  }

  function buildImpactCell(row) {
    const score = Math.max(1, Math.min(5, Number(row.impact?.score || 1)));
    const cell = element("div", "monitor-cell impact-cell");
    const dots = element("div", "impact-dots");
    for (let index = 1; index <= 5; index += 1) {
      dots.append(element("i", `impact-dot${index <= score ? " filled" : ""}`));
    }
    cell.append(
      dots,
      element("span", "impact-label", `${score}/5 · ${IMPACT_NAMES[score]}`),
    );
    return cell;
  }

  function toggleRow(row, article) {
    if (!article) return;
    const detail = article.querySelector(".expanded-research");
    const button = article.querySelector(".row-toggle");
    const expanding = !state.expanded.has(row.source_id);
    if (expanding) {
      state.expanded.add(row.source_id);
      state.journeyOpen = row.source_id;
      article.dataset.expanded = "true";
      detail.hidden = false;
      button.setAttribute("aria-expanded", "true");
      button.setAttribute("aria-label", `Collapse ${row.ticker} ${row.rns_title}`);
      writeJourneyUrl(row.source_id);
      void ensureDetail(row, detail);
    } else {
      state.expanded.delete(row.source_id);
      article.dataset.expanded = "false";
      detail.hidden = true;
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-label", `Expand ${row.ticker} ${row.rns_title}`);
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
    container.replaceChildren(element("div", "detail-loading", "Loading full research…"));
    try {
      const response = await fetch(row.detail_url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const detail = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(detail?.error?.message || "Full research is unavailable.");
      }
      if (detail.schema_version !== MONITORING_SCHEMA) {
        throw new Error("The Analyst Note data contract is incompatible.");
      }
      state.detailCache.set(row.source_id, detail);
      renderDetail(detail, container);
    } catch (error) {
      container.replaceChildren(
        element("div", "detail-error", error.message || "Full research is unavailable."),
      );
    }
  }

  function renderDetail(detail, container) {
    const research = detail.research || {};
    const inner = element("div", "expanded-inner");
    const top = element("div", "expanded-topline");
    top.append(element("p", "", "FULL ANALYST NOTE"));

    const actions = element("div", "expanded-top-actions");
    const ticker = clean(detail.ticker);
    if (ticker) {
      const company = element("a", "company-inline-link", "COMPANY RESEARCH →");
      company.href = `/company/${encodeURIComponent(ticker)}`;
      company.setAttribute("aria-label", `Open ${ticker} Company Intelligence`);
      actions.append(company);
    }
    const source = safeExternalLink(
      detail.original_source_url || research.provenance?.source_urls?.[0],
      "ORIGINAL RNS ↗",
      "source-link",
    );
    if (source) actions.append(source);
    if (actions.children.length) top.append(actions);

    const grid = element("div", "expanded-grid");
    const first = element("div", "expanded-column");
    first.append(
      researchBlock("RNS SUMMARY", [
        element("p", "research-verdict", research.verdict || detail.rns_title),
        element("p", "", research.takeaway || detail.what_changed),
      ]),
      buildFactBlock(research.evidence || []),
    );

    const second = element("div", "expanded-column");
    second.append(
      buildWhatChangedBlock(research.what_changed || {}),
      researchBlock("AI VIEW", [
        element("p", "", research.analyst_view || detail.ai_view),
      ]),
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
    if (!usable.length) return buildListBlock("KEY NUMBERS", ["No structured numbers disclosed."]);
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
    return researchBlock("KEY NUMBERS", [table]);
  }

  function buildWhatChangedBlock(change) {
    const stack = element("div", "change-stack");
    [
      ["BEFORE", change.before],
      ["TODAY", change.today],
      ["READ-THROUGH", change.read_through],
    ].forEach(([label, value]) => {
      if (!clean(value)) return;
      const item = element("div", "change-item");
      item.append(element("span", "", label), element("strong", "", value));
      stack.append(item);
    });
    return researchBlock("WHAT CHANGED", [stack]);
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
    const lines = events.map((event) => {
      const metric = event.metric || "Guidance";
      const period = event.period ? ` · ${event.period}` : "";
      const value = event.value ? `: ${event.value}` : "";
      return `${metric}${period}${value} (${clean(event.status).toUpperCase()})`;
    });
    return buildListBlock("OUTLOOK & GUIDANCE", lines);
  }

  function buildDisclosureBlock(disclosure, provenance) {
    const items = [];
    (disclosure.missing_items || []).forEach((item) => items.push(`Not disclosed: ${item}`));
    if (disclosure.management_language_mismatch) {
      items.push(disclosure.management_language_mismatch);
    }
    (provenance.source_warnings || []).forEach((warning) => items.push(`Source warning: ${warning}`));
    if (!items.length && disclosure.status === "complete") return document.createDocumentFragment();
    if (!items.length && disclosure.note) items.push(disclosure.note);
    const block = buildListBlock("DISCLOSURE GAPS / SOURCE WARNINGS", items);
    if (block instanceof HTMLElement) block.classList.add("research-warning");
    return block;
  }

  function updatePagination() {
    const pages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    controls.previous.disabled = state.page === 0;
    controls.next.disabled = state.page >= pages - 1;
    controls.pageStatus.textContent = `PAGE ${state.page + 1} OF ${pages}`;
  }

  function emptyState() {
    const block = element("div", "empty-state");
    const wrap = element("div");

    if (!state.rows.length && state.requestedDate) {
      wrap.append(
        element("h2", "", `No publishable announcements on ${formatLongDate(state.requestedDate)}.`),
        element("p", "", "This dated link does not currently resolve to a public monitoring record."),
      );
      const latest = element("a", "empty-state-action", "RETURN TO LATEST MARKET DAY →");
      latest.href = "/";
      wrap.append(latest);
    } else {
      wrap.append(
        element("h2", "", "No announcements match these filters."),
        element("p", "", "Reset the monitoring controls or broaden the selected signal and impact range."),
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
      element("h2", "", "Monitoring data is temporarily unavailable."),
      element("p", "", error?.message || "Please refresh the page shortly."),
    );
    block.append(wrap);
    controls.rows.append(block);
    controls.feedCount.textContent = "Live feed unavailable";
    controls.resultStatus.textContent = "The publication-safe API could not be loaded";
  }

  function revealJourneyRow() {
    state.pendingReveal = false;
    if (!state.journeyOpen) return;
    const article = [...controls.rows.querySelectorAll("article.monitor-row")].find(
      (row) => row.dataset.sourceId === state.journeyOpen,
    );
    if (!article) return;

    article.classList.add("journey-target");
    article.scrollIntoView({ block: "center" });
    const toggle = article.querySelector(".row-toggle");
    toggle?.focus({ preventScroll: true });
    window.setTimeout(() => article.classList.remove("journey-target"), 2200);
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
    }).format(new Date(`${iso}T12:00:00Z`)).toUpperCase();
  }

  function formatTime(value) {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  }

  function formatContextDate(value) {
    const cleanValue = clean(value);
    const parsed = new Date(cleanValue.length === 10 ? `${cleanValue}T12:00:00Z` : cleanValue);
    if (Number.isNaN(parsed.getTime())) return cleanValue.toUpperCase();
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(parsed).toUpperCase();
  }

  function formatSigned(value) {
    return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
  }

  function formatPrice(value, currency = "GBp") {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    if (currency === "GBp") return `${number.toFixed(2)}p`;
    return `${currency || ""} ${number.toFixed(2)}`.trim();
  }

  function scrollToSheet() {
    document.getElementById("monitoring-sheet")?.scrollIntoView({ block: "start" });
  }
})();
