(() => {
  "use strict";

  const COMPANY_SCHEMA = "scbb-company-v1";
  const MONITORING_SCHEMA = "scbb-monitoring-v1";
  const LONDON = "Europe/London";
  const IMPACT_NAMES = {
    1: "ROUTINE",
    2: "MINOR",
    3: "MATERIAL",
    4: "HIGH",
    5: "CRITICAL",
  };
  const VISIBLE_HISTORY = 12;

  const state = {
    company: null,
    detailCache: new Map(),
    expandedHistory: new Set(),
    showAllHistory: false,
  };

  document.addEventListener("DOMContentLoaded", initialise);

  async function initialise() {
    const ticker = pathTicker();
    if (!ticker) {
      renderError(new Error("A company ticker is required."));
      return;
    }
    try {
      const response = await fetch(`/api/v1/company/${encodeURIComponent(ticker)}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.error?.message || "Company research is unavailable.");
      }
      if (payload.schema_version !== COMPANY_SCHEMA) {
        throw new Error("The Company Intelligence data contract is incompatible.");
      }
      state.company = payload;
      renderCompany(payload);
    } catch (error) {
      renderError(error);
    }
  }

  function pathTicker() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts[0] !== "company" || !parts[1]) return "";
    return clean(decodeURIComponent(parts[1])).toUpperCase().replace(/\.L$/, "");
  }

  function renderCompany(company) {
    document.title = `${company.ticker} · ${company.company} · Smallcaps.ai`;
    document.getElementById("company-ticker").textContent = company.ticker;
    document.getElementById("company-name").textContent = company.company;
    document.getElementById("company-market").textContent = [company.market, company.isin]
      .map(clean)
      .filter(Boolean)
      .join(" · ") || "AIM";
    document.getElementById("company-coverage").textContent = coverageText(company.coverage || {});

    const root = document.getElementById("company-content");
    root.replaceChildren();

    if (company.current_position) {
      root.append(renderCurrentPosition(company.current_position));
    }
    if ((company.guidance || []).length) {
      root.append(renderGuidance(company.guidance));
    }
    if ((company.metrics || []).length) {
      root.append(renderMetrics(company.metrics));
    }
    if ((company.open_management_claims || []).length || (company.resolved_management_claims || []).length) {
      root.append(
        renderClaims(
          company.open_management_claims || [],
          company.resolved_management_claims || [],
        ),
      );
    }
    if ((company.disclosure_gaps || []).length) {
      root.append(renderGaps(company.disclosure_gaps));
    }
    if ((company.history || []).length) {
      root.append(renderHistory(company.history));
    }

    if (!root.children.length) {
      root.append(emptyState("Company research is still building.", "The first publishable RNS analysis will establish this monitoring sheet."));
    }
  }

  function coverageText(coverage) {
    const count = Number(coverage.announcement_count || 0);
    const noun = count === 1 ? "ANALYSED RNS" : "ANALYSED RNSS";
    const parts = [];
    if (coverage.coverage_since) {
      parts.push(`COVERAGE SINCE ${formatDate(coverage.coverage_since)}`);
    }
    parts.push(`${count} ${noun}`);
    parts.push(coverage.status === "established" ? "ESTABLISHED HISTORY" : "HISTORY STILL BUILDING");
    return parts.join(" · ");
  }

  function renderCurrentPosition(current) {
    const body = element("div");
    const grid = element("div", "company-current-grid");
    const main = element("div", "company-current-main");
    const meta = element("div", "company-current-meta");
    meta.append(
      signalBadge(current.signal),
      element("span", "", formatDate(current.published_at)),
      element("span", "", formatTime(current.published_at)),
      element("span", "", clean(current.rns_type) || "RNS"),
    );
    main.append(meta);
    main.append(element("h2", "", current.research?.verdict || current.rns_title));
    main.append(
      element(
        "p",
        "company-current-change",
        current.what_changed || current.research?.what_changed?.today || "No decision-useful change was identified.",
      ),
    );
    const ai = element("div", "company-ai-view");
    ai.append(
      element("span", "", "AI VIEW"),
      element("p", "", current.ai_view || current.research?.analyst_view || ""),
    );
    main.append(ai);

    const actions = element("div", "company-actions");
    const source = safeLink(
      current.original_source_url || current.research?.provenance?.source_urls?.[0],
      "ORIGINAL RNS ↗",
      "company-action",
    );
    if (source) actions.append(source);
    const feed = element("a", "company-action company-action-primary", "OPEN IN RNS FEED →");
    feed.href = `/?date=${dateKey(current.published_at)}&open=${encodeURIComponent(current.source_id)}`;
    actions.append(feed);
    main.append(actions);

    const side = element("aside", "company-current-side");
    side.append(
      stat("OUTLOOK", current.outlook || "N/A", current.outlook === "N/A" ? "No guidance event" : "Latest structured guidance status"),
      marketStat(current.market_reaction || {}),
      balanceStat(current.balance_sheet || {}),
      impactStat(current.impact || {}),
    );
    grid.append(main, side);
    body.append(grid);

    const detail = document.createElement("details");
    detail.className = "company-full-note";
    detail.append(element("summary", "", "VIEW FULL ANALYST NOTE"));
    detail.append(renderNote(current));
    body.append(detail);
    return section("CURRENT VIEW", "Latest publication-safe Smallcaps.ai judgement.", body, "current-view");
  }

  function stat(label, value, note) {
    const block = element("div", "company-stat");
    block.append(
      element("span", "company-stat-label", label),
      element("strong", "company-stat-value", clean(value) || "N/A"),
      element("span", "company-stat-note", clean(note)),
    );
    return block;
  }

  function marketStat(reaction) {
    const change = Number(reaction.change_pct);
    const available = reaction.status === "available" && Number.isFinite(change);
    const arrow = available ? (change > 0 ? "↑" : change < 0 ? "↓" : "→") : "—";
    const value = available ? `${arrow} ${signed(change)}%` : "—%";
    const close = reaction.close_price ?? reaction.latest_price;
    const note = available && close != null
      ? `${reaction.phase === "close" ? "RNS-day close" : "Latest"} ${formatPrice(close, reaction.currency)}`
      : "Pricing pending";
    return stat("MARKET REACTION", value, note);
  }

  function balanceStat(balance) {
    let note = "Not disclosed";
    const dated = balance.as_of_date || balance.period || balance.source_published_at;
    if (balance.status === "current") {
      note = dated ? `Reported ${formatDate(dated)}` : "Reported in latest RNS";
    } else if (balance.status === "carried") {
      note = dated ? `Last reported ${formatDate(dated)}` : "Carried from latest disclosure";
    }
    return stat("BALANCE SHEET", balance.value || "Not disclosed", note);
  }

  function impactStat(impact) {
    const score = clampImpact(impact.score);
    const block = element("div", "company-stat");
    block.append(element("span", "company-stat-label", "IMPACT"));
    block.append(impactDots(score));
    block.append(
      element("strong", "company-stat-value", `${score}/5 · ${IMPACT_NAMES[score]}`),
      element("span", "company-stat-note", "Materiality is independent from signal direction"),
    );
    return block;
  }

  function renderGuidance(items) {
    const table = element("div", "company-data-table");
    table.append(
      tableHead("company-guidance-grid", ["METRIC", "PERIOD", "CURRENT", "PREVIOUS", "STATUS", "SOURCE"]),
    );
    items.forEach((item) => {
      const previous = clean(item.previous_value || item.comparator) || "—";
      const row = tableRow("company-guidance-grid", [
        cell(item.metric, item.title),
        cell(item.period || "—"),
        cell(item.value || "Not quantified"),
        cell(previous),
        statusCell(item.status),
        sourceCell(item.source_url),
      ]);
      table.append(row);
    });
    return section("GUIDANCE", "Current forward-looking statements retained from Company Memory.", table, "guidance");
  }

  function renderMetrics(items) {
    const table = element("div", "company-data-table");
    table.append(
      tableHead("company-metrics-grid", ["METRIC", "LATEST", "PREVIOUS", "CHANGE", "PERIOD", "SOURCE"]),
    );
    items.forEach((item) => {
      const latestPoint = (item.points || []).at(-1) || {};
      const row = tableRow("company-metrics-grid", [
        cell(item.label || item.metric, item.basis === "calculated" ? "Smallcaps.ai calculation" : "Reported"),
        cell(item.latest_value || "—"),
        cell(item.previous_value || "—"),
        cell(metricChange(item)),
        cell(item.period_family || latestPoint.period || latestPoint.as_of_date || "—"),
        sourceCell(latestPoint.source_url),
      ]);
      table.append(row);
    });
    return section("METRICS THAT MATTER", "The most decision-useful comparable or genuinely numerical series.", table, "metrics");
  }

  function metricChange(item) {
    if (item.change_direction === "flat") return "UNCHANGED";
    if (["up", "down"].includes(item.change_direction) && Number.isFinite(Number(item.change_percent))) {
      const value = Math.abs(Number(item.change_percent)).toFixed(1);
      return `${item.change_direction === "up" ? "↑" : "↓"} ${value}%`;
    }
    if (["up", "down"].includes(item.change_direction)) {
      return item.change_direction.toUpperCase();
    }
    return "—";
  }

  function renderClaims(openItems, resolvedItems) {
    const body = element("div");
    if (openItems.length) {
      body.append(claimTable(openItems));
    }
    if (resolvedItems.length) {
      const details = document.createElement("details");
      details.className = "company-resolved";
      details.append(
        element(
          "summary",
          "",
          `DELIVERED, MISSED OR SUPERSEDED · ${resolvedItems.length}`,
        ),
        claimTable(resolvedItems),
      );
      body.append(details);
    }
    return section("MANAGEMENT PROMISES", "Open commitments and their eventual outcomes.", body, "promises");
  }

  function claimTable(items) {
    const table = element("div", "company-data-table");
    table.append(
      tableHead("company-claims-grid", ["PROMISE", "TARGET", "DATE", "STATUS", "SOURCE"]),
    );
    items.forEach((item) => {
      table.append(
        tableRow("company-claims-grid", [
          cell(item.claim, item.metric),
          cell(item.target_value || "—"),
          cell(item.target_date || "—"),
          statusCell(item.status, item.outcome),
          sourceCell(item.source_url),
        ]),
      );
    });
    return table;
  }

  function renderGaps(items) {
    const list = element("div", "company-gap-list");
    items.forEach((item) => {
      const row = element("div", "company-gap-row");
      row.append(element("strong", "", item.item));
      const source = safeLink(item.source_url, "LAST RELEVANT RNS ↗", "company-source-link");
      if (source) row.append(source);
      list.append(row);
    });
    return section("WHAT REMAINS UNCLEAR", "Material information the company record still does not answer.", list, "gaps");
  }

  function renderHistory(items) {
    const body = element("div", "company-history-table");
    body.append(
      tableHead("company-history-head", ["DATE / RNS", "ANALYST VIEW", "SIGNAL", "MARKET", "IMPACT", "ACTIONS"]),
    );
    const visible = state.showAllHistory ? items : items.slice(0, VISIBLE_HISTORY);
    visible.forEach((item) => body.append(historyRow(item)));

    if (!state.showAllHistory && items.length > VISIBLE_HISTORY) {
      const more = element(
        "button",
        "company-history-more",
        `SHOW EARLIER ANNOUNCEMENTS · ${items.length - VISIBLE_HISTORY}`,
      );
      more.type = "button";
      more.addEventListener("click", () => {
        state.showAllHistory = true;
        const replacement = renderHistory(items);
        body.closest("section")?.replaceWith(replacement);
      });
      body.append(more);
    }
    return section("RNS HISTORY", "How the investment case has developed through published announcements.", body, "history");
  }

  function historyRow(item) {
    const article = element("article", "company-history-row");
    article.dataset.sourceId = item.source_id;
    const grid = element("div", "company-history-grid");

    const date = element("div", "company-history-date");
    date.append(
      element("strong", "", formatDate(item.published_at)),
      element("small", "", `${formatTime(item.published_at)} · ${clean(item.rns_type) || "RNS"}`),
    );

    const copy = element("div", "company-history-copy");
    copy.append(
      element("strong", "", item.headline),
      element("p", "", item.takeaway || ""),
    );

    const signal = element("div");
    signal.append(signalBadge(item.signal));

    const market = element("div");
    const reaction = item.market_reaction || {};
    const change = Number(reaction.change_pct);
    if (reaction.status === "available" && Number.isFinite(change)) {
      market.append(
        element("strong", "", `${change > 0 ? "↑" : change < 0 ? "↓" : "→"} ${signed(change)}%`),
        element("small", "", reaction.phase === "close" ? "RNS-DAY CLOSE" : "LATEST"),
      );
    } else {
      market.append(element("strong", "", "—%"), element("small", "", "PRICING PENDING"));
    }

    const impact = element("div");
    const score = clampImpact(item.impact?.score);
    impact.append(impactDots(score), element("small", "", `${score}/5 · ${IMPACT_NAMES[score]}`));

    const actions = element("div", "company-history-actions");
    const read = element("button", "company-history-action", "READ ANALYSIS →");
    read.type = "button";
    read.setAttribute("aria-expanded", "false");
    read.addEventListener("click", () => toggleHistory(item, article, read));
    actions.append(read);
    const source = safeLink(item.original_source_url, "ORIGINAL RNS ↗", "company-history-action");
    if (source) actions.append(source);

    grid.append(date, copy, signal, market, impact, actions);
    article.append(grid);
    const detail = element("div", "company-history-detail");
    detail.hidden = true;
    article.append(detail);
    return article;
  }

  async function toggleHistory(item, article, button) {
    const detail = article.querySelector(".company-history-detail");
    const opening = detail.hidden;
    detail.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
    button.textContent = opening ? "CLOSE ANALYSIS ↑" : "READ ANALYSIS →";
    if (!opening) return;

    if (state.detailCache.has(item.source_id)) {
      detail.replaceChildren(renderNote(state.detailCache.get(item.source_id)));
      return;
    }
    detail.replaceChildren(element("div", "company-loading", "Loading full research…"));
    try {
      const response = await fetch(item.detail_url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.error?.message || "Full research is unavailable.");
      }
      if (payload.schema_version !== MONITORING_SCHEMA) {
        throw new Error("The Analyst Note data contract is incompatible.");
      }
      state.detailCache.set(item.source_id, payload);
      detail.replaceChildren(renderNote(payload));
    } catch (error) {
      detail.replaceChildren(
        emptyState("Full research is temporarily unavailable.", error?.message || "Please try again shortly."),
      );
    }
  }

  function renderNote(detail) {
    const research = detail.research || {};
    const grid = element("div", "company-note-grid");
    const first = element("div");
    first.append(
      noteBlock("RNS SUMMARY", [
        element("p", "", research.verdict || detail.rns_title || ""),
        element("p", "", research.takeaway || detail.what_changed || ""),
      ]),
      factsBlock(research.evidence || []),
    );
    const second = element("div");
    second.append(
      changedBlock(research.what_changed || {}),
      noteBlock("AI VIEW", [element("p", "", research.analyst_view || detail.ai_view || "")]),
      listBlock("WHAT TO WATCH", research.watch_items || []),
    );
    const third = element("div");
    third.append(
      guidanceBlock(research.guidance_events || []),
      listBlock("SUPPORTS THE CASE", research.supports_case || []),
      listBlock("CHALLENGES THE CASE", research.challenges_case || []),
      disclosureBlock(research.disclosure || {}, research.provenance || {}),
    );
    grid.append(first, second, third);
    return grid;
  }

  function noteBlock(title, children) {
    const block = element("section", "company-note-block");
    block.append(element("h3", "", title));
    children.filter((child) => child && clean(child.textContent)).forEach((child) => block.append(child));
    return block;
  }

  function factsBlock(facts) {
    const usable = facts.filter((item) => clean(item.label) || clean(item.value));
    if (!usable.length) return listBlock("KEY NUMBERS", ["No structured numbers disclosed."]);
    const list = element("ul");
    usable.forEach((fact) => {
      const comparison = fact.previous_value ? `; previous ${fact.previous_value}` : "";
      list.append(element("li", "", `${fact.label || fact.metric}: ${fact.value || "Not disclosed"}${comparison}`));
    });
    return noteBlock("KEY NUMBERS", [list]);
  }

  function changedBlock(change) {
    const values = [
      ["BEFORE", change.before],
      ["TODAY", change.today],
      ["READ-THROUGH", change.read_through],
    ].filter(([, value]) => clean(value));
    if (!values.length) return document.createDocumentFragment();
    const list = element("ul");
    values.forEach(([label, value]) => list.append(element("li", "", `${label}: ${value}`)));
    return noteBlock("WHAT CHANGED", [list]);
  }

  function listBlock(title, values) {
    const items = values.map(clean).filter(Boolean);
    if (!items.length) return document.createDocumentFragment();
    const list = element("ul");
    items.forEach((value) => list.append(element("li", "", value)));
    return noteBlock(title, [list]);
  }

  function guidanceBlock(items) {
    if (!items.length) return document.createDocumentFragment();
    return listBlock(
      "OUTLOOK & GUIDANCE",
      items.map((item) => `${item.metric}${item.period ? ` · ${item.period}` : ""}${item.value ? `: ${item.value}` : ""} (${clean(item.status).toUpperCase()})`),
    );
  }

  function disclosureBlock(disclosure, provenance) {
    const items = [];
    (disclosure.missing_items || []).forEach((item) => items.push(`Not disclosed: ${item}`));
    if (disclosure.management_language_mismatch) items.push(disclosure.management_language_mismatch);
    (provenance.source_warnings || []).forEach((item) => items.push(`Source warning: ${item}`));
    if (!items.length && disclosure.note) items.push(disclosure.note);
    return listBlock("DISCLOSURE GAPS / SOURCE WARNINGS", items);
  }

  function section(title, description, body, key) {
    const section = element("section", "company-section");
    section.dataset.companySection = key || slug(title);
    const head = element("header", "company-section-head");
    head.append(element("h2", "", title));
    if (description) head.append(element("p", "", description));
    section.append(head, body);
    return section;
  }

  function tableHead(className, labels) {
    const head = element("div", className);
    labels.forEach((label) => head.append(element("span", "", label)));
    return head;
  }

  function tableRow(className, cells) {
    const row = element("div", `company-data-row ${className}`);
    cells.forEach((cellNode) => row.append(cellNode));
    return row;
  }

  function cell(value, note = "") {
    const node = element("div");
    node.append(element("strong", "", clean(value) || "—"));
    if (clean(note)) node.append(element("small", "", note));
    return node;
  }

  function statusCell(value, note = "") {
    const node = element("div");
    node.append(element("span", "company-status", clean(value).replace(/-/g, " ") || "N/A"));
    if (clean(note)) node.append(element("small", "", note));
    return node;
  }

  function sourceCell(url) {
    const node = element("div");
    const link = safeLink(url, "SOURCE RNS ↗", "company-source-link");
    if (link) node.append(link);
    else node.append(element("span", "", "—"));
    return node;
  }

  function signalBadge(value) {
    return element("span", `signal signal-${slug(value)}`, clean(value) || "NO COLOUR");
  }

  function impactDots(score) {
    const dots = element("div", "company-impact-dots");
    for (let index = 1; index <= 5; index += 1) {
      dots.append(element("i", `company-impact-dot${index <= score ? " filled" : ""}`));
    }
    return dots;
  }

  function safeLink(value, label, className) {
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

  function emptyState(title, copy) {
    const block = element("div", "company-empty");
    block.append(element("h2", "", title), element("p", "", copy));
    return block;
  }

  function renderError(error) {
    const ticker = pathTicker() || "—";
    document.getElementById("company-ticker").textContent = ticker;
    document.getElementById("company-name").textContent = "Company research unavailable";
    document.getElementById("company-coverage").textContent = "NO PUBLICATION-SAFE COMPANY RECORD WAS RETURNED";
    const root = document.getElementById("company-content");
    root.replaceChildren();
    const block = element("div", "company-error");
    block.append(
      element("h2", "", "Company Intelligence is temporarily unavailable."),
      element("p", "", error?.message || "Return to the AIM RNS feed and try again shortly."),
    );
    root.append(block);
  }

  function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null && text !== "") node.textContent = String(text);
    return node;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }

  function slug(value) {
    return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function clampImpact(value) {
    return Math.max(1, Math.min(5, Number(value || 1)));
  }

  function dateKey(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: LONDON,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(date);
    const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${map.year}-${map.month}-${map.day}`;
  }

  function formatDate(value) {
    const date = new Date(clean(value).length === 10 ? `${value}T12:00:00Z` : value);
    if (Number.isNaN(date.getTime())) return clean(value).toUpperCase();
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(date).toUpperCase();
  }

  function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: LONDON,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  }

  function signed(value) {
    return `${value > 0 ? "+" : ""}${Number(value).toFixed(1)}`;
  }

  function formatPrice(value, currency = "GBp") {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    if (currency === "GBp") return `${number.toFixed(2)}p`;
    return `${currency || ""} ${number.toFixed(2)}`.trim();
  }
})();
