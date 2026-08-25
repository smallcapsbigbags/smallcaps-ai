(() => {
  "use strict";

  const NEWSROOM_SCHEMA = "aim-daily-newsroom-v1";
  const LONDON = "Europe/London";
  const EDITIONS = {
    early_read: { label: "EARLY READ · 07:30", short: "07:30 EARLY" },
    morning_note: { label: "MORNING EDITION · 08:00", short: "08:00 MORNING" },
    aim_close: { label: "AIM CLOSE · 16:35", short: "16:35 CLOSE" },
    custom: { label: "CUSTOM EDITION", short: "CUSTOM" },
  };

  document.addEventListener("DOMContentLoaded", initialise);

  async function initialise() {
    document.querySelectorAll("[data-edition-state]").forEach((button) => {
      button.addEventListener("click", () => loadEdition(button.dataset.editionState || "morning_note", true));
    });
    const params = new URLSearchParams(window.location.search);
    const state = clean(params.get("state")) || "morning_note";
    await loadEdition(state, false);
  }

  async function loadEdition(state, updateUrl) {
    const editionState = EDITIONS[state] ? state : "morning_note";
    setPressedState(editionState);
    setLoading();

    const params = new URLSearchParams(window.location.search);
    const date = clean(params.get("date"));
    const api = new URLSearchParams({ state: editionState });
    if (date) api.set("date", date);

    if (updateUrl) {
      const next = new URLSearchParams(window.location.search);
      next.set("state", editionState);
      const query = next.toString();
      window.history.replaceState({}, "", query ? `/?${query}` : "/");
    }

    try {
      const response = await fetch(`/api/v1/aim-daily/newsroom?${api.toString()}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.error?.message || "The newsroom is unavailable.");
      }
      if (payload.schema_version !== NEWSROOM_SCHEMA) {
        throw new Error("The AIM Daily newsroom contract is incompatible.");
      }
      renderEdition(payload);
    } catch (error) {
      renderError(error);
    }
  }

  function setLoading() {
    document.getElementById("daily-error").hidden = true;
    document.getElementById("lead-section").hidden = true;
    document.getElementById("quiet-section").hidden = true;
    document.getElementById("also-section").hidden = true;
    document.getElementById("quick-section").hidden = true;
    document.getElementById("edition-summary").textContent = "Loading the newsroom…";
    document.getElementById("rest-summary").textContent = "Loading complete market coverage…";
  }

  function renderEdition(edition) {
    document.title = `${formatLongDate(edition.date)} · The AIM Daily · Smallcaps.ai`;
    document.getElementById("edition-date").textContent = formatLongDate(edition.date).toUpperCase();
    document.getElementById("edition-label").textContent = editionLabel(edition.edition_state, edition.cutoff);
    document.getElementById("daily-updated").textContent = `NEWSROOM ${formatTime(edition.generated_at)}`;

    const screened = Number(edition.screened_candidate_count || 0);
    const selected = Number(edition.selected_story_count || 0);
    const published = Number(edition.published_article_count || 0);
    const withheld = Number(edition.withheld_story_count || 0);
    const other = Number(edition.other_analysed_count || 0);

    const summary = document.getElementById("edition-summary");
    summary.replaceChildren();
    summary.append(
      strong(`${screened} full analyses`),
      document.createTextNode(` · ${selected} ${plural(selected, "story", "stories")} worth attention`),
    );
    if (withheld) {
      summary.append(document.createTextNode(` · ${withheld} withheld by copy desk`));
    }

    renderLead(edition.lead);
    renderAlso(edition.also_matters || []);
    renderQuick(edition.quick_takes || []);

    const rest = document.getElementById("rest-summary");
    if (other > 0) {
      rest.textContent = `${other} other analysed ${plural(other, "announcement", "announcements")} did not earn a publication slot in this edition.`;
    } else if (screened > published) {
      rest.textContent = `${screened - published} analysed ${plural(screened - published, "announcement", "announcements")} remain outside the published edition.`;
    } else {
      rest.textContent = "Every analysed development selected by the editor is shown above.";
    }

    document.getElementById("daily-error").hidden = true;
  }

  function renderLead(article) {
    const section = document.getElementById("lead-section");
    const quiet = document.getElementById("quiet-section");
    const root = document.getElementById("lead-story");
    root.replaceChildren();

    if (!article) {
      section.hidden = true;
      quiet.hidden = false;
      return;
    }

    quiet.hidden = true;
    section.hidden = false;
    const layout = element("article", "lead-layout");
    layout.dataset.storyKey = clean(article.story_key);

    const main = element("div", "lead-main");
    main.append(storyKicker(article));
    main.append(element("h3", "lead-headline", article.headline));
    main.append(storyMeta(article));
    main.append(storyCopy(article, { full: true }));
    main.append(storyActions(article));

    const side = element("aside", "lead-side");
    const graphic = renderNumberGraphic(article.the_number);
    if (graphic) side.append(graphic);
    if (article.the_catch?.text) {
      side.append(asideCard("THE CATCH", article.the_catch.text));
    }
    if ((article.whats_missing || []).length) {
      side.append(asideCard("WHAT'S MISSING", article.whats_missing.map((item) => item.text).join(" ")));
    }
    if (article.next_test?.text) {
      side.append(asideCard("NEXT TEST", article.next_test.text));
    }

    layout.append(main, side);
    root.append(layout);
  }

  function renderAlso(articles) {
    const section = document.getElementById("also-section");
    const root = document.getElementById("also-stories");
    root.replaceChildren();
    if (!articles.length) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    articles.forEach((article) => root.append(renderAlsoStory(article)));
  }

  function renderAlsoStory(article) {
    const card = element("article", "also-story");
    card.dataset.storyKey = clean(article.story_key);
    card.append(storyKicker(article));
    card.append(element("h3", "also-headline", article.headline));
    card.append(storyMeta(article));
    card.append(storyCopy(article, { full: false }));
    const graphic = renderNumberGraphic(article.the_number);
    if (graphic) card.append(graphic);
    if (article.the_catch?.text) {
      card.append(asideCard("THE CATCH", article.the_catch.text));
    }
    card.append(storyActions(article));
    return card;
  }

  function renderQuick(articles) {
    const section = document.getElementById("quick-section");
    const root = document.getElementById("quick-stories");
    root.replaceChildren();
    if (!articles.length) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    articles.forEach((article, index) => {
      const row = element("article", "quick-story");
      row.dataset.storyKey = clean(article.story_key);
      row.append(element("span", "quick-index", String(index + 1).padStart(2, "0")));

      const title = element("div");
      title.append(storyKicker(article));
      title.append(element("h3", "quick-headline", article.headline));
      row.append(title);

      const copy = element("div", "quick-copy");
      copy.append(element("p", "", article.news?.text || article.view?.text || ""));
      row.append(copy);

      const action = element("div", "quick-action");
      const company = companyLink(article, "COMPANY →", "daily-action");
      if (company) action.append(company);
      row.append(action);
      root.append(row);
    });
  }

  function storyKicker(article) {
    const line = element("p", "story-kicker");
    const company = companyLink(article, clean(article.ticker) || clean(article.company), "");
    if (company) line.append(company);
    else line.append(document.createTextNode(clean(article.ticker) || clean(article.company) || "AIM"));
    line.append(document.createTextNode(" · "));
    const signal = element("span", `signal-mark signal-${signalClass(article.signal)}`, clean(article.signal) || "NO COLOUR");
    line.append(signal);
    return line;
  }

  function storyMeta(article) {
    const meta = element("p", "story-meta");
    meta.append(
      strong(`IMPACT ${Number(article.impact_score || 0)}/5`),
      document.createTextNode(clean(article.outlook) ? `OUTLOOK ${clean(article.outlook)}` : ""),
      document.createTextNode(clean(article.story_family) ? `STORY ${clean(article.story_family).replaceAll("_", " ")}` : ""),
    );
    [...meta.childNodes].forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE && !clean(node.textContent)) node.remove();
    });
    return meta;
  }

  function storyCopy(article, options) {
    const root = element("div", "story-copy");
    if (article.news?.text) {
      root.append(copySection("NEWS", article.news.text, "story-news"));
    }
    if (options.full && (article.context || []).length) {
      root.append(copyListSection("CONTEXT", article.context.map((item) => item.text), "story-context"));
    } else if (!options.full && article.context?.[0]?.text) {
      root.append(copySection("CONTEXT", article.context[0].text, "story-context"));
    }
    if (article.view?.text) {
      root.append(copySection("THE VIEW", article.view.text, "story-view"));
    }
    return root;
  }

  function copySection(label, text, extraClass) {
    const block = element("div", `story-section ${extraClass}`);
    block.append(
      element("span", "story-section-label", label),
      element("p", "", text),
    );
    return block;
  }

  function copyListSection(label, items, extraClass) {
    const block = element("div", `story-section ${extraClass}`);
    block.append(element("span", "story-section-label", label));
    const list = element("div", "story-section-list");
    items.filter(clean).forEach((text) => list.append(element("p", "", text)));
    block.append(list);
    return block;
  }

  function storyActions(article) {
    const root = element("div", "story-actions");
    const company = companyLink(article, "COMPANY INTELLIGENCE →", "daily-action");
    if (company) root.append(company);
    const source = originalSource(article);
    if (source) root.append(source);
    return root;
  }

  function renderNumberGraphic(number) {
    if (!number || !(number.points || []).length) return null;
    const figure = element("figure", "evidence-graphic");
    figure.append(element("figcaption", "number-label", "THE NUMBER"));
    figure.append(element("strong", "number-title", clean(number.label) || clean(number.metric) || "KEY METRIC"));
    const track = element("div", "number-track");
    number.points.slice(-3).forEach((point) => {
      const row = element("div", "number-point");
      row.append(
        element("strong", "", point.value),
        element("span", "", formatShortDate(point.published_at)),
      );
      track.append(row);
    });
    figure.append(track);
    const direction = clean(number.direction).toUpperCase();
    if (direction && direction !== "UNCLEAR") {
      figure.append(element("p", "number-direction", `${direction} ACROSS COMPARABLE DISCLOSURES`));
    }
    return figure;
  }

  function asideCard(label, text) {
    const card = element("section", "story-aside-card");
    card.append(element("h3", "", label), element("p", "", text));
    return card;
  }

  function originalSource(article) {
    const urls = [
      ...(article.source_urls || []),
      ...((article.news?.provenance || []).map((item) => item.source_url)),
    ];
    const url = urls.map(clean).find(safeHttpUrl);
    if (!url) return null;
    const link = element("a", "source-link", "READ THE EVIDENCE ↗");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }

  function companyLink(article, label, className) {
    const ticker = clean(article.ticker).toUpperCase().replace(/\.L$/, "");
    if (!ticker) return null;
    const link = element("a", className, label);
    link.href = `/company/${encodeURIComponent(ticker)}`;
    return link;
  }

  function renderError(error) {
    document.getElementById("lead-section").hidden = true;
    document.getElementById("quiet-section").hidden = true;
    document.getElementById("also-section").hidden = true;
    document.getElementById("quick-section").hidden = true;
    const root = document.getElementById("daily-error");
    root.hidden = false;
    document.getElementById("daily-error-message").textContent = clean(error?.message) || "The newsroom is unavailable.";
    document.getElementById("edition-summary").textContent = "Newsroom connection interrupted.";
  }

  function setPressedState(state) {
    document.querySelectorAll("[data-edition-state]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.editionState === state));
    });
  }

  function editionLabel(state, cutoff) {
    if (EDITIONS[state]) return EDITIONS[state].label;
    return cutoff ? `CUSTOM EDITION · ${cutoff}` : "CUSTOM EDITION";
  }

  function signalClass(value) {
    const signal = clean(value).toUpperCase();
    if (signal === "GREEN") return "green";
    if (signal === "AMBER") return "amber";
    if (signal === "RED") return "red";
    return "no-colour";
  }

  function formatLongDate(value) {
    const date = parseDate(value);
    if (!date) return clean(value) || "TODAY";
    return new Intl.DateTimeFormat("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: LONDON,
    }).format(date);
  }

  function formatShortDate(value) {
    const date = parseDate(value);
    if (!date) return clean(value);
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "2-digit",
      timeZone: LONDON,
    }).format(date).toUpperCase();
  }

  function formatTime(value) {
    const date = parseDate(value);
    if (!date) return "—";
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: LONDON,
    }).format(date);
  }

  function parseDate(value) {
    const raw = clean(value);
    if (!raw) return null;
    const date = new Date(raw.length === 10 ? `${raw}T12:00:00Z` : raw);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function safeHttpUrl(value) {
    try {
      const url = new URL(value, window.location.origin);
      return ["http:", "https:"].includes(url.protocol);
    } catch (_error) {
      return false;
    }
  }

  function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null && String(text) !== "") node.textContent = String(text);
    return node;
  }

  function strong(text) {
    return element("strong", "", text);
  }

  function plural(count, singular, pluralWord) {
    return count === 1 ? singular : pluralWord;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }
})();
