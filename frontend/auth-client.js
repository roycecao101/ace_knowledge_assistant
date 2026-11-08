"use strict";
window.aceAuth = {
  csrf: "",
  user: null,
  async request(path, method = "GET", body, options = {}) {
    const send = () => fetch(path, {method, credentials: "same-origin", cache: "no-store",
      headers: {"Content-Type": "application/json", "X-CSRF-Token": this.csrf},
      body: body === undefined ? undefined : JSON.stringify(body), signal: options.signal});
    let response = await send();
    // Cookies are shared between tabs; page memory is not. A new login in
    // another tab can replace the session while this page still has its token.
    // Retry only an explicit CSRF rejection, which happens before any mutation.
    if (response.status === 403 && response.headers.get("X-CSRF-Error") === "invalid"
        && !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
      await this.init(options);
      response = await send();
    }
    if (response.status === 401) {
      this.csrf = ""; this.user = null;
      location.replace(location.pathname.includes("admin") ? "/admin-login.html" : "/login.html");
      throw new Error("Your session expired. Please sign in again.");
    }
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Please check the supplied values.");
    return data;
  },
  async init(options = {}) {
    const data = await this.request("/api/auth/me", "GET", undefined, options);
    if (this.user && (this.user.id !== data.user.id || this.user.role !== data.user.role)) {
      this.csrf = "";
      throw new Error("The signed-in account changed in another tab. Reload this page before making changes.");
    }
    this.csrf = data.csrf_token;
    this.user = data.user;
    return data.user;
  },
  async logout() {
    await this.request("/api/auth/logout", "POST");
    this.csrf = ""; this.user = null;
    location.replace("/login.html");
  }
};
