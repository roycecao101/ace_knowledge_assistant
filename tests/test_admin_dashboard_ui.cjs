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
  const log = {active_count:1,raw_candidate_count:6,scan_status:'succeeded',last_success:1794095704,error:'',discrepancies:[{
    id:'synthetic-stable-issue',generation:'synthetic-generation',status:'Needs Review',
    topic:'Synthetic telescope calibration schedule',pair_count:6,evidence_count:2,
    document_a:{filename:'Fiction A.docx',heading:'Calibration',page:null,office:'Company-wide'},
    document_b:{filename:'Fiction B.pdf',heading:'',page:2,office:'Alpharetta only'},
  }]};
  const state = {source_type:'drive', configured:true,folder_id:'synthetic-folder',connection_verified:true,
    sync_status:'succeeded',running:false,last_success:1794095704,last_attempt:1794095704,
    indexed_count:1,unreadable_count:1,documents:[
      {filename:'Synthetic <b>literal</b>.docx',category:'All Categories',offices:[],modified:'2026-11-07',status:'indexed'},
      {filename:'Unreadable.pdf',category:'All Categories',offices:['Lilburn'],status:'unreadable',error:'Password-protected PDF'},
    ]};
  const document = {
    querySelector(selector) { if (!nodes.has(selector)) nodes.set(selector,new Element()); return nodes.get(selector); },
    querySelectorAll() { return []; },
    createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag),
    createTextNode: value => {const n = new Element('#text'); n.textContent = value; return n;},
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
        if (url === '/api/admin/discrepancies') return structuredClone(log);
        if (url === '/api/admin/discrepancies/synthetic-generation/synthetic-stable-issue') {
          if (!log.active_count) throw new Error('This discrepancy is no longer available. Refresh the Find & Fix Log.');
          const item = structuredClone(log.discrepancies[0]);
          item.document_a.quote = 'Synthetic telescope calibration occurs every Monday before opening.';
          item.document_b.quote = 'Synthetic telescope calibration occurs every Tuesday before opening.';
          item.evidence = [
            {document_a:structuredClone(item.document_a),document_b:structuredClone(item.document_b)},
            {document_a:structuredClone(item.document_a),document_b:{...item.document_b,filename:'Fiction C.pdf',page:3,quote:'Synthetic telescope calibration occurs every Wednesday before opening.'}},
          ];
          return item;
        }
        if (url === '/api/admin/settings') {state.folder_id = body.folder_id; return {ok:true};}
        if (url === '/api/admin/sync') return {status:'scheduled'};
        if (/\/api\/admin\/(employees|admins)\/[^/]+$/.test(url) && method === 'PATCH') {
          const accounts = url.includes('/employees/') ? employees : admins;
          Object.assign(accounts.find(a => url.endsWith(`/${a.id}`)), body); return {ok:true};
        }
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
  return {nodes,calls,offices,employees,admins,state,log,click,navigate,submit,context,content:nodes.get('#content'),modal:nodes.get('#modal'),dialog:nodes.get('#dialog-content')};
}

test('six sections render, legacy knowledge links resolve, and unknown links recover', async () => {
  const page = await dashboard();
  const links = page.nodes.get('#navigation').querySelectorAll('a');
  assert.deepEqual(links.map(n => n.textContent), ['Overview','Employee Management','Knowledge Management','Office Management','Admin Management','Find & Fix Log']);
  for (const hash of ['#knowledge','#documents','#sync','#settings']) {
    await page.navigate(hash);
    assert.equal(page.nodes.get('#page-title').textContent,'Knowledge Management');
    assert.equal(page.content.querySelectorAll('h2').filter(n => n.textContent === 'Google Drive Connection').length,1);
    assert.equal(field(page.content.querySelector('form'), 'folder_id').value, 'synthetic-folder');
    assert.equal(page.content.querySelector('summary').textContent, 'Advanced Settings');
    assert.ok(text(page.content).includes('Synthetic <b>literal</b>.docx'));
    assert.ok(text(page.content).includes('Password-protected PDF'));
    assert.equal(links.find(n => n.dataset.section === 'knowledge').attributes['aria-current'],'page');
  }
  await page.navigate('#unknown');
  assert.equal(page.nodes.get('#page-title').textContent,'Overview');
  for (const hash of ['#guardian','#pulse','#find-fix']) {
    await page.navigate(hash);
    assert.equal(page.nodes.get('#page-title').textContent,'Find & Fix Log');
    assert.ok(text(page.content).includes('Needs Review'));
  }
  assert.ok(!text(page.content).includes('service is not connected'));
});

test('Find & Fix alert, verified detail refresh, sync, resolved and failed states render', async () => {
  const page = await dashboard();
  const alert = page.content.querySelectorAll('a').find(n => n.href === '#find-fix');
  assert.ok(alert && alert.textContent.includes('1 potential policy discrepancy requires review'));
  await page.navigate('#find-fix');
  assert.ok(text(page.content).includes('Last successful discrepancy scan'));
  assert.ok(text(page.content).includes('Fiction A.docx'));
  assert.ok(text(page.content).includes('Policy issue / topic'));
  assert.ok(text(page.content).includes('Synthetic telescope calibration schedule'));
  assert.ok(text(page.content).includes('6 candidate passage pairs grouped into 1 distinct policy issue.'));
  assert.ok(!text(page.content).includes('Google Drive Connection'));
  assert.ok(!text(page.content).includes('synthetic-folder'));
  assert.equal(page.content.querySelectorAll('blockquote').length,0);
  assert.equal(page.content.querySelectorAll('tr').length,2); // One header, one issue.
  await page.click(byText(page.content,'button','View details'));
  assert.ok(page.calls.some(c => c.url === '/api/admin/discrepancies/synthetic-generation/synthetic-stable-issue'));
  assert.equal(page.dialog.querySelectorAll('blockquote').length,2);
  for (const value of ['Document A','Document B','Fiction A.docx','Fiction B.pdf','Alpharetta only','Calibration','Monday','Tuesday']) assert.ok(text(page.dialog).includes(value));
  assert.ok(text(page.dialog).includes('Human review is required'));
  assert.ok(text(page.dialog).includes('does not determine which source is correct'));
  assert.equal(byText(page.dialog,'button','Previous comparison').disabled,true);
  await page.click(byText(page.dialog,'button','Next comparison'));
  assert.equal(page.dialog.querySelectorAll('blockquote').length,2);
  assert.ok(text(page.dialog).includes('Verified comparison 2 of 2'));
  assert.ok(text(page.dialog).includes('Fiction C.pdf'));
  assert.ok(text(page.dialog).includes('Wednesday'));
  assert.equal(byText(page.dialog,'button','Next comparison').disabled,true);
  await page.click(byText(page.dialog,'button','Previous comparison'));
  assert.ok(text(page.dialog).includes('Verified comparison 1 of 2'));
  assert.ok(text(page.dialog).includes('Tuesday'));
  page.modal.close();
  await page.click(byText(page.content,'button','Re-sync now'));
  assert.ok(page.calls.some(c => c.url === '/api/admin/sync' && c.method === 'POST'));
  page.log.active_count = 0;
  await page.click(byText(page.content,'button','View details'));
  assert.ok(text(page.nodes.get('#message')).includes('no longer available'));
  page.log.discrepancies = [];
  await page.click(byText(page.content,'button','Refresh status'));
  assert.ok(text(page.content).includes('No supported potential discrepancies found'));
  assert.equal(page.content.querySelectorAll('blockquote').length,0);
  await page.navigate('#overview');
  assert.ok(!text(page.content).includes('require review'));
  page.log.scan_status = 'failed'; page.log.error = 'Discrepancy analysis could not complete.';
  await page.navigate('#find-fix');
  assert.ok(text(page.content).includes('Scan failed'));
  assert.ok(text(page.content).includes('Unavailable'));
  assert.ok(text(page.content).includes(page.log.error));
  assert.ok(!text(page.content).includes('No supported potential discrepancies found'));
  page.log.scan_status = 'incomplete';
  await page.navigate('#find-fix');
  assert.ok(text(page.content).includes('Analysis incomplete'));
  assert.ok(text(page.content).includes('Unavailable'));
  page.log.scan_status = 'not_scanned';
  await page.navigate('#find-fix');
  assert.ok(text(page.content).includes('Awaiting analysis'));
  assert.ok(!text(page.content).includes('No supported potential discrepancies found'));
  await page.navigate('#overview');
  assert.ok(text(page.content).includes('analysis is incomplete'));
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
  const folderPattern = new RegExp(`^(?:${field(form, 'folder_id').pattern})$`, 'v');
  assert.equal(folderPattern.test('synthetic-folder_1'), true);
  assert.equal(folderPattern.test('invalid folder'), false);
  field(form,'folder_id').value = 'synthetic-updated'; await page.submit(form);
  assert.equal(page.state.folder_id,'synthetic-updated');
  page.state.running = true; page.state.sync_status = 'running';
  await page.click(byText(page.content,'button','Refresh status'));
  assert.equal(byText(page.content,'button','Synchronizing…').disabled,true);
  assert.equal(page.content.querySelector('form').querySelector('button').disabled,true);
});

test('employee creation preserves its one-time PIN through an earlier queued dialog close', async () => {
  const page = await dashboard('#employees');
  await page.click(byText(page.content,'button','Create employee'));
  const form = page.dialog.querySelector('form');
  const identifierPattern = new RegExp(`^(?:${field(form, 'id').pattern})$`, 'v');
  assert.equal(identifierPattern.test('SYN-NEW_01'), true);
  assert.equal(identifierPattern.test('invalid identifier'), false);
  field(form,'id').value = 'SYN-NEW'; field(form,'name').value = 'Synthetic New';
  await page.submit(form);
  assert.equal(page.modal.open,true);
  assert.ok(text(page.dialog).includes('00000000'));
  page.modal.listeners.close(); // Browser-delivered close event from the prior form.
  assert.ok(text(page.dialog).includes('00000000'));
  page.modal.close();
  assert.ok(!text(page.dialog).includes('00000000'));
});

test('deactivation requires confirmation; cancel preserves access and reactivation still works', async () => {
  const page = await dashboard('#employees');
  const writes = () => page.calls.filter(c => c.method === 'PATCH');
  await page.click(byText(page.content, 'button', 'Deactivate'));
  assert.equal(writes().length, 0);
  assert.ok(text(page.dialog).includes('Synthetic Employee (SYN-01)'));
  assert.ok(text(page.dialog).includes('Existing sessions will end'));
  await page.click(byText(page.dialog, 'button', 'Keep account active'));
  assert.equal(page.modal.open, false);
  assert.equal(writes().length, 0);
  await page.click(byText(page.content, 'button', 'Deactivate'));
  await page.click(byText(page.dialog, 'button', 'Deactivate account'));
  assert.equal(page.modal.open, false);
  assert.equal(writes()[0].url, '/api/admin/employees/SYN-01');
  assert.equal(writes()[0].body.active, false);
  assert.ok(text(page.content).includes('Inactive'));
  await page.click(byText(page.content, 'button', 'Reactivate'));
  assert.equal(writes()[1].body.active, true);
});

test('administrator minimum has a visible explanation and eligible deactivation has confirmation', async () => {
  const page = await dashboard('#admins');
  assert.equal(byText(page.content, 'button', 'Deactivate').disabled, true);
  assert.ok(text(page.content).includes('Add another active administrator'));
  assert.equal(byText(page.content, 'button', 'Deactivate').attributes['aria-describedby'], 'admin-minimum-help');
  page.admins.push({id:'SYN-THIRD', name:'Synthetic Third', active:true});
  await page.navigate('#admins');
  assert.equal(byText(page.content, 'button', 'Deactivate').disabled, false);
  await page.click(byText(page.content, 'button', 'Deactivate'));
  assert.ok(text(page.dialog).includes('At least two active administrators must remain'));
  await page.click(byText(page.dialog, 'button', 'Deactivate account'));
  assert.equal(byText(page.content, 'button', 'Deactivate').disabled, true);
});

test('knowledge dates are readable and overview reports existing counts and sync health', async () => {
  const page = await dashboard('#knowledge');
  assert.ok(!text(page.content).includes('2026-11-07'));
  assert.ok(text(page.content).includes('Connection verified'));
  page.state.documents[0].modified = 'invalid';
  await page.navigate('#knowledge');
  assert.ok(text(page.content).includes('Date unavailable'));
  await page.navigate('#overview');
  for (const label of ['Active employees', 'Active administrators', 'Indexed documents', 'Unreadable files', 'Last successful sync:']) {
    assert.ok(text(page.content).includes(label));
  }
  assert.equal(page.content.querySelectorAll('article').length, 4);
  assert.ok(!text(page.content).includes('Questions this month'));
  page.state.sync_status = 'failed';
  await page.navigate('#overview');
  assert.ok(text(page.content).includes('Sync needs attention'));
});

test('concise issue titles preserve the full source heading and exact quotation in details', async () => {
  const page = await dashboard('#find-fix');
  page.log.discrepancies[0].topic = 'Equipment inspection: Equipment inspection occurs every [value] before opening.';
  page.log.discrepancies[0].document_a.heading = 'Inspection: daily equipment';
  await page.navigate('#find-fix');
  assert.ok(byText(page.content, 'p', 'Equipment inspection'));
  assert.equal(page.content.querySelectorAll('tr').length, 2);
  await page.click(byText(page.content, 'button', 'View details'));
  assert.ok(text(page.dialog).includes('Inspection: daily equipment'));
  assert.equal(page.dialog.querySelectorAll('blockquote')[0].textContent, 'Synthetic telescope calibration occurs every Monday before opening.');
});

test('a rejected deactivation stays in the dialog and leaves the account active', async () => {
  const page = await dashboard('#employees');
  const request = page.context.aceAuth.request;
  page.context.aceAuth.request = async (url, method, body) => {
    if (method === 'PATCH') throw new Error('Synthetic authorization denial.');
    return request(url, method, body);
  };
  await page.click(byText(page.content, 'button', 'Deactivate'));
  await page.click(byText(page.dialog, 'button', 'Deactivate account'));
  assert.equal(page.modal.open, true);
  assert.equal(page.employees[0].active, true);
  assert.ok(text(page.dialog).includes('Synthetic authorization denial.'));
  assert.equal(byText(page.dialog, 'button', 'Deactivate account').disabled, false);
});
