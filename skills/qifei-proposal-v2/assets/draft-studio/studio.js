(() => {
  "use strict";
  const model = JSON.parse(document.getElementById("model").textContent);
  const markdown = JSON.parse(document.getElementById("markdown").textContent);
  const STATUS = {
    confirmed: "已确认",
    verified: "已回读",
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

  function fieldHtml(field, slide) {
    let body;
    if (field.key === "screen") body = screenHtml(field.md, slide.title);
    else if (field.key === "visual") body = visualHtml(field.md);
    else if (field.key === "logic") body = logicHtml(field.md);
    else if (field.key === "lead") body = `<figure class="preview">${block(field.md)}</figure>`;
    else body = `<div class="md">${block(field.md)}</div>`;
    if (INTERNAL.has(field.key)) {
      return `<details class="internal field field-${field.key}"><summary>${field.name}<span class="tag">内部</span></summary>${body}</details>`;
    }
    const label = field.key === "lead" ? "" : `<div class="field-label">${field.name}${field.key === "visual" ? '<span class="tag">生产</span>' : ""}</div>`;
    return `<section class="field field-${field.key}">${label}${body}</section>`;
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
    document.getElementById("doc-meta").innerHTML = metaBits.join(" · ");

    const counts = {};
    const all = model.chapters.flatMap((c) => c.slides);
    all.forEach((s) => { counts[s.status] = (counts[s.status] || 0) + 1; });

    const toc = [`<div class="toc-summary">${Object.keys(STATUS).filter((k) => counts[k]).map((k) => `<span class="chip st-${k}">${STATUS[k]} ${counts[k]}</span>`).join("")}</div>`];
    const doc = [`<div class="doc-head"><h1>${inline(model.title)}</h1><div class="sub">${model.chapters.length} 章 · ${all.length} 页 · 来源 <code>${esc(meta.source || "")}</code></div></div>`];
    if (model.preface_md) doc.push(`<div class="preface md">${block(model.preface_md)}</div>`);

    model.chapters.forEach((ch, ci) => {
      toc.push(`<div class="toc-chapter"><a href="#${ch.id}">${ci + 1}. ${inline(ch.title)}</a>${ch.slides.map((s) => `<a class="toc-slide" href="#${anchor(s.id)}" data-slide="${s.id}"><span class="dot st-${s.status}"></span><span class="sid">${s.id}</span><span class="t">${inline(s.title)}</span></a>`).join("")}</div>`);
      const chain = ch.slides.length > 1
        ? `<div class="chain"><div class="chain-label">本章标题链（连起来读，检查论证是否断开）</div><ol>${ch.slides.map((s) => `<li><span class="sid">${s.id}</span><a href="#${anchor(s.id)}">${inline(s.title)}</a></li>`).join("")}</ol></div>`
        : "";
      doc.push(`<section class="chapter" id="${ch.id}" data-chapter><div class="chapter-head"><div class="chapter-kicker">Chapter ${String(ci + 1).padStart(2, "0")}</div><h2>${inline(ch.title)}</h2><div class="chapter-intro md">${block(ch.intro_md)}</div>${chain}</div>`);
      ch.slides.forEach((s) => {
        doc.push(`<article class="slide" id="${anchor(s.id)}" data-slide-id="${s.id}"><div class="slide-head"><span class="slide-id">${s.id}</span><h3 class="slide-title">${inline(s.title)}</h3>${chip(s.status)}</div><div class="slide-body">${s.fields.map((f) => fieldHtml(f, s)).join("")}</div></article>`);
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

  function download(profile) {
    const blob = new Blob([markdown[profile]], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${model.title.replace(/[\\/:*?"<>|｜]+/g, "-")}${profile === "brief" ? "-简洁版" : ""}.md`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function scrollSpy() {
    const links = new Map([...document.querySelectorAll(".toc-slide")].map((a) => [a.dataset.slide, a]));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        links.forEach((a) => a.classList.remove("active"));
        const link = links.get(e.target.dataset.slideId);
        if (link) { link.classList.add("active"); link.scrollIntoView({ block: "nearest" }); }
      });
    }, { rootMargin: "-80px 0px -70% 0px" });
    document.querySelectorAll(".slide").forEach((el) => io.observe(el));
  }

  render();
  let saved = "full";
  try { saved = localStorage.getItem("draft-studio-view") || "full"; } catch (_) { /* default view */ }
  setView(saved);
  scrollSpy();

  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, a");
    if (!t) return;
    if (t.dataset.view) setView(t.dataset.view);
    if (t.dataset.download) { download(t.dataset.download); document.getElementById("export-menu").hidden = true; }
    if (t.dataset.action === "toggle-menu") { const m = document.getElementById("export-menu"); m.hidden = !m.hidden; }
    if (t.dataset.action === "print") { document.getElementById("export-menu").hidden = true; window.print(); }
    if (t.dataset.action === "toggle-toc") document.body.classList.toggle("toc-open");
    if (t.classList.contains("toc-slide")) document.body.classList.remove("toc-open");
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".menu")) document.getElementById("export-menu").hidden = true;
  });
  document.getElementById("search").addEventListener("input", (e) => filter(e.target.value));
})();
