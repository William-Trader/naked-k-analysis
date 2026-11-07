import {
  fmt, fmtPrice, pct, colorOf, dirCN, statusCN, agreeCN, esc,
  timeHM, timeFull, timeAgo, marketCN
} from './format.js';

const $ = id => document.getElementById(id);

function card(title, sub, body, cls = '') {
  return `<section class="card ${cls}">
    <div class="card-h"><b>${title}</b><span>${sub || ''}</span></div>
    <div class="card-b">${body}</div>
  </section>`;
}

function verdictCard(p) {
  const c = p.combined || {};
  const dir = c.direction || 'neutral';
  const conf = c.confidence ?? 0;
  const rows = (c.intervals || []).map(x => {
    const col = x.direction === 'long' ? 'var(--up)' : x.direction === 'short' ? 'var(--down)' : 'var(--muted)';
    return `<div class="list-row"><span>${esc(x.interval)}</span>
      <span style="color:${col}">${dirCN(x.direction)} · ${x.confidence ?? '—'}</span>
      <span class="muted">结构 ${esc(x.structure || '—')}</span></div>`;
  }).join('');
  return card('综合研判', `${c.grade ? 'GRADE ' + c.grade : ''}`, `
    <div class="verdict">
      <div>
        <div class="v-dir ${dir}">${dirCN(dir)}</div>
        <div class="chips">
          <span class="chip ${dir === 'long' ? 'long' : dir === 'short' ? 'short' : ''}">${agreeCN(c.agreement)}</span>
          <span class="chip">${(p.mtf && p.mtf.label) || 'MTF —'}</span>
        </div>
      </div>
      <div class="v-meta">置信度<br><b style="font-size:18px;color:var(--gold)">${conf}</b> / 68<br>
        <span>${esc(p.name || p.symbol)}</span></div>
    </div>
    <div class="conf"><i style="width:${Math.max(0, Math.min(100, conf))}%"></i></div>
    <div class="v-reasons">${(c.reasons || []).slice(0, 3).map(esc).join('<br>') || '等待更多结构信息'}</div>
    ${rows ? `<div style="margin-top:8px">${rows}</div>` : ''}
  `);
}

function stepper(status) {
  const steps = ['armed', 'triggered', 'confirmed', 'managing'];
  const idx = Math.max(0, steps.indexOf(status));
  return `<div class="stepper">${steps.map((s, i) =>
    `<div class="st ${i < idx ? 'done' : ''} ${i === idx ? 'now' : ''}">${statusCN(s)}</div>`
  ).join('')}</div>`;
}

function planCard(p) {
  const plan = p.plan;
  if (!plan) {
    return card('交易计划', 'PLAN', `
      <div class="empty">当前无有效计划。<br>引擎在结构成立时自动建立；也可立即分析。</div>
      <div class="plan-actions"><button class="ghost-btn" data-act="analyze">立即分析</button></div>
    `);
  }
  const sideCls = plan.side === 'long' ? 'long' : 'short';
  const ttl = plan.ttl_at ? timeFull(plan.ttl_at) : '—';
  const ev = (plan.snapshot && plan.snapshot.reasons) || [];
  return card('交易计划', `#${plan.id || '—'} · ${esc(plan.interval || '')}`, `
    ${stepper(plan.status)}
    <div class="plan-side">
      <span class="side-badge ${sideCls}">${plan.side_cn || dirCN(plan.side)}</span>
      <span class="plan-status">${statusCN(plan.status)}</span>
    </div>
    <div class="plan-levels">
      <div class="lvl entry"><span>触发</span><b>${fmtPrice(plan.trigger)}</b></div>
      <div class="lvl stop"><span>止损</span><b>${fmtPrice(plan.stop)}</b></div>
      <div class="lvl tp"><span>目标1</span><b>${fmtPrice(plan.target1)}</b></div>
    </div>
    <div class="plan-foot">
      <span>R:R <b style="color:var(--gold)">${plan.rr ?? '—'}</b></span>
      <span>置信 ${plan.confidence ?? '—'} · ${esc(plan.grade || '')}</span>
      <span>风险 ${plan.risk_pct ?? '—'}%</span>
    </div>
    <div class="plan-foot"><span>目标2 ${fmtPrice(plan.target2)}</span><span>失效 ${ttl}</span></div>
    ${plan.invalidation ? `<div class="plan-inval">失效条件：${esc(plan.invalidation)}</div>` : ''}
    ${ev.length ? `<div class="v-reasons" style="margin-top:6px">${ev.slice(0, 2).map(esc).join('<br>')}</div>` : ''}
    <div class="plan-actions">
      <button class="ghost-btn" data-act="void-plan" data-id="${plan.id}">作废计划</button>
      <button class="ghost-btn" data-act="analyze">重新分析</button>
    </div>
  `);
}

function intervalCard(p) {
  const order = p.interval_order || Object.keys(p.intervals || {});
  const tf = order.includes(window.__nkaRightInterval) ? window.__nkaRightInterval : order[0];
  const iv = (p.intervals || {})[tf];
  if (!iv) return card('周期分析', '', '<div class="empty">暂无周期数据</div>');
  const st = iv.stance || {};
  const f = iv.features || {};
  const struct = iv.structure || {};
  const pats = (iv.patterns || []).slice(0, 4);
  const tabs = order.map(x => `<button data-act="right-interval" data-tf="${x}" class="${x === tf ? 'on' : ''}">${x}</button>`).join('');
  const patRows = pats.length ? pats.map(x => {
    const col = x.direction === 'bullish' ? 'var(--up)' : x.direction === 'bearish' ? 'var(--down)' : 'var(--muted)';
    const q = Math.max(0, Math.min(100, x.quality || 0));
    return `<div class="pat-row"><span style="color:${col}">${esc(x.label || x.type)}</span>
      <span class="ql"><i><b style="width:${q}%"></b></i><span class="mono">${q}</span></span></div>`;
  }).join('') : '<div class="empty">无标准形态，等待结构</div>';
  return card('周期分析', tf.toUpperCase(), `
    <div class="itab">${tabs}</div>
    <div class="kv">
      <div><span>方向</span><b style="color:${st.direction === 'long' ? 'var(--up)' : st.direction === 'short' ? 'var(--down)' : 'var(--muted)'}">${dirCN(st.direction)}</b></div>
      <div><span>结构</span><b>${esc(struct.state || '—')}</b></div>
      <div><span>ADX</span><b>${fmt(f.adx, 1)}</b></div>
      <div><span>RSI</span><b>${fmt(f.rsi, 1)}</b></div>
      <div><span>ATR%</span><b>${fmt(f.atr_pct, 2)}</b></div>
      <div><span>VOL Z</span><b>${fmt(f.vol_z, 2)}</b></div>
      <div><span>POS20</span><b>${Math.round((f.pos20 || 0) * 100)}%</b></div>
      <div><span>重叠</span><b>${fmt(f.overlap, 2)}</b></div>
    </div>
    <div style="margin-top:8px">${patRows}</div>
    ${struct.bos ? `<div class="muted" style="font-size:10px;margin-top:6px">BOS ${esc(struct.bos.kind)} @ ${fmtPrice(struct.bos.level)}${struct.choch ? ' · CHoCH' : ''}</div>` : ''}
    ${(st.reasons || []).length ? `<div class="v-reasons" style="margin-top:6px">${st.reasons.slice(0, 3).map(esc).join('<br>')}</div>` : ''}
  `);
}

function levelsCard(p, tf) {
  const iv = (p.intervals || {})[tf] || {};
  const ann = iv.annotations || {};
  const lv = ann.levels || {};
  const rows = (arr, cls) => (arr || []).slice(0, 4).map(x => `
    <div class="list-row">
      <span class="lv" style="color:${cls}">${fmtPrice(x.price)}</span>
      <span class="muted">${x.touches || 0} 次</span>
      <span class="muted">${x.distance_pct > 0 ? '+' : ''}${fmt(x.distance_pct, 2)}%</span>
      <span class="strength">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= (x.strength || 0) ? 'on' : ''}"></i>`).join('')}</span>
    </div>`).join('');
  return card('关键价位', tf.toUpperCase(), `
    <div class="muted" style="font-size:9.5px;letter-spacing:.1em;margin-bottom:3px">阻力 RESISTANCE</div>
    ${rows(lv.resistances, 'var(--resistance)') || '<div class="empty">—</div>'}
    <div class="muted" style="font-size:9.5px;letter-spacing:.1em;margin:8px 0 3px">支撑 SUPPORT</div>
    ${rows(lv.supports, 'var(--support)') || '<div class="empty">—</div>'}
  `);
}

function llmCard(p, st) {
  const status = st.llm || {};
  const note = st.llmNotes[p.symbol];
  let body = '';
  if (!status.enabled) {
    body = `<div class="empty">LLM 未启用。<br><span class="mono">${esc(status.reason || '')}</span></div>`;
  } else if (!note) {
    body = `<div class="empty">让模型基于当前结构写一段解读（不参与定价）。</div>`;
  } else if (note.error) {
    body = `<div class="empty" style="color:var(--amber)">解读失败：${esc(note.error)}</div>`;
  } else {
    body = `<div class="llm-box">
      <div class="sum">${esc(note.summary || '')}</div>
      <div>${esc(note.scenario || '')}</div>
      ${note.invalidation ? `<div class="muted" style="margin-top:4px">失效：${esc(note.invalidation)}</div>` : ''}
      ${(note.warnings || []).map(w => `<div class="warn">⚠ ${esc(w)}</div>`).join('')}
    </div>`;
  }
  return card('AI 解读', status.enabled ? esc(status.model || '') : 'OFF', `
    ${body}
    <div class="llm-actions">
      <button class="ghost-btn" data-act="llm-annotate" ${status.enabled ? '' : 'disabled'}>生成解读</button>
      <button class="ghost-btn" data-act="open-settings">参数库</button>
    </div>
  `);
}

function eventsCard(p) {
  const events = ((p.history && p.history.events) || []).slice(0, 8);
  const rows = events.map(e => {
    const ev = e.event || {};
    const cls = (e.type || '').replace(/[^a-z0-9]/gi, '');
    return `<div class="event ${cls}">
      <span class="t">${timeHM(e.ts)}</span>
      <span class="ty">${esc(e.type)}</span>
      <span class="muted">${esc(ev.reason || '')}</span>
      <span class="px">${fmtPrice(e.price)}</span>
    </div>`;
  }).join('');
  return card('计划事件', 'LIFECYCLE', rows || '<div class="empty">暂无事件</div>');
}

function systemCard(p, st) {
  const s = st.settings || {};
  const prof = p.params_profile || {};
  return card('数据与引擎', 'SYSTEM', `
    <div class="kv">
      <div><span>来源</span><b>${esc(p.source || '—')}</b></div>
      <div><span>市场</span><b>${marketCN(p.market)}</b></div>
      <div><span>数据时间</span><b>${timeFull(p.data_ts)}</b></div>
      <div><span>分析时间</span><b>${timeHM(p.as_of)}</b></div>
      <div><span>参数版本</span><b>v${prof.version ?? 0} · ${esc(prof.source || 'default')}</b></div>
      <div><span>周期模式</span><b>${s.mode === 'single' ? '单周期' : '多周期'}</b></div>
      <div><span>自动触发</span><b>${s.auto_trigger ? 'ON' : 'OFF'}</b></div>
      <div><span>推送</span><b>${s.auto_push ? 'QQ ON' : 'QQ OFF'}</b></div>
    </div>
    <div class="muted" style="font-size:9.5px;margin-top:7px">计划由确定性引擎建立；LLM 只写解读与受限参数建议。</div>
  `);
}

export function renderPanels(el, st) {
  const p = st.symbols[st.active];
  if (!p || p.error) {
    el.innerHTML = `<div class="skeleton-card">${p ? '数据不可用：' + esc(p.error) : '加载中…'}</div>`;
    return;
  }
  const order = p.interval_order || Object.keys(p.intervals || {});
  const tf = order.includes(window.__nkaRightInterval) ? window.__nkaRightInterval : order[0];
  window.__nkaRightInterval = tf;
  el.innerHTML = [
    verdictCard(p),
    planCard(p),
    intervalCard(p),
    levelsCard(p, tf),
    llmCard(p, st),
    eventsCard(p),
    systemCard(p, st)
  ].join('');
  $('side-sub').textContent = `${st.interval.toUpperCase()} 图 · ${tf.toUpperCase()} 分析 · ${p.name || p.symbol}`;
}
