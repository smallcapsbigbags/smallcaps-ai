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
  function render(card) {
    if (!window.SmallcapsCard) throw new Error("The card could not load. Refresh the page after copying your text.");
    window.SmallcapsCard.render(result, card);
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
