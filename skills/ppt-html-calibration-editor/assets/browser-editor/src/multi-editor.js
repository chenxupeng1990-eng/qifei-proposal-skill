import { createStateStore } from './state.js';

export function mountPptMultiEditor({ documentId }) {
  document.documentElement.classList.add('ppt-editor-multi-active');
  const slides = [...document.querySelectorAll('.slide')];
  const root = document.createElement('div');
  root.className = 'ppt-multi-toolbar';
  root.innerHTML = `<strong>全稿编辑</strong><span>双击文字编辑 · 自动保存到本机浏览器</span><button type="button">退出编辑</button>`;
  root.querySelector('button').addEventListener('click', () => {
    const url = new URL(location.href);
    url.searchParams.delete('edit');
    location.href = url;
  });
  document.body.append(root);

  const mounted = [];
  for (const [index, slide] of slides.entries()) {
    slide.style.display = 'block';
    slide.classList.add('ppt-multi-slide');
    const shell = document.createElement('div');
    shell.className = 'ppt-multi-shell';
    slide.parentNode.insertBefore(shell, slide);
    shell.append(slide);
    const slideId = slide.dataset.page || slide.id || `slide-${index + 1}`;
    const store = createStateStore({ documentId, slideId });
    const elements = [...slide.querySelectorAll('[data-editable="text"][data-edit-id]')];
    const saved = store.load();
    for (const element of elements) {
      const state = saved?.elements?.[element.dataset.editId];
      if (state?.text != null) element.textContent = state.text;
      element.title = '单击编辑文字';
      element.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (element.contentEditable === 'true') return;
        element.contentEditable = 'true';
        element.focus({ preventScroll: true });
        element.classList.add('ppt-multi-editing');
      });
      element.addEventListener('blur', () => {
        element.contentEditable = 'false';
        element.classList.remove('ppt-multi-editing');
        const current = store.load() || { schemaVersion: 1, documentId, slideId, elements: {} };
        current.updatedAt = new Date().toISOString();
        current.elements[element.dataset.editId] = { ...(current.elements[element.dataset.editId] || {}), type: 'text', text: element.innerText };
        store.save(current);
      });
      element.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') element.blur();
      });
    }
    mounted.push({ slideId, elements: elements.length });
  }
  function fitSlides() {
    for (const shell of document.querySelectorAll('.ppt-multi-shell')) {
      const slide = shell.querySelector('.ppt-multi-slide');
      const scale = shell.clientWidth / 1920;
      slide.style.transformOrigin = 'top left';
      slide.style.transform = `scale(${scale})`;
      shell.style.height = `${1080 * scale}px`;
    }
  }
  fitSlides();
  addEventListener('resize', fitSlides);
  return { documentId, slides: mounted };
}
