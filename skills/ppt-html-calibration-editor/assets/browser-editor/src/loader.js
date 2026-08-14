import { mountPptEditor } from './editor.js';
import { mountPptMultiEditor } from './multi-editor.js';

const params = new URLSearchParams(location.search);
const isEditMode = params.get('edit') === '1';
const isMultiEditMode = params.get('edit') === 'all';
const isCaptureMode = params.has('capture') && !isEditMode;
if (isMultiEditMode) {
  window.__PPT_MULTI_EDITOR__ = mountPptMultiEditor({
    documentId: document.body.dataset.documentId || document.title || 'ppt-document',
  });
} else if (!isCaptureMode && (isEditMode || document.body.dataset.editorAuto === 'true')) {
  const requested = params.get('capture');
  const slides = [...document.querySelectorAll('.slide, .slide-canvas')];
  const canvas = requested
    ? slides.find((slide) => slide.dataset.page === requested || slide.dataset.slideId === requested || slide.id === requested || slide.classList.contains(requested))
    : slides.find((slide) => getComputedStyle(slide).display !== 'none') ?? slides[0];

  if (canvas) {
    window.__PPT_EDITOR__ = mountPptEditor({
      canvas,
      documentId: document.body.dataset.documentId || document.title || 'ppt-document',
      slideId: canvas.dataset.page || canvas.dataset.slideId || canvas.id || requested || 'slide',
    });
  }
}
