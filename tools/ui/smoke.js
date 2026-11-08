/* Smoke test: every page address opens without an error and isn't empty, signed out, as a new member and as the
   admin; the spot picker and report dialogs open and close; a member asks a seller (start_chat -> the thread).
   ui_test.py fails the run on any Python/JS exception it sees.
   python -I tools/ui_test.py --only smoke.js. Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const shown = (el) => el && el.getClientRects().length > 0;
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  async function visit(hash) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash, hash, 40000);
    await sleep(500);
    const n = (($('.ui-main') || document.body).innerText || '').trim().length;
    if (n < 40) bad.push(hash + ' is empty');
    log.push((n < 40 ? 'EMPTY ' : 'ok   ') + hash + ' (' + n + ' chars)');
  }
  const button = (sel, re) => $$(sel + ' button').find((b) => re.test(b.textContent) && shown(b));
  const inputs = () => $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter(shown);
  async function signOut() {
    $('.anvil-role-avatar button').click();
    await sleep(300);
    $$('.ui-menu button').find((b) => /Sign out/.test(b.textContent)).click();
    await until(() => location.hash === '#landing' && window.UI_READY, 'signed out');
  }
  async function dialog(open, what) {
    open();
    const box = await until(() => $('.anvil-modal-content .dlg-host'), what + ' dialog');
    await sleep(800);
    $$('.anvil-modal-content button').find((b) => /^(Cancel|Not now)$/.test(b.textContent.trim())).click();
    await until(() => !$('.anvil-modal-content .dlg-host'), what + ' closed');
    log.push('ok   ' + what + ' dialog opens and closes');
    return box;
  }
  async function signUp(name, email, pw) {
    await visit('#auth/signup');
    const i = inputs();
    type(i[0], name); type(i[1], email); type(i[2], pw);
    type($$('.au-card input[type=date]').find(shown), '1990-05-17');
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    button('.au-card .anvil-role-btn-block', /Create account/).click();
  }
  try {
    // ---- visitors
    for (const h of ['#landing', '#browse', '#browse/chair', '#auth', '#auth/signup', '#auth/reset', '#item/no-such-item', '#seller/nobody']) await visit(h);
    await visit('#browse');
    const item = (await until(() => $('a.bt-link[href^="#item/"]'), 'a listing card')).getAttribute('href');
    await visit(item);
    const seller = $('a.it-seller').getAttribute('href');
    await visit(seller);
    await visit('#browse');
    await dialog(() => button('.br-head', /./).click(), 'spot picker');

    // ---- a new member (18+ from the date of birth)
    await signUp('Smoke Tester', 'smoke' + Date.now() + '@example.com', 'Hb-' + Math.random().toString(36).slice(2) + '-Kq7');
    await until(() => location.hash === '#browse' && window.UI_READY, 'signed up', 60000);
    for (const h of ['#browse', '#sell', '#sell/not-mine', '#messages', '#mine', '#mine/reserved', '#mine/sold', '#mine/saved', '#profile', '#landing', seller]) await visit(h);
    await visit(item);
    await dialog(() => button('.it-actions', /Report/).click(), 'report');
    button('.it-ask', /Send/).click();
    await until(() => location.hash.indexOf('#messages/') === 0 && window.UI_READY && $('.ms-thread'), 'chat thread after asking', 40000);
    await sleep(600);
    log.push('ok   asking the seller opens the chat (' + location.hash + ')');
    const thread = location.hash;
    await visit('#messages');
    await visit(thread);
    await signOut();

    // ---- the admin (ADMIN_EMAILS address; made on the first run in this local database)
    const pw = 'Hb-local-admin-Kq7-2026';
    await visit('#auth');
    let i = inputs(); type(i[0], 'arkulinskis@gmail.com'); type(i[1], pw);
    button('.au-card .anvil-role-btn-block', /^Sign in$/).click();
    await sleep(3000);
    if (location.hash !== '#browse') await signUp('Local Admin', 'arkulinskis@gmail.com', pw);
    await until(() => location.hash === '#browse' && window.UI_READY, 'signed in as admin', 60000);
    for (const h of ['#admin', '#admin/listings', '#admin/reports', '#admin/feedback', '#admin/users', '#admin/demo', item]) await visit(h);
    await signOut();
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log };
  } catch (e) {
    log.push(String(e && e.message || e));
    log.push('at ' + location.hash + ': ' + ((($('.anvil-modal-content') || $('.ui-main') || document.body).innerText) || '').replace(/\s+/g, ' ').slice(0, 400));
    return { ok: false, log };
  }
})();
