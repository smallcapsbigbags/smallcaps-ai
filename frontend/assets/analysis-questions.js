/* Source-scoped follow-ups. No saved browser history, HTML injection or paid retries. */
(() => {
  "use strict";
  const section = document.getElementById("questions");
  if (!section) return;
  const form = document.getElementById("question-form");
  const input = document.getElementById("question-text");
  const button = document.getElementById("question-button");
  const label = document.getElementById("question-button-label");
  const message = document.getElementById("question-message");
  const history = document.getElementById("question-history");
  const signIn = document.getElementById("question-sign-in");
  const hint = document.getElementById("question-hint");
  let analysisId = null;
  let generation = 0;
  let busy = false;
  let ready = false;
  let ended = false;
  let turns = [];
  let pending = null;
  let nextIndex = 0;
  let remaining = 8;
  const controllers = new Set();

  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function say(text, error = false) {
    message.textContent = text;
    message.dataset.error = String(error);
  }
  function sync() {
    const size = input.value.trim().length;
    button.disabled = busy || ended || !ready || (remaining <= 0 && !pending) || size < 3 || size > 2000;
    input.disabled = busy;
    label.textContent = busy ? "Thinking…" : pending ? "Check answer" : "Ask";
    form.setAttribute("aria-busy", String(busy));
    hint.textContent = remaining <= 2
      ? remaining > 0 ? `${remaining} ${remaining === 1 ? "question" : "questions"} left for this announcement.` : "Question limit reached for this announcement."
      : "Based on this announcement.";
  }
  function path(suffix = "") {
    return `/api/v1/analyse/${encodeURIComponent(analysisId)}/questions${suffix}`;
  }
  async function request(url, options = {}) {
    const controller = new AbortController();
    controllers.add(controller);
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal, credentials: "same-origin", cache: "no-store" });
      const data = await response.json();
      if (!response.ok) {
        const error = new Error(data.error?.message || "The answer is temporarily unavailable. Your question is still here.");
        error.code = data.error?.code;
        throw error;
      }
      return data;
    } finally {
      clearTimeout(timer);
      controllers.delete(controller);
    }
  }
  function showTurns() {
    history.replaceChildren();
    turns.forEach(turn => {
      const item = node("article", undefined, "question-turn");
      item.dataset.questionId = turn.question_id;
      item.append(node("p", turn.question, "asked-question"));
      const answer = node("div", undefined, "question-answer");
      if (turn.status === "complete" && Array.isArray(turn.result?.paragraphs)) {
        turn.result.paragraphs.forEach(text => answer.append(node("p", text)));
        (turn.result.calculations || []).forEach(fact => {
          const calculation = node("div", undefined, "answer-calculation");
          calculation.append(node("p", `${fact.label}: ${fact.value}`), node("p", fact.note));
          answer.append(calculation);
        });
        if (Array.isArray(turn.result.sources) && turn.result.sources.length) {
          const sources = node("details", undefined, "answer-sources");
          sources.append(node("summary", "Source passages"));
          sources.append(node("p", "From the pasted text; not independently verified.", "answer-source-note"));
          turn.result.sources.forEach(source => sources.append(node("blockquote", source.quote)));
          answer.append(sources);
        }
      } else if (turn.status === "failed") {
        answer.append(node("p", turn.error_code === "REVIEW_REQUIRED"
          ? "We couldn’t support a reliable answer from this text. Try a more specific question."
          : "This answer wasn’t completed. Your announcement is unchanged.", "answer-failure"));
      } else {
        answer.append(node("p", "Thinking…", "answer-pending"));
      }
      item.append(answer);
      history.append(item);
    });
  }
  function acceptTurn(turn) {
    if (!turn?.question_id || !Number.isInteger(turn.turn_index)) throw new Error("The answer could not be loaded. Your question is still here.");
    const old = turns.findIndex(item => item.question_id === turn.question_id);
    if (old >= 0) turns[old] = turn;
    else turns.push(turn);
    turns.sort((a, b) => a.turn_index - b.turn_index);
    nextIndex = Math.max(nextIndex, turn.turn_index + 1);
    remaining = Math.max(0, 8 - nextIndex);
    showTurns();
  }
  async function loadHistory(g) {
    const data = await request(path());
    if (g !== generation) return false;
    if (!Array.isArray(data.turns) || !Number.isInteger(data.next_turn_index)) throw new Error("Questions are temporarily unavailable.");
    turns = data.turns;
    nextIndex = data.next_turn_index;
    remaining = data.remaining;
    ready = true;
    showTurns();
    return true;
  }
  function handleError(error) {
    if (error.code === "AUTH_REQUIRED") signIn.hidden = false;
    if (error.code === "NOT_FOUND" || error.code === "CHAT_DISABLED" || error.code === "ANALYSIS_DISABLED") ended = true;
    say(error.name === "AbortError" || error instanceof TypeError
      ? "Connection interrupted. Your question is still here. Check the answer again."
      : error.message, true);
  }
  function reset() {
    generation += 1;
    controllers.forEach(controller => controller.abort());
    section.hidden = true;
    analysisId = null;
    ready = busy = ended = false;
    turns = [];
    pending = null;
    nextIndex = 0;
    remaining = 8;
    input.value = "";
    history.replaceChildren();
    signIn.hidden = true;
    say("");
    sync();
  }
  async function attach(id) {
    reset();
    if (typeof id !== "string" || !id) return;
    analysisId = id;
    section.hidden = false;
    const g = generation;
    busy = true;
    sync();
    try {
      await loadHistory(g);
    } catch (error) {
      if (g === generation) {
        handleError(error);
        // A user may explicitly try again; never auto-start a model request.
        ready = !ended;
      }
    } finally {
      if (g === generation) { busy = false; sync(); }
    }
  }
  input.addEventListener("input", () => {
    if (pending && input.value.trim() !== pending.question) pending = null;
    say(input.value.length > 2000 ? "Keep your question under 2,000 characters." : "", input.value.length > 2000);
    sync();
  });
  input.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !button.disabled) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (button.disabled || !analysisId) return;
    const g = generation;
    busy = true;
    signIn.hidden = true;
    say("");
    sync();
    try {
      // Read the authoritative conversation before every explicit submission. This
      // finds a lost POST response and detects stale tabs without another paid call.
      if (!await loadHistory(g)) return;
      const active = turns.find(turn => turn.status === "processing");
      let turn = pending ? turns.find(item => item.request_id === pending.request_id) : null;
      if (!turn && active) {
        throw new Error("Another question is being answered. Your question is still here; try again shortly.");
      }
      if (!turn) {
        if (remaining <= 0) { say("Question limit reached for this announcement."); return; }
        pending = pending || { question: input.value.trim(), request_id: crypto.randomUUID(), turn_index: nextIndex };
        turn = await request(path(), { method: "POST", headers: { "Content-Type": "application/json", "X-Smallcaps-Action": "ask" }, body: JSON.stringify(pending) });
        if (g !== generation) return;
      }
      acceptTurn(turn);
      const start = Date.now();
      while (turn.status === "processing") {
        if (Date.now() - start > 150000) throw new Error("This is taking longer than expected. Check the same answer again shortly.");
        await new Promise(resolve => setTimeout(resolve, 1200));
        if (g !== generation) return;
        turn = await request(path(`/${encodeURIComponent(turn.question_id)}`));
        if (g !== generation) return;
      }
      acceptTurn(turn);
      pending = null;
      if (turn.status === "complete") {
        input.value = "";
        say("Answer ready.");
      } else {
        say(turn.error_code === "REVIEW_REQUIRED" ? "We couldn’t support a reliable answer. Your question is still here."
          : "The answer wasn’t completed. Your question is still here.", true);
      }
    } catch (error) {
      if (g !== generation) return;
      if (["CONVERSATION_CHANGED", "INVALID_INPUT", "QUESTIONS_BUSY", "AUTH_REQUIRED", "CHAT_DISABLED"].includes(error.code)) pending = null;
      handleError(error);
    } finally {
      if (g === generation) { busy = false; sync(); }
    }
  });
  sync();
  window.SmallcapsQuestions = Object.freeze({attach, reset});
})();
