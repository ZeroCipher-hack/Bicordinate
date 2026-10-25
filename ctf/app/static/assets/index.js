'use strict';
(async () => {
  if ((await api('/api/session')).data.logged_in) { location.href = '/challenges'; return; }
  const st = (await api('/api/state')).data;
  $('#stats').replaceChildren(...[[st.challenges, 'masala'], [fmt(st.points), 'jami ball'], [st.players, 'ishtirokchi']].map(
    ([n, l]) => h('div', {}, h('b', {}, n), h('span', {}, l))));
  $('#f').addEventListener('submit', async (e) => {
    e.preventDefault();
    $('#err').textContent = '';
    const r = await api('/api/login', { name: $('#name').value, pin: $('#pin').value });
    if (!r.ok) { $('#err').textContent = r.data.error || 'Xato'; return; }
    location.href = r.data.created ? '/terminal' : '/challenges';
  });
})();
