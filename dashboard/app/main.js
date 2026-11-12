import { get, post, connect } from './api.js';
import { state, patch, subscribe } from './store.js';
import { initChart, setPayload, refit, updateLayers } from './chart.js';
import { renderPanels } from './panels.js';
import { bootModals, openUniverse, openSettings, bindSettings } from './settings.js';
import { fmtPrice, pct, colorOf, marketCN, esc, dirCN, timeHM } from './format.js';

const $ = id => document.getElementById(id);
let streamClose = null;
let refreshTimer = null;

function parseHash() {
  const m = location.hash.match(/^#\/([A-Za-z0-9]{2,16})(?:\/(15m|30m|1h|4h|1d))?/);
  if (m) {
    state.active = m[1].toUpperCase();
    if (m[2]) state.interval = m[2];
  }
}

function setHash() {
  const h = `#/${state.active}/${state.interval}`;
  if (location.hash !== h) history.replaceState(null, '', h);
}

async function boot() {
  initChart();
  await bootModals();
  parseHash();
  bindUI();
  subscribe(render);
  try {
    const [uni, settings, llm] = await Promise.all([
      get('/api/universe'), get('/api/settings'), get('/api/llm/status')
    ]);
    patch({ universe: uni.universe || [], settings, llm });
    if (!state.interval) state.interval = (settings.intervals || ['4h'])[0];
    await loadOverview();
    if (!state.symbols[state.active]) {
      const first = (settings.active_symbols || [])[0];
      if (first) { state.active = first; await loadSymbol(first); }
    }
    tickClock();
    setInterval(tickClock, 1000);
    startStream();
    refreshTimer = setInterval(() => refreshActive(), 25000);
    render(state);
    const qp = new URLSearchParams(location.search);
    if (qp.get('llm') === '1' || qp.get('setup') === '1') {
      await openSettings();
      setTimeout(() => {
        const el = document.getElementById('llm-key-input');
        if (el) { el.focus(); el.scrollIntoView({ block: 'center' }); }
      }, 200);
    }
  } catch (e) {
    patch({ lastError: String(e) });
    $('chart-empty').hidden = false;
    $('chart-empty').textContent = '初始化失败：' + e.message;
  }
}

async function loadOverview() {
  const syms = (state.settings.active_symbols || []).join(',');
  const ivs = (state.settings.mode === 'single')
    ? [state.settings.single_interval || '4h']
    : (state.settings.intervals || ['4h', '15m']);
  const r = await get('/api/overview', { symbols: syms, intervals: ivs.join(',') });
  const merged = Object.assign({}, state.symbols, r.symbols || {});
  patch({ symbols: merged, settings: r.settings || state.settings });
}

async function loadSymbol(sym, force = false) {
  if (!sym) return;
  try {
    const p = await get('/api/symbol', { symbol: sym, force: force ? 1 : 0 });
    const symbols = Object.assign({}, state.symbols, { [sym]: p });
    patch({ symbols });
  } catch (e) {
    console.error('loadSymbol', e);
  }
}

function refreshActive() {
  if (document.hidden) return;
  loadSymbol(state.active);
}

function startStream() {
  if (streamClose) streamClose();
  let pending = null;
  streamClose = connect((ev, data) => {
    if (ev === 'symbol') {
      if (data.symbol !== state.active) return;
      const cur = state.symbols[state.active];
      if (cur) {
        const next = Object.assign({}, cur, {
          price: data.price ?? cur.price,
          plan: data.plan ?? cur.plan,
          combined: data.combined ?? cur.combined
        });
        patch({ symbols: Object.assign({}, state.symbols, { [state.active]: next }) });
      }
      clearTimeout(pending);
      pending = setTimeout(() => loadSymbol(state.active), 1200);
    } else if (ev === 'plan') {
      if (!data.symbol || data.symbol === state.active) {
        clearTimeout(pending);
        pending = setTimeout(() => loadSymbol(state.active), 900);
      }
    } else if (ev === 'settings') {
      patch({ settings: data });
    } else if (ev === 'llm') {
      patch({ llm: data });
    }
  }, ok => patch({ connected: ok }));
}

function bindUI() {
  $('sym-rail').addEventListener('click', e => {
    const b = e.target.closest('button.tab');
    if (!b) return;
    switchSymbol(b.dataset.sym);
  });
  $('tf-rail').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    setIntervalTF(b.dataset.tf);
  });
  $('chart-flags').addEventListener('change', e => {
    const cb = e.target.closest('input[data-layer]');
    if (!cb) return;
    updateLayers({ [cb.dataset.layer]: cb.checked });
  });
  $('btn-refit').addEventListener('click', refit);
  $('btn-reanalyze').addEventListener('click', () => analyzeNow());
  $('side-scroll').addEventListener('click', onPanelClick);
  window.addEventListener('hashchange', () => {
    parseHash();
    if (!state.symbols[state.active]) loadSymbol(state.active);
    render(state);
  });
  bindSettings({
    onSettingsSaved: async () => {
      await loadOverview();
      const active = state.settings.active_symbols || [];
      if (!active.includes(state.active) && active.length) {
        state.active = active[0];
      }
      await loadSymbol(state.active, true);
      render(state);
    }
  });
  window.addEventListener('keydown', e => {
    if (e.target.matches('input,textarea,select')) return;
    if (e.key === '1') setIntervalTF('15m');
    if (e.key === '2') setIntervalTF('4h');
    if (e.key === '3') setIntervalTF('1d');
    if (e.key === '/') { e.preventDefault(); openUniverse(); }
    if (e.key.toLowerCase() === 'r') analyzeNow();
  });
}

async function switchSymbol(sym) {
  if (!sym) return;
  state.active = sym;
  setHash();
  if (!state.symbols[sym]) await loadSymbol(sym, true);
  render(state);
}

function setIntervalTF(tf) {
  const p = state.symbols[state.active];
  const order = (p && p.interval_order) || (state.settings.intervals || []);
  if (order.length && !order.includes(tf)) return;
  state.interval = tf;
  setHash();
  render(state);
}

let toastTimer = null;
function toast(msg, kind = 'ok') {
  const el = $('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'toast ' + kind;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
}

async function analyzeNow() {
  const btn = $('btn-reanalyze');
  if (btn) { btn.disabled = true; btn.textContent = '分析中…'; }
  try {
    const p = await post('/api/analyze', { symbol: state.active });
    if (p && p.error) {
      toast('分析失败：' + p.error, 'err');
      return;
    }
    patch({ symbols: Object.assign({}, state.symbols, { [state.active]: p }) });
    const c = p.combined || {};
    toast(`分析完成 · ${c.direction_cn || '中性'} · 置信 ${c.confidence ?? '—'} · ${new Date().toLocaleTimeString('zh-CN', {hour12:false})}`);
  } catch (e) {
    console.error(e);
    toast('分析请求失败：' + e.message, 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '重新分析'; }
  }
}

async function onPanelClick(e) {
  const btn = e.target.closest('button');
  if (!btn) return;
  const act = btn.dataset.act;
  if (act === 'analyze') return analyzeNow();
  if (act === 'void-plan') {
    if (!confirm('作废这条计划？')) return;
    await post('/api/plan/action', { plan_id: Number(btn.dataset.id), action: 'void' });
    await loadSymbol(state.active, true);
    return;
  }
  if (act === 'right-interval') {
    window.__nkaRightInterval = btn.dataset.tf;
    renderPanels($('side-scroll'), state);
    return;
  }
  if (act === 'llm-annotate') {
    btn.disabled = true; btn.textContent = '生成中…';
    try {
      const r = await post('/api/llm/annotate', { symbol: state.active });
      const notes = Object.assign({}, state.llmNotes, { [state.active]: r });
      patch({ llmNotes: notes });
    } catch (err) {
      patch({ llmNotes: Object.assign({}, state.llmNotes, { [state.active]: { error: String(err) } }) });
    } finally {
      btn.disabled = false; btn.textContent = '生成解读';
    }
    return;
  }
  if (act === 'open-settings') return openSettings();
  if (act === 'llm-key') {
    await openSettings();
    setTimeout(() => {
      const el = document.getElementById('llm-key-input');
      if (el) { el.focus(); el.scrollIntoView({ block: 'center' }); }
    }, 120);
    return;
  }
}

function tickClock() {
  const d = new Date();
  $('clock').textContent = d.toLocaleTimeString('zh-CN', { hour12: false });
}

function render(st) {
  const p = st.symbols[st.active];
  renderRail(st);
  renderTop(st, p);
  if (p) {
    const order = p.interval_order || Object.keys(p.intervals || {});
    if (order.length && !order.includes(st.interval)) state.interval = order[0];
    setPayload(p, state.interval);
    renderPanels($('side-scroll'), st);
    $('chart-empty').hidden = !!(p.intervals && p.intervals[st.interval] &&
      p.intervals[st.interval].candles && p.intervals[st.interval].candles.length);
  }
  renderStatus(st, p);
}

function renderRail(st) {
  const active = (st.settings.active_symbols || Object.keys(st.symbols));
  $('sym-rail').innerHTML = active.map(s => {
    const u = (st.universe || []).find(x => x.symbol === s) || { symbol: s, name: s };
    return `<button class="tab ${s === st.active ? 'on' : ''}" data-sym="${esc(String(s))}"
      title="${esc(u.name)}">${esc(s.replace('USDT', '/USDT'))}</button>`;
  }).join('');
}

function renderTop(st, p) {
  const u = (st.universe || []).find(x => x.symbol === st.active) || {};
  $('sym-title').textContent = (p && p.name) || u.name || st.active;
  $('market-tag').textContent = marketCN((p && p.market) || u.market);
  if (p) {
    $('last-price').textContent = fmtPrice(p.price);
    $('last-price').style.color = colorOf(p.change24h);
    $('last-chg').textContent = pct(p.change24h);
    $('last-chg').style.color = colorOf(p.change24h);
    $('freshness').textContent = `${p.source || '—'} · 数据 ${timeHM(p.data_ts)} · 分析 ${timeHM(p.as_of)}`;
  }
  renderTF(st, p);
  const live = $('live');
  live.classList.toggle('ok', !!st.connected);
  live.querySelector('span').textContent = st.connected ? '实时' : '轮询';
}

function renderTF(st, p) {
  const order = (p && p.interval_order) || (st.settings && st.settings.intervals) || ['15m', '4h'];
  const rail = $('tf-rail');
  if (!rail) return;
  if (!order.includes(st.interval) && order.length) state.interval = order[0];
  rail.innerHTML = order.map(tf =>
    `<button data-tf="${esc(String(tf))}" class="${tf === st.interval ? 'on' : ''}">${esc(String(tf).toUpperCase())}</button>`
  ).join('');
}

function renderStatus(st, p) {
  const s = st.settings || {};
  $('st-engine').textContent = `引擎 ${s.auto_analyze ? '自动分析' : '手动'} · ${s.auto_trigger ? '自动触发' : '触发关闭'}`;
  $('st-symbols').textContent = `标的 ${(s.active_symbols || []).length}/${s.max_symbols || 6} · ${s.mode === 'single' ? '单周期' : '多周期'}`;
  const plan = p && p.plan;
  $('st-plan').textContent = plan
    ? `计划 #${plan.id} ${plan.side_cn || dirCN(plan.side)} ${plan.status_cn || plan.status}`
    : '计划 —';
  $('st-llm').textContent = st.llm && st.llm.enabled
    ? `LLM ${st.llm.model || 'on'}` : 'LLM off';
}

boot();
