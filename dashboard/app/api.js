const TOKEN = new URLSearchParams(location.search).get('token') || localStorage.getItem('nk_token') || '';
if (TOKEN) localStorage.setItem('nk_token', TOKEN);

function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, v);
  });
  if (TOKEN) p.set('token', TOKEN);
  const s = p.toString();
  return s ? '?' + s : '';
}

export async function get(path, params) {
  const r = await fetch(path + qs(params), { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
  return r.json();
}

export async function post(path, body) {
  const r = await fetch(path + qs({}), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body || {})
  });
  if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
  return r.json();
}

export function connect(onEvent, onState) {
  let es = null;
  let tries = 0;
  function open() {
    try {
      es = new EventSource('/api/stream' + qs({}));
    } catch (e) {
      onState && onState(false);
      return;
    }
    es.addEventListener('hello', () => { tries = 0; onState && onState(true); });
    es.addEventListener('symbol', e => onEvent && onEvent('symbol', JSON.parse(e.data)));
    es.addEventListener('plan', e => onEvent && onEvent('plan', JSON.parse(e.data)));
    es.addEventListener('settings', e => onEvent && onEvent('settings', JSON.parse(e.data)));
    es.onerror = () => {
      onState && onState(false);
      es.close();
      tries += 1;
      setTimeout(open, Math.min(15000, 1500 * tries));
    };
  }
  open();
  return () => es && es.close();
}
