/* Editorial card. No model calls, network requests or financial arithmetic. */
(() => {
  "use strict";
  const SVG = "http://www.w3.org/2000/svg";
  const LEVELS = ["", "Routine", "Minor", "Material", "High", "Critical"];
  const PATHS = Object.freeze({
    bars: "M4 20V13h3v7M10 20V8h3v12M16 20V3h3v17M3 21h18",
    calendar: "M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1ZM8 3v4M16 3v4M4 10h16",
    factory: "M3 21V10l6 4V9l6 4V3h4v18ZM7 17h2M12 17h2M17 17h1",
    dividend: "M13 3v8h8a8 8 0 0 0-8-8ZM9 4a9 9 0 1 0 11 11H9Z",
    cash: "M3 7h18v13H3ZM6 7V4h13M14 13.5a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z",
    coins: "M3 9c0-3 10-3 10 0s-10 3-10 0ZM3 9v5c0 3 10 3 10 0V9M3 14v5c0 3 10 3 10 0v-5M11 4c0-3 10-3 10 0s-10 3-10 0ZM21 4v5c0 2-3 3-6 3M21 9v5c0 2-3 3-6 3",
    document: "M6 3h8l4 4v14H6ZM14 3v5h4M9 12h6M9 16h6",
    qualification: "M12 3 2 21h20ZM12 9v5M12 17v.2"
  });
  const text = value => typeof value === "string" ? value.trim() : "";
  const key = value => text(value).toLowerCase().replace(/\s+/g, " ").replace(/[.!;]+$/, "");
  function node(tag, content, className) {
    const el = document.createElement(tag);
    if (content !== undefined && content !== null) el.textContent = content;
    if (className) el.className = className;
    return el;
  }
  function unique(values) {
    const seen = new Set();
    return values.map(text).filter(value => value && !seen.has(key(value)) && seen.add(key(value)));
  }
  function graphic(kind, className) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", className);
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", PATHS[kind]);
    svg.append(path);
    return svg;
  }
  function icon(fact) {
    const label = `${text(fact.metric)} ${text(fact.label)}`.toLowerCase();
    let kind = "document";
    if (/dividend/.test(label)) kind = "dividend";
    else if (/cash|debt|fund|liquidity/.test(label)) kind = "cash";
    else if (/production|launch/.test(label)) kind = "factory";
    else if (/develop|duration|month|date|term|deadline/.test(label)) kind = "calendar";
    else if (/profit|pbt|ebit|annual revenue|consideration|contract value/.test(label)) kind = "coins";
    else if (/revenue|sales|margin|eps|earnings|growth/.test(label)) kind = "bars";
    return graphic(kind, "metric-icon");
  }
  function context(fact) {
    // Keep the original periods and comparisons. Never infer a trend or do arithmetic.
    return unique([
      fact.period,
      fact.as_of_date ? `As at ${fact.as_of_date}` : "",
      fact.previous_value ? `Previously ${fact.previous_value}` : "",
      fact.comparator,
    ]).join(" · ");
  }
  function factNotes(parent, fact) {
    const detail = context(fact);
    if (detail) parent.append(node("p", detail, "metric-context"));
    if (text(fact.note)) parent.append(node("p", fact.note, "metric-note"));
    if (fact.basis === "calculated") parent.append(node("span", "Calculated", "fact-basis"));
    if (fact.basis === "not-disclosed") parent.append(node("span", "Not disclosed", "fact-basis"));
    if (fact.basis === "source-warning") parent.append(node("span", "Source warning", "fact-basis"));
    if (["previously-disclosed", "reiterated"].includes(fact.information_status)) {
      parent.append(node("span", fact.information_status === "reiterated" ? "Reiterated" : "Previously disclosed", "fact-basis"));
    }
  }
  function dateLabel(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text(value))) return "";
    const parsed = new Date(`${value}T12:00:00Z`);
    if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return "";
    return new Intl.DateTimeFormat("en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}).format(parsed);
  }
  function section(title, paragraphs, extraClass = "") {
    const block = node("section", null, `result-section ${extraClass}`.trim());
    block.append(node("h3", title));
    unique(paragraphs).forEach(value => block.append(node("p", value)));
    return block;
  }
  function metricIndexes(card, facts) {
    const requested = Array.isArray(card.metric_indexes) ? card.metric_indexes : facts.map((_, i) => i);
    return [...new Set(requested)].filter(i => Number.isInteger(i) && i >= 0 && i < facts.length
      && ["reported", "calculated"].includes(facts[i].basis)
      && facts[i].information_status !== "not-disclosed" && /\d/.test(text(facts[i].value))).slice(0, 4);
  }
  function render(target, card) {
    if (!card || !Array.isArray(card.facts) || card.facts.some(f => !f || typeof f !== "object")
        || !text(card.headline)) throw new Error("The analysis could not be displayed. Your text is still here.");
    const compact = card.schema_version === "rnsrepo-card-1";
    const facts = card.facts;
    const identity = card.identity || {};
    const indexes = metricIndexes(card, facts);
    const fragment = document.createDocumentFragment();
    const header = node("header", null, "result-header");
    const company = node("div", null, "identity");
    if (text(identity.ticker)) company.append(node("span", identity.ticker, "ticker"));
    company.append(node("span", text(identity.company) || "Announcement", "company-name"));
    header.append(company);
    const meta = node("p", null, "source-meta");
    // This is a user-supplied announcement, not independently authenticated RNS evidence.
    meta.append(node("span", "Announcement"));
    const formatted = dateLabel(identity.publication_date);
    if (formatted) {
      const time = node("time", formatted, "source-date");
      time.dateTime = identity.publication_date;
      meta.append(time);
    }
    header.append(meta);
    const headline = node("h2", card.headline);
    headline.id = "result-headline";
    fragment.append(header, headline);
    if (text(card.summary)) fragment.append(node("p", card.summary, "result-summary"));
    if (indexes.length) {
      const metrics = node("dl", null, "metrics");
      metrics.dataset.count = String(indexes.length);
      indexes.forEach(i => {
        const fact = facts[i];
        const tile = node("div", null, "metric");
        tile.dataset.factIndex = String(i);
        const label = node("dt", fact.label, "metric-label");
        const value = node("dd", fact.value, "metric-value");
        if (text(fact.value).length > 13) value.dataset.long = "true";
        tile.append(icon(fact), label, value);
        const notes = node("dd", null, "metric-detail");
        factNotes(notes, fact);
        if (notes.childNodes.length) tile.append(notes);
        metrics.append(tile);
      });
      fragment.append(metrics);
    }
    const changed = text(card.what_changed);
    // A contract card leads with what happened, numbers and conditions; its full delta
    // remains available below. Other announcements retain a distinct explanatory section.
    const showChanged = changed && (compact || card.rns_type !== "Contracts")
      && ![key(card.summary), key(card.headline)].includes(key(changed));
    if (showChanged) fragment.append(section("What changed", [changed], "what-changed"));
    // Legacy notes were not instructed to mirror essential caveats into primary fields.
    // Keep their entire analyst view visible rather than silently moving it into detail.
    const editorial = compact || card.versions?.editorial === "paste-editorial-2b";
    const qualifications = unique([
      ...(editorial ? [] : [card.analyst_view]),
      ...(Array.isArray(card.what_matters) ? card.what_matters : []),
    ]);
    // Never hide a source-warning fact just because it was not selected as a tile.
    facts.filter(f => f.basis === "source-warning").forEach(f => {
      qualifications.push(unique([`${text(f.label)}: ${text(f.value)}`, f.note]).join(". "));
    });
    const visibleQualifications = unique(qualifications);
    const fallbackView = !visibleQualifications.length ? text(card.analyst_view) : "";
    if (visibleQualifications.length) {
      const band = node("aside", null, "qualification-strip what-matters");
      band.setAttribute("aria-label", "Important context");
      const copy = node("div", null, "qualification-copy");
      visibleQualifications.forEach(value => copy.append(node("p", value)));
      band.append(graphic("qualification", "qualification-icon"), copy);
      fragment.append(band);
    }
    if (fallbackView) fragment.append(node("p", fallbackView, "result-commentary"));
    const remaining = facts.map((_, i) => i).filter(i => !indexes.includes(i));
    const extraChanged = changed && !showChanged
      && ![key(card.summary), key(card.headline), ...visibleQualifications.map(key)].includes(key(changed));
    const extraView = text(card.analyst_view)
      && ![key(card.summary), key(changed), key(fallbackView), ...visibleQualifications.map(key)].includes(key(card.analyst_view));
    if (!compact && (remaining.length || extraChanged || extraView)) {
      const details = node("details", null, "more-facts");
      details.append(node("summary", remaining.length ? "More facts" : "More detail"));
      if (extraChanged) details.append(section("What changed", [changed], "detail-changed"));
      if (extraView) details.append(section("Analysis", [card.analyst_view], "detail-analysis"));
      if (remaining.length) {
        const list = node("dl", null, "fact-list");
        remaining.forEach(i => {
          const fact = facts[i];
          const row = node("div", null, "fact-row");
          row.dataset.factIndex = String(i);
          row.append(node("dt", fact.label), node("dd", fact.value, "fact-value"));
          const notes = node("dd", null, "fact-detail");
          factNotes(notes, fact);
          if (notes.childNodes.length) row.append(notes);
          list.append(row);
        });
        details.append(list);
      }
      fragment.append(details);
    }
    const footer = node("footer", null, "result-footer");
    footer.append(node("span", compact
      ? `AI summary of ${card.selection?.reduced ? "selected sections of " : ""}pasted text · Not independently verified`
      : "AI analysis of pasted text · Not independently verified", "source-note"));
    const level = Number.isInteger(card.materiality) ? LEVELS[card.materiality] : "";
    const impact = node("details", null, "materiality");
    impact.append(node("summary", `Impact · ${level || "Unrated"}`));
    impact.append(node("p", text(card.materiality_rationale) || "Significance of the announcement, not a prediction of its share-price movement."));
    if (!compact) footer.append(impact);
    fragment.append(footer);
    target.replaceChildren(fragment);
    target.dataset.layout = compact ? "rnsrepo-card-1" : "paste-card-2b";
    target.dataset.direction = compact ? "brand" : ["green", "amber", "red", "grey"].includes(card.direction) ? card.direction : "grey";
  }
  window.SmallcapsCard = Object.freeze({render});
})();
