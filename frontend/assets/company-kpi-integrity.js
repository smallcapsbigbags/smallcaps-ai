(() => {
  "use strict";

  const COMPANY_SCHEMA = "scbb-company-v1";
  const INTEGRITY_VERSION = "kpi-integrity-v1";
  const MAX_KEY_NUMBERS = 6;
  const nativeFetch = window.fetch.bind(window);

  let companyPayload = null;
  let scheduled = false;

  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    if (isCompanyRequest(args[0]) && response.ok) {
      response.clone().json().then(captureCompany).catch(() => undefined);
    }
    return response;
  };

  document.addEventListener("DOMContentLoaded", () => {
    const content = document.getElementById("company-content");
    if (!content) return;
    new MutationObserver(scheduleEnhancement).observe(content, {
      childList: true,
      subtree: true,
    });
    scheduleEnhancement();
  });

  function isCompanyRequest(input) {
    try {
      const raw = input instanceof Request ? input.url : String(input || "");
      const url = new URL(raw, window.location.href);
      return url.origin === window.location.origin
        && url.pathname.startsWith("/api/v1/company/");
    } catch (_error) {
      return false;
    }
  }

  function captureCompany(payload) {
    if (!payload || payload.schema_version !== COMPANY_SCHEMA) return;
    companyPayload = payload;
    scheduleEnhancement();
  }

  function scheduleEnhancement() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhanceKeyNumbers();
    });
  }

  function enhanceKeyNumbers() {
    if (!companyPayload) return;
    const metrics = (companyPayload.metrics || [])
      .filter((item) => clean(item?.latest_value))
      .slice(0, MAX_KEY_NUMBERS);
    const cards = [...document.querySelectorAll(".repo-metric")];
    if (!cards.length || cards.length !== metrics.length) return;

    cards.forEach((card, index) => enhanceMetricCard(card, metrics[index]));
  }

  function enhanceMetricCard(card, metric) {
    if (!(card instanceof HTMLElement) || card.dataset.kpiEnhanced === "true") return;

    const integrity = metric?.integrity || {};
    const status = clean(integrity.status) || "single-point";
    card.dataset.kpiIdentity = clean(metric.identity);
    card.dataset.trendStatus = status;
    card.dataset.kpiIntegrity = clean(integrity.version) || INTEGRITY_VERSION;

    const trend = validTrend(metric);
    const foot = card.querySelector(".repo-metric-foot");
    if (trend.length >= 2 && status === "comparable") {
      const chart = sparkline(metric, trend);
      if (foot) card.insertBefore(chart, foot);
      else card.append(chart);
    } else if (Number(integrity.suppressed_points || 0) > 0) {
      const note = document.createElement("p");
      note.className = "repo-metric-integrity-note";
      note.textContent = "Other periods or units kept separate.";
      if (clean(integrity.reason)) note.title = integrity.reason;
      if (foot) card.insertBefore(note, foot);
      else card.append(note);
    }

    card.dataset.kpiEnhanced = "true";
  }

  function validTrend(metric) {
    if (metric?.integrity?.version !== INTEGRITY_VERSION) return [];
    const points = Array.isArray(metric.trend_points) ? metric.trend_points : [];
    return points.filter((point) => (
      Number.isFinite(Number(point?.comparable_value_numeric))
      && clean(point?.source_id)
      && safeSource(point?.source_url)
    ));
  }

  function sparkline(metric, points) {
    const figure = document.createElement("figure");
    figure.className = "repo-metric-trend";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "repo-sparkline");
    svg.setAttribute("viewBox", "0 0 160 44");
    svg.setAttribute("role", "img");
    svg.setAttribute("focusable", "false");
    svg.setAttribute("aria-label", trendLabel(metric, points));

    const baseline = document.createElementNS("http://www.w3.org/2000/svg", "line");
    baseline.setAttribute("class", "repo-sparkline-baseline");
    baseline.setAttribute("x1", "4");
    baseline.setAttribute("x2", "156");
    baseline.setAttribute("y1", "38");
    baseline.setAttribute("y2", "38");

    const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    path.setAttribute("class", "repo-sparkline-path");
    path.setAttribute("points", plotPoints(points));

    const first = pointMarker(points, 0);
    const latest = pointMarker(points, points.length - 1);
    latest.setAttribute("class", "repo-sparkline-point repo-sparkline-point-latest");
    svg.append(baseline, path, first, latest);

    const caption = document.createElement("figcaption");
    caption.className = "repo-metric-trend-caption";
    const count = points.length;
    const excluded = Number(metric?.integrity?.suppressed_points || 0);
    caption.textContent = `${count} like-for-like period${count === 1 ? "" : "s"}`
      + (excluded > 0 ? ` · ${excluded} kept separate` : "");
    if (clean(metric?.integrity?.reason)) caption.title = metric.integrity.reason;

    figure.append(svg, caption);
    return figure;
  }

  function coordinates(points) {
    const values = points.map((point) => Number(point.comparable_value_numeric));
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const spread = maximum - minimum;
    return values.map((value, index) => {
      const x = points.length === 1 ? 80 : 4 + (152 * index) / (points.length - 1);
      const y = spread === 0 ? 21 : 4 + 32 * (1 - (value - minimum) / spread);
      return { x, y };
    });
  }

  function plotPoints(points) {
    return coordinates(points)
      .map(({ x, y }) => `${x.toFixed(2)},${y.toFixed(2)}`)
      .join(" ");
  }

  function pointMarker(points, index) {
    const position = coordinates(points)[index];
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "repo-sparkline-point");
    circle.setAttribute("cx", position.x.toFixed(2));
    circle.setAttribute("cy", position.y.toFixed(2));
    circle.setAttribute("r", "2.3");
    return circle;
  }

  function trendLabel(metric, points) {
    const label = clean(metric.label) || clean(metric.metric) || "Metric";
    const first = points[0];
    const latest = points.at(-1);
    return `${label}: ${clean(first.value)} to ${clean(latest.value)} across ${points.length} like-for-like periods.`;
  }

  function safeSource(value) {
    try {
      const url = new URL(clean(value), window.location.href);
      return url.protocol === "https:" || url.protocol === "http:";
    } catch (_error) {
      return false;
    }
  }

  function clean(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }
})();
