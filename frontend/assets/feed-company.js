(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("sheet-rows");
    if (!root) return;

    const enhance = () => {
      root.querySelectorAll("article.monitor-row").forEach((row) => {
        const tickerNode = row.querySelector(".ticker");
        const line = row.querySelector(".ticker-line");
        const ticker = String(tickerNode?.textContent || "").trim().toUpperCase();
        if (!ticker || !line) return;

        if (!line.querySelector(".company-research-link")) {
          const link = document.createElement("a");
          link.className = "company-research-link";
          link.href = `/company/${encodeURIComponent(ticker)}`;
          link.setAttribute("aria-label", `Open ${ticker} Company Intelligence`);
          while (line.firstChild) link.append(line.firstChild);
          line.append(link);
        }

        const top = row.querySelector(".expanded-topline");
        if (top && !top.querySelector(".company-inline-link")) {
          const link = document.createElement("a");
          link.className = "company-inline-link";
          link.href = `/company/${encodeURIComponent(ticker)}`;
          link.textContent = "COMPANY RESEARCH →";
          const source = top.querySelector(".source-link");
          if (source) top.insertBefore(link, source);
          else top.append(link);
        }
      });
    };

    enhance();
    new MutationObserver(enhance).observe(root, { childList: true, subtree: true });
  });
})();
