(() => {
'use strict';
const $ = id => document.getElementById(id);
const h = (t, c, x) => 
  { const e = document.createElement(t); 
    if (c) e.className = c; if (x != null) e.textContent = x; 
    return e; };

const store = 
{ get(k, d) 
  { try { const v = localStorage.getItem(k); 
    return v ? JSON.parse(v) : d; } catch { return d; } }, 
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); 
    } catch {} } };

let ST = Object.assign({ glow: 1, intro: 1, size: 16 }, store.get('sift.set', {})), 
HI = store.get('sift.hist', []);
const sv = () => store.set('sift.set', ST);

[...'SIFT'].forEach((l, i) => 
  { const s = h('span', '', l); 
    s.style.animationDelay = (3.4 + i * .28) + 's'; 
    $('iw').appendChild(s); });

function endIntro()
 { const e = $('intro'); 
  if (!e) return; 
  e.classList.add('out'); 
  document.body.classList.remove('lock'); 
  setTimeout(() => e.remove(), 1700); 
}

$('skip').addEventListener('click', endIntro);
if (ST.intro) setTimeout(endIntro, 6800);
 else { $('intro').remove(); 
  document.body.classList.remove('lock'); 
}

function applySt() 
{ $('sg').checked = !!ST.glow; 
  $('si').checked = !!ST.intro; 
  $('sz').value = ST.size; 
  $('gl').hidden = !ST.glow; 
  document.documentElement.style.fontSize = ST.size + 'px'; 
}

const gear = o => 
  $('set').classList.toggle('open', o);
$('nSet').addEventListener('click', () => gear(true)); 
$('sdone').addEventListener('click', () => gear(false));
$('sg').addEventListener('input', e => 
  { ST.glow = +e.target.checked; sv(); applySt(); });
$('si').addEventListener('input', e => 
  { ST.intro = +e.target.checked; sv(); });
$('sz').addEventListener('input', e => 
  { ST.size = +e.target.value; sv(); applySt(); });

let ct; 
$('sclr').addEventListener('click', e => 
  { const b = e.currentTarget; 
    if (b.dataset.c) { HI = []; 
      store.set('sift.hist', HI); 
      drawHist(); b.textContent = 'Clear recent'; 
      delete b.dataset.c; 
    }

     else { b.dataset.c = 1; 
        b.textContent = 'Tap again to confirm'; 
        clearTimeout(ct); 
        ct = setTimeout(() => 
          { b.textContent = 'Clear recent'; 
            delete b.dataset.c; }, 3000); } });

addEventListener('pointermove', 
  e => { const s = document.documentElement.style; 
    s.setProperty('--gx', e.clientX + 'px'); 
    s.setProperty('--gy', e.clientY + 'px'); });

document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => 
  $(b.dataset.go).scrollIntoView({ behavior: 'smooth' })));

async function api(p, o) {
  const r = await fetch(p, Object.assign({ headers: 
    { 'Content-Type': 'application/json' } }, o));
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Something went wrong. Check the address and try again.');
  return d;
}

function show(r) {
  const box = $('res'); box.replaceChildren(); box.hidden = false;
  const top = h('div', 'top'), rw = h('div', 'rw');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); 
  svg.setAttribute('viewBox', '0 0 120 120'); 
  svg.setAttribute('class', 'ring ' + (r.score >= 75 ? '' : r.score >= 50 ? 'm' : 'l'));
  const mk = c => { const e = document.createElementNS('http://www.w3.org/2000/svg', 'circle'); 
    e.setAttribute('cx', 60); 
    e.setAttribute('cy', 60); 
    e.setAttribute('r', 52); e.setAttribute('class', c); 
    return e; };
  const v = mk('v'); 
  v.setAttribute('stroke-dashoffset', 326.7); 
  svg.append(mk('t'), v); 
  rw.append(svg, h('div', 'sc', r.score));
  const info = h('div'); 
  info.append(h('h2', 
    'serif', r.score >= 75 ? 'Looking good' : 
    r.score >= 50 ? 'Needs some care' : 'Needs work'), 
  h('div', 'ru', r.url));
  top.append(rw, info); box.append(top);

  requestAnimationFrame(() => 
    requestAnimationFrame(() => 
      v.setAttribute('stroke-dashoffset', 326.7 * (1 - r.score / 100))));
  const s = r.stats, chips = h('div', 'chips');

  [`${s.words} words`, 
    `title ${s.title} chars`, 
    `${s.images} images`, 
    `${s.internal} internal links`, 
    `${s.external} external links`, 
    `${r.ms} ms`].
    forEach(t => chips.append(h('span', 'chip', t)));

  box.append(chips);
  if (r.issues.length) 
    { box.append(h('h3', 'serif', 'Fix these, in this order')); 
    r.issues.forEach(i => { const d = h('div', 'is'), b = h('div'); 
      b.append(h('span', 'tag ' + i.sev, i.sev === 'mid' ? 'medium' : i.sev), h('b', '', i.title)); 
      d.append(b, h('p', '', i.fix)); 
      box.append(d); }); }
  else box.append(h('p', '', 'Nothing to fix. Annoyingly clean.'));

  if (r.passed.length) 
    { box.append(h('h3', 'serif', 'Already fine')); 
      const p = h('div'); 
      r.passed.forEach(t => p.append(h('span', 'ok', '✓ ' + t))); 
      box.append(p); 
    }

  box.scrollIntoView
  ({ behavior: 'smooth', block: 'nearest' });
}
function drawHist() {
  $('hist').hidden = !HI.length; 
  const l = $('hl'); l.replaceChildren();
  HI.slice(0, 8).forEach(x => { const b = h('button', 'hi'); 
    b.type = 'button'; 
    b.append(h('span', '', x.url), h('span', '', String(x.score))); 
    b.addEventListener('click', async () => 
      { try { show(await api('/api/audit/' + encodeURIComponent(x.id))); 
      } catch (e) { $('msg').className = 'msg bad'; $('msg').textContent = 'That one has expired.'; 
      } }); l.append(b); });
}

$('form').addEventListener('submit', async e => {
  e.preventDefault(); 

  const m = $('msg'), b = $('go'), u = $('u').value.trim(); 
  m.className = 'msg';
  if (u.length < 3) { m.className = 'msg bad'; 
    m.textContent = 'Type a page address first.'; return; }
  b.disabled = true; m.textContent = 'Reading the page…';

  try { 
    const r = await api('/api/audit', 
      { method: 'POST', body: JSON.stringify({ url: u }) }); 
      m.textContent = ''; 
      show(r); HI.unshift({ id: r.id, url: r.url, score: r.score }); 
      HI = HI.slice(0, 20); store.set('sift.hist', HI); 
      drawHist(); 
    }

  catch (err) { m.className = 'msg bad'; m.textContent = err.message; }
  b.disabled = false;
});

$('wl').addEventListener('submit', async e => {
  e.preventDefault(); 
  
  const m = $('wm'); 
  m.className = 'msg';

  try { 
    await api('/api/waitlist', { method: 'POST', body: JSON.stringify({ email: $('em').value }) }); 
    m.className = 'msg good'; 
    m.textContent = 'You are on the list.'; 
    $('em').value = ''; }
  catch (err) { m.className = 'msg bad'; m.textContent = err.message; }
});

const C = [
['Title and description', 'Are they there, are they the right length, do they say something real.'], 
['Headings', 'One H1, and a sensible set of H2s under it.'], 
['Indexing signals', 'Status code, redirects, canonical link, noindex in the page or the headers.'], 
['Images and links', 'Alt text coverage, and how the page links in and out.'], 
['Sharing tags', 'What shows up when someone pastes the link into a chat.'], 
['Structured data and weight', 'JSON-LD, page size and how long the server took to answer.']
];

C.forEach(([t, d]) => 
  { const c = h('div', 'card'); 
    c.append(h('h3', '', t), h('p', '', d)); 
    $('cg').append(c); });

[
  ['Free', 'R0', 'Ten audits a day. Everything above.'], 
  ['Solo', 'R199 a month', 'Saved history and weekly re-checks of up to 25 pages.'],
  ['Team', 'R599 a month', 'Shared reports, 200 pages and an API key.']
]

.forEach(([n, p, d]) => 
  { const c = h('div', 'card'); 
    c.append(h('h3', '', n), h('div', 'price', p), 
    h('p', '', d)); $('pg').append(c); });
applySt(); drawHist();
})();