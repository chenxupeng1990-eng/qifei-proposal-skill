import { mountPptEditor } from './editor.js';

const params = new URLSearchParams(location.search);
const isEditMode = params.get('edit') === '1';
const isCaptureMode = params.has('capture') && !isEditMode;
if (!isCaptureMode && (isEditMode || document.body.dataset.editorAuto === 'true')) {
  const requested = params.get('capture');
  const slides = [...document.querySelectorAll('.slide')];
  const canvas = requested
    ? slides.find((slide) => slide.dataset.page === requested || slide.id === requested || slide.classList.contains(requested))
    : slides.find((slide) => getComputedStyle(slide).display !== 'none') ?? slides[0];

  if (canvas) {
    window.__PPT_EDITOR__ = mountPptEditor({
      canvas,
      documentId: document.body.dataset.documentId || document.title || 'ppt-document',
      slideId: canvas.dataset.page || canvas.id || requested || 'slide',
    });
  }
}
