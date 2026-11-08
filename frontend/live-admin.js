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
  document.querySelector(".avatar").textContent = user.name.split(/\s+/).map(s => s[0]).slice(0, 2).join("");
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
    renderDialog(title, [renderForm(fields, "Save", async data => {
      const result = await submit(Object.fromEntries(data)); modal.close();
      if (result.pin) showPin(result.pin);
      await run(navigate);
    })]);
  }
  const date = value => value ? new Date(value * 1000).toLocaleString() : "Never";
  const syncLabels = {not_configured: "Folder not configured", pending: "Awaiting first synchronization",
    running: "Synchronization in progress", failed: "Last synchronization failed", succeeded: "Last synchronization completed"};
  function knowledgePanel(state) {
    const synthetic = state.source_type === "local";
    const source = panel(synthetic ? "Synthetic development connection" : "Google Drive Connection",
      "Automatic synchronization is checked every five minutes and runs at least daily while the server is online.");
    if (synthetic) source.append(el("p", "", "This server uses fictional local documents."));
    const details = el("dl");
    [["Current folder ID", state.folder_id || "Not configured"],
      ["Last successful synchronization", date(state.last_success)],
      ["Most recent synchronization status", syncLabels[state.sync_status] || "Unknown"],
      ["Last attempt", date(state.last_attempt)]].forEach(([key, value]) => details.append(el("dt", "", key), el("dd", "", value)));
    source.append(details);
    source.append(el("p", "panel-description", state.connection_verified ? "Folder access verified by a successful synchronization." : "Folder access awaits a successful synchronization."));
    if (state.error) renderStatus(state.error, "error", source.appendChild(el("div")));
    const resync = button("Re-sync now", () => run(async () => {
      resync.disabled = true;
      try {
        await aceAuth.request("/api/admin/sync", "POST");
        renderStatus("Synchronization requested. Refresh status to check its outcome.");
        await navigate();
      } finally { resync.disabled = state.running || !state.configured; }
    }), "primary");
    resync.disabled = state.running || !state.configured;
    const actions = el("div", "actions");
    actions.append(resync, button("Refresh status", () => run(navigate))); source.append(actions);
    return source;
  }
  const officeOptions = offices => offices.map(o => ({value: o.name, label: `${o.name} (${[o.code, ...o.aliases].join(" / ")})`}));
  let refreshTimer;
  let navigationVersion = 0;
  async function navigate() {
    clearTimeout(refreshTimer);
    const version = ++navigationVersion;
    const section = sectionForHash();
    const id = section[0];
    document.querySelector("#page-title").textContent = section[1];
    document.querySelector("#breadcrumb").textContent = section[1];
    document.querySelector("#page-description").textContent = section[2];
    nav.querySelectorAll("a").forEach(a => {if(a.dataset.section === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");});
    content.replaceChildren(el("p", "muted", "Loading workspace…"));
    content.setAttribute("aria-busy", "true");
    const show = (...nodes) => { content.replaceChildren(...nodes); content.setAttribute("aria-busy", "false"); };
    try {
      if (id === "overview") {
        const [employees, admins, state] = await Promise.all([aceAuth.request("/api/admin/employees"), aceAuth.request("/api/admin/admins"), aceAuth.request("/api/admin/knowledge")]);
        if (version !== navigationVersion) return;
        show(renderCards([["Active employees", employees.filter(e => e.active).length, "Account access"], ["Active administrators", admins.filter(a => a.active).length, "At least two must remain"],
          ["Indexed documents", state.indexed_count, "Readable approved documents"], ["Unreadable files", state.unreadable_count, "Review in Knowledge Management"]]),
          panel("Knowledge workspace", "Monitor Google Drive and review indexed or unreadable files in one place.", button("Open Knowledge Management", () => { location.hash = "knowledge"; }, "primary")));
        return;
      }
      if (id === "employees" || id === "admins") {
        const employee = id === "employees";
        const path = `/api/admin/${id}`;
        const [rows, offices] = await Promise.all([aceAuth.request(path), employee ? aceAuth.request("/api/admin/offices") : Promise.resolve([])]);
        if (version !== navigationVersion) return;
        const p = panel(employee ? "Employees" : "Administrators", "Manage authenticated account access.", button(employee ? "Create employee" : "Add administrator", () => editForm("Create account", [
          {name:"id", label:"Account identifier", pattern:"[A-Za-z0-9_-]{1,80}", maxLength:80}, {name:"name",label:"Display name"},
          employee ? {name:"office",label:"Home office", options:officeOptions(offices)} : {name:"password",label:"Password (at least 12 characters)",type:"password",maxLength:256}
        ], data => aceAuth.request(path,"POST", data)), "primary"));
        const label = el("label", "", employee ? "Search employees" : "Search administrators");
        const input = el("input"); input.type = "search"; input.placeholder = "Name, identifier, office, or status"; label.append(input);
        const toolbar = el("div", "toolbar"); toolbar.append(label);
        const holder = el("div");
        function update() {
          const query = input.value.trim().toLowerCase();
          holder.replaceChildren(renderTable("Accounts", ["Name","Identifier",employee ? "Home office" : "Role","Status","Actions"], rows.filter(a => `${a.name} ${a.id} ${a.office || ""} ${a.active ? "active" : "inactive"}`.toLowerCase().includes(query)).map(a => {
            const actions = el("div", "actions");
            const status = button(a.active ? "Deactivate" : "Reactivate", () => run(async () => {
              await aceAuth.request(`${path}/${encodeURIComponent(a.id)}`,"PATCH",{active:!a.active}); await navigate();
            }));
            if (!employee && a.active && rows.filter(a => a.active).length <= 2) {
              status.disabled = true; status.title = "At least two active administrators must remain";
            }
            actions.append(status);
            if (employee) actions.append(
              button("Edit employee", () => editForm("Edit employee", [{name:"name",label:"Display name",value:a.name}, {name:"office",label:"Home office",value:a.office,options:officeOptions(offices)}], data => aceAuth.request(`${path}/${encodeURIComponent(a.id)}/details`,"PATCH",data))),
              button("Reset PIN", () => run(async () => showPin((await aceAuth.request(`${path}/${encodeURIComponent(a.id)}/pin`,"POST")).pin))));
            else actions.append(button("Change password", () => editForm("Replace administrator password", [{name:"password", label:"New password (at least 12 characters)",type:"password",maxLength:256}], data => aceAuth.request(`${path}/${encodeURIComponent(a.id)}/password`,"POST",data))));
            return [a.name,a.id,employee ? a.office : "Administrator",badge(a.active ? "Active" : "Inactive",a.active ? "" : "neutral"),actions];
          })));
        }
        input.addEventListener("input", update); update(); p.append(toolbar, holder); show(p); return;
      }
      if (id === "knowledge") {
        const state = await aceAuth.request("/api/admin/knowledge");
        if (version !== navigationVersion) return;
        const office = d => d.offices.length ? d.offices.join(" and ") : "Company-wide";
        const docs = panel("Indexed Documents", "Metadata only. Manage approved source files in Google Drive, then synchronize.");
        docs.append(renderTable("Indexed documents", ["Filename", "Category", "Applicable office", "Last modified"], state.documents.filter(d => d.status === "indexed").map(d => [d.filename,d.category,office(d),d.modified || "Not supplied"])));
        const unreadable = panel("Unreadable Files", "Files I could not read are excluded from search. Provide an approved readable version in Drive, then re-sync.");
        unreadable.append(renderTable("Unreadable files", ["Filename", "Category", "Applicable office", "Extraction failure"], state.documents.filter(d => d.status === "unreadable").map(d => [d.filename,d.category,office(d),d.error])));
        const settings = panel("Settings", "Configure the approved knowledge folder. Changing folders pauses search until the next successful synchronization. OAuth authorization is managed securely on the server.");
        const form = renderForm([{name:"folder_id", label:"Google Drive folder ID", value:state.folder_id, maxLength:200, pattern:"[A-Za-z0-9_-]{1,200}"}], "Save folder ID", async data => {
          await aceAuth.request("/api/admin/settings", "PATCH", Object.fromEntries(data));
          renderStatus("Knowledge folder saved. Re-sync to update the index."); await run(navigate);
        });
        form.querySelector("button").disabled = state.running;
        form.querySelectorAll("input").forEach(input => { input.disabled = state.running; });
        settings.append(form);
        show(knowledgePanel(state), docs, unreadable, settings);
        // Only poll while settings are disabled, preserving unsaved edits otherwise.
        if (state.running) refreshTimer = setTimeout(() => run(navigate), 3000);
        return;
      }
      if (id === "offices") {
        const offices = await aceAuth.request("/api/admin/offices");
        if (version !== navigationVersion) return;
        const p = panel("Office directory", "Office codes identify document scope. Lilburn uses both LIL and ADC.", button("Add office", () => editForm("Add office", [
          {name:"name",label:"Office name",help:"Use a unique office name."},
          {name:"code",label:"Office code",maxLength:10,pattern:"[A-Za-z][A-Za-z0-9]{1,9}",help:"2–10 letters or digits, starting with a letter. Codes are saved in uppercase."}
        ], async data => {
          const result = await aceAuth.request("/api/admin/offices", "POST", data);
          renderStatus("Office added. It is available in employee forms and search office selectors. Re-sync to apply its code to existing documents.");
          return result;
        }), "primary"));
        p.append(renderTable("Available offices", ["Office name", "Office code", "Alternate code"], offices.map(o => [o.name,badge(o.code),o.aliases.join(", ") || "—"])));
        show(p); return;
      }
      show(panel("Policy Guardian", "Policy change monitoring is planned. Continue reviewing approved documents and synchronization status in Knowledge Management."));
    } catch (error) {
      if (version !== navigationVersion) return;
      show(panel("Unable to load this section", "Please retry. Your saved records remain available.", button("Retry", () => run(navigate))));
      throw error;
    }
  }
  window.addEventListener("hashchange", () => {
    document.querySelector("#message").replaceChildren();
    document.querySelector("#main").focus();
    run(navigate);
  });
  await run(navigate);
})().catch(error => renderStatus(error.message, "error"));
