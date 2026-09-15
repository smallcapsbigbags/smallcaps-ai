/* One deterministic card. No model calls, network requests or financial arithmetic. */
(() => {
  "use strict";
  const SVG = "http://www.w3.org/2000/svg";
  const LEVELS = ["", "Routine", "Minor", "Material", "High", "Critical"];
  const PATHS = Object.freeze({
    bars: "M4 20V13h3v7M10 20V8h3v12M16 20V3h3v17M3 21h18",
    calendar: "M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1ZM8 3v4M16 3v4M4 10h16M8 14h2M14 14h2",
    factory: "M3 21V10l6 4V9l6 4V3h4v18ZM7 17h2M12 17h2M17 17h1",
    dividend: "M13 3v8h8a8 8 0 0 0-8-8ZM9 4a9 9 0 1 0 11 11H9Z",
    cash: "M3 7h18v13H3ZM6 7V4h13M14 13.5a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM6 11h1M17 17h1",
    coins: "M3 9c0-3 10-3 10 0s-10 3-10 0ZM3 9v5c0 3 10 3 10 0V9M3 14v5c0 3 10 3 10 0v-5M11 4c0-3 10-3 10 0s-10 3-10 0ZM21 4v5c0 2-3 3-6 3M21 9v5c0 2-3 3-6 3",
    document: "M6 3h8l4 4v14H6ZM14 3v5h4M9 12h6M9 16h6"
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
  function icon(fact) {
    const label = `${text(fact.metric)} ${text(fact.label)}`.toLowerCase();
    let kind = "document";
    if (/dividend/.test(label)) kind = "dividend";
    else if (/cash|debt|fund|liquidity/.test(label)) kind = "cash";
    else if (/production|launch/.test(label)) kind = "factory";
    else if (/develop|duration|month|date|term|deadline/.test(label)) kind = "calendar";
    else if (/profit|pbt|ebit|annual revenue|consideration|contract value/.test(label)) kind = "coins";
    else if (/revenue|sales|margin|eps|earnings|growth/.test(label)) kind = "bars";
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "metric-icon");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", PATHS[kind]);
    svg.append(path);
    return svg;
  }
  function context(fact) {
    // No inferred date, percentage change, trend arrow or string-to-number conversion.
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
    unique(paragraphs).forEach((value, i) => block.append(node("p", value, i ? "section-qualification" : "section-lead")));
    return block;
  }
  function metricIndexes(card, facts) {
    // Old in-memory responses remain readable. New responses supply source indexes.
    const requested = Array.isArray(card.metric_indexes) ? card.metric_indexes : facts.map((_, i) => i);
    return [...new Set(requested)].filter(i => Number.isInteger(i) && i >= 0 && i < facts.length
      && ["reported", "calculated"].includes(facts[i].basis)
      && facts[i].information_status !== "not-disclosed" && /\d/.test(text(facts[i].value))).slice(0, 4);
  }
  function render(target, card) {
    if (!card || !Array.isArray(card.facts) || card.facts.some(f => !f || typeof f !== "object")
        || !text(card.headline)) throw new Error("The analysis could not be displayed. Your text is still here.");
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
    if (text(card.rns_type)) meta.append(node("span", card.rns_type));
    const formatted = dateLabel(identity.publication_date);
    if (formatted) {
      const time = node("time", formatted, "source-date");
      time.dateTime = identity.publication_date;
      meta.append(time);
    }
    if (meta.childNodes.length) header.append(meta);
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
        // Accessible definition-list order; CSS places the number ahead of its label.
        tile.append(icon(fact), label, value);
        const notes = node("dd", null, "metric-detail");
        factNotes(notes, fact);
        if (notes.childNodes.length) tile.append(notes);
        metrics.append(tile);
      });
      fragment.append(metrics);
    }
    const changed = text(card.what_changed);
    if (changed) fragment.append(section("What changed", [changed]));
    const matters = unique([card.analyst_view, ...(Array.isArray(card.what_matters) ? card.what_matters : [])]);
    // Warnings are always visible, even when their fact did not make a headline tile.
    facts.filter(f => f.basis === "source-warning").forEach(f => {
      matters.push(unique([`${text(f.label)}: ${text(f.value)}`, f.note]).join(". "));
    });
    if (matters.length) fragment.append(section("What matters", matters, "what-matters"));
    const remaining = facts.map((_, i) => i).filter(i => !indexes.includes(i));
    if (remaining.length) {
      const details = node("details", null, "more-facts");
      details.append(node("summary", "More facts"));
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
      fragment.append(details);
    }
    const footer = node("footer", null, "result-footer");
    footer.append(node("span", "AI analysis of pasted text · Not independently verified", "source-note"));
    const level = Number.isInteger(card.materiality) ? LEVELS[card.materiality] : "";
    const impact = node("details", null, "materiality");
    impact.append(node("summary", `Impact · ${level || "Unrated"}`));
    impact.append(node("p", text(card.materiality_rationale) || "Significance of the announcement, not a prediction of its share-price movement."));
    footer.append(impact);
    fragment.append(footer);
    target.replaceChildren(fragment);
    target.dataset.direction = ["green", "amber", "red", "grey"].includes(card.direction) ? card.direction : "grey";
  }
  window.SmallcapsCard = Object.freeze({render});
})();
