(() => {
  "use strict";
  let data = null;
  let view = null;
  let editing = null; // "file#id" of the entry open in the edit form
  const STAGE_NAMES = { all: "全部阶段", intake: "接案", strategy: "策略", manuscript: "母稿", review: "全稿审查", visual: "视觉", production: "生产", export: "导出" };
  const STATUS_NAMES = { active: "生效", retired: "已停用" };
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const $ = (id) => document.getElementById(id);
  const stageFilter = $("stage");
  const searchBox = $("search");
  const showInactive = $("show-inactive");

  async function api(path, body) {
    const res = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json", "X-Box-Token": TOKEN },
      body: body ? JSON.stringify(body) : undefined,
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "请求失败");
    return json;
  }

  let toastTimer = null;
  function toast(text, err) {
    const el = $("toast");
    el.textContent = text;
    el.className = `toast show${err ? " err" : ""}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = "toast"; }, 2600);
  }

  // ---------- Data views ----------
  const pending = () => data.projects.flatMap((p) => p.candidates.filter((c) => c.status === "candidate").map((c) => ({ ...c, projectName: p.name })));
  const projectEntries = () => data.projects.flatMap((p) => p.entries.map((e) => ({ ...e, projectName: p.name })));
  const isActive = (e) => e.status === "active";

  function entriesFor(v) {
    if (v === "owner") return data.owner;
    if (v === "playbook") return data.playbook;
    if (v === "all") return [...projectEntries(), ...data.owner, ...data.playbook];
    if (v.startsWith("project:")) {
      const p = data.projects.find((x) => x.key === v.slice(8));
      return p ? p.entries.map((e) => ({ ...e, projectName: p.name })) : [];
    }
    return [];
  }

  function visible(list) {
    const stage = stageFilter.value;
    const q = searchBox.value.trim().toLowerCase();
    return list.filter((e) => (showInactive.checked || view === "inbox" || isActive(e))
      && (!stage || e.stages.includes(stage) || e.stages.includes("all"))
      && (!q || `${e.id} ${e.title} ${e.body} ${e.source} ${e.scope.join(" ")} ${e.projectName || ""}`.toLowerCase().includes(q)));
  }

  // ---------- Rendering ----------
  function navItem(key, name, count, cls) {
    return `<button type="button" class="nav-item${view === key ? " active" : ""}" data-view="${esc(key)}"><span class="name">${esc(name)}</span><span class="count ${cls || ""}">${count}</span></button>`;
  }

  function renderNav() {
    const inbox = pending().length;
    const active = (list) => list.filter(isActive).length;
    let html = navItem("inbox", "待审候选", inbox, inbox ? "pending" : "");
    html += navItem("all", "全部生效记忆", active(entriesFor("all")));
    html += `<div class="nav-group">跨项目</div>`;
    html += navItem("owner", data.layers.owner, active(data.owner));
    html += navItem("playbook", data.layers.playbook, active(data.playbook));
    html += `<div class="nav-group">${esc(data.layers.project)}</div>`;
    html += data.projects.length
      ? data.projects.map((p) => navItem(`project:${p.key}`, p.name, active(p.entries))).join("")
      : `<div class="nav-group">还没有项目</div>`;
    $("nav").innerHTML = html;
  }

  const HEADS = {
    inbox: ["待审候选", "Agent 在阶段放行时从工作台的评论、修改和确认里提炼的经验。可以先改再采纳，采纳后写进对应层级，之后每个阶段自动加载。"],
    all: ["全部生效记忆", "Agent 加载时的顺序：项目记忆在前，然后是 Owner 偏好、方法论。"],
    owner: ["Owner 偏好", "跨项目稳定的判断习惯、审美、禁忌和交付口味。"],
    playbook: ["方法论", "跨项目验证过的论证结构、页面载体和反复出现的失败模式。"],
  };

  function renderHead() {
    let [title, text] = HEADS[view] || [];
    if (view.startsWith("project:")) {
      const p = data.projects.find((x) => x.key === view.slice(8));
      title = p ? p.name : "项目";
      text = p ? `项目记忆只在这个项目里加载。项目目录：${p.path}` : "";
    }
    $("view-head").innerHTML = `<h1>${esc(title)}</h1><p>${esc(text)}</p>`;
  }

  const layerTag = (layer) => `<span class="tag layer-${layer}">${esc(data.layers[layer] || layer)}</span>`;
  const stageTags = (stages) => stages.map((s) => `<span class="tag">${esc(STAGE_NAMES[s] || s)}</span>`).join("");

  function statusText(status) {
    if (status.startsWith("superseded:")) return `已被 ${status.slice(11)} 取代`;
    return STATUS_NAMES[status] || status;
  }

  function entryCard(e) {
    const key = `${e.file}#${e.id}`;
    if (editing === key) return entryForm(e, key);
    const where = e.layer === "project" && view === "all" ? `<span class="tag">${esc(e.projectName)}</span>` : "";
    const status = isActive(e) ? "" : `<span class="tag status">${esc(statusText(e.status))}</span>`;
    const toggle = isActive(e) ? "停用" : "恢复生效";
    return `<article class="card${isActive(e) ? "" : " inactive"}" data-key="${esc(key)}">
      <div class="card-top"><div class="card-title">${esc(e.title)}</div>${status}${view === "all" ? layerTag(e.layer) : ""}</div>
      <div class="card-body">${esc(e.body)}</div>
      <div class="meta"><code>${esc(e.id)}</code>${where}${stageTags(e.stages)}${e.scope.length ? `<span>适用：${esc(e.scope.join("、"))}</span>` : ""}<span>${esc(e.date)}</span><span>来源：${esc(e.source)}</span></div>
      <div class="card-actions"><button type="button" class="btn quiet" data-toggle>${toggle}</button><button type="button" class="btn" data-edit>编辑</button></div>
    </article>`;
  }

  function stageInput(stages) {
    return `<label>阶段<input class="f-stages" value="${esc(stages.join(", "))}" title="可选：${esc(data.stages.join(" / "))}"></label>`;
  }

  function entryForm(e, key) {
    return `<article class="card" data-key="${esc(key)}"><div class="form">
      <input class="f-title" value="${esc(e.title)}" aria-label="结论">
      <textarea class="f-body" rows="3" aria-label="正文">${esc(e.body)}</textarea>
      <div class="form-row">${stageInput(e.stages)}<label>适用<input class="f-scope" value="${esc(e.scope.join(", "))}" placeholder="留空表示通用"></label></div>
      <div class="from"><code>${esc(e.id)}</code> · ${esc(e.date)} · 来源：${esc(e.source)}</div>
    </div><div class="card-actions"><button type="button" class="btn quiet" data-cancel>取消</button><button type="button" class="btn primary" data-save>保存</button></div></article>`;
  }

  function candidateCard(c) {
    const layers = Object.entries(data.layers).map(([k, v]) => `<option value="${k}" ${k === c.target ? "selected" : ""}>${esc(v)}</option>`).join("");
    return `<article class="card" data-project="${esc(c.project)}" data-cid="${esc(c.id)}"><div class="form">
      <div class="meta"><code>${esc(c.id)}</code><span class="tag">${esc(c.projectName)}</span><span>${esc(c.date)}</span><span>来源：${esc(c.source)}</span></div>
      <input class="f-title" value="${esc(c.title)}" aria-label="结论">
      <textarea class="f-body" rows="3" aria-label="正文">${esc(c.body)}</textarea>
      <div class="form-row"><label>写入<select class="f-layer">${layers}</select></label>${stageInput(c.stages)}</div>
    </div><div class="card-actions"><button type="button" class="btn" data-reject>丢弃</button><button type="button" class="btn primary" data-accept>采纳</button></div></article>`;
  }

  function renderCards() {
    const list = visible(view === "inbox" ? pending() : entriesFor(view));
    const empty = view === "inbox" ? "没有待审的候选。" : "这里还没有记忆。";
    $("cards").innerHTML = list.length ? list.map(view === "inbox" ? candidateCard : entryCard).join("") : `<div class="empty">${empty}</div>`;
  }

  function renderSwitch() {
    const box = $("enabled");
    box.checked = data.enabled;
    box.disabled = data.env_override;
    box.parentElement.title = data.env_override ? "当前由环境变量 QIFEI_MEMORY 决定，这里不能切换" : "关闭后 Agent 不读取、不记录记忆，门禁也不检查";
    $("off-banner").hidden = data.enabled;
  }

  function render() {
    renderSwitch();
    renderNav();
    renderHead();
    renderCards();
  }

  function setView(v) {
    view = v;
    editing = null;
    try { localStorage.setItem("memory-box-view", v); } catch (_) { /* per-viewer convenience */ }
    render();
  }

  // ---------- Actions ----------
  const stagesOf = (card) => card.querySelector(".f-stages").value.split(/[,，、\s]+/).filter(Boolean);

  async function act(card, path, body, done) {
    card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      const res = await api(path, body);
      data = res.memory;
      done(res);
      render();
    } catch (error) {
      card.querySelectorAll("button").forEach((b) => { b.disabled = false; });
      toast(error.message, true);
    }
  }

  function findEntry(key) {
    return entriesFor("all").find((e) => `${e.file}#${e.id}` === key);
  }

  $("cards").addEventListener("click", (ev) => {
    const card = ev.target.closest(".card");
    if (!card) return;
    if (card.dataset.cid) {
      const base = { project: card.dataset.project, id: card.dataset.cid };
      if (ev.target.closest("[data-accept]")) {
        act(card, "/api/candidate/accept", {
          ...base, layer: card.querySelector(".f-layer").value, title: card.querySelector(".f-title").value,
          body: card.querySelector(".f-body").value, stages: stagesOf(card),
        }, (res) => toast(`${base.id} 已写入记忆 ${res.accepted}`));
      }
      if (ev.target.closest("[data-reject]")) act(card, "/api/candidate/reject", base, () => toast(`${base.id} 已丢弃`));
      return;
    }
    const key = card.dataset.key;
    const e = findEntry(key);
    if (!e) return;
    if (ev.target.closest("[data-edit]")) { editing = key; renderCards(); document.querySelector(`[data-key="${CSS.escape(key)}"] .f-title`)?.focus(); return; }
    if (ev.target.closest("[data-cancel]")) { editing = null; renderCards(); return; }
    const payload = { file: e.file, id: e.id, title: e.title, body: e.body, stages: e.stages, scope: e.scope, status: e.status };
    if (ev.target.closest("[data-toggle]")) {
      const status = isActive(e) ? "retired" : "active";
      act(card, "/api/entry/update", { ...payload, status }, () => toast(status === "active" ? `${e.id} 已恢复生效` : `${e.id} 已停用，不再加载`));
    }
    if (ev.target.closest("[data-save]")) {
      act(card, "/api/entry/update", {
        ...payload, title: card.querySelector(".f-title").value, body: card.querySelector(".f-body").value,
        stages: stagesOf(card), scope: card.querySelector(".f-scope").value.split(/[,，、\s]+/).filter(Boolean),
      }, () => { editing = null; toast(`${e.id} 已保存`); });
    }
  });

  $("nav").addEventListener("click", (ev) => {
    const item = ev.target.closest("[data-view]");
    if (item) setView(item.dataset.view);
  });
  [stageFilter, showInactive].forEach((el) => el.addEventListener("change", renderCards));
  $("enabled").addEventListener("change", async (ev) => {
    const enabled = ev.target.checked;
    try {
      const res = await api("/api/settings", { enabled });
      data = res.memory;
      render();
      toast(enabled ? "提案记忆已启用" : "提案记忆已关闭");
    } catch (error) {
      ev.target.checked = !enabled;
      toast(error.message, true);
    }
  });
  searchBox.addEventListener("input", renderCards);

  async function reload(announce) {
    const before = new Set(data ? pending().map((c) => `${c.project}#${c.id}`) : []);
    data = await api("/api/memory");
    const fresh = pending().filter((c) => !before.has(`${c.project}#${c.id}`)).length;
    if (announce && fresh) toast(`新增 ${fresh} 条待审候选`);
    if (!editing) render(); else renderNav();
  }

  (async () => {
    data = await api("/api/memory");
    $("home").textContent = data.home;
    stageFilter.innerHTML = `<option value="">全部阶段</option>` + data.stages.filter((s) => s !== "all").map((s) => `<option value="${s}">${esc(STAGE_NAMES[s] || s)}</option>`).join("");
    let saved = null;
    try { saved = localStorage.getItem("memory-box-view"); } catch (_) { /* default */ }
    const known = (v) => v && (HEADS[v] || data.projects.some((p) => `project:${p.key}` === v));
    view = pending().length ? "inbox" : known(saved) ? saved : "all";
    render();
    const source = new EventSource(`/api/events?token=${encodeURIComponent(TOKEN)}`);
    source.addEventListener("changed", () => reload(true).catch(() => toast("刷新失败", true)));
  })().catch(() => toast("记忆库加载失败", true));
})();
