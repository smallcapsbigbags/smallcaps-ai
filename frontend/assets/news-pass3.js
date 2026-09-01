(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const sheet = document.getElementById("sheet-rows");
    const search = document.getElementById("search-filter");
    const filtersToggle = document.getElementById("filters-toggle");
    const filterPanel = document.getElementById("filter-panel");

    if (search) search.setAttribute("aria-keyshortcuts", "/");

    const annotateRows = () => {
      document.querySelectorAll(".monitor-row .row-toggle").forEach((toggle) => {
        toggle.setAttribute("aria-keyshortcuts", "Enter Space Escape");
      });
    };

    annotateRows();

    if (sheet) {
      const observer = new MutationObserver(annotateRows);
      observer.observe(sheet, { childList: true, subtree: true });

      sheet.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) return;
        const row = event.target.closest(".monitor-row");
        if (!row || !sheet.contains(row)) return;
        if (event.target.closest("a, button, input, select, textarea, label")) return;
        if (event.target.closest(".expanded-research")) return;
        if (window.getSelection?.().toString()) return;
        row.querySelector(".row-toggle")?.click();
      });
    }

    document.addEventListener("keydown", (event) => {
      const active = document.activeElement;
      const editing = active instanceof HTMLInputElement
        || active instanceof HTMLTextAreaElement
        || active instanceof HTMLSelectElement
        || active?.getAttribute?.("contenteditable") === "true";

      if (event.key === "/" && !editing && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        search?.focus();
        return;
      }

      if (event.key !== "Escape") return;

      const expandedRow = active instanceof Element
        ? active.closest(".monitor-row[data-expanded=\"true\"]")
        : null;
      if (expandedRow) {
        event.preventDefault();
        const toggle = expandedRow.querySelector(".row-toggle");
        toggle?.click();
        toggle?.focus();
        return;
      }

      if (filterPanel && !filterPanel.hidden) {
        event.preventDefault();
        filtersToggle?.click();
        filtersToggle?.focus();
        return;
      }

      if (active === search && search?.value) {
        event.preventDefault();
        search.value = "";
        search.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
  });
})();
