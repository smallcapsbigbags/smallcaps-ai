(() => {
  "use strict";

  const SIGNAL_LABELS = {
    GREEN: "Positive",
    AMBER: "Mixed",
    RED: "Negative",
    "NO COLOUR": "Neutral",
  };

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("company-content");
    if (!root) return;

    let scheduled = false;
    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(() => {
        scheduled = false;
        polishCompany(root);
      });
    };

    schedule();
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
    window.addEventListener("smallcaps:watchlist-change", schedule);
  });

  function polishCompany(root) {
    updateWatchlistCount();
    polishSections(root);
    polishCurrentView(root);
    polishHistory(root);
    polishLinks(root);
    polishSignals(root);
    polishCopy(root);
    root.querySelectorAll(".company-note-grid").forEach(polishNoteGrid);
  }

  function updateWatchlistCount() {
    const count = document.getElementById("watchlist-nav-count");
    const store = window.SmallcapsWatchlist;
    if (!count || !store) return;
    const total = store.read().length;
    setText(count, String(total));
    count.hidden = total === 0;
  }

  function polishSections(root) {
    const headings = {
      "CURRENT VIEW": "LATEST COMPANY NEWS",
      "MANAGEMENT PROMISES": "MANAGEMENT COMMITMENTS",
      "RNS HISTORY": "COMPANY NEWS HISTORY",
    };
    const descriptions = {
      "LATEST COMPANY NEWS": "Latest published facts and what changed.",
      GUIDANCE: "Current disclosed forward-looking statements.",
      "METRICS THAT MATTER": "Material reported or calculated company series.",
      "MANAGEMENT COMMITMENTS": "Open disclosed commitments and their eventual outcomes.",
      "WHAT REMAINS UNCLEAR": "Decision-useful information the published record does not yet answer.",
      "COMPANY NEWS HISTORY": "Chronological record of published facts, changes and market reaction.",
    };

    root.querySelectorAll(".company-section-head").forEach((head) => {
      const heading = head.querySelector("h2");
      if (!heading) return;
      const current = clean(heading.textContent).toUpperCase();
      if (headings[current]) setText(heading, headings[current]);
      const finalTitle = clean(heading.textContent).toUpperCase();
      const description = head.querySelector("p");
      if (description && descriptions[finalTitle]) {
        setText(description, descriptions[finalTitle]);
      }
    });
  }

  function polishCurrentView(root) {
    const section = root.querySelector('[data-company-section="current-view"]');
    if (!section) return;

    section.querySelectorAll(".company-current-meta span").forEach((node) => {
      if (clean(node.textContent).toUpperCase() === "RNS") setText(node, "Company news");
    });

    const change = section.querySelector(".company-current-change");
    if (change) change.dataset.label = "WHAT CHANGED";

    const fullNote = section.querySelector(".company-full-note");
    const summary = findNoteBlock(fullNote, ["RNS SUMMARY", "TAKE"]);
    const paragraphs = summary ? [...summary.querySelectorAll("p")].filter((node) => clean(node.textContent)) : [];
    const takeaway = clean(paragraphs.at(-1)?.textContent);

    const take = section.querySelector(".company-ai-view");
    if (take) {
      const label = take.querySelector("span");
      const copy = take.querySelector("p");
      if (label) setText(label, "TAKE");
      if (copy && takeaway) setText(copy, takeaway);
    }

    const detailsSummary = fullNote?.querySelector("summary");
    if (detailsSummary) setText(detailsSummary, "VIEW EVIDENCE");
  }

  function polishHistory(root) {
    const headMap = {
      "DATE / RNS": "DATE / NEWS",
      "ANALYST VIEW": "TAKE",
      MARKET: "DAY",
      IMPACT: "MATERIALITY",
    };
    root.querySelectorAll(".company-history-head > span").forEach((node) => {
      const current = clean(node.textContent).toUpperCase();
      if (headMap[current]) setText(node, headMap[current]);
    });

    root.querySelectorAll(".company-history-date small").forEach((node) => {
      const current = clean(node.textContent);
      if (/ · RNS$/i.test(current)) setText(node, current.replace(/ · RNS$/i, " · COMPANY NEWS"));
    });

    root.querySelectorAll(".company-history-action").forEach((node) => {
      const current = clean(node.textContent).toUpperCase();
      if (current === "READ ANALYSIS →") setText(node, "VIEW EVIDENCE →");
      if (current === "CLOSE ANALYSIS ↑") setText(node, "CLOSE EVIDENCE ↑");
      if (current === "ORIGINAL RNS ↗") setText(node, "SOURCE ↗");
      if (current === "OPEN IN FEED →") setText(node, "OPEN IN NEWS →");
    });
  }

  function polishLinks(root) {
    root.querySelectorAll("a").forEach((link) => {
      const current = clean(link.textContent).toUpperCase();
      if (current === "ORIGINAL RNS ↗") setText(link, "SOURCE ↗");
      if (current === "SOURCE RNS ↗") setText(link, "SOURCE ↗");
      if (current === "LAST RELEVANT RNS ↗") setText(link, "LAST RELEVANT SOURCE ↗");
      if (current === "OPEN IN RNS FEED →") setText(link, "OPEN IN NEWS →");
      if (current === "OPEN IN FEED →") setText(link, "OPEN IN NEWS →");
      if (link.classList.contains("company-feed-link") || current.includes("OPEN IN RNS FEED")) {
        const href = link.getAttribute("href") || "";
        if (href.startsWith("/?")) link.setAttribute("href", `/rns${href.slice(1)}`);
      }
    });
  }

  function polishSignals(root) {
    root.querySelectorAll(".signal").forEach((node) => {
      const current = clean(node.textContent).toUpperCase();
      if (SIGNAL_LABELS[current]) setText(node, SIGNAL_LABELS[current]);
    });

    root.querySelectorAll(".company-stat-label").forEach((node) => {
      if (clean(node.textContent).toUpperCase() === "IMPACT") setText(node, "MATERIALITY");
    });

    root.querySelectorAll(".company-stat-value, .company-history-row small").forEach((node) => {
      const current = clean(node.textContent);
      const next = current
        .replace(/\bCRITICAL\b/g, "VERY HIGH")
        .replace(/\bMINOR\b/g, "LOW")
        .replace(/RNS-DAY CLOSE/gi, "DAY CLOSE");
      if (next !== current) setText(node, next);
    });
  }

  function polishCopy(root) {
    root.querySelectorAll(".company-stat-note, .company-empty p, .company-error p").forEach((node) => {
      const current = clean(node.textContent);
      const next = current
        .replace(/RNS-day close/gi, "Announcement-day close")
        .replace(/Reported in latest RNS/gi, "Reported in latest company news")
        .replace(/publishable RNS analysis/gi, "publishable company-news analysis")
        .replace(/this monitoring sheet/gi, "this company record")
        .replace(/AIM RNS feed/gi, "Company News");
      if (next !== current) setText(node, next);
    });
  }

  function polishNoteGrid(grid) {
    [...grid.querySelectorAll(".company-note-block")].forEach((block) => {
      const heading = block.querySelector("h3");
      if (!heading) return;
      const title = clean(heading.textContent).toUpperCase();

      if (["AI VIEW", "WHAT TO WATCH", "SUPPORTS THE CASE", "CHALLENGES THE CASE"].includes(title)) {
        block.remove();
        return;
      }

      if (title === "RNS SUMMARY" || title === "TAKE") {
        setText(heading, "TAKE");
        const paragraphs = [...block.querySelectorAll("p")].filter((node) => clean(node.textContent));
        if (paragraphs.length > 1) paragraphs.slice(0, -1).forEach((node) => node.remove());
      } else if (title === "KEY NUMBERS") {
        setText(heading, "MATERIAL FACTS");
      } else if (title === "OUTLOOK & GUIDANCE") {
        setText(heading, "GUIDANCE");
      } else if (title === "DISCLOSURE GAPS / SOURCE WARNINGS") {
        setText(heading, "NOT DISCLOSED / SOURCE CHECKS");
      }

      if (clean(heading.textContent).toUpperCase() === "WHAT CHANGED") {
        block.querySelectorAll("li").forEach((item) => {
          if (clean(item.textContent).toUpperCase().startsWith("READ-THROUGH:")) item.remove();
        });
      }
    });
  }

  function findNoteBlock(root, titles) {
    if (!root) return null;
    const wanted = new Set(titles.map((value) => value.toUpperCase()));
    return [...root.querySelectorAll(".company-note-block")].find((block) => {
      const title = clean(block.querySelector("h3")?.textContent).toUpperCase();
      return wanted.has(title);
    }) || null;
  }

  function setText(node, value) {
    if (!node) return;
    if (clean(node.textContent) === value) return;
    node.textContent = value;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }
})();
