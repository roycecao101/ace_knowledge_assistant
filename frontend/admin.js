"use strict";

/* Shared dashboard components and isolated synthetic preview.
 * Live requests are implemented in live-admin.js through auth-client.js:
 * GET /api/auth/me restores the existing session and CSRF token.
 * GET /api/admin/knowledge supplies Documents, Synchronization, and Settings.
 * POST /api/admin/sync starts synchronization; PATCH /api/admin/settings saves
 * the folder ID. GET /api/admin/sync is not the status endpoint.
 * All requests use the same origin as the FastAPI-served administrator page.
 * The preview adapter below intentionally performs no live API operations.
 */
const adminApi = Object.freeze({
  async request() {
    throw new Error("Admin backend not connected. A separately authenticated session is required.");
  },
});

const localDevelopment = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) || location.protocol === "file:";
const previewMode = globalThis.ACE_SYNTHETIC_PREVIEW === true && localDevelopment && new URLSearchParams(location.search).get("preview") === "1";
if (previewMode) {
  document.querySelectorAll("[data-employee-view]").forEach(link => {
    link.href = "index.html?preview=1";
  });
}
const sections = [
  ["overview", "Overview", "A clear view of your team’s knowledge workspace."],
  ["employees", "Employee Management", "Manage access across offices. All records shown here are fictional."],
  ["documents", "Document Management", "Knowledge indexed from Google Drive. Manage source files in Drive."],
  ["sync", "Google Drive Synchronization", "Monitor indexing and review synchronization issues."],
  ["offices", "Office Management", "Keep office labels and knowledge access organized."],
  ["admins", "Admin Management", "Separate administrator access with a minimum of two active administrators."],
  ["settings", "Settings", "Knowledge sources, inference limits, and operating information."],
  ["pulse", "Policy Pulse", "X-factor · Help Miriam spot policy updates and affected offices."],
];

// Fictional fixtures are instantiated only inside an explicit local preview.
function previewData() {
  return {
    employees: [
      { id: "DEMO-001", name: "Sample Employee A", office: "ALP", active: true },
      { id: "DEMO-002", name: "Sample Employee B", office: "NOR", active: true },
      { id: "DEMO-003", name: "Sample Employee C", office: "LIL/ADC", active: false },
      { id: "DEMO-004", name: "Sample Employee D", office: "ALP", active: true },
    ],
    offices: [["Alpharetta", "ALP"], ["Norcross", "NOR"], ["Lilburn", "LIL/ADC"]],
    admins: [{ name: "Demo Manager A", role: "Owner", active: true }, { name: "Demo Manager B", role: "Administrator", active: true }, { name: "Demo Manager C", role: "Administrator", active: false }],
    documents: [
      ["Sample Onboarding.pdf", "Training & Onboarding", ["ALP", "NOR", "LIL/ADC"], "Nov 7, 2026 · 06:00 EST"],
      ["Sample Office Checklist.docx", "Front Office", ["NOR"], "Nov 7, 2026 · 06:00 EST"],
      ["Sample Safety Guide.pdf", "OSHA & Safety", ["ALP", "LIL/ADC"], "Nov 7, 2026 · 06:00 EST"],
    ],
    pulse: [
      { kind: "Modified", file: "Sample Onboarding.pdf", offices: ["ALP", "NOR", "LIL/ADC"], detail: "Sample orientation timing changed.", before: "Synthetic policy: Orientation is held in week one.", after: "Synthetic policy: Orientation is held before the first scheduled shift." },
      { kind: "Added", file: "Sample Office Checklist.docx", offices: ["NOR"], detail: "New sample checklist indexed.", before: "No prior indexed version.", after: "Synthetic checklist: Review the daily office checklist." },
      { kind: "Renamed", file: "Sample Safety Guide.pdf", offices: ["ALP", "LIL/ADC"], detail: "Previously: Sample Safety Notes.pdf", before: "Filename: Sample Safety Notes.pdf", after: "Filename: Sample Safety Guide.pdf · Content unchanged." },
      { kind: "Moved", file: "Sample Scheduling.pdf", offices: ["ALP", "NOR"], detail: "Office scope changed from ALP to NOR.", before: "Folder: Demo / ALP / Front Office", after: "Folder: Demo / NOR / Front Office · No content change." },
      { kind: "Deleted", file: "Sample Retired Procedure.pdf", offices: ["LIL/ADC"], detail: "Removed from the knowledge index.", before: "Synthetic retired procedure: Use the old sample checklist.", after: "Document deleted. No current indexed version." },
    ],
  };
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function button(text, action, className = "") {
  const node = el("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}
function badge(text, tone = "") { return el("span", `badge ${tone}`, text); }
function officeLabels(offices) {
  const node = el("span");
  offices.forEach(office => node.append(badge(office)));
  return node;
}
function renderStatus(text, tone = "info", target = document.querySelector("#message")) {
  const message = el("div", `notice ${tone}`, text);
  target.replaceChildren(message);
  return message;
}
function panel(title, description = "", action) {
  const node = el("section", "panel");
  const top = el("div", "panel-top");
  const heading = el("div");
  heading.append(el("h2", "", title));
  if (description) heading.append(el("p", "panel-description", description));
  top.append(heading);
  if (action) top.append(action);
  node.append(top);
  return node;
}
function renderTable(caption, columns, rows) {
  const scroll = el("div", "table-scroll");
  const table = el("table");
  table.append(el("caption", "", caption));
  const head = el("thead");
  const tr = el("tr");
  columns.forEach(column => { const th = el("th", "", column); th.scope = "col"; tr.append(th); });
  head.append(tr);
  const body = el("tbody");
  rows.forEach(row => {
    const tr = el("tr");
    row.forEach(value => { const td = el("td"); td.append(value instanceof Node ? value : document.createTextNode(String(value))); tr.append(td); });
    body.append(tr);
  });
  if (!rows.length) {
    const td = el("td", "muted", "No matching records."); td.colSpan = columns.length;
    const tr = el("tr"); tr.append(td); body.append(tr);
  }
  table.append(head, body); scroll.append(table); return scroll;
}
function renderCards(items) {
  const grid = el("div", "cards");
  items.forEach(([label, value, note]) => {
    const card = el("article", "card");
    card.append(el("div", "card-label", label), el("div", "card-value", value), el("div", "card-note", note));
    grid.append(card);
  });
  return grid;
}
const modal = document.querySelector("#modal");
const dialogContent = document.querySelector("#dialog-content");
let dialogCleanup = () => {};
function renderDialog(title, children, cleanup = () => {}) {
  dialogCleanup(); dialogCleanup = cleanup;
  const heading = el("h2", "", title); heading.id = "dialog-title";
  dialogContent.replaceChildren(heading, ...children);
  modal.showModal();
}
modal.addEventListener("close", () => { dialogCleanup(); dialogCleanup = () => {}; dialogContent.replaceChildren(); });
document.querySelector("#close-dialog").addEventListener("click", () => modal.close());
function renderForm(fields, submitLabel, onSubmit) {
  const form = el("form", "form");
  fields.forEach(field => {
    const label = el("label", "", field.label);
    const input = el(field.options ? "select" : "input");
    input.name = field.name;
    if (field.options) field.options.forEach(value => { const option = el("option", "", value); option.value = value; input.append(option); });
    else { input.type = field.type || "text"; input.maxLength = 120; }
    input.required = field.required !== false;
    if (field.value !== undefined) input.value = field.value;
    if (field.min !== undefined) input.min = field.min;
    if (field.max !== undefined) input.max = field.max;
    label.append(input);
    if (field.help) label.append(el("small", "", field.help));
    form.append(label);
  });
  const submit = el("button", "primary", submitLabel); submit.type = "submit"; form.append(submit);
  form.addEventListener("submit", event => { event.preventDefault(); onSubmit(new FormData(form)); });
  return form;
}
function unavailable(action) {
  modal.close();
  renderStatus(`Preview only: ${action} was not performed. The Python backend must authenticate and authorize this operation. No records were changed.`);
}
function confirmAction(title, description) {
  renderDialog(title, [el("p", "", description), el("p", "muted", "This preview does not perform or save administrative actions."), button("Preview confirmation", () => unavailable(title), "primary")]);
}
function previewForm(title, fields) {
  renderDialog(title, [el("p", "muted", "Use fictional values only. Submission shows an integration notice; no changes are saved."), renderForm(fields, "Preview request", () => unavailable(title))]);
}
function resetPin(employee) {
  renderDialog("Reset employee PIN", [
    el("p", "", `Employee ${employee.id} · ${employee.name}. A live reset must require recent admin authentication, server authorization, and identity verification through an approved channel. The backend must invalidate the previous PIN.`),
    el("p", "muted", "Preview the one-time display using a synthetic eight-digit value. It is not a credential and cannot grant access."),
    button("Preview one-time PIN display", () => {
      const pin = el("div", "pin", "00000000");
      let timer;
      renderDialog("Synthetic PIN · one-time display", [el("p", "", "DEMO ONLY · Not a valid credential. A real PIN must be generated securely by the backend and shown only in its reset response. Deliver it privately after verifying the employee’s identity."), pin, el("p", "muted", "This display is cleared when closed or after 60 seconds. It is not stored or logged.")], () => { pin.textContent = ""; clearTimeout(timer); });
      timer = setTimeout(() => { modal.close(); renderStatus("The synthetic PIN display has expired."); }, 60_000);
    }, "primary"),
  ]);
}

function startPreview() {
  const data = previewData();
  const content = document.querySelector("#content");
  document.querySelector("#access-gate").hidden = true;
  document.querySelector("#dashboard").hidden = false;
  const navigation = document.querySelector("#navigation");
  sections.forEach(([id, name], index) => {
    const link = el("a"); link.href = `#${id}`;
    link.append(el("span", "nav-number", String(index + 1).padStart(2, "0")), document.createTextNode(name));
    link.dataset.section = id; navigation.append(link);
  });
  const lastSync = "Nov 7, 2026 · 06:00 EST";
  const createEmployee = () => previewForm("Create employee", [{ name: "id", label: "Employee ID" }, { name: "name", label: "Display name" }, { name: "office", label: "Home office", options: data.offices.map(o => o[1]) }]);
  const renderers = {
    overview() {
      content.append(renderCards([
        ["Active employees", String(data.employees.filter(e => e.active).length), "Across all three offices · sample data"],
        ["Indexed documents", String(data.documents.length), "Readable documents in the sample index"],
        ["Offices", String(data.offices.length), "ALP · NOR · LIL/ADC"],
        ["Questions this month", "1,248", "Ace-wide aggregate · fictional"],
      ]));
      renderStatus("Latest sync attempt failed at 08:00 EST: Google Drive connection expired. The last successful index remains available. Review synchronization before retrying.", "error", content.appendChild(el("div")));
      const grid = el("div", "two-columns");
      const sync = panel("Knowledge health", "Keep the team connected to current source material.", button("Review sync", () => { location.hash = "sync"; }));
      const dl = el("dl");
      [["Last successful synchronization", lastSync], ["Current synchronization status", "Failed · attention required"], ["Unreadable files", "2 sample files need review"]].forEach(([k,v]) => dl.append(el("dt", "", k), el("dd", "", v)));
      sync.append(dl);
      const usage = panel("Ace-wide usage", "Aggregate totals only · fictional reporting period: November 2026");
      usage.append(renderTable("No employee-level analytics or question text", ["Metric", "Total"], [["Searches", "1,248"], ["Source-backed answers", "1,096"], ["Unresolved searches", "152"], ["Paid AI questions today", "84 / 300"]]));
      grid.append(sync, usage); content.append(grid);
      const pulse = panel("Policy Pulse — X-factor", "Five sample changes ready for Miriam to review.", button("Review policy changes →", () => { location.hash = "pulse"; }, "primary"));
      pulse.append(el("p", "change-summary", "1 added · 1 modified · 1 renamed · 1 moved · 1 deleted")); content.append(pulse);
    },
    employees() {
      const p = panel("Employee directory", "PIN hashes and existing PINs are never included in the frontend.", button("Create employee", createEmployee, "primary"));
      const toolbar = el("div", "toolbar"); const label = el("label", "", "Search employees"); const input = el("input"); input.type = "search"; input.placeholder = "Name, employee ID, office, or status"; label.append(input); toolbar.append(label);
      const holder = el("div");
      function update() {
        const query = input.value.trim().toLowerCase();
        const rows = data.employees.filter(e => `${e.name} ${e.id} ${e.office} ${e.active ? "active" : "inactive"}`.toLowerCase().includes(query)).map(e => {
          const actions = el("div", "actions");
          actions.append(button(e.active ? "Deactivate" : "Reactivate", () => confirmAction(`${e.active ? "Deactivate" : "Reactivate"} ${e.id}`, "The server must verify your permissions and apply the account status change."), e.active ? "danger" : ""), button("Reset PIN", () => resetPin(e)));
          return [e.name, e.id, officeLabels([e.office]), badge(e.active ? "Active" : "Inactive", e.active ? "" : "neutral"), actions];
        });
        holder.replaceChildren(renderTable(`${rows.length} matching fictional employees`, ["Employee", "Employee ID", "Home office", "Status", "Actions"], rows));
      }
      input.addEventListener("input", update); update(); p.append(toolbar, holder); content.append(p);
    },
    documents() {
      const p = panel("Indexed documents", "Metadata only. Uploads and image pasting are not supported; edit knowledge files in Google Drive.");
      p.append(renderTable("Fictional indexed document metadata", ["Filename", "Category", "Applicable offices", "Last synchronization"], data.documents.map(d => [d[0], d[1], officeLabels(d[2]), d[3]]))); content.append(p);
      const failed = panel("Files I could not read", "These sample files were skipped. Correct the source in Drive, then re-sync.");
      failed.append(renderTable("Unreadable source files", ["Filename", "Office", "Reason", "Suggested action"], [["Sample Scanned Notice.pdf", officeLabels(["ALP"]), "No extractable text", "Replace with a readable text document in Drive"], ["Sample Locked Guide.pdf", officeLabels(["NOR"]), "Password-protected file", "Provide an approved readable version in Drive"]])); content.append(failed);
    },
    sync() {
      const p = panel("Google Drive synchronization", "The last successful index remains available after a failed attempt.", button("Re-sync now", () => confirmAction("Re-sync Google Drive", "The backend must validate admin authorization, enqueue the sync, prevent overlapping jobs, and report its outcome."), "primary"));
      const dl = el("dl"); [["Current status", "Failed · Google Drive authorization required"], ["Last successful sync", lastSync], ["Last attempt", "Nov 7, 2026 · 08:00 EST"], ["Schedule", "Daily at 06:00 America/New_York · sample configuration"]].forEach(([k,v]) => dl.append(el("dt", "", k), el("dd", "", v))); p.append(dl); content.append(p);
      renderStatus("Sample error: Drive connection expired (DRIVE_AUTH_EXPIRED). Reconnect the integration through the secure backend setup, then retry. Two unreadable sample files also need review.", "error", content.appendChild(el("div")));
    },
    offices() {
      const p = panel("Office directory", "Office scope must be authorized by the backend.", button("Add office", () => previewForm("Add office", [{ name: "name", label: "Office name" }, { name: "code", label: "Office code" }]), "primary"));
      p.append(renderTable("Ace office labels · employee counts are fictional", ["Office", "Label", "Active employees"], data.offices.map(([name, code]) => [name, officeLabels([code]), data.employees.filter(e => e.office === code && e.active).length]))); content.append(p);
    },
    admins() {
      renderStatus("At least two administrators must remain active. The backend must enforce this rule in a transaction for every deactivation, removal, or role change. Only authorized administrators may manage accounts.", "info", content.appendChild(el("div")));
      const p = panel("Administrator accounts", "Demo owner permissions shown for layout inspection only.", button("Add administrator", () => previewForm("Add administrator", [{ name: "name", label: "Display name" }, { name: "email", label: "Work email (fictional)", type: "email" }, { name: "role", label: "Role", options: ["Administrator", "Owner"] }]), "primary"));
      const activeCount = data.admins.filter(a => a.active).length;
      p.append(renderTable("Fictional administrator accounts", ["Administrator", "Role", "Status", "Actions"], data.admins.map(a => {
        const actions = el("div", "actions");
        const statusButton = button(a.active ? "Deactivate" : "Reactivate", () => confirmAction(`Change access for ${a.name}`, "The backend must verify account-management permissions and maintain two active administrators."));
        if (a.active && activeCount <= 2) { statusButton.disabled = true; statusButton.title = "Two active administrators must remain"; }
        actions.append(statusButton, button("Manage role", () => previewForm(`Manage ${a.name}`, [{ name: "role", label: "Role", options: ["Administrator", "Owner"], value: a.role }])));
        return [a.name, a.role, badge(a.active ? "Active" : "Inactive", a.active ? "" : "neutral"), actions];
      }))); p.append(el("p", "panel-description", "Deactivation is disabled because this example has exactly two active administrators.")); content.append(p);
    },
    settings() {
      const p = panel("Knowledge & inference", "Sample settings only. Connection secrets belong exclusively on the backend.");
      p.append(renderForm([
        { name: "folder", label: "Google Drive knowledge-folder ID", value: "DEMO_FOLDER_ID_NOT_CONNECTED", help: "Fictional placeholder. The backend must validate folder access using its secure Drive integration." },
        { name: "paid", label: "Paid AI inference", options: ["Enabled (sample)", "Disabled"] },
        { name: "cap", label: "Daily AI question cap", type: "number", min: 1, max: 100000, value: 300, help: "Defaults to 300 when paid inference is enabled. Enforce the Ace-wide limit on the server; this browser cannot enforce usage caps." },
      ], "Preview settings request", () => unavailable("Save settings"))); content.append(p);
      const system = panel("System configuration & monthly costs", "Illustrative estimates only, not a provider quote or actual Ace costs.");
      system.append(renderTable("Fictional monthly operating budget · USD", ["Component", "Configuration", "Monthly estimate"], [["Application hosting", "Python / FastAPI · backend pending", "$15"], ["Knowledge storage", "Google Drive + search index", "$5"], ["AI inference", "Usage dependent · 300 questions/day cap", "$10–$40"], ["Estimated total", "No live billing integration", "$30–$60"]]));
      system.append(el("p", "panel-description", "A question cap is not a dollar spending limit. Model choice, tokens, and provider pricing determine costs. Configure credentials, retention, authentication, CSRF protection, and spending controls on the server.")); content.append(system);
    },
    pulse() {
      content.append(renderCards([["Added", "1", "New knowledge"], ["Modified", "1", "Content updated"], ["Renamed / moved", "2", "Names and office scope"], ["Deleted", "1", "Removed from the index"]]));
      const p = panel("Policy Pulse — X-factor", "For Miriam · Compare sample versions and check highlighted office labels. All text is synthetic.");
      p.append(renderTable("Changes detected in the last successful sample sync", ["Change", "Document", "Affected offices", "Details", "Review"], data.pulse.map(change => [badge(change.kind, change.kind === "Deleted" ? "error" : change.kind === "Modified" ? "warn" : ""), change.file, officeLabels(change.offices), change.detail, button("View changes", () => {
        const before = el("section"); before.append(el("h3", "", "Previous version · Nov 6, 2026"), el("div", "version before", change.before));
        const after = el("section"); after.append(el("h3", "", "Current version · Nov 7, 2026"), el("div", "version after", change.after));
        renderDialog(`${change.kind}: ${change.file}`, [officeLabels(change.offices), el("p", "muted", "Synthetic version comparison · not Ace policy. Live version access must be authorized by the backend."), before, after]);
      })]))); content.append(p);
    },
  };
  function navigate(initial = false) {
    const id = location.hash.slice(1);
    const section = sections.find(s => s[0] === id) || sections[0];
    navigation.querySelectorAll("a").forEach(link => { if (link.dataset.section === section[0]) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current"); });
    document.querySelector("#breadcrumb").textContent = section[1];
    document.querySelector("#page-title").textContent = section[1];
    document.querySelector("#page-description").textContent = section[2];
    document.querySelector("#message").replaceChildren(); content.replaceChildren();
    renderers[section[0]]();
    if (!initial) document.querySelector("#main").focus();
  }
  window.addEventListener("hashchange", () => navigate()); navigate(true);
}

// No uploads, pasted images, browser persistence, analytics, or credential logs.
document.addEventListener("paste", event => {
  if ([...(event.clipboardData?.items || [])].some(item => item.kind === "file")) event.preventDefault();
});
document.addEventListener("dragover", event => { if (event.dataTransfer?.types.includes("Files")) event.preventDefault(); });
document.addEventListener("drop", event => { if (event.dataTransfer?.files.length) event.preventDefault(); });
// Clear a one-time PIN when the tab is hidden as well as when its dialog closes.
document.addEventListener("visibilitychange", () => { if (document.hidden && modal.open) modal.close(); });
if (previewMode) startPreview();
else if (localDevelopment) document.querySelector("#local-help").hidden = false;
