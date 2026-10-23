// Renders Project Synapse phase progress from status.json (written by the Synapse harness).
// Shows only phase names, status and percentages. Refreshes every 60 seconds.
(() => {
  const list = document.getElementById("phase-list");
  const updated = document.getElementById("phase-updated");
  const LABEL = { passed: "Complete", active: "In progress", review: "In review", stopped: "Stopped", pending: "" };

  function render(status) {
    list.replaceChildren(
      ...status.phases.map((p, i) => {
        const li = document.createElement("li");
        li.className = `phase phase--${p.status}` + (i === status.current ? " phase--current" : "");
        if (i === status.current) li.setAttribute("aria-current", "step");

        const dot = document.createElement("span");
        dot.className = "phase-dot";
        dot.setAttribute("aria-hidden", "true");

        const body = document.createElement("div");
        body.className = "phase-body";
        const head = document.createElement("div");
        head.className = "phase-head";
        const tag = document.createElement("span");
        tag.className = "phase-tag";
        tag.textContent = `Phase ${i}`;
        const name = document.createElement("span");
        name.className = "phase-name";
        name.textContent = p.name;
        const pct = document.createElement("span");
        pct.className = "phase-pct";
        pct.textContent = p.status === "pending" ? "" : `${p.progress}%`;
        head.append(tag, name, pct);
        body.append(head);

        if (i === status.current && p.status !== "passed") {
          const bar = document.createElement("div");
          bar.className = "phase-bar";
          bar.setAttribute("role", "progressbar");
          bar.setAttribute("aria-valuemin", "0");
          bar.setAttribute("aria-valuemax", "100");
          bar.setAttribute("aria-valuenow", String(p.progress));
          const fill = document.createElement("span");
          fill.style.width = `${p.progress}%`;
          bar.append(fill);
          const label = document.createElement("span");
          label.className = "phase-state";
          label.textContent = LABEL[p.status] || "";
          body.append(bar, label);
        }
        li.append(dot, body);
        return li;
      })
    );
    updated.textContent = "Updated " + new Date(status.updated).toLocaleString();
  }

  async function refresh() {
    try {
      const res = await fetch(`status.json?t=${Date.now()}`, { cache: "no-store" });
      if (res.ok) render(await res.json());
    } catch {
      /* keep the last good render; try again on the next tick */
    }
  }

  refresh();
  setInterval(refresh, 60_000);
  document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && refresh());
})();
