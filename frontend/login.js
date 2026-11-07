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
    if (!response.ok) throw new Error("Invalid account or credentials. Try again later.");
    loginForm.credential.value = "";
    location.replace(document.body.dataset.role === "admin" ? "/admin.html" : "/index.html");
  } catch (failure) { error.textContent = failure.message; }
  finally { button.disabled = false; }
});
