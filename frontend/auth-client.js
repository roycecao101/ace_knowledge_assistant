"use strict";
window.aceAuth = {
  csrf: "",
  async request(path, method = "GET", body) {
    const response = await fetch(path, {method, credentials: "same-origin", cache: "no-store",
      headers: {"Content-Type": "application/json", "X-CSRF-Token": this.csrf},
      body: body === undefined ? undefined : JSON.stringify(body)});
    if (response.status === 401) {
      location.replace(location.pathname.includes("admin") ? "/admin-login.html" : "/login.html");
      throw new Error("Your session expired. Please sign in again.");
    }
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Please check the supplied values.");
    return data;
  },
  async init() {
    const data = await this.request("/api/auth/me");
    this.csrf = data.csrf_token;
    return data.user;
  },
  async logout() {
    await this.request("/api/auth/logout", "POST");
    location.replace("/login.html");
  }
};
