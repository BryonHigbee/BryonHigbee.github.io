// Renders DiskNCM progress from status.json (published by the DiskNCM harness).
// Shows only phase names, statuses, percentages and to-do titles.
// Refreshes every 60 seconds and whenever the tab becomes visible again.
(() => {
  const phaseList = document.getElementById("phase-list");
  const todoCard = document.getElementById("todo-card");
  const todoList = document.getElementById("todo-list");
  const updated = document.getElementById("status-updated");

  const PHASE_LABEL = { active: "In progress", review: "In review", stopped: "Stopped", passed: "Complete", pending: "" };
  const TODO_LABEL = { todo: "To do", doing: "Doing", done: "Done", blocked: "Blocked" };

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const pct = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  // older status files used "done" for finished phases
  const phaseStatus = (s) => (s === "done" ? "passed" : PHASE_LABEL[s] !== undefined ? s : "pending");

  function renderPhases(phases, current) {
    phaseList.replaceChildren(
      ...phases.map((p, i) => {
        const status = phaseStatus(p.status);
        const isCurrent = (i === current || status === "active") && status !== "passed";
        const progress = status === "passed" ? 100 : pct(p.progress);

        const li = el("li", `phase phase--${status}` + (isCurrent ? " phase--current" : ""));
        if (isCurrent) li.setAttribute("aria-current", "step");

        const dot = el("span", "phase-dot");
        dot.setAttribute("aria-hidden", "true");
        const body = el("div", "phase-body");
        const head = el("div", "phase-head");
        head.append(
          el("span", "phase-tag", `Phase ${i}`),
          el("span", "phase-name", p.name),
          el("span", "phase-pct", status === "pending" ? "" : `${progress}%`)
        );
        body.append(head);

        if (isCurrent) {
          const bar = el("div", "phase-bar");
          bar.setAttribute("role", "progressbar");
          bar.setAttribute("aria-label", `Phase ${i} progress`);
          bar.setAttribute("aria-valuemin", "0");
          bar.setAttribute("aria-valuemax", "100");
          bar.setAttribute("aria-valuenow", String(progress));
          const fill = el("span");
          fill.style.width = `${progress}%`;
          bar.append(fill);
          body.append(bar, el("span", "phase-state", PHASE_LABEL[status]));
        }
        li.append(dot, body);
        return li;
      })
    );
  }

  function renderTodos(todos) {
    // status files from before to-dos existed have no "todos" key: hide the card
    todoCard.hidden = !Array.isArray(todos);
    if (todoCard.hidden) return;
    if (todos.length === 0) {
      todoList.replaceChildren(el("li", "todo todo--empty", "Nothing listed right now."));
      return;
    }
    todoList.replaceChildren(
      ...todos.map((t) => {
        const status = TODO_LABEL[t.status] ? t.status : "todo";
        const li = el("li", `todo todo--${status}`);
        li.append(el("span", "todo-title", t.title), el("span", `chip chip--${status}`, TODO_LABEL[status]));
        return li;
      })
    );
  }

  function render(status) {
    renderPhases(Array.isArray(status.phases) ? status.phases : [], Number(status.current));
    renderTodos(status.todos);
    const when = new Date(status.updated);
    updated.textContent = Number.isNaN(when.getTime()) ? "" : `Updated ${when.toLocaleString()}`;
  }

  let hasRendered = false;
  async function refresh() {
    try {
      const res = await fetch(`status.json?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      render(await res.json());
      hasRendered = true;
    } catch {
      // keep the last good render; try again on the next tick
      if (!hasRendered) updated.textContent = "Status is unavailable right now.";
    }
  }

  refresh();
  setInterval(refresh, 60_000);
  document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && refresh());
})();
