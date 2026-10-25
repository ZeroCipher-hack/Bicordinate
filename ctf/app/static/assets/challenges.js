'use strict';
(async () => {
  const me = await mountTop('challenges');
  let list = [], cat = 'hammasi', sel = location.hash.slice(1);

  async function load(keepPanel) {
    const r = await api('/api/challenges');
    if (r.data.status === 'before') {
      $('.qs').replaceChildren(h('div', { class: 'empty', style: 'width:100%' }, 'Musobaqa hali boshlanmagan. Soat 0 ga yetganda savollar shu yerda paydo bo\'ladi.'));
      return;
    }
    list = r.data.challenges;
    draw(keepPanel);
  }

  function draw(keepPanel) {
    const done = list.filter((c) => c.solved);
    const total = list.reduce((s, c) => s + c.points, 0);
    $('#sub').textContent = `${done.length} / ${list.length} yechildi · ${fmt(done.reduce((s, c) => s + c.points, 0))} / ${fmt(total)} ball`;
    $('#prog').style.width = (list.length ? done.length / list.length * 100 : 0) + '%';

    const cats = ['hammasi', ...new Set(list.map((c) => c.category))];
    $('#chips').replaceChildren(...cats.map((k) => h('button', { class: 'chip' + (k === cat ? ' on' : ''), onclick: () => { cat = k; draw(true); } },
      k === 'hammasi' ? 'Hammasi' : k[0].toUpperCase() + k.slice(1), h('span', {}, k === 'hammasi' ? list.length : list.filter((c) => c.category === k).length))));

    $('#grid').replaceChildren(...list.filter((c) => cat === 'hammasi' || c.category === cat).map((c) => h('button', {
      class: `q${c.solved ? ' done' : ''}${c.id === sel ? ' sel' : ''}`, type: 'button', onclick: () => select(c.id),
    },
      h('div', { class: 'l1' }, tag(c.category), h('span', { class: 'pts' }, `${c.points} ball`)),
      h('div', { class: 'nm' }, c.name),
      h('div', { class: 'ft' },
        c.first_blood ? h('div', { class: 'fb' }, drop(), `First blood: ${c.first_blood}`) : h('div', { class: 'first' }, "Hali hech kim yechmagan. Birinchi bo'l!"),
        h('div', { class: 'l2' }, h('span', {}, `${c.solves} kishi yechgan`), c.solved ? h('span', { class: 'ok' }, '✓ Yechilgan') : null)))));

    if (!keepPanel) panel();
  }

  function panel() {
    const ch = list.find((c) => c.id === sel);
    $('#drawer').replaceChildren(ch ? taskPanel(ch, {
      solvers: true,
      changed: async () => { await load(false); },
    }) : h('div', { class: 'empty' }, 'Masalani tanlang'));
  }

  function select(id) { sel = id; history.replaceState(null, '', '#' + id); draw(false); }

  await load(false);
  setInterval(() => load(true), 20000); // hisoblagichlar va first blood yangilanib turadi, panel qo'zg'almaydi
})();
