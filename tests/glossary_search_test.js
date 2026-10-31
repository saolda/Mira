// Run the exact exported script using a small DOM double; no browser dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const data = html.match(/<script id="glossary-search-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const records = JSON.parse(data);
let focused = null;
let timer = 0;
const timers = new Map();
class Element {
  constructor(tag, id = '') {
    this.tagName = tag; this.id = id; this.children = []; this.attributes = {};
    this.events = {}; this.textContent = ''; this.hidden = false; this.value = ''; this.scrolls = [];
    const classes = new Set();
    this.classList = {add: (v) => classes.add(v), remove: (v) => classes.delete(v), contains: (v) => classes.has(v)};
  }
  setAttribute(k, v) { this.attributes[k] = v; }
  removeAttribute(k) { delete this.attributes[k]; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  addEventListener(type, fn) { this.events[type] = fn; }
  scrollIntoView(options) { this.scrolls.push(options); }
  focus() { focused = this; }
}
const ids = {};
for (const match of html.matchAll(/\bid="([^"]+)"/g)) ids[match[1]] = new Element('div', match[1]);
ids['glossary-search-data'].textContent = data;
const document = {getElementById: (id) => ids[id] || null, createElement: (tag) => new Element(tag)};
const window = {matchMedia: () => ({matches: true}),
  setTimeout: (fn, delay) => {assert.equal(delay, 2400); timers.set(++timer, fn); return timer;},
  clearTimeout: (id) => timers.delete(id)};
vm.runInNewContext(script, {document, window});
const input = ids['glossary-search'];
const results = ids['glossary-results'];
const count = ids['glossary-match-count'];
function search(query) { input.value = query; input.events.input(); return results.children.map((v) => v.children[0].textContent); }
function key(key, extras = {}) {
  const event = {key, ...extras, prevented: false, preventDefault() {this.prevented = true;}};
  input.events.keydown(event); return event;
}
assert.equal(count.textContent, records.length + ' glossary entries');
assert.equal(results.hidden, true);
assert.deepEqual(search('ALPHA'), ['Alpha', 'Alpha beta', 'Betalpha']); // exact, prefix, substring
assert.equal(count.textContent, '3 matching entries');
assert.equal(input.attributes['aria-activedescendant'], 'glossary-option-g1');
assert.equal(key('ArrowDown').prevented, true);
assert.equal(input.attributes['aria-activedescendant'], 'glossary-option-g2');
assert.equal(key('ArrowUp').prevented, true);
assert.equal(input.attributes['aria-activedescendant'], 'glossary-option-g1');
key('ArrowUp');
assert.equal(input.attributes['aria-activedescendant'], 'glossary-option-g3');
assert.equal(key('Enter').prevented, true);
assert.equal(focused.id, 'g3');
assert.equal(ids.g3.classList.contains('is-highlighted'), true);
assert.equal(ids.g3.scrolls.at(-1).block, 'start');
assert.equal(ids.g3.scrolls.at(-1).behavior, 'auto');
assert.deepEqual(search('First alias'), ['Alpha']);
assert.equal(results.children[0].children[1].textContent, 'g1 · Alias: First alias');
results.children[0].events.click();
assert.equal(focused.id, 'g1');
assert.equal(ids.g3.classList.contains('is-highlighted'), false);
assert.equal(ids.g1.classList.contains('is-highlighted'), true);
assert.equal(timers.size, 1);
[...timers.values()][0]();
assert.equal(ids.g1.classList.contains('is-highlighted'), false);
assert.deepEqual(search('Cafe\u0301'), ['Café']);
assert.deepEqual(search('ＳＴＲＡＳＳＥ'), ['Straße protein']);
assert.deepEqual(search('ος'), ['ΟΣ']);
assert.deepEqual(search('  multiple\t \n words  '), ['Spacing term']);
assert.deepEqual(search('T cell'), ['T-cell response']);
assert.deepEqual(search('pha bet'), ['Alpha beta']);
assert.deepEqual(search('ninth-alias'), ['Many aliases']);
assert.deepEqual(search('only-in-definition'), []);
assert.equal(count.textContent, '0 matching entries');
assert.equal(ids['glossary-no-matches'].hidden, false);
assert.equal(results.hidden, true);
assert.equal(key('Enter').prevented, false);
assert.deepEqual(search('citation-only'), []);
assert.deepEqual(search('passage-only'), []);
assert.deepEqual(search('</script>'), ['</script><img src=x onerror=alert(1)>']);
assert.equal(results.children[0].children[0].textContent, '</script><img src=x onerror=alert(1)>');
assert.deepEqual(results.children[0].children.map((v) => v.tagName), ['span', 'small']);
assert.equal(key('f', {ctrlKey: true}).prevented, false);
assert.deepEqual(search(''), []);
assert.equal(ids['glossary-no-matches'].hidden, true);
assert.equal(input.attributes['aria-activedescendant'], undefined);
console.log('Search, ranking, aliases, Unicode, keyboard navigation, highlighting and text-only results passed.');
