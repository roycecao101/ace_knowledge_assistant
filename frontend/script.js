"use strict";

// API layer. Session cookies are sent only to this application's origin.
// The backend must enforce authentication, authorization, and source verification.
const searchApi = {
  async search(question, office, category) {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 45_000);
    try {
      const data = await aceAuth.request("/api/search", "POST", { question, office, category },
        { signal: controller.signal });
      validateResponse(data);
      return data;
    } finally {
      clearTimeout(deadline);
    }
  },
};

function validateResponse(data) {
  if (!data || !["found", "not_found", "conflict", "unavailable"].includes(data.status)) {
    throw new Error("Unsupported response");
  }
  if (data.status === "found" || data.status === "conflict") {
    if (!Array.isArray(data.results) || data.results.length < (data.status === "conflict" ? 2 : 1)) {
      throw new Error("Missing verified sources");
    }
    for (const result of data.results) {
      if (!result || !["quote", "filename", "office"].every(key => typeof result[key] === "string" && result[key].trim()) ||
          !(typeof result.heading === "string" && result.heading.trim() || Number.isInteger(result.page) && result.page > 0)) {
        throw new Error("Incomplete verified source");
      }
    }
  }
}

// Rendering layer. All API text is inserted with textContent, never interpreted as HTML.
const form = document.querySelector("#search-form");
const questionInput = document.querySelector("#question");
const officeSelect = document.querySelector("#office");
const categorySelect = document.querySelector("#category");
const resultsRegion = document.querySelector("#results");
const welcome = document.querySelector("#welcome");
const searchButton = document.querySelector("#search-button");
const searchLabel = document.querySelector("#search-label");
let searching = false;
let signInRequired = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderQuote(result) {
  const sourceCard = element("div", "quote");
  sourceCard.append(element("blockquote", "", result.quote));
  const source = element("div", "source");
  source.append(element("strong", "", result.filename));
  if (result.heading) source.append(element("span", "", result.heading));
  if (Number.isInteger(result.page) && result.page > 0) source.append(element("span", "", `Page ${result.page}`));
  source.append(element("span", "office-badge", result.office));
  sourceCard.append(source);
  return sourceCard;
}

function renderResult(data, synthetic = false) {
  resultsRegion.replaceChildren();
  welcome.hidden = true;
  const card = element("article", `result-card ${data.status}`);
  if (synthetic) card.append(element("span", "preview-badge", "SYNTHETIC PREVIEW · NOT ACE POLICY"));
  if (data.status === "found") {
    card.append(element("h2", "result-title", "✓ Verified source information"));
    data.results.forEach(result => card.append(renderQuote(result)));
  } else if (data.status === "not_found") {
    card.append(element("p", "result-message", "I could not find this in Ace's approved materials."));
  } else if (data.status === "conflict") {
    card.append(element("h2", "result-title", "⚠ Conflicting information"));
    card.append(element("p", "result-message", "These approved documents disagree. Please check with your manager which one applies."));
    data.results.forEach(result => card.append(renderQuote(result)));
  } else {
    card.append(element("h2", "result-title", "! Assistant unavailable"));
    card.append(element("p", "result-message", "The assistant is unavailable right now. Please check the documents directly or ask your manager."));
    const retry = element("button", "primary retry", "Try Again");
    retry.type = "button";
    retry.addEventListener("click", () => {
      if (synthetic) renderResult({ status: "unavailable" }, true);
      else form.requestSubmit();
    });
    card.append(retry);
  }
  resultsRegion.append(card);
}

function setLoading(active) {
  searching = active;
  searchButton.disabled = active || signInRequired;
  questionInput.disabled = active || signInRequired;
  officeSelect.disabled = active || signInRequired;
  categorySelect.disabled = active || signInRequired;
  searchLabel.textContent = active ? "Searching…" : "Search";
  resultsRegion.setAttribute("aria-busy", String(active));
  if (active) {
    welcome.hidden = true;
    const loading = element("div", "loading");
    const spinner = element("span", "spinner");
    spinner.setAttribute("aria-hidden", "true");
    loading.append(spinner, element("span", "", "Searching approved company documents…"));
    resultsRegion.replaceChildren(loading);
  }
}

function clearAuthenticatedUI() {
  signInRequired = true;
  document.querySelector("#employee-name").textContent = "";
  document.querySelector("#auth-status").textContent = "Sign in required";
  document.querySelector("#admin-dashboard-link").hidden = true;
  document.querySelector("#logout").disabled = true;
  questionInput.value = "";
  officeSelect.value = "";
  categorySelect.value = "";
  welcome.hidden = true;
  resultsRegion.replaceChildren(element("p", "result-message", "Please sign in again."));
  setLoading(false);
}

// A preview is possible only on loopback/file URLs with an explicit URL flag.
// It never calls the API, never uses the entered question, and cannot activate
// on a deployed hostname, even if ?preview=1 is added to the production URL.
const localDevelopment = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) || location.protocol === "file:";
const previewMode = globalThis.ACE_SYNTHETIC_PREVIEW === true && localDevelopment && new URLSearchParams(location.search).get("preview") === "1";

// Development navigation only. Production must use a server-verified admin
// session to show this link; FastAPI must authorize every admin route and API.
if (previewMode) {
  const adminLink = document.querySelector("#admin-dashboard-link");
  adminLink.href = "admin.html?preview=1";
  adminLink.hidden = false;
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (searching || previewMode || signInRequired) return;
  const question = questionInput.value.trim();
  if (!question) {
    questionInput.setCustomValidity("Enter a question to search.");
    questionInput.reportValidity();
    return;
  }
  const office = officeSelect.value;
  const category = categorySelect.value;
  setLoading(true);
  try {
    renderResult(await searchApi.search(question, office, category));
  } catch (error) {
    // Do not log question text, responses, or employee information.
    // The shared client has already cleared authentication and begun redirecting.
    if (error.status === 401) clearAuthenticatedUI();
    else renderResult({ status: "unavailable" });
  } finally {
    setLoading(false);
  }
});
questionInput.addEventListener("input", () => questionInput.setCustomValidity(""));
questionInput.addEventListener("paste", event => {
  if ([...event.clipboardData.items].some(item => item.kind === "file")) event.preventDefault();
});
questionInput.addEventListener("drop", event => {
  if (event.dataTransfer.files.length) event.preventDefault();
});

// No real policies or question-specific fixtures. These are visual specimens only.
if (previewMode) {
  document.querySelector("#preview-controls").hidden = false;
  document.querySelector("#auth-status").textContent = "Synthetic development preview";
  searchButton.disabled = true;
  questionInput.disabled = true;
  questionInput.placeholder = "Choose a synthetic result state below";
  const specimen = {
    quote: "This is a synthetic quotation for interface preview only. It is not an Ace Family Dental policy.",
    filename: "Synthetic Example Document A.pdf",
    office: "Company-wide",
    heading: "Sample section",
    page: 1,
  };
  document.querySelector("#preview-state").addEventListener("change", event => {
    const status = event.target.value;
    if (status === "welcome") {
      resultsRegion.replaceChildren();
      welcome.hidden = false;
      return;
    }
    const results = status === "conflict" ? [specimen, {
      ...specimen,
      quote: "This second synthetic quotation represents a disagreement for display testing only. Ask a manager which document applies.",
      filename: "Synthetic Example Document B.pdf",
      office: "Norcross only",
      heading: "Another sample section",
      page: 2,
    }] : [specimen];
    renderResult({ status, results }, true);
  });
}

// Authentication integration: after your backend verifies the session, set
// employee-name and the home-office selection from that verified response.
// Enable Logout only when a real server-side logout endpoint is connected.
// Neither the office selector nor this frontend grants access to documents.

if (!previewMode) {
  searchButton.disabled = true;
  let homeOffice;
  async function refreshOffices() {
    const offices = await aceAuth.request("/api/offices");
    const selected = officeSelect.value || homeOffice;
    officeSelect.replaceChildren(...offices.map(office => {
      const option = element("option", "", `${office.name} (${[office.code, ...office.aliases].join(" / ")})`);
      option.value = office.name;
      return option;
    }));
    officeSelect.value = offices.some(o => o.name === selected) ? selected : homeOffice;
  }
  aceAuth.init().then(async user => {
    homeOffice = user.home_office;
    await refreshOffices();
    document.querySelector("#employee-name").textContent = user.name;
    document.querySelector("#auth-status").textContent = user.role === "admin" ? "Administrator · Employee View" : "Signed in";
    officeSelect.value = user.home_office;
    document.querySelector("#admin-dashboard-link").hidden = user.role !== "admin";
    const logout = document.querySelector("#logout");
    logout.disabled = false; logout.title = "Sign out";
    logout.addEventListener("click", () => aceAuth.logout().catch(() => location.replace("/login.html")));
    searchButton.disabled = false;
    officeSelect.addEventListener("focus", () => refreshOffices().catch(error => {
      if (error.status === 401) clearAuthenticatedUI();
      else document.querySelector("#auth-status").textContent = "Office list could not refresh. Try again.";
    }));
  }).catch(error => {
    if (error.status === 401) clearAuthenticatedUI();
    else document.querySelector("#auth-status").textContent = "Sign in required";
  });
}
