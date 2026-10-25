'use strict';
(async () => {
  await mountTop('terminal');

  // ---- terminal
  const term = new Terminal({
    fontFamily: 'ui-monospace, "DejaVu Sans Mono", Menlo, Consolas, monospace', fontSize: 15, cursorBlink: true, scrollback: 3000,
    theme: { background: '#0a0d10', foreground: '#e6e9ee', cursor: '#f2b134', selectionBackground: '#3a4a63' },
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open($('#term'));
  const st = $('#st');
  let ws;
  const setSt = (on, text) => { st.className = 'st' + (on ? ' on' : ''); st.lastChild.textContent = text; };
  const sendSize = () => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ t: 'r', c: term.cols, r: term.rows })); };
  const refit = () => { try { fit.fit(); sendSize(); } catch (_) { /* ko'rinmayotgan paytda */ } };

  function connect() {
    $('#reconnect').hidden = true;
    term.reset();
    setSt(false, 'ulanmoqda…');
    ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/terminal');
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => { setSt(true, 'sandbox tayyor'); refit(); term.focus(); };
    ws.onmessage = (e) => {
      if (typeof e.data === 'string') { try { term.writeln('\r\n\x1b[33m' + JSON.parse(e.data).msg + '\x1b[0m'); } catch (_) { /* e'tiborsiz */ } }
      else term.write(new Uint8Array(e.data));
    };
    ws.onclose = () => { setSt(false, 'uzildi'); $('#reconnect').hidden = false; };
  }
  term.onData((d) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ t: 'i', d })); });
  $('#reconnect').addEventListener('click', connect);
  new ResizeObserver(refit).observe($('#term'));
  fit.fit();
  connect();

  // ---- yon panel: masala
  const pick = $('#pick'), box = $('#task');
  let list = [];
  async function load() {
    const r = await api('/api/challenges');
    list = r.data.challenges;
    if (r.data.status === 'before') { box.replaceChildren(h('div', { class: 'desc' }, 'Musobaqa hali boshlanmagan.')); return; }
    const cur = pick.value || new URLSearchParams(location.search).get('task') || list[0]?.id;
    pick.replaceChildren(...list.map((c) => h('option', { value: c.id }, `${c.solved ? '✓ ' : ''}[${CAT[c.category]}] ${c.name} · ${c.points}`)));
    pick.value = list.some((c) => c.id === cur) ? cur : list[0]?.id;
    show();
  }
  function show() {
    const ch = list.find((c) => c.id === pick.value);
    if (ch) box.replaceChildren(taskPanel(ch, { changed: load }));
  }
  pick.addEventListener('change', () => { history.replaceState(null, '', '?task=' + pick.value); show(); });
  load();
})();
