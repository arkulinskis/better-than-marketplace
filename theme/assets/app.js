/* core.js: the shared front-end engine (window.UI). Same in every app made from APP_MAKER/template;
   app-specific things live in web/app.js (brand, nav, footer) and web/pages/*.html (the pages).

   Pages:   UI.page(name, {title, nav, icon, auth, order, chrome}, mount)
              auth: null (anyone) | 'guest' (signed-out only) | 'user' | 'admin'
              nav: label for the header / phone tab bar (omit to keep it out of the menus)
              mount(view, ctx) draws into `view`; ctx = {args, me, go, api}. Return a Promise (the page
              is "ready" when it resolves) or {ready, destroy}. URLs are #name/arg1/arg2.
   Server:  UI.api(fn, ...args) -> Promise of the server function's return value. A reply of
              {ok: false, error} rejects with that message (shown as a toast unless you .catch it).
            UI.apiQuiet(fn, ...args) is the same without Anvil's loading spinner.
   Auth:    UI.auth('login'|'signup'|'reset'|'logout', {...}) -> Promise of {ok, me, message}
   Helpers: UI.esc, UI.icon, UI.toast, UI.modal, UI.confirm, UI.busy, UI.formData, UI.fmtDate, UI.ago,
            UI.store, UI.setTheme, UI.feedback, UI.go, UI.refresh
   Tests:   window.UI_READY is true when the current page has finished loading. */
(function () {
  'use strict';
  if (window.UI && window.UI.__v) return;
  var UI = window.UI = { __v: 1, pages: {}, me: null, config: { name: 'App', key: 'app', home: 'home', landing: 'landing' } };
  window.UI_READY = false;

  UI.configure = function (cfg) { Object.keys(cfg).forEach(function (k) { UI.config[k] = cfg[k]; }); };

  /* ------------------------------------------------------------------ small helpers */
  UI.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  UI.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  UI.initials = function (name) {
    var p = String(name || '?').trim().split(/\s+/);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
  };
  UI.fmtDate = function (iso, opts) {
    if (!iso) return '';
    var d = iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso);
    return d.toLocaleDateString(undefined, opts || { day: 'numeric', month: 'short', year: 'numeric' });
  };
  UI.fmtDateTime = function (iso) {
    return iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  };
  UI.ago = function (iso) {
    if (!iso) return '';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'just now';
    var steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month'], [Infinity, 'year']], n = s / 60;
    for (var i = 0; i < steps.length; i++) {
      if (n < steps[i][0]) { n = Math.floor(n); return UI.plural(n, steps[i][1]) + ' ago'; }
      n = n / steps[i][0];
    }
    return '';
  };
  UI.store = {
    get: function (k, dflt) { try { var v = localStorage.getItem(UI.config.key + '.' + k); return v == null ? dflt : JSON.parse(v); } catch (e) { return dflt; } },
    set: function (k, v) { try { localStorage.setItem(UI.config.key + '.' + k, JSON.stringify(v)); } catch (e) {} }
  };
  UI.formData = function (form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === 'checkbox') out[el.name] = el.checked;
      else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value;
    });
    return out;
  };
  /* Disable a button while a Promise runs; returns the Promise. */
  UI.busy = function (btn, promise) {
    if (!btn) return promise;
    btn.disabled = true; btn.classList.add('is-busy');
    var done = function () { btn.disabled = false; btn.classList.remove('is-busy'); };
    promise.then(done, done);
    return promise;
  };

  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.7c2.2.6 3.5 2.4 3.5 5.3"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M12 8V5M9 5.5 7.5 4M15 5.5 16.5 4M7 13H3M21 13h-4M7.5 18l-3 2M16.5 18l3 2M7.5 9.5l-3-2M16.5 9.5l3-2"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13"/><path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    pin: '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13.5" r="3.5"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    filter: '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"/>',
    more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'
  };
  UI.ICONS = ICONS;
  UI.icon = function (name, cls) {
    return '<svg class="ui-ic ' + (cls || '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || ICONS.sparkle) + '</svg>';
  };

  /* ------------------------------------------------------------------ toasts, modals */
  UI.toast = function (msg, kind) {
    var box = document.querySelector('.ui-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'ui ui-toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var t = document.createElement('div');
    t.className = 'ui-toast' + (kind ? ' ' + kind : '');
    t.innerHTML = (kind === 'error' ? UI.icon('info') : kind === 'ok' ? UI.icon('check') : '') + '<span>' + UI.esc(msg) + '</span>';
    box.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, kind === 'error' ? 6500 : 3200);
  };
  UI.modal = function (html, opts) {
    opts = opts || {};
    var prev = document.activeElement;
    var wrap = document.createElement('div');
    wrap.className = 'ui ui-modal-wrap';
    wrap.innerHTML = '<div class="ui-modal' + (opts.wide ? ' wide' : '') + '" role="dialog" aria-modal="true">' +
      '<button class="ui-btn ghost icon ui-modal-x" data-close aria-label="Close">' + UI.icon('x') + '</button>' + html + '</div>';
    document.body.appendChild(wrap);
    document.documentElement.classList.add('ui-modal-open');
    function key(e) { if (e.key === 'Escape') close(); }
    function close() {
      if (!wrap.parentNode) return;
      wrap.remove(); document.removeEventListener('keydown', key);
      if (!document.querySelector('.ui-modal-wrap')) document.documentElement.classList.remove('ui-modal-open');
      if (opts.onclose) opts.onclose();
      if (prev && prev.focus) prev.focus();
    }
    document.addEventListener('keydown', key);
    wrap.addEventListener('mousedown', function (e) { if (e.target === wrap) close(); });
    wrap.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) close(); });
    var first = wrap.querySelector('input, textarea, select');
    setTimeout(function () { (first || wrap.querySelector('.ui-modal')).focus && (first || wrap.querySelector('.ui-modal')).focus(); }, 30);
    return { el: wrap.querySelector('.ui-modal'), close: close };
  };
  UI.confirm = function (o) {
    o = typeof o === 'string' ? { title: o } : (o || {});
    return new Promise(function (resolve) {
      var answered = false;
      var m = UI.modal('<h2>' + UI.esc(o.title || 'Are you sure?') + '</h2>' + (o.text ? '<p class="muted">' + UI.esc(o.text) + '</p>' : '') +
        '<div class="ui-row end" style="margin-top:20px"><button class="ui-btn ghost" data-close>' + UI.esc(o.cancel || 'Cancel') + '</button>' +
        '<button class="ui-btn ' + (o.danger ? 'danger solid' : 'primary') + '" data-ok>' + UI.esc(o.ok || 'OK') + '</button></div>',
      { onclose: function () { if (!answered) resolve(false); } });
      m.el.querySelector('[data-ok]').onclick = function () { answered = true; m.close(); resolve(true); };
    });
  };

  /* ------------------------------------------------------------------ theme */
  UI.theme = function () { return UI.store.get('theme', 'auto'); };
  UI.applyTheme = function (t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
    var dark = t === 'dark' || (t !== 'light' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('ui-dark', !!dark);
  };
  UI.setTheme = function (t) { UI.store.set('theme', t); UI.applyTheme(t); };
  UI.applyTheme(UI.theme());
  if (window.matchMedia) {
    try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { UI.applyTheme(UI.theme()); }); } catch (e) {}
  }

  /* ------------------------------------------------------------------ server bridge */
  var bridge = null;
  function send(kind, payload) {
    if (!bridge) return Promise.reject(new Error('The app is still starting.'));
    var out;
    try { out = bridge(kind, JSON.stringify(payload || {})); } catch (e) { return Promise.reject(e); }
    return Promise.resolve(out).then(function (r) {
      r = typeof r === 'string' ? JSON.parse(r) : (r || {});
      if (r.error) {
        var err = new Error(r.error); err.uiApi = true; err.denied = !!r.denied;
        if (r.detail) console.error(kind, payload && payload.fn, r.detail);
        if (r.reload) setTimeout(function () { location.reload(); }, 2500);
        throw err;
      }
      return r.result;
    });
  }
  function apiCall(quiet, fn, args) {
    return send('call', { fn: fn, args: args, quiet: quiet }).then(function (res) {
      if (res && typeof res === 'object' && res.ok === false) {
        var err = new Error(res.error || 'That didn\'t work.'); err.uiApi = true; err.expected = true; err.result = res;
        throw err;
      }
      return res;
    });
  }
  UI.api = function (fn) { return apiCall(false, fn, Array.prototype.slice.call(arguments, 1)); };
  UI.apiQuiet = function (fn) { return apiCall(true, fn, Array.prototype.slice.call(arguments, 1)); };
  /* Errors nobody caught become a toast, so a failed action is never silent. */
  window.addEventListener('unhandledrejection', function (e) {
    if (e.reason && e.reason.uiApi) { e.preventDefault(); UI.toast(e.reason.message, 'error'); }
  });

  /* Sign in / up / out. On success it navigates: to where the visitor was heading (UI.after) or home
     after signing in, to the landing page after signing out. */
  UI.auth = function (kind, payload) {
    return send(kind, payload || {}).then(function (r) {
      if (r && r.ok === false) { var err = new Error(r.error); err.uiApi = true; err.expected = true; throw err; }
      if (r && 'me' in r && (r.me || kind === 'logout')) {
        UI.me = r.me || null;
        var target = r.me ? (UI.after || '#' + UI.config.home) : '#' + UI.config.landing;
        UI.after = null;
        if (location.hash === target) route(); else location.hash = target;
      }
      return r;
    });
  };
  /* Update the signed-in user's details (e.g. a new name) and redraw the header, without reloading the page. */
  UI.setMe = function (me) {
    UI.me = me || null;
    if (shellRoot) renderChrome(current.name);
  };

  /* ------------------------------------------------------------------ pages and routing */
  UI.page = function (name, opts, mount) {
    if (typeof opts === 'function') { mount = opts; opts = {}; }
    opts.name = name; opts.mount = mount;
    UI.pages[name] = opts;
  };
  UI.allowed = function (p) {
    if (!p) return false;
    if (p.auth === 'user') return !!UI.me;
    if (p.auth === 'admin') return !!(UI.me && UI.me.is_admin);
    if (p.auth === 'guest') return !UI.me;
    return true;
  };
  UI.navPages = function () {
    return Object.keys(UI.pages).map(function (k) { return UI.pages[k]; })
      .filter(function (p) { return p.nav && UI.allowed(p) && (!p.when || p.when()); })
      .sort(function (a, b) { return (a.order || 50) - (b.order || 50); });
  };
  UI.parseHash = function () {
    var h = (location.hash || '').replace(/^#!?\/?/, '');
    var parts = h.split('?')[0].split('/').filter(function (x) { return x !== ''; }).map(decodeURIComponent);
    return { name: parts[0] || '', args: parts.slice(1) };
  };
  UI.hashFor = function (name) {
    var args = Array.prototype.slice.call(arguments, 1).filter(function (a) { return a != null && a !== ''; });
    return '#' + [name].concat(args.map(encodeURIComponent)).join('/');
  };
  UI.go = function (name) {
    var h = UI.hashFor.apply(null, arguments);
    if (location.hash === h) route(); else location.hash = h;
  };
  UI.refresh = function () { route(); };
  UI.after = null;  // where to go after signing in

  var shellRoot = null, view = null, current = { name: null, destroy: null }, routeSeq = 0;

  function defaultPage() { return UI.me ? UI.config.home : UI.config.landing; }

  function route() {
    var r = UI.parseHash(), name = r.name || defaultPage(), p = UI.pages[name];
    if (!p) { name = defaultPage(); p = UI.pages[name]; r.args = []; }
    if (p.auth === 'guest' && UI.me) { p = UI.pages[UI.config.home]; name = UI.config.home; r.args = []; }
    if ((p.auth === 'user' || p.auth === 'admin') && !UI.me) {
      UI.after = location.hash && location.hash !== '#' ? location.hash : null;
      p = UI.pages.auth; name = 'auth'; r.args = [];
    }
    if (p.auth === 'admin' && !(UI.me && UI.me.is_admin)) {
      UI.toast('That page is for admins only.', 'error');
      p = UI.pages[UI.config.home]; name = UI.config.home; r.args = [];
    }
    var seq = ++routeSeq;
    window.UI_READY = false;
    if (current.destroy) { try { current.destroy(); } catch (e) { console.error(e); } }
    current = { name: name, args: r.args, destroy: null };
    if (shellRoot) {
      shellRoot.className = 'ui ui-shell page-' + name + (UI.me ? ' signed-in' : ' signed-out') + (p.chrome === false ? ' no-chrome' : '');
      renderChrome(name);
    }
    // A fresh element for every page, so listeners a page adds to `view` never pile up.
    var fresh = view.cloneNode(false);
    view.parentNode.replaceChild(fresh, view);
    view = fresh;
    window.scrollTo(0, 0);
    document.title = (p.title ? (typeof p.title === 'function' ? p.title(r.args) : p.title) + ' · ' : '') + UI.config.name;
    var ctx = { name: name, args: r.args, me: UI.me, go: UI.go, api: UI.api, page: p };
    var out;
    try { out = p.mount(view, ctx); } catch (e) { console.error(e); out = Promise.reject(e); }
    var ready = out && typeof out.then === 'function' ? out : (out && out.ready) || Promise.resolve();
    if (out && out.destroy) current.destroy = out.destroy;
    Promise.resolve(ready).then(function () { if (seq === routeSeq) window.UI_READY = true; },
      function (e) {
        if (seq !== routeSeq) return;
        console.error(e);
        if (!view.innerHTML) view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('info') +
          '<h3>This page didn\'t load</h3><p class="muted">' + UI.esc(e && e.message || 'Something went wrong.') + '</p>' +
          '<button class="ui-btn" onclick="UI.refresh()">Try again</button></div></div>';
        window.UI_READY = true;
      });
  }
  UI.current = function () { return current; };

  /* The shell's parts come from web/app.js: UI.shell = {header(me, active), footer(me), tabbar(me, active)} */
  function renderChrome(active) {
    var S = UI.shell || {};
    var hd = shellRoot.querySelector('[data-ui-header]'), ft = shellRoot.querySelector('[data-ui-footer]'), tb = shellRoot.querySelector('[data-ui-tabbar]');
    if (hd) hd.innerHTML = S.header ? S.header(UI.me, active) : '';
    if (ft) ft.innerHTML = S.footer ? S.footer(UI.me, active) : '';
    if (tb) tb.innerHTML = S.tabbar ? S.tabbar(UI.me, active) : '';
  }
  UI.renderChrome = function () { if (shellRoot) renderChrome(current.name); };

  /* Called by client_code/Main.py (and by the local harness) once the page is up. */
  UI.start = function (node, bridgeFn, bootJson) {
    bridge = bridgeFn;
    var boot = typeof bootJson === 'string' ? JSON.parse(bootJson || '{}') : (bootJson || {});
    UI.me = boot.me || null;
    var host = node && node.matches && node.matches('[data-ui-app]') ? node : (node && node.querySelector('[data-ui-app]')) || node || document.body;
    host.innerHTML = '<div class="ui ui-shell">' +
      '<header class="ui-header" data-ui-header></header>' +
      '<main class="ui-main" data-ui-view></main>' +
      '<footer class="ui-footer" data-ui-footer></footer>' +
      '<nav class="ui-tabbar" data-ui-tabbar aria-label="Main"></nav></div>';
    shellRoot = host.firstChild;
    view = host.querySelector('[data-ui-view]');
    if (UI.shell && UI.shell.wire) UI.shell.wire(shellRoot);
    window.addEventListener('hashchange', route);
    route();
  };

  /* ------------------------------------------------------------------ feedback form (footer + menu) */
  UI.feedback = function (kind) {
    var kinds = [['bug', 'Something\'s broken', 'bug'], ['idea', 'An idea', 'bulb'], ['question', 'A question', 'info'], ['other', 'Something else', 'chat']];
    var m = UI.modal('<h2>Send feedback</h2><p class="muted">Found a bug or have an idea? It goes straight to the people who make ' + UI.esc(UI.config.name) + '.</p>' +
      '<form class="ui-stack" data-fb>' +
      '<div class="ui-choices">' + kinds.map(function (k) {
        return '<label class="ui-choice"><input type="radio" name="kind" value="' + k[0] + '"' + ((kind || 'bug') === k[0] ? ' checked' : '') + '>' +
          '<span>' + UI.icon(k[2]) + UI.esc(k[1]) + '</span></label>';
      }).join('') + '</div>' +
      '<label class="ui-field"><span>What happened, or what would you like?</span><textarea name="message" rows="5" required minlength="5" placeholder="The more detail, the better."></textarea></label>' +
      (UI.me ? '' : '<label class="ui-field"><span>Your email <em>(optional, if you\'d like a reply)</em></span><input type="email" name="email" autocomplete="email"></label>') +
      '<p class="ui-hint">We also send the page you were on, your screen size and browser, to help us fix bugs.</p>' +
      '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('arrow') + 'Send</button></div></form>');
    var form = m.el.querySelector('[data-fb]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(form);
      var ctx = { page: location.hash || '#', screen: innerWidth + 'x' + innerHeight, browser: navigator.userAgent.slice(0, 280), theme: UI.theme() };
      UI.busy(form.querySelector('[type=submit]'), UI.api('submit_feedback', v.kind, v.message, v.email || null, ctx)).then(function () {
        m.close(); UI.toast('Thank you! Your message was sent.', 'ok');
      });
    });
    return m;
  };

  /* Shared clicks: [data-go="page/arg"], [data-feedback], [data-theme-set] anywhere in the app. */
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-go],[data-feedback],[data-theme-set]');
    if (!el) return;
    if (el.hasAttribute('data-go')) { e.preventDefault(); UI.go.apply(null, el.getAttribute('data-go').split('/')); }
    else if (el.hasAttribute('data-feedback')) { e.preventDefault(); UI.feedback(el.getAttribute('data-feedback') || null); }
    else if (el.hasAttribute('data-theme-set')) { e.preventDefault(); UI.setTheme(el.getAttribute('data-theme-set')); if (UI.shell && UI.shell.onTheme) UI.shell.onTheme(); }
  });
})();


/* app.js: this app's identity and frame: name, header, footer, phone tab bar, unread badge.
   Pages live in web/pages/*.html (shared marketplace helpers: web/pages/_shared.html). The engine (window.UI) is web/core.js. */
(function () {
  'use strict';
  UI.configure({
    name: 'Better Than Marketplace',
    key: 'betterthanmarketplace',     // prefix for this app's browser storage
    tagline: 'Snap it. Name it. Sold. Your neighbourhood garage sale, open all week.',
    home: 'browse',                    // first page after signing in
    landing: 'landing'                 // first page for visitors who aren't signed in
  });
  // Listing photos are served by the app's /photo endpoint. Main.py sets APP_API in Anvil; locally it's _/api.
  UI.apiBase = function () { return (window.APP_API || '_/api').replace(/\/$/, ''); };

  var esc = UI.esc;
  var unread = 0;

  function brand() {
    return '<a class="ui-brand" href="#" data-go="' + (UI.me ? UI.config.home : UI.config.landing) + '" aria-label="' + esc(UI.config.name) + ' home">' +
      '<img src="_/theme/icon.svg" alt="" width="34" height="34"><span class="bt-word">Better Than<b>Marketplace</b></span></a>';
  }

  function themeSwitch() {
    var t = UI.theme();
    return '<div class="ui-seg" role="group" aria-label="Appearance">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
      return '<button type="button" data-theme-set="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  function userMenu(me) {
    return '<div class="ui-menu" data-menu hidden>' +
      '<div class="ui-menu-head"><strong>' + esc(me.name) + '</strong><span class="muted small">' + esc(me.email) + '</span>' +
      (me.spot ? '<span class="small">' + UI.icon('pin') + ' ' + esc(me.spot.label) + '</span>' : '') + '</div>' +
      '<a href="#seller/' + esc(me.key) + '" data-go="seller/' + esc(me.key) + '">' + UI.icon('grid') + 'Your public page</a>' +
      '<a href="#profile" data-go="profile">' + UI.icon('user') + 'Your profile</a>' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<div class="ui-menu-block"><span class="small muted">Appearance</span>' + themeSwitch() + '</div>' +
      '<button type="button" data-feedback>' + UI.icon('chat') + 'Send feedback</button>' +
      '<button type="button" data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms</button>' +
      '<button type="button" data-signout>' + UI.icon('logout') + 'Sign out</button></div>';
  }

  function dot(p) {
    return p.name === 'messages' && unread ? '<span class="tb-dot" aria-label="' + unread + ' unread">' + (unread > 9 ? '9+' : unread) + '</span>' : '';
  }

  UI.shell = {
    header: function (me, active) {
      var nav = UI.navPages();
      return '<div class="ui-header-in">' + brand() +
        (me ? '<nav class="ui-nav" aria-label="Main">' + nav.map(function (p) {
          return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span>' + dot(p) + '</a>';
        }).join('') + '</nav>' : '') +
        '<div class="ui-header-right">' +
        (me ? '<button type="button" class="ui-avatar-btn" data-menu-toggle aria-label="Your account" aria-haspopup="true">' + esc(UI.initials(me.name)) + '</button>' + userMenu(me)
          : (active === 'auth' ? '' : (active !== 'browse' ? '<a class="ui-btn ghost bt-browse" href="#browse" data-go="browse">' + UI.icon('search') + '<span>Browse</span></a>' : '') +
              '<a class="ui-btn ghost" href="#auth" data-go="auth">Sign in</a><a class="ui-btn primary" href="#auth/signup" data-go="auth/signup">Join</a>')) +
        '</div></div>';
    },
    footer: function (me) {
      return '<div class="ui-footer-in"><div class="ui-footer-brand">' + brand() + '<p class="muted small">' + esc(UI.config.tagline) + '</p>' +
        '<p class="muted small">For people 18 and older. Meet in public, look before you pay.</p></div>' +
        '<div class="ui-footer-links">' +
        '<a href="#browse" data-go="browse">Browse</a>' +
        '<a href="#landing" data-go="landing">How it works</a>' +
        '<button type="button" data-feedback>Send feedback</button>' +
        '<button type="button" data-lk-open="overview">Privacy &amp; Terms</button>' +
        '</div><p class="ui-footer-legal small muted">© ' + new Date().getFullYear() + ' ' + esc(UI.config.name) + '</p></div>';
    },
    tabbar: function (me, active) {
      var nav = UI.navPages();
      if (!me || nav.length < 2) return '';
      return nav.slice(0, 4).map(function (p) {
        if (p.name === 'sell') {
          return '<a href="#sell" class="tb-sell' + (active === 'sell' ? ' on' : '') + '"><span class="tb-bubble">' + UI.icon('camera') + '</span><span>Sell</span></a>';
        }
        return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span>' + dot(p) + '</a>';
      }).join('') + '<a href="#profile" class="' + (active === 'profile' ? 'on' : '') + '">' + UI.icon('user') + '<span>You</span></a>';
    },
    wire: function (root) {
      root.addEventListener('click', function (e) {
        var t = e.target.closest('[data-menu-toggle]');
        var menu = root.querySelector('[data-menu]');
        if (t && menu) { menu.hidden = !menu.hidden; t.setAttribute('aria-expanded', String(!menu.hidden)); return; }
        if (e.target.closest('[data-signout]')) { UI.auth('logout').then(function () { UI.toast('Signed out. See you soon!'); }); }
        if (menu && !menu.hidden && !e.target.closest('[data-menu] .ui-seg')) menu.hidden = true;
      });
      document.addEventListener('keydown', function (e) {
        var menu = root.querySelector('[data-menu]');
        if (e.key === 'Escape' && menu) menu.hidden = true;
      });
      pollBadges();
    },
    onTheme: function () {  // redraw the menu's Auto/Light/Dark buttons and keep the menu open
      var menu = document.querySelector('[data-menu]'), open = menu && !menu.hidden;
      UI.renderChrome();
      if (open) document.querySelector('[data-menu]').hidden = false;
    }
  };

  /* Unread messages: a quiet check every 40 seconds while the tab is visible (and after each page change). */
  UI.setUnread = function (n) {
    n = n || 0;
    if (n === unread) return;
    unread = n;
    var menu = document.querySelector('[data-menu]'), open = menu && !menu.hidden;
    UI.renderChrome();
    if (open) document.querySelector('[data-menu]').hidden = false;
  };
  function checkBadges() {
    if (!UI.me || document.hidden) return;
    UI.apiQuiet('badges').then(function (b) { UI.setUnread(b.unread); }, function () {});
  }
  function pollBadges() {
    setTimeout(checkBadges, 600);
    setInterval(checkBadges, 40000);
    window.addEventListener('hashchange', function () { setTimeout(checkBadges, 900); });
    document.addEventListener('visibilitychange', checkBadges);
  }
})();


/* ===== _shared.html ===== */
(function () {
  'use strict';
  var esc = UI.esc;
  var BTM = window.BTM = {};
  var HOME = { lat: 45.5088, lng: -73.5878 };  // Montréal: where the map opens when we know nothing else

  /* ---------------------------------------------------------------- formatting */
  BTM.photo = function (key, thumb) {
    return key ? UI.apiBase() + '/photo?k=' + encodeURIComponent(key) + (thumb ? '&s=t' : '') : '';
  };
  BTM.money = function (n) {
    var whole = Math.round(n) === n;
    return '$' + Number(n).toLocaleString('en-CA', { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 });
  };
  BTM.price = function (it) {
    if (it.price_mode === 'free') return 'Free';
    if (it.price_mode === 'offer' || it.price == null) return 'Make an offer';
    return BTM.money(it.price);
  };
  BTM.tag = function (it, cls) {
    var mode = it.price_mode === 'free' ? 'free' : it.price_mode === 'offer' || it.price == null ? 'offer' : '';
    return '<span class="bt-tag ' + mode + ' ' + (cls || '') + '">' + esc(mode === 'offer' && cls !== 'big' ? 'Offer' : BTM.price(it)) + '</span>';
  };
  BTM.dist = function (d) {
    if (d == null) return '';
    if (d < 1) return 'under 1 km';
    return (d < 10 ? d.toFixed(1).replace(/\.0$/, '') : Math.round(d)) + ' km';
  };
  BTM.heartIcon = function () {
    return '<svg class="ui-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>';
  };

  BTM.card = function (it, opts) {
    opts = opts || {};
    var sold = it.status === 'sold';
    return '<article class="bt-card' + (sold ? ' is-sold' : '') + '" data-key="' + esc(it.key) + '">' +
      '<a class="bt-link" href="#item/' + esc(it.key) + '" data-go="item/' + esc(it.key) + '" aria-label="' + esc(it.title + ', ' + BTM.price(it)) + '"></a>' +
      '<div class="bt-ph">' + (it.cover ? '<img src="' + esc(BTM.photo(it.cover, true)) + '" alt="" loading="lazy" decoding="async">' : '') +
        (sold ? '<div class="bt-stamp"><span>SOLD</span></div>' : BTM.tag(it)) +
        (it.status === 'reserved' ? '<span class="bt-ribbon ui-badge ink">Reserved</span>' : it.hidden ? '<span class="bt-ribbon ui-badge bad">Hidden</span>' : '') +
        (it.photos > 1 && !sold ? '<span class="bt-count">' + UI.icon('image') + it.photos + '</span>' : '') +
        (opts.noHeart || it.mine || sold ? '' : '<button type="button" class="bt-heart' + (it.saved ? ' on' : '') + '" data-save="' + esc(it.key) + '" aria-pressed="' + !!it.saved + '" aria-label="Save">' + BTM.heartIcon() + '</button>') +
      '</div><div class="bt-body"><h3 class="bt-title">' + esc(it.title) + '</h3><div class="bt-meta">' +
        (it.dist != null ? '<span>' + UI.icon('pin') + esc(BTM.dist(it.dist)) + '</span>' : it.area ? '<span>' + UI.icon('pin') + esc(it.area) + '</span>' : '') +
        '<span>' + esc(sold && it.sold_at ? 'sold ' + UI.ago(it.sold_at) : UI.ago(it.posted)) + '</span>' +
        (it.mine ? '<span class="ui-badge accent">Yours</span>' : '') + (it.demo ? '<span class="ui-badge">Demo</span>' : '') +
      '</div></div></article>';
  };
  BTM.grid = function (items, opts) {
    return '<div class="bt-grid">' + items.map(function (it) { return BTM.card(it, opts); }).join('') + '</div>';
  };

  /* ---------------------------------------------------------------- the viewer's spot (for distances) */
  // Guests: kept in this browser only. Members: their selling spot, unless they picked another one here.
  BTM.where = function () {
    var w = UI.store.get('where', null);
    if (w && w.anywhere) return null;
    if (w && w.lat != null) return w;
    if (UI.me && UI.me.spot) return { lat: UI.me.spot.lat, lng: UI.me.spot.lng, label: UI.me.spot.label, mine: true };
    return null;
  };
  // w: a spot, 'anywhere' (no distances, even for members with a selling spot), or null (back to the default)
  BTM.setWhere = function (w) {
    UI.store.set('where', w === 'anywhere' ? { anywhere: true } : w && w.lat != null ? { lat: w.lat, lng: w.lng, label: w.label || 'Pinned spot' } : null);
  };
  BTM.opts = function (extra) {
    var w = BTM.where(), o = {};
    if (w) { o.lat = w.lat; o.lng = w.lng; o.label = w.label; }
    Object.keys(extra || {}).forEach(function (k) { o[k] = extra[k]; });
    return o;
  };

  /* ---------------------------------------------------------------- saving (hearts), anywhere */
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-save]');
    if (!b) return;
    e.preventDefault(); e.stopPropagation();
    if (!UI.me) {
      UI.after = location.hash;
      UI.toast('Join (it\'s free) to save things you like.');
      UI.go('auth', 'signup');
      return;
    }
    var key = b.getAttribute('data-save');
    UI.api('toggle_save', key).then(function (r) {
      document.querySelectorAll('[data-save="' + key + '"]').forEach(function (h) {
        h.classList.toggle('on', r.saved); h.setAttribute('aria-pressed', String(r.saved));
        h.classList.remove('pop'); void h.offsetWidth; if (r.saved) h.classList.add('pop');
        var label = h.querySelector('[data-save-label]');
        if (label) label.textContent = r.saved ? 'Saved' : 'Save';
      });
      UI.toast(r.saved ? 'Saved. Find it under My stuff.' : 'Removed from your saved items.', r.saved ? 'ok' : '');
    });
  }, true);

  /* ---------------------------------------------------------------- maps (Leaflet, loaded only when needed) */
  var leafletP = null;
  BTM.leaflet = function () {
    if (window.L && window.L.map) return Promise.resolve(window.L);
    if (leafletP) return leafletP;
    leafletP = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = function () { window.L ? resolve(window.L) : reject(new Error('no map')); };
      s.onerror = function () { leafletP = null; reject(new Error('The map couldn\'t load.')); };
      document.head.appendChild(s);
      setTimeout(function () { if (!window.L) { leafletP = null; reject(new Error('The map is taking too long to load.')); } }, 12000);
    });
    return leafletP;
  };
  /* OpenStreetMap's own tiles (light use, with the browser's normal Referer, as their tile policy asks).
     CARTO's free basemaps started answering "API key required" in Oct 2026. Dark mode inverts the tiles in CSS. */
  BTM.tiles = function (L, map) {
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
  };
  BTM.pinIcon = function (L) {
    return L.divIcon({ className: '', iconSize: [34, 42], iconAnchor: [17, 40],
      html: '<svg class="bt-pin" viewBox="0 0 34 42"><path d="M17 40s14-12.6 14-23A14 14 0 0 0 3 17c0 10.4 14 23 14 23z" fill="#ff5a36" stroke="#1e1a16" stroke-width="2.5"/>' +
        '<circle cx="17" cy="17" r="6" fill="#ffc93c" stroke="#1e1a16" stroke-width="2.5"/></svg>' });
  };
  /* Nominatim: only on a tap (search or pin), never while typing, as its usage policy asks. */
  function areaName(a) {
    if (!a) return '';
    var local = a.neighbourhood || a.suburb || a.quarter || a.city_district || a.borough || '';
    var town = a.city || a.town || a.village || a.municipality || a.county || '';
    return [local, town].filter(Boolean).filter(function (v, i, all) { return all.indexOf(v) === i; }).join(', ').slice(0, 60);
  }
  BTM.reverse = function (lat, lng) {
    return fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=15&addressdetails=1&lat=' + lat + '&lon=' + lng)
      .then(function (r) { return r.json(); }).then(function (j) { return areaName(j.address); }).catch(function () { return ''; });
  };
  BTM.search = function (text) {
    return fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=5&q=' + encodeURIComponent(text))
      .then(function (r) { return r.json(); });
  };

  /* The spot picker: a map with a pin, "use my location", a place search and the area name.
     Resolves {lat, lng, label}, {extra: name} for an extra button, or null when closed. */
  BTM.pickSpot = function (o) {
    o = o || {};
    return new Promise(function (resolve) {
      var done = false, pos = o.lat != null ? { lat: o.lat, lng: o.lng } : null, map = null, marker = null, L = null, autoLabel = !o.label;
      var m = UI.modal('<h2>' + esc(o.title || 'Where are you?') + '</h2>' + (o.text ? '<p class="muted">' + esc(o.text) + '</p>' : '') +
        '<div class="ui-row bt-spot-tools"><button type="button" class="ui-btn sm accent" data-locate>' + UI.icon('pin') + 'Use my location</button>' +
        '<form class="bt-spot-search" data-find><input type="search" name="q" placeholder="Or search a place" aria-label="Search a place">' +
        '<button class="ui-btn sm icon" type="submit" aria-label="Search">' + UI.icon('search') + '</button></form></div>' +
        '<div class="bt-spot-results" data-results hidden></div>' +
        '<div class="bt-map" data-map><div class="bt-map-msg">Loading the map…</div></div>' +
        '<p class="ui-hint">' + esc(o.hint || 'Tap the map to move the pin.') + '</p>' +
        '<label class="ui-field"><span>' + esc(o.labelTitle || 'Name of the area') + '</span><input type="text" name="label" maxlength="60" placeholder="e.g. Mile End, Montréal" value="' + esc(o.label || '') + '"></label>' +
        '<div data-err class="ui-error" hidden style="margin-top:12px"></div>' +
        '<div class="ui-row end" style="margin-top:16px">' + (o.extra || '') + '<button type="button" class="ui-btn ghost" data-close>Cancel</button>' +
        '<button type="button" class="ui-btn primary" data-ok>' + esc(o.ok || 'Save') + '</button></div>',
      { wide: true, onclose: function () { if (!done) resolve(null); } });
      var el = m.el, labelInput = el.querySelector('[name=label]');
      labelInput.addEventListener('input', function () { autoLabel = !labelInput.value.trim(); });
      function err(msg) { var b = el.querySelector('[data-err]'); b.textContent = msg || ''; b.hidden = !msg; }
      function setPos(p, zoom, lookUp) {
        pos = { lat: +p.lat, lng: +p.lng };
        err('');
        if (map) {
          if (!marker) marker = L.marker([pos.lat, pos.lng], { icon: BTM.pinIcon(L), draggable: true }).addTo(map)
            .on('dragend', function (ev) { var ll = ev.target.getLatLng(); setPos({ lat: ll.lat, lng: ll.lng }, null, true); });
          else marker.setLatLng([pos.lat, pos.lng]);
          if (zoom) map.setView([pos.lat, pos.lng], zoom);
        }
        if (lookUp && autoLabel) BTM.reverse(pos.lat, pos.lng).then(function (name) { if (name && autoLabel) labelInput.value = name; });
      }
      BTM.leaflet().then(function (LL) {
        L = LL;
        var box = el.querySelector('[data-map]');
        box.innerHTML = '';
        map = L.map(box, { scrollWheelZoom: true }).setView([pos ? pos.lat : HOME.lat, pos ? pos.lng : HOME.lng], pos ? 14 : 11);
        BTM.tiles(L, map);
        map.on('click', function (ev) { setPos(ev.latlng, null, true); });
        if (pos) setPos(pos);
        setTimeout(function () { map.invalidateSize(); }, 120);
      }, function (e) {
        el.querySelector('[data-map]').innerHTML = '<div class="bt-map-msg">' + esc(e.message) + ' Use your location or search a place instead.</div>';
      });
      el.addEventListener('click', function (e) {
        if (e.target.closest('[data-locate]')) {
          var b = e.target.closest('[data-locate]');
          if (!navigator.geolocation) { err('This browser can\'t share its location. Search a place instead.'); return; }
          UI.busy(b, new Promise(function (res) {
            navigator.geolocation.getCurrentPosition(function (p) {
              setPos({ lat: p.coords.latitude, lng: p.coords.longitude }, 14, true); res();
            }, function () { err('We couldn\'t get your location. Allow it in your browser, or search a place.'); res(); },
            { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 });
          }));
          return;
        }
        var r = e.target.closest('[data-pick]');
        if (r) {
          var it = JSON.parse(r.getAttribute('data-pick'));
          if (autoLabel || !labelInput.value.trim()) { labelInput.value = it.name; autoLabel = true; }
          setPos(it, 14, false);
          el.querySelector('[data-results]').hidden = true;
          return;
        }
        var x = e.target.closest('[data-extra]');
        if (x) { done = true; m.close(); resolve({ extra: x.getAttribute('data-extra') }); return; }
        if (e.target.closest('[data-ok]')) {
          var label = labelInput.value.trim();
          if (!pos) { err('Put a pin on the map first (tap the map, use your location, or search).'); return; }
          if (o.requireLabel !== false && label.length < 2) { err('Give the area a name, like a neighbourhood or a town.'); labelInput.focus(); return; }
          done = true; m.close(); resolve({ lat: pos.lat, lng: pos.lng, label: label || 'Pinned spot' });
        }
      });
      el.querySelector('[data-find]').addEventListener('submit', function (e) {
        e.preventDefault();
        var text = e.target.q.value.trim(), box = el.querySelector('[data-results]');
        if (text.length < 2) return;
        UI.busy(e.target.querySelector('button'), BTM.search(text).then(function (list) {
          box.hidden = false;
          box.innerHTML = list.length ? list.map(function (p) {
            var name = areaName(p.address) || (p.display_name || '').split(',').slice(0, 2).join(',');
            return '<button type="button" data-pick="' + esc(JSON.stringify({ lat: +p.lat, lng: +p.lon, name: name.slice(0, 60) })) + '">' + esc(p.display_name) + '</button>';
          }).join('') : '<p class="muted small" style="margin:0">No place found. Try another spelling, or tap the map.</p>';
        }, function () { box.hidden = false; box.innerHTML = '<p class="muted small" style="margin:0">Search isn\'t working right now. Tap the map instead.</p>'; }));
      });
    });
  };

  /* Set (or change) where the signed-in member sells from. Resolves the updated me, or null. */
  BTM.editSpot = function () {
    var s = UI.me && UI.me.spot;
    return BTM.pickSpot({ title: 'Where do you sell from?', ok: 'Save my spot',
      text: 'Buyers see the area name and how far away you are, never your address. Your items for sale move with you.',
      hint: 'Tap the map to move the pin. A street corner near you is plenty.',
      label: s && s.label, lat: s && s.lat, lng: s && s.lng
    }).then(function (p) {
      if (!p || p.extra) return null;
      return UI.api('set_spot', p.label, p.lat, p.lng).then(function (r) { UI.setMe(r.me); UI.toast('Saved: you sell from ' + r.me.spot.label + '.', 'ok'); return r.me; });
    });
  };

  /* ---------------------------------------------------------------- 18+ */
  BTM.ageOf = function (iso) {
    var d = new Date(iso + 'T12:00:00'), t = new Date();
    if (isNaN(d)) return null;
    var a = t.getFullYear() - d.getFullYear();
    if (t.getMonth() < d.getMonth() || (t.getMonth() === d.getMonth() && t.getDate() < d.getDate())) a--;
    return a;
  };
  BTM.maxBirthdate = function () { var t = new Date(); return (t.getFullYear() - 18) + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0'); };
  BTM.ageGate = function () {
    return new Promise(function (resolve) {
      var ok = false;
      var m = UI.modal('<h2>Quick check: are you 18 or older?</h2><p class="muted">Better Than Marketplace is for adults. We only keep that you confirmed it, not your birthday.</p>' +
        '<form class="ui-stack" data-age><label class="ui-field"><span>Date of birth</span><input type="date" name="birthdate" required max="' + BTM.maxBirthdate() + '"></label>' +
        '<div data-err class="ui-error" hidden></div><div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Not now</button>' +
        '<button class="ui-btn primary" type="submit">Confirm</button></div></form>', { onclose: function () { if (!ok) resolve(null); } });
      m.el.querySelector('[data-age]').addEventListener('submit', function (e) {
        e.preventDefault();
        var v = e.target.birthdate.value, box = m.el.querySelector('[data-err]'), age = BTM.ageOf(v);
        if (age == null) { box.textContent = 'Please enter your date of birth.'; box.hidden = false; return; }
        UI.busy(e.target.querySelector('[type=submit]'), UI.api('confirm_age', v)).then(function (r) {
          ok = true; UI.setMe(r.me); m.close(); resolve(r.me);
        }, function (err) {
          box.textContent = err.message; box.hidden = false;
          if (age < 18) { ok = true; setTimeout(function () { m.close(); location.hash = '#landing'; location.reload(); }, 2500); }
        });
      });
    });
  };

  /* ---------------------------------------------------------------- photos: shrink on the phone before uploading */
  function drawJpeg(img, max, quality) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height, s = Math.min(1, max / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
    var g = c.getContext('2d');
    g.fillStyle = '#ffffff'; g.fillRect(0, 0, c.width, c.height);
    g.imageSmoothingQuality = 'high';
    g.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', quality);
  }
  BTM.shrink = function (file) {
    return new Promise(function (resolve, reject) {
      if (!file || !/^image\//.test(file.type || 'image/')) { reject(new Error('That file isn\'t a picture.')); return; }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        try {
          var full = drawJpeg(img, 1600, 0.82), thumb = drawJpeg(img, 560, 0.74);
          URL.revokeObjectURL(url);
          resolve({ full: full, thumb: thumb });
        } catch (e) { reject(new Error('That picture couldn\'t be read.')); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('That picture couldn\'t be read. Try a JPEG or PNG.')); };
      img.src = url;
    });
  };

  /* ---------------------------------------------------------------- share, confetti, little art */
  BTM.share = function (it) {
    var url = location.href.split('#')[0] + '#item/' + it.key;
    var text = it.title + ' · ' + BTM.price(it) + ' on ' + UI.config.name;
    if (navigator.share) return navigator.share({ title: it.title, text: text, url: url }).catch(function () {});
    var done = function () { UI.toast('Link copied. Paste it anywhere.', 'ok'); };
    if (navigator.clipboard) return navigator.clipboard.writeText(url).then(done, function () { UI.modal('<h2>Share this item</h2><input type="text" readonly value="' + esc(url) + '">'); });
    UI.modal('<h2>Share this item</h2><input type="text" readonly value="' + esc(url) + '">');
  };
  BTM.confetti = function () {
    var box = document.createElement('div'), colors = ['#ff5a36', '#ffc93c', '#9be7b0', '#7fb7f0', '#ffffff'];
    box.className = 'bt-confetti';
    for (var i = 0; i < 70; i++) {
      var p = document.createElement('i');
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[i % colors.length];
      p.style.setProperty('--dx', (Math.random() * 160 - 80) + 'px');
      p.style.setProperty('--r', (Math.random() * 900 - 450) + 'deg');
      p.style.animationDuration = (1.6 + Math.random() * 1.6) + 's';
      p.style.animationDelay = Math.random() * 0.4 + 's';
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(function () { box.remove(); }, 4200);
  };
  /* An empty-state drawing: an empty price tag on a string. */
  BTM.emptyArt = function () {
    return '<svg class="bt-empty-art" viewBox="0 0 120 90" aria-hidden="true"><path d="M8 10 C30 30 40 34 52 40" fill="none" stroke="currentColor" stroke-width="2.5" stroke-dasharray="4 5"/>' +
      '<g transform="rotate(-14 80 50)"><path d="M60 30 H104 a6 6 0 0 1 6 6 V64 a6 6 0 0 1 -6 6 H60 L46 50 Z" fill="#ffc93c" stroke="#1e1a16" stroke-width="3" stroke-linejoin="round"/>' +
      '<circle cx="57" cy="50" r="4" fill="#fff7ec" stroke="#1e1a16" stroke-width="2.5"/><path d="M72 50 h28" stroke="#1e1a16" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 7"/></g></svg>';
  };
})();

/* ===== admin.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['overview', 'Overview', 'grid'], ['listings', 'Listings', 'image'], ['reports', 'Reports', 'shield'], ['feedback', 'Feedback', 'inbox'],
              ['users', 'Users', 'users'], ['demo', 'Demo data', 'database']];

  UI.page('admin', { title: 'Admin', auth: 'admin' }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'overview';
    var fbFilter = 'new', lsWhich = 'all', lsQuery = '', repStatus = 'open';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Admin</h1><p class="muted">Only admins see this page.</p></div></div>' +
      '<nav class="ui-tabs">' + TABS.map(function (t) {
        return '<a href="#admin/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</a>';
      }).join('') + '</nav><div data-body><div class="ui-skel"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function overview() {
      return UI.api('admin_overview').then(function (d) {
        var stat = function (n, label, go) { return '<a class="ui-card ui-stat" href="#admin/' + go + '" style="text-decoration:none;color:inherit"><b>' + n + '</b><span>' + label + '</span></a>'; };
        body.innerHTML = '<div class="ad-stats">' + stat(d.users, 'people signed up', 'users') + stat(d.listings, 'items for sale', 'listings') +
          stat(d.sold, 'sold', 'listings') + stat(d.chats, 'chats', 'overview') + stat(d.reports_open, 'open reports', 'reports') +
          stat(d.hidden, 'hidden items', 'listings') + stat(d.feedback_new, 'new feedback', 'feedback') + stat(d.admins, UI.plural(d.admins, 'admin').replace(/^\d+ /, ''), 'users') + '</div>' +
          '<p class="muted small" style="margin-top:18px">Demo data is <b>' + esc(d.demo.state) + '</b> (' + d.demo.counts.users + ' demo people). Manage it in the Demo data tab.</p>';
      });
    }

    function feedback() {
      return UI.api('list_feedback', null).then(function (d) {
        var items = d.items.filter(function (i) { return fbFilter === 'all' || i.status === fbFilter; });
        body.innerHTML = '<div class="ui-row" style="margin-bottom:16px"><div class="ui-seg">' + [['new', 'New'], ['read', 'Read'], ['done', 'Done'], ['all', 'All']].map(function (f) {
          var n = f[0] === 'all' ? d.items.length : d.counts[f[0]];
          return '<button data-filter="' + f[0] + '" class="' + (fbFilter === f[0] ? 'on' : '') + '">' + f[1] + ' (' + n + ')</button>';
        }).join('') + '</div></div>' +
          (items.length ? '<div class="ad-fb">' + items.map(function (i) {
            var c = i.context || {};
            return '<div class="ui-item" data-id="' + esc(i.id) + '"><div class="meta"><span class="ui-badge ' + (i.kind === 'bug' ? 'bad' : i.kind === 'idea' ? 'brand' : '') + '">' + esc(i.kind_label) + '</span>' +
              '<b>' + esc(i.name) + '</b>' + (i.email ? '<a href="mailto:' + esc(i.email) + '">' + esc(i.email) + '</a>' : '') + '<span>' + esc(UI.fmtDateTime(i.created)) + '</span></div>' +
              '<p class="msg">' + esc(i.message) + '</p>' +
              '<div class="ctx">' + esc([c.page, c.screen, c.theme, c.browser].filter(Boolean).join(' · ')) + '</div>' +
              '<textarea data-note placeholder="Private note (only admins see it)">' + esc(i.note) + '</textarea>' +
              '<div class="ui-row" style="margin-top:10px">' + ['new', 'read', 'done'].map(function (s) {
                return '<button class="ui-btn sm' + (i.status === s ? ' primary' : '') + '" data-status="' + s + '">' + s[0].toUpperCase() + s.slice(1) + '</button>';
              }).join('') + '<span class="ui-spacer"></span><button class="ui-btn sm danger" data-del-fb>' + UI.icon('trash') + 'Delete</button></div></div>';
          }).join('') + '</div>'
            : '<div class="ui-empty">' + UI.icon('inbox') + '<h3>No ' + (fbFilter === 'all' ? '' : fbFilter + ' ') + 'messages</h3><p>Messages from the "Send feedback" form show up here.</p></div>');
      });
    }

    function users(query) {
      return UI.api('list_users', query || null).then(function (d) {
        body.innerHTML = '<form class="ui-row" data-search style="margin-bottom:14px"><input type="search" name="q" placeholder="Search by name or email" value="' + esc(query || '') + '" style="max-width:360px">' +
          '<button class="ui-btn" type="submit">' + UI.icon('search') + 'Search</button><span class="muted small">' + UI.plural(d.total, 'person', 'people') + '</span></form>' +
          '<table class="ad-users"><thead><tr><th>Name</th><th>Email</th><th>Joined</th><th>Admin</th><th>Active</th></tr></thead><tbody>' +
          d.users.map(function (u) {
            return '<tr data-id="' + esc(u.id) + '"><td><b>' + esc(u.name) + '</b></td><td class="email">' + esc(u.email) + '</td><td class="joined muted">' + esc(UI.fmtDate(u.joined)) + '</td>' +
              '<td><label class="ui-check"><input type="checkbox" data-admin' + (u.is_admin ? ' checked' : '') + '> Admin</label></td>' +
              '<td><label class="ui-check"><input type="checkbox" data-enabled' + (u.enabled ? ' checked' : '') + '> Active</label></td></tr>';
          }).join('') + '</tbody></table>';
      });
    }

    function demo() {
      return UI.api('admin_overview').then(function (d) {
        var c = d.demo.counts;
        body.innerHTML = '<div class="ui-card ui-narrow" style="margin:0"><h3>Demo data</h3>' +
          '<p class="muted">Example people and content, so the app never looks empty for the first visitors. Demo rows are flagged, so removing them never touches real data. Once removed, it stays removed until you load it again.</p>' +
          '<p>Status: <b>' + esc(d.demo.state) + '</b> · ' + Object.keys(c).map(function (k) { return c[k] + ' ' + esc(k); }).join(', ') + '</p>' +
          '<div class="ui-row"><button class="ui-btn primary" data-demo="load">' + UI.icon('refresh') + (d.demo.state === 'loaded' ? 'Reload demo data' : 'Load demo data') + '</button>' +
          '<button class="ui-btn danger" data-demo="remove">' + UI.icon('trash') + 'Remove demo data</button></div></div>';
      });
    }

    function listingRow(it, acts) {
      return '<div class="ui-card ad-l" data-key="' + esc(it.key) + '"><a href="#item/' + esc(it.key) + '" data-go="item/' + esc(it.key) + '">' +
        (it.cover ? '<img src="' + esc(BTM.photo(it.cover, true)) + '" alt="">' : '<span class="ph"></span>') + '</a>' +
        '<div style="min-width:0"><h3><a href="#item/' + esc(it.key) + '" data-go="item/' + esc(it.key) + '">' + esc(it.title) + '</a></h3><div class="facts">' + BTM.tag(it, 'inline') +
        '<span>' + esc(it.status) + '</span><span><a href="#seller/' + esc(it.owner_key) + '" data-go="seller/' + esc(it.owner_key) + '">' + esc(it.owner) + '</a>' + (it.owner_email ? ' · ' + esc(it.owner_email) : '') + '</span>' +
        '<span>' + esc(it.area) + '</span><span>' + esc(UI.ago(it.posted)) + '</span><span>' + it.views + ' views</span>' +
        (it.reports ? '<span class="ui-badge bad">' + UI.plural(it.reports, 'report') + '</span>' : '') + (it.hidden ? '<span class="ui-badge bad">Hidden</span>' : '') +
        (it.demo ? '<span class="ui-badge">Demo</span>' : '') + '</div>' + (it.hidden && it.hidden_reason ? '<div class="why muted">' + esc(it.hidden_reason) + '</div>' : '') + '</div>' +
        '<div class="ad-acts">' + (acts || ((it.hidden ? '<button class="ui-btn sm" data-hide="0">Show again</button>' : '<button class="ui-btn sm" data-hide="1">Hide</button>') +
          '<button class="ui-btn sm danger" data-ldel>' + UI.icon('trash') + 'Delete</button>')) + '</div></div>';
    }

    function listings() {
      return UI.api('admin_listings', lsQuery || null, lsWhich).then(function (d) {
        body.innerHTML = '<div class="ui-row" style="margin-bottom:14px"><div class="ui-seg">' + [['all', 'All'], ['reported', 'Reported'], ['hidden', 'Hidden'], ['sold', 'Sold']].map(function (f) {
          return '<button data-which="' + f[0] + '" class="' + (lsWhich === f[0] ? 'on' : '') + '">' + f[1] + '</button>';
        }).join('') + '</div><form class="ui-row" data-lsearch style="flex:1"><input type="search" name="q" placeholder="Title, area or seller" value="' + esc(lsQuery) + '" style="max-width:300px">' +
          '<button class="ui-btn" type="submit">' + UI.icon('search') + 'Search</button><span class="muted small">' + UI.plural(d.total, 'listing') + '</span></form></div>' +
          (d.items.length ? '<div class="ad-ls">' + d.items.map(function (it) { return listingRow(it); }).join('') + '</div>'
            : '<div class="ui-empty">' + UI.icon('image') + '<h3>No listings here</h3></div>');
      });
    }

    function reports() {
      return UI.api('admin_reports', repStatus).then(function (d) {
        body.innerHTML = '<div class="ui-row" style="margin-bottom:14px"><div class="ui-seg">' + [['open', 'Open (' + d.open + ')'], ['done', 'Acted on'], ['dismissed', 'Dismissed']].map(function (f) {
          return '<button data-rstatus="' + f[0] + '" class="' + (repStatus === f[0] ? 'on' : '') + '">' + f[1] + '</button>';
        }).join('') + '</div><span class="muted small">Three open reports from different people hide an item until you look.</span></div>' +
          (d.reports.length ? '<div class="ad-ls">' + d.reports.map(function (r) {
            return '<div class="ui-card ad-rep" data-rid="' + esc(r.id) + '"><div class="ui-row"><span class="ui-badge bad">' + esc(r.reason) + '</span><b>' + esc(r.reporter) + '</b>' +
              '<span class="muted small">' + esc(UI.fmtDateTime(r.created)) + '</span></div>' + (r.details ? '<p style="margin:8px 0 0;white-space:pre-wrap">' + esc(r.details) + '</p>' : '') +
              (r.listing ? listingRow(r.listing, r.status === 'open' ? '<button class="ui-btn sm" data-resolve="dismiss">It\'s fine</button><button class="ui-btn sm" data-resolve="hide">Hide it</button>' +
                '<button class="ui-btn sm danger" data-resolve="delete">' + UI.icon('trash') + 'Delete it</button>' : ' ') : '<p class="muted">The item was deleted.</p>') + '</div>';
          }).join('') + '</div>' : '<div class="ui-empty">' + UI.icon('shield') + '<h3>No ' + (repStatus === 'open' ? 'open ' : '') + 'reports</h3><p>When members report an item, it shows up here.</p></div>');
      });
    }

    var DRAW = { overview: overview, listings: listings, reports: reports, feedback: feedback, users: users, demo: demo };

    view.addEventListener('click', function (e) {
      var lw = e.target.closest('[data-which]');
      if (lw) { lsWhich = lw.getAttribute('data-which'); listings(); return; }
      var rs = e.target.closest('[data-rstatus]');
      if (rs) { repStatus = rs.getAttribute('data-rstatus'); reports(); return; }
      var hd = e.target.closest('[data-hide]');
      if (hd) {
        var hk = hd.closest('[data-key]').getAttribute('data-key'), flag = hd.getAttribute('data-hide') === '1';
        UI.busy(hd, UI.api('admin_set_hidden', hk, flag, flag ? 'Hidden by a moderator.' : '')).then(function () { UI.toast(flag ? 'Hidden.' : 'Visible again.', 'ok'); listings(); });
        return;
      }
      var ld = e.target.closest('[data-ldel]');
      if (ld) {
        UI.confirm({ title: 'Delete this listing?', text: 'Its photos go too. This can\'t be undone.', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_listing', ld.closest('[data-key]').getAttribute('data-key')).then(function () { UI.toast('Deleted.'); listings(); });
        });
        return;
      }
      var rv = e.target.closest('[data-resolve]');
      if (rv) {
        var act = rv.getAttribute('data-resolve'), rid = rv.closest('[data-rid]').getAttribute('data-rid');
        var go = function () { UI.busy(rv, UI.api('admin_resolve_report', rid, act)).then(function () { UI.toast('Done.', 'ok'); reports(); }); };
        if (act === 'delete') UI.confirm({ title: 'Delete the item?', ok: 'Delete', danger: true }).then(function (yes) { if (yes) go(); }); else go();
        return;
      }
      var f = e.target.closest('[data-filter]');
      if (f) { fbFilter = f.getAttribute('data-filter'); feedback(); return; }
      var st = e.target.closest('[data-status]');
      if (st) {
        var card = st.closest('[data-id]');
        UI.api('set_feedback_status', card.getAttribute('data-id'), st.getAttribute('data-status'), card.querySelector('[data-note]').value).then(function () { UI.toast('Saved', 'ok'); feedback(); });
        return;
      }
      var del = e.target.closest('[data-del-fb]');
      if (del) {
        UI.confirm({ title: 'Delete this message?', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_feedback', del.closest('[data-id]').getAttribute('data-id')).then(feedback);
        });
        return;
      }
      var dm = e.target.closest('[data-demo]');
      if (dm) {
        var load = dm.getAttribute('data-demo') === 'load';
        UI.confirm({ title: load ? 'Load the demo data?' : 'Remove the demo data?', text: load ? 'Demo people and content are added (any old demo rows are replaced).' : 'Every demo row is deleted. Real data stays.', ok: load ? 'Load' : 'Remove', danger: !load })
          .then(function (yes) { if (yes) UI.busy(dm, UI.api(load ? 'demo_load' : 'demo_remove')).then(function () { UI.toast('Done', 'ok'); demo(); }); });
      }
    });
    view.addEventListener('change', function (e) {
      var row = e.target.closest('tr[data-id]');
      if (!row) return;
      var id = row.getAttribute('data-id'), box = e.target;
      var fn = box.hasAttribute('data-admin') ? 'set_admin' : box.hasAttribute('data-enabled') ? 'set_enabled' : null;
      if (fn) UI.api(fn, id, box.checked).then(function () { UI.toast('Saved', 'ok'); }, function (err) { box.checked = !box.checked; UI.toast(err.message, 'error'); });
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-search]')) { e.preventDefault(); users(UI.formData(e.target).q); }
      if (e.target.matches('[data-lsearch]')) { e.preventDefault(); lsQuery = UI.formData(e.target).q || ''; listings(); }
    });
    return DRAW[tab]();
  });
})();

/* ===== auth.html ===== */
(function () {
  var esc = UI.esc;
  function pw(name, auto) {
    return '<div class="au-pw"><input type="password" name="' + name + '" autocomplete="' + auto + '" required minlength="8">' +
      '<button type="button" data-show>Show</button></div>';
  }
  UI.page('auth', { title: 'Sign in', auth: 'guest' }, function (view, ctx) {
    var mode = ['signup', 'reset'].indexOf(ctx.args[0]) >= 0 ? ctx.args[0] : 'login';
    function draw(msg, isErr) {
      var heading = { login: 'Welcome back', signup: 'Create your account', reset: 'Reset your password' }[mode];
      var sub = { login: 'Sign in to continue to ' + esc(UI.config.name) + '.', signup: 'Free, takes a few seconds. For people 18 and older.',
        reset: 'We\'ll email you a link to choose a new password.' }[mode];
      view.innerHTML = '<div class="au-wrap"><div class="ui-card au-card">' +
        '<h1>' + heading + '</h1><p class="muted">' + sub + '</p>' +
        (mode !== 'reset' ? '<div class="ui-seg" role="tablist"><button type="button" data-mode="login" class="' + (mode === 'login' ? 'on' : '') + '">Sign in</button>' +
          '<button type="button" data-mode="signup" class="' + (mode === 'signup' ? 'on' : '') + '">Create account</button></div>' : '<div style="height:14px"></div>') +
        '<form class="ui-stack" data-form="' + mode + '" novalidate>' +
        (mode === 'signup' ? '<label class="ui-field"><span>Your name</span><input type="text" name="name" autocomplete="name" required maxlength="60"></label>' : '') +
        '<label class="ui-field"><span>Email</span><input type="email" name="email" autocomplete="email" required></label>' +
        (mode === 'login' ? '<label class="ui-field"><span>Password</span>' + pw('password', 'current-password') + '</label>' : '') +
        (mode === 'signup' ? '<label class="ui-field"><span>Password <em>(at least 8 characters)</em></span>' + pw('password', 'new-password') + '</label>' +
          '<label class="ui-field"><span>Date of birth</span><input type="date" name="birthdate" required max="' + BTM.maxBirthdate() + '" autocomplete="bday">' +
          '<span class="au-age">' + UI.icon('lock') + 'Only to check you\'re 18 or older. We don\'t keep it.</span></label>' +
          (window.LegalKit ? '<div>' + LegalKit.consentField() + '</div>' : '') : '') +
        '<div data-msg role="alert"' + (msg ? ' class="' + (isErr ? 'ui-error' : 'ui-note') + '">' + esc(msg) : ' hidden>') + '</div>' +
        '<button class="ui-btn primary block" type="submit">' + { login: 'Sign in', signup: 'Create account', reset: 'Send the link' }[mode] + '</button></form>' +
        '<div class="au-links">' + (mode === 'login' ? '<a data-mode="reset">Forgot your password?</a>' : '<a data-mode="login">' + UI.icon('back') + ' Back to sign in</a>') +
        '<a href="#landing" data-go="landing">About ' + esc(UI.config.name) + '</a></div></div></div>';
      var first = view.querySelector('input');
      if (first && !msg) first.focus();
    }
    view.addEventListener('click', function (e) {
      var m = e.target.closest('[data-mode]');
      if (m) { e.preventDefault(); mode = m.getAttribute('data-mode'); history.replaceState(null, '', '#auth' + (mode === 'login' ? '' : '/' + mode)); draw(); return; }
      var s = e.target.closest('[data-show]');
      if (s) { var i = s.parentNode.querySelector('input'); i.type = i.type === 'password' ? 'text' : 'password'; s.textContent = i.type === 'password' ? 'Show' : 'Hide'; }
    });
    view.addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target, v = UI.formData(form);
      var problem = !/^\S+@\S+\.\S+$/.test(v.email || '') ? 'Please enter a valid email address.'
        : mode !== 'reset' && (v.password || '').length < (mode === 'signup' ? 8 : 1) ? (mode === 'signup' ? 'Please choose a password of at least 8 characters.' : 'Please enter your password.')
        : mode === 'signup' && (v.name || '').trim().length < 2 ? 'Please tell us your name.'
        : mode === 'signup' && BTM.ageOf(v.birthdate) == null ? 'Please enter your date of birth.'
        : mode === 'signup' && BTM.ageOf(v.birthdate) < 18 ? 'Sorry, you need to be 18 or older to join Better Than Marketplace.' : null;
      if (problem) { say(problem, true); return; }
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;  // the kit shows its own message
      UI.busy(form.querySelector('[type=submit]'), UI.auth(mode, v)).then(function (r) {
        if (mode === 'reset' || (r && !r.me)) { mode = 'login'; draw(r && r.message, false); restore({ email: v.email }); }
        else UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    });
    function say(msg, isErr) {
      var box = view.querySelector('[data-msg]');
      box.className = isErr ? 'ui-error' : 'ui-note'; box.textContent = msg; box.hidden = false;
    }
    function restore(v) {
      ['name', 'email', 'birthdate'].forEach(function (k) { var i = view.querySelector('[name=' + k + ']'); if (i && v[k]) i.value = v[k]; });
    }
    draw();
  });
})();

/* ===== browse.html ===== */
(function () {
  var esc = UI.esc;
  var FILTERS = [['all', 'Everything'], ['free', 'Free'], ['under20', 'Under $20'], ['today', 'New today']];
  var RADII = [[1, '1 km'], [3, '3 km'], [5, '5 km'], [10, '10 km'], [25, '25 km'], [0, 'Any distance']];

  UI.page('browse', { title: 'Browse', nav: 'Browse', icon: 'search', order: 10 }, function (view, ctx) {
    var saved = UI.store.get('browse', null) || {};
    var st = { filter: saved.filter || 'all', sort: saved.sort || 'near', radius: saved.radius != null ? saved.radius : 10 };
    st.q = ctx.args[0] || '';
    var items = [], next = null, last = null;

    function shell() {
      var w = BTM.where();
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="br-head"><div><div class="eyebrow">' + (w ? 'Near ' + esc(w.label) : 'Fresh finds') + '</div>' +
        '<h1>' + (ctx.me ? 'What are your <em>neighbours</em> selling?' : 'Good stuff, <em>close by</em>') + '</h1></div>' +
        '<button type="button" class="bt-pill" data-where>' + UI.icon('pin') + '<span>' + (w ? esc(w.label) : 'Set your spot for distances') + '</span>' + UI.icon('chevron') + '</button></div>' +
        (ctx.me ? '' : '<div class="br-join"><p>Snap a photo, give it a name, and it\'s for sale. Join free to sell and message sellers (18+).</p>' +
          '<a class="ui-btn primary sm" href="#auth/signup" data-go="auth/signup">Join free</a></div>') +
        '<div class="br-bar"><form class="br-search" data-search role="search"><input type="search" name="q" placeholder="Search: lamp, bike, free books…" value="' + esc(st.q) + '" aria-label="Search">' +
        '<button class="ui-btn" type="submit">' + UI.icon('search') + '<span>Search</span></button></form></div>' +
        '<div class="br-chips" data-chips></div><div data-results><div class="bt-grid">' + [1, 2, 3, 4].map(function () { return '<div class="ui-skel" style="aspect-ratio:4/6"></div>'; }).join('') + '</div></div></div>';
    }
    function chips(d) {
      var w = BTM.where();
      view.querySelector('[data-chips]').innerHTML = FILTERS.map(function (f) {
        return '<button type="button" class="br-chip' + (st.filter === f[0] ? ' on' : '') + '" data-filter="' + f[0] + '">' + f[1] + '</button>';
      }).join('') +
        (w ? '<select data-radius aria-label="Distance">' + RADII.map(function (r) { return '<option value="' + r[0] + '"' + (+st.radius === r[0] ? ' selected' : '') + '>' + (r[0] ? 'Within ' + r[1] : r[1]) + '</option>'; }).join('') + '</select>' : '') +
        '<select data-sort aria-label="Sort">' + [['near', 'Nearest first'], ['new', 'Newest first'], ['cheap', 'Cheapest first']].filter(function (s) { return w || s[0] !== 'near'; })
          .map(function (s) { return '<option value="' + s[0] + '"' + (d && d.sort === s[0] ? ' selected' : '') + '>' + s[1] + '</option>'; }).join('') + '</select>' +
        (d ? '<span class="br-count">' + UI.plural(d.total, 'item') + '</span>' : '');
    }
    function results(append) {
      var box = view.querySelector('[data-results]');
      if (!items.length) {
        var w = BTM.where(), narrow = w && +st.radius && +st.radius < 25;
        box.innerHTML = '<div class="ui-empty">' + BTM.emptyArt() + '<h3>' + (st.q ? 'Nothing matches "' + esc(st.q) + '"' : 'Nothing here yet') + '</h3>' +
          '<p>' + (narrow ? 'Nothing within ' + st.radius + ' km. Try a wider area.' : st.filter !== 'all' ? 'Try another filter.' : 'Be the first to sell something around here.') + '</p>' +
          '<div class="ui-row" style="justify-content:center">' + (narrow ? '<button class="ui-btn" data-widen>Show within 25 km</button>' : '') +
          (st.q || st.filter !== 'all' ? '<button class="ui-btn" data-clear>Clear filters</button>' : '') +
          '<a class="ui-btn primary" href="#sell" data-go="sell">' + UI.icon('camera') + 'Sell something</a></div></div>';
        return;
      }
      if (append) {
        var grid = box.querySelector('.bt-grid');
        grid.insertAdjacentHTML('beforeend', append.map(function (it) { return BTM.card(it); }).join(''));
      } else box.innerHTML = BTM.grid(items);
      var more = box.querySelector('.br-more');
      if (more) more.remove();
      if (next != null) box.insertAdjacentHTML('beforeend', '<div class="br-more"><button class="ui-btn" data-more>Show more</button></div>');
    }
    function opts(offset) {
      return BTM.opts({ q: st.q, filter: st.filter, sort: st.sort, radius: BTM.where() ? +st.radius : 0, offset: offset || 0, limit: 24 });
    }
    function load() {
      UI.store.set('browse', { filter: st.filter, sort: st.sort, radius: st.radius });
      return UI.api('browse', opts()).then(function (d) {
        last = d; items = d.items; next = d.next;
        chips(d); results();
      });
    }

    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-filter]'))) { st.filter = t.getAttribute('data-filter'); load(); return; }
      if (e.target.closest('[data-widen]')) { st.radius = 25; load(); return; }
      if (e.target.closest('[data-clear]')) { st.q = ''; st.filter = 'all'; view.querySelector('[name=q]').value = ''; history.replaceState(null, '', '#browse'); load(); return; }
      if ((t = e.target.closest('[data-more]'))) {
        UI.busy(t, UI.api('browse', opts(next)).then(function (d) { items = items.concat(d.items); next = d.next; results(d.items); }));
        return;
      }
      if (e.target.closest('[data-where]')) {
        var w = BTM.where(), mine = UI.me && UI.me.spot;
        BTM.pickSpot({ title: 'Show me what\'s near…', ok: 'Show what\'s near here', requireLabel: false, labelTitle: 'Name of the area (optional)',
          text: 'We use this only in this browser, to sort by distance. It isn\'t saved with your account.',
          label: w && w.label, lat: w && w.lat, lng: w && w.lng,
          extra: (mine && !(w && w.mine) ? '<button type="button" class="ui-btn ghost" data-extra="mine">' + UI.icon('pin') + 'My selling spot</button>' : '') +
            (w ? '<button type="button" class="ui-btn ghost" data-extra="clear">Anywhere</button>' : '')
        }).then(function (p) {
          if (!p) return;
          if (p.extra === 'mine') BTM.setWhere(null);
          else if (p.extra === 'clear') { BTM.setWhere('anywhere'); st.sort = 'new'; }
          else { BTM.setWhere(p); st.sort = 'near'; }
          shell(); load();
        });
      }
    });
    view.addEventListener('change', function (e) {
      if (e.target.matches('[data-radius]')) { st.radius = +e.target.value; load(); }
      if (e.target.matches('[data-sort]')) { st.sort = e.target.value; load(); }
    });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-search]')) return;
      e.preventDefault();
      st.q = e.target.q.value.trim();
      history.replaceState(null, '', st.q ? '#browse/' + encodeURIComponent(st.q) : '#browse');
      load();
    });
    shell();
    return load();
  });
})();

/* ===== item.html ===== */
(function () {
  var esc = UI.esc;

  UI.page('item', { title: 'Item' }, function (view, ctx) {
    var key = ctx.args[0], it = null, map = null, idx = 0;

    function quick() {
      var q = ['Hi! Is this still available?', 'Could I pick it up today?', 'Where could we meet?'];
      if (it.price_mode === 'price' && it.price >= 10) q.splice(1, 0, 'Would you take ' + BTM.money(Math.max(1, Math.round(it.price * 0.8))) + '?');
      if (it.price_mode === 'offer') q.splice(1, 0, 'How much would you like for it?');
      return q;
    }

    function gallery() {
      var keys = it.photo_keys;
      return '<div class="it-gallery"><div class="it-strip" data-strip>' + keys.map(function (k, i) {
        return '<img src="' + esc(BTM.photo(k)) + '" alt="' + esc(it.title + ' (photo ' + (i + 1) + ')') + '" data-zoom="' + i + '"' + (i ? ' loading="lazy"' : '') + '>';
      }).join('') + '</div>' +
        (it.status === 'sold' ? '<div class="it-sold"><span>SOLD</span></div>' : '') +
        (keys.length > 1 ? '<div class="it-dots">' + keys.map(function (k, i) { return '<i class="' + (i ? '' : 'on') + '"></i>'; }).join('') + '</div>' +
          '<button class="ui-btn icon it-arrow l" data-step="-1" aria-label="Previous photo">' + UI.icon('back') + '</button>' +
          '<button class="ui-btn icon it-arrow r" data-step="1" aria-label="Next photo">' + UI.icon('arrow') + '</button>' : '') + '</div>' +
        (keys.length > 1 ? '<div class="it-thumbs">' + keys.map(function (k, i) {
          return '<button type="button" data-thumb="' + i + '" class="' + (i ? '' : 'on') + '" aria-label="Photo ' + (i + 1) + '"><img src="' + esc(BTM.photo(k, true)) + '" alt=""></button>';
        }).join('') + '</div>' : '');
    }

    function ownerBox() {
      return '<div class="ui-card it-owner"><h3>This is your item</h3>' +
        (it.hidden ? '<div class="ui-error" style="margin-bottom:12px">' + esc(it.hidden_reason || 'Hidden by a moderator.') + ' Only you can see it.</div>' : '') +
        '<div class="it-stats"><span><b>' + (it.views || 0) + '</b>' + (it.views === 1 ? 'view' : 'views') + '</span><span><b>' + (it.chats || 0) + '</b>' + (it.chats === 1 ? 'chat' : 'chats') + '</span></div>' +
        '<div class="ui-seg" role="group" aria-label="Status">' + [['active', 'For sale'], ['reserved', 'Reserved'], ['sold', 'Sold']].map(function (s) {
          return '<button type="button" data-status="' + s[0] + '" class="' + (it.status === s[0] ? 'on' : '') + '">' + s[1] + '</button>';
        }).join('') + '</div>' +
        '<div class="ui-row" style="margin-top:14px"><a class="ui-btn primary" href="#sell/' + esc(it.key) + '" data-go="sell/' + esc(it.key) + '">' + UI.icon('edit') + 'Edit</a>' +
        (it.status !== 'sold' ? '<button class="ui-btn" data-bump' + (it.can_bump ? '' : ' disabled title="Once a day"') + '>' + UI.icon('refresh') + 'Bump to top</button>' : '') +
        '<button class="ui-btn" data-share>' + UI.icon('external') + 'Share</button>' +
        '<button class="ui-btn danger" data-delete>' + UI.icon('trash') + 'Delete</button></div>' +
        (it.status !== 'sold' && !it.can_bump ? '<p class="ui-hint">You can bump an item back to the top once a day.</p>' : '') + '</div>';
    }

    function askBox() {
      if (it.status === 'sold') return '<div class="ui-card soft"><h3>This one found a new home</h3><p class="muted">It\'s sold. ' +
        '<a href="#seller/' + esc(it.seller.key) + '" data-go="seller/' + esc(it.seller.key) + '">See what else ' + esc(it.seller.name.split(' ')[0]) + ' is selling</a>.</p></div>';
      if (!ctx.me) return '<div class="ui-card it-ask"><h3>Interested?</h3><p class="muted">Join free to message ' + esc(it.seller.name.split(' ')[0]) + ' (you need to be 18 or older).</p>' +
        '<button class="ui-btn primary block" data-join>' + UI.icon('chat') + 'Join to message the seller</button>' +
        '<p class="ui-hint" style="text-align:center">Have an account? <a href="#auth" data-signin>Sign in</a></p></div>';
      return '<form class="ui-card it-ask" data-ask><h3>' + (it.chat ? 'Message ' : 'Ask ') + esc(it.seller.name.split(' ')[0]) + '</h3>' +
        (it.chat ? '<p class="small muted" style="margin-top:-4px">You already have a chat about this. <a href="#messages/' + esc(it.chat) + '" data-go="messages/' + esc(it.chat) + '">Open it</a></p>' : '') +
        '<div class="it-quick">' + quick().map(function (t) { return '<button type="button" data-q="' + esc(t) + '">' + esc(t) + '</button>'; }).join('') + '</div>' +
        '<textarea name="text" maxlength="1000" placeholder="Write a message…" aria-label="Message">' + (it.chat ? '' : 'Hi! Is this still available?') + '</textarea>' +
        '<button class="ui-btn primary block" type="submit" style="margin-top:10px">' + UI.icon('chat') + 'Send</button></form>';
    }

    function draw() {
      document.title = it.title + ' · ' + UI.config.name;
      var s = it.seller, first = s.name.split(' ')[0];
      view.innerHTML = '<div class="ui-wrap">' +
        '<button class="ui-btn ghost sm it-back" data-back>' + UI.icon('back') + 'Back</button>' +
        '<div class="it-grid"><div>' + gallery() + '</div>' +
        '<div class="it-info it-stack"><div>' +
          '<div class="ui-row">' + BTM.tag(it, 'big') + (it.status === 'reserved' ? '<span class="ui-badge ink">Reserved</span>' : '') + (it.demo ? '<span class="ui-badge">Demo</span>' : '') + '</div>' +
          '<h1>' + esc(it.title) + '</h1>' +
          '<div class="it-meta"><span>' + UI.icon('pin') + esc(it.area) + (it.dist != null ? ' · ' + esc(BTM.dist(it.dist)) + ' away' : '') + '</span>' +
          '<span>' + UI.icon('clock') + 'Posted ' + esc(UI.ago(it.posted)) + '</span></div>' +
          (it.can_edit ? '' : '<div class="it-actions">' + (it.status === 'sold' ? '' : '<button type="button" class="bt-heart' + (it.saved ? ' on' : '') + '" data-save="' + esc(it.key) + '" aria-pressed="' + !!it.saved + '">' + BTM.heartIcon() + '<span data-save-label>' + (it.saved ? 'Saved' : 'Save') + '</span></button>') +
            '<button class="ui-btn" data-share>' + UI.icon('external') + 'Share</button>' +
            (ctx.me ? '<button class="ui-btn ghost" data-report>' + UI.icon('info') + 'Report</button>' : '') + '</div>') +
        '</div>' +
        (it.can_edit ? ownerBox() : askBox()) +
        (it.note ? '<div class="ui-card soft"><h3>From ' + esc(it.can_edit ? 'you' : first) + '</h3><p class="it-note">' + esc(it.note) + '</p></div>' : '') +
        '<div class="ui-card soft"><a class="it-seller" href="#seller/' + esc(s.key) + '" data-go="seller/' + esc(s.key) + '"><span class="ui-avatar">' + esc(UI.initials(s.name)) + '</span>' +
          '<span style="flex:1;min-width:0"><b>' + esc(s.name) + '</b><span class="muted small">Member since ' + esc(UI.fmtDate(s.since, { month: 'long', year: 'numeric' })) + ' · ' +
          s.sold + ' sold · ' + s.active + ' for sale</span></span>' + UI.icon('arrow') + '</a>' +
          (it.map ? '<div class="bt-map it-map" data-map><div class="bt-map-msg">' + UI.icon('pin') + ' Around ' + esc(it.area) + '</div></div>' +
            '<p class="ui-hint">Roughly where ' + esc(it.can_edit ? 'you are' : first + ' is') + ': exact spots are never shown. Agree on a place to meet in the chat.</p>' : '') + '</div>' +
        (it.can_edit ? '' : '<div class="ui-card it-safe"><h3>' + UI.icon('shield') + ' Meet safely</h3><ul><li>Meet in a public place in daylight, or bring a friend.</li>' +
          '<li>Look at the item before you pay. Never pay in advance.</li><li>Keep the chat here: we never ask for your password or card.</li></ul></div>') +
        '</div></div>' +
        (it.more.length ? '<section class="bt-section"><h2>More from ' + esc(it.can_edit ? 'you' : first) + '</h2>' + BTM.grid(it.more) + '</section>' : '') + '</div>';
      wireStrip();
      if (it.map) drawMap();
    }

    function wireStrip() {
      var strip = view.querySelector('[data-strip]');
      if (!strip) return;
      strip.addEventListener('scroll', function () {
        var i = Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth));
        if (i === idx) return;
        idx = i;
        view.querySelectorAll('.it-dots i').forEach(function (d, j) { d.classList.toggle('on', j === i); });
        view.querySelectorAll('[data-thumb]').forEach(function (d, j) { d.classList.toggle('on', j === i); });
      }, { passive: true });
    }
    function show(i) {
      var strip = view.querySelector('[data-strip]'), n = it.photo_keys.length;
      i = (i + n) % n;
      strip.scrollTo({ left: i * strip.clientWidth, behavior: 'smooth' });
    }

    function drawMap() {
      BTM.leaflet().then(function (L) {
        var box = view.querySelector('[data-map]');
        if (!box || !document.body.contains(box)) return;
        box.innerHTML = '';
        map = L.map(box, { scrollWheelZoom: false, zoomControl: true, attributionControl: true }).setView([it.map.lat, it.map.lng], 13);
        BTM.tiles(L, map);
        L.circle([it.map.lat, it.map.lng], { radius: 900, color: '#ff5a36', weight: 3, fillColor: '#ffc93c', fillOpacity: 0.35 }).addTo(map);
      }, function () { /* the area name is already shown in the box */ });
    }

    function load() {
      return UI.api('get_listing', key, BTM.opts()).then(function (r) { it = r.item; draw(); }, function (err) {
        view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="ui-empty">' + BTM.emptyArt() + '<h3>' + esc(err.message) + '</h3>' +
          '<p>It may have been sold or taken down.</p><a class="ui-btn primary" href="#browse" data-go="browse">Browse what\'s for sale</a></div></div>';
      });
    }

    view.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-back]')) { if (history.length > 1) history.back(); else UI.go('browse'); return; }
      if ((t = e.target.closest('[data-step]'))) { show(idx + +t.getAttribute('data-step')); return; }
      if ((t = e.target.closest('[data-thumb]'))) { show(+t.getAttribute('data-thumb')); return; }
      if ((t = e.target.closest('[data-zoom]'))) {
        var light = document.createElement('div');
        light.className = 'ui it-light'; light.innerHTML = '<img src="' + esc(t.src) + '" alt="">';
        light.onclick = function () { light.remove(); };
        document.body.appendChild(light);
        return;
      }
      if ((t = e.target.closest('[data-q]'))) {
        var ta = view.querySelector('[data-ask] textarea');
        ta.value = t.getAttribute('data-q'); ta.focus();
        return;
      }
      if (e.target.closest('[data-join]')) { UI.after = '#item/' + key; UI.go('auth', 'signup'); return; }
      if (e.target.closest('[data-signin]')) { e.preventDefault(); UI.after = '#item/' + key; UI.go('auth'); return; }
      if (e.target.closest('[data-share]')) { BTM.share(it); return; }
      if (e.target.closest('[data-report]')) { report(); return; }
      if ((t = e.target.closest('[data-status]'))) {
        var st = t.getAttribute('data-status');
        if (st === it.status) return;
        UI.api('set_listing_status', key, st).then(function () {
          if (st === 'sold') { BTM.confetti(); UI.toast('Sold! Nice one.', 'ok'); } else UI.toast(st === 'reserved' ? 'Marked as reserved.' : 'Back on sale.', 'ok');
          return load();
        });
        return;
      }
      if ((t = e.target.closest('[data-bump]'))) { UI.busy(t, UI.api('bump_listing', key)).then(function () { UI.toast('Bumped to the top of the feed.', 'ok'); load(); }); return; }
      if (e.target.closest('[data-delete]')) {
        UI.confirm({ title: 'Delete "' + it.title + '"?', text: 'The photos are deleted too. Chats about it stay, with its name.', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_listing', key).then(function () { UI.toast('Deleted.'); UI.go(ctx.me ? 'mine' : 'browse'); });
        });
      }
    });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-ask]')) return;
      e.preventDefault();
      var text = e.target.text.value.trim();
      if (!text) { e.target.text.focus(); return; }
      var send = function () {
        return UI.busy(e.target.querySelector('[type=submit]'), UI.api('start_chat', key, text)).then(function (r) {
          UI.toast('Sent to ' + it.seller.name.split(' ')[0] + '.', 'ok'); UI.go('messages', r.chat);
        });
      };
      if (!ctx.me.adult) { BTM.ageGate().then(function (me) { if (me) { ctx.me = me; send(); } }); return; }
      send();
    });

    function report() {
      var reasons = [['prohibited', 'Not allowed here (weapons, drugs, animals…)'], ['scam', 'Scam or spam'], ['offensive', 'Offensive'], ['wrong', 'Misleading photos or info'], ['other', 'Something else']];
      var m = UI.modal('<h2>Report this item</h2><p class="muted">Our moderators take a look. The seller isn\'t told who reported it.</p>' +
        '<form class="ui-stack" data-rep><div class="ui-choices" style="grid-template-columns:1fr">' + reasons.map(function (r, i) {
          return '<label class="ui-choice"><input type="radio" name="reason" value="' + r[0] + '"' + (i ? '' : ' checked') + '><span>' + esc(r[1]) + '</span></label>';
        }).join('') + '</div><label class="ui-field"><span>Anything to add? <em>(optional)</em></span><textarea name="details" maxlength="600" rows="3"></textarea></label>' +
        '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn danger solid" type="submit">Send report</button></div></form>');
      m.el.querySelector('[data-rep]').addEventListener('submit', function (e) {
        e.preventDefault();
        var v = UI.formData(e.target);
        UI.busy(e.target.querySelector('[type=submit]'), UI.api('report_listing', key, v.reason, v.details)).then(function () { m.close(); UI.toast('Thanks. We\'ll take a look.', 'ok'); });
      });
    }

    view.innerHTML = '<div class="ui-wrap"><div class="it-grid"><div class="ui-skel" style="aspect-ratio:4/5"></div><div class="ui-skel" style="height:320px"></div></div></div>';
    return { ready: load(), destroy: function () { if (map) { try { map.remove(); } catch (e) {} } } };
  });
})();

/* ===== landing.html ===== */
(function () {
  var COPY = {
    eyebrow: 'Your neighbourhood garage sale, open all week',
    title: 'Snap it. Name it. <em>Sold.</em>',
    lead: 'Selling your stuff shouldn\'t take longer than using it did. Take a photo with your phone, give it a name, and it\'s up for your neighbours to see. No forms, no categories, no fees.',
    cta: 'Start selling, it\'s free',
    proof: ['Post in under 30 seconds', 'No fees, ever', 'Closest first', 'Adults only (18+)'],
    stepsTitle: 'Three taps from closet to cash',
    stepsLead: 'The only thing you have to type is a name.',
    steps: [['camera', 'Snap', 'Take a photo, or a few. Your phone shrinks them and uploads while you type.'],
            ['edit', 'Name it', 'Just a name. Add a price if you like, or pick Free or Make an offer. That\'s it.'],
            ['chat', 'Meet up', 'Neighbours message you here. Agree on a time, meet somewhere public, done.']],
    vs: [['Pick a category, a sub-category, a condition, a brand…', 'A photo and a name'],
         ['Sponsored listings and ads between everything', 'Just your neighbours\' stuff, closest first'],
         ['Your profile tied to a social network', 'A display name and an area. That\'s all anyone sees'],
         ['Fees and "boost your listing" upsells', 'Free. Bump your item to the top once a day, also free']],
    features: [['pin', 'Closest first', 'Everything is sorted by distance, so you can walk over and pick it up.'],
               ['camera', 'Photos first', 'Big pictures, little text. See it, want it, ask.'],
               ['chat', 'Chat built in', 'One-tap questions like "Is it still available?". Your email stays private.'],
               ['heart', 'Save the good stuff', 'Heart things to come back to them later.'],
               ['refresh', 'Bump, reserve, sold', 'One tap to bump to the top, hold it for a buyer, or mark it sold.'],
               ['shield', 'Adults only, moderated', 'Every member confirms they\'re 18+. Report anything off and a moderator looks.']],
    faq: [['Is it really free?', 'Yes. No listing fees, no commission, no ads. You and the buyer settle up in person, however you agree.'],
          ['Why do I need an account and a location to sell?', 'So buyers know who they\'re talking to and roughly how far away you are. They see your display name, your area\'s name and a distance, never your address or email.'],
          ['Why 18 and older?', 'Selling to strangers means meeting up and handling money, so accounts are for adults. We ask for your date of birth when you join and keep only the fact that you confirmed it.'],
          ['What can\'t I sell?', 'Weapons, drugs, alcohol, tobacco and vapes, medicines, animals, recalled or stolen goods, counterfeits and adult content. The Terms of Use have the full list.'],
          ['How do I stay safe?', 'Meet in a public place in daylight or bring a friend, look at the item before you pay, and never pay in advance. Report anything that feels off.'],
          ['Does it work on my phone?', 'It\'s made for your phone. Add it to your home screen and selling something is one tap away.']],
    bandTitle: 'Got a closet full of maybes?',
    bandLead: 'Turn them into someone\'s yes. It takes about 30 seconds.'
  };

  function chair() {
    var O = 'stroke="#1e1a16" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"';
    return '<svg viewBox="0 0 400 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="400" height="640" fill="#fde7c8"/>' +
      '<rect y="420" width="400" height="220" fill="#000" opacity=".06"/><ellipse cx="200" cy="424" rx="150" ry="14" fill="#000" opacity=".12"/>' +
      '<g transform="translate(0 20)"><rect x="112" y="150" width="176" height="180" rx="46" fill="#ffc93c" ' + O + '/><rect x="96" y="288" width="208" height="74" rx="26" fill="#f5ae1e" ' + O + '/>' +
      '<rect x="66" y="234" width="62" height="140" rx="30" fill="#ffc93c" ' + O + '/><rect x="272" y="234" width="62" height="140" rx="30" fill="#ffc93c" ' + O + '/>' +
      '<line x1="108" y1="374" x2="98" y2="404" stroke="#1e1a16" stroke-width="10" stroke-linecap="round"/><line x1="292" y1="374" x2="302" y2="404" stroke="#1e1a16" stroke-width="10" stroke-linecap="round"/></g></svg>';
  }
  function heroArt() {
    return '<div class="lp-art" aria-hidden="true"><div class="lp-phone"><div class="lp-screen">' + chair() +
      '<div class="lp-finder"></div><div class="lp-name">Yellow armchair<i></i></div><div class="lp-shutter"></div><div class="lp-flash"></div></div></div>' +
      '<div class="lp-sticker price">' + BTM.tag({ price: 85, price_mode: 'price' }) + '</div>' +
      '<div class="lp-sticker chat"><small>Ana · 2 min ago</small>Is it still available?</div>' +
      '<div class="lp-sticker near">' + UI.icon('pin') + '800 m away</div></div>';
  }

  UI.page('landing', { title: 'Snap it. Name it. Sold.' }, function (view, ctx) {
    var me = ctx.me, C = COPY, esc = UI.esc;
    var primary = me ? '<a class="ui-btn primary lg" href="#sell" data-go="sell">' + UI.icon('camera') + 'Sell something</a><a class="ui-btn lg" href="#browse" data-go="browse">Browse</a>'
      : '<a class="ui-btn primary lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + ' ' + UI.icon('arrow') + '</a>' +
        '<a class="ui-btn lg" href="#browse" data-go="browse">' + UI.icon('search') + 'See what\'s for sale</a>';
    view.innerHTML =
      '<section class="lp-hero"><div class="ui-wrap"><div>' +
        '<div class="eyebrow">' + esc(C.eyebrow) + '</div><h1>' + C.title + '</h1><p class="lp-lead">' + esc(C.lead) + '</p>' +
        '<div class="lp-cta">' + primary + '</div>' +
        '<div class="lp-proof">' + C.proof.map(function (p) { return '<span>' + UI.icon('check') + esc(p) + '</span>'; }).join('') + '</div>' +
      '</div>' + heroArt() + '</div></section>' +
      '<section class="lp-section" id="how"><div class="ui-wrap"><div class="lp-head"><h2>' + esc(C.stepsTitle) + '</h2><p>' + esc(C.stepsLead) + '</p></div>' +
        '<div class="lp-steps">' + C.steps.map(function (s) { return '<div class="ui-card lp-step"><span class="num">' + UI.icon(s[0]) + '</span><h3>' + esc(s[1]) + '</h3><p class="muted">' + esc(s[2]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section lp-strip"><div class="ui-wrap"><div class="lp-live-head"><div><div class="eyebrow" data-live-where>For sale right now</div><h2>Fresh on the curb</h2></div>' +
        '<a class="ui-btn" href="#browse" data-go="browse">See everything ' + UI.icon('arrow') + '</a></div><div data-live><div class="bt-grid">' +
        [1, 2, 3, 4].map(function () { return '<div class="ui-skel" style="aspect-ratio:4/6"></div>'; }).join('') + '</div></div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Why it\'s better</h2><p>Everything you don\'t need, left out.</p></div>' +
        '<div class="lp-vs"><div class="lp-vs-label"><span>The usual marketplace</span><span>Better Than Marketplace</span></div>' +
        C.vs.map(function (r) { return '<div class="lp-vs-row"><div class="old">' + UI.icon('x') + '<span>' + esc(r[0]) + '</span></div><div class="new">' + UI.icon('check') + '<span>' + esc(r[1]) + '</span></div></div>'; }).join('') +
        '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Made for both sides of the yard sale</h2></div>' +
        '<div class="ui-grid">' + C.features.map(function (f) { return '<div class="ui-card lp-feature">' + UI.icon(f[0]) + '<h3>' + esc(f[1]) + '</h3><p>' + esc(f[2]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Questions</h2></div><div class="lp-faq">' +
        C.faq.map(function (q) { return '<details><summary>' + esc(q[0]) + '</summary><p>' + esc(q[1]) + '</p></details>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-band"><div><h2>' + esc(C.bandTitle) + '</h2><p>' + esc(C.bandLead) + '</p></div>' +
        (me ? '<a class="ui-btn lg" href="#sell" data-go="sell">' + UI.icon('camera') + 'Sell something</a>' : '<a class="ui-btn lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + '</a>') +
      '</div></div></section>';
    return UI.api('browse', BTM.opts({ sort: BTM.where() ? 'near' : 'new', limit: 8 })).then(function (d) {
      var box = view.querySelector('[data-live]');
      if (d.origin) view.querySelector('[data-live-where]').textContent = 'For sale near ' + d.origin.label;
      box.innerHTML = d.items.length ? BTM.grid(d.items) : '<div class="ui-empty">' + BTM.emptyArt() + '<h3>The curb is empty</h3><p>Be the first to put something out.</p></div>';
    }, function () { view.querySelector('[data-live]').innerHTML = ''; });
  });
})();

/* ===== messages.html ===== */
(function () {
  var esc = UI.esc;

  UI.page('messages', { title: 'Chats', nav: 'Chats', icon: 'chat', auth: 'user', order: 30 }, function (view, ctx) {
    var key = ctx.args[0] || null, filter = UI.store.get('chatFilter', 'all'), chats = [], chat = null, msgs = [], timer = null, alive = true;

    function rowHtml(c) {
      return '<a class="ms-row' + (c.key === key ? ' on' : '') + (c.unread ? ' unread' : '') + '" href="#messages/' + esc(c.key) + '" data-go="messages/' + esc(c.key) + '">' +
        (c.cover ? '<img src="' + esc(BTM.photo(c.cover, true)) + '" alt="">' : '<span class="ph"></span>') +
        '<span class="grow"><b>' + esc(c.title) + '</b><span class="who">' + (c.role === 'buying' ? 'Buying from ' : 'Selling to ') + esc(c.other) + '</span>' +
        '<span class="last">' + (c.last_mine ? 'You: ' : '') + esc(c.last_text) + '</span></span>' +
        '<span class="when">' + esc(UI.ago(c.last_at).replace(' ago', '')) + '</span>' +
        (c.unread ? '<span class="dot">' + c.unread + '</span>' : '') + '</a>';
    }
    function sideHtml() {
      var list = chats.filter(function (c) { return filter === 'all' || c.role === filter; });
      var n = function (r) { return chats.filter(function (c) { return r === 'all' || c.role === r; }).length; };
      return '<div class="ui-seg" style="margin-bottom:12px">' + [['all', 'All'], ['buying', 'Buying'], ['selling', 'Selling']].map(function (f) {
        return '<button type="button" data-filter="' + f[0] + '" class="' + (filter === f[0] ? 'on' : '') + '">' + f[1] + ' (' + n(f[0]) + ')</button>';
      }).join('') + '</div>' +
        (list.length ? '<div class="ms-list">' + list.map(rowHtml).join('') + '</div>'
          : '<div class="ui-empty">' + BTM.emptyArt() + '<h3>No chats yet</h3><p>' + (filter === 'selling' ? 'When someone asks about your stuff, it shows up here.' :
            'Found something you like? Message the seller from its page.') + '</p><a class="ui-btn primary" href="#browse" data-go="browse">Browse</a></div>');
    }
    function dayOf(iso) { return new Date(iso).toDateString(); }
    function bubbles() {
      var out = [], lastDay = null;
      msgs.forEach(function (m) {
        var d = dayOf(m.at);
        if (d !== lastDay) { out.push('<div class="ms-day">' + esc(d === new Date().toDateString() ? 'Today' : UI.fmtDate(m.at, { weekday: 'short', day: 'numeric', month: 'short' })) + '</div>'); lastDay = d; }
        out.push('<div class="ms-b' + (m.mine ? ' mine' : '') + '">' + esc(m.text) + '<time>' + esc(new Date(m.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })) + '</time></div>');
      });
      if (chat.status === 'sold') out.push('<p class="ms-note">' + UI.icon('check') + ' This item is marked as sold.</p>');
      if (chat.status === 'gone') out.push('<p class="ms-note">The seller took this item down.</p>');
      return out.join('');
    }
    function quickReplies() {
      var q = chat.role === 'buying' ? ['Is it still available?', 'Could I pick it up today?', 'Where could we meet?', 'Thanks!']
        : ['Yes, it\'s still available!', 'When would suit you?', 'Sorry, it\'s reserved.', 'Thanks!'];
      return '<div class="ms-quick">' + q.map(function (t) { return '<button type="button" data-q="' + esc(t) + '">' + esc(t) + '</button>'; }).join('') + '</div>';
    }
    function threadHtml() {
      var c = chat;
      return '<div class="ms-thread"><div class="ms-top"><a class="ui-btn ghost icon" href="#messages" data-go="messages" aria-label="All chats">' + UI.icon('back') + '</a>' +
        (c.cover ? '<img src="' + esc(BTM.photo(c.cover, true)) + '" alt="">' : '') +
        '<div class="grow">' + (c.listing ? '<a class="title" href="#item/' + esc(c.listing) + '" data-go="item/' + esc(c.listing) + '">' + esc(c.title) + '</a>' : '<span class="title"><b>' + esc(c.title) + '</b></span>') +
        '<div class="sub">' + (c.role === 'buying' ? 'Buying from ' : 'Selling to ') + '<a href="#seller/' + esc(c.other_key) + '" data-go="seller/' + esc(c.other_key) + '">' + esc(c.other) + '</a></div></div>' +
        (c.status !== 'gone' ? BTM.tag(c, 'inline') : '') + '</div>' +
        '<div class="ms-body" data-body>' + bubbles() + '</div>' + quickReplies() +
        '<form class="ms-send" data-send><textarea name="text" maxlength="1000" placeholder="Message ' + esc(c.other.split(' ')[0]) + '…" aria-label="Message" rows="1"></textarea>' +
        '<button class="ui-btn primary icon" type="submit" aria-label="Send">' + UI.icon('arrow') + '</button></form></div>';
    }
    function draw() {
      var hasThread = !!chat;
      view.innerHTML = '<div class="ui-wrap ms-wrap' + (hasThread ? ' has-thread' : '') + '">' +
        (hasThread ? '' : '<div class="ui-page-head"><div><h1>Chats</h1><p class="muted">Questions about your stuff, and your questions to sellers.</p></div></div>') +
        '<div class="ms-grid' + (hasThread ? ' has-thread' : '') + (chats.length ? '' : ' single') + '"><div class="ms-side" data-side>' + sideHtml() + '</div>' +
        (chats.length ? '<div class="ms-pane">' + (hasThread ? threadHtml() : '<div class="ms-empty-pane"><div>' + UI.icon('chat') + '<p>Pick a chat on the left.</p></div></div>') + '</div>' : '') + '</div></div>';
      scrollDown();
    }
    function scrollDown() { var b = view.querySelector('[data-body]'); if (b) b.scrollTop = b.scrollHeight; }
    function appendNew(list) {
      var seen = {}; msgs.forEach(function (m) { seen[m.id] = 1; });
      var fresh = list.filter(function (m) { return !seen[m.id]; });
      if (!fresh.length) return;
      msgs = msgs.concat(fresh);
      var b = view.querySelector('[data-body]');
      if (b) { b.innerHTML = bubbles(); scrollDown(); }
    }
    function poll() {
      if (!alive || !chat || document.hidden) return;
      var after = msgs.length ? msgs[msgs.length - 1].at : null;
      UI.apiQuiet('poll_chat', key, after).then(function (r) { if (alive) appendNew(r.messages); }, function () {});
    }

    function load() {
      return UI.api('list_chats').then(function (d) {
        chats = d.chats;
        if (!key) { chat = null; draw(); return; }
        return UI.api('get_chat', key).then(function (r) {
          chat = r.chat; msgs = r.messages;
          chats.forEach(function (c) { if (c.key === key) c.unread = 0; });
          draw();
          timer = setInterval(poll, 4000);
          var unread = chats.reduce(function (n, c) { return n + (c.unread || 0); }, 0);
          if (UI.setUnread) UI.setUnread(unread);
          var ta = view.querySelector('[data-send] textarea');
          if (ta && matchMedia('(pointer: fine)').matches) ta.focus();
        }, function (e) { chat = null; draw(); UI.toast(e.message, 'error'); });
      });
    }

    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-filter]'))) { filter = t.getAttribute('data-filter'); UI.store.set('chatFilter', filter); view.querySelector('[data-side]').innerHTML = sideHtml(); return; }
      if ((t = e.target.closest('[data-q]'))) { var ta = view.querySelector('[data-send] textarea'); ta.value = t.getAttribute('data-q'); ta.focus(); }
    });
    view.addEventListener('keydown', function (e) {
      if (e.target.matches('[data-send] textarea') && e.key === 'Enter' && !e.shiftKey && matchMedia('(pointer: fine)').matches) {
        e.preventDefault(); e.target.form.requestSubmit ? e.target.form.requestSubmit() : e.target.form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      }
    });
    view.addEventListener('input', function (e) {
      if (e.target.matches('[data-send] textarea')) { e.target.style.height = 'auto'; e.target.style.height = Math.min(140, e.target.scrollHeight + 4) + 'px'; }
    });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-send]')) return;
      e.preventDefault();
      var ta = e.target.text, text = ta.value.trim();
      if (!text) return;
      var send = function () {
        return UI.busy(e.target.querySelector('[type=submit]'), UI.api('send_message', key, text)).then(function (r) {
          ta.value = ''; ta.style.height = '';
          appendNew([r.message]);
          chats.forEach(function (c) { if (c.key === key) { c.last_text = text; c.last_mine = true; c.last_at = r.message.at; } });
          ta.focus();
        });
      };
      if (!(UI.me && UI.me.adult)) { BTM.ageGate().then(function (m) { if (m) send(); }); return; }
      send();
    });

    view.innerHTML = '<div class="ui-wrap ms-wrap"><div class="ui-skel" style="height:360px"></div></div>';
    return { ready: load(), destroy: function () { alive = false; clearInterval(timer); } };
  });
})();

/* ===== mine.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['active', 'For sale'], ['reserved', 'Reserved'], ['sold', 'Sold'], ['saved', 'Saved']];

  UI.page('mine', { title: 'My stuff', nav: 'My stuff', icon: 'grid', auth: 'user', order: 40 }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'active';
    var data = null, saved = null;

    function row(it) {
      var acts = [];
      if (it.status === 'active') acts.push('<button class="ui-btn sm" data-set="reserved">Reserve</button>', '<button class="ui-btn sm accent" data-set="sold">' + UI.icon('check') + 'Sold</button>');
      if (it.status === 'reserved') acts.push('<button class="ui-btn sm" data-set="active">Back on sale</button>', '<button class="ui-btn sm accent" data-set="sold">' + UI.icon('check') + 'Sold</button>');
      if (it.status === 'sold') acts.push('<button class="ui-btn sm" data-set="active">Sell again</button>');
      if (it.status !== 'sold' && it.can_bump) acts.push('<button class="ui-btn sm" data-bump title="Back to the top of the feed">' + UI.icon('refresh') + 'Bump</button>');
      acts.push('<a class="ui-btn sm ghost icon" href="#sell/' + esc(it.key) + '" data-go="sell/' + esc(it.key) + '" aria-label="Edit">' + UI.icon('edit') + '</a>',
        '<button class="ui-btn sm ghost icon danger" data-del aria-label="Delete">' + UI.icon('trash') + '</button>');
      return '<div class="ui-card mn-row" data-key="' + esc(it.key) + '">' +
        '<a href="#item/' + esc(it.key) + '" data-go="item/' + esc(it.key) + '">' + (it.cover ? '<img src="' + esc(BTM.photo(it.cover, true)) + '" alt="">' : '<span class="ph"></span>') + '</a>' +
        '<div style="min-width:0"><h3><a href="#item/' + esc(it.key) + '" data-go="item/' + esc(it.key) + '">' + esc(it.title) + '</a></h3>' +
        '<div class="facts">' + BTM.tag(it, 'inline') + '<span>' + UI.icon('star') + it.views + ' views</span><span>' + UI.icon('chat') + UI.plural(it.chats, 'chat') + '</span>' +
        '<span>' + UI.icon('clock') + esc(it.status === 'sold' && it.sold_at ? 'sold ' + UI.ago(it.sold_at) : UI.ago(it.posted)) + '</span>' +
        (it.hidden_reason ? '<span class="ui-badge bad">Hidden</span>' : '') + '</div></div>' +
        '<div class="mn-acts">' + acts.join('') + '</div></div>';
    }

    function body() {
      if (tab === 'saved') {
        if (!saved) return '<div class="ui-skel" style="height:240px"></div>';
        return saved.length ? BTM.grid(saved) : '<div class="ui-empty">' + BTM.emptyArt() + '<h3>Nothing saved yet</h3><p>Tap the heart on anything you like to keep it here.</p>' +
          '<a class="ui-btn primary" href="#browse" data-go="browse">Browse</a></div>';
      }
      var list = data.lists[tab];
      if (list.length) return '<div class="mn-list">' + list.map(row).join('') + '</div>';
      return '<div class="ui-empty">' + BTM.emptyArt() + '<h3>' + { active: 'Nothing for sale right now', reserved: 'Nothing reserved', sold: 'Nothing sold yet' }[tab] + '</h3>' +
        '<p>' + { active: 'Got something you don\'t use? Snap it, name it, and it\'s up in seconds.', reserved: 'Mark an item as reserved while a buyer is on the way.',
          sold: 'Mark items as sold when they\'re gone: they stay on your page for a month as proof you\'re a good seller.' }[tab] + '</p>' +
        (tab === 'active' ? '<a class="ui-btn primary" href="#sell" data-go="sell">' + UI.icon('camera') + 'Sell something</a>' : '') + '</div>';
    }
    function draw() {
      var L = data.lists, counts = { active: L.active.length, reserved: L.reserved.length, sold: L.sold.length, saved: data.saved };
      view.innerHTML = '<div class="ui-wrap"><div class="mn-head"><div><div class="eyebrow">' + (data.spot ? 'Selling from ' + esc(data.spot.label) : 'No selling spot yet') + '</div><h1>Your stuff</h1></div>' +
        '<div class="ui-row"><a class="ui-btn" href="#seller/' + esc(UI.me.key) + '" data-go="seller/' + esc(UI.me.key) + '">' + UI.icon('user') + 'Your public page</a>' +
        '<a class="ui-btn primary" href="#sell" data-go="sell">' + UI.icon('camera') + 'Sell something</a></div></div>' +
        '<div class="mn-stats">' + TABS.map(function (t) {
          return '<a class="ui-card mn-stat' + (tab === t[0] ? ' on' : '') + '" href="#mine/' + t[0] + '" data-go="mine/' + t[0] + '"><b>' + counts[t[0]] + '</b><span>' + t[1] + '</span></a>';
        }).join('') + '</div><div data-body>' + body() + '</div></div>';
    }
    function load() {
      return UI.api('my_listings').then(function (d) {
        data = d; draw();
        if (tab === 'saved') return UI.api('my_saved', BTM.opts()).then(function (s) { saved = s.items; view.querySelector('[data-body]').innerHTML = body(); });
      });
    }

    view.addEventListener('click', function (e) {
      var t, r = e.target.closest('[data-key]'), key = r && r.getAttribute('data-key');
      if ((t = e.target.closest('[data-set]'))) {
        var st = t.getAttribute('data-set');
        UI.busy(t, UI.api('set_listing_status', key, st)).then(function () {
          if (st === 'sold') { BTM.confetti(); UI.toast('Sold! Nice one.', 'ok'); } else UI.toast(st === 'reserved' ? 'Marked as reserved.' : 'Back on sale.', 'ok');
          load();
        });
        return;
      }
      if ((t = e.target.closest('[data-bump]'))) { UI.busy(t, UI.api('bump_listing', key)).then(function () { UI.toast('Bumped to the top.', 'ok'); load(); }); return; }
      if (e.target.closest('[data-del]')) {
        UI.confirm({ title: 'Delete this item?', text: 'Its photos are deleted too. This can\'t be undone.', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_listing', key).then(function () { UI.toast('Deleted.'); load(); });
        });
      }
    });

    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:300px"></div></div>';
    return load();
  });
})();

/* ===== profile.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('profile', { title: 'Your profile', auth: 'user' }, function (view, ctx) {
    var me = UI.me || ctx.me;
    view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="pf-head"><span class="ui-avatar">' + esc(UI.initials(me.name)) + '</span>' +
      '<div><h1>' + esc(me.name) + '</h1><div class="muted">' + esc(me.email) + (me.joined ? ' · member since ' + esc(UI.fmtDate(me.joined, { month: 'long', year: 'numeric' })) : '') + '</div></div></div>' +
      '<div class="ui-card pf-spot" style="margin-bottom:16px"><div class="ui-row between"><div><h3 style="margin:0">' + UI.icon('pin') + ' Where you sell from</h3>' +
      '<p class="muted small" style="margin:4px 0 0">' + (me.spot ? 'Buyers see <b>' + esc(me.spot.label) + '</b> and how far away it is, never your address.' : 'Not set yet. You need it to sell.') + '</p></div>' +
      '<button class="ui-btn' + (me.spot ? '' : ' primary') + '" data-spot>' + (me.spot ? 'Change' : 'Set my spot') + '</button></div>' +
      '<div class="ui-row" style="margin-top:12px">' + (me.adult ? '<span class="ui-badge good">' + UI.icon('check') + '18+ confirmed</span>' : '<button class="ui-btn sm" data-age>Confirm I\'m 18 or older</button>') +
      '<a class="ui-btn sm ghost" href="#seller/' + esc(me.key) + '" data-go="seller/' + esc(me.key) + '">' + UI.icon('user') + 'Your public page</a>' +
      '<a class="ui-btn sm ghost" href="#mine" data-go="mine">' + UI.icon('grid') + 'Your stuff</a></div></div>' +
      '<div class="pf-grid"><form class="ui-card ui-stack" data-name><h3>Your name</h3><label class="ui-field"><span>Shown to other people</span>' +
      '<input type="text" name="name" value="' + esc(me.name) + '" maxlength="60" required></label><button class="ui-btn primary" type="submit">Save</button></form>' +
      '<div class="ui-card ui-stack"><h3>Appearance</h3><p class="muted small">Follow your device, or pick one.</p><div data-theme-box></div>' +
      '<h3 style="margin-top:22px">Password</h3><p class="muted small">We\'ll email you a link to choose a new one.</p>' +
      '<button class="ui-btn" data-reset>' + UI.icon('mail') + 'Email me a reset link</button></div></div>' +
      '<div class="ui-card" style="margin-top:16px"><div class="pf-links">' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<button data-feedback>' + UI.icon('chat') + 'Send feedback</button>' +
      '<button data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms, and your data</button>' +
      '<button data-signout-here>' + UI.icon('logout') + 'Sign out</button></div></div></div>';
    function themeBox() {
      var t = UI.theme();
      view.querySelector('[data-theme-box]').innerHTML = '<div class="ui-seg">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
        return '<button type="button" data-theme-pick="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
      }).join('') + '</div>';
    }
    themeBox();
    view.addEventListener('click', function (e) {
      var t = e.target.closest('[data-theme-pick]');
      if (t) { UI.setTheme(t.getAttribute('data-theme-pick')); themeBox(); UI.renderChrome(); return; }
      if (e.target.closest('[data-reset]')) {
        UI.busy(e.target.closest('[data-reset]'), UI.auth('reset', { email: me.email })).then(function (r) { UI.toast(r.message, 'ok'); });
      }
      if (e.target.closest('[data-signout-here]')) UI.auth('logout');
      if (e.target.closest('[data-spot]')) BTM.editSpot().then(function (m) { if (m) UI.refresh(); });
      if (e.target.closest('[data-age]')) BTM.ageGate().then(function (m) { if (m) UI.refresh(); });
    });
    view.querySelector('[data-name]').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(e.target);
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('update_profile', v.name)).then(function (r) {
        UI.setMe(r.me); ctx.me = r.me; UI.toast('Saved', 'ok');
        view.querySelector('.pf-head h1').textContent = r.me.name;
      });
    });
  });
})();

/* ===== sell.html ===== */
(function () {
  var esc = UI.esc;
  var MAX = 8;

  UI.page('sell', { title: 'Sell', nav: 'Sell', icon: 'camera', auth: 'user', order: 20 }, function (view, ctx) {
    var editKey = ctx.args[0] || null;
    var tiles = [];           // {id, key, src, state: 'up' | 'ok' | 'err', data}
    var form = { title: '', price_mode: 'price', price: '', note: '' };
    var queue = Promise.resolve(), seq = 0, posted = 0, alive = true;

    function me() { return UI.me || ctx.me; }

    /* ---------- before the first post: 18+ and the selling spot */
    function setup() {
      var m = me(), adult = !!m.adult, spot = !!m.spot;
      view.innerHTML = '<div class="ui-wrap sl-wrap"><div class="sl-head"><div><div class="eyebrow">Two quick things first</div><h1>Let\'s get you selling</h1></div></div>' +
        '<div class="sl-steps">' +
        '<div class="ui-card sl-step' + (adult ? ' done' : '') + '"><span class="num">' + (adult ? UI.icon('check') : '1') + '</span><div style="flex:1"><h3>You\'re 18 or older</h3>' +
          '<p class="muted">Better Than Marketplace is for adults.</p>' + (adult ? '<span class="ui-badge good">' + UI.icon('check') + 'Confirmed</span>' : '<button class="ui-btn primary" data-age>Confirm my age</button>') + '</div></div>' +
        '<div class="ui-card sl-step' + (spot ? ' done' : '') + '"><span class="num">' + (spot ? UI.icon('check') : '2') + '</span><div style="flex:1"><h3>Where you sell from</h3>' +
          '<p class="muted">Buyers see your area and how far away it is, never your address.</p>' +
          (spot ? '<span class="ui-badge good">' + UI.icon('pin') + esc(m.spot.label) + '</span>' : '<button class="ui-btn primary" data-spot' + (adult ? '' : ' disabled') + '>' + UI.icon('pin') + 'Set my spot</button>') + '</div></div>' +
        '</div></div>';
    }

    /* ---------- the form */
    function tileHtml(t, i) {
      return '<div class="sl-tile" data-tile="' + t.id + '"><img src="' + esc(t.src) + '" alt="Photo ' + (i + 1) + '" data-cover-pick title="' + (i ? 'Make this the cover photo' : 'Cover photo') + '">' +
        (i === 0 ? '<span class="sl-cover ui-badge accent">Cover</span>' : '') +
        '<button type="button" class="sl-x" data-remove aria-label="Remove photo">' + UI.icon('x') + '</button>' +
        (t.state === 'up' ? '<div class="sl-state"><span class="sl-ring"></span></div>' : t.state === 'err' ? '<div class="sl-state err" data-retry>Didn\'t upload.<br>Tap to retry</div>' : '') + '</div>';
    }
    function trayHtml() {
      if (!tiles.length) {
        return '<button type="button" class="sl-snap" data-cam><span class="sl-cam">' + UI.icon('camera') + '</span><b>Snap a photo</b>' +
          '<span class="muted">Point, shoot, done. Add up to ' + MAX + '.</span></button>' +
          '<div class="sl-or"><button type="button" data-lib>' + UI.icon('image') + ' or pick from your photos</button></div>';
      }
      return '<div class="sl-tray">' + tiles.map(tileHtml).join('') +
        (tiles.length < MAX ? '<button type="button" class="sl-add" data-cam>' + UI.icon('camera') + 'Add photo</button>' : '') + '</div>' +
        (tiles.length > 1 ? '<p class="ui-hint">Tap a photo to make it the cover.</p>' : '');
    }
    function drawTray() { var b = view.querySelector('[data-tray]'); if (b) b.innerHTML = trayHtml(); updatePost(); }

    function formHtml() {
      var m = me();
      return '<div class="ui-wrap sl-wrap"><div class="sl-head"><div><div class="eyebrow">' + (editKey ? 'Edit your item' : posted ? 'Next one!' : 'Snap it. Name it. Sold.') + '</div>' +
        '<h1>' + (editKey ? 'Edit item' : 'Sell something') + '</h1></div>' +
        '<div class="sl-spot">' + UI.icon('pin') + 'Selling from <b>' + esc(m.spot.label) + '</b><button type="button" data-spot>change</button></div></div>' +
        '<div data-tray>' + trayHtml() + '</div>' +
        '<form class="sl-form ui-stack" data-form novalidate>' +
        '<label class="ui-field sl-name"><span>What is it?</span><input type="text" name="title" maxlength="80" placeholder="e.g. Yellow armchair" value="' + esc(form.title) + '" autocomplete="off" enterkeyhint="done"></label>' +
        '<div class="ui-field"><span>Price</span><div class="sl-price-row"><div class="ui-seg" role="group" aria-label="Price type">' +
          [['price', 'Price'], ['free', 'Free'], ['offer', 'Make an offer']].map(function (p) {
            return '<button type="button" data-mode="' + p[0] + '" class="' + (form.price_mode === p[0] ? 'on' : '') + '">' + p[1] + '</button>';
          }).join('') + '</div>' +
          '<label class="sl-money"' + (form.price_mode === 'price' ? '' : ' hidden') + '><span>$</span><input type="number" name="price" inputmode="decimal" min="0" step="1" placeholder="0" value="' + esc(form.price) + '" aria-label="Price in dollars"></label></div>' +
          '<div class="sl-quick"' + (form.price_mode === 'price' ? '' : ' hidden') + '>' + [5, 10, 20, 40, 75, 100].map(function (n) { return '<button type="button" data-amount="' + n + '">$' + n + '</button>'; }).join('') + '</div></div>' +
        '<details class="sl-more"' + (form.note ? ' open' : '') + '><summary>' + UI.icon('plus') + 'Add a note (optional)</summary>' +
          '<textarea name="note" maxlength="1000" placeholder="Size, condition, pick-up times… only if you feel like it.">' + esc(form.note) + '</textarea></details>' +
        '<div data-err class="ui-error" hidden></div>' +
        '<div class="sl-post"><button class="ui-btn primary lg block" type="submit" data-post>' + UI.icon('check') + (editKey ? 'Save changes' : 'Post it') + '</button></div>' +
        (editKey ? '<p style="text-align:center"><a href="#item/' + esc(editKey) + '" data-go="item/' + esc(editKey) + '">Cancel</a></p>' : '') +
        '</form></div>' +
        '<input type="file" accept="image/*" capture="environment" data-cam-input hidden>' +
        '<input type="file" accept="image/*" multiple data-lib-input hidden>';
    }
    function drawForm() { view.innerHTML = formHtml(); updatePost(); }
    function grab() {
      var f = view.querySelector('[data-form]');
      if (!f) return;
      form.title = f.title.value; form.price = f.price.value; form.note = f.note.value;
    }
    function updatePost() {
      var b = view.querySelector('[data-post]');
      if (!b) return;
      var waiting = tiles.some(function (t) { return t.state === 'up'; });
      b.innerHTML = UI.icon(waiting ? 'clock' : 'check') + (waiting ? 'Uploading photos…' : editKey ? 'Save changes' : 'Post it');
    }
    function err(msg) { var b = view.querySelector('[data-err]'); if (b) { b.textContent = msg || ''; b.hidden = !msg; } }

    /* ---------- photos: shrink, show, upload one by one */
    function addFiles(files) {
      files = Array.prototype.slice.call(files || []).slice(0, MAX - tiles.length);
      if (!files.length) return;
      files.forEach(function (file) {
        var t = { id: 't' + (++seq), key: null, src: '', state: 'up', data: null };
        tiles.push(t);
        t.ready = BTM.shrink(file).then(function (d) {
          t.data = d; t.src = d.thumb;
          drawTray();
          return upload(t);
        }, function (e) {
          tiles = tiles.filter(function (x) { return x !== t; });
          drawTray(); UI.toast(e.message, 'error');
        });
      });
      drawTray();
      var name = view.querySelector('[name=title]');
      if (name && !name.value) setTimeout(function () { name.focus(); }, 300);
    }
    function upload(t) {
      t.state = 'up'; drawTray();
      queue = queue.then(function () {
        if (!alive || tiles.indexOf(t) < 0) return;
        return UI.apiQuiet('upload_photo', t.data.full, t.data.thumb).then(function (r) {
          t.key = r.key; t.state = 'ok'; t.data = { thumb: t.data.thumb };  // keep memory small
        }, function (e) { t.state = 'err'; UI.toast(e.message, 'error'); }).then(drawTray);
      });
      return queue;
    }

    /* ---------- post / save */
    function submit() {
      grab();
      err('');
      if (!tiles.length) { err('Add at least one photo: tap the camera.'); return; }
      if (form.title.trim().length < 2) { err('Give it a name, like "Blue armchair".'); view.querySelector('[name=title]').focus(); return; }
      if (form.price_mode === 'price' && form.price === '') { err('Type a price, or choose Free or Make an offer.'); view.querySelector('[name=price]').focus(); return; }
      var btn = view.querySelector('[data-post]');
      UI.busy(btn, Promise.all(tiles.map(function (t) { return t.ready; })).then(function () {
        var failed = tiles.filter(function (t) { return t.state === 'err'; });
        if (failed.length) throw Object.assign(new Error('Some photos didn\'t upload. Tap them to retry, or remove them.'), { uiApi: true, expected: true });
        var keys = tiles.map(function (t) { return t.key; });
        var price = form.price_mode === 'price' ? +form.price : null;
        return editKey ? UI.api('update_listing', editKey, form.title, form.price_mode, price, form.note, keys)
          : UI.api('create_listing', form.title, form.price_mode, price, form.note, keys);
      })).then(function (r) {
        if (editKey) { UI.toast('Saved.', 'ok'); UI.go('item', editKey); return; }
        posted++;
        done(r.key);
      }, function (e) { err(e.message); });
    }
    function done(key) {
      var first = tiles[0], it = { key: key, title: form.title.trim(), price: form.price_mode === 'price' ? +form.price : null, price_mode: form.price_mode,
        status: 'active', cover: null, photos: tiles.length, posted: new Date().toISOString(), area: me().spot.label, mine: true };
      var card = BTM.card(it, { noHeart: true }).replace('<div class="bt-ph">', '<div class="bt-ph"><img src="' + esc(first.src) + '" alt="">');
      view.innerHTML = '<div class="ui-wrap sl-wrap sl-done"><div class="eyebrow">' + (posted > 1 ? posted + ' items posted this round' : 'Posted') + '</div>' +
        '<h1>It\'s for sale!</h1><p class="muted">Neighbours near ' + esc(me().spot.label) + ' can see it now. Messages land in Chats.</p>' + card +
        '<div class="ui-row"><button class="ui-btn primary lg" data-next>' + UI.icon('camera') + 'Snap the next thing</button>' +
        '<a class="ui-btn lg" href="#item/' + esc(key) + '" data-go="item/' + esc(key) + '">See it</a></div>' +
        '<p style="margin-top:18px"><a href="#mine" data-go="mine">All your stuff</a></p></div>';
      BTM.confetti();
      tiles = []; form = { title: '', price_mode: form.price_mode === 'offer' ? 'offer' : 'price', price: '', note: '' };
    }

    /* ---------- events */
    view.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-age]')) { BTM.ageGate().then(function (m) { if (m) start(); }); return; }
      if (e.target.closest('[data-spot]')) { grab(); BTM.editSpot().then(function (m) { if (m) start(); }); return; }
      if (e.target.closest('[data-cam]')) { view.querySelector('[data-cam-input]').click(); return; }
      if (e.target.closest('[data-lib]')) { view.querySelector('[data-lib-input]').click(); return; }
      if (e.target.closest('[data-next]')) { drawForm(); setTimeout(function () { var c = view.querySelector('[data-cam-input]'); if (c && matchMedia('(pointer: coarse)').matches) c.click(); }, 50); return; }
      if ((t = e.target.closest('[data-remove]'))) {
        var id = t.closest('[data-tile]').getAttribute('data-tile');
        tiles = tiles.filter(function (x) { return x.id !== id; }); drawTray(); return;
      }
      if ((t = e.target.closest('[data-retry]'))) {
        var rt = tiles.filter(function (x) { return x.id === t.closest('[data-tile]').getAttribute('data-tile'); })[0];
        if (rt && rt.data && rt.data.full) rt.ready = upload(rt); else if (rt) { tiles.splice(tiles.indexOf(rt), 1); drawTray(); UI.toast('Please take that photo again.'); }
        return;
      }
      if ((t = e.target.closest('[data-cover-pick]'))) {
        var ct = tiles.filter(function (x) { return x.id === t.closest('[data-tile]').getAttribute('data-tile'); })[0];
        if (ct && tiles.indexOf(ct) > 0) { tiles.splice(tiles.indexOf(ct), 1); tiles.unshift(ct); drawTray(); }
        return;
      }
      if ((t = e.target.closest('[data-mode]'))) {
        grab(); form.price_mode = t.getAttribute('data-mode');
        view.querySelectorAll('[data-mode]').forEach(function (b) { b.classList.toggle('on', b === t); });
        view.querySelector('.sl-money').hidden = form.price_mode !== 'price';
        view.querySelector('.sl-quick').hidden = form.price_mode !== 'price';
        if (form.price_mode === 'price') view.querySelector('[name=price]').focus();
        return;
      }
      if ((t = e.target.closest('[data-amount]'))) { view.querySelector('[name=price]').value = t.getAttribute('data-amount'); return; }
    });
    view.addEventListener('change', function (e) {
      if (e.target.matches('[data-cam-input], [data-lib-input]')) { addFiles(e.target.files); e.target.value = ''; }
    });
    view.addEventListener('submit', function (e) { if (e.target.matches('[data-form]')) { e.preventDefault(); submit(); } });

    function start() {
      var m = me();
      if (!m.adult || !m.spot) { setup(); return Promise.resolve(); }
      if (!editKey) { drawForm(); return Promise.resolve(); }
      return UI.api('get_for_edit', editKey).then(function (r) {
        var it = r.item;
        form = { title: it.title, price_mode: it.price_mode || 'price', price: it.price != null ? String(it.price) : '', note: it.note };
        tiles = it.photo_keys.map(function (k) { return { id: 't' + (++seq), key: k, src: BTM.photo(k, true), state: 'ok', data: null }; });
        drawForm();
      }, function (e) {
        view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="ui-empty"><h3>' + esc(e.message) + '</h3><a class="ui-btn" href="#mine" data-go="mine">Your stuff</a></div></div>';
      });
    }
    return { ready: start(), destroy: function () { alive = false; } };
  });
})();

/* ===== seller.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('seller', { title: 'Seller' }, function (view, ctx) {
    var key = ctx.args[0];
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:160px"></div></div>';
    return UI.api('seller_page', key, BTM.opts()).then(function (d) {
      var s = d.seller, first = s.name.split(' ')[0];
      document.title = s.name + ' · ' + UI.config.name;
      view.innerHTML = '<div class="ui-wrap"><div class="ui-card sp-head"><span class="ui-avatar">' + esc(UI.initials(s.name)) + '</span>' +
        '<div style="flex:1;min-width:0"><h1>' + esc(s.name) + '</h1>' +
        '<div class="sp-facts">' + (s.area ? '<span class="ui-badge">' + UI.icon('pin') + esc(s.area) + '</span>' : '') +
        '<span class="ui-badge">' + UI.icon('calendar') + 'Member since ' + esc(UI.fmtDate(s.since, { month: 'long', year: 'numeric' })) + '</span>' +
        '<span class="ui-badge">' + UI.icon('check') + s.sold + ' sold</span><span class="ui-badge">' + UI.icon('grid') + s.active + ' for sale</span>' +
        (s.demo ? '<span class="ui-badge">Demo seller</span>' : '') + '</div></div>' +
        (d.mine ? '<div class="ui-row"><span class="muted small">This is how others see your page.</span><a class="ui-btn primary" href="#sell" data-go="sell">' + UI.icon('camera') + 'Sell something</a></div>' : '') + '</div>' +
        '<section class="bt-section"><h2>' + (d.mine ? 'You\'re selling' : first + ' is selling') + '</h2>' +
        (d.items.length ? BTM.grid(d.items) : '<div class="ui-empty">' + BTM.emptyArt() + '<h3>Nothing for sale right now</h3><p>' +
          (d.mine ? 'Snap something you don\'t need any more.' : 'Check back soon.') + '</p></div>') + '</section>' +
        (d.sold.length ? '<section class="bt-section"><h2>Sold lately</h2>' + BTM.grid(d.sold) + '</section>' : '') + '</div>';
    }, function (e) {
      view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="ui-empty">' + BTM.emptyArt() + '<h3>' + esc(e.message) + '</h3><a class="ui-btn primary" href="#browse" data-go="browse">Browse</a></div></div>';
    });
  });
})();
