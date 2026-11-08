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
  const scanLabels = {not_scanned: "Awaiting analysis", failed: "Scan failed", incomplete: "Analysis incomplete"};
  function discrepancyNotice(log) {
    const notice = el("div", "notice warn");
    notice.setAttribute("role", "status");
    if (log.active_count) {
      const link = el("a", "", `⚠ ${log.active_count} potential policy discrepancies require review.`);
      link.href = "#find-fix"; notice.append(link);
    } else if (log.scan_status !== "succeeded") {
      const link = el("a", "", "Policy discrepancy analysis is incomplete. Open Find & Fix Log.");
      link.href = "#find-fix"; notice.append(link);
    } else notice.hidden = true;
    return notice;
  }
  function sourceEvidence(title, source) {
    const node = el("section", "discrepancy-source");
    node.append(el("h3", "", title), el("blockquote", "", source.quote));
    const info = el("dl");
    [["Source filename", source.filename], ["Heading", source.heading || "Not supplied"],
      ["Page", source.page || "Not supplied"], ["Applicable office", source.office]].forEach(([key, value]) => info.append(el("dt", "", key), el("dd", "", value)));
    node.append(info); return node;
  }
  function issueDetails(detail) {
    const evidence = detail.evidence || [{document_a: detail.document_a, document_b: detail.document_b}];
    const comparison = el("div", "discrepancy-comparison");
    const position = el("p", "muted");
    let index = 0;
    const previous = button("Previous comparison", () => { index--; display(); });
    const next = button("Next comparison", () => { index++; display(); });
    function display() {
      comparison.replaceChildren(sourceEvidence("Document A", evidence[index].document_a), sourceEvidence("Document B", evidence[index].document_b));
      position.textContent = `Verified comparison ${index + 1} of ${evidence.length}. ${detail.pair_count || 1} candidate passage pairs grouped into this issue.`;
      previous.disabled = index === 0; next.disabled = index === evidence.length - 1;
    }
    const actions = el("div", "actions");
    if (evidence.length > 1) actions.append(previous, next);
    display();
    return [badge("Needs Review", "warn"), el("h3", "", detail.topic || "Policy issue"),
      el("p", "muted", "Human review is required. These verified quotations may disagree; this log does not determine which source is correct. Review their context and applicable offices with the appropriate manager."),
      position, comparison, actions];
  }
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
        const [employees, admins, state, log] = await Promise.all([aceAuth.request("/api/admin/employees"), aceAuth.request("/api/admin/admins"), aceAuth.request("/api/admin/knowledge"), aceAuth.request("/api/admin/discrepancies")]);
        if (version !== navigationVersion) return;
        show(discrepancyNotice(log), renderCards([["Active employees", employees.filter(e => e.active).length, "Account access"], ["Active administrators", admins.filter(a => a.active).length, "At least two must remain"],
          ["Indexed documents", state.indexed_count, "Readable approved documents"], ["Unreadable files", state.unreadable_count, "Review in Knowledge Management"]]),
          panel("Knowledge workspace", "Monitor Google Drive and review indexed or unreadable files in one place.", button("Open Knowledge Management", () => { location.hash = "knowledge"; }, "primary")));
        refreshTimer = setTimeout(() => run(navigate), 10000);
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
      if (id === "find-fix") {
        const [state, log] = await Promise.all([aceAuth.request("/api/admin/knowledge"), aceAuth.request("/api/admin/discrepancies")]);
        if (version !== navigationVersion) return;
        const review = panel("Active potential discrepancies", "These passages may disagree. Confirm the correct policy with the appropriate manager, update the authorized source in Google Drive, then click Re-sync now. Alerts clear when the updated index no longer supports the discrepancy.");
        if (log.error) review.append(el("p", "notice error", log.error));
        if (state.unreadable_count) review.append(el("p", "notice warn", "Unreadable files are excluded from this scan. Review them in Knowledge Management."));
        if (!log.active_count) review.append(el("p", "muted", log.scan_status === "succeeded" ? "No supported potential discrepancies found. This local scan may miss differently worded conflicts." : "Analysis has not completed for the current index. Re-sync to retry."));
        if (log.raw_candidate_count != null) review.append(el("p", "muted", `${log.raw_candidate_count} candidate passage pair${log.raw_candidate_count === 1 ? "" : "s"} grouped into ${log.active_count} distinct policy issue${log.active_count === 1 ? "" : "s"}.`));
        review.append(renderTable("Potential discrepancies requiring review", ["Policy issue / topic", "Status", "Document A", "Document B", "Review"], log.discrepancies.map(item => [
          item.topic || "Policy issue", badge("Needs Review", "warn"), item.document_a.filename, item.document_b.filename,
          button("View details", () => run(async () => {
            const detail = await aceAuth.request(`/api/admin/discrepancies/${encodeURIComponent(item.generation)}/${item.id}`);
            renderDialog("Potential policy discrepancy", issueDetails(detail));
          }))
        ])));
        const completed = log.scan_status === "succeeded";
        const label = completed ? (log.active_count ? "Completed with discrepancies" : "Completed with no supported discrepancies") : scanLabels[log.scan_status] || "Unknown";
        const summary = renderCards([["Active potential discrepancies", completed ? log.active_count : "Unavailable", "Needs Review"], ["Last successful discrepancy scan", date(log.last_success), "Local analysis"], ["Last scan status", label, "Current index"]]);
        summary.className += " scan-summary";
        show(summary, review, knowledgePanel(state));
        refreshTimer = setTimeout(() => run(navigate), state.running ? 3000 : 10000);
        return;
      }
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
