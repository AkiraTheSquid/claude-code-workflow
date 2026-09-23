/* ------------------------------------------------------------------
   mockup harness — one runtime for the index gallery and every variant.

   index.html      : <div id="mockup-index"></div>  → gallery is rendered
                     from mockups.config.js. Nothing to hand-write.
   variant-*.html  : end the page script with
                       Mockup.boot({ variant: 'a', scenes: SCENES });
                     → floating bar (variants · scenes · phone) + the scene
                       named in ?scene= is applied.

   A scene switch is a real navigation, not a state reset — the page
   reloads clean, so a scene can never inherit the previous scene's DOM.

   Keys: ← →  scene   [ ]  variant   i  index   p  phone   h  hide bar
   (ignored while typing in an input / textarea / contenteditable)
   ------------------------------------------------------------------ */

(function () {
  'use strict';

  const CFG = window.MOCKUPS;
  if (!CFG) {
    console.error('[mockup] mockups.config.js did not load — nothing to render.');
    return;
  }

  const variants = CFG.variants || [];
  const params = new URLSearchParams(location.search);
  const byId = (id) => variants.find((v) => v.id === id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* ------------------------------ index ------------------------------ */

  function sceneCard(v, s) {
    return `<a class="mx-scene" href="${esc(v.file)}?scene=${encodeURIComponent(s.id)}">
      <b>${esc(s.name || s.id)}</b>
      <span>${s.note || ''}</span>
      <span class="mx-tag">${esc(v.id.toUpperCase())} · ?scene=${esc(s.id)}</span>
    </a>`;
  }

  function stillCard(item) {
    return `<a class="mx-scene" href="${esc(item.file)}">
      <b>${esc(item.name || item.file)}</b>
      <span>${item.note || ''}</span>
      <span class="mx-tag">${esc(item.file)}</span>
    </a>`;
  }

  function renderIndex(root) {
    document.title = CFG.title || 'Mockups';
    const sections = variants.map((v) => `
      <section class="mx-variant">
        <h2>${esc(v.name || v.id)}${v.status
          ? `<span class="mx-status" data-status="${esc(v.status)}">${esc(v.status)}</span>` : ''}</h2>
        ${v.lede ? `<p class="mx-lede">${v.lede}</p>` : ''}
        <div class="mx-grid">${(v.scenes || []).map((s) => sceneCard(v, s)).join('')}</div>
      </section>`).join('');

    const stills = (CFG.stills || []).length ? `
      <section class="mx-variant">
        <h2>Stills · earlier passes</h2>
        <div class="mx-grid">${CFG.stills.map(stillCard).join('')}</div>
      </section>` : '';

    root.innerHTML = `
      <div class="mx-page">
        <h1>${esc(CFG.title || 'Mockups')}</h1>
        <p class="mx-sub">${CFG.subtitle || 'Nothing is wired. Every screen is the same file, driven by a scene name.'}</p>
        ${sections}
        ${stills}
        ${CFG.notes ? `<div class="mx-note">${CFG.notes}</div>` : ''}
      </div>`;
  }

  /* --------------------------- variant pages --------------------------- */

  function go(file, sceneId) {
    location.href = `${file}?scene=${encodeURIComponent(sceneId)}`;
  }

  function openPhone() {
    const w = (CFG.phone && CFG.phone.width) || 420;
    const h = (CFG.phone && CFG.phone.height) || 860;
    window.open(location.href, 'mockup-phone', `width=${w},height=${h}`);
  }

  function buildBar(v, sceneId) {
    const scenes = v.scenes || [];
    const bar = document.createElement('div');
    bar.className = 'mockup-bar';
    bar.innerHTML = `
      <a href="index.html" title="All mockups (i)">☰ all</a>
      <span class="mb-sep"></span>
      <span class="mb-label">v</span>
      ${variants.map((o) => {
        const target = (o.scenes || []).some((s) => s.id === sceneId)
          ? sceneId
          : ((o.scenes || [])[0] || {}).id;
        return `<a class="${o.id === v.id ? 'is-current' : ''}"
                   href="${esc(o.file)}?scene=${encodeURIComponent(target || '')}"
                   title="${esc(o.name || o.id)}">${esc(o.id.toUpperCase())}</a>`;
      }).join('')}
      <span class="mb-sep"></span>
      ${scenes.map((s) => `<a class="${s.id === sceneId ? 'is-current' : ''}"
           href="${esc(v.file)}?scene=${encodeURIComponent(s.id)}"
           title="${esc(s.note || '')}">${esc(s.name || s.id)}</a>`).join('')}
      <span class="mb-sep"></span>
      <button type="button" data-act="phone" title="Open this scene in a phone-width window (p)">phone</button>
      <button type="button" data-act="hide" title="Hide this bar (h)">×</button>`;

    const tab = document.createElement('div');
    tab.className = 'mockup-tab';
    tab.textContent = '· · ·';
    tab.title = 'Show the mockup bar (h)';
    tab.hidden = true;

    const setHidden = (hide) => {
      bar.hidden = hide;
      tab.hidden = !hide;
      try { localStorage.setItem('mockup-bar-hidden', hide ? '1' : '0'); } catch (e) { /* private mode */ }
    };
    bar.addEventListener('click', (e) => {
      const act = e.target.closest('[data-act]');
      if (!act) return;
      if (act.dataset.act === 'phone') openPhone();
      if (act.dataset.act === 'hide') setHidden(true);
    });
    tab.addEventListener('click', () => setHidden(false));

    document.body.append(bar, tab);
    let stored = '0';
    try { stored = localStorage.getItem('mockup-bar-hidden') || '0'; } catch (e) { /* private mode */ }
    setHidden(stored === '1');
    return { setHidden, isHidden: () => bar.hidden };
  }

  function bindKeys(v, sceneId, bar) {
    const scenes = v.scenes || [];
    const si = Math.max(0, scenes.findIndex((s) => s.id === sceneId));
    const vi = Math.max(0, variants.findIndex((o) => o.id === v.id));

    document.addEventListener('keydown', (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target;
      // A mock is full of textareas — never steal a key from one.
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;

      const step = (arr, i, d) => arr[(i + d + arr.length) % arr.length];
      switch (e.key) {
        case 'ArrowRight': go(v.file, step(scenes, si, 1).id); break;
        case 'ArrowLeft': go(v.file, step(scenes, si, -1).id); break;
        case ']': case '}': {
          const nv = step(variants, vi, 1);
          go(nv.file, ((nv.scenes || []).find((s) => s.id === sceneId) || (nv.scenes || [])[0] || {}).id);
          break;
        }
        case '[': case '{': {
          const pv = step(variants, vi, -1);
          go(pv.file, ((pv.scenes || []).find((s) => s.id === sceneId) || (pv.scenes || [])[0] || {}).id);
          break;
        }
        case 'i': case 'I': location.href = 'index.html'; break;
        case 'p': case 'P': openPhone(); break;
        case 'h': case 'H': bar.setHidden(!bar.isHidden()); break;
        default: return;
      }
      e.preventDefault();
    });
  }

  /**
   * boot({ variant, scenes, onScene })
   *   variant : id in mockups.config.js
   *   scenes  : { sceneId() {…} } — each mutates the already-rendered DOM
   *   onScene : optional (sceneId) => void, run after the scene function
   */
  function boot(opts) {
    const v = byId(opts.variant);
    if (!v) { console.error(`[mockup] variant "${opts.variant}" is not in mockups.config.js`); return; }

    const listed = (v.scenes || []).map((s) => s.id);
    const wanted = params.get('scene') || listed[0];
    const scenes = opts.scenes || {};

    // A scene listed on the index but not implemented here is the bug that
    // shows up as "the card does nothing" — say so instead of failing silent.
    listed.filter((id) => !scenes[id]).forEach((id) =>
      console.warn(`[mockup] ${v.id}: scene "${id}" is on the index but has no function`));
    Object.keys(scenes).filter((id) => !listed.includes(id)).forEach((id) =>
      console.warn(`[mockup] ${v.id}: scene "${id}" exists but is not on the index`));

    document.title = `${CFG.title || 'Mockup'} — ${v.id.toUpperCase()} · ${wanted}`;
    document.body.dataset.mockupVariant = v.id;
    document.body.dataset.mockupScene = wanted;

    if (scenes[wanted]) {
      try { scenes[wanted](); } catch (err) { console.error(`[mockup] scene "${wanted}" threw:`, err); }
    }
    if (opts.onScene) opts.onScene(wanted);

    const bar = buildBar(v, wanted);
    bindKeys(v, wanted, bar);
    // A screenshot driver waits on this instead of guessing a timeout.
    document.documentElement.dataset.mockupReady = '1';
  }

  window.Mockup = { boot, renderIndex, config: CFG, scene: params.get('scene') };

  const indexRoot = document.getElementById('mockup-index');
  if (indexRoot) {
    renderIndex(indexRoot);
    document.documentElement.dataset.mockupReady = '1';
  }
})();
