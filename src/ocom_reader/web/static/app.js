// OCOM Reader Web UI — vanilla JS, no framework, no build step.
// Every data-bearing call goes through /api/*; this file only renders
// what the API already returned. Repository selection is client-only
// state (localStorage) — it never mutates the server's shared
// workspace.json active pointer. See MILESTONE-018-DESIGN.md.

const state = {
  repo: localStorage.getItem("ocom-reader-repo") || null,
};

function setRepo(name) {
  state.repo = name;
  localStorage.setItem("ocom-reader-repo", name);
}

function apiUrl(path, params) {
  const url = new URL(path, window.location.origin);
  if (state.repo) url.searchParams.set("repo", state.repo);
  for (const [k, v] of Object.entries(params || {})) url.searchParams.set(k, v);
  return url.toString();
}

async function apiGet(path, params) {
  const res = await fetch(apiUrl(path, params));
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function renderMarkdownInline(text) {
  let escaped = escapeHtml(text);
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");
  return escaped;
}

function docListItem(doc, reasons, score) {
  const li = document.createElement("li");
  const title = document.createElement("div");
  title.className = "doc-title";
  title.textContent = doc.title + (score !== undefined ? ` (score ${score})` : "");
  li.appendChild(title);

  const path = document.createElement("div");
  path.className = "doc-path";
  path.textContent = doc.path;
  li.appendChild(path);

  if (doc.preview) {
    const preview = document.createElement("div");
    preview.className = "doc-preview";
    preview.innerHTML = renderMarkdownInline(doc.preview);
    li.appendChild(preview);
  }

  if (reasons && reasons.length) {
    const r = document.createElement("div");
    r.className = "doc-reasons";
    r.textContent = reasons.join("; ");
    li.appendChild(r);
  }

  return li;
}

function setStatus(text) {
  document.getElementById("status-line").textContent = text;
}

function clearResults() {
  document.getElementById("answer-text").textContent = "";
  document.getElementById("evidence-list").innerHTML = "";
  document.getElementById("related-list").innerHTML = "";
  document.getElementById("reading-order-list").innerHTML = "";
}

async function runAsk(query) {
  setStatus("Asking…");
  try {
    const answer = await apiGet("/api/ask", { q: query });
    clearResults();
    document.getElementById("answer-text").textContent = answer.answer;

    const evidenceList = document.getElementById("evidence-list");
    for (const doc of answer.evidence) {
      evidenceList.appendChild(docListItem(doc.document, doc.reasons, doc.score));
    }

    const relatedList = document.getElementById("related-list");
    for (const doc of answer.related_documents) {
      relatedList.appendChild(docListItem(doc.document, doc.reasons, doc.score));
    }

    const orderList = document.getElementById("reading-order-list");
    for (const doc of answer.reading_order) {
      orderList.appendChild(docListItem(doc));
    }

    setStatus(answer.grounded ? "" : "No documentation found.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

async function runSearch(query) {
  setStatus("Searching…");
  try {
    const result = await apiGet("/api/search", { q: query });
    clearResults();
    const evidenceList = document.getElementById("evidence-list");
    for (const match of result.matches) {
      const reasons = match.reasons.map((r) => `${r.kind}: ${r.detail}`);
      evidenceList.appendChild(
        docListItem({ title: match.entry.registry_id, path: match.entry.registry_id }, reasons, match.score)
      );
    }
    setStatus(result.matches.length ? "" : "No matches.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

async function runExplain(query) {
  setStatus("Explaining…");
  try {
    const result = await apiGet("/api/explain", { q: query });
    clearResults();
    const evidenceList = document.getElementById("evidence-list");
    for (const doc of result.documents) {
      evidenceList.appendChild(docListItem(doc.document, doc.reasons, doc.score));
    }
    setStatus(result.documents.length ? "" : "Nothing found to explain.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

async function loadWorkspace() {
  const data = await apiGet("/api/workspace");
  const select = document.getElementById("repo-select");
  const list = document.getElementById("workspace-list");
  select.innerHTML = "";
  list.innerHTML = "";

  if (!data.repositories.length) {
    const opt = document.createElement("option");
    opt.textContent = "(no repositories registered)";
    select.appendChild(opt);
    list.innerHTML = "<li>No repositories registered.</li>";
    return;
  }

  if (!state.repo) {
    const activeEntry = data.repositories.find((r) => r.active);
    setRepo(activeEntry ? activeEntry.name : data.repositories[0].name);
  }

  for (const r of data.repositories) {
    const opt = document.createElement("option");
    opt.value = r.name;
    opt.textContent = r.name + (r.active ? " (default)" : "");
    if (r.name === state.repo) opt.selected = true;
    select.appendChild(opt);

    const li = document.createElement("li");
    li.textContent = `${r.name} — ${r.path}`;
    list.appendChild(li);
  }
}

async function loadPlugins() {
  const list = document.getElementById("plugin-list");
  list.innerHTML = "";
  try {
    const data = await apiGet("/api/plugins");
    if (!data.plugins.length) {
      list.innerHTML = "<li>No plugins discovered.</li>";
      return;
    }
    for (const p of data.plugins) {
      const li = document.createElement("li");
      const stateSpan = document.createElement("span");
      stateSpan.className = "state-" + p.state;
      stateSpan.textContent = p.state;
      li.textContent = `${p.name} v${p.version} — `;
      li.appendChild(stateSpan);
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li>Error loading plugins: ${escapeHtml(err.message)}</li>`;
  }
}

function initDarkMode() {
  const stored = localStorage.getItem("ocom-reader-theme");
  if (stored) document.documentElement.setAttribute("data-theme", stored);
  document.getElementById("dark-toggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("ocom-reader-theme", next);
  });
}

function initForm() {
  const form = document.getElementById("ask-form");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = document.getElementById("query-input").value.trim();
    if (query) runAsk(query);
  });
  form.querySelectorAll("button[data-mode]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const query = document.getElementById("query-input").value.trim();
      if (!query) return;
      const mode = btn.getAttribute("data-mode");
      if (mode === "search") runSearch(query);
      else if (mode === "explain") runExplain(query);
      else runAsk(query);
    });
  });
}

async function init() {
  initDarkMode();
  initForm();

  document.getElementById("repo-select").addEventListener("change", (event) => {
    setRepo(event.target.value);
    loadPlugins();
  });

  try {
    const health = await apiGet("/api/health");
    document.getElementById("reader-version").textContent = "OCOM Reader " + health.reader_version;
  } catch (err) {
    document.getElementById("reader-version").textContent = "Could not reach server.";
  }

  await loadWorkspace();
  await loadPlugins();
}

init();
