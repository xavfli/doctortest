/* Login and registration screen. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;

  /* Demo credentials. Kept in one place so the buttons below, the sidebar
     text and the admin login form can never drift apart. */
  var DEMO_ACCOUNTS = [
    { label: "Admin", email: "admin@osh.uz", password: "admin12345" },
    { label: "O‘qituvchi", email: "teacher@osh.uz", password: "teacher12345" },
  ];

  function render(view, navigate) {
    var state = { mode: "login", error: "", busy: false, settings: {} };

    var wrap = el("div", { class: "auth-wrap" }, [
      el("div", { class: "auth-side" }, [
        el("div", { class: "auth-hero" }, [
          el("h1", { text: "Oilaviy shifokorlik testi" }),
          el("p", {
            class: "muted",
            text: "Tizimga kirib, 20 ta savollik testni ishni boshlang. " +
              "Barcha natijalar serverda saqlanadi.",
          }),
          el("div", { class: "auth-points" }, [
            point("Har bo‘limda 20 ta savol", "Savollar har urinishda tasodifiy tartibda beriladi."),
            point("Serverda baholash", "To‘g‘ri javob hech qachon brauzerda saqlanmaydi."),
            point("Statistika", "Barcha urinishlar va natijalar tarixi saqlanadi."),
          ]),
        ]),
        el("div", { class: "small muted" }, [
          el("p", { text: "Demo hisoblar:" }),
        ].concat(DEMO_ACCOUNTS.map(function (acc) {
          return el("div", { class: "mono small", text: acc.email + " / " + acc.password });
        }))),
      ]),

      el("div", { class: "card" }, [
        el("div", { class: "tabs" }, [
          el("button", {
            class: "active",
            text: "Kirish",
            onclick: function () { state.mode = "login"; draw(); },
          }),
          el("button", {
            text: "Ro‘yxatdan o‘tish",
            onclick: function () { state.mode = "register"; draw(); },
          }),
        ]),
        el("div", { id: "authForm" }),
      ]),
    ]);

    view.appendChild(wrap);
    draw();

    function draw() {
      var form = document.getElementById("authForm");
      form.innerHTML = "";
      if (state.error) {
        form.appendChild(el("div", { class: "alert error", text: state.error }));
      }
      var isLogin = state.mode === "login";
      form.appendChild(el("div", { class: "field" }, [
        el("label", { for: "email", text: "E-pochta" }),
        el("input", {
          type: "email", id: "email", name: "email",
          placeholder: "siz@osh.uz", autocomplete: "username",
        }),
      ]));
      if (!isLogin) {
        form.appendChild(el("div", { class: "field" }, [
          el("label", { for: "fullName", text: "F.I.O." }),
          el("input", {
            type: "text", id: "fullName", name: "full_name",
            placeholder: "Ism Familiya", autocomplete: "name",
          }),
        ]));
      }
      form.appendChild(el("div", { class: "field" }, [
        el("label", { for: "password", text: "Parol" }),
        App.passwordInput({
          id: "password", name: "password",
          placeholder: isLogin ? "Parolni kiriting" : "Kamida 8 ta belgi",
          autocomplete: isLogin ? "current-password" : "new-password",
        }),
      ]));
      var submit = el("button", {
        class: "primary block",
        text: state.busy ? "Kutilmoqda…" : (isLogin ? "Kirish" : "Ro‘yxatdan o‘tish"),
        onclick: submitForm,
      });
      form.appendChild(submit);

      // One-click demo login so the credentials cannot be mistyped.
      if (isLogin) {
        var quick = el("div", { class: "quick-login" }, [
          el("span", { class: "small muted", text: "Demo hisobga bir bosishda kirish:" }),
        ]);
        DEMO_ACCOUNTS.forEach(function (acc) {
          quick.appendChild(el("button", {
            class: "ghost small",
            type: "button",
            text: acc.label,
            onclick: function () {
              if (state.busy) return;
              state.error = "";
              App.api.post("/auth/login", { email: acc.email, password: acc.password })
                .then(function (data) {
                  App.store.token = data.access_token;
                  App.store.user = data.user;
                  App.store.password = acc.password;
                  App.toast("Xush kelibsiz, " + data.user.full_name, "success");
                  navigate("#/tests");
                })
                .catch(function (err) {
                  state.error = err.message || "Kirishda xatolik";
                  draw();
                });
            },
          }));
        });
        form.appendChild(quick);
      }
      form.appendChild(el("div", { class: "hint", text: isLogin
        ? "Ro‘yxatdan o‘tmaganmisiz? Yuqoridagi registratsiya tabiga o‘ting."
        : "Ro‘yxatdan o‘tgan foydalanuvchi student ro‘lini oladi." }));
      document.getElementById("email").focus();
    }

    function submitForm() {
      if (state.busy) return;
      var email = document.getElementById("email").value.trim();
      // Strip accidental surrounding whitespace: a pasted "admin12345 " would
      // otherwise fail with a message that looks like a wrong password.
      var password = document.getElementById("password").value.trim();
      var fullName = state.mode === "register"
        ? (document.getElementById("fullName") || {}).value
        : null;
      state.error = "";
      state.busy = true;
      draw();

      var path = state.mode === "login" ? "/auth/login" : "/auth/register";
      var payload = { email: email, password: password };
      if (state.mode === "register") { payload.full_name = fullName || ""; payload.role = "student"; }

      App.api.post(path, payload)
        .then(function (data) {
          App.store.token = data.access_token;
          App.store.user = data.user;
          App.store.password = password;
          App.toast("Xush kelibsiz, " + data.user.full_name, "success");
          navigate("#/tests");
        })
        .catch(function (err) {
          state.busy = false;
          state.error = err.message || "Kirishda xatolik";
          draw();
        });
    }
  }

  function point(title, text) {
    return el("div", { class: "auth-point" }, [
      el("span", { class: "dot" }),
      el("div", {}, [el("b", { text: title }), el("span", { text: text })]),
    ]);
  }

  global.Pages = global.Pages || {};
  global.Pages.auth = { render: render };
})(window);
