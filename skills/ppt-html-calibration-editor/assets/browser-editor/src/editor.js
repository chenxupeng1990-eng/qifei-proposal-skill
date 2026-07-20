import { createStateStore } from './state.js';

const LOGICAL_WIDTH = 1920;
const LOGICAL_HEIGHT = 1080;
const SNAP_X = [0, 96, 960, 1824, 1920];
const SNAP_Y = [0, 72, 540, 1008, 1080];

const number = (value, fallback = 0) => Number.isFinite(Number.parseFloat(value)) ? Number.parseFloat(value) : fallback;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function snap(value, targets, bypass) {
  if (bypass) return value;
  const hit = targets.find((target) => Math.abs(value - target) <= 6);
  return hit ?? value;
}

function logicalRect(element, canvas) {
  const canvasRect = canvas.getBoundingClientRect();
  const rect = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  const scaleX = canvasRect.width / LOGICAL_WIDTH;
  const scaleY = canvasRect.height / LOGICAL_HEIGHT;
  return {
    x: (rect.left - canvasRect.left) / scaleX - number(style.marginLeft),
    y: (rect.top - canvasRect.top) / scaleY - number(style.marginTop),
    width: rect.width / scaleX,
    height: rect.height / scaleY,
  };
}

function elementState(element, canvas) {
  const rect = logicalRect(element, canvas);
  const style = getComputedStyle(element);
  const base = {
    type: element.dataset.editable,
    x: Math.round(rect.x * 100) / 100,
    y: Math.round(rect.y * 100) / 100,
    width: Math.round(rect.width * 100) / 100,
    height: Math.round(rect.height * 100) / 100,
    opacity: number(style.opacity, 1),
    zIndex: number(style.zIndex, 1),
  };
  if (base.type === 'text') {
    const fontSize = number(style.fontSize, 16);
    const lineHeight = style.lineHeight === 'normal' ? 1.2 : number(style.lineHeight, fontSize * 1.2) / fontSize;
    return { ...base, text: element.innerText, fontSize, fontWeight: number(style.fontWeight, 400), lineHeight: Math.round(lineHeight * 1000) / 1000, color: style.color, textAlign: style.textAlign };
  }
  return { ...base, src: element.getAttribute('src') || '', sourceFileName: element.dataset.sourceFileName || '' };
}

function applyState(element, state) {
  element.style.position = 'absolute';
  element.style.left = `${state.x}px`;
  element.style.top = `${state.y}px`;
  element.style.width = `${state.width}px`;
  element.style.height = `${state.height}px`;
  element.style.opacity = `${state.opacity ?? 1}`;
  element.style.zIndex = `${state.zIndex ?? 1}`;
  if (state.type === 'text') {
    const legacyText = state.html == null ? null : (() => {
      const holder = document.createElement('textarea');
      holder.innerHTML = String(state.html).replace(/<[^>]*>/g, '');
      return holder.value;
    })();
    element.textContent = state.text ?? legacyText ?? element.textContent;
    element.style.fontSize = `${state.fontSize}px`;
    element.style.fontWeight = `${state.fontWeight}`;
    element.style.lineHeight = `${state.lineHeight}`;
    element.style.color = state.color;
    element.style.textAlign = state.textAlign;
  } else if (state.src) {
    element.setAttribute('src', state.src);
    element.dataset.sourceFileName = state.sourceFileName || '';
  }
}

function createUi(slideId) {
  const root = document.createElement('div');
  root.className = 'ppt-editor-root';
  root.innerHTML = `
    <header class="ppt-editor-toolbar">
      <strong>${slideId}</strong><span class="ppt-editor-status">已载入</span>
      <button type="button" data-action="undo" disabled>撤销</button>
      <button type="button" data-action="redo" disabled>重做</button>
      <button type="button" data-action="preview">隐藏框线</button>
      <button type="button" data-action="export" disabled>导出 JSON</button>
      <button type="button" data-action="import" disabled>导入 JSON</button>
      <button type="button" data-action="reset" disabled>恢复本页</button>
    </header>
    <aside class="ppt-editor-panel" hidden>
      <div class="ppt-editor-text-controls">
        <label>字号<input data-prop="fontSize" type="number" min="8" max="200" step="1"></label>
        <label>字重<select data-prop="fontWeight"><option>400</option><option>500</option><option>700</option><option>900</option></select></label>
        <label>行距<input data-prop="lineHeight" type="number" min="0.8" max="3" step="0.05"></label>
        <label>颜色<input data-prop="color" type="color"></label>
        <label>对齐<select data-prop="textAlign"><option value="left">左</option><option value="center">中</option><option value="right">右</option></select></label>
      </div>
      <div class="ppt-editor-image-controls" hidden>
        <label>透明度<input data-prop="opacity" type="range" min="0" max="1" step="0.05"></label>
        <label>层级<input data-prop="zIndex" type="number" min="1" max="999" step="1"></label>
        <button type="button" data-action="replace-image">替换图片</button>
      </div>
    </aside>
    <div class="ppt-editor-selection" hidden>${['nw','n','ne','e','se','s','sw','w'].map(h => `<i class="ppt-editor-handle" data-handle="${h}"></i>`).join('')}</div>
    <div class="ppt-editor-guide guide-x"></div><div class="ppt-editor-guide guide-y"></div>
    <div class="ppt-editor-safe-area"></div>
    <input type="file" accept="image/*" data-role="image-file" hidden>
    <input type="file" accept="application/json,.json" data-role="json-file" hidden>`;
  document.body.append(root);
  return root;
}

function colorToHex(color) {
  const match = color.match(/\d+/g);
  if (!match) return '#000000';
  return `#${match.slice(0, 3).map(value => Number(value).toString(16).padStart(2, '0')).join('')}`;
}

export function mountPptEditor({ canvas, documentId, slideId }) {
  if (!canvas || canvas.dataset.editorMounted === 'true') return null;
  canvas.dataset.editorMounted = 'true';
  document.documentElement.classList.add('ppt-editor-active');
  const stage = document.createElement('div');
  stage.className = 'ppt-editor-stage';
  canvas.parentNode.insertBefore(stage, canvas);
  stage.append(canvas);
  function fitCanvas() {
    const scale = Math.min(1, (innerWidth - 300) / LOGICAL_WIDTH, (innerHeight - 100) / LOGICAL_HEIGHT);
    canvas.style.transformOrigin = 'top left';
    canvas.style.transform = `scale(${scale})`;
    stage.style.width = `${LOGICAL_WIDTH * scale}px`;
    stage.style.height = `${LOGICAL_HEIGHT * scale}px`;
  }
  fitCanvas();
  const store = createStateStore({ documentId, slideId });
  const elements = [...canvas.querySelectorAll('[data-editable][data-edit-id]')];
  const pristineElements = Object.fromEntries(elements.map((element) => [element.dataset.editId, elementState(element, canvas)]));
  const ui = createUi(slideId);
  const selection = ui.querySelector('.ppt-editor-selection');
  const panel = ui.querySelector('.ppt-editor-panel');
  const status = ui.querySelector('.ppt-editor-status');
  const safeArea = ui.querySelector('.ppt-editor-safe-area');
  let selected = null;
  let saveTimer = null;
  let editingText = false;
  let history = [];
  let historyIndex = -1;

  const saved = store.load();
  if (saved) elements.forEach((element) => saved.elements[element.dataset.editId] && applyState(element, saved.elements[element.dataset.editId]));

  function setStatus(message) { status.textContent = message; }
  function currentState() {
    return {
      schemaVersion: 1,
      documentId,
      slideId,
      updatedAt: new Date().toISOString(),
      elements: Object.fromEntries(elements.map((element) => [element.dataset.editId, elementState(element, canvas)])),
    };
  }
  function saveSoon() {
    clearTimeout(saveTimer);
    setStatus('保存中…');
    saveTimer = setTimeout(saveNow, 300);
  }
  function saveNow() {
    clearTimeout(saveTimer);
    store.save(currentState());
    setStatus('已保存到本机浏览器');
  }
  function updateHistoryButtons() {
    ui.querySelector('[data-action="undo"]').disabled = historyIndex <= 0;
    ui.querySelector('[data-action="redo"]').disabled = historyIndex >= history.length - 1;
  }
  function pushHistory() {
    const state = currentState();
    const previous = history[historyIndex];
    if (previous && JSON.stringify(previous.elements) === JSON.stringify(state.elements)) return;
    history = history.slice(0, historyIndex + 1);
    history.push(state);
    if (history.length > 50) history.shift();
    historyIndex = history.length - 1;
    updateHistoryButtons();
  }
  function applySnapshot(state) {
    elements.forEach((element) => {
      const elementData = state.elements[element.dataset.editId];
      if (elementData) applyState(element, elementData);
    });
    refreshOverlay(); syncPanel(); saveNow(); updateHistoryButtons();
  }
  function undo() {
    if (historyIndex <= 0) return;
    historyIndex -= 1;
    applySnapshot(history[historyIndex]);
  }
  function redo() {
    if (historyIndex >= history.length - 1) return;
    historyIndex += 1;
    applySnapshot(history[historyIndex]);
  }
  function refreshOverlay() {
    const canvasRect = canvas.getBoundingClientRect();
    const scaleX = canvasRect.width / LOGICAL_WIDTH;
    const scaleY = canvasRect.height / LOGICAL_HEIGHT;
    Object.assign(safeArea.style, {
      left: `${canvasRect.left + 96 * scaleX}px`,
      top: `${canvasRect.top + 72 * scaleY}px`,
      width: `${1728 * scaleX}px`,
      height: `${936 * scaleY}px`,
    });
    if (!selected || selection.hidden) return;
    const rect = selected.getBoundingClientRect();
    selection.style.left = `${rect.left}px`;
    selection.style.top = `${rect.top}px`;
    selection.style.width = `${rect.width}px`;
    selection.style.height = `${rect.height}px`;
    const logical = logicalRect(selected, canvas);
    selection.classList.toggle('is-outside-canvas', logical.x < 0 || logical.y < 0 || logical.x + logical.width > LOGICAL_WIDTH || logical.y + logical.height > LOGICAL_HEIGHT);
  }
  function syncPanel() {
    if (!selected) return;
    const state = elementState(selected, canvas);
    const text = state.type === 'text';
    ui.querySelector('.ppt-editor-text-controls').hidden = !text;
    ui.querySelector('.ppt-editor-image-controls').hidden = text;
    for (const input of panel.querySelectorAll('[data-prop]')) {
      if (!(input.dataset.prop in state)) continue;
      input.value = input.dataset.prop === 'color' ? colorToHex(state.color) : state[input.dataset.prop];
    }
  }
  function select(element) {
    if (selected) delete selected.dataset.editorSelected;
    selected = element;
    if (!selected) { selection.hidden = true; panel.hidden = true; return; }
    selected.dataset.editorSelected = 'true';
    selection.hidden = false;
    panel.hidden = false;
    syncPanel();
    refreshOverlay();
  }

  function enterTextEdit(element, event) {
    event?.preventDefault();
    event?.stopPropagation();
    select(element);
    editingText = true;
    element.setAttribute('contenteditable', 'true');
    element.focus({ preventScroll: true });
    const range = document.createRange();
    range.selectNodeContents(element);
    const browserSelection = getSelection();
    browserSelection.removeAllRanges();
    browserSelection.addRange(range);
  }

  function beginTransform(event, element, handle = null) {
    if (editingText) return;
    if (!handle && element.dataset.editable === 'text' && event.detail > 1) return;
    if (handle || element.dataset.editable !== 'text') event.preventDefault();
    select(element);
    const start = { x: event.clientX, y: event.clientY, rect: logicalRect(element, canvas) };
    const scaleX = canvas.getBoundingClientRect().width / LOGICAL_WIDTH;
    const scaleY = canvas.getBoundingClientRect().height / LOGICAL_HEIGHT;
    function move(moveEvent) {
      const dx = (moveEvent.clientX - start.x) / scaleX;
      const dy = (moveEvent.clientY - start.y) / scaleY;
      let { x, y, width, height } = start.rect;
      if (!handle) {
        x = snap(x + dx, SNAP_X, moveEvent.altKey);
        y = snap(y + dy, SNAP_Y, moveEvent.altKey);
      } else {
        if (handle.includes('e')) width = Math.max(40, width + dx);
        if (handle.includes('s')) height = Math.max(30, height + dy);
        if (handle.includes('w')) { x += dx; width = Math.max(40, width - dx); }
        if (handle.includes('n')) { y += dy; height = Math.max(30, height - dy); }
        if (element.dataset.editable === 'image') {
          const aspect = start.rect.width / start.rect.height;
          if (handle.includes('e') || handle.includes('w')) {
            height = width / aspect;
            if (handle.includes('n')) y = start.rect.y + start.rect.height - height;
          } else {
            width = height * aspect;
          }
          if (handle.includes('w')) x = start.rect.x + start.rect.width - width;
        }
      }
      Object.assign(element.style, { position: 'absolute', left: `${x}px`, top: `${y}px`, width: `${width}px`, height: `${height}px` });
      refreshOverlay();
    }
    function end() {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', end);
      saveSoon(); syncPanel(); pushHistory();
    }
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', end, { once: true });
  }

  elements.forEach((element) => {
    element.addEventListener('click', (event) => {
      event.stopPropagation();
      if (element.dataset.editable === 'text' && event.detail > 1) enterTextEdit(element, event);
      else select(element);
    });
    element.addEventListener('pointerdown', (event) => {
      if (element.dataset.editable === 'text' && event.detail > 1) enterTextEdit(element, event);
      else beginTransform(event, element);
    });
    if (element.dataset.editable === 'text') {
      element.addEventListener('dblclick', (event) => enterTextEdit(element, event));
      element.addEventListener('input', () => { refreshOverlay(); saveSoon(); });
      element.addEventListener('blur', () => { editingText = false; element.removeAttribute('contenteditable'); saveSoon(); refreshOverlay(); pushHistory(); });
      element.addEventListener('keydown', (event) => { if (event.key === 'Escape') element.blur(); });
    }
  });
  selection.querySelectorAll('[data-handle]').forEach((handle) => handle.addEventListener('pointerdown', (event) => selected && beginTransform(event, selected, handle.dataset.handle)));
  panel.addEventListener('input', (event) => {
    if (!selected) return;
    const prop = event.target.dataset.prop;
    if (!prop) return;
    const value = event.target.value;
    selected.style[prop] = ['fontSize'].includes(prop) ? `${value}px` : value;
    refreshOverlay(); saveSoon();
  });
  panel.addEventListener('change', (event) => { if (event.target.dataset.prop) pushHistory(); });
  canvas.addEventListener('click', (event) => { if (event.target === canvas) select(null); });
  ui.querySelector('[data-action="preview"]').addEventListener('click', () => {
    ui.classList.toggle('is-previewing');
    const hidden = ui.classList.contains('is-previewing');
    selection.hidden = hidden || !selected;
    panel.hidden = hidden || !selected;
    ui.querySelector('[data-action="preview"]').textContent = hidden ? '显示框线' : '隐藏框线';
  });
  const imageFile = ui.querySelector('[data-role="image-file"]');
  const jsonFile = ui.querySelector('[data-role="json-file"]');
  ui.querySelector('[data-action="replace-image"]').addEventListener('click', () => imageFile.click());
  imageFile.addEventListener('change', () => {
    const file = imageFile.files?.[0];
    if (!file || !selected || selected.dataset.editable !== 'image') return;
    if (!file.type.startsWith('image/')) { setStatus('图片格式无效'); return; }
    if (file.size > 2.5 * 1024 * 1024) { setStatus('图片超过 2.5MB，请先压缩'); return; }
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      selected.src = reader.result;
      selected.dataset.sourceFileName = file.name;
      selected.addEventListener('load', () => { refreshOverlay(); saveSoon(); pushHistory(); }, { once: true });
    });
    reader.readAsDataURL(file);
  });
  ui.querySelector('[data-action="undo"]').addEventListener('click', undo);
  ui.querySelector('[data-action="redo"]').addEventListener('click', redo);
  ui.querySelector('[data-action="export"]').disabled = false;
  ui.querySelector('[data-action="import"]').disabled = false;
  ui.querySelector('[data-action="reset"]').disabled = false;
  function exportJSON() { return store.exportJSON(currentState()); }
  ui.querySelector('[data-action="export"]').addEventListener('click', () => {
    const blob = new Blob([exportJSON()], { type: 'application/json' });
    const href = URL.createObjectURL(blob);
    const link = Object.assign(document.createElement('a'), { href, download: `${slideId}-edits.json` });
    link.click(); setTimeout(() => URL.revokeObjectURL(href), 0);
  });
  ui.querySelector('[data-action="import"]').addEventListener('click', () => jsonFile.click());
  jsonFile.addEventListener('change', async () => {
    const file = jsonFile.files?.[0];
    if (!file) return;
    try {
      const state = store.importJSON(await file.text());
      applySnapshot(state); pushHistory(); setStatus('修改 JSON 已导入');
    } catch (error) { setStatus(`导入失败：${error.message}`); }
  });
  ui.querySelector('[data-action="reset"]').addEventListener('click', () => {
    if (!confirm('恢复当前页到 HTML 原始状态？')) return;
    const state = { schemaVersion: 1, documentId, slideId, updatedAt: new Date().toISOString(), elements: pristineElements };
    store.clear(); applySnapshot(state); pushHistory(); setStatus('已恢复当前页');
  });
  window.addEventListener('resize', () => { fitCanvas(); refreshOverlay(); });
  window.addEventListener('scroll', refreshOverlay, true);
  window.addEventListener('pagehide', saveNow);
  pushHistory();
  requestAnimationFrame(refreshOverlay);
  return { root: ui, select, getState: currentState, exportJSON, undo, redo, store };
}
