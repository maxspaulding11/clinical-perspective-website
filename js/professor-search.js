/* ============================================================
   Find a professor by research interest — renders data/professors.json
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

  let DATA = { professors: [] };
  let query = '';

  function matches(p) {
    if (!query) return true;
    return p._hay.indexOf(query) !== -1;
  }

  function starBtn(p) {
    const saved = window.TCPSaved && window.TCPSaved.isProfSaved(p.id);
    return '<button type="button" class="star-btn' + (saved ? ' is-saved' : '') + '" ' +
      'data-star-prof="' + esc(p.id) + '" aria-pressed="' + (saved ? 'true' : 'false') + '" ' +
      'aria-label="' + (saved ? 'Remove from my list' : 'Save to my list') + '" ' +
      'title="' + (saved ? 'Saved — click to remove' : 'Save to my list') + '">' +
      (saved ? '★' : '☆') + '</button>';
  }

  function card(p) {
    const interests = (p.interests || [])
      .map(i => '<li>' + esc(i) + '</li>')
      .join('');

    return '<li class="fac-card">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.name) + '</h3>' +
          '<p class="fac-sub">' + esc(p.school) + (p.program ? ' · ' + esc(p.program) : '') + '</p>' +
        '</div>' +
        starBtn(p) +
      '</div>' +
      '<ul class="prof-interests">' + interests + '</ul>' +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">View their university page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
  }

  function render() {
    const list = $('#prof-list');
    const shown = DATA.professors.filter(matches);

    $('#prof-showing').textContent = query
      ? 'Showing ' + shown.length + ' of ' + DATA.professors.length + ' professors'
      : '';

    list.innerHTML = shown.length
      ? shown.map(card).join('')
      : '<li class="fac-empty">Nothing matches that search.</li>';
  }

  function boot(data) {
    data.professors.sort((a, b) => a.name.localeCompare(b.name));
    data.professors.forEach(p => {
      p._hay = [p.name, p.school, p.program, ...(p.interests || [])].join(' ').toLowerCase();
    });
    DATA = data;
    const schools = new Set(data.professors.map(p => p.school));
    $('#prof-stats').innerHTML =
      '<strong>' + data.professors.length + '</strong> professors across <strong>' +
      schools.size + '</strong> programs · last updated ' + esc(data.updated || '');
    render();
  }

  fetch('../data/professors.json')
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(boot)
    .catch(() => {
      $('#prof-list').innerHTML =
        '<li class="fac-empty">Could not load the professor list. Please refresh.</li>';
    });

  $('#prof-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    render();
  });

  $('#prof-list').addEventListener('click', e => {
    const btn = e.target.closest('[data-star-prof]');
    if (!btn || !window.TCPSaved) return;
    const saved = window.TCPSaved.toggleProf(btn.dataset.starProf);
    btn.classList.toggle('is-saved', saved);
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save to my list');
    btn.title = saved ? 'Saved — click to remove' : 'Save to my list';
    btn.textContent = saved ? '★' : '☆';
  });

  document.addEventListener('tcp-saved-synced', render);
})();
