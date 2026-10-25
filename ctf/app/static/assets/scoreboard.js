'use strict';
(async () => {
  await mountTop('scoreboard');
  const bloodNum = (n) => h('span', { class: 'bl' }, n || '–');

  async function refresh() {
    const [sb, fd] = await Promise.all([api('/api/scoreboard'), api('/api/feed')]);
    const rows = sb.data.rows, me = sb.data.me;
    $('#count').textContent = `Jonli · ${sb.data.count} ishtirokchi`;

    const order = [rows[1], rows[0], rows[2]].filter(Boolean);
    $('#podium').replaceChildren(...order.map((r) => h('div', { class: `pod p${r.rank}` },
      h('div', { class: 'l1' }, h('div', { class: 'pl' }, r.rank), h('div', { class: 'muted', style: 'font-size:13px' }, `${r.solved} masala`)),
      h('div', { class: 'nm' }, r.name),
      h('div', { class: 'l3' }, h('div', { class: 'sc' }, fmt(r.score)), h('div', { class: 'bl' }, drop('x'), `${r.bloods} first blood`)))));
    document.querySelectorAll('.pod svg').forEach((s) => s.setAttribute('class', ''));

    const top = Math.max(1, rows[0]?.score || 1);
    $('#tbl').replaceChildren(
      h('div', { class: 'tr th' }, h('div', {}, "O'rin"), h('div', {}, 'Ism'), h('div', {}, 'Yechgan'), h('div', {}, 'First blood'), h('div', {}, 'Oxirgi'), h('div', {}, 'Ball')),
      ...rows.map((r) => h('div', { class: `tr${r.id === me ? ' me' : ''}${r.rank <= 3 ? ' top3' : ''}` },
        h('div', { class: 'pl' }, r.rank), h('div', {}, r.id === me ? `${r.name} (siz)` : r.name), h('div', { class: 'mono' }, r.solved),
        h('div', { class: 'mono' }, bloodNum(r.bloods)), h('div', { class: 'mn' }, r.last ? hm(r.last) : '–'),
        h('div', { class: 'scb' }, h('b', {}, fmt(r.score)), h('i', {}, h('em', { style: `width:${Math.max(0, r.score) / top * 100}%` }))))));

    $('#feed').replaceChildren(...(fd.data.length ? fd.data.map((f) => h('div', { class: 'fe' },
      h('time', {}, hm(f.at)),
      h('div', {}, h('strong', {}, f.name), ' ', h('span', { class: 'muted' }, 'yechdi'), ` ${f.task} `, h('span', { class: 'pts' }, `+${f.points}`), ' ',
        f.blood ? h('span', { class: 'blood' }, drop(), 'FIRST BLOOD') : null)))
      : [h('div', { class: 'muted', style: 'padding:10px 0' }, 'Hali hech kim yechmagan.')]));
  }
  await refresh();
  setInterval(refresh, 5000);
})();
