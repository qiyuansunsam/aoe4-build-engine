/* Simplified Chinese localisation layer (embedded by build.py before crafter.js).
 *
 * The app renders English through template strings. In zh mode a MutationObserver translates text
 * nodes and the title/placeholder/aria-label attributes of everything rendered. Observer callbacks
 * run as microtasks before the next paint, so English never flashes. Lookup order: overrides, the
 * game's own official translations (data/i18n-zh-game.json, built by scripts/build_zh_locale.py),
 * the hand-written UI dictionary (data/i18n-zh-ui.json), then its regex patterns, then a split on
 * separators (" · ", " + ", ", ", ": ", parentheses) that translates each piece and keeps the rest.
 * Player names, numbers, times, ids and anything inside [data-i18n-skip] stay untouched.
 *
 * Every translated node or attribute remembers its English original, so switching back restores
 * the DOM and then re-runs the current route's render. English is the default; only a saved choice
 * (localStorage 'aoe-crafter-lang' = 'zh') switches the app to Chinese.
 */
(function () {
  'use strict';
  const KEY = 'aoe-crafter-lang';
  const ATTRS = ['title', 'placeholder', 'aria-label'];
  const SKIP = 'script,style,[data-i18n-skip],#ai-output,.build-comments-list article p';
  const NAMES = '.player-search';
  const LATIN = /[A-Za-z]{2}/;
  const data = window.I18N_ZH || {};
  let lang = 'en';
  try { if (localStorage.getItem(KEY) === 'zh') lang = 'zh'; } catch {}

  const norm = s => String(s).replace(/\s+/g, ' ').trim();
  // squash: case and punctuation-insensitive key, so id-derived labels ("Precision Cross Breeding",
  // "FarBerries", "Zhu Xis Legacy") still find "Precision Cross-Breeding", "Far berries", "Zhu Xi's Legacy".
  const squash = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
  let maps = null, lower = null, loose = null, patterns = [], namePattern = null;
  const cache = new Map();
  let depth = 0;

  function init() {
    if (maps) return;
    const ui = data.ui || {}, game = data.game || {};
    const toMap = (...objects) => {
      const m = new Map();
      for (const obj of objects) for (const k in obj || {}) if (k[0] !== '_' && typeof obj[k] === 'string') m.set(norm(k), obj[k]);
      return m;
    };
    maps = [toMap(ui.overrides), toMap(game.terms, game.text), toMap(ui.strings, ui.data)];
    lower = new Map(); loose = new Map();
    for (let i = maps.length - 1; i >= 0; i--) for (const [k, v] of maps[i]) {
      lower.set(k.toLowerCase(), v);
      const l = squash(k);
      if (l.length > 5 && k.length < 60) loose.set(l, v);
    }
    patterns = [];
    for (const p of ui.patterns || []) {
      const [source, to] = Array.isArray(p) ? p : [p.re, p.to];
      try { patterns.push([new RegExp('^(?:' + source + ')$'), to]); } catch (err) { console.warn('i18n pattern', source, err); }
    }
    namePattern = [/^Player (\d+)$/, maps[2].get('Player') ? maps[2].get('Player') + ' $1' : '玩家 $1'];
  }

  function lookup(key) {
    for (const m of maps) { const v = m.get(key); if (v != null) return v; }
    const low = key.toLowerCase(), v = lower.get(low);
    if (v != null) return v;
    if (/[a-z]s$/.test(low) && low.length > 3) {
      const singular = lower.get(low.slice(0, -1)) ?? (low.endsWith('ies') ? lower.get(low.slice(0, -3) + 'y') : null) ?? (low.endsWith('es') ? lower.get(low.slice(0, -2)) : null);
      if (singular != null) return singular;
    }
    const l = squash(key);
    return l.length > 5 ? loose.get(l) ?? (l.endsWith('s') ? loose.get(l.slice(0, -1)) : null) ?? null : null;
  }

  // Replacement syntax: $1 inserts a group as is; {1} inserts it translated. A {n} group with Latin
  // letters that does not translate makes the pattern fail, so the next pattern or the split is tried.
  function fill(to, m) {
    let ok = true;
    const out = to.replace(/\{(\d)\}/g, (_, n) => {
      const g = m[n];
      if (g == null) return '';
      if (!LATIN.test(g)) return g;
      const t = nested(g);
      if (t == null) ok = false;
      return t ?? g;
    }).replace(/\$(\d)/g, (_, n) => m[n] ?? '');
    return ok ? out : null;
  }

  // A piece inside a pattern or after a number: translated whole, or by the separator split as long
  // as nothing English is left over.
  function nested(g) {
    if (depth >= 4) return lookup(norm(g));
    depth++;
    try {
      const t = basic(g) ?? composite(norm(g));
      return t != null && !LATIN.test(t.replace(/VS Code|AoE4 World|AoE 4|AoE IV/g, '')) ? t : null;
    } finally { depth--; }
  }

  function basic(key) {
    key = norm(key);
    if (!LATIN.test(key)) return null;
    const hit = lookup(key);
    if (hit != null) return hit;
    // A " · " list is translated piece by piece (composite); only patterns written for such lists may span it.
    const list = MAJOR.test(key);
    if (depth < 3) {
      depth++;
      try { for (const [re, to] of patterns) { if (list && !/[·•|]/.test(re.source)) continue; const m = key.match(re); if (m) { const t = fill(to, m); if (t != null) return t; } } }
      finally { depth--; }
    }
    if (list) { const n = key.match(/^([+\-−×]?\d[\d,.:]*\s*(?:%|s|x)?)\s+(.+)$/), t = n && lookup(n[2]); return t != null && n ? n[1] + ' ' + t : null; }
    // A number or time before or after a known term: "12 villagers", "0:00 Scout", "carry +5".
    let m = key.match(/^([+\-−×]?\d[\d,.:]*\s*(?:%|s|x)?)\s+(.+)$/);
    if (m && LATIN.test(m[2])) { const t = lookup(m[2]) ?? nested(m[2]); if (t != null) return m[1] + ' ' + t; }
    m = key.match(/^(.+?)\s+([+\-−×]?\d[\d,.:]*\s*(?:%|s|x)?)$/);
    if (m && LATIN.test(m[1])) { const t = lookup(m[1]) ?? nested(m[1]); if (t != null) return t + ' ' + m[2]; }
    return null;
  }

  const SPLIT = /(\s+[·•|+\/→←–—=−-]\s+|,\s+|;\s+|:\s+|\s*\(\s*|\s*\)\s*|\s*\[\s*|\s*\]\s*|\s+vs\.?\s+)/;
  const MAJOR = /\s[·•|]\s/, MAJOR_SPLIT = /(\s+[·•|]\s+)/;
  function composite(key) {
    // List items first ("2 Ger at Far berries · 1 Wheelbarrow (Improved)"), so a name with a parenthesis stays whole.
    const items = key.split(MAJOR_SPLIT);
    if (items.length > 1) {
      let changed = false, prose = false;
      const out = items.map((part, i) => {
        if (i % 2 || !LATIN.test(part)) return part;
        const t = basic(part) ?? composite(part);
        if (t == null) { if (/[a-z]\.\s+[A-Z]|[.!?]$/.test(part) || part.split(' ').length >= 6) prose = true; return part; }
        changed = true; return t;
      });
      if (changed && !prose) return out.join('');
    }
    const parts = key.split(SPLIT);
    if (parts.length < 2) return null;
    // Untranslated pieces may stay English only when they look like names (player, build title).
    // Prose (a sentence, or six or more words) is left wholly English rather than half translated.
    let changed = false, prose = false;
    const out = parts.map((part, i) => {
      if (i % 2) return part === ' vs ' || part === ' vs. ' ? ' 对 ' : part;
      if (!LATIN.test(part)) return part;
      const t = basic(part);
      if (t == null) {
        if (/[a-z]\.\s+[A-Z]|[.!?]$/.test(part) || part.split(' ').length >= 6) prose = true;
        return part;
      }
      changed = true;
      return t;
    });
    return changed && !prose ? out.join('') : null;
  }

  function tr(text) {
    const key = norm(text);
    if (!key || !LATIN.test(key)) return null;
    if (cache.has(key)) return cache.get(key);
    const out = basic(key) ?? composite(key);
    cache.set(key, out);
    return out;
  }

  function wrap(original, translated) {
    const lead = original.match(/^\s*/)[0], trail = original.match(/\s*$/)[0];
    return lead + translated + trail;
  }

  const textState = new WeakMap(), attrState = new WeakMap();

  function setText(node, original, shown) {
    textState.set(node, { orig: original, shown });
    if (node.data !== shown) node.data = shown;
  }

  function englishOf(node) {
    const e = textState.get(node);
    return e && e.shown === node.data ? e.orig : node.data;
  }

  // Descriptions render as lines split by <br>; translate the whole block so line counts may differ.
  function block(parent) {
    const kids = [...parent.childNodes];
    if (!kids.every(n => n.nodeType === 3 || n.nodeName === 'BR')) return false;
    const texts = kids.filter(n => n.nodeType === 3), english = texts.map(englishOf);
    const t = tr(english.join(' '));
    if (t == null) return false;
    const lines = t.split('\n'), last = texts.length - 1;
    texts.forEach((n, i) => setText(n, english[i], i < last ? (lines[i] ?? '') : lines.slice(i).join('\n')));
    return true;
  }

  function text(node, nameOnly) {
    const cur = node.data, e = textState.get(node);
    if (e && cur === e.shown) return;
    if (!LATIN.test(cur)) { if (e) textState.delete(node); return; }
    let t;
    if (nameOnly) { const m = norm(cur).match(namePattern[0]); t = m ? namePattern[1].replace('$1', m[1]) : null; }
    else t = tr(cur);
    if (t != null) return setText(node, cur, wrap(cur, t));
    if (e) textState.delete(node);
    const p = node.parentNode;
    if (!nameOnly && p && p.nodeType === 1 && p.querySelector(':scope>br')) block(p);
  }

  // Custom dropdowns take their aria-label from the wrapping <label>'s whole text, which includes the
  // option texts. Translate just the label's own words instead.
  function selectLabel(el) {
    const select = el.closest('.custom-select').querySelector('select'), label = select && select.labels && select.labels[0];
    if (!label) return null;
    let s = '';
    const tw = document.createTreeWalker(label, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) if (!n.parentElement.closest('.custom-select,select')) s += ' ' + englishOf(n);
    return norm(s) || null;
  }

  function attrs(el) {
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v == null || !LATIN.test(v)) continue;
      let rec = attrState.get(el);
      if (rec && rec[a] && rec[a].shown === v) continue;
      let t = null, label = null;
      if (a === 'aria-label' && el.closest('.custom-select') && (el.classList.contains('select-trigger') || el.getAttribute('role') === 'listbox')) label = selectLabel(el);
      t = label ? tr(label) ?? (LATIN.test(label) ? null : label) : tr(v);
      if (t == null) { if (rec) delete rec[a]; continue; }
      if (!rec) attrState.set(el, rec = {});
      rec[a] = { orig: v, shown: t };
      el.setAttribute(a, t);
    }
  }

  const skipped = el => !!(el && el.closest && el.closest(SKIP));
  const named = el => !!(el && el.closest && el.closest(NAMES));

  // Text inside these stays as typed, but their placeholder/title/aria-label are still translated.
  const OPAQUE = 'textarea,input';
  const accept = n => {
    if (n.nodeType !== 1) return NodeFilter.FILTER_ACCEPT;
    if (n.matches(SKIP)) return NodeFilter.FILTER_REJECT;
    if (n.matches(OPAQUE)) { attrs(n); return NodeFilter.FILTER_REJECT; }
    return NodeFilter.FILTER_ACCEPT;
  };

  function walk(root) {
    if (root.nodeType === 3) { const p = root.parentElement; if (p && !skipped(p) && !p.matches(OPAQUE)) text(root, named(p)); return; }
    if (root.nodeType !== 1 || skipped(root)) return;
    if (root.matches(OPAQUE)) return attrs(root);
    attrs(root);
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, { acceptNode: accept });
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      if (n.nodeType === 3) text(n, named(n.parentElement));
      else attrs(n);
    }
  }

  function restore(root) {
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = root; n; n = tw.nextNode()) {
      if (n.nodeType === 3) {
        const e = textState.get(n);
        if (e) { if (n.data === e.shown) n.data = e.orig; textState.delete(n); }
      } else if (n.nodeType === 1) {
        const rec = attrState.get(n);
        if (rec) { for (const a in rec) if (n.getAttribute(a) === rec[a].shown) n.setAttribute(a, rec[a].orig); attrState.delete(n); }
      }
    }
  }

  const observer = new MutationObserver(records => {
    if (lang !== 'zh') return;
    for (const r of records) {
      if (r.type === 'childList') { for (const n of r.addedNodes) if (n.isConnected) walk(n); }
      else if (r.type === 'characterData') { const p = r.target.parentElement; if (p && r.target.isConnected && !skipped(p) && !p.matches(OPAQUE)) text(r.target, named(p)); }
      else if (r.target.isConnected && !skipped(r.target)) attrs(r.target);
    }
    observer.takeRecords();
  });

  function toggleLabel() {
    const b = document.getElementById('lang-toggle');
    if (!b) return;
    const zh = lang === 'zh';
    b.textContent = zh ? 'English' : '中文';
    b.lang = zh ? 'en' : 'zh-CN';
    b.setAttribute('aria-label', zh ? 'Switch to English' : '切换到简体中文');
  }

  function apply() {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    toggleLabel();
    if (lang === 'zh') { init(); walk(document.documentElement); }
  }

  function setLanguage(next) {
    next = next === 'zh' ? 'zh' : 'en';
    if (next === lang) return;
    lang = next;
    try { localStorage.setItem(KEY, next); } catch {}
    if (next === 'en') restore(document.documentElement);
    apply();
    observer.takeRecords();
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }

  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  apply();
  const button = document.getElementById('lang-toggle');
  if (button) button.addEventListener('click', () => setLanguage(lang === 'zh' ? 'en' : 'zh'));
  window.AoEI18n = { get lang() { return lang; }, setLanguage, translate: s => (lang === 'zh' ? (init(), tr(s)) : null) };
})();
