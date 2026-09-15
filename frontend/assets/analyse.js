(() => {
  "use strict";
  const form = document.getElementById("analyse-form");
  if (!form) return;
  const input = document.getElementById("rns-text");
  const button = document.getElementById("analyse-button");
  const label = document.getElementById("button-label");
  const message = document.getElementById("form-message");
  const result = document.getElementById("result");
  const signIn = document.getElementById("sign-in");
  let busy = false;
  let analysisId = null;
  let submittedText = "";
  let resume = false;

  function say(text, error = false) {
    message.textContent = text;
    message.dataset.error = String(error);
  }
  function sync() {
    const size = input.value.trim().length;
    document.getElementById("input-count").textContent = size ? `${size.toLocaleString("en-GB")} characters` : "";
    button.disabled = busy || size < 120 || size > 120000;
    input.disabled = busy;
    form.setAttribute("aria-busy", String(busy));
    label.textContent = busy ? "Analysing…" : resume ? "Check analysis" : "Analyse";
  }
  input.addEventListener("input", () => {
    if (input.value !== submittedText) {
      analysisId = null;
      resume = false;
      result.hidden = true;
      result.replaceChildren();
      document.getElementById("analyse-shell").classList.remove("has-result");
    }
    say(input.value.length > 120000 ? "This is over 120,000 characters. Paste one announcement at a time." : "", input.value.length > 120000);
    sync();
  });
  input.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !button.disabled) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined && text !== null) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function icon(fact) {
    const text = `${fact.metric || ""} ${fact.label}`.toLowerCase();
    let path = "M4 19V12h3v7m3 0V7h3v12m3 0V3h3v16M3 21h18";
    if (/develop|month|date/.test(text)) path = "M4 5h16v16H4zM8 3v4m8-4v4M4 10h16m-12 4h2m4 0h2";
    else if (/production/.test(text)) path = "M3 21V10l6 4V9l6 4V3h4v18H3zm4-4h2m4 0h2m3 0h1";
    else if (/dividend/.test(text)) path = "M12 3v9h9A9 9 0 0 0 12 3zm-3 2a9 9 0 1 0 10 10H9V5z";
    else if (/cash|debt/.test(text)) path = "M3 7h18v14H3V7zm0 0V4h15v3m-3 5h6v5h-6z";
    else if (/profit|pbt|ebit|annual revenue/.test(text)) path = "M4 6c0-3 12-3 12 0s-12 3-12 0zm0 0v5c0 3 12 3 12 0V6M4 11v5c0 3 12 3 12 0m0-6h4v10c0 2-7 3-10 1";
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "metric-icon");
    svg.setAttribute("aria-hidden", "true");
    const line = document.createElementNS(svg.namespaceURI, "path");
    line.setAttribute("d", path);
    svg.append(line);
    return svg;
  }
  function factContext(fact) {
    return [fact.period, fact.as_of_date, fact.previous_value ? `Previously ${fact.previous_value}` : fact.comparator].filter(Boolean).join(" · ");
  }
  function section(title, paragraphs) {
    const block = node("section", null, "result-section");
    block.append(node("h3", title));
    paragraphs.filter(Boolean).forEach((text) => block.append(node("p", text)));
    return block;
  }
  function render(card) {
    result.replaceChildren();
    result.dataset.direction = ["green", "amber", "red", "grey"].includes(card.direction) ? card.direction : "grey";
    const identity = node("div", null, "identity");
    if (card.identity.ticker) identity.append(node("span", card.identity.ticker, "ticker"));
    identity.append(node("span", card.identity.company || "Announcement", "company-name"));
    result.append(identity);
    const date = card.identity.publication_date;
    if (date) {
      const formatted = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
      const time = node("time", formatted, "source-date");
      time.dateTime = date;
      result.append(time);
    }
    const headline = node("h2", card.headline);
    headline.id = "result-headline";
    result.append(headline, node("p", card.summary, "result-summary"));
    const metrics = node("div", null, "metrics");
    card.facts.slice(0, 4).forEach((fact) => {
      const tile = node("div", null, "metric");
      tile.append(icon(fact), node("strong", fact.value, "metric-value"), node("span", fact.label, "metric-label"));
      const context = factContext(fact);
      if (context) tile.append(node("p", context, "metric-context"));
      if (fact.note) tile.append(node("p", fact.note, "metric-note"));
      if (fact.basis !== "reported") tile.append(node("p", fact.basis.replaceAll("-", " "), "metric-context"));
      metrics.append(tile);
    });
    if (card.facts.length) result.append(metrics);
    result.append(section("What changed", [card.what_changed]));
    if (card.what_matters.length) result.append(section("What matters", card.what_matters));
    if (card.facts.length > 4) {
      const detail = node("details", null, "more-facts");
      detail.append(node("summary", "More facts"));
      card.facts.slice(4).forEach((fact) => detail.append(node("p", [
        `${fact.label}: ${fact.value}`, factContext(fact), fact.note,
        fact.basis !== "reported" ? fact.basis.replaceAll("-", " ") : ""
      ].filter(Boolean).join("\n"))));
      result.append(detail);
    }
    const footer = node("div", null, "result-footer");
    footer.append(node("span", "Based on pasted text · Not independently verified"));
    const levels = ["", "Routine", "Minor", "Material", "High", "Critical"];
    const impact = node("span", `Impact · ${levels[card.materiality] || "Unrated"}`, "materiality");
    impact.title = card.materiality_rationale;
    footer.append(impact);
    result.append(footer);
    result.hidden = false;
    document.getElementById("analyse-shell").classList.add("has-result");
    result.focus({ preventScroll: true });
    result.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  async function request(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url, { ...options, credentials: "same-origin", cache: "no-store", signal: controller.signal });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401) signIn.hidden = false;
        const failure = new Error(data.error?.message || "Analysis is temporarily unavailable.");
        failure.code = data.error?.code;
        throw failure;
      }
      return data;
    } finally { clearTimeout(timer); }
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button.disabled) return;
    busy = true;
    signIn.hidden = true;
    result.hidden = true;
    submittedText = input.value;
    sync();
    say(resume ? "Checking your analysis…" : "Analysing the announcement…");
    try {
      let job;
      if (resume && analysisId) {
        job = await request(`/api/v1/analyse/${encodeURIComponent(analysisId)}`);
      } else {
        // Establish ownership before a paid POST so a lost POST response can be retried safely.
        await request("/api/v1/analyse");
        job = await request("/api/v1/analyse", {
          method: "POST", headers: { "Content-Type": "application/json", "X-Smallcaps-Action": "analyse" },
          body: JSON.stringify({ text: submittedText })
        });
      }
      analysisId = job.analysis_id;
      const start = Date.now();
      while (job.status === "processing") {
        if (Date.now() - start > 600000) throw new Error("This is taking longer than expected. Check the analysis again shortly.");
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (Date.now() - start > 45000) say("Still analysing. Complex announcements can take longer.");
        job = await request(`/api/v1/analyse/${encodeURIComponent(analysisId)}`);
      }
      resume = false;
      analysisId = null;
      if (job.status !== "complete") {
        throw new Error(job.error_code === "REVIEW_REQUIRED"
          ? "We couldn’t produce a reliable card. Check that the complete announcement is included."
          : "Analysis is temporarily unavailable. Your text is still here. Please try again later.");
      }
      render(job.result);
      say("");
    } catch (error) {
      if (error.code === "NOT_FOUND") analysisId = null;
      resume = Boolean(analysisId);
      say(error.name === "AbortError" || error instanceof TypeError
        ? "Connection interrupted. Your text is still here; try again to check the same analysis."
        : error.message, true);
    } finally { busy = false; sync(); }
  });
  sync();
})();
