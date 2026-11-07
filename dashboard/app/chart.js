import { fmtPrice, pct, colorOf } from './format.js';

const C = {
  up: '#ff5b6e', down: '#22c77a', gold: '#e0b968', blue: '#4f9cf9',
  violet: '#9b8cff', amber: '#f0a94c', text: '#dce7f5', muted: '#71839a',
  line: '#1b2836', support: '#3f9d7a', resistance: '#d17a5a', risk: '#ff8a4c'
};

let chart = null, candles = null, e20 = null, e50 = null, volume = null;
let wrap = null, overlay = null, ctx = null, ohlcEl = null;
let payload = null, interval = '4h';
let layers = { structure: true, patterns: true, zones: true, plan: true };
let lastKey = '';
let ro = null;

function autoFmt(p) {
  if (p === null || p === undefined) return '';
  const a = Math.abs(p);
  if (a >= 1000) return p.toFixed(1);
  if (a >= 10) return p.toFixed(2);
  if (a >= 1) return p.toFixed(3);
  return p.toFixed(4);
}

export function initChart() {
  wrap = document.getElementById('chart-wrap');
  overlay = document.getElementById('overlay');
  ohlcEl = document.getElementById('ohlc');
  ctx = overlay.getContext('2d');
  const el = document.getElementById('chart');
  if (!window.LightweightCharts) {
    document.getElementById('chart-empty').hidden = false;
    document.getElementById('chart-empty').textContent = '图表库未加载';
    return;
  }
  chart = LightweightCharts.createChart(el, {
    autoSize: true,
    layout: {
      background: { type: 'solid', color: '#080d14' },
      textColor: '#8ea1b8', fontSize: 10,
      fontFamily: 'Inter, -apple-system, "PingFang SC", sans-serif'
    },
    grid: {
      vertLines: { color: '#0e1824' },
      horzLines: { color: '#0e1824' }
    },
    rightPriceScale: {
      borderColor: C.line, scaleMargins: { top: 0.06, bottom: 0.22 },
      entireTextOnly: false
    },
    timeScale: {
      borderColor: C.line, timeVisible: true, secondsVisible: false,
      rightOffset: 10, barSpacing: 8, minBarSpacing: 2
    },
    crosshair: {
      mode: 0,
      vertLine: { color: '#33475f', width: 1, style: 2, labelBackgroundColor: '#1b2a3c' },
      horzLine: { color: '#33475f', width: 1, style: 2, labelBackgroundColor: '#1b2a3c' }
    },
    localization: { priceFormatter: autoFmt },
    handleScroll: true, handleScale: true
  });

  candles = chart.addCandlestickSeries({
    upColor: C.up, downColor: C.down, borderVisible: false,
    wickUpColor: C.up, wickDownColor: C.down,
    priceLineVisible: false, lastValueVisible: true
  });
  e20 = chart.addLineSeries({
    color: C.gold, lineWidth: 1, priceLineVisible: false,
    lastValueVisible: false, crosshairMarkerVisible: false
  });
  e50 = chart.addLineSeries({
    color: C.blue, lineWidth: 1, priceLineVisible: false,
    lastValueVisible: false, crosshairMarkerVisible: false
  });
  volume = chart.addHistogramSeries({
    priceFormat: { type: 'volume' }, priceScaleId: 'vol',
    priceLineVisible: false, lastValueVisible: false
  });
  chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false });

  chart.subscribeCrosshairMove(param => {
    if (!param || !param.time || !payload) return updateOHLC(null);
    const bar = param.seriesData && param.seriesData.get(candles);
    if (bar) updateOHLC(bar);
    else updateOHLC(null);
  });
  chart.timeScale().subscribeVisibleLogicalRangeChange(() => redraw());
  chart.timeScale().subscribeVisibleTimeRangeChange(() => redraw());
  ro = new ResizeObserver(() => { sizeCanvas(); redraw(); });
  ro.observe(wrap);
  window.addEventListener('resize', () => { sizeCanvas(); redraw(); });
  sizeCanvas();
  updateLayers(layers);
}

function sizeCanvas() {
  if (!overlay || !wrap) return;
  const dpr = window.devicePixelRatio || 1;
  const w = wrap.clientWidth, h = wrap.clientHeight;
  overlay.width = Math.max(1, Math.round(w * dpr));
  overlay.height = Math.max(1, Math.round(h * dpr));
  overlay.style.width = w + 'px';
  overlay.style.height = h + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

export function updateLayers(l) {
  layers = Object.assign({}, layers, l || {});
  redraw();
}

export function setPayload(p, tf) {
  payload = p;
  interval = tf || interval;
  const iv = payload && payload.intervals && payload.intervals[interval];
  const empty = document.getElementById('chart-empty');
  if (!iv || !iv.candles || !iv.candles.length) {
    if (empty) { empty.hidden = false; empty.textContent = '该周期暂无数据'; }
    if (candles) candles.setData([]);
    if (volume) volume.setData([]);
    return;
  }
  if (empty) empty.hidden = true;
  const key = payload.symbol + ':' + interval;
  const first = key !== lastKey;
  candles.setData(iv.candles.map(k => ({
    time: Math.floor(k.t / 1000), open: k.o, high: k.h, low: k.l, close: k.c
  })));
  e20.setData((iv.ema20_series || []).map((v, i) => {
    const k = iv.candles[i];
    return k && v != null ? { time: Math.floor(k.t / 1000), value: v } : null;
  }).filter(Boolean));
  e50.setData((iv.ema50_series || []).map((v, i) => {
    const k = iv.candles[i];
    return k && v != null ? { time: Math.floor(k.t / 1000), value: v } : null;
  }).filter(Boolean));
  volume.setData(iv.candles.map(k => ({
    time: Math.floor(k.t / 1000), value: k.v,
    color: k.c >= k.o ? 'rgba(255,91,110,.26)' : 'rgba(34,199,122,.22)'
  })));
  updateOHLC(null);
  if (first) {
    chart.timeScale().fitContent();
    // show the most recent ~140 bars, not the whole history
    setTimeout(() => {
      try {
        const n = iv.candles.length;
        chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 140), to: n + 8 });
      } catch (e) {}
    }, 20);
    lastKey = key;
  }
  requestAnimationFrame(redraw);
}

export function refit() {
  if (chart) chart.timeScale().fitContent();
}

function updateOHLC(bar) {
  if (!ohlcEl || !payload) return;
  const iv = payload.intervals && payload.intervals[interval];
  if (!iv || !iv.candles || !iv.candles.length) return;
  const k = bar || iv.candles[iv.candles.length - 1];
  const prev = iv.candles[iv.candles.length - 2];
  const chg = prev ? (k.close - prev.close) / prev.close * 100 : 0;
  ohlcEl.innerHTML =
    `<span style="color:${colorOf(chg)}">${fmtPrice(k.close)} ${pct(chg)}</span>` +
    ` <span class="muted">O</span> ${fmtPrice(k.open)}` +
    ` <span class="muted">H</span> ${fmtPrice(k.high)}` +
    ` <span class="muted">L</span> ${fmtPrice(k.low)}` +
    ` <span class="muted">V</span> ${fmtNum(k.volume)}`;
}

function fmtNum(v) {
  if (v == null) return '—';
  if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return String(Math.round(v));
}

function ts() { return chart.timeScale(); }
function rightEdge() {
  try {
    const w = chart.priceScale('right').width();
    return wrap.clientWidth - w - 2;
  } catch (e) { return wrap.clientWidth - 62; }
}
function X(t) {
  const x = ts().timeToCoordinate(t);
  if (x != null) return x;
  const last = payload && payload.intervals && payload.intervals[interval] &&
    payload.intervals[interval].candles;
  if (!last || !last.length) return null;
  const lastT = Math.floor(last[last.length - 1].t / 1000);
  const firstT = Math.floor(last[0].t / 1000);
  if (t > lastT) return rightEdge();
  if (t < firstT) return 0;
  return null;
}
function Y(p) {
  const y = candles.priceToCoordinate(p);
  return y == null ? null : y;
}

function line(x1, y1, x2, y2, color, width = 1, dash = []) {
  if ([x1, y1, x2, y2].some(v => v == null)) return;
  ctx.save();
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash(dash);
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  ctx.restore();
}

function label(x, y, text, color, align = 'right', bg = 'rgba(9,14,21,.86)') {
  if (x == null || y == null || !text) return;
  ctx.save();
  ctx.font = '10px "SF Mono", ui-monospace, Menlo, monospace';
  const pad = 4, w = ctx.measureText(text).width + pad * 2, h = 15;
  let bx = align === 'right' ? x - w : x;
  bx = Math.max(2, Math.min(wrap.clientWidth - w - 2, bx));
  const by = Math.max(1, Math.min(wrap.clientHeight - h - 1, y - h / 2));
  ctx.fillStyle = bg;
  ctx.fillRect(bx, by, w, h);
  ctx.strokeStyle = color; ctx.globalAlpha = .45; ctx.strokeRect(bx + .5, by + .5, w - 1, h - 1);
  ctx.globalAlpha = 1;
  ctx.fillStyle = color; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  ctx.fillText(text, bx + pad, by + h / 2 + .5);
  ctx.restore();
}

function boxPoly(points, fill, stroke) {
  const pts = points.map(p => ({ x: X(p.t), y: Y(p.p) })).filter(p => p.x != null && p.y != null);
  if (pts.length < 2) return;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
  ctx.closePath();
  ctx.fillStyle = fill; ctx.fill();
  ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.stroke();
  ctx.restore();
  return pts;
}

function rect(x1, y1, x2, y2, fill, stroke) {
  if ([x1, y1, x2, y2].some(v => v == null)) return;
  ctx.save();
  ctx.fillStyle = fill; ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
  ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
  ctx.strokeRect(x1 + .5, y1 + .5, x2 - x1 - 1, y2 - y1 - 1);
  ctx.restore();
}

export function redraw() {
  if (!ctx || !payload || !chart) return;
  const iv = payload.intervals && payload.intervals[interval];
  if (!iv || !iv.candles || !iv.candles.length) return;
  ctx.clearRect(0, 0, wrap.clientWidth, wrap.clientHeight);
  const ann = iv.annotations || {};
  const now = Math.floor(Date.now() / 1000);
  const right = rightEdge();

  // ---------- supply / demand zones ----------
  if (layers.zones) {
    for (const z of ann.zones || []) {
      const y1 = Y(z.top), y2 = Y(z.bottom);
      if (y1 == null || y2 == null) continue;
      const x1 = X(z.from_t) ?? 0;
      rect(x1, Math.min(y1, y2), right, Math.max(y1, y2),
        z.kind === 'demand' ? 'rgba(63,157,122,.09)' : 'rgba(209,122,90,.08)',
        z.kind === 'demand' ? 'rgba(63,157,122,.45)' : 'rgba(209,122,90,.42)');
      label(right - 4, Math.max(10, Math.min(y1, y2) - 4),
        z.label, z.kind === 'demand' ? C.support : C.resistance, 'right',
        'rgba(9,14,21,.92)');
    }
  }

  // ---------- horizontal levels ----------
  if (layers.structure) {
    const levels = ann.levels || {};
    for (const s of (levels.supports || []).slice(0, 4)) {
      const y = Y(s.price); if (y == null) continue;
      line(0, y, right, y, 'rgba(63,157,122,.38)', 1, [2, 4]);
      label(right - 4, y, 'S ' + fmtPrice(s.price), C.support);
    }
    for (const r of (levels.resistances || []).slice(0, 4)) {
      const y = Y(r.price); if (y == null) continue;
      line(0, y, right, y, 'rgba(209,122,90,.38)', 1, [2, 4]);
      label(right - 4, y, 'R ' + fmtPrice(r.price), C.resistance);
    }
  }

  // ---------- channels ----------
  if (layers.structure) {
    for (const ch of ann.channels || []) {
      const pts = ch.points || [];
      if (pts.length < 2) continue;
      const x1 = X(pts[0].t), y1 = Y(pts[0].p);
      const x2 = X(pts[1].t) ?? right, y2 = Y(pts[1].p);
      let x3 = right, y3 = y2;
      if (ch.extend_to && ch.points && ch.points[1]) {
        const slope = (y2 - y1) / Math.max(1, (x2 - x1));
        y3 = y2 + slope * (right - x2);
      }
      line(x1, y1, x2, y2, 'rgba(91,115,145,.55)', 1, [5, 4]);
      line(x2, y2, x3, y3, 'rgba(91,115,145,.35)', 1, [2, 5]);
      label(right - 4, y3, ch.label, 'rgba(151,173,198,.9)');
    }
  }

  // ---------- zigzag / pivots ----------
  if (layers.structure && ann.zigzag && ann.zigzag.length > 1) {
    ctx.save();
    ctx.beginPath();
    let started = false;
    for (const p of ann.zigzag) {
      const x = X(p.t), y = Y(p.p);
      if (x == null || y == null) continue;
      if (!started) { ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = 'rgba(122,148,178,.35)';
    ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();
  }

  // ---------- patterns ----------
  if (layers.patterns) {
    (ann.patterns || []).forEach((p, pi) => {
      const bull = p.direction === 'bullish';
      const col = bull ? C.up : p.direction === 'bearish' ? C.down : C.gold;
      const fill = bull ? 'rgba(255,91,110,.07)' : p.direction === 'bearish'
        ? 'rgba(34,199,122,.06)' : 'rgba(224,185,104,.05)';
      const pts = boxPoly(p.points || [], fill, col);
      if (p.box) {
        const y1 = Y(p.box.top), y2 = Y(p.box.bottom);
        const x1 = X(p.box.from_t) ?? 0;
        rect(x1, Math.min(y1, y2), right, Math.max(y1, y2), fill, col);
      }
      for (const ln of p.lines || []) {
        const y = Y(ln.price); if (y == null) continue;
        const x1 = X(ln.from_t) ?? 0;
        line(x1, y, right, y, col, ln.strength >= 3 ? 1.4 : 1,
          ln.dashed === false ? [] : [4, 4]);
        label(right - 4, y, ln.label + ' ' + fmtPrice(ln.price), col);
      }
      if (pts && pts.length) {
        const cx = pts.reduce((a, b) => a + b.x, 0) / pts.length;
        const cy = Math.min(...pts.map(p => p.y)) - 8;
        if (pi < 3) label(cx + 34, cy, p.label + (p.quality ? ' ' + p.quality : ''), col, 'right');
      }
    });
  }

  // ---------- plan ----------
  const plan = payload.plan;
  if (layers.plan && plan && plan.status !== 'closed' && plan.status !== 'void') {
    const t = Number(plan.trigger), s = Number(plan.stop);
    const tp1 = Number(plan.target1), tp2 = Number(plan.target2);
    const long = plan.side === 'long';
    const x0 = Math.max(0, X(plan.created_at ? Math.floor(plan.created_at / 1000) : now) ?? 0);
    const yT = Y(t), yS = Y(s), y1 = Y(tp1), y2 = tp2 ? Y(tp2) : null;
    if (yT != null && yS != null) {
      const za = Math.min(yT, yS), zb = Math.max(yT, yS);
      rect(x0, za, right, zb, long ? 'rgba(255,138,76,.06)' : 'rgba(255,138,76,.06)',
        'rgba(255,138,76,.35)');
      line(x0, yT, right, yT, C.gold, 1.4, [6, 4]);
      label(right - 4, yT, '触发 ' + fmtPrice(t), C.gold);
      line(x0, yS, right, yS, C.risk, 1.2, [3, 4]);
      label(right - 4, yS, '止损 ' + fmtPrice(s), C.risk);
    }
    if (y1 != null) {
      line(x0, y1, right, y1, C.blue, 1.2, [3, 4]);
      label(right - 4, y1, '目标1 ' + fmtPrice(tp1), C.blue);
    }
    if (y2 != null) {
      line(x0, y2, right, y2, 'rgba(79,156,249,.55)', 1, [2, 5]);
      label(right - 4, y2, '目标2 ' + fmtPrice(tp2), 'rgba(79,156,249,.8)');
    }
    const st = document.getElementById('chart-wrap');
    ctx.save();
    ctx.font = '700 11px Inter, sans-serif';
    ctx.fillStyle = long ? C.up : C.down;
    ctx.fillText((long ? 'LONG' : 'SHORT') + ' · ' + (plan.status_cn || plan.status),
      12, 34);
    ctx.restore();
  } else if (layers.plan && plan && (plan.status === 'void' || plan.status === 'closed')) {
    ctx.save();
    ctx.font = '700 11px Inter, sans-serif';
    ctx.fillStyle = C.muted;
    ctx.fillText('计划已结束 · ' + (plan.status_cn || plan.status), 12, 34);
    ctx.restore();
  }

  // ---------- pivot labels ----------
  if (layers.structure) {
    for (const m of (ann.markers || []).slice(-16)) {
      if (m.kind !== 'pivot') continue;
      const x = X(m.t), y = Y(m.p);
      if (x == null || y == null) continue;
      const below = m.side === 'below';
      ctx.save();
      ctx.fillStyle = m.label === 'HH' || m.label === 'HL' ? 'rgba(255,91,110,.9)' :
        m.label === 'LH' || m.label === 'LL' ? 'rgba(34,199,122,.9)' : 'rgba(142,161,184,.85)';
      ctx.font = '9px "SF Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText(m.label, x, y + (below ? 12 : -6));
      ctx.restore();
    }
  }
}

export function getChart() { return chart; }
