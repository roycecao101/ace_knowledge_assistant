const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Run both shipped dashboard scripts with a small in-memory DOM and API fixture.
// This checks rendered controls and actual handlers without real accounts or Drive.
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.listeners = {}; this.dataset = {};
    this.attributes = {}; this.value = ''; this._text = ''; this.disabled = false;
  }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text; }
  append(...nodes) {
    this.children.push(...nodes);
    if (this.tag === 'select' && !this.value && nodes.length) this.value = nodes[0].value;
  }
  prepend(...nodes) { this.children.unshift(...nodes); }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
  addEventListener(event, handler) { this.listeners[event] = handler; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelectorAll(tag) { return this.children.flatMap(child => child instanceof Element ? [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)] : []); }
  querySelector(tag) { return this.querySelectorAll(tag)[0]; }
  showModal() { this.open = true; }
  close() { this.open = false; this.listeners.close?.(); }
  focus() {}
}
const text = node => [node.textContent, ...node.children.map(text)].join(' ');
const byText = (root, tag, value) => root.querySelectorAll(tag).find(node => node.textContent === value);
const field = (form, name) => [...form.querySelectorAll('input'), ...form.querySelectorAll('select')].find(node => node.name === name);

async function dashboard(hash = '#overview') {
  const nodes = new Map(), events = {}, calls = [];
  const offices = [{name:'Alpharetta',code:'ALP',aliases:[]}, {name:'Lilburn',code:'LIL',aliases:['ADC']}, {name:'Norcross',code:'NOR',aliases:[]}];
  const employees = [{id:'SYN-01', name:'Synthetic Employee', office:'Alpharetta',active:true}];
  const admins = [{id:'SYN-ADMIN',name:'Synthetic Manager',active:true}, {id:'SYN-OTHER',name:'Synthetic Other',active:true}];
  const state = {source_type:'drive', configured:true,folder_id:'synthetic-folder',connection_verified:true,
    sync_status:'succeeded',running:false,last_success:1794095704,last_attempt:1794095704,
    indexed_count:1,unreadable_count:1,documents:[
      {filename:'Synthetic <b>literal</b>.docx',category:'All Categories',offices:[],modified:'2026-11-07',status:'indexed'},
      {filename:'Unreadable.pdf',category:'All Categories',offices:['Lilburn'],status:'unreadable',error:'Password-protected PDF'},
    ]};
  const document = {
    querySelector(selector) { if (!nodes.has(selector)) nodes.set(selector,new Element()); return nodes.get(selector); },
    querySelectorAll() { return []; },
    createElement: tag => new Element(tag), createTextNode: value => {const n = new Element('#text'); n.textContent = value; return n;},
    addEventListener() {},
  };
  const context = {document,Node:Element,location:{hostname:'localhost',protocol:'http:',search:'',hash},
    URLSearchParams,setTimeout:(...args) => { const timer = setTimeout(...args); timer.unref(); return timer; },clearTimeout,window:{addEventListener:(name,fn) => {events[name] = fn;}},
    FormData:class { constructor(form) { return [...form.querySelectorAll('input'),...form.querySelectorAll('select')].map(n => [n.name,n.value]); } },
    aceAuth:{
      init:async () => ({name:'Synthetic Manager',role:'admin'}), logout:async () => {},
      request:async (url,method='GET',body) => {
        calls.push({url,method,body});
        if (url === '/api/admin/offices') {
          if (method === 'POST') {
            if (offices.some(o => o.code === body.code)) throw new Error('Office name or code already exists.');
            const office = {...body,aliases:[]}; offices.push(office); return office;
          }
          return structuredClone(offices);
        }
        if (url === '/api/admin/employees') {
          if (method === 'POST') { employees.push({...body,active:true}); return {pin:'00000000'}; }
          return structuredClone(employees);
        }
        if (url === '/api/admin/admins') return structuredClone(admins);
        if (url === '/api/admin/knowledge') return structuredClone(state);
        if (url === '/api/admin/settings') {state.folder_id = body.folder_id; return {ok:true};}
        if (url === '/api/admin/sync') return {status:'scheduled'};
        if (url.endsWith('/details')) { Object.assign(employees[0],body); return {ok:true}; }
        throw new Error(`Unexpected fixture request: ${url}`);
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/admin.js'),'utf8'),context);
  await vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/live-admin.js'),'utf8'),context);
  const tick = () => new Promise(setImmediate);
  const click = async node => { assert.ok(node,'Expected visible control'); await node.listeners.click(); await tick(); };
  const navigate = async hash => { context.location.hash = hash; events.hashchange(); await tick(); };
  const submit = async form => { await form.listeners.submit({preventDefault(){}}); await tick(); };
  return {nodes,calls,offices,state,click,navigate,submit,context,content:nodes.get('#content'),modal:nodes.get('#modal'),dialog:nodes.get('#dialog-content')};
}

test('six sections render, legacy knowledge links resolve, and unknown links recover', async () => {
  const page = await dashboard();
  const links = page.nodes.get('#navigation').querySelectorAll('a');
  assert.deepEqual(links.map(n => n.textContent), ['Overview','Employee Management','Knowledge Management','Office Management','Admin Management','Policy Guardian']);
  for (const hash of ['#knowledge','#documents','#sync','#settings']) {
    await page.navigate(hash);
    assert.equal(page.nodes.get('#page-title').textContent,'Knowledge Management');
    assert.equal(page.content.querySelectorAll('h2').filter(n => n.textContent === 'Google Drive Connection').length,1);
    assert.ok(text(page.content).includes('synthetic-folder'));
    assert.ok(text(page.content).includes('Synthetic <b>literal</b>.docx'));
    assert.ok(text(page.content).includes('Password-protected PDF'));
    assert.equal(links.find(n => n.dataset.section === 'knowledge').attributes['aria-current'],'page');
  }
  await page.navigate('#unknown');
  assert.equal(page.nodes.get('#page-title').textContent,'Overview');
  await page.navigate('#guardian');
  assert.ok(text(page.content).includes('Policy change monitoring is planned.'));
  assert.ok(!text(page.content).includes('service is not connected'));
});

test('office creation updates directory and employee create/edit selectors; duplicate errors stay in form', async () => {
  const page = await dashboard('#offices');
  assert.ok(text(page.content).includes('ADC'));
  await page.click(byText(page.content,'button','Add office'));
  let form = page.dialog.querySelector('form');
  field(form,'name').value = 'Duluth'; field(form,'code').value = 'DUL';
  await page.submit(form);
  assert.equal(page.modal.open,false);
  assert.ok(text(page.content).includes('Duluth'));
  await page.click(byText(page.content,'button','Add office'));
  form = page.dialog.querySelector('form');
  field(form,'name').value = 'Duplicate'; field(form,'code').value = 'DUL';
  await page.submit(form);
  assert.equal(page.modal.open,true);
  assert.ok(text(form).includes('Office name or code already exists'));
  assert.equal(form.querySelector('button').disabled,false);
  page.modal.close();
  await page.navigate('#employees');
  await page.click(byText(page.content,'button','Create employee'));
  assert.ok(field(page.dialog.querySelector('form'),'office').children.some(o => o.value === 'Duluth'));
  page.modal.close();
  await page.click(byText(page.content,'button','Edit employee'));
  form = page.dialog.querySelector('form');
  assert.equal(field(form,'office').value,'Alpharetta');
  field(form,'office').value = 'Duluth'; await page.submit(form);
  assert.ok(page.calls.some(c => c.method === 'PATCH' && c.url.endsWith('/details') && c.body.office === 'Duluth'));
  assert.ok(text(page.content).includes('Duluth'));
});

test('knowledge controls call existing sync/settings APIs and running sync prevents conflicting writes', async () => {
  const page = await dashboard('#knowledge');
  await page.click(byText(page.content,'button','Re-sync now'));
  assert.ok(page.calls.some(c => c.url === '/api/admin/sync' && c.method === 'POST'));
  const form = page.content.querySelector('form');
  field(form,'folder_id').value = 'synthetic-updated'; await page.submit(form);
  assert.equal(page.state.folder_id,'synthetic-updated');
  page.state.running = true; page.state.sync_status = 'running';
  await page.click(byText(page.content,'button','Refresh status'));
  assert.equal(byText(page.content,'button','Re-sync now').disabled,true);
  assert.equal(page.content.querySelector('form').querySelector('button').disabled,true);
});

test('employee creation preserves its one-time PIN through an earlier queued dialog close', async () => {
  const page = await dashboard('#employees');
  await page.click(byText(page.content,'button','Create employee'));
  const form = page.dialog.querySelector('form');
  field(form,'id').value = 'SYN-NEW'; field(form,'name').value = 'Synthetic New';
  await page.submit(form);
  assert.equal(page.modal.open,true);
  assert.ok(text(page.dialog).includes('00000000'));
  page.modal.listeners.close(); // Browser-delivered close event from the prior form.
  assert.ok(text(page.dialog).includes('00000000'));
  page.modal.close();
  assert.ok(!text(page.dialog).includes('00000000'));
});
