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
  const requests = [];
  const context = {
    document, location: {hostname: 'localhost', protocol: 'http:', search: ''},
    URLSearchParams, AbortController, setTimeout, clearTimeout,
    aceAuth: {
      init: async () => ({name: 'Synthetic employee', role: 'employee', home_office: 'Alpharetta'}),
      request: async (url, method, body) => {
        requests.push({url, method, ...body});
        return {status: 'not_found'};
      },
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../frontend/script.js'), 'utf8'), context);
  await Promise.resolve();
  nodes.get('#question').value = 'Could you explain how to buy telescope supplies?';
  nodes.get('#category').value = 'All Categories';
  for (const office of ['Norcross', 'Lilburn', 'Alpharetta']) {
    nodes.get('#office').value = office;
    await nodes.get('#search-form').listeners.submit({preventDefault() {}});
    assert.equal(requests.at(-1).office, office);
  }
  nodes.get('#category').value = 'OSHA & Safety';
  await nodes.get('#search-form').listeners.submit({preventDefault() {}});
  assert.equal(requests.at(-1).category, 'OSHA & Safety');
  assert.ok(requests.every(request => request.url === '/api/search' && request.method === 'POST'));
});
