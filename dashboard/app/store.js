export const state = {
  settings: {},
  universe: [],
  symbols: {},
  active: 'BTCUSDT',
  interval: '4h',
  rightInterval: '4h',
  plans: {},
  events: [],
  llm: {},
  llmNotes: {},
  connected: false,
  loading: false,
  lastError: null,
  layers: { structure: true, patterns: true, zones: true, plan: true },
  paramsSymbol: null
};

const subs = new Set();
let scheduled = false;

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function patch(obj) {
  Object.assign(state, obj);
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    scheduled = false;
    const snap = state;
    subs.forEach(fn => { try { fn(snap); } catch (e) { console.error(e); } });
  });
}

export function current() {
  return state.symbols[state.active] || null;
}
