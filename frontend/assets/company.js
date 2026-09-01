(() => {
  "use strict";

  const COMPANY_SCHEMA = "scbb-company-v1";
  const MONITORING_SCHEMA = "scbb-monitoring-v1";
  const INITIAL_HISTORY_COUNT = 8;
  const IMPACT_NAMES = {
    1: "Low",
    2: "Low",
    3: "Medium",
    4: "High",
    5: "Critical",
  };
  const SIGNAL_LABELS = {
    GREEN: "Positive",
    AMBER: "Mixed",
    RED: "Negative",
    "NO COLOUR": "Neutral",
  };

  const state = {
    company: null,
    detailCache: new Map(),
    historyExpanded: false,
  };

  document.addEventListener("DOMContentLoaded", initialise);

  async function initialise() {
    syncWatchlistNavigation();
    const ticker = pathTicker();
    const tickerNode = document.getElementById("company-ticker");
    if (tickerNode) tickerNode.textContent = ticker || "—";

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
        throw new Error(payload?.error?.message || "Company Intelligence is unavailable.");
      }
      if (payload.schema_version !== COMPANY_SCHEMA) {
        throw new Error("The Company Intelligence data contract is incompatible.");
      }
      state.company = payload;
      renderCompany(payload);
      await activateRequestedEvidence(payload);
    } catch (error) {
      renderError(error);
    }
  }

  function renderCompany(company) {
    document.title = `${clean(company.ticker)} · Company Intelligence · Smallcaps.ai`;
    setText("company-ticker", company.ticker || pathTicker() || "—");
    setText("company-name", company.company || company.ticker || "Company");
    setText("company-market", identityMeta(company));
    setText("company-coverage", coverageText(company.coverage));

    const content = document.getElementById("company-content");
    if (!content) return;
    content.replaceChildren();

    const current = buildCurrentPosition(company.current_position);
    if (current) content.append(current);

    const matters = buildWhatMatters(company);
    if (matters) content.append(matters);

    content.append(buildEvidenceTrail(company));
  }

  function buildCurrentPosition(detail) {
    if (!detail) {
      return section(
        "Current position",
        "The latest decision-useful company view will appear here once a material announcement has been analysed.",
        emptyState(
          "No current position yet",
          "Company coverage is active, but no publishable material announcement is available for this record.",
        ),
        "current-position",
      );
    }

    const card = element("article", `company-position-card tone-${signalTone(detail.signal)}`);
    card.dataset.sourceId = clean(detail.source_id);

    const narrative = element("div", "company-position-narrative");
    const meta = element("div", "company-position-meta");
    meta.append(
      signalBadge(detail.signal),
      element("span", "company-meta-separator", "·"),
      element("span", "", formatDateTime(detail.published_at)),
    );
    if (clean(detail.rns_type)) {
      meta.append(
        element("span", "company-meta-separator", "·"),
        element("span", "", detail.rns_type),
      );
    }

    const headline = element(
      "h3",
      "company-position-headline",
      detail.research?.verdict || detail.rns_title || detail.what_changed || "Latest company update",
    );

    const change = labelledCopy(
      "What changed",
      detail.research?.what_changed?.today || detail.what_changed,
      "company-change-copy",
    );
    const view = labelledCopy(
      "Smallcaps.ai view",
      detail.research?.analyst_view || detail.ai_view,
      "company-view-copy",
    );

    const actions = element("div", "company-actions");
    const source = safeExternalLink(
      detail.original_source_url,
      "Source RNS ↗",
      "company-action company-action-primary",
    );
    if (source) actions.append(source);
    actions.append(
      internalLink(
        newsHref(detail.published_at, detail.source_id),
        "Open in News →",
        "company-action",
      ),
    );

    narrative.append(meta, headline);
    if (change) narrative.append(change);
    if (view) narrative.append(view);
    narrative.append(actions);

    const snapshot = element("aside", "company-position-snapshot", "");
    snapshot.setAttribute("aria-label", "Current company snapshot");
    snapshot.append(
      snapshotItem(
        "Guidance",
        outlookLabel(detail.outlook),
        "Latest disclosed outlook",
        `outlook-${slug(detail.outlook || "na")}`,
      ),
      snapshotItem(
        "Balance sheet",
        detail.balance_sheet?.value || "Not disclosed",
        balanceMeta(detail.balance_sheet),
      ),
      snapshotItem(
        "Market reaction",
        detail.market_reaction?.label || "Pricing pending",
        marketMeta(detail.market_reaction),
      ),
      snapshotItem(
        "Materiality",
        `${clampImpact(detail.impact?.score)}/5`,
        `${titleCase(detail.impact?.level || IMPACT_NAMES[clampImpact(detail.impact?.score)])} impact`,
      ),
    );

    const main = element("div", "company-position-main");
    main.append(narrative, snapshot);
    card.append(main);

    const evidence = evidenceDisclosure(detail, "Show supporting evidence");
    evidence.classList.add("company-current-evidence");
    card.append(evidence);

    return section(
      "Current position",
      "The latest material change, the investor read-through and the reported evidence behind it.",
      card,
      "current-position",
    );
  }

  function buildWhatMatters(company) {
    const cards = [];

    const guidance = (company.guidance || []).slice(0, 5).map(guidanceRow);
    if (guidance.length) {
      cards.push(matterCard(
        "guidance",
        "Guidance",
        "The latest forward-looking statements management has put on record.",
        guidance,
      ));
    }

    const metrics = (company.metrics || []).slice(0, 6).map(metricRow);
    if (metrics.length) {
      cards.push(matterCard(
        "metrics",
        "Metrics that matter",
        "Comparable reported or calculated company measures, with provenance.",
        metrics,
      ));
    }

    const commitments = (company.open_management_claims || []).slice(0, 5).map(claimRow);
    if (commitments.length) {
      cards.push(matterCard(
        "commitments",
        "Management commitments",
        "Open promises and targets that future announcements can confirm or break.",
        commitments,
      ));
    }

    const gaps = (company.disclosure_gaps || []).slice(0, 5).map(gapRow);
    if (gaps.length) {
      cards.push(matterCard(
        "open-questions",
        "Open questions",
        "Decision-useful information the published record still does not answer.",
        gaps,
      ));
    }

    if (!cards.length) return null;
    const grid = element("div", "company-matters-grid");
    cards.forEach((card) => grid.append(card));
    return section(
      "What matters now",
      "The live monitoring sheet: guidance, key metrics, management commitments and unresolved questions.",
      grid,
      "what-matters",
    );
  }

  function buildEvidenceTrail(company) {
    const history = Array.isArray(company.history) ? company.history : [];
    const body = element("div", "company-evidence-trail");

    if (!history.length) {
      body.append(
        emptyState(
          "No evidence trail yet",
          "Analysed company announcements will appear here in chronological order.",
        ),
      );
    } else {
      history.forEach((item, index) => {
        const event = historyEvent(item, index === 0);
        if (index >= INITIAL_HISTORY_COUNT) event.hidden = true;
        body.append(event);
      });

      if (history.length > INITIAL_HISTORY_COUNT) {
        const more = element(
          "button",
          "company-more-button",
          `Show ${history.length - INITIAL_HISTORY_COUNT} older announcement${history.length - INITIAL_HISTORY_COUNT === 1 ? "" : "s"}`,
        );
        more.type = "button";
        more.addEventListener("click", () => {
          state.historyExpanded = !state.historyExpanded;
          body.querySelectorAll(".company-event").forEach((event, index) => {
            event.hidden = !state.historyExpanded && index >= INITIAL_HISTORY_COUNT;
          });
          more.textContent = state.historyExpanded
            ? "Show latest announcements only"
            : `Show ${history.length - INITIAL_HISTORY_COUNT} older announcement${history.length - INITIAL_HISTORY_COUNT === 1 ? "" : "s"}`;
          more.setAttribute("aria-expanded", String(state.historyExpanded));
        });
        more.setAttribute("aria-expanded", "false");
        body.append(more);
      }

      if (company.has_more_history) {
        const note = element(
          "p",
          "company-history-note",
          "This compact record shows the latest covered announcements. Use Company News for the wider archive.",
        );
        note.append(
          document.createTextNode(" "),
          internalLink("/rns", "Open Company News →", "company-inline-link"),
        );
        body.append(note);
      }
    }

    return section(
      "Evidence trail",
      "Every analysed company announcement in this record, newest first, with the source and supporting research one step away.",
      body,
      "evidence-trail",
    );
  }

  function historyEvent(item, latest) {
    const article = element("article", `company-event tone-${signalTone(item.signal)}`);
    article.dataset.sourceId = clean(item.source_id);

    const top = element("div", "company-event-top");
    const meta = element("div", "company-event-meta");
    meta.append(element("time", "", formatDate(item.published_at)));
    if (clean(item.rns_type)) {
      meta.append(element("span", "company-meta-separator", "·"), element("span", "", item.rns_type));
    }
    if (latest) meta.append(element("span", "company-latest-label", "Latest"));
    top.append(meta, signalBadge(item.signal));

    const headline = element("h3", "company-event-headline", item.headline || item.rns_type || "Company announcement");
    const takeaway = clean(item.takeaway)
      ? element("p", "company-event-takeaway", item.takeaway)
      : null;

    const foot = element("div", "company-event-foot");
    const facts = element("div", "company-event-facts");
    facts.append(
      compactFact(
        "Market",
        item.market_reaction?.label || "Pricing pending",
      ),
      compactFact(
        "Materiality",
        `${clampImpact(item.impact?.score)}/5 · ${titleCase(item.impact?.level || IMPACT_NAMES[clampImpact(item.impact?.score)])}`,
      ),
    );

    const actions = element("div", "company-event-actions");
    actions.append(
      internalLink(
        newsHref(item.published_at, item.source_id),
        "Open in News →",
        "company-event-link",
      ),
    );
    const source = safeExternalLink(item.original_source_url, "Source ↗", "company-event-link");
    if (source) actions.append(source);
    foot.append(facts, actions);

    const details = element("details", "company-event-evidence");
    const summary = element("summary", "", "Show evidence");
    const panel = element("div", "company-event-evidence-body");
    details.append(summary, panel);
    details.addEventListener("toggle", () => {
      summary.textContent = details.open ? "Hide evidence" : "Show evidence";
      if (details.open) loadEventEvidence(item, panel);
    });

    article.append(top, headline);
    if (takeaway) article.append(takeaway);
    article.append(foot, details);
    return article;
  }

  async function loadEventEvidence(item, panel) {
    if (panel.dataset.loaded === "true" || panel.dataset.loading === "true") return;
    panel.dataset.loading = "true";

    if (state.detailCache.has(item.source_id)) {
      panel.replaceChildren(renderEvidence(state.detailCache.get(item.source_id)));
      panel.dataset.loaded = "true";
      panel.dataset.loading = "false";
      return;
    }

    panel.replaceChildren(loadingState("Loading supporting research…"));
    try {
      const detailUrl = sameOriginPath(item.detail_url);
      if (!detailUrl) throw new Error("The supporting research link is invalid.");
      const response = await fetch(detailUrl, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.error?.message || "Supporting research is unavailable.");
      }
      if (payload.schema_version !== MONITORING_SCHEMA) {
        throw new Error("The supporting research data contract is incompatible.");
      }
      state.detailCache.set(item.source_id, payload);
      panel.replaceChildren(renderEvidence(payload));
      panel.dataset.loaded = "true";
    } catch (error) {
      panel.replaceChildren(
        inlineError(
          "Supporting research is temporarily unavailable.",
          error?.message || "Please try again shortly.",
        ),
      );
    } finally {
      panel.dataset.loading = "false";
    }
  }

  function evidenceDisclosure(detail, label) {
    const details = element("details", "company-evidence-disclosure");
    const summary = element("summary", "", label);
    const body = element("div", "company-evidence-body");
    body.append(renderEvidence(detail));
    details.append(summary, body);
    details.addEventListener("toggle", () => {
      summary.textContent = details.open ? "Hide supporting evidence" : label;
    });
    return details;
  }

  function renderEvidence(detail) {
    const research = detail?.research || {};
    const grid = element("div", "company-evidence-grid");

    const facts = evidenceFacts(research.evidence || []);
    if (facts) grid.append(facts);

    const changed = evidenceChange(research.what_changed || {});
    if (changed) grid.append(changed);

    const gaps = evidenceGaps(research.disclosure || {}, research.provenance || {});
    if (gaps) grid.append(gaps);

    if (!grid.childElementCount) {
      return inlineError(
        "No structured evidence is available.",
        "Use the source RNS to verify the underlying announcement.",
      );
    }
    return grid;
  }

  function evidenceFacts(items) {
    const usable = items.filter((item) => clean(item.label) || clean(item.metric) || clean(item.value));
    if (!usable.length) return null;
    const group = evidenceGroup("Reported facts", "Numbers and statements extracted from the announcement.");
    const list = element("div", "company-fact-list");
    usable.slice(0, 6).forEach((fact) => {
      const row = element("div", "company-fact-row");
      const copy = element("div");
      copy.append(
        element("span", "company-fact-label", fact.label || fact.metric || "Fact"),
        element("strong", "company-fact-value", fact.value || "Not disclosed"),
      );
      const notes = [];
      if (clean(fact.previous_value)) notes.push(`Previously ${fact.previous_value}`);
      if (clean(fact.period)) notes.push(fact.period);
      if (clean(fact.basis) && clean(fact.basis).toLowerCase() !== "reported") {
        notes.push(titleCase(fact.basis));
      }
      if (notes.length) copy.append(element("small", "", notes.join(" · ")));
      row.append(copy);
      list.append(row);
    });
    group.append(list);
    return group;
  }

  function evidenceChange(change) {
    const before = clean(change.before);
    const today = clean(change.today);
    if (!before && !today) return null;
    const group = evidenceGroup("Before → now", "The explicit movement in the covered company record.");
    const list = element("div", "company-change-list");
    if (before) list.append(changeRow("Before", before));
    if (today) list.append(changeRow("Now", today));
    group.append(list);
    return group;
  }

  function evidenceGaps(disclosure, provenance) {
    const values = [];
    (disclosure.missing_items || []).forEach((item) => {
      const value = clean(item);
      if (value) values.push(`Not disclosed: ${value}`);
    });
    if (clean(disclosure.management_language_mismatch)) {
      values.push(disclosure.management_language_mismatch);
    }
    (provenance.source_warnings || []).forEach((item) => {
      const value = clean(item);
      if (value) values.push(`Source check: ${value}`);
    });
    if (!values.length && clean(disclosure.note)) values.push(disclosure.note);
    if (!values.length) return null;

    const group = evidenceGroup("Not disclosed / source checks", "Limits in the announcement or source material.");
    const list = element("ul", "company-evidence-list");
    values.slice(0, 6).forEach((value) => list.append(element("li", "", value)));
    group.append(list);
    return group;
  }

  function guidanceRow(item) {
    const row = element("div", "company-matter-row");
    const copy = element("div", "company-matter-copy");
    copy.append(
      element("span", "company-matter-label", item.metric || "Guidance"),
      element("strong", "company-matter-value", item.value || "No value disclosed"),
    );
    const meta = [item.period, statusLabel(item.status), item.previous_value ? `Previously ${item.previous_value}` : ""]
      .map(clean)
      .filter(Boolean);
    if (meta.length) copy.append(element("small", "", meta.join(" · ")));
    row.append(copy, provenanceLink(item));
    return row;
  }

  function metricRow(item) {
    const row = element("div", "company-matter-row");
    const copy = element("div", "company-matter-copy");
    copy.append(
      element("span", "company-matter-label", item.label || item.metric || "Metric"),
      element("strong", "company-matter-value company-matter-number", item.latest_value || "Not disclosed"),
    );
    const meta = [];
    if (clean(item.previous_value)) meta.push(`Previously ${item.previous_value}`);
    const movement = metricMovement(item);
    if (movement) meta.push(movement);
    if (clean(item.period_family)) meta.push(item.period_family);
    if (meta.length) copy.append(element("small", "", meta.join(" · ")));
    row.append(copy, provenanceLink((item.points || [])[0] || {}));
    return row;
  }

  function claimRow(item) {
    const row = element("div", "company-matter-row");
    const copy = element("div", "company-matter-copy");
    copy.append(
      element("span", "company-matter-label", statusLabel(item.status) || "Open commitment"),
      element("strong", "company-matter-value company-matter-prose", item.claim || "Management commitment"),
    );
    const meta = [];
    if (clean(item.target_value)) meta.push(`Target ${item.target_value}`);
    if (clean(item.target_date)) meta.push(`Due ${item.target_date}`);
    if (meta.length) copy.append(element("small", "", meta.join(" · ")));
    row.append(copy, provenanceLink(item));
    return row;
  }

  function gapRow(item) {
    const row = element("div", "company-matter-row");
    const copy = element("div", "company-matter-copy");
    copy.append(
      element("span", "company-matter-label", "Unresolved"),
      element("strong", "company-matter-value company-matter-prose", item.item || "Information not disclosed"),
    );
    const sourceDate = formatDate(item.published_at);
    if (sourceDate) copy.append(element("small", "", `Raised from ${sourceDate}`));
    row.append(copy, provenanceLink(item, "Relevant source ↗"));
    return row;
  }

  function matterCard(key, title, copy, rows) {
    const card = element("article", "company-matter-card");
    card.dataset.matterCard = key;
    const head = element("header", "company-matter-head");
    head.append(element("h3", "", title), element("p", "", copy));
    const list = element("div", "company-matter-list");
    rows.forEach((row) => list.append(row));
    card.append(head, list);
    return card;
  }

  function provenanceLink(item, label = "Source ↗") {
    const container = element("div", "company-matter-source");
    const link = safeExternalLink(item?.source_url, label, "company-inline-link");
    if (link) container.append(link);
    return container;
  }

  function snapshotItem(label, value, note, modifier = "") {
    const item = element("div", `company-snapshot-item ${modifier}`.trim());
    item.append(
      element("span", "company-snapshot-label", label),
      element("strong", "company-snapshot-value", clean(value) || "Not disclosed"),
    );
    if (clean(note)) item.append(element("small", "", note));
    return item;
  }

  function compactFact(label, value) {
    const item = element("span", "company-event-fact");
    item.append(element("b", "", label), document.createTextNode(` ${clean(value) || "—"}`));
    return item;
  }

  function signalBadge(signal) {
    const value = clean(signal).toUpperCase() || "NO COLOUR";
    return element(
      "span",
      `company-signal company-signal-${signalTone(value)}`,
      SIGNAL_LABELS[value] || titleCase(value),
    );
  }

  function labelledCopy(label, value, className) {
    const copy = clean(value);
    if (!copy) return null;
    const block = element("div", className);
    block.append(element("span", "company-copy-label", label), element("p", "", copy));
    return block;
  }

  function evidenceGroup(title, copy) {
    const group = element("section", "company-evidence-group");
    const head = element("header", "company-evidence-group-head");
    head.append(element("h4", "", title));
    if (copy) head.append(element("p", "", copy));
    group.append(head);
    return group;
  }

  function changeRow(label, value) {
    const row = element("div", "company-change-row");
    row.append(element("span", "", label), element("p", "", value));
    return row;
  }

  function section(title, description, body, key) {
    const block = element("section", "company-section");
    block.dataset.companySection = key;
    const head = element("header", "company-section-head");
    const copy = element("div");
    copy.append(element("h2", "", title));
    if (description) copy.append(element("p", "", description));
    head.append(copy);
    block.append(head, body);
    return block;
  }

  function emptyState(title, copy) {
    const block = element("div", "company-empty");
    block.append(element("h3", "", title), element("p", "", copy));
    return block;
  }

  function inlineError(title, copy) {
    const block = element("div", "company-inline-error");
    block.append(element("strong", "", title), element("p", "", copy));
    return block;
  }

  function loadingState(label) {
    const block = element("div", "company-inline-loading");
    block.setAttribute("role", "status");
    block.append(element("span"), element("span"), element("span"), element("p", "", label));
    return block;
  }

  function renderError(error) {
    const ticker = pathTicker() || "—";
    setText("company-ticker", ticker);
    setText("company-name", "Company Intelligence unavailable");
    setText("company-market", "AIM");
    setText("company-coverage", "The company record could not be loaded.");

    const content = document.getElementById("company-content");
    if (!content) return;
    const block = element("div", "company-error");
    block.append(
      element("p", "eyebrow", "Company Intelligence"),
      element("h2", "", "This company record is temporarily unavailable."),
      element("p", "", error?.message || "Please try again shortly."),
    );
    const retry = element("button", "company-action company-action-primary", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => window.location.reload());
    block.append(retry);
    content.replaceChildren(block);
  }

  async function activateRequestedEvidence(company) {
    const sourceId = clean(new URLSearchParams(window.location.search).get("open"));
    if (!sourceId) return;

    if (clean(company.current_position?.source_id) === sourceId) {
      const current = document.querySelector(".company-current-evidence");
      if (current instanceof HTMLDetailsElement) {
        current.open = true;
        current.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
        return;
      }
    }

    const event = Array.from(document.querySelectorAll(".company-event"))
      .find((node) => node.dataset.sourceId === sourceId);
    if (!event) return;
    event.hidden = false;
    const details = event.querySelector(".company-event-evidence");
    if (details instanceof HTMLDetailsElement) {
      details.open = true;
      const item = (company.history || []).find((candidate) => clean(candidate.source_id) === sourceId);
      const panel = details.querySelector(".company-event-evidence-body");
      if (item && panel) await loadEventEvidence(item, panel);
    }
    event.classList.add("company-event-requested");
    event.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
  }

  function syncWatchlistNavigation() {
    const store = window.SmallcapsWatchlist;
    const count = document.getElementById("watchlist-nav-count");
    const link = document.getElementById("watchlist-nav-link");
    if (!store || !count || !link) return;

    const sync = (tickers = store.read()) => {
      const total = Array.isArray(tickers) ? tickers.length : 0;
      count.textContent = String(total);
      count.hidden = total === 0;
      link.setAttribute("aria-label", total ? `Watchlist, ${total} companies` : "Watchlist");
    };
    window.addEventListener(store.changeEvent, (event) => {
      sync(Array.isArray(event.detail?.tickers) ? event.detail.tickers : store.read());
    });
    sync();
  }

  function identityMeta(company) {
    const parts = [clean(company.market) || "AIM"];
    if (clean(company.isin)) parts.push(`ISIN ${clean(company.isin)}`);
    return parts.join(" · ");
  }

  function coverageText(coverage = {}) {
    const count = Number(coverage.announcement_count || 0);
    const parts = [];
    const since = formatCoverageDate(coverage.coverage_since);
    if (since) parts.push(`Coverage since ${since}`);
    parts.push(`${count} analysed announcement${count === 1 ? "" : "s"}`);
    if (coverage.status === "building") parts.push("history still building");
    return parts.join(" · ");
  }

  function balanceMeta(balance = {}) {
    const parts = [];
    if (balance.status === "carried") parts.push("Carried from an earlier RNS");
    else if (balance.status === "current") parts.push("Reported in the latest RNS");
    else parts.push("No balance-sheet figure disclosed");
    const date = clean(balance.as_of_date) || clean(balance.period) || formatDate(balance.source_published_at);
    if (date) parts.push(date);
    return parts.join(" · ");
  }

  function marketMeta(reaction = {}) {
    if (reaction.status !== "available") return "Pricing pending";
    const parts = [];
    if (clean(reaction.phase)) parts.push(titleCase(reaction.phase));
    if (clean(reaction.reaction_session)) parts.push(reaction.reaction_session);
    return parts.join(" · ") || "Observed market move";
  }

  function metricMovement(item) {
    if (Number.isFinite(item.change_percent)) {
      const direction = item.change_percent > 0 ? "Up" : item.change_percent < 0 ? "Down" : "Flat";
      return `${direction} ${Math.abs(item.change_percent).toFixed(1)}%`;
    }
    const direction = clean(item.change_direction).toLowerCase();
    if (["up", "down", "flat"].includes(direction)) return titleCase(direction);
    return "";
  }

  function outlookLabel(value) {
    const cleanValue = clean(value).toUpperCase();
    if (!cleanValue || cleanValue === "N/A") return "No guidance event";
    return titleCase(cleanValue);
  }

  function statusLabel(value) {
    const cleanValue = clean(value).replace(/[-_]+/g, " ");
    return cleanValue ? titleCase(cleanValue) : "";
  }

  function formatDate(value) {
    const date = parseDate(value);
    if (!date) return "";
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "Europe/London",
    }).format(date);
  }

  function formatDateTime(value) {
    const date = parseDate(value);
    if (!date) return clean(value);
    const day = formatDate(value);
    const time = new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Europe/London",
    }).format(date);
    return `${day} · ${time}`;
  }

  function formatCoverageDate(value) {
    const cleanValue = clean(value);
    if (!cleanValue) return "";
    const date = parseDate(cleanValue.length === 10 ? `${cleanValue}T12:00:00Z` : cleanValue);
    if (!date) return cleanValue;
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
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
    const cleanValue = clean(value);
    if (!cleanValue) return "";
    try {
      const origin = window.location.origin === "null" ? "https://smallcaps.local" : window.location.origin;
      const url = new URL(cleanValue, origin);
      if (url.origin !== origin) return "";
      if (!["http:", "https:"].includes(url.protocol)) return "";
      return `${url.pathname}${url.search}`;
    } catch (_error) {
      return "";
    }
  }

  function safeExternalLink(value, label, className) {
    const cleanValue = clean(value);
    if (!cleanValue) return null;
    try {
      const origin = window.location.origin === "null" ? "https://smallcaps.local" : window.location.origin;
      const url = new URL(cleanValue, origin);
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
    const companyIndex = parts.lastIndexOf("company");
    if (companyIndex < 0 || !parts[companyIndex + 1]) return "";
    return clean(decodeURIComponent(parts[companyIndex + 1]))
      .toUpperCase()
      .replace(/\.L$/, "")
      .replace(/[^A-Z0-9.-]/g, "")
      .slice(0, 24);
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

  function slug(value) {
    return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
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
    const cleanValue = clean(value);
    if (!cleanValue) return null;
    const date = new Date(cleanValue);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function reducedMotion() {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
  }
})();
