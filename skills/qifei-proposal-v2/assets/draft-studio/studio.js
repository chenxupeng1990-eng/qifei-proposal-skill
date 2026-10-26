(() => {
  "use strict";
  let model = JSON.parse(document.getElementById("model").textContent);
  const markdown = JSON.parse(document.getElementById("markdown").textContent);
  const liveNode = document.getElementById("live");
  const live = liveNode ? JSON.parse(liveNode.textContent) : null;
  const STATUS = {
    confirmed: "已确认",
    verified: "已回读",
    modified: "已修改·待重新确认",
    pending: "待确认",
    unknown: "无状态",
  };
  const INTERNAL = new Set(["bridge", "evidence", "other"]);

  // ---------- Markdown fragment renderer (subset used by proposal drafts) ----------
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function inline(text) {
    let s = esc(text);
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (_, c) => `\u0000${codes.push(c) - 1}\u0000`);
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, alt, src) => imageHtml(alt, src));
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
    s = s.replace(/&lt;br\s*\/?&gt;/g, "<br>");  // Feishu keeps line breaks inside table cells as <br>
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
  }

  function imageHtml(alt, src) {
    const label = alt || "图片";
    return `<img src="${src}" alt="${label}" loading="lazy" data-alt="${label}">`;
  }

  function splitRow(line) {
    return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  }
  const isSep = (line) => /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$/.test(line);
  const stripBold = (s) => s.replace(/^\*\*(.*)\*\*$/, "$1");

  function tableHtml(rows) {
    const head = splitRow(rows[0]);
    const body = rows.slice(2).map(splitRow);
    if (head.length === 2) {
      const cells = body.map((r) => `<div class="k">${inline(stripBold(r[0] || ""))}</div><div>${inline(r[1] || "")}</div>`).join("");
      return `<div class="kv">${cells}</div>`;
    }
    const th = head.map((h) => `<th>${inline(stripBold(h))}</th>`).join("");
    const tr = body.map((r) => `<tr>${head.map((_, i) => `<td>${inline(r[i] || "")}</td>`).join("")}</tr>`).join("");
    return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
  }

  function flowHtml(text) {
    const steps = text.split(/\s*→\s*/).filter(Boolean);
    return `<div class="flow">${steps.map((s, i) => `${i ? '<span class="arrow">→</span>' : ""}<span class="step">${inline(s)}</span>`).join("")}</div>`;
  }

  function directiveHtml(type, title, body) {
    const inner = block(body.join("\n"));
    if (type === "flow") return flowHtml(body.join(" ").replace(/^\s*-\s*/gm, "").trim());
    if (type === "columns") {
      const cols = [];
      body.forEach((l) => { if (l.trim() === "::col" || !cols.length) cols.push([]); if (l.trim() !== "::col") cols[cols.length - 1].push(l); });
      const filled = cols.filter((c) => c.join("").trim());
      return `<div class="columns" style="grid-template-columns: repeat(${filled.length}, minmax(0, 1fr))">${filled.map((c) => `<div class="md">${block(c.join("\n"))}</div>`).join("")}</div>`;
    }
    if (type === "compare") {
      const halves = body.join("\n").split(/^\s*---\s*$/m);
      return `<div class="compare">${halves.map((h) => `<div class="md">${block(h)}</div>`).join("")}</div>`;
    }
    if (type === "data") {
      const cards = body.filter((l) => l.trim().startsWith("-")).map((l) => {
        const [num, ...rest] = l.replace(/^\s*-\s*/, "").split(/[｜|]/);
        return `<div class="card"><div class="num">${inline(num.trim())}</div><div class="lbl">${inline(rest.join("｜").trim())}</div></div>`;
      });
      return `<div class="datacards">${cards.join("")}</div>`;
    }
    const heading = title ? `<p><strong>${inline(title)}</strong></p>` : "";
    return `<div class="callout"><span class="ic">!</span><div class="ct md">${heading}${inner}</div></div>`;
  }

  function block(text) {
    const lines = (text || "").split("\n");
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      const t = line.trim();
      if (!t || /^-{3,}$/.test(t)) { i++; continue; }
      if (t.startsWith("```")) {
        const buf = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith("```")) buf.push(lines[i++]);
        i++;
        out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
        continue;
      }
      const dir = t.match(/^:::\s*([a-z]+)\s*(.*)$/);
      if (dir) {
        const buf = [];
        i++;
        while (i < lines.length && lines[i].trim() !== ":::") buf.push(lines[i++]);
        i++;
        out.push(directiveHtml(dir[1], dir[2], buf));
        continue;
      }
      if (t.startsWith("|") && i + 1 < lines.length && isSep(lines[i + 1])) {
        const buf = [];
        while (i < lines.length && lines[i].trim().startsWith("|")) buf.push(lines[i++]);
        out.push(tableHtml(buf));
        continue;
      }
      const h = t.match(/^(#{1,6})\s+(.*)$/);
      if (h) { out.push(`<h4>${inline(h[2])}</h4>`); i++; continue; }
      if (t.startsWith(">")) {
        const buf = [];
        while (i < lines.length && lines[i].trim().startsWith(">")) buf.push(lines[i++].trim().replace(/^>\s?/, ""));
        out.push(`<blockquote>${block(buf.join("\n"))}</blockquote>`);
        continue;
      }
      if (/^([-*+]|\d+[.)])\s+/.test(t)) {
        const ordered = /^\d/.test(t);
        const items = [];
        while (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
          let item = lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, "");
          i++;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) item += " " + lines[i++].trim();
          items.push(`<li>${inline(item)}</li>`);
        }
        out.push(ordered ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`);
        continue;
      }
      const buf = [];
      while (i < lines.length && lines[i].trim() && !/^(\||```|:::|#{1,6}\s|>|[-*+]\s|\d+[.)]\s)/.test(lines[i].trim())) buf.push(lines[i++].trim());
      if (!buf.length) { buf.push(t); i++; }
      out.push(`<p>${inline(buf.join("<br>"))}</p>`.replace(/&lt;br&gt;/g, "<br>"));
    }
    return out.join("");
  }

  // ---------- Field-specific presentation ----------
  function rowsOf(md) {
    const lines = md.split("\n").filter((l) => l.trim().startsWith("|"));
    if (lines.length < 3 || !isSep(lines[1])) return null;
    return lines.slice(2).map(splitRow).filter((r) => r.length >= 2);
  }

  function screenHtml(md, fallbackTitle) {
    const rows = rowsOf(md);
    if (!rows) return `<div class="md">${block(md)}</div>`;
    let title = "", sub = "";
    const rest = [];
    for (const [k, v] of rows) {
      const key = stripBold(k);
      if (!title && /^标题$|主标题/.test(key)) title = v;
      else if (!sub && /副标题/.test(key)) sub = v;
      else rest.push([key, v]);
    }
    if (!title) title = fallbackTitle || "";
    const lines = (v) => {
      const parts = v.split(/；/).map((x) => x.trim()).filter(Boolean);
      return parts.length > 1 ? `<ul class="s-lines">${parts.map((x) => `<li>${inline(x)}</li>`).join("")}</ul>` : inline(v);
    };
    const restHtml = rest.map(([k, v]) => `<div class="s-row"><div class="k">${inline(k)}</div><div>${lines(v)}</div></div>`).join("");
    const outside = md.split("\n").filter((l) => !l.trim().startsWith("|")).join("\n").trim();
    return `<div class="screen">${title ? `<p class="s-title">${inline(title)}</p>` : ""}${sub ? `<p class="s-sub">${inline(sub)}</p>` : ""}${restHtml}</div>${outside ? `<div class="md">${block(outside)}</div>` : ""}`;
  }

  function visualHtml(md) {
    const rows = rowsOf(md);
    if (!rows) return `<div class="md">${block(md)}</div>`;
    const cells = rows.map(([k, v]) => {
      const key = stripBold(k);
      const wide = /Image2|HTML|避免/.test(key) || v.length > 60;
      return `<div class="cell${wide ? " wide" : ""}"><div class="k">${inline(key)}</div><div class="v">${inline(v)}</div></div>`;
    });
    return `<div class="visual-grid">${cells.join("")}</div>`;
  }

  function logicHtml(md) {
    const t = md.trim();
    if (!t.includes("\n") && (t.match(/→/g) || []).length >= 2) return flowHtml(t);
    return `<div class="md">${block(md)}</div>`;
  }

  const editBtn = (attrs, label = "编辑") => live ? `<button type="button" class="edit-btn" ${attrs}>${label}</button>` : "";

  const PLACEHOLDER = /^(待补充|待填写|待补写|TODO|TBD)[。.！!]?$/i;

  function fieldHtml(field, slide) {
    if (PLACEHOLDER.test(field.md.trim())) {
      const edit = live && field.span ? editBtn(`data-edit="field" data-slide="${slide.id}" data-key="${field.key}"`) : "";
      return `<section class="field field-${field.key} field-todo"><div class="field-label">${field.name}${edit}</div><div class="field-body" data-field="${slide.id}:${field.key}"><span class="todo">待补充</span></div></section>`;
    }
    const canEdit = live && field.span;
    const edit = canEdit ? editBtn(`data-edit="field" data-slide="${slide.id}" data-key="${field.key}"`) : "";
    let body;
    if (field.key === "screen") body = screenHtml(field.md, slide.title);
    else if (field.key === "visual") body = visualHtml(field.md);
    else if (field.key === "logic") body = logicHtml(field.md);
    else if (field.key === "lead") body = `<figure class="preview">${block(field.md)}</figure>`;
    else body = `<div class="md">${block(field.md)}</div>`;
    const box = `<div class="field-body" data-field="${slide.id}:${field.key}">${body}</div>`;
    if (INTERNAL.has(field.key)) {
      return `<details class="internal field field-${field.key}"><summary>${field.name}<span class="tag">内部</span>${edit}</summary>${box}</details>`;
    }
    const tag = field.key === "visual" ? '<span class="tag">生产</span>' : "";
    const label = field.key === "lead" ? (edit ? `<div class="field-label">${field.name}${edit}</div>` : "") : `<div class="field-label">${field.name}${tag}${edit}</div>`;
    return `<section class="field field-${field.key}">${label}${box}</section>`;
  }

  // ---------- Studio authority: chapter confirmation and registration ----------
  function authorityBar(reg) {
    const fresh = reg.status === "verified" && reg.revision === reg.current;
    const state = fresh
      ? `<span class="chip st-confirmed">已登记 rev ${reg.revision}</span>`
      : `<span class="chip st-pending">${reg.revision ? `已登记 rev ${reg.revision}，之后有修改` : "尚未登记"}</span>`;
    const action = live && !fresh ? `<button type="button" class="btn" data-register>登记当前版本（rev ${reg.current}）</button>` : "";
    const chapters = model.chapters.filter((c) => c.studio && c.studio.chapter_id);
    const done = chapters.filter((c) => c.studio.confirmed).length;
    return `<div class="authority-bar"><span class="ab-label">权威源：工作台</span>${state}<span class="ab-sep">·</span><span>章节确认 ${done}/${chapters.length}</span>${reg.all_confirmed && fresh ? '<span class="ab-ok">可以进入全稿审查</span>' : ""}${action}</div>`;
  }

  function chapterConfirm(ch) {
    const s = ch.studio;
    if (!s) return "";
    if (!s.chapter_id) return `<div class="confirm-row muted">${esc(s.reason)}</div>`;
    if (s.confirmed && s.record) {
      return `<div class="confirm-row"><span class="chip st-confirmed">${esc(s.chapter_id)} 已确认</span><span class="muted">${esc(s.record.by)} · ${String(s.record.at).replace("T", " ").slice(0, 16)} · rev ${s.record.revision}</span></div>`;
    }
    const again = s.record ? '<span class="chip st-modified">确认后有修改，需要重新确认</span>' : "";
    if (!live) return `<div class="confirm-row">${again || `<span class="chip st-pending">${esc(s.chapter_id)} 待确认</span>`}</div>`;
    return `<div class="confirm-row">${again}<button type="button" class="btn primary" data-confirm-chapter="${esc(s.chapter_id)}" ${s.reason ? "disabled" : ""}>确认 ${esc(s.chapter_id)}</button>${s.reason ? `<span class="muted">${esc(s.reason)}</span>` : ""}</div>`;
  }

  async function authorityPost(path, body, okText) {
    try {
      const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Studio-Token": live.token }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) { toast(data.error || "没有成功"); return; }
      model = data.model;
      rerender();
      toast(data.registration_pending ? `${okText}；尚未登记：${data.registration_pending}` : okText, "ok");
    } catch (_) { toast("连接不到工作台服务"); }
  }

  // ---------- Page assembly ----------
  const chip = (st) => `<span class="chip st-${st}">${STATUS[st] || st}</span>`;
  const anchor = (id) => `slide-${id}`;

  function render() {
    const meta = model.meta || {};
    document.getElementById("doc-title").textContent = model.title;
    const metaBits = [
      meta.authority ? `权威源 ${meta.authority}` : null,
      meta.revision != null ? `rev ${meta.revision}` : null,
      meta.sha256 ? `<code>${meta.sha256.slice(0, 12)}</code>` : null,
      meta.phase ? `阶段 ${meta.phase}` : null,
      meta.generated_at ? `生成于 ${meta.generated_at.replace("T", " ").slice(0, 16)}` : null,
    ].filter(Boolean);
    if (live) metaBits.unshift(`<span class="live-dot" id="live-state">实时</span>`);
    document.getElementById("doc-meta").innerHTML = metaBits.join(" · ");

    const counts = {};
    const all = model.chapters.flatMap((c) => c.slides);
    all.forEach((s) => { counts[s.status] = (counts[s.status] || 0) + 1; });

    const toc = [`<div class="toc-summary">${Object.keys(STATUS).filter((k) => counts[k]).map((k) => `<span class="chip st-${k}">${STATUS[k]} ${counts[k]}</span>`).join("")}</div>`];
    const doc = [`<div class="doc-head"><h1>${inline(model.title)}</h1><div class="sub">${model.chapters.length} 章 · ${all.length} 页 · 来源 <code>${esc(meta.source || "")}</code></div></div>`];
    const issues = model.format_issues || [];
    if (issues.length) {
      const pages = new Set(issues.map((i) => i.page).filter((p) => p !== "-"));
      const list = issues.slice(0, 40).map((i) => `<li><code>${esc(i.page)}</code> ${inline(i.message)}</li>`).join("");
      // Caution phrases on screen are a content problem, not a format one: normalize cannot fix them.
      const formatCount = issues.filter((i) => !i.message.includes("内部审慎用语")).length;
      const summary = formatCount
        ? `<b>这份母稿不是标准格式</b>：${issues.length} 处问题，涉及 ${pages.size} 页。先运行 <code>draft_studio.py normalize</code> 转换；转换前，认不出的内容按正文显示。`
        : `<b>上屏内容有内部审慎用语</b>：${issues.length} 处，涉及 ${pages.size} 页。上屏只保留来源，边界写进措辞，审慎说明放进讲解方向或证据与来源；改完这些页所在的章才能确认。`;
      doc.push(`<details class="format-warn"><summary>${summary}</summary><ul>${list}</ul>${issues.length > 40 ? `<p>还有 ${issues.length - 40} 处，运行 <code>draft_studio.py check</code> 查看全部。</p>` : ""}</details>`);
    }
    if (model.registration) doc.push(authorityBar(model.registration));
    if (model.preface_md) doc.push(`<div class="preface md">${block(model.preface_md)}</div>`);

    model.chapters.forEach((ch, ci) => {
      toc.push(`<div class="toc-chapter"><a href="#${ch.id}">${ci + 1}. ${inline(ch.title)}</a>${ch.slides.map((s) => `<a class="toc-slide" href="#${anchor(s.id)}" data-slide="${s.id}"><span class="dot st-${s.status}"></span><span class="sid">${s.id}</span><span class="t">${inline(s.title)}</span></a>`).join("")}</div>`);
      const chain = ch.slides.length > 1
        ? `<div class="chain"><div class="chain-label">本章标题链（连起来读，检查论证是否断开）</div><ol>${ch.slides.map((s) => `<li><span class="sid">${s.id}</span><a href="#${anchor(s.id)}">${inline(s.title)}</a></li>`).join("")}</ol></div>`
        : "";
      doc.push(`<section class="chapter" id="${ch.id}" data-chapter><div class="chapter-head"><div class="chapter-kicker">Chapter ${String(ci + 1).padStart(2, "0")}</div><h2>${inline(ch.title)}</h2>${chapterConfirm(ch)}<div class="chapter-intro"><div class="field-body md" data-field="intro:${ch.id}">${block(ch.intro_md)}</div>${ch.intro_span ? editBtn(`data-edit="intro" data-chapter="${ch.id}"`, "编辑本章说明") : ""}</div>${chain}</div>`);
      ch.slides.forEach((s) => {
        const tools = live
          ? `<div class="slide-tools">${editBtn(`data-edit="title" data-slide="${s.id}"`, "改标题")}${s.body_md != null ? editBtn(`data-edit="body" data-slide="${s.id}"`, "编辑本页源文") : ""}</div>`
          : "";
        doc.push(`<article class="slide" id="${anchor(s.id)}" data-slide-id="${s.id}"><div class="slide-head"><span class="slide-id">${s.id}</span><h3 class="slide-title" data-field="title:${s.id}">${inline(s.title)}</h3>${chip(s.status)}</div>${tools}<div class="slide-body${s.body_md != null ? " field-body" : ""}" data-field="body:${s.id}">${s.fields.map((f) => fieldHtml(f, s)).join("")}</div></article>`);
      });
      doc.push(`</section>`);
    });
    doc.push(`<div class="empty" id="empty" hidden>没有匹配的页面</div>`);
    document.getElementById("toc").innerHTML = toc.join("");
    document.getElementById("doc").innerHTML = doc.join("");
    wireImages();
  }

  function wireImages() {
    document.querySelectorAll("#doc img").forEach((img) => {
      img.addEventListener("error", () => {
        const box = document.createElement("div");
        box.className = "img-missing";
        box.innerHTML = `<b>图片无法直接加载</b>（原图可能需要登录飞书）<br>${esc(img.dataset.alt || "")}`;
        img.replaceWith(box);
      }, { once: true });
    });
  }

  // ---------- Interactions ----------
  function setView(view) {
    document.body.classList.remove("view-full", "view-client", "view-chain");
    document.body.classList.add(`view-${view}`);
    if (typeof layoutCards === "function" && live) requestAnimationFrame(() => layoutCards());
    document.querySelectorAll(".segmented button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
    try { localStorage.setItem("draft-studio-view", view); } catch (_) { /* storage may be unavailable */ }
  }

  function filter(query) {
    const q = query.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll(".slide").forEach((el) => {
      const hit = !q || el.textContent.toLowerCase().includes(q);
      el.classList.toggle("hidden", !hit);
      if (hit) shown++;
    });
    document.querySelectorAll("[data-chapter]").forEach((ch) => {
      ch.classList.toggle("hidden", !!q && !ch.querySelector(".slide:not(.hidden)"));
    });
    document.querySelectorAll(".toc-slide").forEach((a) => {
      const card = document.getElementById(anchor(a.dataset.slide));
      a.style.display = card && card.classList.contains("hidden") ? "none" : "";
    });
    document.getElementById("empty").hidden = shown > 0;
  }

  async function download(profile) {
    let text = markdown[profile];
    if (live) {
      const res = await fetch(`/api/markdown?profile=${profile}`, { headers: { "X-Studio-Token": live.token } });
      if (res.ok) text = await res.text();
    }
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${model.title.replace(/[\\/:*?"<>|｜]+/g, "-")}${profile === "brief" ? "-简洁版" : ""}.md`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // Scroll only the TOC panel. scrollIntoView would also start a (smooth) scroll on the page
  // itself, which cancels trackpad momentum mid-swipe and feels like the page gets stuck.
  function keepInToc(link) {
    const toc = document.getElementById("toc");
    const l = link.getBoundingClientRect();
    const t = toc.getBoundingClientRect();
    if (l.top < t.top + 8) toc.scrollTop += l.top - t.top - 8;
    else if (l.bottom > t.bottom - 8) toc.scrollTop += l.bottom - t.bottom + 8;
  }

  let spy = null;
  function scrollSpy() {
    if (spy) spy.disconnect();
    const links = new Map([...document.querySelectorAll(".toc-slide")].map((a) => [a.dataset.slide, a]));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        links.forEach((a) => a.classList.remove("active"));
        const link = links.get(e.target.dataset.slideId);
        if (link) { link.classList.add("active"); keepInToc(link); }
      });
    }, { rootMargin: "-80px 0px -70% 0px" });
    document.querySelectorAll(".slide").forEach((el) => io.observe(el));
    spy = io;
  }

  // ---------- Live studio: edit in place, save to the draft, refresh on every revision ----------
  let editing = null;
  let pendingRemote = null;

  function findSlide(id) {
    for (const ch of model.chapters) for (const s of ch.slides) if (s.id === id) return s;
    return null;
  }

  function currentView() {
    const b = document.querySelector(".segmented button.active");
    return b ? b.dataset.view : "full";
  }

  function rerender(flashIds = []) {
    const anchorEl = [...document.querySelectorAll(".slide")].find((el) => el.getBoundingClientRect().bottom > 80);
    const anchorId = anchorEl && anchorEl.id;
    const offset = anchorEl ? anchorEl.getBoundingClientRect().top : 0;
    const view = currentView();
    const query = document.getElementById("search").value;
    render();
    setView(view);
    if (query) filter(query);
    scrollSpy();
    if (anchorId) {
      const el = document.getElementById(anchorId);
      if (el) window.scrollBy({ top: el.getBoundingClientRect().top - offset, behavior: "instant" });
    }
    applyComments();
    flashIds.forEach((id) => {
      const el = document.getElementById(anchor(id));
      if (el) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
    });
  }

  function toast(text, tone = "") {
    let el = document.getElementById("toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; document.body.appendChild(el); }
    el.className = `toast show ${tone}`;
    el.textContent = text;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = "toast"; }, 3200);
  }

  function sourceFor(kind, ids) {
    if (kind === "intro") {
      const ch = model.chapters.find((c) => c.id === ids.chapter);
      return ch ? (ch.intro_raw != null ? ch.intro_raw : ch.intro_md) : "";
    }
    const s = findSlide(ids.slide);
    if (!s) return "";
    if (kind === "title") return s.title;
    if (kind === "body") return s.body_md || "";
    const f = s.fields.find((x) => x.key === ids.key);
    return f ? (f.raw != null ? f.raw : f.md) : "";
  }

  function openEditor(btn) {
    if (editing) { editing.textarea.focus(); return; }
    const kind = btn.dataset.edit;
    const ids = { slide: btn.dataset.slide, key: btn.dataset.key, chapter: btn.dataset.chapter };
    const slide = ids.slide ? findSlide(ids.slide) : null;
    if (slide && (slide.status === "confirmed" || slide.status === "verified")) {
      if (!window.confirm(`${slide.id} 已确认。保存修改后，这一页会标记为“已修改·待重新确认”。继续编辑吗？`)) return;
    }
    const fieldKey = kind === "field" ? `${ids.slide}:${ids.key}` : kind === "intro" ? `intro:${ids.chapter}` : `${kind}:${ids.slide}`;
    const host = document.querySelector(`[data-field="${CSS.escape(fieldKey)}"]`);
    if (!host) return;
    const details = host.closest("details");
    if (details) details.open = true;
    const original = sourceFor(kind, ids);
    const form = document.createElement("div");
    form.className = `editor ${kind === "title" ? "editor-title" : ""}`;
    form.innerHTML = `
      <textarea spellcheck="false" aria-label="编辑内容"></textarea>
      <div class="editor-bar">
        <span class="editor-hint">${kind === "title" ? "页面标题" : "Markdown 源文"} · ⌘/Ctrl+Enter 保存 · Esc 取消</span>
        <span class="editor-msg"></span>
        <button type="button" class="btn" data-editor="cancel">取消</button>
        <button type="button" class="btn primary" data-editor="save">保存</button>
      </div>`;
    const textarea = form.querySelector("textarea");
    textarea.value = original;
    host.hidden = true;
    host.after(form);
    const autosize = () => { textarea.style.height = "auto"; textarea.style.height = `${Math.min(textarea.scrollHeight + 4, window.innerHeight * 0.7)}px`; };
    textarea.addEventListener("input", autosize);
    textarea.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); closeEditor(); }
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
      if (kind === "title" && e.key === "Enter" && !e.metaKey && !e.ctrlKey) { e.preventDefault(); save(); }
    });
    editing = { kind, ids, host, form, textarea, original, baseSha: model.meta.sha256 };
    autosize();
    textarea.focus();
  }

  function closeEditor() {
    if (!editing) return;
    editing.form.remove();
    editing.host.hidden = false;
    editing = null;
    applyComments();
    if (pendingRemote) { const next = pendingRemote; pendingRemote = null; applyRemote(next); }
  }

  async function save() {
    if (!editing || editing.saving) return;
    const { kind, ids, textarea, form } = editing;
    const msg = form.querySelector(".editor-msg");
    if (textarea.value === editing.original && editing.baseSha === model.meta.sha256) { closeEditor(); return; }
    editing.saving = true;
    msg.textContent = "保存中…";
    msg.className = "editor-msg";
    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Studio-Token": live.token },
        body: JSON.stringify({ target: { kind, slide: ids.slide, key: ids.key, chapter: ids.chapter, md: textarea.value }, base_sha: editing.baseSha }),
      });
      const data = await res.json();
      if (res.status === 409) {
        model = data.model;
        editing.baseSha = data.model.meta.sha256;
        msg.innerHTML = `母稿刚被别处修改（rev ${data.model.meta.revision}）。你的文字还在，<button type="button" class="linkish" data-editor="save">保存到最新版本</button>`;
        msg.className = "editor-msg warn";
        return;
      }
      if (!res.ok) { msg.textContent = data.error || "保存失败"; msg.className = "editor-msg warn"; return; }
      model = data.model;
      const entry = data.entry || {};
      editing.form.remove();
      editing.host.hidden = false;
      editing = null;
      rerender(entry.slides || []);
      toast(entry.unchanged ? "内容没有变化" : `已保存 · rev ${entry.revision}`, "ok");
    } catch (err) {
      msg.textContent = "连接不到工作台服务，内容未保存";
      msg.className = "editor-msg warn";
    } finally {
      if (editing) editing.saving = false;
    }
  }

  async function applyRemote(event) {
    if (event.sha256 === model.meta.sha256) return;
    if (editing) {
      pendingRemote = event;
      const msg = editing.form.querySelector(".editor-msg");
      msg.textContent = `母稿有新版本 rev ${event.revision}${event.slides && event.slides.length ? `（${event.slides.join("、")}）` : ""}，保存时会提示`;
      msg.className = "editor-msg warn";
      return;
    }
    const res = await fetch("/api/model", { headers: { "X-Studio-Token": live.token } });
    if (!res.ok) return;
    model = await res.json();
    rerender(event.slides || []);
    const who = event.actor === "external" ? "母稿文件被外部修改" : "母稿已更新";
    toast(`${who} · rev ${event.revision}${event.slides && event.slides.length ? ` · ${event.slides.join("、")}` : ""}`);
  }

  function connect() {
    if (!live) return;
    const source = new EventSource(`/api/events?token=${encodeURIComponent(live.token)}`);
    const state = (text, cls) => { const el = document.getElementById("live-state"); if (el) { el.textContent = text; el.className = `live-dot ${cls || ""}`; } };
    source.addEventListener("open", () => state("实时"));
    source.addEventListener("error", () => state("重连中…", "off"));
    source.addEventListener("revision", (e) => applyRemote(JSON.parse(e.data)));
    source.addEventListener("comments", () => { if (!composer) loadComments(true); });
    source.addEventListener("state", async () => {
      if (editing) return;
      const res = await fetch("/api/model", { headers: { "X-Studio-Token": live.token } });
      if (res.ok) { model = await res.json(); rerender(); }
    });
  }

  if (live) {
    document.body.classList.add("live");
    document.addEventListener("click", (e) => {
      const edit = e.target.closest("[data-edit]");
      if (edit) { e.preventDefault(); e.stopPropagation(); openEditor(edit); return; }
      const action = e.target.closest("[data-editor]");
      if (action) action.dataset.editor === "save" ? save() : closeEditor();
    }, true);
    window.addEventListener("beforeunload", (e) => { if (editing && editing.textarea.value !== editing.original) e.preventDefault(); });
  }

  // ---------- Comments: select text, comment beside it, reply, resolve ----------
  let comments = { threads: [] };
  const expandedMsgs = new Set();
  let activeThread = null;
  let composer = null;
  let author = "Owner";
  try { author = localStorage.getItem("draft-studio-author") || "Owner"; } catch (_) { /* default author */ }
  const rail = document.getElementById("rail");
  const railCards = document.getElementById("rail-cards");
  const selButton = document.getElementById("sel-comment");
  // Decided threads stay visible by default: they are the record of why the draft changed.
  let filterMode = "all";
  try { filterMode = localStorage.getItem("draft-studio-filter") || "all"; } catch (_) { /* default */ }
  const listMode = () => window.innerWidth < 1180;

  async function api(path, body) {
    const res = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json", "X-Studio-Token": live.token },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "请求失败");
    return data;
  }

  async function loadComments(announce) {
    const before = new Map(comments.threads.map((t) => [t.id, t.messages.length]));
    comments = await api("/api/comments");
    if (announce) {
      for (const t of comments.threads) {
        const last = t.messages[t.messages.length - 1];
        const grew = !before.has(t.id) || before.get(t.id) < t.messages.length;
        if (grew && last && last.author !== author) toast(`${last.author} ${before.has(t.id) ? "回复了" : "评论了"} ${t.slide || ""}`);
      }
    }
    applyComments();
  }

  function textNodes(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => n.parentElement.closest(".edit-btn, .editor, .cmt-count") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    return nodes;
  }

  function wrapRange(root, start, end, className, threadId) {
    const marks = [];
    let pos = 0;
    for (const node of textNodes(root)) {
      const len = node.nodeValue.length;
      const from = Math.max(start, pos), to = Math.min(end, pos + len);
      if (from < to) {
        let target = node;
        if (from > pos) target = target.splitText(from - pos);
        if (to < pos + len) target.splitText(to - from);
        const mark = document.createElement("mark");
        mark.className = className;
        if (threadId) mark.dataset.thread = threadId;
        target.parentNode.insertBefore(mark, target);
        mark.appendChild(target);
        marks.push(mark);
      }
      pos += len;
      if (pos >= end) break;
    }
    return marks;
  }

  function locate(root, thread) {
    const text = textNodes(root).map((n) => n.nodeValue).join("");
    let best = -1, bestScore = -1, from = 0;
    while (true) {
      const i = text.indexOf(thread.quote, from);
      if (i < 0) break;
      let score = 0;
      if (thread.prefix && text.slice(0, i).endsWith(thread.prefix.slice(-12))) score += 2;
      if (thread.suffix && text.slice(i + thread.quote.length).startsWith(thread.suffix.slice(0, 12))) score += 2;
      if (score > bestScore) { best = i; bestScore = score; }
      from = i + 1;
    }
    return best;
  }

  function clearMarks() {
    document.querySelectorAll("mark.cmt-mark").forEach((m) => {
      const parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      m.remove();
      parent.normalize();
    });
    document.querySelectorAll(".cmt-count").forEach((el) => el.remove());
  }

  const visibleThreads = () => comments.threads.filter((t) => filterMode === "all" || t.status === filterMode);

  function applyComments() {
    if (!live) return;
    clearMarks();
    const open = comments.threads.filter((t) => t.status === "open");
    const decided = comments.threads.length - open.length;
    document.getElementById("rail-counts").textContent = `未解决 ${open.length} · 已决定 ${decided}`;
    document.getElementById("rail-toggle").textContent = `评论 ${open.length}`;
    document.getElementById("rail-tab").innerHTML = `<span>评论</span>${open.length ? `<b>${open.length}</b>` : ""}`;
    document.querySelectorAll("#rail-filter button").forEach((b) => b.classList.toggle("active", b.dataset.filter === filterMode));
    const perSlide = {};
    comments.threads.forEach((t) => {
      const c = perSlide[t.slide] || (perSlide[t.slide] = { open: 0, done: 0 });
      t.status === "open" ? c.open++ : c.done++;
    });
    Object.entries(perSlide).forEach(([id, c]) => {
      const head = document.querySelector(`#${CSS.escape(anchor(id))} .slide-head`);
      const tocLink = document.querySelector(`.toc-slide[data-slide="${CSS.escape(id)}"]`);
      if (c.open) {
        if (head) head.insertAdjacentHTML("beforeend", `<button type="button" class="cmt-count" data-goto-slide="${id}" title="本页未解决评论">${c.open}</button>`);
        if (tocLink) tocLink.insertAdjacentHTML("beforeend", `<span class="cmt-count">${c.open}</span>`);
      }
      if (c.done) {
        if (head) head.insertAdjacentHTML("beforeend", `<button type="button" class="cmt-count done" data-goto-slide="${id}" title="本页已决定的意见">${c.done}</button>`);
        if (tocLink && !c.open) tocLink.insertAdjacentHTML("beforeend", `<span class="cmt-count done">${c.done}</span>`);
      }
    });
    for (const thread of visibleThreads()) {
      thread._marks = [];
      const root = document.querySelector(`[data-field="${CSS.escape(thread.field)}"]`);
      if (!root || root.hidden) continue;
      const at = locate(root, thread);
      if (at < 0) continue;
      thread._marks = wrapRange(root, at, at + thread.quote.length, `cmt-mark${thread.status === "resolved" ? " resolved" : ""}`, thread.id);
    }
    renderCards();
  }

  const fmtTime = (iso) => {
    const d = new Date(iso);
    return isNaN(d) ? "" : `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };
  const avatar = (name) => `<span class="avatar${/agent|claude|codex/i.test(name) ? " agent" : ""}">${esc((name || "?").slice(0, 1).toUpperCase())}</span>`;

  function cardHtml(thread) {
    const orphan = !thread._marks || !thread._marks.length;
    if (thread.status === "resolved" && thread.id !== activeThread) {
      // Collapsed decision record: the question and the final word, one line each.
      const first = thread.messages[0];
      const last = thread.messages[thread.messages.length - 1];
      const line = (m) => `<div class="decision-line"><b>${esc(m.author)}</b>${esc(m.text).replace(/\n/g, " ")}</div>`;
      return `<div class="card is-resolved collapsed" data-card="${thread.id}">
        <div class="card-top"><span class="decided">✓ 已决定</span><span class="card-quote" title="${esc(thread.quote)}">${esc(thread.quote)}</span></div>
        ${line(first)}${thread.messages.length > 1 ? line(last) : ""}
        <div class="card-meta">${esc(thread.slide)} · ${thread.id} · ${esc(thread.status_by || "")} ${fmtTime(thread.status_at)} 决定 · ${thread.messages.length} 条${orphan ? ' · <span class="warn">原文已修改</span>' : ""}</div>
      </div>`;
    }
    const msgs = thread.messages.map((m, i) => {
      const key = `${thread.id}:${i}`;
      return `
      <div class="msg">${avatar(m.author)}<div class="msg-main"><div class="msg-head"><b>${esc(m.author)}</b><span>${fmtTime(m.at)}</span></div><div class="msg-text${expandedMsgs.has(key) ? " full" : ""}" data-msg="${key}">${esc(m.text).replace(/\n/g, "<br>")}</div></div></div>`;
    }).join("");
    const resolved = thread.status === "resolved";
    const isActive = thread.id === activeThread;
    return `<div class="card${resolved ? " is-resolved" : ""}${thread.id === activeThread ? " active" : ""}" data-card="${thread.id}">
      <div class="card-top">
        <span class="card-quote" title="${esc(thread.quote)}">${esc(thread.quote)}</span>
        <span class="card-tools">
          <button type="button" data-card-nav="next" title="下一条">⌄</button>
          <button type="button" data-card-nav="prev" title="上一条">⌃</button>
          <button type="button" data-card-status="${resolved ? "open" : "resolved"}" title="${resolved ? "重新打开" : "解决"}">${resolved ? "↺" : "✓"}</button>
          ${isActive ? '<button type="button" class="collapse" data-card-collapse title="收起（Esc）">收起</button>' : ""}
        </span>
      </div>
      <div class="card-meta">${esc(thread.slide)} · ${thread.id}${orphan ? ' · <span class="warn">原文已修改，找不到引用位置</span>' : ""}${resolved ? ` · <span class="decided">✓ ${esc(thread.status_by || "")} ${fmtTime(thread.status_at)} 决定</span>` : ""}</div>
      ${msgs}
      ${!resolved && thread.messages.length && thread.messages[thread.messages.length - 1].author !== author ? `
      <div class="quick">
        <button type="button" class="btn primary" data-quick="resolve">✓ 同意并解决</button>
        <button type="button" class="btn" data-quick="agree">同意</button>
      </div>` : ""}
      <textarea class="reply" rows="1" placeholder="回复（Enter 发送，Shift+Enter 换行）"></textarea>
    </div>`;
  }

  function renderCards() {
    const threads = visibleThreads();
    const order = (t) => {
      const el = (t._marks && t._marks[0]) || document.getElementById(anchor(t.slide));
      return el ? el.getBoundingClientRect().top + window.scrollY : Number.MAX_SAFE_INTEGER;
    };
    threads.sort((a, b) => order(a) - order(b));
    railCards.innerHTML = (composer ? composerHtml() : "") + threads.map(cardHtml).join("") +
      (threads.length || composer ? "" : `<div class="rail-empty">${filterMode === "resolved" ? "还没有已决定的意见。" : "选中正文里的文字，就可以在这里加评论。"}</div>`);
    // Long messages show five lines first; "展开全文" reveals the rest.
    railCards.querySelectorAll(".msg-text:not(.full)").forEach((el) => {
      if (el.scrollHeight > el.clientHeight + 2) el.insertAdjacentHTML("afterend", '<button type="button" class="more" data-msg-toggle>展开全文</button>');
    });
    railCards.querySelectorAll(".msg-text.full").forEach((el) => el.insertAdjacentHTML("afterend", '<button type="button" class="more" data-msg-toggle>收起全文</button>'));
    if (composer) {
      const box = railCards.querySelector(".composer textarea");
      box.value = composer.text || "";
      box.addEventListener("input", () => { composer.text = box.value; });
      setTimeout(() => box.focus(), 0);
    }
    layoutCards();
  }

  function composerHtml() {
    return `<div class="card composer active" data-card="__new">
      <div class="card-top"><span class="card-quote">${esc(composer.quote)}</span></div>
      <div class="msg">${avatar(author)}<div class="msg-main"><div class="msg-head"><b>${esc(author)}</b></div>
      <textarea rows="3" placeholder="写下评论（⌘/Ctrl+Enter 发送，Esc 取消）"></textarea>
      <div class="composer-bar"><button type="button" class="btn" data-composer="cancel">取消</button><button type="button" class="btn primary" data-composer="send">评论</button></div></div></div>
    </div>`;
  }

  function anchorTop(id) {
    if (id === "__new") return composer && composer.top;
    const t = comments.threads.find((x) => x.id === id);
    const el = t && ((t._marks && t._marks[0]) || document.getElementById(anchor(t.slide)));
    return el ? el.getBoundingClientRect().top + window.scrollY : null;
  }

  function layoutCards() {
    if (!live) return;
    const cards = [...railCards.querySelectorAll(".card")];
    if (listMode() || rail.hidden) { cards.forEach((c) => { c.style.top = ""; }); railCards.style.height = ""; return; }
    const base = railCards.getBoundingClientRect().top + window.scrollY;
    let cursor = 0;
    const placed = cards.map((card) => ({ card, want: (anchorTop(card.dataset.card) ?? base) - base }))
      .sort((a, b) => a.want - b.want);
    const activeIndex = placed.findIndex((p) => p.card.classList.contains("active"));
    placed.forEach((p) => { p.top = Math.max(p.want, cursor); cursor = p.top + p.card.offsetHeight + 10; });
    if (activeIndex > 0) {
      // Keep the active card level with its text; push earlier cards up when they collide.
      const a = placed[activeIndex];
      a.top = Math.max(a.want, 0);
      for (let i = activeIndex - 1; i >= 0; i--) {
        const next = placed[i + 1];
        placed[i].top = Math.min(placed[i].top, next.top - placed[i].card.offsetHeight - 10);
      }
      for (let i = activeIndex + 1; i < placed.length; i++) {
        const prev = placed[i - 1];
        placed[i].top = Math.max(placed[i].want, prev.top + prev.card.offsetHeight + 10);
      }
    }
    placed.forEach((p) => { p.card.style.top = `${p.top}px`; });
    railCards.style.height = `${Math.max(cursor, ...placed.map((p) => p.top + p.card.offsetHeight)) + 40}px`;
  }

  function activate(id, scroll) {
    const wasCollapsed = !!railCards.querySelector(`.card.collapsed[data-card="${CSS.escape(id)}"]`);
    const leavingResolved = activeThread && comments.threads.some((t) => t.id === activeThread && t.status === "resolved");
    activeThread = id;
    document.querySelectorAll("mark.cmt-mark").forEach((m) => m.classList.toggle("active", m.dataset.thread === id));
    if (wasCollapsed || leavingResolved) renderCards();
    else railCards.querySelectorAll(".card").forEach((c) => c.classList.toggle("active", c.dataset.card === id));
    if (rail.hidden) toggleRail(true);
    layoutCards();
    if (scroll) {
      const t = comments.threads.find((x) => x.id === id);
      const el = t && ((t._marks && t._marks[0]) || document.getElementById(anchor(t.slide)));
      if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
      if (listMode()) { const card = railCards.querySelector(`[data-card="${id}"]`); if (card) card.scrollIntoView({ block: "nearest" }); }
    }
  }

  function deactivate() {
    if (!activeThread || activeThread === "__new") return;
    const wasResolved = comments.threads.some((t) => t.id === activeThread && t.status === "resolved");
    activeThread = null;
    document.querySelectorAll("mark.cmt-mark.active").forEach((m) => m.classList.remove("active"));
    if (wasResolved) renderCards();
    else { railCards.querySelectorAll(".card.active").forEach((c) => c.classList.remove("active")); layoutCards(); }
  }

  function toggleRail(force) {
    const show = typeof force === "boolean" ? force : rail.hidden;
    rail.hidden = !show;
    document.getElementById("rail-tab").hidden = show;
    document.body.classList.toggle("rail-open", show);
    try { localStorage.setItem("draft-studio-rail", show ? "1" : "0"); } catch (_) { /* optional */ }
    layoutCards();
  }

  // Selection → floating "评论" button
  function selectionTarget() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const range = sel.getRangeAt(0);
    const quote = sel.toString().replace(/\s+/g, " ").trim();
    if (!quote || quote.length > 500) return null;
    const start = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
    const end = range.endContainer.nodeType === 1 ? range.endContainer : range.endContainer.parentElement;
    const root = start.closest("[data-field]");
    if (!root || root !== end.closest("[data-field]") || !root.closest(".slide, .chapter-intro") || root.closest(".editor")) return null;
    const slideEl = root.closest(".slide");
    const before = document.createRange();
    before.setStart(root, 0);
    before.setEnd(range.startContainer, range.startOffset);
    const offset = before.toString().length;
    const full = textNodes(root).map((n) => n.nodeValue).join("");
    const exact = full.slice(offset, offset + range.toString().length);
    return {
      field: root.dataset.field,
      slide: slideEl ? slideEl.dataset.slideId : "",
      quote: exact.trim() || quote,
      prefix: full.slice(Math.max(0, offset - 30), offset),
      suffix: full.slice(offset + exact.length, offset + exact.length + 30),
      rect: range.getBoundingClientRect(),
      root, offset, length: exact.length,
    };
  }

  function updateSelButton() {
    const target = live && !editing ? selectionTarget() : null;
    if (!target) { selButton.hidden = true; selButton._target = null; return; }
    selButton._target = target;
    selButton.hidden = false;
    const r = target.rect;
    selButton.style.top = `${Math.max(70, r.top - 40)}px`;
    selButton.style.left = `${Math.min(window.innerWidth - 90, r.right - 30)}px`;
  }

  function startComposer(target) {
    selButton.hidden = true;
    window.getSelection().removeAllRanges();
    wrapRange(target.root, target.offset, target.offset + target.length, "cmt-mark pending", null);
    const pending = document.querySelector("mark.cmt-mark.pending");
    composer = {
      slide: target.slide, field: target.field, quote: target.quote, prefix: target.prefix, suffix: target.suffix,
      top: pending ? pending.getBoundingClientRect().top + window.scrollY : target.rect.top + window.scrollY,
    };
    activeThread = "__new";
    if (rail.hidden) toggleRail(true);
    renderCards();
  }

  function cancelComposer() {
    composer = null;
    activeThread = null;
    applyComments();
  }

  async function sendComposer() {
    const text = (railCards.querySelector(".composer textarea") || {}).value || "";
    if (!text.trim()) return;
    try {
      const { thread } = await api("/api/comments", { ...composer, text, author, rect: undefined });
      composer = null;
      await loadComments(false);
      activate(thread.id, false);
    } catch (err) { toast(`评论没有保存：${err.message}`); }
  }

  async function sendReply(card, textarea) {
    const text = textarea.value.trim();
    if (!text) return;
    try {
      await api("/api/comments/reply", { id: card.dataset.card, text, author });
      activeThread = card.dataset.card;
      await loadComments(false);
    } catch (err) { toast(`回复没有保存：${err.message}`); }
  }

  async function quickAgree(id, resolve) {
    try {
      await api("/api/comments/reply", { id, text: "同意。", author, resolve });
      if (resolve) activeThread = null;
      await loadComments(false);
      toast(resolve ? `${id} 已同意并解决` : `${id} 已回复同意`, "ok");
    } catch (err) { toast(`没有保存：${err.message}`); }
  }

  async function setStatus(id, status) {
    try {
      await api("/api/comments/status", { id, status, author });
      if (status === "resolved") activeThread = null;
      if (status === "resolved" && filterMode === "open") toast("已决定的意见在“全部”或“已决定”里可以回看");
      await loadComments(false);
      toast(status === "resolved" ? `${id} 已解决` : `${id} 已重新打开`, "ok");
    } catch (err) { toast(err.message); }
  }

  function navigate(id, dir) {
    const ids = [...railCards.querySelectorAll(".card:not(.composer)")].map((c) => c.dataset.card);
    const i = ids.indexOf(id);
    const next = ids[(i + (dir === "next" ? 1 : -1) + ids.length) % ids.length];
    if (next) activate(next, true);
  }

  if (live) {
    document.getElementById("rail-toggle").hidden = false;
    document.getElementById("design-link").hidden = false;
    document.getElementById("rail-author").textContent = `署名：${author} ✎`;
    document.addEventListener("selectionchange", () => requestAnimationFrame(updateSelButton));
    window.addEventListener("scroll", () => { if (!selButton.hidden) updateSelButton(); }, { passive: true });
    selButton.addEventListener("mousedown", (e) => e.preventDefault());
    selButton.addEventListener("click", () => { if (selButton._target) startComposer(selButton._target); });
    document.getElementById("rail-filter").addEventListener("click", (e) => {
      const b = e.target.closest("[data-filter]");
      if (!b) return;
      filterMode = b.dataset.filter;
      try { localStorage.setItem("draft-studio-filter", filterMode); } catch (_) { /* optional */ }
      applyComments();
    });
    document.getElementById("rail-author").addEventListener("click", () => {
      const name = window.prompt("评论署名", author);
      if (name && name.trim()) {
        author = name.trim().slice(0, 40);
        try { localStorage.setItem("draft-studio-author", author); } catch (_) { /* optional */ }
        document.getElementById("rail-author").textContent = `署名：${author} ✎`;
        renderCards();
      }
    });
    document.addEventListener("click", (e) => {
      const confirmBtn = e.target.closest("[data-confirm-chapter]");
      if (confirmBtn) {
        const id = confirmBtn.dataset.confirmChapter;
        const ch = model.chapters.find((c) => c.studio && c.studio.chapter_id === id);
        const n = ch ? ch.slides.length : 0;
        if (window.confirm(`确认 ${id} 的全部 ${n} 页？\n确认会记录每一页当前的内容；之后再修改，这一章会自动退回待确认。`)) {
          authorityPost("/api/confirm", { chapter_id: id, author }, `${id} 已确认`);
        }
        return;
      }
      if (e.target.closest("[data-register]")) { authorityPost("/api/register", {}, "已登记当前版本"); return; }
      const mark = e.target.closest("mark.cmt-mark[data-thread]");
      if (mark) { activate(mark.dataset.thread, false); return; }
      const goto = e.target.closest("[data-goto-slide]");
      if (goto) {
        const mine = comments.threads.filter((t) => t.slide === goto.dataset.gotoSlide);
        const first = mine.find((t) => t.status === "open") || mine[0];
        if (first) activate(first.id, true);
        return;
      }
      if (e.target.closest("[data-composer]")) {
        e.target.closest("[data-composer]").dataset.composer === "send" ? sendComposer() : cancelComposer();
        return;
      }
      const card = e.target.closest(".card[data-card]");
      if (!card) {
        // A click on empty space (not a selection, control or the rail) puts the active card away.
        const selecting = !window.getSelection().isCollapsed;
        if (!selecting && !e.target.closest(".rail, button, a, input, textarea, .editor, .sel-comment, summary")) deactivate();
        return;
      }
      if (card.dataset.card === "__new") return;
      const toggleMsg = e.target.closest("[data-msg-toggle]");
      if (toggleMsg) {
        const text = toggleMsg.previousElementSibling;
        const key = text.dataset.msg;
        expandedMsgs.has(key) ? expandedMsgs.delete(key) : expandedMsgs.add(key);
        text.classList.toggle("full");
        toggleMsg.textContent = text.classList.contains("full") ? "收起全文" : "展开全文";
        layoutCards();
        return;
      }
      if (e.target.closest("[data-card-collapse]")) { deactivate(); return; }
      const quick = e.target.closest("[data-quick]");
      if (quick) { quickAgree(card.dataset.card, quick.dataset.quick === "resolve"); return; }
      const nav = e.target.closest("[data-card-nav]");
      const status = e.target.closest("[data-card-status]");
      if (nav) navigate(card.dataset.card, nav.dataset.cardNav);
      else if (status) setStatus(card.dataset.card, status.dataset.cardStatus);
      else if (!e.target.closest("textarea")) activate(card.dataset.card, true);
    });
    railCards.addEventListener("keydown", (e) => {
      const box = e.target.closest("textarea");
      if (!box) return;
      const card = box.closest(".card");
      if (card.dataset.card === "__new") {
        if (e.key === "Escape") { e.preventDefault(); cancelComposer(); }
        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendComposer(); }
        return;
      }
      if (e.key === "Escape" && !box.value.trim()) { e.preventDefault(); box.blur(); deactivate(); }
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendReply(card, box); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || editing || composer) return;
      if (e.target.closest && e.target.closest("textarea, input")) return;
      deactivate();
    });
    railCards.addEventListener("focusin", (e) => {
      const card = e.target.closest(".card[data-card]");
      if (card && card.dataset.card !== "__new" && activeThread !== card.dataset.card) activate(card.dataset.card, false);
    });
    new ResizeObserver(() => layoutCards()).observe(document.getElementById("doc"));
    window.addEventListener("resize", () => layoutCards());
    document.addEventListener("toggle", () => layoutCards(), true);
    let railPref = "1";
    try { railPref = localStorage.getItem("draft-studio-rail") ?? "1"; } catch (_) { /* default open */ }
    toggleRail(railPref === "1" && !listMode());
  }

  render();
  let saved = "full";
  try { saved = localStorage.getItem("draft-studio-view") || "full"; } catch (_) { /* default view */ }
  setView(saved);
  scrollSpy();
  connect();
  if (live) loadComments(false).catch(() => toast("评论加载失败"));

  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, a");
    if (!t) return;
    if (t.dataset.view) setView(t.dataset.view);
    if (t.dataset.download) { download(t.dataset.download); document.getElementById("export-menu").hidden = true; }
    if (t.dataset.action === "toggle-menu") { const m = document.getElementById("export-menu"); m.hidden = !m.hidden; }
    if (t.dataset.action === "print") { document.getElementById("export-menu").hidden = true; window.print(); }
    if (t.dataset.action === "toggle-toc") document.body.classList.toggle("toc-open");
    if (t.dataset.action === "toggle-rail" && live) toggleRail();
    if (t.classList.contains("toc-slide")) document.body.classList.remove("toc-open");
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".menu")) document.getElementById("export-menu").hidden = true;
  });
  document.getElementById("search").addEventListener("input", (e) => filter(e.target.value));
})();
