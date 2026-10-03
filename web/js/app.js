/* Router and shell wiring for the student app. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;
  var view = document.getElementById("view");

  function navigate(hash) {
    if (global.location.hash === hash) route();
    else global.location.hash = hash;
  }

  function isAuthed() { return !!App.store.token; }
  function isStaff() {
    var u = App.store.user;
    return !!u && (u.role === "admin" || u.role === "teacher");
  }

  function route() {
    var hash = global.location.hash || "#/";
    var parts = hash.replace(/^#\/?/, "").split("/");
    var head = parts[0] || "";
    /* Remember where we came from so the back buttons on the inner pages know
       where to return to. */
    App.pushRoute(hash);
    if (global.Runner) global.Runner.leave();
    highlightNav(head);

    if (!isAuthed()) {
      renderOnly(global.Pages.auth, []);
      return;
    }
    switch (head) {
      case "":
      case "tests":
        renderOnly(global.Pages.tests, []);
        break;
      case "history":
        // Declared after "/{id}" on the server, so it must be a distinct path.
        renderOnly(global.Pages.history, []);
        break;
      case "profile":
        renderOnly(global.Pages.profile, []);
        break;
      case "run":
        if (!global.Runner) break;
        global.Runner.resume(parts[1]).catch(function (err) {
          App.toast(err.message, "error");
          navigate("#/tests");
        });
        break;
      case "result":
        /* renderOnly() clears the view first. The result page must go through it
           too: after submitting, the runner's DOM is still in the view, and
           appending the result without clearing would leave the old question
           and its "Yuborilmoqda..." button on screen above the result. */
        renderOnly(global.Pages.result, [parts[1]]);
        break;
      default:
        renderOnly(global.Pages.tests, []);
    }
  }

  function renderOnly(page, args) {
    view.innerHTML = "";
    if (page) page.render(view, navigate, args);
  }

  function highlightNav(head) {
    var links = document.querySelectorAll("#topNav a[data-nav]");
    Array.prototype.forEach.call(links, function (a) {
      a.classList.toggle("active", a.getAttribute("data-nav") === head);
    });
  }

  function refreshNav() {
    var user = App.store.user;
    document.getElementById("logoutBtn").classList.toggle("hidden", !user);
    document.getElementById("adminLink").classList.toggle("hidden", !isStaff());
  }

  function loadSettings() {
    return App.api.get("/admin/settings")
      .catch(function () { return null; });
  }

  document.getElementById("logoutBtn").addEventListener("click", function () {
    if (global.Runner) global.Runner.leave();
    App.store.clear();
    App.toast("Chiqdingiz", "success");
    navigate("#/");
  });

  global.addEventListener("hashchange", route);

  // Boot: validate the stored token, then render.
  if (isAuthed()) {
    App.api.get("/auth/me")
      .then(function (user) {
        App.store.user = user;
        refreshNav();
        route();
      })
      .catch(function () {
        App.store.clear();
        route();
      });
  } else {
    route();
  }

  refreshNav();
  global.AppShell = { navigate: navigate, refreshNav: refreshNav };
})(window);
