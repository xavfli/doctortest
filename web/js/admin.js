/* Admin panel shell: login gate, hash router, modal helper. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;

  var content = document.getElementById("content");

  function isAdmin() {
    var u = App.store.user;
    return !!u && (u.role === "admin" || u.role === "teacher");
  }

  function login() {
    var email = document.getElementById("loginEmail").value.trim();
    // Trim so a stray space from a paste does not look like a wrong password.
    var password = document.getElementById("loginPassword").value.trim();
    var errBox = document.getElementById("loginError");
    errBox.classList.add("hidden");
    App.api.post("/auth/login", { email: email, password: password })
      .then(function (data) {
        App.store.token = data.access_token;
        App.store.user = data.user;
        App.store.password = password;
        boot();
      })
      .catch(function (err) {
        errBox.textContent = err.message;
        errBox.classList.remove("hidden");
      });
  }

  function boot() {
    if (!isAdmin()) {
      document.getElementById("login").classList.remove("hidden");
      document.getElementById("shell").classList.add("hidden");
      return;
    }
    document.getElementById("login").classList.add("hidden");
    document.getElementById("shell").classList.remove("hidden");
    var u = App.store.user;
    document.getElementById("whoami").textContent = u.full_name + " · " + u.role;
    route();
  }

  function navigate(hash) {
    if (global.location.hash === hash) route();
    else global.location.hash = hash;
  }

  function route() {
    var hash = global.location.hash || "#/dash";
    var head = hash.replace(/^#\/?/, "").split("/")[0] || "dash";
    Array.prototype.forEach.call(document.querySelectorAll("#menu a"), function (a) {
      a.classList.toggle("active", a.getAttribute("data-nav") === head);
    });
    content.innerHTML = "";
    var page = global.Admin && global.Admin.pages[head];
    if (page) page.render(content, navigate);
    else content.appendChild(el("div", { class: "card empty", text: "Sahifa topilmadi" }));
  }

  /* ----------------------------------------------------------------- modal */
  function modal(title, buildBody) {
    var box = document.getElementById("modal");
    document.getElementById("modalTitle").textContent = title;
    var body = document.getElementById("modalBody");
    body.innerHTML = "";
    buildBody(body, closeModal);
    box.classList.remove("hidden");
  }
  function closeModal() {
    document.getElementById("modal").classList.add("hidden");
  }

  document.getElementById("loginBtn").addEventListener("click", login);
  document.getElementById("loginPassword").addEventListener("keydown", function (e) {
    if (e.key === "Enter") login();
  });
  document.getElementById("logout").addEventListener("click", function () {
    App.store.clear();
    global.location.hash = "";
    boot();
  });
  document.getElementById("modalClose").addEventListener("click", closeModal);
  document.getElementById("modal").addEventListener("click", function (e) {
    if (e.target.id === "modal") closeModal();
  });
  global.addEventListener("hashchange", route);
  App.wirePasswordToggles(document);

  global.Admin = global.Admin || { pages: {} };
  global.Admin.navigate = navigate;
  global.Admin.modal = modal;
  global.Admin.closeModal = closeModal;

  if (App.store.token) {
    App.api.get("/auth/me")
      .then(function (user) { App.store.user = user; boot(); })
      .catch(function () { App.store.clear(); boot(); });
  } else {
    boot();
  }
})(window);
