import { get, post } from './api.js';
import { state, patch } from './store.js';
import { esc, fmt, marketCN } from './format.js';

let uni = [];
let selected = new Set();
let handlers = {};
let paramsProfile = null;

export function bindSettings(h) { handlers = h || {}; }

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = true;
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = false;
}

function bindClosers() {
  document.querySelectorAll('[data-close]').forEach(x => {
    x.addEventListener('click', () => {
      x.closest('.modal').hidden = true;
    });
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('.modal').forEach(m => m.hidden = true);
  });
}

export async function bootModals() {
  bindClosers();
  uni = (await get('/api/universe')).universe || [];
  document.getElementById('btn-settings').addEventListener('click', openSettings);
  document.getElementById('btn-universe').addEventListener('click', openUniverse);
  document.getElementById('universe-search').addEventListener('input', e => {
    renderUniverse(e.target.value);
  });
  document.getElementById('btn-apply-universe').addEventListener('click', applyUniverse);
  document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
  document.getElementById('settings-body').addEventListener('click', onSettingsClick);
  document.getElementById('settings-body').addEventListener('change', onSettingsChange);
  document.getElementById('universe-list').addEventListener('change', onUniverseCheck);
}

export function openUniverse() {
  selected = new Set(state.settings.active_symbols || []);
  renderUniverse('');
  document.getElementById('universe-search').value = '';
  updateUniCount();
  openModal('universe-modal');
}

function renderUniverse(q) {
  const term = (q || '').trim().toLowerCase();
  const list = uni.filter(x => !term ||
    x.symbol.toLowerCase().includes(term) ||
    (x.name || '').toLowerCase().includes(term) ||
    (x.market_label || '').includes(term));
  const groups = {};
  list.forEach(x => {
    (groups[x.market_label || marketCN(x.market)] ||= []).push(x);
  });
  const max = Number(state.settings.max_symbols || 6);
  document.getElementById('universe-list').innerHTML = Object.entries(groups).map(([g, items]) => `
    <div class="ugroup">${esc(g)}</div>
    ${items.map(x => `
      <label class="uitem ${selected.has(x.symbol) ? 'on' : ''}" data-sym="${x.symbol}">
        <input type="checkbox" data-sym="${x.symbol}" ${selected.has(x.symbol) ? 'checked' : ''}>
        <span class="code">${esc(x.symbol)}</span>
        <span class="nm">${esc(x.name)}</span>
        ${x.default ? '<span class="tag">默认</span>' : ''}
        <span class="tag">${esc(x.provider)}</span>
      </label>`).join('')}
  `).join('') || '<div class="empty">无匹配标的</div>';
  document.querySelectorAll('.uitem').forEach(el => {
    el.classList.toggle('on', selected.has(el.dataset.sym));
  });
  document.getElementById('universe-count').textContent =
    `已选 ${selected.size} / ${max}`;
}

function onUniverseCheck(e) {
  const cb = e.target.closest('input[type=checkbox]');
  if (!cb) return;
  const sym = cb.dataset.sym;
  const max = Number(state.settings.max_symbols || 6);
  if (cb.checked) {
    if (selected.size >= max) { cb.checked = false; return; }
    selected.add(sym);
  } else {
    selected.delete(sym);
  }
  const item = cb.closest('.uitem');
  if (item) item.classList.toggle('on', cb.checked);
  updateUniCount();
}

function updateUniCount() {
  const max = Number(state.settings.max_symbols || 6);
  document.getElementById('universe-count').textContent = `已选 ${selected.size} / ${max}`;
}

async function applyUniverse() {
  if (!selected.size) return;
  const body = { active_symbols: [...selected] };
  const s = await post('/api/settings', body);
  patch({ settings: s });
  closeModal('universe-modal');
  handlers.onSettingsSaved && handlers.onSettingsSaved(s);
}

export async function openSettings() {
  const [settings, params, llm] = await Promise.all([
    get('/api/settings'), get('/api/symbol-params'), get('/api/llm/status')
  ]);
  patch({ settings, llm });
  const syms = (uni.length ? uni : (await get('/api/universe')).universe || []);
  uni = syms;
  paramsProfile = null;
  const pool = (settings.active_symbols || []).map(s => {
    const u = uni.find(x => x.symbol === s) || { symbol: s, name: s, market: 'crypto' };
    return `<span class="chip gold">${esc(u.symbol)} · ${esc(u.name)}</span>`;
  }).join('');
  const intervalChecks = ['15m', '1h', '4h', '1d'].map(iv =>
    `<label><input type="checkbox" data-setting="intervals" value="${iv}" ${(settings.intervals || []).includes(iv) ? 'checked' : ''}>${iv}</label>`
  ).join('');
  const singleOpts = ['15m', '1h', '4h', '1d'].map(iv =>
    `<option value="${iv}" ${settings.single_interval === iv ? 'selected' : ''}>${iv}</option>`
  ).join('');
  const paramSym = paramsProfile ? paramsProfile.symbol : (settings.active_symbols || [])[0];
  if (!paramsProfile && paramSym) {
    try { paramsProfile = (await get('/api/symbol-params', { symbol: paramSym })).profile; }
    catch (e) { paramsProfile = null; }
  }
  const bounds = params.bounds || {};
  const eff = (paramsProfile && paramsProfile.effective) ||
    (params.profiles && params.profiles[paramSym] && params.profiles[paramSym].effective) || {};
  const rows = Object.keys(bounds).map(k => {
    const b = bounds[k];
    const val = eff[k] ?? '';
    return `<tr><td>${esc(k)}</td>
      <td>${b[0]} — ${b[1]}</td>
      <td><input type="number" step="0.01" data-pkey="${k}" value="${val}"></td></tr>`;
  }).join('');

  document.getElementById('settings-body').innerHTML = `
    <div class="section">
      <h3>标的池</h3>
      <div class="row2">
        <div class="field"><label>最大同时分析标的</label>
          <input type="number" id="set-max" min="1" max="24" value="${settings.max_symbols || 6}">
        </div>
        <div class="field"><label>当前标的</label>
          <div class="chips">${pool}</div>
        </div>
      </div>
      <div class="plan-actions"><button class="ghost-btn" data-act="open-universe">管理标的池</button></div>
      <div class="muted" style="font-size:10px;margin-top:6px">默认分析 BTC / ETH。其他标的接入后按需拉取，不默认占用请求。</div>
    </div>

    <div class="section">
      <h3>分析周期</h3>
      <div class="seg" id="set-mode">
        <button data-mode="multi" class="${settings.mode !== 'single' ? 'on' : ''}">多周期联合</button>
        <button data-mode="single" class="${settings.mode === 'single' ? 'on' : ''}">单周期</button>
      </div>
      <div class="iv-picks" style="margin-top:9px">${intervalChecks}</div>
      <div class="field" style="margin-top:9px;max-width:160px"><label>单周期模式使用</label>
        <select id="set-single">${singleOpts}</select></div>
    </div>

    <div class="section">
      <h3>自动化引擎</h3>
      <div class="toggle"><span>自动分析（按 TTL 刷新）</span>
        <input type="checkbox" data-setting="auto_analyze" ${settings.auto_analyze ? 'checked' : ''}></div>
      <div class="toggle"><span>自动触发（价格到达价位，重新分析并确认）</span>
        <input type="checkbox" data-setting="auto_trigger" ${settings.auto_trigger ? 'checked' : ''}></div>
      <div class="toggle"><span>QQ 推送（仅状态迁移）</span>
        <input type="checkbox" data-setting="auto_push" ${settings.auto_push ? 'checked' : ''}></div>
      <div class="row2">
        <div class="field"><label>分析有效期（分钟）</label>
          <input type="number" id="set-ttl" min="2" max="240" value="${settings.analysis_ttl_min || 30}"></div>
        <div class="field"><label>触发轮询（秒）</label>
          <input type="number" id="set-trigger" min="5" max="300" value="${settings.trigger_seconds || 20}"></div>
      </div>
    </div>

    <div class="section">
      <h3>LLM · 解读与参数迭代</h3>
      <div class="toggle"><span>图表解读（只写评论，不定价）</span>
        <input type="checkbox" data-setting="llm_annotate" ${settings.llm_annotate ? 'checked' : ''}></div>
      <div class="toggle"><span>自动参数迭代（需 ≥20 条计划样本 + 硬边界）</span>
        <input type="checkbox" data-setting="llm_autotune" ${settings.llm_autotune ? 'checked' : ''}></div>
      <div class="muted" style="font-size:10px">${llm.enabled ? '已连接 ' + esc(llm.model || '') : esc(llm.reason || '未配置 NK_LLM_KEY')}</div>
    </div>

    <div class="section">
      <h3>标的参数库</h3>
      <div class="row2">
        <div class="field"><label>标的</label>
          <select id="set-param-symbol">${(settings.active_symbols || []).map(s =>
            `<option ${s === paramSym ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select></div>
        <div class="field"><label>当前配置来源</label>
          <div style="font-size:11px;padding-top:7px" class="muted">
            <span class="badge ${paramsProfile && paramsProfile.source === 'llm' ? 'llm' : 'manual'}">${esc((paramsProfile && paramsProfile.source) || 'default')}</span>
            v${(paramsProfile && paramsProfile.version) || 0}</div></div>
      </div>
      <table class="param-table"><thead><tr><th>参数</th><th>范围</th><th>值</th></tr></thead>
        <tbody>${rows}</tbody></table>
      <div class="plan-actions">
        <button class="ghost-btn" data-act="save-params">保存标的参数</button>
        <button class="ghost-btn" data-act="revert-params">回滚</button>
        <button class="ghost-btn" data-act="llm-optimize">LLM 建议</button>
      </div>
      <div class="muted" style="font-size:10px;margin-top:5px">每个标的单独一套；参数改动下一轮分析生效。LLM 建议受硬边界与样本量约束，不会直接写入。</div>
    </div>
  `;
  openModal('settings-modal');
}

function onSettingsChange(e) {
  if (e.target.closest('#set-mode')) return;
  if (e.target.dataset.setting) return;
  if (e.target.id === 'set-param-symbol') {
    loadParams(e.target.value);
  }
}

async function loadParams(symbol) {
  const r = await get('/api/symbol-params', { symbol });
  paramsProfile = r.profile;
  const eff = paramsProfile.effective || {};
  document.querySelectorAll('[data-pkey]').forEach(inp => {
    inp.value = eff[inp.dataset.pkey] ?? '';
  });
  const badge = document.querySelector('#settings-body .badge');
  if (badge) {
    badge.textContent = paramsProfile.source || 'default';
    badge.className = 'badge ' + (paramsProfile.source === 'llm' ? 'llm' : 'manual');
  }
}

async function onSettingsClick(e) {
  const btn = e.target.closest('button');
  if (!btn) return;
  if (btn.dataset.act === 'open-universe') return openUniverse();
  if (btn.dataset.mode) {
    document.querySelectorAll('#set-mode button').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    return;
  }
  if (btn.dataset.act === 'save-params') {
    const sym = document.getElementById('set-param-symbol').value;
    const patchObj = {};
    document.querySelectorAll('[data-pkey]').forEach(inp => {
      const v = Number(inp.value);
      if (!Number.isNaN(v)) patchObj[inp.dataset.pkey] = v;
    });
    await post('/api/symbol-params', { symbol: sym, patch: patchObj, source: 'manual' });
    await loadParams(sym);
    handlers.onSettingsSaved && handlers.onSettingsSaved(state.settings);
    return;
  }
  if (btn.dataset.act === 'revert-params') {
    const sym = document.getElementById('set-param-symbol').value;
    await post('/api/symbol-params', { symbol: sym, revert: true });
    await loadParams(sym);
    return;
  }
  if (btn.dataset.act === 'llm-optimize') {
    const sym = document.getElementById('set-param-symbol').value;
    btn.textContent = '分析中…';
    try {
      const r = await post('/api/llm/optimize', { symbol: sym });
      const txt = r.error ? '失败：' + r.error :
        (r.patch && Object.keys(r.patch).length
          ? '建议：' + JSON.stringify(r.patch) + (r.validation && r.validation.length ? ' · 校验失败' : '')
          : '样本不足或无建议');
      alert(txt);
    } finally {
      btn.textContent = 'LLM 建议';
    }
  }
}

async function saveSettings() {
  const mode = document.querySelector('#set-mode button.on')?.dataset.mode || 'multi';
  const intervals = [...document.querySelectorAll('[data-setting="intervals"]:checked')]
    .map(x => x.value);
  const body = {
    mode,
    intervals: intervals.length ? intervals : ['4h', '15m'],
    single_interval: document.getElementById('set-single').value,
    max_symbols: Number(document.getElementById('set-max').value) || 6,
    analysis_ttl_min: Number(document.getElementById('set-ttl').value) || 30,
    trigger_seconds: Number(document.getElementById('set-trigger').value) || 20,
    auto_analyze: document.querySelector('[data-setting="auto_analyze"]').checked,
    auto_trigger: document.querySelector('[data-setting="auto_trigger"]').checked,
    auto_push: document.querySelector('[data-setting="auto_push"]').checked,
    llm_annotate: document.querySelector('[data-setting="llm_annotate"]').checked,
    llm_autotune: document.querySelector('[data-setting="llm_autotune"]').checked
  };
  const s = await post('/api/settings', body);
  patch({ settings: s });
  closeModal('settings-modal');
  handlers.onSettingsSaved && handlers.onSettingsSaved(s);
}
