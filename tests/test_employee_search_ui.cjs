const {test} = require('node:test');
const assert = require('node:assert/strict');
const {inspectRender} = require('./employee_renderer.cjs');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('verified evidence renders exact text and complete citations', () => {
  // HTML-like source data must remain literal text.
  const result = {quote: 'Synthetic <b>telescope</b> calibration begins every Thursday.',
    filename: 'Fiction.docx', heading: 'Observatory schedule', office: 'Company-wide'};
  assert.deepEqual(inspectRender({status: 'found', results: [result]}), {
    status: 'found', card_class: 'result-card found', rendered_quotes: 1,
    source_fields_match: true, welcome_hidden: true, not_found_visible: false,
  });
});

test('conflict renders both sources including a PDF page citation', () => {
  const result = {quote: 'Synthetic calibration begins every Thursday.', filename: 'Fiction.pdf',
    page: 3, heading: '', office: 'Norcross only'};
  const rendered = inspectRender({status: 'conflict', results: [result, {...result, page: 4}]});
  assert.equal(rendered.rendered_quotes, 2);
  assert.equal(rendered.source_fields_match, true);
  assert.equal(rendered.not_found_visible, false);
});

test('unavailable and not-found remain distinct display states', () => {
  assert.equal(inspectRender({status: 'not_found'}).not_found_visible, true);
  const unavailable = inspectRender({status: 'unavailable'});
  assert.equal(unavailable.card_class, 'result-card unavailable');
  assert.equal(unavailable.not_found_visible, false);
});

test('incomplete successful response is rejected before rendering', () => {
  assert.throws(() => inspectRender({status: 'found', results: [{quote: 'Synthetic'}]}), /Incomplete verified source/);
});

test('each submitted search sends the current office and category selections', async () => {
  class Element {
    constructor() { this.children = []; this.value = ''; this.listeners = {}; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute() {}
    setCustomValidity() {}
  }
  const nodes = new Map();
  const document = {
    querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, new Element());
      return nodes.get(selector);
    },
    createElement: () => new Element(),
  };
  const offices = [{name:'Alpharetta',code:'ALP',aliases:[]}, {name:'Norcross',code:'NOR',aliases:[]}, {name:'Lilburn',code:'LIL',aliases:['ADC']}];
  const requests = [];
  const context = {
    document, location: {hostname: 'localhost', protocol: 'http:', search: ''},
    URLSearchParams, AbortController, setTimeout, clearTimeout,
    aceAuth: {
      init: async () => ({name: 'Synthetic employee', role: 'employee', home_office: 'Alpharetta'}),
      request: async (url, method, body) => {
        if (url === '/api/offices') return offices;
        requests.push({url, method, ...body});
        return {status: 'not_found'};
      },
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../frontend/script.js'), 'utf8'), context);
  await new Promise(setImmediate);
  assert.equal(nodes.get('#office').children.length, 3);
  offices.push({name:'Duluth',code:'DUL',aliases:[]});
  await nodes.get('#office').listeners.focus();
  assert.equal(nodes.get('#office').children.length, 4);
  assert.equal(nodes.get('#office').children[3].value, 'Duluth');
  nodes.get('#question').value = 'Could you explain how to buy telescope supplies?';
  nodes.get('#category').value = 'All Categories';
  for (const office of ['Norcross', 'Lilburn', 'Alpharetta', 'Duluth']) {
    nodes.get('#office').value = office;
    await nodes.get('#search-form').listeners.submit({preventDefault() {}});
    assert.equal(requests.at(-1).office, office);
  }
  nodes.get('#category').value = 'OSHA & Safety';
  await nodes.get('#search-form').listeners.submit({preventDefault() {}});
  assert.equal(requests.at(-1).category, 'OSHA & Safety');
  assert.ok(requests.every(request => request.url === '/api/search' && request.method === 'POST'));
});

const unavailableMessage = 'The assistant is unavailable right now. Please check the documents directly or ask your manager.';
const syntheticSession = [200, {csrf_token: 'synthetic-csrf', user: {
  id: 'synthetic-employee', name: 'Synthetic employee', role: 'employee', home_office: 'Alpharetta',
}}];

// Exercise both shipped scripts together, with no browser credentials or network.
async function searchPage(responses, initial = syntheticSession) {
  class Element {
    constructor() { this.children = []; this.value = ''; this.textContent = ''; this.listeners = {}; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute(name, value) { this[name] = value; }
    setCustomValidity() {}
  }
  const nodes = new Map(), calls = [], redirects = [], queue = [initial, ...responses];
  const context = {
    window: {},
    document: {
      querySelector(selector) {
        if (!nodes.has(selector)) nodes.set(selector, new Element());
        return nodes.get(selector);
      },
      createElement: () => new Element(),
    },
    location: {pathname: '/index.html', hostname: 'localhost', protocol: 'http:', search: '',
      replace: destination => redirects.push(destination)},
    URLSearchParams, AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => {
      calls.push({url, ...options});
      if (url === '/api/offices') return {status:200, ok:true, json:async () => [
        {name:'Alpharetta',code:'ALP',aliases:[]}, {name:'Norcross',code:'NOR',aliases:[]}, {name:'Lilburn',code:'LIL',aliases:['ADC']},
      ]};
      assert.ok(queue.length, 'Unexpected request');
      const next = queue.shift();
      if (next instanceof Error) throw next;
      const [status, body, csrfError] = next;
      return {status, ok: status >= 200 && status < 300, json: async () => body,
        headers: {get: name => name === 'X-CSRF-Error' ? csrfError : null}};
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/auth-client.js'), 'utf8'), context);
  context.aceAuth = context.window.aceAuth;
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/script.js'), 'utf8'), context);
  await new Promise(setImmediate); // Complete the real authentication initialization.
  return {nodes, calls, redirects, auth: context.aceAuth, submit: async () => {
    nodes.get('#question').value = 'Synthetic telescope question';
    nodes.get('#category').value = 'All Categories';
    await nodes.get('#search-form').listeners.submit({preventDefault() {}});
  }};
}

function renderedText(node) {
  return [node.textContent, ...node.children.map(renderedText)].join(' ');
}

function assertSignedOut(page) {
  assert.equal(page.auth.user, null);
  assert.equal(page.auth.csrf, '');
  assert.deepEqual(page.redirects, ['/login.html']);
  assert.equal(page.nodes.get('#employee-name').textContent, '');
  assert.equal(page.nodes.get('#auth-status').textContent, 'Sign in required');
  assert.equal(page.nodes.get('#admin-dashboard-link').hidden, true);
  for (const selector of ['#search-button', '#question', '#office', '#category', '#logout']) {
    assert.equal(page.nodes.get(selector).disabled, true, selector);
  }
  const text = renderedText(page.nodes.get('#results'));
  assert.match(text, /Please sign in again/);
  assert.ok(!text.includes('Assistant unavailable'));
  assert.ok(!text.includes(unavailableMessage));
  assert.equal(page.nodes.get('#results')['aria-busy'], 'false');
}

test('401 after an active search clears employee UI and blocks follow-up submissions', async () => {
  const page = await searchPage([[200, {status: 'found', results: [{
    quote: 'Synthetic old answer.', filename: 'Fiction.docx', heading: 'Synthetic section', office: 'Company-wide',
  }]}], [401, {detail: 'Please sign in again.'}]]);
  await page.submit();
  assert.match(renderedText(page.nodes.get('#results')), /Synthetic old answer/);
  await page.submit();
  assertSignedOut(page);
  assert.ok(!renderedText(page.nodes.get('#results')).includes('Synthetic old answer'));
  const count = page.calls.length;
  await page.submit();
  assert.equal(page.calls.length, count);
});

test('401 during CSRF recovery redirects without retrying search or showing unavailable', async () => {
  const page = await searchPage([[403, {detail: 'Invalid CSRF token.'}, 'invalid'], [401, {}]]);
  await page.submit();
  assertSignedOut(page);
  assert.deepEqual(page.calls.map(call => call.url), ['/api/auth/me', '/api/offices', '/api/search', '/api/auth/me']);
});

test('401 on page initialization clears UI and redirects to employee login', async () => {
  const page = await searchPage([], [401, {}]);
  assertSignedOut(page);
  await page.submit();
  assert.equal(page.calls.length, 1);
});

test('technical search failures preserve the exact unavailable message and permit retry', async () => {
  for (const failure of [new TypeError('Synthetic offline failure'),
    Object.assign(new Error('Synthetic deadline'), {name: 'AbortError'}),
    [503, {detail: 'Synthetic service failure'}], [200, {status: 'unavailable'}],
    [200, {status: 'found', results: []}]]) {
    const page = await searchPage([failure, [200, {status: 'not_found'}]]);
    await page.submit();
    const card = page.nodes.get('#results').children[0];
    assert.equal(card.className, 'result-card unavailable');
    assert.ok(card.children.some(node => node.textContent === unavailableMessage));
    assert.deepEqual(page.redirects, []);
    assert.equal(page.auth.user.id, 'synthetic-employee');
    assert.equal(page.nodes.get('#search-button').disabled, false);
    await page.submit();
    assert.equal(page.nodes.get('#results').children[0].className, 'result-card not_found');
  }
});
