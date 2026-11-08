// Run the shipped employee validator and renderer with an in-memory DOM.
// Live probes may pass private responses in memory; return booleans/counts only.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function inspectRender(data) {
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener() {}
  }
  const nodes = new Map();
  const document = {
    querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, new Element('div'));
      return nodes.get(selector);
    },
    createElement: tag => new Element(tag),
  };
  const script = fs.readFileSync(path.join(__dirname, '../frontend/script.js'), 'utf8');
  const context = {document, data};
  vm.runInNewContext(script.split('function setLoading(')[0] +
    '\nvalidateResponse(data); renderResult(data);', context);
  const card = nodes.get('#results').children[0];
  const quotes = card.children.filter(child => child.className === 'quote');
  const sourceMatches = quotes.every((quote, i) => {
    const source = quote.children.find(node => node.className === 'source');
    const result = data.results[i];
    return quote.children.find(node => node.tag === 'blockquote').textContent === result.quote &&
      source.children.some(node => node.textContent === result.filename) &&
      source.children.some(node => node.textContent === result.office) &&
      source.children.some(node => node.textContent === result.heading || node.textContent === `Page ${result.page}`);
  });
  return {status: data.status, card_class: card.className, rendered_quotes: quotes.length,
    source_fields_match: sourceMatches, welcome_hidden: nodes.get('#welcome').hidden,
    not_found_visible: card.children.some(node => node.textContent === "I could not find this in Ace's approved materials.")};
}
module.exports = {inspectRender};
