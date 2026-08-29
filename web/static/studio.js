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

  function envRows(esc, envs) {
    if (!envs.length) return `<p class="text-subtext text-xs">no environments declared</p>`;
    return `<table class="studio-table text-xs"><thead><tr><th>env</th><th>url</th><th>host</th><th>deploy</th><th>status</th><th>control</th></tr></thead><tbody>` +
      envs.map(e => `<tr>
        <td>${esc(e.name)}</td>
        <td>${e.url ? `<a class="text-blue" href="${esc(safeHref(e.url))}" target="_blank" rel="noopener">${esc(e.url)}</a>` : `<span class="text-subtext">none</span>`}</td>
        <td>${esc(e.host || "")}</td>
        <td>${esc(e.deploy || "")}</td>
        <td>${badge(esc, e.status || "declared")}</td>
        <td>${e.controllable ? badge(esc, "controllable", "text-green") : `<span class="text-subtext">read only</span>`}</td>
      </tr>`).join("") + `</tbody></table>`;
  }

  function appCard(esc, a) {
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
      <div class="mt-2">${envRows(esc, a.environments || [])}</div>
      ${deps ? `<div class="text-xs mt-2">depends on ${deps}</div>` : ""}
      ${runtime}
      ${a.notes ? `<p class="text-xs text-subtext mt-2">${esc(a.notes)}</p>` : ""}
    </article>`;
  }

  function domainRows(esc, domains) {
    if (!domains.length) return `<p class="text-subtext text-xs">no domains declared; add environments[].url to an app manifest</p>`;
    return `<table class="studio-table text-xs"><thead><tr><th>host</th><th>app</th><th>env</th><th>status</th><th>control</th></tr></thead><tbody>` +
      domains.map(d => `<tr>
        <td><a class="text-blue" href="${esc(safeHref(d.url))}" target="_blank" rel="noopener">${esc(d.host)}</a></td>
        <td>${esc(d.app)}</td><td>${esc(d.env)}</td>
        <td>${badge(esc, d.status)}</td>
        <td>${d.controllable ? badge(esc, "controllable", "text-green") : `<span class="text-subtext">read only</span>`}</td>
      </tr>`).join("") + `</tbody></table>`;
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
    root.innerHTML = `<div class="studio-grid">
      <section>
        <h2 class="font-pixel text-xs text-green mb-2">Library (${esc(doc.counts.apps)})</h2>
        ${errors}
        ${doc.apps.length ? doc.apps.map(a => appCard(esc, a)).join("")
          : `<p class="text-subtext text-xs">no apps yet; create one with the app_create MCP tool</p>`}
      </section>
      <section>
        <h2 class="font-pixel text-xs text-green mb-2">Domains (${esc(doc.counts.domains)})</h2>
        ${domainRows(esc, doc.domains)}
        <h2 class="font-pixel text-xs text-green mt-4 mb-2">Coming</h2>
        <p class="text-xs text-subtext">Meetings, task network and live health land in later phases (${esc(Object.keys(doc.phase).join(", "))}).</p>
      </section>
    </div>`;
  }

  window.VenturesStudio = { mount };
})();
