'use strict';
// Umumiy yordamchilar. Barcha matn textContent orqali qo'yiladi (innerHTML ishlatilmaydi) — ism orqali XSS bo'lmaydi.
const $ = (s, r = document) => r.querySelector(s);
const SVGNS = 'http://www.w3.org/2000/svg';

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}

function drop(cls = 'drop') {
  const s = document.createElementNS(SVGNS, 'svg');
  s.setAttribute('viewBox', '0 0 24 28');
  s.setAttribute('class', cls);
  s.setAttribute('aria-hidden', 'true');
  const p = document.createElementNS(SVGNS, 'path');
  p.setAttribute('d', 'M12 2.5c3.5 4.4 6 7.6 6 11a6 6 0 1 1-12 0c0-3.4 2.5-6.6 6-11z');
  s.append(p);
  return s;
}

async function api(path, body) {
  const opt = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  if (r.status === 401 && location.pathname !== '/') { location.href = '/'; return new Promise(() => {}); }
  let data = {};
  try { data = await r.json(); } catch (_) { /* bo'sh javob */ }
  return { status: r.status, ok: r.ok, data };
}

const fmt = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const pad = (n) => String(n).padStart(2, '0');
const hms = (ts) => { const d = new Date(ts * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const hm = (ts) => hms(ts).slice(0, 5);
const delta = (sec) => `+${Math.floor(sec / 60)}:${pad(Math.floor(sec % 60))}`;
const CAT = { linux: 'LINUX', crypto: 'CRYPTO', web: 'WEB', forensics: 'FORENSICS', misc: 'MISC' };
const tag = (cat) => h('span', { class: `tag t-${cat}` }, CAT[cat] || cat.toUpperCase());

// **qalin** va `kod` — boshqa hech narsa. Hammasi xavfsiz DOM tugunlari.
function md(text) {
  const frag = document.createDocumentFragment();
  for (const para of text.split(/\n\n+/)) {
    const p = h('p');
    for (const part of para.split(/(`[^`]+`|\*\*[^*]+\*\*)/)) {
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) p.append(h('code', {}, part.slice(1, -1)));
      else if (part.startsWith('**') && part.endsWith('**') && part.length > 4) p.append(h('strong', {}, part.slice(2, -2)));
      else p.append(part);
    }
    frag.append(p);
  }
  return frag;
}

let toastTimer;
function toast(msg, kind = 'ok') {
  $('.toast')?.remove();
  const t = h('div', { class: `toast ${kind}`, role: 'status' }, msg);
  document.body.append(t);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.remove(), 4000);
}

// ------------------------------------------------------------ yuqori panel
let topState = { end: null, start: null };
async function mountTop(active) {
  const root = $('#top');
  const [me, st] = await Promise.all([api('/api/me'), api('/api/state')]);
  topState = st.data;
  window.ME = me.data.name;
  const clock = h('div', { class: 'clock' });
  const chip = h('div', { class: 'chip-user' });
  const draw = (m) => chip.replaceChildren(
    h('div', { class: 'avatar' }, m.name[0].toUpperCase()), h('div', { class: 'nm' }, m.name),
    h('div', { class: 'sc' }, `${fmt(m.score)} ball`), h('div', { class: 'rk' }, `#${m.rank}`));
  draw(me.data);
  root.replaceChildren(
    h('a', { class: 'logo', href: '/challenges' }, 'BICO', h('b', {}, '/'), 'CTF'),
    h('nav', { class: 'tabs' }, [['terminal', 'Terminal'], ['challenges', 'Savollar'], ['scoreboard', 'Reyting']].map(
      ([k, t]) => h('a', { href: '/' + k, class: k === active ? 'on' : '' }, t))),
    h('div', { class: 'right' }, clock, chip,
      h('button', { class: 'linkbtn', onclick: async () => { await api('/api/logout', {}); location.href = '/'; } }, 'Chiqish')));
  const skew = topState.now - Date.now() / 1000; // server va brauzer soati farqi
  const tick = () => {
    const now = Date.now() / 1000 + skew;
    let label = null, target = null;
    if (topState.start && now < topState.start) { label = 'Boshlanishiga'; target = topState.start; }
    else if (topState.end && now < topState.end) { label = 'Tugashiga'; target = topState.end; }
    else if (topState.end) { clock.textContent = 'Musobaqa tugadi'; return; }
    if (!label) { clock.textContent = ''; return; }
    const left = Math.max(0, Math.floor(target - now));
    clock.replaceChildren(label + ' ', h('b', {}, `${pad(Math.floor(left / 3600))}:${pad(Math.floor(left / 60) % 60)}:${pad(left % 60)}`));
  };
  tick(); setInterval(tick, 1000);
  window.refreshMe = async () => { const m = await api('/api/me'); draw(m.data); };
  setInterval(window.refreshMe, 20000);
  return me.data;
}

// ------------------------------------------------------------ masala paneli (Terminal va Savollar sahifalarida)
// ch — /api/challenges elementi; opts.solvers — "kim yechdi" ro'yxatini ko'rsatish; opts.changed() — ma'lumot o'zgardi
function taskPanel(ch, opts = {}) {
  const box = h('div', { class: 'task' });
  const input = h('input', { class: 'input code', id: 'flag', 'aria-label': 'Flag', placeholder: 'BICO{...}', autocomplete: 'off', spellcheck: 'false' });
  const send = h('button', { class: 'btn primary', type: 'submit' }, 'Yuborish');
  const hintList = h('div', { class: 'hints' }, ch.hints.map((t) => h('div', { class: 'hintbox' }, md(t))));
  const hintBtn = ch.next_hint_cost != null && !ch.solved
    ? h('button', { class: 'btn', type: 'button', onclick: async () => {
        hintBtn.disabled = true;
        const r = await api('/api/hint', { id: ch.id });
        if (!r.ok) { toast(r.data.error || 'Xato', 'bad'); hintBtn.disabled = false; return; }
        toast(`Hint ochildi (−${r.data.cost} ball)`, 'ok');
        window.refreshMe?.(); opts.changed?.();
      } }, `Hint ochish (−${ch.next_hint_cost} ball)`)
    : null;

  const form = h('form', { class: 'row', onsubmit: async (e) => {
    e.preventDefault();
    const flag = input.value.trim();
    if (!flag) return;
    send.disabled = true;
    const r = await api('/api/submit', { id: ch.id, flag });
    send.disabled = false;
    if (!r.ok) return toast(r.data.error || 'Xato', 'bad');
    if (r.data.already) return toast('Bu masalani allaqachon yechgansiz', 'ok');
    if (!r.data.ok) { input.select(); return toast(r.data.message || "Noto'g'ri flag", 'bad'); }
    toast(r.data.first_blood ? `Birinchi bo'lib yechdingiz! +${r.data.points} ball` : `To'g'ri! +${r.data.points} ball`, r.data.first_blood ? 'blood' : 'ok');
    window.refreshMe?.(); opts.changed?.();
  } }, h('div', { style: 'flex:3 1 160px' }, input), h('div', { style: 'flex:1 1 100px' }, send));

  const files = ch.files.length
    ? h('div', { class: 'files' },
        h('div', { class: 'muted', style: 'font-size:13px;margin-bottom:6px' }, 'Fayllar (terminalda ', h('code', {}, `~/masalalar/${ch.id}/`), ')'),
        ch.files.map((f) => h('a', { href: `/files/${ch.id}/${f}`, download: f }, f)))
    : null;
  const web = ch.web_port
    ? h('div', {}, h('a', { class: 'btn', href: `http://${location.hostname}:${ch.web_port}`, target: '_blank', rel: 'noopener' }, 'Saytni ochish ↗'))
    : null;

  box.append(...[
    h('div', { class: 'l1' }, tag(ch.category), h('span', { class: 'pts' }, `${ch.points} ball`)),
    h('h3', {}, ch.name),
    h('div', { class: 'desc' }, md(ch.description)),
    files, web, hintList, hintBtn,
    ch.solved ? h('div', { style: 'color:var(--green);font-weight:600' }, '✓ Siz bu masalani yechgansiz') : form,
  ].filter(Boolean));
  if (opts.solvers) {
    const list = h('div', {}, h('div', { class: 'muted', style: 'padding:8px 10px;font-size:13px' }, 'Yuklanmoqda…'));
    box.append(h('div', { class: 'solvers' }, h('div', { class: 'h' }, h('strong', {}, 'Kim yechdi'),
      h('span', { class: 'muted', style: 'font-size:13px' }, `${ch.solves} kishi`)), list));
    api(`/api/solvers/${ch.id}`).then((r) => {
      const rows = r.data || [];
      list.replaceChildren(...(rows.length ? rows.slice(0, 15).map((s, i) => h('div', { class: `srow${s.first ? ' fb' : ''}${s.name === window.ME ? ' me' : ''}` },
        h('div', { class: 'n' }, i + 1), h('div', { class: 'nm' }, s.name === window.ME ? `${s.name} (siz)` : s.name),
        s.first ? h('span', { class: 'blood' }, drop(), 'FIRST BLOOD') : null,
        h('div', { class: 'tm' }, s.first ? hms(s.at) : delta(s.at - rows[0].at))))
        : [h('div', { class: 'empty', style: 'padding:14px 10px;text-align:left;color:var(--accent)' }, "Hali hech kim yechmagan. Birinchi bo'l!")]),
        ...(rows.length > 15 ? [h('div', { class: 'muted', style: 'padding:8px 10px;font-size:13px' }, `+ yana ${rows.length - 15} kishi`)] : []));
    });
  }
  return box;
}
