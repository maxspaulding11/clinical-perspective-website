/* ============================================================
   The Clinical Perspective — APA 7 citation engine
   ------------------------------------------------------------
   Pure logic: reference formatting, source look-ups, and a
   Word (.docx) reference-page writer. No DOM wiring lives here,
   so this file is safe to reuse anywhere.

   Exposes window.APA
   ============================================================ */
(function (global) {
  'use strict';

  /* ---------- tiny helpers ---------- */
  const escHtml = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
  const escXml  = s => String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;' }[c]));
  const uid = () => 'r' + Math.random().toString(36).slice(2, 9);

  /* Strip markup/entities that CrossRef sometimes embeds in titles. */
  function clean(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.innerHTML = String(s).replace(/<[^>]+>/g, '');
    return d.textContent.replace(/\s+/g, ' ').trim();
  }

  const stripDot   = s => (s || '').replace(/\s*[.,;:]\s*$/, '');
  const dashPages  = s => (s || '').replace(/\s*[-–—]+\s*/g, '–');

  /* ============================================================
     Sentence case
     ============================================================ */

  /* Words safe to keep capitalised anywhere in a title. */
  const PROPER = new Set(['i','african','american','americans','arab','asian','australian','black','british',
    'canadian','chinese','christian','dutch','english','european','french','german','greek','hispanic','indian',
    'irish','islamic','israeli','italian','japanese','jewish','korean','latino','latina','latinx','mexican',
    'muslim','native','russian','scottish','spanish','swedish','uk','us','usa','welsh','western','eastern',
    'national','international','world','united','states','royal','federal',
    'january','february','march','april','may','june','july','august','september','october','november','december',
    'monday','tuesday','wednesday','thursday','friday','saturday','sunday',
    'alzheimer','alzheimers',"alzheimer's",'parkinson','parkinsons',"parkinson's",'asperger','aspergers',
    "asperger's",'tourette','tourettes',"tourette's",'down','huntington',"huntington's",'wernicke','broca',
    'freud','freudian','jungian','pavlovian','skinnerian','rogerian','bayesian','likert','rorschach','beck',
    'wechsler','hamilton','montreal','stroop','minnesota','california','harvard','oxford','cambridge','stanford',
    'covid','covid-19','sars-cov-2','hiv','aids','dsm','dsm-5','icd','icd-11','nhs','who','cdc','nih','nimh','apa',
    'ptsd','adhd','ocd','asd','bpd','mdd','gad','cbt','dbt','act','emdr','ssri','ssris','mri','fmri','eeg','tms',
    'ecg','rct','rcts','covid19','sars','ebola','zika']);

  /* Words that continue an organisation's name once a proper noun has opened one:
     "National Institute of Mental Health". Only ever extend an existing run. */
  const ORG_WORD = new Set(['association','institute','institutes','university','college','society',
    'organization','organisation','department','ministry','foundation','council','centre','center',
    'academy','federation','bureau','agency','administration','committee','board','office','press',
    'school','hospital','trust','service','services','health','psychological','psychiatric','medical',
    'statistical','national','international','federal','royal','general','surgeon','mental','human',
    'welfare','justice','education','veterans','affairs','research','sciences','science','nursing']);
  const CHAIN_THROUGH = new Set(['of','and','for','the','on','in','&']);

  /* APA wants sentence case for article/book titles. This is deliberately
     conservative: acronyms, eponyms and organisations survive. A personal
     surname inside a title is indistinguishable from an ordinary word, so
     those still need a human eye. */
  function toSentenceCase(title) {
    if (!title) return '';
    let startOfSentence = true;
    let inProperRun = false;
    return title.split(/(\s+)/).map(w => {
      if (/^\s+$/.test(w)) return w;
      const core = w.replace(/^[^\w]+|[^\w]+$/g, '');
      const lower = core.toLowerCase();
      let out = w;

      const isProper  = PROPER.has(lower) || PROPER.has(lower.replace(/(’s|'s|s)$/, ''));
      const isAcronym = /[A-Z].*[A-Z]/.test(core) || /\d/.test(core);
      const continuesOrg = inProperRun && ORG_WORD.has(lower);
      const keep = startOfSentence || isProper || isAcronym || continuesOrg;

      if (!keep && /^[A-Z][a-z’']*$/.test(core)) out = w.replace(core, core.toLowerCase());
      if (startOfSentence && /^[a-z]/.test(core)) out = w.replace(core, core[0].toUpperCase() + core.slice(1));

      if (isProper || continuesOrg) inProperRun = true;
      else if (!CHAIN_THROUGH.has(lower)) inProperRun = false;

      startOfSentence = /[.:?!]\s*$/.test(w);
      if (startOfSentence) inProperRun = false;
      return out;
    }).join('');
  }

  /* ============================================================
     Names
     ============================================================ */

  function initials(given) {
    if (!given) return '';
    return given.trim().split(/\s+/).map(part =>
      part.split('-').filter(Boolean).map(p => p[0].toUpperCase() + '.').join('-')
    ).join(' ');
  }

  function authorName(a) {
    if (a.literal) return a.literal.replace(/\.$/, '');
    const fam = (a.family || '').trim();
    const ini = initials(a.given);
    return ini ? fam + ', ' + ini : fam;
  }

  /* APA 7: up to 20 names in full; 21+ → first 19, ellipsis, final author. */
  function formatAuthors(authors) {
    const names = (authors || []).map(authorName).filter(Boolean);
    if (!names.length) return '';
    if (names.length === 1) return names[0];
    if (names.length === 2) return names[0] + ', & ' + names[1];
    if (names.length <= 20) return names.slice(0, -1).join(', ') + ', & ' + names[names.length - 1];
    return names.slice(0, 19).join(', ') + ', . . . ' + names[names.length - 1];
  }

  /* Editors are not inverted: "T. D. Cannon & T. Widiger". */
  function editorNames(eds) {
    const names = (eds || []).map(a => {
      if (a.literal) return a.literal;
      const ini = initials(a.given);
      return ini ? ini + ' ' + a.family : a.family;
    }).filter(Boolean);
    if (!names.length) return '';
    if (names.length === 1) return names[0];
    if (names.length === 2) return names[0] + ' & ' + names[1];
    return names.slice(0, -1).join(', ') + ', & ' + names[names.length - 1];
  }

  /* ============================================================
     Reference formatting → HTML (<i> for italics)
     ============================================================ */
  function formatRef(r) {
    const it = s => '<i>' + escHtml(s) + '</i>';
    const parts = [];
    const authors = formatAuthors(r.authors);
    const year = r.year ? r.year : 'n.d.';
    const dateStr = r.date ? year + ', ' + r.date : year;
    const title = stripDot(r.title);

    /* A personal name ends in an initial whose period closes the author element;
       a group author ("World Health Organization") needs that period added. */
    const authorsEl = authors && !/\.$/.test(authors) ? authors + '.' : authors;
    const noAuthor = !authors;
    parts.push(noAuthor ? '' : escHtml(authorsEl) + ' (' + escHtml(dateStr) + ').');

    switch (r.type) {
      case 'book': {
        const ed = r.edition ? ' (' + escHtml(r.edition) + ' ed.)' : '';
        parts.push(it(title) + ed + '.');
        if (r.publisher) parts.push(escHtml(r.publisher) + '.');
        break;
      }
      case 'chapter': {
        parts.push(escHtml(title) + '.');
        const eds = editorNames(r.editors);
        const edLabel = (r.editors || []).length > 1 ? 'Eds.' : 'Ed.';
        const pages = r.pages ? ' (pp. ' + escHtml(dashPages(r.pages)) + ')' : '';
        parts.push('In ' + (eds ? escHtml(eds) + ' (' + edLabel + '), ' : '') +
                   it(stripDot(r.container)) + pages + '.');
        if (r.publisher) parts.push(escHtml(r.publisher) + '.');
        break;
      }
      case 'webpage': {
        parts.push(it(title) + '.');
        if (r.container) parts.push(escHtml(stripDot(r.container)) + '.');
        break;
      }
      case 'report': {
        const num = r.number ? ' (' + escHtml(r.number) + ')' : '';
        parts.push(it(title) + num + '.');
        if (r.publisher) parts.push(escHtml(r.publisher) + '.');
        break;
      }
      case 'thesis': {
        parts.push(it(title) + ' [' + escHtml(r.number || 'Doctoral dissertation') + '].');
        if (r.publisher) parts.push(escHtml(r.publisher) + '.');
        break;
      }
      default: {   // journal article / preprint
        parts.push(escHtml(title) + '.');
        let bib = '';
        if (r.container) {
          bib = it(stripDot(r.container));
          if (r.volume) {
            bib += ', ' + it(r.volume);
            if (r.issue) bib += '(' + escHtml(r.issue) + ')';
          }
          if (r.pages) bib += ', ' + escHtml(dashPages(r.pages));
          else if (r.article) bib += ', Article ' + escHtml(r.article);
          bib += '.';
        } else if (r.publisher) {
          bib = escHtml(r.publisher) + '.';
        }
        if (bib) parts.push(bib);
      }
    }

    /* With no author, APA moves the title into the author slot; the date follows it. */
    if (noAuthor && parts[1]) parts[1] += ' (' + escHtml(dateStr) + ').';

    if (r.doi) parts.push('https://doi.org/' + escHtml(r.doi.replace(/^https?:\/\/doi\.org\//i, '')));
    else if (r.url) parts.push(escHtml(r.url));

    /* Tidy punctuation left by empty segments, but leave the ". . ." ellipsis alone. */
    return parts.filter(Boolean).join(' ')
      .replace(/\s+,/g, ',')
      .replace(/([A-Za-z0-9)\]])\s+\./g, '$1.');
  }

  function inText(r, narrative) {
    const a = r.authors || [];
    const surname = x => x.literal ? x.literal.replace(/\.$/, '') : (x.family || '');
    const year = r.year || 'n.d.';
    let names;
    if (!a.length) names = stripDot(r.title).split(/\s+/).slice(0, 4).join(' ');
    else if (a.length === 1) names = surname(a[0]);
    else if (a.length === 2) names = narrative ? surname(a[0]) + ' and ' + surname(a[1])
                                               : surname(a[0]) + ' & ' + surname(a[1]);
    else names = surname(a[0]) + ' et al.';
    return narrative ? names + ' (' + year + ')' : '(' + names + ', ' + year + ')';
  }

  /* Alphabetical by first author surname, then year. */
  const sortKey = r => {
    const a = (r.authors || [])[0];
    const name = a ? (a.literal || a.family || '') : stripDot(r.title);
    return (name + ' ' + (r.year || '')).toLowerCase();
  };
  const sortRefs = refs => refs.slice().sort((a, b) => sortKey(a).localeCompare(sortKey(b)));

  /* ============================================================
     Source look-ups (all three APIs are CORS-open, no keys)
     ============================================================ */

  function parseQuery(q) {
    q = (q || '').trim();
    if (!q) return null;
    const doi = q.match(/\b(10\.\d{4,9}\/[^\s"'<>]+)/i);
    if (doi) return { kind:'doi', value: doi[1].replace(/[.,;)\]]+$/, '') };
    const pmid = q.match(/(?:pmid[:\s]*|pubmed\.ncbi\.nlm\.nih\.gov\/)(\d{5,9})/i);
    if (pmid) return { kind:'pmid', value: pmid[1] };
    const isbnRaw = q.replace(/[-\s]/g, '');
    if (/^(?:isbn:?)?(\d{9}[\dxX]|\d{13})$/i.test(isbnRaw))
      return { kind:'isbn', value: isbnRaw.replace(/^isbn:?/i, '') };
    if (/^\d{5,9}$/.test(q)) return { kind:'pmid', value: q };
    if (/^https?:\/\//i.test(q)) return { kind:'url', value: q };
    return { kind:'unknown', value: q };
  }

  const CROSSREF_TYPES = {
    'journal-article':'article', 'posted-content':'article', 'proceedings-article':'article',
    'book':'book', 'monograph':'book', 'edited-book':'book',
    'book-chapter':'chapter', 'book-part':'chapter', 'report':'report', 'dissertation':'thesis'
  };

  async function fetchDOI(doi) {
    const res = await fetch('https://api.crossref.org/works/' + encodeURIComponent(doi));
    if (res.status === 404) throw new Error('No CrossRef record for ' + doi);
    if (!res.ok) throw new Error('CrossRef returned ' + res.status);
    const m = (await res.json()).message;
    const issued = (m.issued && m.issued['date-parts'] && m.issued['date-parts'][0]) ||
                   (m.created && m.created['date-parts'] && m.created['date-parts'][0]) || [];
    const people = list => (list || []).map(a =>
      a.name ? { literal: clean(a.name) } : { family: clean(a.family), given: clean(a.given) });
    const type = CROSSREF_TYPES[m.type] || 'article';
    return {
      id: uid(), type,
      authors: people(m.author), editors: people(m.editor),
      year: issued[0] ? String(issued[0]) : '',
      title: clean((m.title || [])[0]),
      container: clean((m['container-title'] || [])[0]),
      volume: clean(m.volume), issue: clean(m.issue),
      pages: clean(m.page), article: clean(m['article-number']),
      publisher: type === 'article' ? '' : clean(m.publisher),
      doi: m.DOI, url: '', source: 'CrossRef'
    };
  }

  async function fetchPMID(pmid) {
    const res = await fetch('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=' +
                            pmid + '&retmode=json');
    if (!res.ok) throw new Error('PubMed returned ' + res.status);
    const rec = (await res.json()).result[pmid];
    if (!rec || rec.error) throw new Error('No PubMed record for ' + pmid);

    /* Prefer CrossRef when a DOI exists — fuller journal names and metadata. */
    const doi = (rec.articleids || []).find(x => x.idtype === 'doi');
    if (doi) { try { return await fetchDOI(doi.value); } catch (e) { /* fall through */ } }

    const authors = (rec.authors || []).filter(a => a.authtype === 'Author').map(a => {
      const p = a.name.trim().split(/\s+/);
      const ini = p.length > 1 ? p.pop() : '';
      return { family: p.join(' '), given: ini.split('').join(' ') };
    });
    return {
      id: uid(), type:'article', authors, editors: [],
      year: (rec.pubdate || '').match(/\d{4}/) ? rec.pubdate.match(/\d{4}/)[0] : '',
      title: clean(rec.title),
      container: clean(rec.fulljournalname || rec.source),
      volume: clean(rec.volume), issue: clean(rec.issue), pages: clean(rec.pages),
      publisher:'', doi:'', url:'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/',
      source:'PubMed',
      warn: rec.fulljournalname ? '' : 'PubMed gave an abbreviated journal name — check the full title.'
    };
  }

  async function fetchISBN(isbn) {
    const res = await fetch('https://openlibrary.org/api/books?bibkeys=ISBN:' + isbn + '&format=json&jscmd=data');
    if (!res.ok) throw new Error('Open Library returned ' + res.status);
    const b = (await res.json())['ISBN:' + isbn];
    if (!b) throw new Error('No Open Library record for ISBN ' + isbn);

    /* Open Library carries near-duplicate author records plus junk scraped from
       title pages. Normalise hard, then split people from organisations. */
    const ORG = /\b(association|university|press|institute|organi[sz]ation|society|college|department|ministry|foundation|council|centre|center|committee|agency|bureau|group|board|academy|federation|office|administration)\b/i;
    const seen = new Set();
    const authors = (b.authors || [])
      .map(a => clean(a.name).replace(/[.,]\s*$/, ''))
      .filter(n => n && !/\d/.test(n))
      .filter(n => {
        const k = n.toLowerCase().replace(/[^a-z]/g, '');
        if (seen.has(k)) return false;
        seen.add(k); return true;
      })
      .map(n => {
        const parts = n.split(/\s+/);
        if (parts.length < 2 || parts.length > 4 || ORG.test(n)) return { literal: n };
        const family = parts.pop();
        return { family, given: parts.join(' ') };
      });

    return {
      id: uid(), type:'book', authors, editors: [],
      year: (b.publish_date || '').match(/\d{4}/) ? b.publish_date.match(/\d{4}/)[0] : '',
      title: [clean(b.title), clean(b.subtitle)].filter(Boolean).join(': '),
      container:'', volume:'', issue:'', pages:'',
      publisher: clean(((b.publishers || [])[0] || {}).name || (b.publishers || [])[0]),
      doi:'', url:'', source:'Open Library',
      warn:'Open Library book records are uneven — check the authors, publisher and title casing.'
    };
  }

  async function lookupOne(q) {
    const p = parseQuery(q);
    if (!p) return null;
    if (p.kind === 'doi')  return await fetchDOI(p.value);
    if (p.kind === 'pmid') return await fetchPMID(p.value);
    if (p.kind === 'isbn') return await fetchISBN(p.value);
    if (p.kind === 'url')
      throw new Error('No DOI, PMID or ISBN found in "' + q.slice(0, 42) + '" — add it by hand instead.');
    throw new Error('Couldn’t read "' + q.slice(0, 42) + '" — paste a DOI, PMID or ISBN, or add it by hand.');
  }

  function newRef() {
    return { id: uid(), type:'article', authors: [], editors: [], year:'', title:'',
             container:'', volume:'', issue:'', pages:'', publisher:'', edition:'',
             number:'', date:'', doi:'', url:'' };
  }

  /* "Surname, First M.; Other, A." → author objects */
  function parsePeople(text) {
    return (text || '').split(';').map(s => s.trim()).filter(Boolean).map(s => {
      const m = s.match(/^([^,]+),\s*(.+)$/);
      return m ? { family: m[1].trim(), given: m[2].trim() } : { literal: s };
    });
  }

  /* ============================================================
     Plain text / HTML output
     ============================================================ */
  const refToPlain = r => formatRef(r)
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');

  const refsToPlain = refs => sortRefs(refs).map(refToPlain).join('\n\n');

  /* Hanging-indent HTML — pastes into Word with formatting intact. */
  const refsToHtml = refs => sortRefs(refs).map(r =>
    '<p style="margin:0 0 12pt 0.5in;text-indent:-0.5in;font-family:\'Times New Roman\',serif;' +
    'font-size:12pt;line-height:2;">' + formatRef(r) + '</p>').join('\n');

  /* ============================================================
     Word (.docx) writer
     ------------------------------------------------------------
     A .docx is a ZIP of XML parts. We build one by hand — stored
     (uncompressed) entries are perfectly valid, so no zip library
     is needed and the page stays dependency-free.
     ============================================================ */

  function crc32(buf) {
    let table = crc32.table;
    if (!table) {
      table = crc32.table = new Uint32Array(256);
      for (let i = 0; i < 256; i++) {
        let c = i;
        for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
        table[i] = c >>> 0;
      }
    }
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < buf.length; i++) crc = (crc >>> 8) ^ table[(crc ^ buf[i]) & 0xFF];
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }

  function zipStore(files) {
    const enc = new TextEncoder();
    const chunks = [], central = [];
    let offset = 0;
    const DOS_DATE = 0x2821;   // 2000-01-01, fixed so output is reproducible

    files.forEach(f => {
      const nameB = enc.encode(f.name);
      const data = typeof f.data === 'string' ? enc.encode(f.data) : f.data;
      const crc = crc32(data);

      const lh = new Uint8Array(30 + nameB.length);
      const lv = new DataView(lh.buffer);
      lv.setUint32(0, 0x04034b50, true);
      lv.setUint16(4, 20, true);           // version needed
      lv.setUint16(8, 0, true);            // method: stored
      lv.setUint16(12, DOS_DATE, true);
      lv.setUint32(14, crc, true);
      lv.setUint32(18, data.length, true);
      lv.setUint32(22, data.length, true);
      lv.setUint16(26, nameB.length, true);
      lh.set(nameB, 30);
      chunks.push(lh, data);

      const cd = new Uint8Array(46 + nameB.length);
      const cv = new DataView(cd.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true);           // version made by
      cv.setUint16(6, 20, true);           // version needed
      cv.setUint16(8, 0, true);            // method: stored
      cv.setUint16(14, DOS_DATE, true);
      cv.setUint32(16, crc, true);
      cv.setUint32(20, data.length, true);
      cv.setUint32(24, data.length, true);
      cv.setUint16(28, nameB.length, true);
      cv.setUint32(42, offset, true);      // offset of local header
      cd.set(nameB, 46);
      central.push(cd);

      offset += lh.length + data.length;
    });

    const cdSize = central.reduce((n, c) => n + c.length, 0);
    const eocd = new Uint8Array(22);
    const ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(8, files.length, true);
    ev.setUint16(10, files.length, true);
    ev.setUint32(12, cdSize, true);
    ev.setUint32(16, offset, true);

    return new Blob(chunks.concat(central, [eocd]),
      { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  }

  /* Turn our "<i>…</i>" reference HTML into Word runs. */
  function htmlToRuns(html) {
    const doc = new DOMParser().parseFromString('<div>' + html + '</div>', 'text/html');
    const runs = [];
    (function walk(node, italic) {
      node.childNodes.forEach(c => {
        if (c.nodeType === 3) {
          if (c.nodeValue) runs.push({ text: c.nodeValue, italic });
        } else if (c.nodeType === 1) {
          walk(c, italic || c.tagName === 'I' || c.tagName === 'EM');
        }
      });
    })(doc.body.firstChild, false);
    return runs;
  }

  const runXml = r =>
    '<w:r>' + (r.italic ? '<w:rPr><w:i/></w:rPr>' : '') +
    '<w:t xml:space="preserve">' + escXml(r.text) + '</w:t></w:r>';

  const W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
  const R_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';

  /* Builds an APA 7 reference page: 1in margins, Times New Roman 12pt,
     double spaced, bold centred "References", half-inch hanging indents,
     and a page number in the top-right corner. */
  function buildReferencesDocx(refs, opts) {
    opts = opts || {};
    const heading = opts.heading || 'References';
    const entries = sortRefs(refs).map(r =>
      '<w:p><w:pPr><w:ind w:left="720" w:hanging="720"/></w:pPr>' +
      htmlToRuns(formatRef(r)).map(runXml).join('') +
      '</w:p>'
    ).join('');

    const document_xml =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:document ' + W_NS + ' ' + R_NS + '><w:body>' +
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>' +
        '<w:r><w:rPr><w:b/></w:rPr><w:t>' + escXml(heading) + '</w:t></w:r></w:p>' +
        entries +
        '<w:sectPr>' +
          '<w:headerReference w:type="default" r:id="rId2"/>' +
          '<w:pgSz w:w="12240" w:h="15840"/>' +
          '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" ' +
                   'w:header="720" w:footer="720" w:gutter="0"/>' +
        '</w:sectPr>' +
      '</w:body></w:document>';

    const styles_xml =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:styles ' + W_NS + '>' +
        '<w:docDefaults><w:rPrDefault><w:rPr>' +
          '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>' +
          '<w:sz w:val="24"/><w:szCs w:val="24"/>' +
        '</w:rPr></w:rPrDefault>' +
        '<w:pPrDefault><w:pPr>' +
          '<w:spacing w:before="0" w:after="0" w:line="480" w:lineRule="auto"/>' +
        '</w:pPr></w:pPrDefault></w:docDefaults>' +
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">' +
          '<w:name w:val="Normal"/><w:qFormat/></w:style>' +
      '</w:styles>';

    const header_xml =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:hdr ' + W_NS + '><w:p>' +
        '<w:pPr><w:jc w:val="right"/><w:spacing w:line="240" w:lineRule="auto"/></w:pPr>' +
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>' +
        '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>' +
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>' +
      '</w:p></w:hdr>';

    const content_types =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>' +
        '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>' +
      '</Types>';

    const REL = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"';
    const root_rels =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships ' + REL + '>' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>' +
      '</Relationships>';

    const doc_rels =
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships ' + REL + '>' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>' +
      '</Relationships>';

    return zipStore([
      { name: '[Content_Types].xml',       data: content_types },
      { name: '_rels/.rels',               data: root_rels },
      { name: 'word/document.xml',         data: document_xml },
      { name: 'word/styles.xml',           data: styles_xml },
      { name: 'word/header1.xml',          data: header_xml },
      { name: 'word/_rels/document.xml.rels', data: doc_rels }
    ]);
  }

  function downloadBlob(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  /* ============================================================ */
  global.APA = {
    // formatting
    formatRef, inText, toSentenceCase, formatAuthors, editorNames, initials,
    sortRefs, sortKey,
    // look-ups
    parseQuery, lookupOne, fetchDOI, fetchPMID, fetchISBN,
    // model
    newRef, parsePeople, uid, clean,
    // output
    refToPlain, refsToPlain, refsToHtml, buildReferencesDocx, downloadBlob,
    escHtml
  };
})(window);
