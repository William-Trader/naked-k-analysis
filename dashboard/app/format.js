const NF = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const NF4 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 });

export function fmt(n, d = 2) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
  const v = Number(n);
  if (Math.abs(v) >= 1000) return NF.format(v);
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: d, maximumFractionDigits: Math.max(d, 4)
  }).format(v);
}
export function fmtPrice(n) {
  if (n === null || n === undefined) return '—';
  const v = Number(n);
  if (Math.abs(v) >= 1000) return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(v);
  if (Math.abs(v) >= 100) return new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 }).format(v);
  return NF4.format(v);
}
export function pct(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
  const v = Number(n);
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
}
export function colorOf(n) {
  if (n === null || n === undefined) return 'var(--muted)';
  return Number(n) > 0 ? 'var(--up)' : Number(n) < 0 ? 'var(--down)' : 'var(--text-dim)';
}
export function dirCN(d) {
  return d === 'long' ? '偏多' : d === 'short' ? '偏空' : '中性';
}
export function statusCN(s) {
  return ({
    armed: '待触发', triggered: '已到触发区', confirmed: '已确认',
    managing: '持仓管理', closed: '已结束', void: '已作废'
  })[s] || s || '—';
}
export function agreeCN(a) {
  return ({ aligned: '周期共振', conflict: '周期冲突', no_edge: '无方向优势', single: '单周期' })[a] || a || '—';
}
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
export function timeHM(ms) {
  if (!ms) return '—';
  const d = new Date(Number(ms));
  return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' });
}
export function timeFull(ms) {
  if (!ms) return '—';
  const d = new Date(Number(ms));
  return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit' });
}
export function timeAgo(ms) {
  if (!ms) return '—';
  const s = Math.max(0, (Date.now() - Number(ms)) / 1000);
  if (s < 60) return Math.floor(s) + 's 前';
  if (s < 3600) return Math.floor(s / 60) + 'm 前';
  if (s < 86400) return Math.floor(s / 3600) + 'h 前';
  return Math.floor(s / 86400) + 'd 前';
}
export function marketCN(m) {
  return ({ crypto: '加密货币', commodity: '大宗商品', index: '全球指数',
    future: '海外期货', cn_future: '国内期货' })[m] || m || '—';
}
