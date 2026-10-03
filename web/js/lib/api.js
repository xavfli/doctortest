/* Thin API client: token handling, JSON helpers, toasts and small DOM utils. */
(function (global) {
  "use strict";

  var API_BASE = "/api";
  var TOKEN_KEY = "osh_token";
  var USER_KEY = "osh_user";

  /* The current password is kept in memory only (never localStorage) so that
     self-service password changes can verify it. Cleared on logout. */
  var sessionPassword = null;

  var store = {
    get token() { return localStorage.getItem(TOKEN_KEY); },
    set token(v) { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY); },
    get password() { return sessionPassword; },
    set password(v) { sessionPassword = v; },
    get user() {
      try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); }
      catch (e) { return null; }
    },
    set user(v) { v ? localStorage.setItem(USER_KEY, JSON.stringify(v)) : localStorage.removeItem(USER_KEY); },
    clear: function () {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      sessionPassword = null;
    },
  };

  function url(path, params) {
    var full = API_BASE + path;
    if (params) {
      var qs = Object.keys(params)
        .filter(function (k) { return params[k] !== undefined && params[k] !== null && params[k] !== ""; })
        .map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]); })
        .join("&");
      if (qs) full += (full.indexOf("?") === -1 ? "?" : "&") + qs;
    }
    return full;
  }

  function request(method, path, body, params) {
    var opts = {
      method: method,
      headers: { "Accept": "application/json" },
    };
    if (body !== undefined && body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    if (store.token) opts.headers["Authorization"] = "Bearer " + store.token;
    return fetch(url(path, params), opts).then(function (res) {
      var ctype = res.headers.get("content-type") || "";
      var parse = ctype.indexOf("application/json") !== -1 ? res.json() : res.text();
      return parse.catch(function () { return null; }).then(function (data) {
        if (!res.ok) {
          throw buildError(res, data);
        }
        return data;
      });
    });
  }

  /* FastAPI validation errors arrive as a list of objects; turn them into a
     single readable sentence instead of dumping raw JSON at the user. */
  function buildError(res, data) {
    var detail = data && data.detail !== undefined ? data.detail : null;
    var message;
    if (Array.isArray(detail)) {
      message = detail.map(function (item) {
        if (item && typeof item === "object") {
          var field = FIELD_LABELS[item.loc ? item.loc[item.loc.length - 1] : ""] || "Ma'lumot";
          return field + ": " + (item.msg || "noto‘g‘ri qiymat");
        }
        return String(item);
      }).join("; ");
    } else if (detail && typeof detail === "object") {
      message = detail.msg || JSON.stringify(detail);
    } else if (detail) {
      message = String(detail);
    } else {
      message = res.statusText || "Xatolik yuz berdi";
    }
    var err = new Error(message);
    err.status = res.status;
    err.data = data;
    return err;
  }

  var FIELD_LABELS = {
    email: "E-pochta",
    password: "Parol",
    full_name: "Ism-familiya",
    role: "Rol",
  };

  var api = {
    get: function (p, params) { return request("GET", p, null, params); },
    post: function (p, b, params) { return request("POST", p, b, params); },
    put: function (p, b) { return request("PUT", p, b); },
    patch: function (p, b) { return request("PATCH", p, b); },
    del: function (p) { return request("DELETE", p); },
  };

  /* ------------------------------------------------------------------ toasts */
  function toast(message, kind) {
    var host = document.getElementById("toasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "toasts";
      document.body.appendChild(host);
    }
    var el = document.createElement("div");
    el.className = "toast" + (kind ? " " + kind : "");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 250);
    }, 3200);
  }

  /* -------------------------------------------------------------------- dom */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on" && typeof attrs[k] === "function") {
        node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      } else if (attrs[k] !== null && attrs[k] !== undefined) {
        node.setAttribute(k, attrs[k]);
      }
    });
    (children || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      // Guard against accidentally passing a wrapper object ({node: ...}) or a
      // stray string: appendChild only accepts real Nodes.
      if (typeof c === "object" && c.nodeType === 1) {
        node.appendChild(c);
      } else if (typeof c === "object" && c.node) {
        node.appendChild(c.node);
      } else if (typeof c === "string" || typeof c === "number") {
        node.appendChild(document.createTextNode(String(c)));
      }
    });
    return node;
  }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtDate(value) {
    if (!value) return "—";
    var d = new Date(value);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("uz-UZ", { dateStyle: "short", timeStyle: "short" });
  }

  function fmtDuration(seconds) {
    var s = Math.max(0, Math.round(seconds || 0));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (r < 10 ? "0" : "") + r;
  }

  function scoreBadge(value, passed) {
    var cls = passed === undefined ? (value >= 60 ? "ok" : "bad") : (passed ? "ok" : "bad");
    return '<span class="badge ' + cls + '">' + value + "%</span>";
  }

  /* Password input with an eye button that reveals the typed value. */
  var EYE_OPEN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12z"/>' +
    '<circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M3 3l18 18"/>' +
    '<path d="M10.6 10.6a3 3 0 004.2 4.2"/>' +
    '<path d="M9.9 5.7A9.7 9.7 0 0112 5.5c7 0 10.5 6.5 10.5 6.5a18 18 0 01-2.7 3.4"/>' +
    '<path d="M6.2 6.7A18 18 0 001.5 12S5 18.5 12 18.5c1 0 1.9-.2 2.7-.5"/></svg>';

  function passwordInput(attrs) {
    var input = el("input", attrs);
    input.type = "password";
    var button = el("button", { type: "button", class: "pw-toggle" });
    setToggleState(button, false);
    button.addEventListener("click", function () {
      togglePassword(input, button);
      input.focus();
    });
    return el("div", { class: "pw-wrap" }, [input, button]);
  }

  function setToggleState(button, visible) {
    button.innerHTML = visible ? EYE_OFF : EYE_OPEN;
    button.title = visible ? "Parolni yashirish" : "Parolni ko‘rsatish";
    button.setAttribute("aria-label", button.title);
    button.setAttribute("aria-pressed", visible ? "true" : "false");
  }

  function togglePassword(input, button) {
    var visible = input.type === "password";
    input.type = visible ? "text" : "password";
    setToggleState(button, visible);
  }

  /* Wire buttons written directly in HTML:
     <button class="pw-toggle" data-toggle-for="inputId"> */
  function wirePasswordToggles(root) {
    var scope = root || document;
    Array.prototype.forEach.call(
      scope.querySelectorAll(".pw-toggle[data-toggle-for]"),
      function (button) {
        var input = scope.querySelector("#" + CSS.escape(button.getAttribute("data-toggle-for")));
        if (!input) return;
        setToggleState(button, input.type === "text");
        button.addEventListener("click", function () {
          togglePassword(input, button);
          input.focus();
        });
      }
    );
  }

  /* ------------------------------------------------------------ back button */
  /* A short trail of visited routes, so a "back" button can return to the page
     the student actually came from instead of guessing. Entries are pushed by
     the router on every navigation; the newest one is always the current page,
     so `previousRoute()` looks one step back from it. The list is capped so a
     long session cannot grow it without bound. */
  var routeTrail = [];
  var TRAIL_MAX = 20;

  function pushRoute(hash) {
    var value = hash || "#/";
    if (routeTrail[routeTrail.length - 1] === value) return;
    routeTrail.push(value);
    if (routeTrail.length > TRAIL_MAX) routeTrail.shift();
  }

  function previousRoute() {
    /* Drop the current page, then skip anything that would send the student
       back into the running attempt (that flow owns its own navigation). */
    for (var i = routeTrail.length - 2; i >= 0; i--) {
      var entry = routeTrail[i];
      if (entry.indexOf("#/run/") === 0) continue;
      return entry;
    }
    return "";
  }

  /* Back button used across the app. `fallback` is the page to open when there
     is no earlier route — which happens when the student lands straight on a
     result link, e.g. #/result/824 in a fresh tab. Without a fallback such a
     button would either do nothing or leave the site entirely. */
  function backButton(navigate, fallback, label) {
    return el("button", {
      class: "ghost back-btn",
      type: "button",
      title: "Orqaga qaytish",
      onclick: function () {
        var target = previousRoute() || fallback || "#/";
        navigate(target);
      },
    }, [
      el("span", { class: "back-arrow", text: "←" }),
      el("span", { text: label || "Orqaga" }),
    ]);
  }

  global.App = {
    api: api,
    store: store,
    toast: toast,
    el: el,
    escapeHtml: escapeHtml,
    fmtDate: fmtDate,
    fmtDuration: fmtDuration,
    scoreBadge: scoreBadge,
    passwordInput: passwordInput,
    wirePasswordToggles: wirePasswordToggles,
    backButton: backButton,
    pushRoute: pushRoute,
    previousRoute: previousRoute,
    API_BASE: API_BASE,
  };
})(window);
