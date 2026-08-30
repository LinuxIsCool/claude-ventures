// web/static/studio.js
// Studio tab for the venture detail page: app Library and Domains.
// Reads one document: api/venture/<slug>/studio. No network calls of its own
// beyond that fetch; live health arrives in a later phase.
(function () {
  const badge = (esc, text, tone) => `<span class="badge ${tone || ""}">${esc(text)}</span>`;
  const remoteHref = (remote) => remote ? `https://github.com/${remote}` : "";

  // Manifests are data, not code; only http and https may become links.
  function safeHref(url) {
    try { return /^https?:$/i.test(new URL(url, location.href).protocol) ? url : "#"; }
    catch (_) { return "#"; }
  }

  function gitLine(esc, g) {
    if (g === null || g === undefined) return `<span class="text-subtext">no repo declared</span>`;
    if (!g.ok) return `<span class="text-subtext">${esc(g.reason)}: ${esc(g.path)}</span>`;
    const dirty = g.dirty ? `<span class="text-yellow">${esc(g.dirty)} changed</span>` : `<span class="text-green">clean</span>`;
    const wt = g.worktrees > 1 ? ` · ${esc(g.worktrees)} worktrees` : "";
    const when = g.last_commit ? ` · last commit ${esc(g.last_commit.slice(0, 10))}` : "";
    return `<span class="text-blue">${esc(g.branch)}</span> @ <code>${esc(g.head)}</code> · ${dirty}${wt}${when} · ${esc(g.vcs)}`;
  }

  function envRows(esc, envs, opts, a) {
    if (!envs.length) return `<p class="text-subtext text-xs">no environments declared</p>`;
    return `<table class="studio-table text-xs"><thead><tr><th>env</th><th>url</th><th>host</th><th>deploy</th><th>status</th><th>live</th><th>control</th><th>actions</th></tr></thead><tbody>` +
      envs.map(e => `<tr>
        <td>${esc(e.name)}</td>
        <td>${e.url ? `<a class="text-blue" href="${esc(safeHref(e.url))}" target="_blank" rel="noopener">${esc(e.url)}</a>` : `<span class="text-subtext">none</span>`}</td>
        <td>${esc(e.host || "")}</td>
        <td>${esc(e.deploy || "")}</td>
        <td>${badge(esc, e.status || "declared")}</td>
        <td>${liveBadge(esc, e.live, opts.stale, opts.nowMs)}</td>
        <td>${e.controllable ? badge(esc, "controllable", "text-green") : `<span class="text-subtext">read only</span>`}</td>
        <td>${actionButtons(esc, a, e)}</td>
      </tr>`).join("") + `</tbody></table>`;
  }

  function appCard(esc, a, opts) {
    const repo = a.repo || {};
    const remote = repo.remote ? `<a class="text-blue" href="${esc(safeHref(remoteHref(repo.remote)))}" target="_blank" rel="noopener">${esc(repo.remote)}</a>` : "";
    const deps = (a.depends_on || []).map(d => badge(esc, d)).join(" ");
    const runtime = a.runtime && a.runtime.kind && a.runtime.kind !== "none"
      ? `<div class="text-xs text-subtext mt-1">runtime: ${esc(a.runtime.kind)}${a.runtime.project ? ` · ${esc(a.runtime.project)}` : ""}${a.runtime.hostname ? ` · ${esc(a.runtime.hostname)}` : ""}</div>` : "";
    return `<article class="ui-card mb-2">
      <div class="flex items-center gap-2">
        <span class="font-pixel text-xs text-green">${esc(a.name || a.slug)}</span>
        ${badge(esc, a.kind || "app")} ${badge(esc, a.stage || "")}
        ${a.project ? `<span class="text-subtext text-xs">project: ${esc(a.project)}</span>` : ""}
      </div>
      <div class="text-xs mt-1"><code>${esc(repo.path || "")}</code> ${remote}</div>
      <div class="text-xs mt-1">${gitLine(esc, a.git)}</div>
      ${a.run ? `<div class="text-xs mt-1 text-subtext">run: <code>${esc(a.run)}</code>${a.test ? ` · test: <code>${esc(a.test)}</code>` : ""}</div>` : ""}
      ${a.status_doc ? `<div class="text-xs text-subtext">status doc: <code>${esc(a.status_doc)}</code></div>` : ""}
      <div class="mt-2">${envRows(esc, a.environments || [], opts, a)}</div>
      ${containerChips(esc, a.live)}
      ${deps ? `<div class="text-xs mt-2">depends on ${deps}</div>` : ""}
      ${runtime}
      ${a.notes ? `<p class="text-xs text-subtext mt-2">${esc(a.notes)}</p>` : ""}
    </article>`;
  }

  function domainRows(esc, domains) {
    if (!domains.length) return `<p class="text-subtext text-xs">no domains declared; add environments[].url to an app manifest</p>`;
    return `<table class="studio-table text-xs"><thead><tr><th>host</th><th>app</th><th>env</th><th>status</th><th>cert</th><th>control</th></tr></thead><tbody>` +
      domains.map(d => `<tr>
        <td><a class="text-blue" href="${esc(safeHref(d.url))}" target="_blank" rel="noopener">${esc(d.host)}</a></td>
        <td>${esc(d.app)}</td><td>${esc(d.env)}</td>
        <td>${badge(esc, d.status)}</td>
        <td>${certBadge(esc, d.cert)}</td>
        <td>${d.controllable ? badge(esc, "controllable", "text-green") : `<span class="text-subtext">read only</span>`}</td>
      </tr>`).join("") + `</tbody></table>`;
  }

  // ---- Network section: tasks as a dependency DAG ---------------------------
  const VENDOR = ["static/vendor/cytoscape.min.js", "static/vendor/dagre.min.js", "static/vendor/cytoscape-dagre.js"];
  let vendorPromise = null;
  function loadVendor() {
    if (window.cytoscape && window.dagre) return Promise.resolve(true);
    if (vendorPromise) return vendorPromise;
    vendorPromise = VENDOR.reduce((p, src) => p.then(() => new Promise((res, rej) => {
      const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = () => rej(new Error(src));
      document.head.appendChild(s);
    })), Promise.resolve()).then(() => {
      if (window.cytoscape && window.dagre && window.cytoscapeDagre) window.cytoscape.use(window.cytoscapeDagre);
      return !!(window.cytoscape && window.dagre);
    }).catch(() => false);
    return vendorPromise;
  }

  const PROJECT_COLOURS = ["#89b4fa", "#a6e3a1", "#f9e2af", "#fab387", "#cba6f7", "#94e2d5", "#f38ba8", "#b4befe"];
  const PRIORITY_BORDER = { critical: "#f38ba8", high: "#fab387", medium: "#89b4fa", low: "#7f849c" };

  function projectColour(index) { return PROJECT_COLOURS[index % PROJECT_COLOURS.length]; }

  function renderFallbackList(esc, net) {
    const byRank = {};
    net.nodes.forEach(n => { const r = net.ranks[n.id] || 0; (byRank[r] = byRank[r] || []).push(n); });
    return `<p class="text-xs text-subtext mb-2">Graph library unavailable; showing tasks by dependency depth.</p>` +
      Object.keys(byRank).sort((a, b) => a - b).map(r => `<div class="mb-2"><div class="text-xs text-subtext">depth ${esc(r)}</div>` +
        byRank[r].map(n => `<a class="flex items-center gap-2 text-xs" href="${esc(safeHref(n.href))}">
          <span class="text-subtext">#${esc(n.id)}</span><span class="flex-1">${esc(n.title)}</span>
          ${n.external ? badge(esc, n.venture || "missing") : badge(esc, n.project)}${badge(esc, n.status)}</a>`).join("") + `</div>`).join("");
  }

  function drawGraph(container, net, opts) {
    const projectIndex = {};
    net.groups.projects.forEach((g, i) => projectIndex[g.key] = i);
    const onPath = new Set(opts.critical ? net.critical_path : []);
    const visible = new Set(net.nodes.filter(n => !opts.project || n.external || n.project === opts.project).map(n => n.id));
    const touched = new Set();
    net.edges.forEach(e => { if (visible.has(e.source) && visible.has(e.target)) { touched.add(e.source); touched.add(e.target); } });
    if (!opts.isolated) {
      net.nodes.forEach(n => { if (!n.external && !touched.has(n.id)) visible.delete(n.id); });
    }
    if (!visible.size) {
      container.innerHTML = `<p class="text-subtext text-xs">no dependency edges among open tasks; tick "show without dependencies" to list them</p>`;
      return null;
    }
    const elements = [];
    net.nodes.forEach(n => { if (!visible.has(n.id)) return; elements.push({ data: {
      id: n.id, label: `#${n.id} ${n.title.length > 38 ? n.title.slice(0, 37) + "…" : n.title}`,
      colour: n.external ? "#313244" : projectColour(projectIndex[n.project] || 0),
      border: n.external ? "#7f849c" : (PRIORITY_BORDER[n.priority] || "#89b4fa"),
      dashed: n.external ? "dashed" : "solid", faded: n.done ? 0.45 : 1, path: onPath.has(n.id) ? 1 : 0, href: n.href } }); });
    net.edges.forEach(e => { if (visible.has(e.source) && visible.has(e.target)) elements.push({ data: {
      id: e.source + "->" + e.target, source: e.source, target: e.target, path: onPath.has(e.source) && onPath.has(e.target) ? 1 : 0 } }); });
    const cy = window.cytoscape({ container, elements,
      style: [
        { selector: "node", style: { "background-color": "data(colour)", "border-color": "data(border)", "border-width": 2,
          "border-style": "data(dashed)", label: "data(label)", "font-size": 9, "font-family": "monospace", color: "#cdd6f4",
          "text-wrap": "wrap", "text-max-width": 140, "text-valign": "center", shape: "round-rectangle", width: 150, height: 34,
          opacity: "data(faded)" } },
        { selector: "node[path = 1]", style: { "border-width": 4, "border-color": "#f9e2af" } },
        { selector: "edge", style: { width: 1.5, "line-color": "#585b70", "target-arrow-color": "#585b70",
          "target-arrow-shape": "triangle", "curve-style": "bezier" } },
        { selector: "edge[path = 1]", style: { width: 3, "line-color": "#f9e2af", "target-arrow-color": "#f9e2af" } },
      ],
      layout: { name: "dagre", rankDir: "TB", nodeSep: 18, rankSep: 48, fit: false } });
    cy.zoom(0.8); cy.pan({ x: 20, y: 20 });
    container.style.height = Math.min(1400, Math.max(560, Math.ceil(cy.elements().boundingBox().h * 0.8) + 60)) + "px";
    cy.resize();
    cy.on("tap", "node", evt => { const href = safeHref(evt.target.data("href")); if (href !== "#") window.location.assign(href); });
    return cy;
  }

  async function renderNetwork(section, slug, helpers) {
    const { api, esc } = helpers;
    const state = { project: "", done: false, critical: false, isolated: false };
    section.innerHTML = `<p class="text-subtext text-xs">loading network…</p>`;
    let net;
    let cy = null;
    const load = async () => { net = await api("api/venture/" + encodeURIComponent(slug) + "/network" + (state.done ? "?done=1" : "")); };
    try { await load(); } catch (e) { section.innerHTML = `<p class="text-xs text-yellow">network unavailable: ${esc(e && e.message ? e.message : String(e))}</p>`; return; }
    const hasLib = await loadVendor();
    const paint = () => {
      if (cy) { cy.destroy(); cy = null; }
      const touched = new Set();
      net.edges.forEach(e => { touched.add(e.source); touched.add(e.target); });
      const isolatedCount = net.nodes.filter(n => !n.external && !touched.has(n.id)).length;
      const legend = net.groups.projects.map((g, i) => `<span class="studio-legend-item"><i style="background:${projectColour(i)}"></i>${esc(g.key)} (${esc(g.count)})</span>`).join("");
      section.innerHTML = `<div class="flex items-center gap-2 text-xs mb-2 flex-wrap">
          <select class="input" data-project><option value="">all projects</option>${net.groups.projects.map(g => `<option value="${esc(g.key)}" ${state.project === g.key ? "selected" : ""}>${esc(g.key)}</option>`).join("")}</select>
          <label><input type="checkbox" data-done ${state.done ? "checked" : ""}> include done</label>
          <label><input type="checkbox" data-critical ${state.critical ? "checked" : ""}> critical path (${esc(net.critical_path.length)})</label>
          <label><input type="checkbox" data-isolated ${state.isolated ? "checked" : ""}> show ${esc(isolatedCount)} without dependencies</label>
          <button type="button" class="toolbar-action" data-fit>fit</button>
          <span class="text-subtext">${esc(net.counts.nodes)} tasks · ${esc(net.counts.edges)} edges · ${esc(net.counts.external)} external${net.counts.cycles ? ` · <span class="text-yellow">${esc(net.counts.cycles)} cycle edge(s) dropped</span>` : ""}</span>
        </div><div class="studio-legend mb-2">${legend}<span class="studio-legend-item"><i style="background:#313244;border:1px dashed #7f849c"></i>other venture / missing</span></div>
        <div class="studio-network" data-canvas></div>`;
      const canvas = section.querySelector("[data-canvas]");
      if (hasLib && net.nodes.length) cy = drawGraph(canvas, net, state);
      else canvas.innerHTML = net.nodes.length ? renderFallbackList(esc, net) : `<p class="text-subtext text-xs">no open tasks with dependencies for this venture</p>`;
      section.querySelector("[data-project]").onchange = e => { state.project = e.target.value; paint(); };
      section.querySelector("[data-critical]").onchange = e => { state.critical = e.target.checked; paint(); };
      section.querySelector("[data-isolated]").onchange = e => { state.isolated = e.target.checked; paint(); };
      section.querySelector("[data-done]").onchange = async e => { state.done = e.target.checked; await load(); paint(); };
      section.querySelector("[data-fit]").onclick = () => { if (cy) cy.fit(undefined, 20); };
    };
    paint();
  }

  // ---- Meetings section: catalogue from meetings.db -------------------------
  function meetingDetails(esc, m) {
    const list = (title, rows, fmt) => rows.length ? `<div class="mt-2"><div class="text-subtext text-xs">${title} (${esc(rows.length)})</div>` +
      rows.map(r => `<div class="text-xs studio-meeting-item">${fmt(r)}${r.quote ? `<div class="text-subtext studio-quote">“${esc(r.quote)}”</div>` : ""}</div>`).join("") + `</div>` : "";
    return list("Decisions", m.decisions, r => `${esc(r.text)} ${badge(esc, r.type)}${r.reversibility && r.reversibility !== "unknown" ? " " + badge(esc, r.reversibility) : ""}`)
      + list("Risks", m.risks, r => `${esc(r.text)} ${badge(esc, r.severity)}${r.mitigation ? `<div class="text-subtext">mitigation: ${esc(r.mitigation)}</div>` : ""}`)
      + list("Action items", m.actions, r => `${esc(r.text)} ${badge(esc, r.status, r.status === "open" ? "text-yellow" : "")}${r.assignee ? ` <span class="text-subtext">${esc(r.assignee)}</span>` : ""}${r.deadline ? ` <span class="text-subtext">${esc(r.deadline)}</span>` : ""}${r.backlog_task_id ? ` <a class="text-blue" href="${esc(safeHref("/backlog/tasks/" + r.backlog_task_id))}">#${esc(r.backlog_task_id)}</a>` : ""}`)
      || `<p class="text-subtext text-xs mt-2">nothing extracted for this meeting yet</p>`;
  }

  // Summaries are stored as markdown; strip the markup we do not want to
  // render literally and cap the length before esc() runs on the result.
  function plainSummary(text) {
    const stripped = String(text || "")
      .split("\n").map(line => line.replace(/^#{1,6}\s*/, "")).join("\n")
      .replace(/\*\*|__/g, "")
      .replace(/\s+/g, " ")
      .trim();
    return stripped.length > 600 ? stripped.slice(0, 600) + "…" : stripped;
  }

  function meetingRows(esc, items) {
    if (!items.length) return `<p class="text-subtext text-xs">no meetings match</p>`;
    return `<table class="studio-table text-xs studio-meetings"><thead><tr><th></th><th>date</th><th>title</th><th>source</th><th>status</th><th>D</th><th>R</th><th>A</th><th>min</th></tr></thead><tbody>` +
      items.map(m => `<tr data-expand="${esc(m.id)}">
          <td><button type="button" class="toolbar-action" aria-label="expand">+</button></td>
          <td>${esc(m.date)}</td>
          <td>${m.transcript_href ? `<a class="text-blue" href="${esc(safeHref(m.transcript_href))}">${esc(m.title)}</a>` : esc(m.title)}</td>
          <td>${esc(m.source)}</td><td>${badge(esc, m.status)}</td>
          <td>${esc(m.counts.decisions)}</td><td>${esc(m.counts.risks)}</td>
          <td>${esc(m.counts.actions_open)}/${esc(m.counts.actions_total)}</td>
          <td>${m.duration_min == null ? "" : esc(m.duration_min)}</td>
        </tr><tr class="studio-meeting-detail" hidden><td></td><td colspan="8">${m.summary ? `<p class="text-xs">${esc(plainSummary(m.summary))}</p>` : ""}${meetingDetails(esc, m)}</td></tr>`).join("") + `</tbody></table>`;
  }

  async function renderMeetings(section, slug, helpers) {
    const { api, esc } = helpers;
    let q = "";
    const load = () => api("api/venture/" + encodeURIComponent(slug) + "/meetings" + (q ? "?q=" + encodeURIComponent(q) : ""));
    const paint = async () => {
      section.innerHTML = `<p class="text-subtext text-xs">loading meetings…</p>`;
      let doc;
      try { doc = await load(); } catch (e) { section.innerHTML = `<p class="text-xs text-yellow">meetings unavailable: ${esc(e && e.message ? e.message : String(e))}</p>`; return; }
      if (!doc.available) { section.innerHTML = `<p class="text-xs text-subtext">meetings unavailable: ${esc(doc.reason)}</p>`; return; }
      const a = doc.aggregates;
      section.innerHTML = `<form class="flex items-center gap-2 text-xs mb-2" data-meeting-search>
          <input class="input" name="q" value="${esc(q)}" placeholder="search title, summary, agenda">
          <button type="submit" class="toolbar-action">search</button>
          <span class="text-subtext">${esc(a.meetings)} meetings · ${esc(a.decisions)} decisions · ${esc(a.risks)} risks · ${esc(a.actions_open)} open actions${doc.fts ? "" : " · plain search (no FTS)"}</span>
        </form>
        ${meetingRows(esc, doc.items)}
        ${doc.untagged ? `<p class="text-subtext text-xs mt-2">${esc(doc.untagged)} meetings in the corpus carry no venture tag and cannot appear here.</p>` : ""}`;
      section.querySelector("[data-meeting-search]").onsubmit = e => { e.preventDefault(); q = e.target.q.value.trim(); paint(); };
      section.querySelectorAll("tr[data-expand]").forEach(tr => tr.querySelector("button").onclick = () => {
        const detail = tr.nextElementSibling; detail.hidden = !detail.hidden; tr.querySelector("button").textContent = detail.hidden ? "+" : "-";
      });
    };
    await paint();
  }

  // ---- live badges from the poller snapshot --------------------------------
  function ageText(iso, nowMs) {
    const t = Date.parse(iso);
    if (!iso || Number.isNaN(t)) return "";
    const s = Math.max(0, Math.round((nowMs - t) / 1000));
    return s < 90 ? `${s}s ago` : s < 5400 ? `${Math.round(s / 60)}m ago` : `${Math.round(s / 3600)}h ago`;
  }
  function liveBadge(esc, live, stale, nowMs) {
    if (!live) return `<span class="text-subtext">no probe</span>`;
    const tone = live.ok ? (live.decided_by === "gated" ? "text-blue" : "text-green") : "text-yellow";
    const label = live.ok ? (live.decided_by === "gated" ? "gated" : "up") : (live.decided_by === "error" ? "down" : `http ${live.status}`);
    const title = `${live.probe || ""} · ${live.decided_by} · ${live.elapsed_ms} ms${live.error ? " · " + live.error : ""}`;
    return `<span class="badge ${tone} ${stale ? "studio-stale" : ""}" title="${esc(title)}">${esc(label)}${live.status && live.decided_by !== "error" ? ` ${esc(live.status)}` : ""}</span> <span class="text-subtext">${esc(ageText(live.checked_at, nowMs))}${stale ? " · stale" : ""}</span>`;
  }
  function certBadge(esc, cert) {
    if (!cert) return `<span class="text-subtext">http</span>`;
    if (cert.error) return `<span class="badge text-yellow" title="${esc(cert.error)}">cert ?</span>`;
    const tone = cert.days_left < 14 ? "text-yellow" : "text-green";
    return `<span class="badge ${tone}" title="${esc(cert.not_after || "")}">${esc(cert.days_left)}d</span>`;
  }
  function containerChips(esc, live) {
    if (!live) return "";
    if (live.containers_error) return `<div class="text-xs text-yellow mt-1">containers: ${esc(live.containers_error)}</div>`;
    if (!live.containers.length) return `<div class="text-xs text-subtext mt-1">no containers carry this app's legion labels</div>`;
    return `<div class="text-xs mt-1 studio-live">` + live.containers.map(c => {
      const tone = c.state === "running" ? (c.health === "unhealthy" ? "text-yellow" : "text-green") : "text-subtext";
      return `<span class="badge ${tone}" title="${esc(c.status || "")}">${esc(c.name)}${c.env ? ` · ${esc(c.env)}` : ""} · ${esc(c.state)}${c.health && c.health !== "none" ? ` · ${esc(c.health)}` : ""}</span>`;
    }).join(" ") + `</div>`;
  }

  // ---- actions (studio-actions satellite; declared-only, dev only) ----------
  const ACTIONS_URL = "/studio-actions/api/mutate";
  async function mutate(tool, args) {
    const r = await fetch(ACTIONS_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool, args }) });
    let body = null; try { body = await r.json(); } catch (_) { body = null; }
    if (r.status === 404 && !body) return { unavailable: true, message: "studio-actions mount is not running" };
    if (!r.ok) return { error: (body && (body.code || body.error || body.message)) || `HTTP ${r.status}`, body };
    return body.result || body;
  }
  function actionButtons(esc, a, e) {
    if (!(e.controllable && a.runtime && a.runtime.kind === "compose")) return "";
    const d = `data-venture="${esc(a.venture)}" data-app="${esc(a.slug)}" data-env="${esc(e.name)}"`;
    return `<span class="studio-actions">
      <button type="button" class="toolbar-action" data-action="status" ${d}>status</button>
      <button type="button" class="toolbar-action" data-action="start" ${d}>start</button>
      <button type="button" class="toolbar-action" data-action="stop" ${d}>stop</button>
      <button type="button" class="toolbar-action" data-action="logs" ${d}>logs</button>
      <button type="button" class="toolbar-action" data-action="shell" ${d}>shell</button>
    </span>`;
  }
  function renderLogs(esc, out) {
    if (out.unavailable) return `<p class="text-xs text-yellow">${esc(out.message)}</p>`;
    if (out.error) return `<p class="text-xs text-yellow">refused: ${esc(out.error)}</p>`;
    if (out.containers) return `<div class="text-xs">${out.containers.length ? out.containers.map(c => badge(esc, `${c.name} · ${c.state}${c.health ? " · " + c.health : ""}`)).join(" ") : "no containers for this project"}</div>`;
    if (out.lines) return `<pre class="studio-log">${esc(out.lines.join("\n"))}</pre>`;
    if (out.url) return `<p class="text-xs">shell opened: <a class="text-blue" href="${esc(safeHref(out.url))}" target="_blank" rel="noopener">${esc(out.url)}</a> (expires in ${esc(Math.round((out.expires_at * 1000 - Date.now()) / 60000))} min)</p>`;
    return `<p class="text-xs">${out.ok ? "ok" : "failed"} · exit ${esc(out.exit)}${out.elapsed_ms != null ? ` · ${esc(Math.round(out.elapsed_ms))} ms` : ""}${out.output_tail ? `<pre class="studio-log">${esc(out.output_tail)}</pre>` : ""}${out.error ? `<span class="text-yellow"> ${esc(out.error)}</span>` : ""}</p>`;
  }
  function wireActions(root, esc) {
    root.querySelectorAll("[data-action]").forEach(btn => btn.onclick = async () => {
      const { action, venture, app, env } = btn.dataset;
      const card = btn.closest("article"); let panel = card.querySelector("[data-action-output]");
      if (!panel) { panel = document.createElement("div"); panel.setAttribute("data-action-output", ""); panel.className = "mt-2"; card.appendChild(panel); }
      if (action === "stop" && !window.confirm(`Stop ${app} ${env}? (compose stop; volumes untouched)`)) return;
      panel.innerHTML = `<p class="text-xs text-subtext">${esc(action)}…</p>`;
      const tool = action === "shell" ? "studio_shell_open" : `studio_${action}`;
      const args = action === "shell" ? { venture, app } : { venture, app, env };
      const out = await mutate(tool, args);
      panel.innerHTML = renderLogs(esc, out);
      if (out.url) window.open(safeHref(out.url), "_blank", "noopener");
    });
  }

  async function mount(root, slug, helpers) {
    const { api, esc } = helpers;
    root.innerHTML = `<p class="text-subtext text-xs">loading studio…</p>`;
    let doc;
    try { doc = await api("api/venture/" + encodeURIComponent(slug) + "/studio"); }
    catch (e) { root.innerHTML = `<p class="text-xs text-yellow">studio unavailable: ${esc(e && e.message ? e.message : String(e))}</p>`; return; }
    if (doc.error) { root.innerHTML = `<p class="text-xs text-yellow">studio: ${esc(doc.error)}</p>`; return; }
    const errors = (doc.errors || []).length
      ? `<p class="text-xs text-yellow mb-2">skipped unreadable manifests: ${doc.errors.map(esc).join(", ")}</p>` : "";
    const nowMs = Date.now();
    const stale = doc.snapshot.stale;
    const opts = { stale, nowMs };
    root.innerHTML = `<div class="studio-grid">
      <section>
        <h2 class="font-pixel text-xs text-green mb-2">Library (${esc(doc.counts.apps)})</h2>
        <div class="text-xs text-subtext mb-2" data-snapshot-age>${doc.snapshot.present ? `live snapshot ${esc(ageText(doc.snapshot.generated_at, nowMs))}${stale ? " (stale)" : ""}` : "no live snapshot yet: the poller has not run"}</div>
        ${errors}
        ${doc.apps.length ? doc.apps.map(a => appCard(esc, a, opts)).join("")
          : `<p class="text-subtext text-xs">no apps yet; create one with the app_create MCP tool</p>`}
      </section>
      <section>
        <h2 class="font-pixel text-xs text-green mb-2">Domains (${esc(doc.counts.domains)})</h2>
        ${domainRows(esc, doc.domains)}
      </section>
      </div>
      <section class="mt-4"><h2 class="font-pixel text-xs text-green mb-2">Meetings</h2><div data-meetings></div></section>
      <section class="mt-4"><h2 class="font-pixel text-xs text-green mb-2">Network</h2><div data-network></div></section>`;
    renderNetwork(root.querySelector("[data-network]"), slug, helpers);
    renderMeetings(root.querySelector("[data-meetings]"), slug, helpers);
    wireActions(root, esc);
  }

  window.VenturesStudio = { mount };
})();
