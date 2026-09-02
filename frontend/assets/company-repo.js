(() => {
  "use strict";

  const COMPANY_SCHEMA = "scbb-company-v1";
  const MONITORING_SCHEMA = "scbb-monitoring-v1";
  const INITIAL_NEWS_COUNT = 10;
  const MAX_KEY_NUMBERS = 6;
  const SIGNAL_LABELS = Object.freeze({
    GREEN: "Positive",
    AMBER: "Mixed",
    RED: "Negative",
    "NO COLOUR": "Neutral",
  });
  const SIGNAL_SHORT = Object.freeze({
    GREEN: "POS",
    AMBER: "MIXED",
    RED: "NEG",
    "NO COLOUR": "NEUTRAL",
  });
  const GENERIC_CHANGE = new Set([
    "",
    "coverage is building",
    "coverage is building.",
    "no comparator available",
    "no meaningful comparator",
    "not disclosed",
    "n/a",
    "unknown",
  ]);

  const state = {
    company: null,
    detailCache: new Map(),
    newsExpanded: false,
  };

  document.addEventListener("DOMContentLoaded", initialise);
  document.addEventListener("keydown", handleKeyboard);

  async function initialise() {
    const ticker = pathTicker();
    setText("company-ticker", ticker || "—");

    if (!ticker) {
      renderError(new Error("A company ticker was not supplied."));
      return;
    }

    try {
      const response = await fetch(`/api/v1/company/${encodeURIComponent(ticker)}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.error?.message || "Company data is unavailable.");
      }
      if (payload.schema_version !== COMPANY_SCHEMA) {
        throw new Error("The company data contract is incompatible.");
      }

      state.company = payload;
      renderCompany(payload);
      await activateRequestedAnnouncement(payload);
    } catch (error) {
      renderError(error);
    }
  }

  function renderCompany(company) {
    const ticker = clean(company.ticker) || pathTicker() || "—";
    document.title = `${ticker} · Smallcaps.ai`;
    setText("company-ticker", ticker);
    setText("company-name", company.company || ticker);
    setText("company-market", clean(company.market) || "AIM");
    setText("company-coverage", coverageText(company.coverage));

    const content = document.getElementById("company-content");
    if (!content) return;
    content.replaceChildren();

    content.append(buildStory(company));

    const numbers = buildKeyNumbers(company);
    if (numbers) content.append(numbers);

    content.append(buildCompanyNews(company));
  }

  function buildStory(company) {
    const block = element("section", "repo-section repo-story-section");
    block.id = "company-story";
    block.dataset.companySection = "current-position";
    block.append(visuallyHiddenHeading("Company story"));

    const detail = company.current_position;
    if (!detail) {
      block.append(
        emptyState(
          "Story building.",
          "The latest material company position will appear after a publishable announcement is analysed.",
        ),
      );
      return block;
    }

    const card = element("article", `repo-story tone-${signalTone(detail.signal)}`);
    card.dataset.sourceId = clean(detail.source_id);

    const meta = element("div", "repo-story-meta");
    const metaCopy = element("div", "repo-story-meta-copy");
    metaCopy.append(
      signalBadge(detail.signal, false),
      metaSeparator(),
      element("span", "", `${clampImpact(detail.impact?.score)}/5`),
      metaSeparator(),
      element("time", "", formatDate(detail.published_at)),
    );
    if (clean(detail.rns_type)) {
      metaCopy.append(metaSeparator(), element("span", "", detail.rns_type));
    }

    const actions = element("div", "repo-actions");
    const source = safeExternalLink(
      detail.original_source_url,
      "Source ↗",
      "repo-action company-action company-action-primary",
    );
    if (source) actions.append(source);
    actions.append(
      internalLink(
        newsHref(detail.published_at, detail.source_id),
        "Open in News →",
        "repo-action company-action",
      ),
    );
    meta.append(metaCopy, actions);

    const now = storyNow(detail);
    const change = storyChange(detail);
    const watch = storyWatch(company, detail);

    const grid = element("div", "repo-story-grid");
    grid.append(
      storyCell("NOW", now.value, now.note, "now"),
      storyCell("CHANGE", change.value, change.note, "change"),
      storyCell("WATCH", watch.value, watch.note, "watch"),
    );

    card.append(meta, grid);
    block.append(card);
    return block;
  }

  function storyNow(detail) {
    const research = detail.research || {};
    const value = firstDistinct(
      [
        research.takeaway,
        research.verdict,
        research.what_changed?.today,
        detail.what_changed,
        detail.rns_title,
      ],
      "",
    ) || "Latest company position not yet summarised.";

    return {
      value: clipWords(value, 36),
      note: currentFactsLine(detail),
    };
  }

  function storyChange(detail) {
    const research = detail.research || {};
    const today = meaningfulChange(research.what_changed?.today)
      || meaningfulChange(detail.what_changed);
    const before = meaningfulChange(research.what_changed?.before);

    if (!today) {
      return {
        value: research.what_changed?.coverage_status === "building"
          ? "Baseline building."
          : "No explicit change stated.",
        note: "",
      };
    }

    return {
      value: clipWords(today, 34),
      note: before && normaliseCompare(before) !== normaliseCompare(today)
        ? `Before: ${clipWords(before, 24)}`
        : "",
    };
  }

  function storyWatch(company, detail) {
    const watchItems = (detail.research?.watch_items || [])
      .map(clean)
      .filter(Boolean);
    if (watchItems.length) {
      return {
        value: clipWords(watchItems[0], 30),
        note: watchItems[1] ? clipWords(watchItems[1], 22) : "",
      };
    }

    const claim = (company.open_management_claims || []).find((item) => clean(item.claim));
    if (claim) {
      const meta = [];
      if (clean(claim.target_value)) meta.push(`Target ${claim.target_value}`);
      if (clean(claim.target_date)) meta.push(`Due ${claim.target_date}`);
      return {
        value: clipWords(claim.claim, 30),
        note: meta.join(" · "),
      };
    }

    const guidance = (company.guidance || []).find(
      (item) => clean(item.metric) || clean(item.value),
    );
    if (guidance) {
      const label = clean(guidance.metric) || "Guidance";
      const value = clean(guidance.value);
      const meta = [guidance.period, statusLabel(guidance.status)]
        .map(clean)
        .filter(Boolean)
        .join(" · ");
      return {
        value: clipWords(value ? `${label}: ${value}` : label, 30),
        note: meta,
      };
    }

    const gap = (company.disclosure_gaps || []).find((item) => clean(item.item));
    if (gap) {
      return {
        value: clipWords(gap.item, 30),
        note: "Not disclosed",
      };
    }

    return {
      value: "No explicit next test disclosed.",
      note: "",
    };
  }

  function storyCell(label, value, note, modifier) {
    const cell = element("section", `repo-story-cell repo-story-${modifier}`);
    cell.append(
      element("h2", "repo-label", label),
      element("p", "repo-story-value", value),
    );
    if (clean(note)) cell.append(element("p", "repo-story-note", note));
    return cell;
  }

  function currentFactsLine(detail) {
    const values = [];
    const outlook = outlookShort(detail.outlook);
    if (outlook) values.push(outlook);

    const balance = detail.balance_sheet || {};
    if (
      balance.status !== "not-disclosed"
      && clean(balance.value)
      && clean(balance.value).toLowerCase() !== "not disclosed"
    ) {
      const label = clean(balance.label);
      values.push(
        `${genericBalanceLabel(label) ? "Balance sheet" : label} ${clean(balance.value)}`,
      );
    }

    if (detail.market_reaction?.status === "available" && clean(detail.market_reaction.label)) {
      values.push(detail.market_reaction.label);
    }

    return values.slice(0, 3).join(" · ");
  }

  function buildKeyNumbers(company) {
    const metrics = (company.metrics || [])
      .filter((item) => clean(item.latest_value))
      .slice(0, MAX_KEY_NUMBERS);
    if (!metrics.length) return null;

    const block = element("section", "repo-section repo-numbers-section");
    block.id = "key-numbers";
    block.dataset.companySection = "key-numbers";
    block.append(sectionHead("Key numbers", `${metrics.length} latest reported`));

    const grid = element("div", "repo-metric-grid");
    metrics.forEach((metric) => grid.append(metricCard(metric)));
    block.append(grid);
    return block;
  }

  function metricCard(metric) {
    const card = element("article", "repo-metric");
    const latestPoint = Array.isArray(metric.points) ? metric.points.at(-1) || {} : {};

    const top = element("div", "repo-metric-top");
    top.append(
      element("span", "repo-metric-label", metric.label || metric.metric || "Metric"),
      element("strong", "repo-metric-value", metric.latest_value || "—"),
    );

    const meta = [];
    if (clean(metric.previous_value)) meta.push(`Prev ${metric.previous_value}`);
    const movement = metricMovement(metric);
    if (movement) meta.push(movement);
    const period = clean(latestPoint.period)
      || clean(latestPoint.as_of_date)
      || clean(metric.period_family);
    if (period) meta.push(period);
    if (clean(metric.basis).toLowerCase() === "calculated") meta.push("Calc");

    const foot = element("div", "repo-metric-foot");
    foot.append(element("span", "repo-metric-meta", meta.join(" · ") || "Latest disclosure"));
    const source = safeExternalLink(
      latestPoint.source_url,
      "Source ↗",
      "repo-source-link",
    );
    if (source) foot.append(source);

    card.append(top, foot);
    return card;
  }

  function buildCompanyNews(company) {
    const history = Array.isArray(company.history) ? company.history : [];
    const block = element("section", "repo-section repo-news-section");
    block.id = "company-news";
    block.dataset.companySection = "company-news";
    block.append(sectionHead("Company news", newsCountText(history.length, company.has_more_history)));

    if (!history.length) {
      block.append(
        emptyState(
          "No company news yet.",
          "Analysed announcements will appear here in date order.",
        ),
      );
      return block;
    }

    const list = element("div", "repo-news-list");
    history.forEach((item, index) => {
      const event = newsItem(item, index === 0);
      if (index >= INITIAL_NEWS_COUNT) event.hidden = true;
      list.append(event);
    });
    block.append(list);

    if (history.length > INITIAL_NEWS_COUNT) {
      const controls = element("div", "repo-news-controls");
      const more = element(
        "button",
        "repo-more-button",
        `Show ${history.length - INITIAL_NEWS_COUNT} older`,
      );
      more.type = "button";
      more.setAttribute("aria-expanded", "false");
      more.addEventListener("click", () => {
        state.newsExpanded = !state.newsExpanded;
        list.querySelectorAll(".repo-news-item").forEach((item, index) => {
          item.hidden = !state.newsExpanded && index >= INITIAL_NEWS_COUNT;
        });
        more.textContent = state.newsExpanded
          ? "Show latest only"
          : `Show ${history.length - INITIAL_NEWS_COUNT} older`;
        more.setAttribute("aria-expanded", String(state.newsExpanded));
      });
      controls.append(more);
      if (company.has_more_history) {
        controls.append(element("span", "repo-history-note", "Latest 200 shown"));
      }
      block.append(controls);
    } else if (company.has_more_history) {
      block.append(element("p", "repo-history-note", "Latest 200 shown"));
    }

    return block;
  }

  function newsItem(item, latest) {
    const details = element("details", `repo-news-item tone-${signalTone(item.signal)}`);
    details.dataset.sourceId = clean(item.source_id);

    const summary = element("summary", "repo-news-summary");
    const date = element("time", "repo-news-date", formatShortDate(item.published_at));
    date.dateTime = clean(item.published_at);

    const copy = element("div", "repo-news-copy");
    const eyebrow = element("div", "repo-news-eyebrow");
    if (clean(item.rns_type)) eyebrow.append(element("span", "", item.rns_type));
    if (latest) eyebrow.append(element("span", "repo-latest", "Latest"));
    copy.append(
      eyebrow,
      element("h3", "repo-news-headline", item.headline || item.rns_type || "Company update"),
    );
    if (clean(item.takeaway)) {
      copy.append(element("p", "repo-news-takeaway", clipWords(item.takeaway, 28)));
    }

    const stats = element("div", "repo-news-stats");
    stats.append(
      signalBadge(item.signal, true),
      element("span", "repo-impact", `${clampImpact(item.impact?.score)}/5`),
    );
    if (item.market_reaction?.status === "available" && clean(item.market_reaction.label)) {
      stats.append(element("span", "repo-market", marketShort(item.market_reaction)));
    }
    stats.append(element("span", "repo-chevron", "›"));

    summary.append(date, copy, stats);

    const panel = element("div", "repo-news-detail");
    panel.setAttribute("role", "region");
    panel.setAttribute(
      "aria-label",
      `${clean(item.headline) || clean(item.rns_type) || "Company update"} detail`,
    );

    details.append(summary, panel);
    details.addEventListener("toggle", () => {
      if (details.open) void loadEventDetail(item, panel);
    });
    return details;
  }

  async function loadEventDetail(item, panel) {
    if (panel.dataset.loaded === "true" || panel.dataset.loading === "true") return;
    panel.dataset.loading = "true";

    if (state.detailCache.has(item.source_id)) {
      panel.replaceChildren(renderAnnouncementDetail(state.detailCache.get(item.source_id)));
      panel.dataset.loaded = "true";
      panel.dataset.loading = "false";
      return;
    }

    panel.replaceChildren(loadingState("Loading facts…"));

    try {
      const detailUrl = sameOriginPath(item.detail_url);
      if (!detailUrl) throw new Error("The announcement detail link is invalid.");

      const response = await fetch(detailUrl, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.error?.message || "Announcement detail is unavailable.");
      }
      if (payload.schema_version !== MONITORING_SCHEMA) {
        throw new Error("The announcement data contract is incompatible.");
      }

      state.detailCache.set(item.source_id, payload);
      panel.replaceChildren(renderAnnouncementDetail(payload));
      panel.dataset.loaded = "true";
    } catch (error) {
      panel.replaceChildren(
        inlineError(
          "Detail unavailable.",
          error?.message || "Use the source announcement and try again shortly.",
        ),
      );
    } finally {
      panel.dataset.loading = "false";
    }
  }

  function renderAnnouncementDetail(detail) {
    const wrapper = element("div", "repo-detail-body");
    const grid = element("div", "repo-detail-grid");
    const research = detail.research || {};

    const facts = detailFacts(research.evidence || []);
    if (facts) grid.append(facts);

    const change = detailChange(research.what_changed || {});
    if (change) grid.append(change);

    const watch = detailWatch(research);
    if (watch) grid.append(watch);

    if (!grid.childElementCount) {
      grid.append(
        inlineError(
          "No structured detail.",
          "Use the source announcement to verify the underlying disclosure.",
        ),
      );
    }
    wrapper.append(grid);

    const missing = detailMissing(research.disclosure || {}, research.provenance || {});
    if (missing) wrapper.append(missing);

    const actions = element("div", "repo-detail-actions");
    const source = safeExternalLink(
      detail.original_source_url,
      "Source ↗",
      "repo-action company-action company-action-primary",
    );
    if (source) actions.append(source);
    actions.append(
      internalLink(
        newsHref(detail.published_at, detail.source_id),
        "Open in News →",
        "repo-action company-action",
      ),
    );
    wrapper.append(actions);
    return wrapper;
  }

  function detailFacts(items) {
    const usable = items.filter(
      (item) => clean(item.label) || clean(item.metric) || clean(item.value),
    );
    if (!usable.length) return null;

    const group = detailGroup("FACTS");
    const list = element("dl", "repo-fact-list");
    usable.slice(0, 8).forEach((fact) => {
      const row = element("div", "repo-fact");
      const label = element("dt", "", fact.label || fact.metric || "Fact");
      const value = element("dd", "", fact.value || "Not disclosed");
      if (clean(fact.previous_value)) {
        value.append(element("small", "", `Prev ${fact.previous_value}`));
      }
      row.append(label, value);
      list.append(row);
    });
    group.append(list);
    return group;
  }

  function detailChange(change) {
    const before = meaningfulChange(change.before);
    const today = meaningfulChange(change.today);
    if (!before && !today) return null;

    const group = detailGroup("CHANGE");
    const rows = element("div", "repo-change-list");
    if (before) rows.append(changeLine("Before", before));
    if (today) rows.append(changeLine("Now", today));
    group.append(rows);
    return group;
  }

  function detailWatch(research) {
    const values = (research.watch_items || []).map(clean).filter(Boolean);

    if (!values.length) {
      (research.guidance_events || []).forEach((item) => {
        if (values.length >= 3) return;
        const label = clean(item.metric);
        const value = clean(item.value);
        if (label || value) values.push(value ? `${label}: ${value}` : label);
      });
    }

    if (!values.length) return null;
    const group = detailGroup("WATCH");
    const list = element("ul", "repo-watch-list");
    values.slice(0, 3).forEach((value) => list.append(element("li", "", value)));
    group.append(list);
    return group;
  }

  function detailMissing(disclosure, provenance) {
    const values = [];
    (disclosure.missing_items || []).forEach((value) => {
      const item = clean(value);
      if (item) values.push(item);
    });
    if (clean(disclosure.management_language_mismatch)) {
      values.push(disclosure.management_language_mismatch);
    }
    (provenance.source_warnings || []).forEach((value) => {
      const item = clean(value);
      if (item) values.push(`Source check: ${item}`);
    });
    if (!values.length) return null;

    const strip = element("section", "repo-missing");
    strip.append(element("h4", "repo-label", "NOT DISCLOSED"));
    const list = element("ul", "");
    values.slice(0, 5).forEach((value) => list.append(element("li", "", value)));
    strip.append(list);
    return strip;
  }

  function detailGroup(label) {
    const group = element("section", "repo-detail-group");
    group.append(element("h4", "repo-label", label));
    return group;
  }

  function changeLine(label, value) {
    const row = element("div", "repo-change-line");
    row.append(element("span", "", label), element("p", "", value));
    return row;
  }

  async function activateRequestedAnnouncement(company) {
    const sourceId = clean(new URLSearchParams(window.location.search).get("open")).slice(0, 180);
    if (!sourceId) return;

    const target = [...document.querySelectorAll(".repo-news-item")]
      .find((item) => item.dataset.sourceId === sourceId);
    if (target instanceof HTMLDetailsElement) {
      target.hidden = false;
      target.open = true;
      const historyItem = (company.history || [])
        .find((item) => clean(item.source_id) === sourceId);
      const panel = target.querySelector(".repo-news-detail");
      if (historyItem && panel) await loadEventDetail(historyItem, panel);
      target.classList.add("repo-news-requested");
      target.scrollIntoView({
        block: "center",
        behavior: reducedMotion() ? "auto" : "smooth",
      });
      return;
    }

    const story = document.querySelector(`.repo-story[data-source-id="${cssEscape(sourceId)}"]`);
    if (story) {
      story.classList.add("repo-story-requested");
      story.scrollIntoView({
        block: "center",
        behavior: reducedMotion() ? "auto" : "smooth",
      });
    }
  }

  function sectionHead(title, meta) {
    const head = element("header", "repo-section-head");
    head.append(element("h2", "", title));
    if (clean(meta)) head.append(element("span", "", meta));
    return head;
  }

  function visuallyHiddenHeading(text) {
    return element("h2", "sr-only", text);
  }

  function emptyState(title, copy) {
    const block = element("div", "repo-empty");
    block.append(element("h3", "", title), element("p", "", copy));
    return block;
  }

  function inlineError(title, copy) {
    const block = element("div", "repo-inline-error");
    block.append(element("strong", "", title), element("p", "", copy));
    return block;
  }

  function loadingState(label) {
    const block = element("div", "repo-loading");
    block.setAttribute("role", "status");
    block.append(element("span"), element("span"), element("span"), element("p", "", label));
    return block;
  }

  function renderError(error) {
    const ticker = pathTicker() || "—";
    setText("company-ticker", ticker);
    setText("company-name", "Company unavailable");
    setText("company-market", "AIM");
    setText("company-coverage", "The company repository could not be loaded.");

    const content = document.getElementById("company-content");
    if (!content) return;

    const block = element("div", "repo-error");
    block.append(
      element("p", "eyebrow", "COMPANY"),
      element("h2", "", "This company is temporarily unavailable."),
      element("p", "", error?.message || "Please try again shortly."),
    );
    const retry = element("button", "repo-action repo-action-primary", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => window.location.reload());
    block.append(retry);
    content.replaceChildren(block);
  }

  function handleKeyboard(event) {
    if (event.key === "/" && !isTypingTarget(event.target)) {
      const search = document.querySelector("[data-company-search-input]");
      if (search instanceof HTMLInputElement) {
        event.preventDefault();
        search.focus();
        search.select();
      }
      return;
    }

    if (event.key !== "Escape") return;
    const open = [...document.querySelectorAll(".repo-news-item[open]")].at(-1);
    if (open instanceof HTMLDetailsElement) {
      open.open = false;
      open.querySelector("summary")?.focus();
    }
  }

  function signalBadge(signal, short) {
    const value = clean(signal).toUpperCase() || "NO COLOUR";
    const label = short
      ? SIGNAL_SHORT[value] || titleCase(value)
      : SIGNAL_LABELS[value] || titleCase(value);
    const badge = element(
      "span",
      `repo-signal repo-signal-${signalTone(value)}`,
      label,
    );
    badge.setAttribute(
      "aria-label",
      SIGNAL_LABELS[value] || titleCase(value),
    );
    return badge;
  }

  function metricMovement(item) {
    if (Number.isFinite(item.change_percent)) {
      const arrow = item.change_percent > 0 ? "↑" : item.change_percent < 0 ? "↓" : "→";
      return `${arrow}${Math.abs(item.change_percent).toFixed(1)}%`;
    }

    const direction = clean(item.change_direction).toLowerCase();
    if (direction === "up") return "↑";
    if (direction === "down") return "↓";
    if (direction === "flat") return "→";
    return "";
  }

  function marketShort(reaction) {
    if (Number.isFinite(reaction.change_pct)) return `${reaction.change_pct >= 0 ? "+" : ""}${reaction.change_pct.toFixed(1)}%`;
    return clipWords(reaction.label, 4);
  }

  function outlookShort(value) {
    const outlook = clean(value).toUpperCase();
    if (!outlook || outlook === "N/A") return "";
    if (outlook === "MAINTAINED") return "Guidance unchanged";
    if (outlook === "UPGRADED") return "Guidance ↑";
    if (outlook === "DOWNGRADED") return "Guidance ↓";
    if (outlook === "NEW GUIDANCE") return "New guidance";
    if (outlook === "MIXED") return "Guidance mixed";
    return titleCase(outlook);
  }

  function coverageText(coverage = {}) {
    const count = Math.max(0, Number(coverage.announcement_count || 0));
    const parts = [`${count} analysed`];
    const since = formatMonthYear(coverage.coverage_since);
    if (since) parts.push(`since ${since}`);
    if (coverage.status === "building") parts.push("history building");
    return parts.join(" · ");
  }

  function newsCountText(count, hasMore) {
    if (hasMore) return `${count}+ analysed`;
    return `${count} analysed`;
  }

  function meaningfulChange(value) {
    const text = clean(value);
    return GENERIC_CHANGE.has(text.toLowerCase()) ? "" : text;
  }

  function genericBalanceLabel(value) {
    const label = clean(value).toLowerCase();
    return !label || label === "balance sheet" || label === "balance-sheet position";
  }

  function firstDistinct(values, exclude) {
    const excluded = normaliseCompare(exclude);
    for (const value of values) {
      const text = clean(value);
      if (text && normaliseCompare(text) !== excluded) return text;
    }
    return "";
  }

  function normaliseCompare(value) {
    return clean(value).toLowerCase().replace(/[.!?]+$/g, "");
  }

  function clipWords(value, limit) {
    const text = clean(value);
    if (!text) return "";
    const words = text.split(" ");
    if (words.length <= limit) return text;
    return `${words.slice(0, limit).join(" ").replace(/[,:;.-]+$/g, "")}…`;
  }

  function metaSeparator() {
    return element("span", "repo-meta-separator", "·");
  }

  function statusLabel(value) {
    const text = clean(value).replace(/[-_]+/g, " ");
    return text ? titleCase(text) : "";
  }

  function formatDate(value) {
    const date = parseDate(value);
    if (!date) return clean(value);
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "Europe/London",
    }).format(date);
  }

  function formatShortDate(value) {
    const date = parseDate(value);
    if (!date) return clean(value);
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "2-digit",
      timeZone: "Europe/London",
    }).format(date);
  }

  function formatMonthYear(value) {
    const text = clean(value);
    if (!text) return "";
    const date = parseDate(text.length === 10 ? `${text}T12:00:00Z` : text);
    if (!date) return text;
    return new Intl.DateTimeFormat("en-GB", {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  }

  function newsHref(publishedAt, sourceId) {
    const date = parseDate(publishedAt);
    const dateValue = date
      ? new Intl.DateTimeFormat("en-CA", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          timeZone: "Europe/London",
        }).format(date)
      : "";
    const params = new URLSearchParams();
    if (dateValue) params.set("date", dateValue);
    if (clean(sourceId)) params.set("open", clean(sourceId));
    const query = params.toString();
    return query ? `/rns?${query}` : "/rns";
  }

  function sameOriginPath(value) {
    const text = clean(value);
    if (!text) return "";
    try {
      const origin = window.location.origin === "null"
        ? "https://smallcaps.local"
        : window.location.origin;
      const url = new URL(text, origin);
      if (url.origin !== origin || !["http:", "https:"].includes(url.protocol)) return "";
      return `${url.pathname}${url.search}`;
    } catch (_error) {
      return "";
    }
  }

  function safeExternalLink(value, label, className) {
    const text = clean(value);
    if (!text) return null;
    try {
      const origin = window.location.origin === "null"
        ? "https://smallcaps.local"
        : window.location.origin;
      const url = new URL(text, origin);
      if (!["http:", "https:"].includes(url.protocol)) return null;
      const link = internalLink(url.href, label, className);
      if (url.origin !== origin) {
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      return link;
    } catch (_error) {
      return null;
    }
  }

  function internalLink(href, label, className) {
    const link = element("a", className, label);
    link.href = href;
    return link;
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = clean(value);
  }

  function pathTicker() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    const index = parts.lastIndexOf("company");
    if (index < 0 || !parts[index + 1]) return "";
    return clean(decodeURIComponent(parts[index + 1]))
      .toUpperCase()
      .replace(/\.L$/, "")
      .replace(/[^A-Z0-9.-]/g, "")
      .slice(0, 20);
  }

  function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "") node.textContent = clean(text);
    return node;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }

  function titleCase(value) {
    return clean(value)
      .toLowerCase()
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function signalTone(value) {
    const signal = clean(value).toUpperCase();
    if (signal === "GREEN") return "positive";
    if (signal === "AMBER") return "mixed";
    if (signal === "RED") return "negative";
    return "neutral";
  }

  function clampImpact(value) {
    const score = Number.parseInt(value, 10);
    return Number.isFinite(score) ? Math.min(5, Math.max(1, score)) : 1;
  }

  function parseDate(value) {
    const text = clean(value);
    if (!text) return null;
    const date = new Date(text);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function reducedMotion() {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
  }

  function isTypingTarget(target) {
    return target instanceof HTMLInputElement
      || target instanceof HTMLTextAreaElement
      || target instanceof HTMLSelectElement
      || target?.isContentEditable === true;
  }

  function cssEscape(value) {
    if (window.CSS?.escape) return window.CSS.escape(value);
    return clean(value).replace(/["\\]/g, "\\$&");
  }
})();
