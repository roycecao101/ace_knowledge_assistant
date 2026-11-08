"use strict";
if (!previewMode) (async () => {
  const content = document.querySelector("#content");
  const run = async action => {
    try { await action(); } catch (error) { renderStatus(error.message, "error"); }
  };
  const user = await aceAuth.init();
  if (user.role !== "admin") { location.replace("/admin-login.html"); return; }
  document.querySelector("#access-gate").hidden = true;
  document.querySelector("#dashboard").hidden = false;
  document.querySelector(".preview-notice").hidden = true;
  document.querySelector(".page-heading > .badge").textContent = "Authenticated workspace";
  document.querySelector(".sidebar-foot").textContent = "Secure administrator session";
  document.querySelector(".profile strong").textContent = user.name;
  document.querySelector(".profile small").textContent = "Administrator";
  document.querySelector(".header").append(button("Logout", () => run(() => aceAuth.logout())));
  const nav = document.querySelector("#navigation");
  sections.forEach(([id, name], index) => {
    const a = el("a", "", name); a.href = `#${id}`; a.dataset.section = id;
    a.prepend(el("span", "nav-number", String(index + 1).padStart(2,"0"))); nav.append(a);
  });
  function showPin(pin) {
    let timer;
    const node = el("div", "pin", pin);
    renderDialog("One-time employee PIN", [el("p", "", "Deliver this PIN privately. It cannot be retrieved again."), node], () => {node.textContent = ""; clearTimeout(timer);});
    timer = setTimeout(() => modal.close(), 60000);
  }
  function editForm(title, fields, submit) {
    renderDialog(title, [renderForm(fields, "Save", data => run(async () => {
      const result = await submit(Object.fromEntries(data)); modal.close();
      if (result.pin) showPin(result.pin);
      await navigate();
    }))]);
  }
  const date = value => value ? new Date(value * 1000).toLocaleString() : "Never";
  const syncLabels = {not_configured: "Folder not configured", pending: "Awaiting first synchronization",
    running: "Synchronization in progress", failed: "Last synchronization failed", succeeded: "Last synchronization completed"};
  function knowledgePanel(state) {
    const synthetic = state.source_type === "local";
    const source = panel(synthetic ? "Synthetic development synchronization" : "Google Drive synchronization", "Automatic synchronization is checked every five minutes and runs at least daily while the server is online.");
    if (synthetic) source.append(el("p", "", "This server uses fictional local documents. Google Drive access has not been tested here."));
    source.append(el("p", "", state.configured ? "Knowledge folder configured." : "Configure a knowledge folder in Settings."));
    source.append(el("p", "", state.connection_verified ? "This folder has completed a successful synchronization." : "Access to this folder has not yet been verified by a successful synchronization."));
    source.append(el("p", "", syncLabels[state.sync_status]));
    source.append(el("p", "", `Last successful synchronization: ${date(state.last_success)}`));
    source.append(el("p", "", `Last attempt: ${date(state.last_attempt)}`));
    if (state.error) source.append(el("p", "error", state.error));
    const resync = button("Re-sync now", () => run(async () => {
      resync.disabled = true;
      try {
        await aceAuth.request("/api/admin/sync", "POST");
        renderStatus("Synchronization requested. Its outcome will appear below.");
        await navigate();
      } finally { resync.disabled = false; }
    }), "primary");
    resync.disabled = state.running || !state.configured;
    source.append(resync, button("Refresh status", () => run(navigate)));
    return source;
  }
  let refreshTimer;
  let navigationVersion = 0;
  async function navigate() {
    clearTimeout(refreshTimer);
    const version = ++navigationVersion;
    const id = location.hash.slice(1) || "overview";
    const section = sections.find(s => s[0] === id) || sections[0];
    document.querySelector("#page-title").textContent = section[1];
    document.querySelector("#breadcrumb").textContent = section[1];
    document.querySelector("#page-description").textContent = "";
    nav.querySelectorAll("a").forEach(a => {if(a.dataset.section === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");});
    content.replaceChildren();
    if (id === "overview") {
      const [employees, admins, state] = await Promise.all([aceAuth.request("/api/admin/employees"), aceAuth.request("/api/admin/admins"), aceAuth.request("/api/admin/knowledge")]);
      if (version !== navigationVersion) return;
      content.append(renderCards([["Active employees", employees.filter(e => e.active).length, "Account access"], ["Active administrators", admins.filter(a => a.active).length, "At least two must remain"],
        ["Indexed documents", state.indexed_count, "Readable approved documents"], ["Files I could not read", state.unreadable_count, "Review in Document Management"]]));
      content.append(knowledgePanel(state));
      refreshTimer = setTimeout(() => run(navigate), state.running ? 3000 : 30000);
      return;
    }
    if (id === "employees" || id === "admins") {
      const employee = id === "employees";
      const path = `/api/admin/${id}`;
      const rows = await aceAuth.request(path);
      if (version !== navigationVersion) return;
      const p = panel(employee ? "Employees" : "Administrators", "Manage authenticated account access.", button(employee ? "Create employee" : "Add administrator", () => editForm("Create account", [
        {name:"id", label:"Account identifier"}, {name:"name",label:"Display name"},
        employee ? {name:"office",label:"Home office", options:["Alpharetta","Norcross","Lilburn"]} : {name:"password",label:"Password (at least 12 characters)",type:"password"}
      ], data => aceAuth.request(path,"POST", data)), "primary"));
      p.append(renderTable("Accounts", ["Name","Identifier",employee ? "Home office" : "Role","Status","Actions"], rows.map(a => {
        const actions = el("div", "actions");
        actions.append(button(a.active ? "Deactivate" : "Reactivate", () => run(async () => {
          await aceAuth.request(`${path}/${encodeURIComponent(a.id)}`,"PATCH",{active:!a.active}); await navigate();
        })));
        if(employee) actions.append(button("Reset PIN", () => run(async () => showPin((await aceAuth.request(`${path}/${encodeURIComponent(a.id)}/pin`,"POST")).pin))));
        else actions.append(button("Change password", () => editForm("Replace administrator password", [{name:"password", label:"New password (at least 12 characters)",type:"password"}], data => aceAuth.request(`${path}/${encodeURIComponent(a.id)}/password`,"POST",data))));
        return [a.name,a.id,employee ? a.office : "Administrator",a.active ? "Active" : "Inactive",actions];
      }))); content.append(p); return;
    }
    if (["documents", "sync", "settings"].includes(id)) {
      const state = await aceAuth.request("/api/admin/knowledge");
      if (version !== navigationVersion) return;
      const p = knowledgePanel(state);
      p.append(renderForm([{name:"folder_id", label:"Google Drive folder ID", value:state.folder_id}], "Save folder ID", data => run(async () => {
        await aceAuth.request("/api/admin/settings", "PATCH", Object.fromEntries(data));
        await navigate();
      })));
      content.append(p);
      const rows = state.documents;
      const office = d => d.offices.length ? d.offices.join(" and ") : "Company-wide";
      const docs = panel("Documents", "Manage source files in Google Drive, then synchronize.");
      docs.append(renderTable("Indexed documents", ["Filename", "Category", "Office", "Modified"], rows.filter(d => d.status === "indexed").map(d => [d.filename,d.category,office(d),d.modified])));
      content.append(docs);
      const unreadable = panel("Files I could not read", "These files are excluded from employee search. Replace image-only scans with text PDFs, Google Docs, or Word documents.");
      unreadable.append(renderTable("Unreadable files", ["Filename", "Extraction error"], rows.filter(d => d.error).map(d => [d.filename,d.error])));
      content.append(unreadable);
      if (state.running) refreshTimer = setTimeout(() => run(navigate), 3000);
      return;
    }
    content.append(panel(section[1], "This service is not connected. No changes can be made until its backend integration is configured."));
  }
  window.addEventListener("hashchange", () => run(navigate)); await run(navigate);
})().catch(error => renderStatus(error.message, "error"));
