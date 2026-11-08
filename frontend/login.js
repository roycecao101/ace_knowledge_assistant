"use strict";
const loginForm = document.querySelector("form");
loginForm.addEventListener("submit", async event => {
  event.preventDefault();
  const button = loginForm.querySelector("button");
  const error = document.querySelector("#login-error");
  button.disabled = true; error.textContent = "";
  try {
    const response = await fetch(`/api/auth/${document.body.dataset.role}/login`, {
      method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({identifier: loginForm.identifier.value, credential: loginForm.credential.value})
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error("Invalid account or credentials. Try again later.");
      if (response.status === 403) throw new Error("Sign in was blocked by the server's origin settings. Open this page from the FastAPI server.");
      if (response.status === 404 || response.status === 405) throw new Error("Authentication is unavailable on this server. Open the FastAPI application on port 8000.");
      throw new Error("Sign in is unavailable. Check that the FastAPI server and database are ready.");
    }
    loginForm.credential.value = "";
    location.replace(document.body.dataset.role === "admin" ? "/admin.html" : "/index.html");
  } catch (failure) { error.textContent = failure instanceof TypeError ? "Cannot reach the authentication server. Check that FastAPI is running." : failure.message; }
  finally { button.disabled = false; }
});
