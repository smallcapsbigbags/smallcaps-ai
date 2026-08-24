(() => {
  "use strict";

  const MONTHS = {
    JAN: "01",
    FEB: "02",
    MAR: "03",
    APR: "04",
    MAY: "05",
    JUN: "06",
    JUL: "07",
    AUG: "08",
    SEP: "09",
    OCT: "10",
    NOV: "11",
    DEC: "12",
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
        enhanceHistoryLinks(root);
        enhanceTableSemantics(root);
        polishMetricPeriods(root);
      });
    };

    schedule();
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  });

  function enhanceHistoryLinks(root) {
    root.querySelectorAll("article.company-history-row").forEach((row) => {
      if (row.dataset.feedJourneyReady === "true") return;
      const sourceId = clean(row.dataset.sourceId);
      const dateText = clean(row.querySelector(".company-history-date strong")?.textContent);
      const isoDate = parseDisplayDate(dateText);
      const actions = row.querySelector(".company-history-actions");
      if (!sourceId || !isoDate || !actions) return;

      const link = document.createElement("a");
      link.className = "company-history-action company-feed-link";
      link.href = `/?date=${isoDate}&open=${encodeURIComponent(sourceId)}`;
      link.textContent = "OPEN IN FEED →";
      link.setAttribute("aria-label", `Open the ${dateText} announcement in the RNS feed`);

      const original = [...actions.querySelectorAll("a")].find((item) =>
        clean(item.textContent).startsWith("ORIGINAL RNS"),
      );
      actions.insertBefore(link, original || null);
      row.dataset.feedJourneyReady = "true";
    });
  }

  function enhanceTableSemantics(root) {
    root.querySelectorAll(".company-data-table, .company-history-table").forEach((table) => {
      if (table.dataset.semanticTableReady === "true") return;
      const title = clean(
        table.closest(".company-section")?.querySelector(".company-section-head h2")?.textContent,
      );
      table.setAttribute("role", "table");
      table.setAttribute("aria-label", title ? `${title} table` : "Company research table");

      table.querySelectorAll(".company-data-head, .company-history-head").forEach((head) => {
        head.setAttribute("role", "row");
        [...head.children].forEach((cell) => cell.setAttribute("role", "columnheader"));
      });
      table.querySelectorAll(".company-data-row, .company-history-grid").forEach((row) => {
        row.setAttribute("role", "row");
        [...row.children].forEach((cell) => cell.setAttribute("role", "cell"));
      });
      table.dataset.semanticTableReady = "true";
    });
  }

  function polishMetricPeriods(root) {
    root
      .querySelectorAll('[data-company-section="metrics"] .company-data-row')
      .forEach((row) => {
        const period = row.children[4]?.querySelector("strong");
        if (clean(period?.textContent).toLowerCase() === "point in time") {
          period.textContent = "LATEST REPORTED";
        }
      });
  }

  function parseDisplayDate(value) {
    const match = /^(\d{1,2})\s+([A-Z]{3})\s+(\d{4})$/.exec(clean(value).toUpperCase());
    if (!match || !MONTHS[match[2]]) return "";
    return `${match[3]}-${MONTHS[match[2]]}-${match[1].padStart(2, "0")}`;
  }

  function clean(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }
})();
