/* PA Terminal drawing layer: core TradingView-style tools on the canvas overlay. */
import { get, post } from './api.js';

const CN = {
  cursor: '光标', select: '选择', trend: '趋势线', ray: '射线', hline: '水平线',
  rect: '矩形', fib: '斐波那契', text: '文字', measure: '测量', arrow: '箭头',
  brush: '画笔', eraser: '擦除'
};

export function createDrawings(opts) {
  const { chart, series, overlay, wrap, ctx, toX, toY, rightEdge, redraw, getBars } = opts;
  const state = {
    tool: 'cursor', color: '#e0b968', width: 1.6, magnet: true, locked: false,
    drawings: [], selected: null, draft: null, drag: null, brush: [],
    undo: [], redo: [], symbol: null, interval: null, saveTimer: null, loaded: false
  };

  function setPointer() {
    overlay.style.pointerEvents = (state.tool === 'cursor') ? 'none' : 'auto';
    overlay.style.cursor = state.tool === 'eraser' ? 'not-allowed'
      : state.tool === 'cursor' ? 'default' : 'crosshair';
  }

  function setTool(tool) {
    if (state.locked && tool !== 'cursor' && tool !== 'select') return;
    state.tool = tool;
    state.draft = null;
    state.brush = [];
    document.querySelectorAll('[data-draw-tool]').forEach(b =>
      b.classList.toggle('on', b.dataset.drawTool === tool));
    setPointer();
    redraw();
  }

  function setStyle(patch) {
    Object.assign(state, patch || {});
    document.querySelectorAll('[data-draw-tool]').forEach(b => {
      if (b.dataset.drawTool === 'magnet') b.classList.toggle('on', state.magnet);
      if (b.dataset.drawTool === 'lock') b.classList.toggle('on', state.locked);
    });
    const c = document.getElementById('draw-color');
    const w = document.getElementById('draw-width');
    if (c) c.value = state.color;
    if (w) w.value = String(state.width);
    redraw();
  }

  function snapshot() {
    state.undo.push(JSON.stringify(state.drawings));
    if (state.undo.length > 60) state.undo.shift();
    state.redo = [];
  }

  function undo() {
    if (!state.undo.length) return;
    state.redo.push(JSON.stringify(state.drawings));
    state.drawings = JSON.parse(state.undo.pop());
    state.selected = null;
    save();
    redraw();
  }

  function redo() {
    if (!state.redo.length) return;
    state.undo.push(JSON.stringify(state.drawings));
    state.drawings = JSON.parse(state.redo.pop());
    save();
    redraw();
  }

  function clearAll() {
    if (!state.drawings.length) return;
    if (!confirm('清空当前周期全部绘图？')) return;
    snapshot();
    state.drawings = [];
    state.selected = null;
    save();
    redraw();
  }

  function save() {
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(async () => {
      if (!state.symbol || !state.interval) return;
      try {
        await post('/api/drawings', {
          symbol: state.symbol, interval: state.interval, lines: state.drawings
        });
      } catch (e) { console.error('drawing save', e); }
    }, 500);
  }

  async function load(symbol, interval) {
    state.symbol = symbol;
    state.interval = interval;
    state.loaded = false;
    state.drawings = [];
    state.selected = null;
    try {
      const r = await get('/api/drawings', { symbol, interval });
      state.drawings = Array.isArray(r.lines) ? r.lines : [];
    } catch (e) { state.drawings = []; }
    state.loaded = true;
    redraw();
  }

  function setSymbol(symbol, interval) {
    if (state.symbol === symbol && state.interval === interval) return;
    load(symbol, interval);
  }

  function bars() { return (getBars && getBars()) || []; }

  function pointAt(ev) {
    const r = overlay.getBoundingClientRect();
    const x = ev.clientX - r.left, y = ev.clientY - r.top;
    let t = chart.timeScale().coordinateToTime(x);
    let p = series.coordinateToPrice(y);
    const bs = bars();
    if (bs.length) {
      if (t == null) {
        let best = null, bd = 1e9;
        for (const b of bs) {
          const bx = chart.timeScale().timeToCoordinate(Math.floor(b.t / 1000));
          if (bx == null) continue;
          const d = Math.abs(bx - x);
          if (d < bd) { bd = d; best = b; }
        }
        if (best) t = Math.floor(best.t / 1000);
      }
      if (state.magnet && p != null) {
        let best = null, bd = 1e9;
        for (const b of bs.slice(-160)) {
          for (const v of [b.h, b.l, b.c]) {
            const by = series.priceToCoordinate(v);
            if (by == null) continue;
            const d = Math.abs(by - y);
            if (d < bd && d < 10) { bd = d; best = v; }
          }
        }
        if (best != null) p = best;
      }
    }
    return { x, y, t, p };
  }

  function hit(ev) {
    const { x, y } = pointAt(ev);
    for (let i = state.drawings.length - 1; i >= 0; i--) {
      const d = state.drawings[i];
      if (d.locked) continue;
      const pts = (d.points || []).map(p => ({ x: toX(p.t), y: toY(p.p) }));
      if (!pts.length) continue;
      if (d.type === 'hline') {
        if (Math.abs(pts[0].y - y) < 7) return { d, index: i, x, y };
      } else if (d.type === 'text') {
        if (Math.abs(pts[0].x - x) < 45 && Math.abs(pts[0].y - y) < 18) return { d, index: i, x, y };
      } else {
        for (let k = 0; k < pts.length - 1; k++) {
          if (distToSeg(x, y, pts[k], pts[k + 1]) < 7) return { d, index: i, x, y };
        }
      }
    }
    return null;
  }

  function distToSeg(px, py, a, b) {
    const dx = b.x - a.x, dy = b.y - a.y;
    const len = dx * dx + dy * dy;
    if (!len) return Math.hypot(px - a.x, py - a.y);
    let t = ((px - a.x) * dx + (py - a.y) * dy) / len;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (a.x + t * dx), py - (a.y + t * dy));
  }

  function finishDraft() {
    const d = state.draft;
    state.draft = null;
    if (!d || !d.points || d.points.length < 2) return;
    if (d.points.some(p => p.t == null || p.p == null)) return;
    snapshot();
    state.drawings.push(d);
    save();
    redraw();
  }

  function onDown(ev) {
    if (state.locked) return;
    const pt = pointAt(ev);
    if (pt.t == null || pt.p == null) return;
    const p = { t: pt.t, p: pt.p };
    if (state.tool === 'eraser') {
      const h = hit(ev);
      if (h) { snapshot(); state.drawings.splice(h.index, 1); save(); redraw(); }
      return;
    }
    if (state.tool === 'select') {
      const h = hit(ev);
      state.selected = h ? h.d.id : null;
      state.drag = h ? { d: h.d, x: pt.x, y: pt.y, origin: JSON.parse(JSON.stringify(h.d.points)) } : null;
      redraw();
      return;
    }
    if (state.tool === 'text') {
      const text = prompt('输入文字');
      if (text) {
        snapshot();
        state.drawings.push({ id: uid(), type: 'text', points: [p], text,
          color: state.color, width: state.width });
        save(); redraw();
      }
      return;
    }
    if (state.tool === 'hline') {
      snapshot();
      state.drawings.push({ id: uid(), type: 'hline', points: [p],
        color: state.color, width: state.width });
      save(); redraw();
      return;
    }
    if (state.tool === 'brush') {
      state.brush = [p];
      state.draft = { id: uid(), type: 'brush', points: [p],
        color: state.color, width: state.width };
      return;
    }
    state.draft = { id: uid(), type: state.tool, points: [p],
      color: state.color, width: state.width };
    redraw();
  }

  function onMove(ev) {
    if (state.drag) {
      const pt = pointAt(ev);
      if (pt.t == null || pt.p == null) return;
      const dxT = pt.t - state.drag.x, dyP = pt.p - state.drag.y;
      state.drag.d.points = state.drag.origin.map(p => ({ t: p.t, p: p.p }));
      const bs = bars();
      const idx = nearestIndex(bs, state.drag.x);
      const idx2 = nearestIndex(bs, pt.t);
      const dt = idx2 != null && idx != null ? (bs[idx2].t - bs[idx].t) / 1000 : dxT;
      state.drag.d.points.forEach(p => { p.t += dt; p.p += dyP; });
      redraw();
      return;
    }
    if (!state.draft) return;
    const pt = pointAt(ev);
    if (pt.t == null || pt.p == null) return;
    const p = { t: pt.t, p: pt.p };
    if (state.draft.type === 'brush') {
      const last = state.draft.points[state.draft.points.length - 1];
      if (!last || Math.abs(last.t - p.t) > 1 || Math.abs(last.p - p.p) > 0) {
        if (state.draft.points.length < 2000) state.draft.points.push(p);
      }
    } else {
      state.draft.points[1] = p;
    }
    redraw();
  }

  function onUp(ev) {
    if (state.drag) {
      snapshot();
      save();
      state.drag = null;
      redraw();
      return;
    }
    if (!state.draft) return;
    if (state.draft.type === 'brush') {
      if (state.draft.points.length > 1) {
        snapshot(); state.drawings.push(state.draft); save();
      }
      state.draft = null; state.brush = []; redraw();
      return;
    }
    finishDraft();
  }

  function nearestIndex(bs, t) {
    if (!bs.length || t == null) return null;
    let bi = null, bd = Infinity;
    bs.forEach((b, i) => { const d = Math.abs(b.t / 1000 - t); if (d < bd) { bd = d; bi = i; } });
    return bi;
  }

  function uid() { return 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }

  function render(context) {
    const c = context || ctx;
    if (!c || !state.loaded) return;
    const all = state.drawings.slice();
    if (state.draft) all.push(state.draft);
    for (const d of all) {
      const sel = d.id === state.selected;
      drawOne(c, d, sel);
    }
  }

  function drawOne(c, d, sel) {
    const pts = (d.points || []).map(p => ({ x: toX(p.t), y: toY(p.p) }))
      .filter(p => p.x != null && p.y != null);
    if (!pts.length) return;
    c.save();
    c.strokeStyle = d.color || state.color;
    c.fillStyle = d.color || state.color;
    c.lineWidth = sel ? (d.width || 1.5) + 1.2 : (d.width || 1.5);
    c.globalAlpha = d.type === 'brush' ? .95 : 1;
    if (sel) { c.shadowColor = '#e0b968'; c.shadowBlur = 6; }
    const right = rightEdge();
    if (d.type === 'hline') {
      c.setLineDash([]); c.beginPath(); c.moveTo(0, pts[0].y); c.lineTo(right, pts[0].y); c.stroke();
      tag(c, right - 3, pts[0].y - 9, fmtP(d.points[0].p), d.color || state.color);
    } else if (d.type === 'trend' || d.type === 'ray' || d.type === 'arrow' || d.type === 'measure') {
      if (pts.length < 2) return c.restore();
      let a = pts[0], b = pts[1];
      if (d.type === 'ray' || d.type === 'arrow') {
        const dx = b.x - a.x, dy = b.y - a.y;
        if (Math.abs(dx) > 0.1) {
          const k = (right - a.x) / dx;
          b = { x: right, y: a.y + dy * k };
        }
      }
      c.setLineDash(d.type === 'measure' ? [5, 4] : []);
      c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
      if (d.type === 'arrow') arrowHead(c, a, b);
      if (d.type === 'measure') {
        const dp = d.points[1].p - d.points[0].p;
        const pct = d.points[0].p ? dp / d.points[0].p * 100 : 0;
        const tidx = nearestIndex(bars(), d.points[1].t), iidx = nearestIndex(bars(), d.points[0].t);
        const barsN = tidx != null && iidx != null ? Math.abs(tidx - iidx) : 0;
        const txt = `${dp >= 0 ? '+' : ''}${fmtP(dp)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%) · ${barsN} bars`;
        tag(c, (a.x + b.x) / 2, (a.y + b.y) / 2 - 20, txt, d.color || state.color);
      }
    } else if (d.type === 'rect') {
      if (pts.length < 2) return c.restore();
      const x1 = Math.min(pts[0].x, pts[1].x), x2 = Math.max(pts[0].x, pts[1].x);
      const y1 = Math.min(pts[0].y, pts[1].y), y2 = Math.max(pts[0].y, pts[1].y);
      c.globalAlpha = .10; c.fillRect(x1, y1, x2 - x1, y2 - y1);
      c.globalAlpha = 1; c.setLineDash([4, 3]); c.strokeRect(x1, y1, x2 - x1, y2 - y1);
    } else if (d.type === 'fib') {
      if (pts.length < 2) return c.restore();
      const ratios = [0, .236, .382, .5, .618, .786, 1];
      ratios.forEach(r => {
        const y = pts[0].y + (pts[1].y - pts[0].y) * r;
        c.globalAlpha = r === 0 || r === 1 ? .9 : .45;
        c.setLineDash(r === 0 || r === 1 ? [] : [4, 4]);
        c.beginPath(); c.moveTo(Math.min(pts[0].x, pts[1].x), y);
        c.lineTo(right, y); c.stroke();
        const price = d.points[0].p + (d.points[1].p - d.points[0].p) * r;
        tag(c, right - 3, y - 9, `${r.toFixed(3)}  ${fmtP(price)}`, d.color || state.color);
      });
    } else if (d.type === 'text') {
      tag(c, pts[0].x, pts[0].y, d.text || '', d.color || state.color);
    } else if (d.type === 'brush') {
      c.setLineDash([]); c.beginPath();
      pts.forEach((p, i) => i ? c.lineTo(p.x, p.y) : c.moveTo(p.x, p.y));
      c.stroke();
    }
    c.restore();
  }

  function arrowHead(c, a, b) {
    const ang = Math.atan2(b.y - a.y, b.x - a.x);
    const s = 8;
    c.beginPath(); c.moveTo(b.x, b.y);
    c.lineTo(b.x - s * Math.cos(ang - .4), b.y - s * Math.sin(ang - .4));
    c.lineTo(b.x - s * Math.cos(ang + .4), b.y - s * Math.sin(ang + .4));
    c.closePath(); c.fill();
  }

  function tag(c, x, y, text, color) {
    if (!text) return;
    c.save();
    c.font = '10px "SF Mono", ui-monospace, Menlo, monospace';
    const w = c.measureText(text).width + 8, h = 15;
    let bx = Math.max(2, Math.min(wrap.clientWidth - w - 2, x - w));
    let by = Math.max(1, Math.min(wrap.clientHeight - h - 1, y - 7));
    c.fillStyle = 'rgba(9,14,21,.88)'; c.fillRect(bx, by, w, h);
    c.strokeStyle = color; c.globalAlpha = .55; c.strokeRect(bx + .5, by + .5, w - 1, h - 1);
    c.globalAlpha = 1; c.fillStyle = color; c.textAlign = 'left'; c.textBaseline = 'middle';
    c.fillText(text, bx + 4, by + h / 2 + .5);
    c.restore();
  }

  function fmtP(v) {
    if (v == null) return '—';
    const a = Math.abs(v);
    if (a >= 1000) return v.toFixed(2);
    if (a >= 10) return v.toFixed(2);
    if (a >= 1) return v.toFixed(3);
    return v.toFixed(4);
  }

  function bind() {
    overlay.addEventListener('pointerdown', onDown);
    overlay.addEventListener('pointermove', onMove);
    overlay.addEventListener('pointerup', onUp);
    overlay.addEventListener('pointerleave', onUp);
    window.addEventListener('keydown', e => {
      if (e.target.matches('input,textarea,select')) return;
      if (e.key === 'Escape') { state.draft = null; state.drag = null; setTool('cursor'); redraw(); }
      if ((e.key === 'Delete' || e.key === 'Backspace') && state.selected) {
        snapshot();
        state.drawings = state.drawings.filter(d => d.id !== state.selected);
        state.selected = null; save(); redraw();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault(); e.shiftKey ? redo() : undo();
      }
    });
    document.querySelectorAll('[data-draw-tool]').forEach(b => {
      b.addEventListener('click', () => {
        const t = b.dataset.drawTool;
        if (t === 'undo') return undo();
        if (t === 'redo') return redo();
        if (t === 'clear') return clearAll();
        if (t === 'magnet') return setStyle({ magnet: !state.magnet });
        if (t === 'lock') return setStyle({ locked: !state.locked });
        setTool(t);
      });
    });
    const color = document.getElementById('draw-color');
    const width = document.getElementById('draw-width');
    if (color) color.addEventListener('input', e => setStyle({ color: e.target.value }));
    if (width) width.addEventListener('change', e => setStyle({ width: Number(e.target.value) }));
    setStyle({});
  }

  bind();
  setPointer();
  return { setSymbol, render, setTool, undo, redo, clearAll, state };
}
