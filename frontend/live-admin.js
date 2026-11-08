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
  const date = localDate;
  const syncLabels = {not_configured: "Folder not configured", pending: "Awaiting first synchronization",
    running: "Synchronization in progress", failed: "Last synchronization failed", succeeded: "Last synchronization completed"};
  const scanLabels = {not_scanned: "Awaiting analysis", failed: "Scan failed", incomplete: "Analysis incomplete"};
  function discrepancyNotice(log) {
    const notice = el("div", "notice warn review-alert");
    notice.setAttribute("role", "status");
    const copy = el("div");
    if (log.active_count) {
      copy.append(el("strong", "", "Policy discrepancies need your attention"));
      const link = el("a", "", `⚠ ${log.active_count} potential policy ${log.active_count === 1 ? "discrepancy requires" : "discrepancies require"} review.`);
      link.href = "#find-fix"; copy.append(link, el("p", "", "Open Find & Fix Log to compare verified sources and review them with a manager."));
    } else if (log.scan_status !== "succeeded") {
      const link = el("a", "", "Policy discrepancy analysis is incomplete. Open Find & Fix Log.");
      link.href = "#find-fix"; copy.append(link);
    } else notice.hidden = true;
    notice.append(copy);
    return notice;
  }
  function sourceEvidence(title, source) {
    const node = el("section", "discrepancy-source");
    const heading = el("h3", "", title);
    heading.append(badge("Verified quotation"));
    node.append(heading, el("blockquote", "", source.quote));
    const info = el("dl");
    [["Source filename", source.filename], ["Heading", source.heading || "Not supplied"],
      ["Page", source.page || "Not supplied"], ["Applicable office", source.office]].forEach(([key, value]) => info.append(el("dt", "", key), el("dd", "", value)));
    node.append(info); return node;
  }
  function issueDetails(detail) {
    const evidence = detail.evidence || [{document_a: detail.document_a, document_b: detail.document_b}];
    const comparison = el("div", "discrepancy-comparison");
    const position = el("p", "comparison-position");
    position.setAttribute("aria-live", "polite");
    let index = 0;
    const previous = button("Previous comparison", () => { index--; display(); });
    const next = button("Next comparison", () => { index++; display(); });
    function display() {
      comparison.replaceChildren(sourceEvidence("Document A", evidence[index].document_a), sourceEvidence("Document B", evidence[index].document_b));
      const pairs = detail.pair_count || 1;
      position.textContent = `Verified comparison ${index + 1} of ${evidence.length}. ${pairs} candidate passage pair${pairs === 1 ? "" : "s"} grouped into this issue.`;
      previous.disabled = index === 0; next.disabled = index === evidence.length - 1;
    }
    const actions = el("div", "actions");
    if (evidence.length > 1) actions.append(previous, next);
    display();
    return [badge("Needs Review", "warn"), el("h3", "", policyTitle(detail.topic)),
      el("p", "muted", "Human review is required. These verified quotations may disagree; this log does not determine which source is correct. Review their context and applicable offices with the appropriate manager."),
      position, comparison, actions, reviewWorkflow()];
  }
  function syncButton(state) {
    const resync = button(state.running ? "Synchronizing…" : "Re-sync now", () => run(async () => {
      resync.disabled = true;
      try {
        await aceAuth.request("/api/admin/sync", "POST");
        renderStatus("Synchronization requested. Refresh status to check its outcome.");
        await navigate();
      } finally { resync.disabled = state.running || !state.configured; }
    }), "primary");
    resync.disabled = state.running || !state.configured;
    if (!state.configured) resync.title = "Configure the approved folder in Knowledge Management first.";
    return resync;
  }
  function syncHealth(state) {
    const node = el("div", "sync-health");
    const copy = el("div");
    const synthetic = state.source_type === "local";
    copy.append(el("h3", "", synthetic ? "Synthetic document source" : "Google Drive"),
      el("p", "", syncLabels[state.sync_status] || "Status unavailable"),
      el("p", "", `Last successful sync: ${date(state.last_success)}`));
    const label = synthetic ? "Local source" : !state.configured ? "Setup required" : state.sync_status === "failed" ? "Sync needs attention" : state.connection_verified ? "Connection verified" : "Not yet verified";
    node.append(copy, badge(label, state.sync_status === "failed" || (!state.connection_verified && !synthetic) ? "warn" : ""));
    return node;
  }
  function compactSync(state) {
    const strip = el("section", "sync-strip");
    strip.setAttribute("aria-label", "Synchronization status");
    const copy = el("div", "sync-copy", syncLabels[state.sync_status] || "Status unavailable");
    copy.append(el("small", "", `Last successful sync: ${date(state.last_success)}`));
    const link = el("a", "view-link", "Knowledge Management"); link.href = "#knowledge";
    strip.append(copy, syncButton(state), button("Refresh status", () => run(navigate)), link);
    return strip;
  }
  function knowledgePanel(state) {
    const synthetic = state.source_type === "local";
    const source = panel(synthetic ? "Synthetic development connection" : "Google Drive Connection",
      "Automatic synchronization is checked every five minutes and runs at least daily while the server is online.");
    if (synthetic) source.append(el("p", "", "This server uses fictional local documents."));
    source.append(syncHealth(state));
    const details = el("dl", "status-details");
    [["Last attempt", date(state.last_attempt)], ["Approved source", state.configured ? "Knowledge folder configured" : "Set up a folder in Advanced Settings"]]
      .forEach(([key, value]) => {
        const item = el("div"); item.append(el("dt", "", key), el("dd", "", value)); details.append(item);
      });
    source.append(details);
    source.append(el("p", "panel-description", state.connection_verified ? "Folder access verified by a successful synchronization. Connection health reflects the most recent sync; review any errors below." : "Folder access awaits a successful synchronization."));
    if (state.error) renderStatus(state.error, "error", source.appendChild(el("div")));
    const actions = el("div", "actions");
    actions.append(syncButton(state), button("Refresh status", () => run(navigate))); source.append(actions);
    return source;
  }
  const officeOptions = offices => offices.map(o => ({value: o.name, label: `${o.name} (${[o.code, ...o.aliases].join(" / ")})`}));
  let refreshTimer;
  let navigationVersion = 0;
  function scheduleRefresh(delay) {
    refreshTimer = setTimeout(() => {
      // Keep keyboard focus, open comparisons, and in-progress edits stable.
      if (modal.open || content.contains?.(document.activeElement)) scheduleRefresh(delay);
      else run(navigate);
    }, delay);
  }
  function confirmDeactivation(account, path, employee) {
    const feedback = el("div"); feedback.setAttribute("role", "alert");
    const confirm = button("Deactivate account", async () => {
      confirm.disabled = true;
      try {
        await aceAuth.request(`${path}/${encodeURIComponent(account.id)}`, "PATCH", {active: false});
        modal.close(); await run(navigate);
        renderStatus(`${account.name} has been deactivated.`);
      } catch (error) { renderStatus(error.message, "error", feedback); }
      finally { confirm.disabled = false; }
    }, "primary danger");
    const actions = el("div", "dialog-actions");
    actions.append(button("Keep account active", () => modal.close()), confirm);
    renderDialog(`Deactivate ${employee ? "employee" : "administrator"}?`, [
      el("p", "", `${account.name} (${account.id}) will lose access immediately. Existing sessions will end. You can reactivate this account later.`),
      el("p", "muted", employee ? "Their home-office assignment will be retained." : "At least two active administrators must remain."),
      actions, feedback]);
  }
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
        const health = panel("Knowledge health", "Check source availability and the most recent successful synchronization.", button("Open Knowledge Management", () => { location.hash = "knowledge"; }, "primary"));
        health.append(syncHealth(state));
        if (state.error) health.append(el("p", "notice error", state.error));
        if (state.unreadable_count) health.append(el("p", "panel-description", `${state.unreadable_count} unreadable file${state.unreadable_count === 1 ? " is" : "s are"} excluded from search. Review them in Knowledge Management.`));
        show(discrepancyNotice(log), renderCards([["Active employees", employees.filter(e => e.active).length, "Enabled employee accounts", "employees"], ["Active administrators", admins.filter(a => a.active).length, "Minimum of two active accounts", "admins"],
          ["Indexed documents", state.indexed_count, "Readable approved documents", "documents"], ["Unreadable files", state.unreadable_count, "Excluded from employee search", "warning"]]), health);
        scheduleRefresh(10000);
        return;
      }
      if (id === "employees" || id === "admins") {
        const employee = id === "employees";
        const path = `/api/admin/${id}`;
        const [rows, offices] = await Promise.all([aceAuth.request(path), employee ? aceAuth.request("/api/admin/offices") : Promise.resolve([])]);
        if (version !== navigationVersion) return;
        const p = panel(employee ? "Employees" : "Administrators", "Manage authenticated account access.", button(employee ? "Create employee" : "Add administrator", () => editForm("Create account", [
          {name:"id", label:"Account identifier", pattern:"[A-Za-z0-9_\\-]{1,80}", maxLength:80}, {name:"name",label:"Display name"},
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
            const status = button(a.active ? "Deactivate" : "Reactivate", () => {
              if (a.active) confirmDeactivation(a, path, employee);
              else return run(async () => { await aceAuth.request(`${path}/${encodeURIComponent(a.id)}`, "PATCH", {active:true}); await navigate(); });
            }, a.active ? "danger" : "");
            status.setAttribute("aria-label", `${a.active ? "Deactivate" : "Reactivate"} ${a.name}`);
            if (!employee && a.active && rows.filter(a => a.active).length <= 2) {
              status.disabled = true; status.title = "At least two active administrators must remain";
              status.setAttribute("aria-describedby", "admin-minimum-help");
            }
            actions.append(status);
            if (employee) actions.append(
              button("Edit employee", () => editForm("Edit employee", [{name:"name",label:"Display name",value:a.name}, {name:"office",label:"Home office",value:a.office,options:officeOptions(offices)}], data => aceAuth.request(`${path}/${encodeURIComponent(a.id)}/details`,"PATCH",data))),
              button("Reset PIN", () => run(async () => showPin((await aceAuth.request(`${path}/${encodeURIComponent(a.id)}/pin`,"POST")).pin))));
            else actions.append(button("Change password", () => editForm("Replace administrator password", [{name:"password", label:"New password (at least 12 characters)",type:"password",maxLength:256}], data => aceAuth.request(`${path}/${encodeURIComponent(a.id)}/password`,"POST",data))));
            return [a.name,a.id,employee ? a.office : "Administrator",badge(a.active ? "Active" : "Inactive",a.active ? "" : "neutral"),actions];
          })));
        }
        input.addEventListener("input", update); update(); p.append(toolbar, holder);
        if (!employee && rows.filter(a => a.active).length <= 2) {
          const help = el("p", "panel-description", "Deactivation is disabled for active administrators because at least two must remain. Add another active administrator before deactivating an existing one.");
          help.id = "admin-minimum-help"; p.append(help);
          holder.querySelectorAll("button").forEach(control => { if (control.disabled) control.setAttribute("aria-describedby", help.id); });
        }
        show(p); return;
      }
      if (id === "knowledge") {
        const state = await aceAuth.request("/api/admin/knowledge");
        if (version !== navigationVersion) return;
        const office = d => d.offices.length ? d.offices.join(" and ") : "Company-wide";
        const docs = panel("Indexed Documents", "Metadata only. Manage approved source files in Google Drive, then synchronize.");
        docs.append(renderTable(`${state.indexed_count} indexed documents`, ["Filename", "Category", "Applicable office", "Last modified"], state.documents.filter(d => d.status === "indexed").map(d => [d.filename,d.category,office(d),date(d.modified, "Not supplied")])));
        const unreadable = panel("Unreadable Files", "Files I could not read are excluded from search. Provide an approved readable version in Drive, then re-sync.");
        unreadable.append(renderTable("Unreadable files", ["Filename", "Category", "Applicable office", "Extraction failure"], state.documents.filter(d => d.status === "unreadable").map(d => [d.filename,d.category,office(d),d.error])));
        const settings = el("details", "panel advanced-settings");
        settings.append(el("summary", "", "Advanced Settings"));
        const settingsBody = el("div", "advanced-body");
        settingsBody.append(el("p", "panel-description", "Configure the approved knowledge folder. Changing folders pauses search until the next successful synchronization. OAuth authorization is managed securely on the server."));
        const form = renderForm([{name:"folder_id", label:"Google Drive folder ID", value:state.folder_id, maxLength:200, pattern:"[A-Za-z0-9_\\-]{1,200}"}], "Save folder ID", async data => {
          await aceAuth.request("/api/admin/settings", "PATCH", Object.fromEntries(data));
          renderStatus("Knowledge folder saved. Re-sync to update the index."); await run(navigate);
        });
        form.querySelector("button").disabled = state.running;
        form.querySelectorAll("input").forEach(input => { input.disabled = state.running; });
        settingsBody.append(form); settings.append(settingsBody);
        show(knowledgePanel(state), docs, unreadable, settings);
        // Only poll while settings are disabled, preserving unsaved edits otherwise.
        if (state.running) scheduleRefresh(3000);
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
        p.append(renderTable("Available offices", ["Office name", "Primary code", "Alternate codes"], offices.map(o => {
          const aliases = el("span"); o.aliases.forEach(code => aliases.append(badge(code, "neutral code")));
          return [o.name,badge(o.code, "code"),o.aliases.length ? aliases : "No alternate code"];
        })));
        show(p); return;
      }
      if (id === "find-fix") {
        const [state, log] = await Promise.all([aceAuth.request("/api/admin/knowledge"), aceAuth.request("/api/admin/discrepancies")]);
        if (version !== navigationVersion) return;
        const review = panel("Policies that need review", "One entry per distinct policy issue. Open the details to compare exact verified quotations; the appropriate manager decides which policy applies.");
        if (log.error) review.append(el("p", "notice error", log.error));
        if (state.unreadable_count) review.append(el("p", "notice warn", "Unreadable files are excluded from this scan. Review them in Knowledge Management."));
        if (!log.active_count) review.append(el("p", "empty-state", log.scan_status === "succeeded" ? "No supported potential discrepancies found. This local scan may miss differently worded conflicts." : "Analysis has not completed for the current index. Re-sync to retry."));
        if (log.raw_candidate_count != null && log.scan_status === "succeeded") review.append(el("p", "panel-description", `${log.raw_candidate_count} candidate passage pair${log.raw_candidate_count === 1 ? "" : "s"} grouped into ${log.active_count} distinct policy issue${log.active_count === 1 ? "" : "s"}.`));
        if (log.discrepancies.length) {
          const table = renderTable("Potential discrepancies requiring review", ["Policy issue / topic", "Status", "Verified sources", "Review"], log.discrepancies.map(item => {
          const title = el("div");
          const heading = el("p", "issue-title", policyTitle(item.topic));
          heading.title = item.topic || "Policy issue"; title.append(heading);
          const sources = el("div");
          [item.document_a, item.document_b].forEach((source, index) => {
            const file = el("div", "issue-file", `${index === 0 ? "A" : "B"} · ${source.filename}`);
            if (source.office) file.append(el("p", "issue-meta", source.office)); sources.append(file);
          });
          const details = button("View details", () => run(async () => {
            const detail = await aceAuth.request(`/api/admin/discrepancies/${encodeURIComponent(item.generation)}/${item.id}`);
            renderDialog("Potential policy discrepancy", issueDetails(detail));
          }));
          details.setAttribute("aria-label", `View details: ${item.topic || "Policy issue"}`);
          return [title, badge("Needs Review", "warn"), sources, details];
        }));
          table.className += " issue-table"; review.append(table);
        }
        const completed = log.scan_status === "succeeded";
        const label = completed ? (log.active_count ? "Completed with discrepancies" : "Completed with no supported discrepancies") : scanLabels[log.scan_status] || "Unknown";
        const summary = renderCards([["Active potential discrepancies", completed ? log.active_count : "Unavailable", completed ? (log.active_count ? "Needs Review" : "No open issues") : "Re-sync to complete analysis"], ["Last successful discrepancy scan", date(log.last_success), "Local analysis"], ["Last scan status", label, "Current index"]]);
        summary.className += " scan-summary";
        const workflow = panel("How to resolve a discrepancy", "Human review is required. No policy is selected or corrected automatically.");
        workflow.append(reviewWorkflow());
        show(compactSync(state), summary, review, workflow);
        scheduleRefresh(state.running ? 3000 : 10000);
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
    document.querySelector("#main").focus({preventScroll: true});
    window.scrollTo?.({top: 0, behavior: "instant"});
    run(navigate);
  });
  await run(navigate);
})().catch(error => renderStatus(error.message, "error"));
