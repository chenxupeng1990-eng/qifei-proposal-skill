(() => {
  "use strict";
  // Design review: draw a box on a captured page, comment, and let the agent answer.
  // Boxes are stored in 1920×1080 page pixels; the PNG hash tells whether the page has changed since.
  const live = JSON.parse(document.getElementById("live").textContent);
  const W = 1920, H = 1080;
  const $ = id => document.getElementById(id);
  const stage = $("d-stage"), img = $("d-img"), draftBox = $("d-draft");
  let pages = [], threads = [], current = 0, filter = "open", activeId = null, pending = null;
  let author = "Owner";
  try { author = localStorage.getItem("draft-studio-author") || "Owner"; } catch (_) { /* default author */ }

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fileUrl = rel => `/files/${rel.split("/").map(encodeURIComponent).join("/")}?token=${encodeURIComponent(live.token)}`;
  const page = () => pages[current];

  function toast(text) {
    const node = $("d-toast");
    node.textContent = text;
    node.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => node.classList.remove("show"), 2600);
  }

  async function api(path, body) {
    const res = await fetch(path, body ? {
      method: "POST", headers: { "Content-Type": "application/json", "X-Studio-Token": live.token }, body: JSON.stringify(body),
    } : { headers: { "X-Studio-Token": live.token } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  async function load() {
    const data = await api("/api/design");
    const keep = page() && page().slide_id;
    pages = data.pages;
    threads = data.threads;
    const at = pages.findIndex(p => p.slide_id === keep);
    current = at >= 0 ? at : Math.min(current, Math.max(0, pages.length - 1));
    render();
  }

  function visible(slide) {
    return threads.filter(t => (!slide || t.slide === slide) && (filter === "all" || t.status === "open"));
  }

  function render() {
    $("d-empty").hidden = pages.length > 0;
    stage.hidden = !pages.length;
    $("d-author").textContent = `署名：${author}`;
    $("d-pages").innerHTML = pages.map((p, i) => {
      const open = threads.filter(t => t.slide === p.slide_id && t.status === "open").length;
      return `<button type="button" class="d-page${i === current ? " active" : ""}" data-index="${i}">${esc(p.slide_id)}${open ? `<span class="d-badge">${open}</span>` : ""}</button>`;
    }).join("");
    if (!pages.length) { $("d-threads").innerHTML = ""; return; }
    const p = page();
    $("d-slide").textContent = `${p.slide_id} · ${current + 1}/${pages.length}`;
    const src = fileUrl(p.png_path) + `&v=${p.png_sha256.slice(0, 12)}`;
    if (img.dataset.src !== src) { img.src = src; img.dataset.src = src; }
    const shown = visible(p.slide_id);
    $("d-boxes").innerHTML = shown.map(t => {
      const r = t.rect;
      const cls = ["d-box", t.stale ? "stale" : "", t.status === "resolved" ? "resolved" : "", t.id === activeId ? "active" : ""].join(" ");
      return `<div class="${cls}" data-id="${t.id}" style="left:${r.x / W * 100}%;top:${r.y / H * 100}%;width:${r.w / W * 100}%;height:${r.h / H * 100}%"><b>${t.id}</b></div>`;
    }).join("");
    $("d-threads").innerHTML = shown.length ? shown.map(card).join("") : `<p class="d-none">${filter === "open" ? "这一页没有未解决的评论。" : "这一页还没有评论。"}</p>`;
  }

  function card(t) {
    const tags = `<span class="tag ${t.status}">${t.status === "open" ? "未解决" : "已解决"}</span>${t.stale ? '<span class="tag stale" title="评论之后页面重新渲染过，框的位置可能已经变了">页面已更新</span>' : ""}`;
    const messages = t.messages.map(m => `<div class="dmsg"><span>${esc(m.author)} ${esc(m.at.slice(5, 16).replace("T", " "))}</span>${esc(m.text)}</div>`).join("");
    const toggle = t.status === "open"
      ? `<button type="button" class="btn" data-status="resolved">解决</button>`
      : `<button type="button" class="btn" data-status="open">重新打开</button>`;
    return `<div class="dcard${t.id === activeId ? " active" : ""}" data-id="${t.id}">
      <div class="dcard-top"><strong>${t.id}</strong>${tags}</div>
      ${t.crop_path ? `<img class="dcard-crop" src="${fileUrl(t.crop_path)}" alt="框选区域">` : ""}
      ${t.anchor ? `<div class="dcard-anchor">“${esc(t.anchor.text)}”</div>` : ""}
      ${messages}
      <textarea rows="2" placeholder="回复…"></textarea>
      <div class="d-actions"><button type="button" class="btn ghost" data-status="deleted" title="删除这条评论">删除</button>${toggle}<button type="button" class="btn primary" data-reply>回复</button></div>
    </div>`;
  }

  // Drawing: pointer position → page pixels.
  function toPage(event) {
    const box = stage.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W, (event.clientX - box.left) / box.width * W)),
      y: Math.max(0, Math.min(H, (event.clientY - box.top) / box.height * H)),
    };
  }
  let start = null;
  stage.addEventListener("pointerdown", event => {
    if (event.target.closest(".d-box") || !pages.length) return;
    start = toPage(event);
    stage.setPointerCapture(event.pointerId);
    draftBox.hidden = true;
  });
  stage.addEventListener("pointermove", event => {
    if (!start) return;
    const end = toPage(event);
    const r = { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), w: Math.abs(end.x - start.x), h: Math.abs(end.y - start.y) };
    Object.assign(draftBox.style, { left: `${r.x / W * 100}%`, top: `${r.y / H * 100}%`, width: `${r.w / W * 100}%`, height: `${r.h / H * 100}%` });
    draftBox.hidden = false;
    pending = { rect: r };
  });
  stage.addEventListener("pointerup", () => {
    if (!start) return;
    start = null;
    if (!pending || pending.rect.w < 8 || pending.rect.h < 8) { draftBox.hidden = true; pending = null; return; }
    openComposer();
  });

  function openComposer() {
    const r = pending.rect;
    const scale = img.naturalWidth / W || 1;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(r.w * scale);
    canvas.height = Math.round(r.h * scale);
    canvas.getContext("2d").drawImage(img, r.x * scale, r.y * scale, r.w * scale, r.h * scale, 0, 0, canvas.width, canvas.height);
    pending.crop = canvas.toDataURL("image/png");
    pending.slide = page().slide_id;
    pending.png_sha256 = page().png_sha256;
    $("d-crop").src = pending.crop;
    const boxes = page().text_boxes || [];
    const anchor = bestAnchor(r, boxes);
    $("d-anchor").textContent = anchor ? `框住的文字：“${anchor}”`
      : boxes.length ? "框里没有文字（底图或配图区域）" : "这页截图没有记录文字位置，Agent 按框的坐标和截图定位";
    $("d-composer").hidden = false;
    $("d-text").value = "";
    $("d-text").focus();
  }

  function bestAnchor(r, boxes) {
    let best = null, score = 0;
    for (const b of boxes) {
      const ix = Math.max(0, Math.min(r.x + r.w, b.x + b.w) - Math.max(r.x, b.x));
      const iy = Math.max(0, Math.min(r.y + r.h, b.y + b.h) - Math.max(r.y, b.y));
      const s = ix * iy / Math.max(1, b.w * b.h);
      if (s > score) { best = b; score = s; }
    }
    return best && best.text;
  }

  function closeComposer() {
    pending = null;
    draftBox.hidden = true;
    $("d-composer").hidden = true;
  }

  $("d-cancel").addEventListener("click", closeComposer);
  $("d-send").addEventListener("click", async () => {
    const text = $("d-text").value.trim();
    if (!text) return toast("先写下要改的地方");
    try {
      const data = await api("/api/design/comments", { ...pending, text, author });
      activeId = data.thread.id;
      threads = data.threads;
      closeComposer();
      render();
      toast(`${data.thread.id} 已发送，Agent 可以用 design_review.py list 看到`);
    } catch (error) { toast(error.message); }
  });

  document.addEventListener("click", async event => {
    const pageButton = event.target.closest(".d-page");
    if (pageButton) { current = Number(pageButton.dataset.index); activeId = null; closeComposer(); return render(); }
    const filterButton = event.target.closest("[data-filter]");
    if (filterButton) {
      filter = filterButton.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach(b => b.classList.toggle("active", b === filterButton));
      return render();
    }
    if (event.target.id === "d-author") {
      const name = prompt("评论署名", author);
      if (name && name.trim()) {
        author = name.trim().slice(0, 40);
        try { localStorage.setItem("draft-studio-author", author); } catch (_) { /* optional */ }
        render();
      }
      return;
    }
    const target = event.target.closest(".dcard, .d-box");
    if (!target) return;
    const id = target.dataset.id;
    const thread = threads.find(t => t.id === id);
    if (event.target.closest("[data-reply]")) {
      const text = target.querySelector("textarea").value.trim();
      if (!text) return toast("回复不能为空");
      try { threads = (await api("/api/design/reply", { id, text, author })).threads; render(); } catch (error) { toast(error.message); }
      return;
    }
    const status = event.target.closest("[data-status]");
    if (status) {
      if (status.dataset.status === "deleted" && !window.confirm(`删除评论 ${id}？删除后不再显示，记录仍保留在文件里。`)) return;
      try { threads = (await api("/api/design/status", { id, status: status.dataset.status, author })).threads; render(); } catch (error) { toast(error.message); }
      return;
    }
    if (event.target.closest("textarea")) return;
    if (activeId !== id) { activeId = id; if (thread) current = Math.max(0, pages.findIndex(p => p.slide_id === thread.slide)); render(); }
  });

  document.addEventListener("keydown", event => {
    if (event.target.closest("textarea, input")) return;
    if (event.key === "ArrowRight" && current < pages.length - 1) { current += 1; activeId = null; closeComposer(); render(); }
    if (event.key === "ArrowLeft" && current > 0) { current -= 1; activeId = null; closeComposer(); render(); }
    if (event.key === "Escape") closeComposer();
  });

  const source = new EventSource(`/api/events?token=${encodeURIComponent(live.token)}`);
  source.addEventListener("design", () => load().catch(() => toast("评论刷新失败")));
  window.addEventListener("focus", () => load().catch(() => {}));  // pick up pages captured again meanwhile
  load().catch(error => toast(`加载失败：${error.message}`));
})();
