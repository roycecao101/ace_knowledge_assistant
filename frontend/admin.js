"use strict";

/* Shared dashboard components and isolated synthetic preview.
 * Live requests are implemented in live-admin.js through auth-client.js:
 * GET /api/auth/me restores the existing session and CSRF token.
 * GET /api/admin/knowledge supplies the consolidated Knowledge Management page.
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
  ["employees", "Employee Management", "Manage employee access and home-office assignments."],
  ["knowledge", "Knowledge Management", "Connect Google Drive, synchronize documents, and review your index."],
  ["offices", "Office Management", "Manage office names and codes used across your workspace."],
  ["admins", "Admin Management", "Manage secure administrator access."],
  ["find-fix", "Find & Fix Log", "Review potential discrepancies in approved policies."],
];
function sectionForHash() {
  const requested = location.hash.slice(1);
  const id = ({documents: "knowledge", sync: "knowledge", settings: "knowledge", pulse: "find-fix", guardian: "find-fix"})[requested] || requested;
  return sections.find(section => section[0] === id) || sections[0];
}

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
  scroll.tabIndex = 0;
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", `${caption}. Scroll horizontally to see all columns.`);
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
  items.forEach(([label, value, note, icon]) => {
    const card = el("article", "card");
    const heading = el("div", "card-heading");
    heading.append(el("div", "card-label", label));
    if (icon) {
      const symbol = el("span", `card-icon metric-${icon}`);
      symbol.setAttribute("aria-hidden", "true");
      const paths = {
        employees: "M9 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m3 11v-3a6 6 0 0 0-2-4",
        admins: "m12 3 8 3v6c0 4-5 8-8 9-3-1-8-5-8-9V6ZM8 12l3 3 5-6",
        documents: "M6 3h8l4 4v14H6ZM14 3v5h4M9 12h6m-6 4h6",
        warning: "m12 3 10 18H2ZM12 9v5m0 3v1",
      };
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("fill", "none");
      svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "1.7");
      svg.setAttribute("stroke-linejoin", "round"); svg.setAttribute("stroke-linecap", "round");
      svg.setAttribute("focusable", "false");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", paths[icon] || paths.documents); svg.append(path); symbol.append(svg); heading.append(symbol);
    }
    card.append(heading, el("div", "card-value", value), el("div", "card-note", note));
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
  heading.tabIndex = -1;
  const top = el("div", "dialog-heading");
  const dismiss = button("×", () => modal.close(), "dialog-dismiss");
  dismiss.setAttribute("aria-label", "Close dialog");
  top.append(heading, dismiss);
  dialogContent.replaceChildren(top, ...children);
  modal.showModal();
  heading.focus({preventScroll: true});
  modal.scrollTop = 0;
}

// Display-only formatting. Quotation and citation strings are never rewritten.
function localDate(value, fallback = "Never") {
  if (!value) return fallback;
  const dateOnly = typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
  const parsed = dateOnly ? new Date(...value.split("-").map((n, i) => Number(n) - (i === 1 ? 1 : 0)))
    : new Date(typeof value === "number" ? value * 1000 : value);
  if (Number.isNaN(parsed.getTime())) return "Date unavailable";
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric",
    ...(dateOnly ? {} : { hour: "numeric", minute: "2-digit", timeZoneName: "short" }) });
}

function reviewWorkflow() {
  const list = el("ol", "review-workflow");
  [["Compare the sources", "Read both exact quotations, their context, and applicable offices."],
    ["Confirm with a manager", "The appropriate manager decides which policy applies."],
    ["Correct and re-sync", "Update the authorized source in Google Drive, then re-sync. The log updates after analysis."]]
    .forEach(([title, copy]) => {
      const item = el("li"); item.append(el("strong", "", title), document.createTextNode(copy)); list.append(item);
    });
  return list;
}

function policyTitle(topic) {
  // The analyzer supplies a heading followed by a detailed comparison signature.
  // Keep the heading as the row title; source evidence is always shown verbatim.
  return (topic || "Policy issue").split(/:\s+/, 1)[0];
}
modal.addEventListener("close", () => {
  // A queued close event from the account form must not clear a new PIN dialog.
  if (modal.open) return;
  dialogCleanup(); dialogCleanup = () => {}; dialogContent.replaceChildren();
});
document.querySelector("#close-dialog").addEventListener("click", () => modal.close());
function renderForm(fields, submitLabel, onSubmit) {
  const form = el("form", "form");
  fields.forEach(field => {
    const label = el("label", "", field.label);
    const input = el(field.options ? "select" : "input");
    input.name = field.name;
    if (field.options) field.options.forEach(value => {
      const option = el("option", "", typeof value === "object" ? value.label : value);
      option.value = typeof value === "object" ? value.value : value; input.append(option);
    });
    else { input.type = field.type || "text"; input.maxLength = field.maxLength || 120; }
    input.required = field.required !== false;
    if (field.value !== undefined) input.value = field.value;
    if (field.pattern) input.pattern = field.pattern;
    if (field.min !== undefined) input.min = field.min;
    if (field.max !== undefined) input.max = field.max;
    label.append(input);
    if (field.help) label.append(el("small", "", field.help));
    form.append(label);
  });
  const submit = el("button", "primary", submitLabel); submit.type = "submit"; form.append(submit);
  const feedback = el("div"); feedback.setAttribute("role", "status"); form.append(feedback);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    submit.disabled = true; feedback.replaceChildren();
    try { await onSubmit(new FormData(form)); }
    catch (error) { renderStatus(error.message, "error", feedback); }
    finally { submit.disabled = false; }
  });
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
    knowledge() { renderers.sync(); renderers.documents(); renderers.settings(); },
    overview() {
      content.append(renderCards([
        ["Active employees", String(data.employees.filter(e => e.active).length), "Enabled sample accounts", "employees"],
        ["Active administrators", String(data.admins.filter(a => a.active).length), "At least two must remain", "admins"],
        ["Indexed documents", String(data.documents.length), "Readable sample documents", "documents"],
        ["Unreadable files", "2", "Sample files excluded from search", "warning"],
      ]));
      renderStatus("Latest sync attempt failed at 08:00 EST: Google Drive connection expired. The last successful index remains available. Review synchronization before retrying.", "error", content.appendChild(el("div")));
      const sync = panel("Knowledge health", "Keep the team connected to current source material.", button("Review sync", () => { location.hash = "knowledge"; }));
      const dl = el("dl");
      [["Last successful synchronization", lastSync], ["Current synchronization status", "Failed · attention required"], ["Unreadable files", "2 sample files need review"]].forEach(([k,v]) => dl.append(el("dt", "", k), el("dd", "", v)));
      sync.append(dl);
      content.append(sync);
      content.append(panel("Find & Fix Log", "Review potential policy discrepancies after synchronization.", button("Open Find & Fix Log", () => { location.hash = "find-fix"; }, "primary")));
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
      const p = panel("Settings", "Synthetic settings preview. Connection secrets belong exclusively on the backend.");
      p.append(renderForm([{ name: "folder", label: "Google Drive knowledge-folder ID", value: "DEMO_FOLDER_ID_NOT_CONNECTED" }], "Preview settings request", () => unavailable("Save settings")));
      content.append(p);
    },
    "find-fix"() {
      content.append(renderCards([["Active potential discrepancies", "0", "Synthetic preview"], ["Last successful discrepancy scan", lastSync, "Sample timestamp"], ["Last scan status", "Completed", "Synthetic preview"]]));
      content.append(panel("Find & Fix Log", "The live workspace shows verified quotation pairs. Review them with the appropriate manager, update authorized source documents in Google Drive, then re-sync.", button("Re-sync now", () => unavailable("Re-sync"), "primary")));
    },
  };
  function navigate(initial = false) {
    const section = sectionForHash();
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
