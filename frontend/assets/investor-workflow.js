(() => {
  "use strict";

  const MONTHS = Object.freeze({
    january: "01",
    february: "02",
    march: "03",
    april: "04",
    may: "05",
    june: "06",
    july: "07",
    august: "08",
    september: "09",
    october: "10",
    november: "11",
    december: "12",
  });

  document.addEventListener("DOMContentLoaded", initialise);

  function initialise() {
    if (!document.body?.classList.contains("product-page")) return;

    if (document.body.classList.contains("company-news-page")) {
      initialiseNewsWorkflow(isWatchlist());
      return;
    }
    if (document.body.classList.contains("company-intelligence-page")) {
      initialiseCompanyWorkflow();
      return;
    }
    if (document.body.classList.contains("daily-body")) {
      initialiseDailyWorkflow();
    }
  }

  function initialiseNewsWorkflow(watchlist) {
    const rows = document.getElementById("sheet-rows");
    if (!rows) return;

    const refresh = scheduled(() => {
      decorateNewsRows();
      if (watchlist) renderWatchlistAttention();
    });

    new MutationObserver(refresh).observe(rows, { childList: true, subtree: true });
    document.addEventListener("change", (event) => {
      if (event.target instanceof HTMLSelectElement && event.target.closest(".filter-panel")) {
        refresh();
      }
    });

    const changeEvent = window.SmallcapsWatchlist?.changeEvent;
    if (changeEvent) window.addEventListener(changeEvent, refresh);
    refresh();
  }

  function decorateNewsRows() {
    document.querySelectorAll("article.monitor-row").forEach((row) => {
      const priority = rowPriority(row);
      const current = row.dataset.investorPriority || "";
      const next = priority?.key || "";
      if (current !== next) row.dataset.investorPriority = next;

      const meta = row.querySelector(".news-meta");
      if (!meta) return;
      let marker = meta.querySelector(".investor-marker");

      if (!priority) {
        marker?.remove();
        return;
      }

      if (!marker) {
        marker = element("span", "investor-marker");
        const impact = meta.querySelector(".impact-scale");
        if (impact) impact.after(marker);
        else meta.prepend(marker);
      }

      const className = `investor-marker investor-marker-${priority.tone}`;
      if (marker.className !== className) marker.className = className;
      if (marker.textContent !== priority.label) marker.textContent = priority.label;
      marker.setAttribute(
        "aria-label",
        `${priority.label.toLowerCase()} based on ${priority.signalLabel} signal and materiality ${priority.impact} out of 5`,
      );
    });
  }

  function renderWatchlistAttention() {
    const summary = document.querySelector(".feed-summary");
    const sheet = document.querySelector(".monitoring-sheet");
    if (!summary || !sheet) return;

    let panel = document.getElementById("investor-attention");
    if (!panel) {
      panel = element("section", "investor-attention");
      panel.id = "investor-attention";
      panel.setAttribute("aria-labelledby", "investor-attention-title");
      summary.after(panel);
    }

    const rows = [...document.querySelectorAll("article.monitor-row")]
      .filter((row) => !row.hidden);
    const review = rows
      .map((row) => ({ row, priority: rowPriority(row) }))
      .filter(({ priority }) => priority?.attention)
      .sort(comparePriority);
    const materialPositive = rows.filter((row) => {
      const priority = rowPriority(row);
      return priority?.key === "material-positive";
    });
    const pricePending = rows.filter((row) =>
      clean(row.querySelector(".price-line")?.textContent).includes("PRICE PENDING"),
    );

    const signature = JSON.stringify({
      rows: rows.map((row) => [
        row.dataset.sourceId || "",
        clean(row.querySelector(".news-headline")?.textContent),
      ]),
      review: review.map(({ row }) => row.dataset.sourceId || ""),
      positive: materialPositive.map((row) => row.dataset.sourceId || ""),
      pending: pricePending.map((row) => row.dataset.sourceId || ""),
      sort: document.getElementById("sort-filter")?.value || "",
    });
    if (panel.dataset.signature === signature) return;
    panel.dataset.signature = signature;

    const copy = element("div", "investor-attention-copy");
    const title = element("h2", "", "What needs attention.");
    title.id = "investor-attention-title";
    copy.append(
      element("p", "investor-eyebrow", "WATCHLIST ATTENTION"),
      title,
      element(
        "p",
        "investor-attention-intro",
        "Latest visible updates, prioritised by signal and materiality.",
      ),
    );

    const sort = document.getElementById("sort-filter");
    const sortButton = element(
      "button",
      "investor-sort-button",
      sort?.value === "impact" ? "Return to newest first" : "Sort highest materiality",
    );
    sortButton.type = "button";
    sortButton.addEventListener("click", () => {
      if (!sort) return;
      sort.value = sort.value === "impact" ? "latest" : "impact";
      sort.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const head = element("div", "investor-attention-head");
    head.append(copy, sortButton);

    const stats = element("div", "investor-attention-stats");
    stats.append(
      attentionStat("Needs review", review.length, review[0]?.row, "negative"),
      attentionStat("Material positive", materialPositive.length, materialPositive[0], "positive"),
      attentionStat("Price pending", pricePending.length, pricePending[0], "neutral"),
    );

    const stories = element("div", "investor-attention-stories");
    if (review.length) {
      stories.append(element("p", "investor-attention-label", "REVIEW FIRST"));
      review.slice(0, 3).forEach(({ row, priority }) => {
        stories.append(attentionStory(row, priority));
      });
    } else {
      stories.append(
        element(
          "p",
          "investor-attention-clear",
          rows.length
            ? "No latest visible update meets the review threshold."
            : "Watchlist updates will appear here once the feed is ready.",
        ),
      );
    }

    panel.replaceChildren(head, stats, stories);
  }

  function attentionStat(label, count, row, tone) {
    const node = row
      ? element("button", `investor-attention-stat tone-${tone}`)
      : element("div", `investor-attention-stat tone-${tone}`);
    if (node instanceof HTMLButtonElement) {
      node.type = "button";
      node.addEventListener("click", () => revealRow(row));
      node.setAttribute("aria-label", `${label}: ${count}. Open the first matching update.`);
    }
    node.append(
      element("strong", "", String(count)),
      element("span", "", label),
      element("small", "", "On this page"),
    );
    return node;
  }

  function attentionStory(row, priority) {
    const button = element("button", "investor-attention-story");
    button.type = "button";
    button.addEventListener("click", () => revealRow(row));

    const top = element("span", "investor-attention-story-top");
    top.append(
      element("b", "", clean(row.querySelector(".ticker")?.textContent) || "AIM"),
      element("span", `investor-story-signal tone-${priority.tone}`, priority.label),
      element("span", "", `${priority.impact}/5`),
    );
    button.append(
      top,
      element(
        "strong",
        "investor-attention-story-title",
        clean(row.querySelector(".news-headline")?.textContent) || "Company update",
      ),
    );
    return button;
  }

  function revealRow(row) {
    if (!(row instanceof HTMLElement)) return;
    const toggle = row.querySelector("button.row-toggle");
    if (toggle?.getAttribute("aria-expanded") !== "true") toggle?.click();
    row.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
    window.setTimeout(() => toggle?.focus({ preventScroll: true }), reducedMotion() ? 0 : 280);
  }

  function initialiseCompanyWorkflow() {
    const content = document.getElementById("company-content");
    if (!content) return;
    const refresh = scheduled(renderNextChecks);
    new MutationObserver(refresh).observe(content, { childList: true, subtree: true });
    refresh();
  }

  function renderNextChecks() {
    const content = document.getElementById("company-content");
    const current = content?.querySelector('[data-company-section="current-position"]');
    const matters = content?.querySelector('[data-company-section="what-matters"]');
    if (!content || !current || !matters) return;

    const candidates = [
      nextCheck("Open question", "open-questions", "review"),
      nextCheck("Management commitment", "commitments", "commitment"),
      nextCheck("Guidance", "guidance", "guidance"),
    ].filter(Boolean);

    let section = document.getElementById("company-next-checks");
    if (!candidates.length) {
      section?.remove();
      return;
    }

    const signature = JSON.stringify(candidates.map(({ type, value, meta }) => [type, value, meta]));
    if (section?.dataset.signature === signature) return;

    if (!section) {
      section = element("section", "company-section investor-next-checks");
      section.id = "company-next-checks";
      section.dataset.companySection = "next-checks";
      current.after(section);
    }
    section.dataset.signature = signature;

    const head = element("header", "company-section-head");
    const heading = element("div");
    heading.append(
      element("h2", "", "Next checks"),
      element(
        "p",
        "",
        "The recorded items most likely to update the current company view.",
      ),
    );
    head.append(heading);

    const grid = element("div", "investor-check-grid");
    candidates.forEach((candidate) => {
      const link = element("a", `investor-check investor-check-${candidate.tone}`);
      link.href = `#${candidate.targetId}`;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        const target = document.getElementById(candidate.targetId);
        target?.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
        window.setTimeout(() => {
          target?.setAttribute("tabindex", "-1");
          target?.focus({ preventScroll: true });
        }, reducedMotion() ? 0 : 280);
      });
      link.append(
        element("span", "investor-check-type", candidate.type),
        element("strong", "investor-check-value", candidate.value),
      );
      if (candidate.meta) link.append(element("small", "", candidate.meta));
      link.append(element("span", "investor-check-action", "VIEW EVIDENCE →"));
      grid.append(link);
    });

    section.replaceChildren(head, grid);
  }

  function nextCheck(type, key, tone) {
    const card = document.querySelector(`[data-matter-card="${key}"]`);
    const row = card?.querySelector(".company-matter-row");
    const value = clean(row?.querySelector(".company-matter-value")?.textContent);
    if (!card || !row || !value) return null;

    const targetId = `company-matter-${key}`;
    if (card.id !== targetId) card.id = targetId;
    return {
      type,
      value,
      meta: clean(row.querySelector("small")?.textContent),
      tone,
      targetId,
    };
  }

  function initialiseDailyWorkflow() {
    const masthead = document.querySelector(".daily-masthead");
    const date = document.getElementById("edition-date");
    if (!masthead || !date) return;

    const refresh = scheduled(renderDailyFollowThrough);
    new MutationObserver(refresh).observe(date, { childList: true, characterData: true, subtree: true });
    refresh();
  }

  function renderDailyFollowThrough() {
    const masthead = document.querySelector(".daily-masthead");
    const summary = masthead?.querySelector(".daily-summary-strip");
    if (!masthead || !summary) return;

    let follow = document.getElementById("daily-follow-through");
    if (!follow) {
      follow = element("nav", "daily-follow-through");
      follow.id = "daily-follow-through";
      follow.setAttribute("aria-label", "Follow through from The AIM Daily");
      summary.after(follow);
    }

    const marketDate = resolveDailyDate();
    const newsHref = marketDate ? `/rns?date=${encodeURIComponent(marketDate)}` : "/rns";
    const signature = newsHref;
    if (follow.dataset.signature === signature) return;
    follow.dataset.signature = signature;

    follow.replaceChildren(
      element("span", "daily-follow-label", "FOLLOW THROUGH"),
      internalLink(newsHref, "Open this market day in Company News →", "daily-follow-link"),
      internalLink("/rns?watchlist=1", "Review Watchlist →", "daily-follow-link"),
    );
  }

  function resolveDailyDate() {
    const requested = clean(new URLSearchParams(window.location.search).get("date"));
    if (validIsoDate(requested)) return requested;

    const text = clean(document.getElementById("edition-date")?.textContent).toLowerCase();
    const match = text.match(/(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)?[,]?\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})/i);
    if (!match) return "";
    const month = MONTHS[match[2].toLowerCase()];
    if (!month) return "";
    const value = `${match[3]}-${month}-${String(Number(match[1])).padStart(2, "0")}`;
    return validIsoDate(value) ? value : "";
  }

  function rowPriority(row) {
    const signal = clean(row.dataset.signal).toUpperCase();
    const impactText = row.querySelector(".impact-scale")?.getAttribute("aria-label") || "";
    const impact = Number(impactText.match(/materiality\s+(\d)/i)?.[1] || 0);
    const signalLabel = signal === "RED"
      ? "negative"
      : signal === "AMBER"
        ? "mixed"
        : signal === "GREEN"
          ? "positive"
          : "neutral";

    if (signal === "RED" && impact >= 4) {
      return {
        key: "high-attention",
        label: "HIGH ATTENTION",
        tone: "negative",
        attention: true,
        impact,
        signalLabel,
        weight: 40 + impact,
      };
    }
    if ((signal === "RED" && impact >= 3) || (signal === "AMBER" && impact >= 4)) {
      return {
        key: "review",
        label: "REVIEW",
        tone: "mixed",
        attention: true,
        impact,
        signalLabel,
        weight: 30 + impact,
      };
    }
    if (signal === "GREEN" && impact >= 4) {
      return {
        key: "material-positive",
        label: "MATERIAL",
        tone: "positive",
        attention: false,
        impact,
        signalLabel,
        weight: 20 + impact,
      };
    }
    return null;
  }

  function comparePriority(a, b) {
    return (b.priority?.weight || 0) - (a.priority?.weight || 0);
  }

  function scheduled(callback) {
    let pending = false;
    return () => {
      if (pending) return;
      pending = true;
      window.requestAnimationFrame(() => {
        pending = false;
        callback();
      });
    };
  }

  function internalLink(href, label, className) {
    const link = element("a", className, label);
    link.href = href;
    return link;
  }

  function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function validIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function isWatchlist() {
    return new URLSearchParams(window.location.search).get("watchlist") === "1";
  }

  function reducedMotion() {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }
})();
