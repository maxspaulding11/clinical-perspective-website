/* ============================================================
   Find a professor by research interest.

   This file used to render the list. It no longer does: every card,
   interest and badge is written into the HTML by
   scripts/render_professors.py, and what is left here is the search box,
   the save stars, and nothing else. See the note above CARDS.
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);


  let query = '';

  function paintStar(btn, saved) {
    btn.classList.toggle('is-saved', saved);
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save to my list');
    btn.title = saved ? 'Saved — click to remove' : 'Save to my list';
    btn.textContent = saved ? '★' : '☆';
  }

  // Correct the stars already on screen instead of rebuilding the list.
  //
  // Same defect the tracker had: this page ships its cards pre-rendered with
  // every star empty, because the HTML is one document served to everybody,
  // and the real saved list arrives later from a fetch to another origin.
  // Re-rendering on arrival tore down and rebuilt every card well after first
  // paint -- and there are 2,647 names here, so it is the larger of the two.
  // Nothing in that sync changes which professors match or what a card says.
  function repaintSaved() {
    if (!window.TCPSaved) return;
    document.querySelectorAll('#prof-list [data-star-prof]').forEach(b => {
      paintStar(b, window.TCPSaved.isProfSaved(b.dataset.starProf));
    });
  }



  // Nothing is fetched. Everything this page shows is already in the HTML.
  //
  // It used to pull professors.json (229KB gzipped) and programs.json (79KB)
  // on every visit, to fill in interests and accepting-status badges that the
  // server could have written in the first place. At 134KB of HTML that made
  // a single visit 442KB, and it is why this was the heaviest page on the
  // site when Netlify cut the whole thing off for bandwidth on 8 October 2026.
  //
  // render_professors.py now ships every card complete, badge included --
  // data/star-map.json resolves the names that previously needed the fuzzy
  // matcher here. So the list is built, the badges are right, and there is
  // nothing left to wait for.
  const CARDS = [];
  (function indexCards() {
    const list = $('#prof-list');
    if (!list) return;
    for (const el of list.querySelectorAll(':scope > .fac-card')) {
      // The card's own text is the search index: name, school, program and
      // every interest, which is exactly what _hay used to concatenate.
      CARDS.push({ el: el, hay: (el.textContent || '').toLowerCase() });
    }
  })();

  // Filtering hides and shows; it never rebuilds.
  //
  // Rebuilding was what tore the list down to 150 cards and grew it back,
  // which cost this page a CLS of 1.013. Toggling display touches only the
  // cards whose state actually changes and moves nothing else.
  function render() {
    let shown = 0;
    for (const c of CARDS) {
      const hit = !query || c.hay.indexOf(query) !== -1;
      if (hit) shown++;
      const want = hit ? '' : 'none';
      if (c.el.style.display !== want) c.el.style.display = want;
    }
    const empty = $('#prof-empty');
    if (empty) empty.hidden = shown !== 0;
    $('#prof-showing').textContent = query
      ? 'Showing ' + shown + ' of ' + CARDS.length + ' professors'
      : '';
  }

  // Same reasoning as the tracker: the handler records the query and returns,
  // so the typed character paints without waiting for 2,647 cards.
  let filterTimer = 0;

  $('#prof-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    clearTimeout(filterTimer);
    filterTimer = setTimeout(render, 160);
  });

  $('#prof-list').addEventListener('click', e => {
    const btn = e.target.closest('[data-star-prof]');
    if (!btn || !window.TCPSaved) return;
    paintStar(btn, window.TCPSaved.toggleProf(btn.dataset.starProf));
  });

  // Repaint, do not re-render: this fires after a cross-origin fetch, long
  // past first paint, and rebuilding 2,647 cards there shifted the page.
  document.addEventListener('tcp-saved-synced', repaintSaved);
})();
