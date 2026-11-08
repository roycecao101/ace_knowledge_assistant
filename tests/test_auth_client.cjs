// Browser session lifecycle without credentials, personal browser state or network.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(require('node:path').join(__dirname, '../frontend/auth-client.js'), 'utf8');
function setup(responses, pathname = '/admin.html') {
  const calls = [], redirects = [];
  const context = {window: {}, location: {pathname, replace: path => redirects.push(path)},
    fetch: async (path, options) => {
      calls.push({path, ...options});
      assert.ok(responses.length, 'Unexpected extra request');
      const next = responses.shift();
      if (next instanceof Error) throw next;
      const [status, data, csrfError] = next;
      return {status, ok: status >= 200 && status < 300, json: async () => data,
        headers: {get: name => name === 'X-CSRF-Error' ? csrfError : null}};
    }};
  vm.runInNewContext(source, context);
  return {auth: context.window.aceAuth, calls, redirects};
}
const me = (token, id = 'fictional-admin', role = 'admin') => [200, {csrf_token: token, user: {id, role}}];
const rejected = [403, {detail: 'Invalid CSRF token.'}, 'invalid'];

test('authentication failures carry status, clear state and redirect without retry', async () => {
  for (const [pathname, destination] of [['/index.html', '/login.html'], ['/admin.html', '/admin-login.html']]) {
    const {auth, calls, redirects} = setup([me('current'), [401, {}]], pathname);
    await auth.init();
    await assert.rejects(auth.request('/api/search', 'POST', {question: 'Synthetic question'}),
      error => error.status === 401);
    assert.equal(auth.csrf, '');
    assert.equal(auth.user, null);
    assert.deepEqual(redirects, [destination]);
    assert.equal(calls.length, 2);
  }
});

test('new page obtains current token and sends cookie/token on mutations', async () => {
  const {auth, calls} = setup([me('current'), [200, {ok: true}]]);
  await auth.init();
  await auth.request('/api/admin/settings', 'PATCH', {folder_id: 'root'});
  assert.equal(calls[1].headers['X-CSRF-Token'], 'current');
  assert.equal(calls[1].body, JSON.stringify({folder_id: 'root'}));
  assert.ok(calls.every(call => call.credentials === 'same-origin' && call.cache === 'no-store'));
});
test('another tab rotates same-account cookie: refresh and retry once', async () => {
  const {auth, calls} = setup([me('old'), rejected, me('new'), [200, {ok: true}]]);
  await auth.init();
  await auth.request('/api/admin/settings', 'PATCH', {folder_id: 'root'});
  assert.deepEqual(calls.map(call => call.path), ['/api/auth/me', '/api/admin/settings', '/api/auth/me', '/api/admin/settings']);
  assert.equal(calls[1].headers['X-CSRF-Token'], 'old');
  assert.equal(calls[3].headers['X-CSRF-Token'], 'new');
  assert.equal(calls[1].body, calls[3].body);
});
test('CSRF retry is bounded when session changes again', async () => {
  const {auth, calls} = setup([me('old'), rejected, me('new'), rejected]);
  await auth.init();
  await assert.rejects(auth.request('/api/admin/sync', 'POST'), /Invalid CSRF/);
  assert.equal(calls.length, 4);
});
test('origin and role denials never replay a mutation', async () => {
  for (const detail of ['Invalid request origin.', 'Administrator access required.']) {
    const {auth, calls} = setup([me('token'), [403, {detail}]]);
    await auth.init();
    await assert.rejects(auth.request('/api/admin/sync', 'POST'), {message: detail});
    assert.equal(calls.length, 2);
  }
});
test('expired session during recovery clears token and redirects', async () => {
  const {auth, calls, redirects} = setup([me('old'), rejected, [401, {}]]);
  await auth.init();
  await assert.rejects(auth.request('/api/admin/sync', 'POST'), /session expired/);
  assert.equal(auth.csrf, '');
  assert.equal(auth.user, null);
  assert.deepEqual(redirects, ['/admin-login.html']);
  assert.equal(calls.length, 3);
});
test('a different account in another tab requires page reload before mutation', async () => {
  const {auth, calls} = setup([me('old'), rejected, me('new', 'other-admin')]);
  await auth.init();
  await assert.rejects(auth.request('/api/admin/sync', 'POST'), /account changed/);
  assert.equal(auth.csrf, '');
  assert.equal(calls.length, 3);
});
test('logout refreshes a stale token, revokes session and clears page state', async () => {
  const {auth, redirects} = setup([me('old'), rejected, me('new'), [200, {ok: true}]]);
  await auth.init();
  await auth.logout();
  assert.equal(auth.csrf, '');
  assert.equal(auth.user, null);
  assert.deepEqual(redirects, ['/login.html']);
});
test('network failures never replay a mutation', async () => {
  const {auth, calls} = setup([me('current'), new TypeError('offline')]);
  await auth.init();
  await assert.rejects(auth.request('/api/admin/sync', 'POST'), /offline/);
  assert.equal(calls.length, 2);
});
test('search abort signal is preserved through CSRF recovery', async () => {
  const {auth, calls} = setup([me('old'), rejected, me('new'), [200, {status: 'not_found'}]]);
  await auth.init();
  const controller = new AbortController();
  await auth.request('/api/search', 'POST', {question: 'fictional question'}, {signal: controller.signal});
  assert.ok(calls.slice(1).every(call => call.signal === controller.signal));
});
test('employee search uses shared client and still validates responses', async () => {
  const calls = [];
  let answer = {status: 'not_found'};
  const context = {AbortController, setTimeout, clearTimeout, aceAuth: {request: async (...args) => {
    calls.push(args); return answer;
  }}};
  const script = readFileSync(require('node:path').join(__dirname, '../frontend/script.js'), 'utf8');
  vm.runInNewContext(script.split('// Rendering layer.')[0] + '\nglobalThis.api = searchApi;', context);
  assert.equal((await context.api.search('fictional question', 'Norcross', 'All Categories')).status, 'not_found');
  assert.equal(calls[0][0], '/api/search');
  assert.equal(calls[0][1], 'POST');
  assert.ok(calls[0][3].signal instanceof AbortSignal);
  answer = {status: 'found', results: [{quote: 'unverified'}]};
  await assert.rejects(context.api.search('fictional question', 'Norcross', 'All Categories'), /Incomplete verified source/);
});
