const SCHEMA_VERSION = 1;

function assertIdentity(state, documentId, slideId) {
  if (!state || typeof state !== 'object') throw new Error('Invalid editor state');
  if (state.schemaVersion !== SCHEMA_VERSION) throw new Error('Unsupported schemaVersion');
  if (state.documentId !== documentId) throw new Error('documentId does not match');
  if (state.slideId !== slideId) throw new Error('slideId does not match');
  if (!state.elements || typeof state.elements !== 'object' || Array.isArray(state.elements)) {
    throw new Error('elements must be an object');
  }
  return state;
}

export function createStateStore({ documentId, slideId, storage = globalThis.localStorage }) {
  if (!documentId || !slideId) throw new Error('documentId and slideId are required');
  const key = `ppt-editor:${documentId}:${slideId}:v1`;

  return {
    key,
    load() {
      const raw = storage.getItem(key);
      if (!raw) return null;
      try {
        return assertIdentity(JSON.parse(raw), documentId, slideId);
      } catch {
        return null;
      }
    },
    save(state) {
      const normalized = assertIdentity(state, documentId, slideId);
      storage.setItem(key, JSON.stringify(normalized));
      return normalized;
    },
    clear() {
      storage.removeItem(key);
    },
    exportJSON(state) {
      const normalized = {
        schemaVersion: SCHEMA_VERSION,
        documentId,
        slideId,
        updatedAt: state.updatedAt ?? new Date().toISOString(),
        elements: state.elements ?? {},
      };
      assertIdentity(normalized, documentId, slideId);
      return JSON.stringify(normalized, null, 2);
    },
    importJSON(json) {
      const state = assertIdentity(JSON.parse(json), documentId, slideId);
      this.save(state);
      return state;
    },
  };
}
