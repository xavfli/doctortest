/* Attempt history and profile pages. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;

  function renderHistory(view, navigate) {
    var host = el("div");
    view.appendChild(host);
    host.innerHTML = '<div class="card"><span class="spinner"></span> Yuklanmoqda…</div>';

    App.api.get("/attempts/history", { limit: 100 })
      .then(function (rows) {
        host.innerHTML = "";
        host.appendChild(el("div", { class: "page-head row-between" }, [
          el("h1", { text: "Urinishlar tarixi" }),
          App.backButton(navigate, "#/tests"),
        ]));
        if (!rows.length) {
          host.appendChild(el("div", { class: "card empty", text: "Hali urinish yo‘q." }));
          return;
        }
        var table = el("table", { class: "history" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "#" }), el("th", { text: "Test" }),
            el("th", { text: "Bo‘lim" }), el("th", { text: "Natija" }),
            el("th", { text: "To‘g‘ri" }), el("th", { text: "Vaqt" }),
            el("th", { text: "Sana" }), el("th", { text: "" }),
          ])]),
        ]);
        var tbody = el("tbody");
        rows.forEach(function (r) {
          tbody.appendChild(el("tr", {}, [
            el("td", { class: "mono", text: String(r.id) }),
            el("td", { text: r.title_snapshot }),
            el("td", { text: r.block_number + "-bo‘lim" }),
            el("td", { html: App.scoreBadge(r.score_percent, r.passed) }),
            el("td", { text: r.correct_answers + " / " + r.total_questions }),
            el("td", { text: App.fmtDuration(r.time_spent_seconds) }),
            el("td", { class: "small muted", text: App.fmtDate(r.started_at) }),
            el("td", { class: "actions" }, [
              el("button", {
                class: "sm",
                text: "Ko‘rish",
                onclick: function () { navigate("#/result/" + r.id); },
              }),
            ]),
          ]));
        });
        table.appendChild(tbody);
        host.appendChild(el("div", { class: "card" }, [
          el("div", { class: "table-wrap" }, [table]),
        ]));
      })
      .catch(function (err) {
        host.innerHTML = '<div class="alert error">' + App.escapeHtml(err.message) + "</div>";
      });
  }

  function renderProfile(view, navigate) {
    var user = App.store.user || {};
    view.appendChild(el("div", { class: "page-head row-between" }, [
      el("h1", { text: "Profil" }),
      App.backButton(navigate, "#/tests"),
    ]));
    var card = el("div", { class: "card" }, [
      el("div", { class: "kv" }, [el("span", { text: "Ism" }), el("span", { text: user.full_name || "—" })]),
      el("div", { class: "kv" }, [el("span", { text: "E-pochta" }), el("span", { class: "mono", text: user.email || "—" })]),
      el("div", { class: "kv" }, [el("span", { text: "Rol" }), el("span", { class: "badge info", text: user.role || "—" })]),
      el("div", { class: "kv" }, [el("span", { text: "Urinishlar" }), el("span", { text: String(user.attempts_count || 0) })]),
      el("div", { class: "kv" }, [
        el("span", { text: "O‘rtacha ball" }),
        el("span", { text: user.average_score === null || user.average_score === undefined ? "—" : user.average_score + "%" }),
      ]),
    ]);
    view.appendChild(card);

    var pw = el("div", { class: "card" }, [
      el("h2", { text: "Parolni o‘zgartirish" }),
      el("div", { class: "field" }, [
        el("label", { for: "newPass", text: "Yangi parol" }),
        App.passwordInput({ id: "newPass", autocomplete: "new-password" }),
      ]),
      el("button", {
        class: "primary",
        text: "Saqlash",
        onclick: function () {
          var value = document.getElementById("newPass").value;
          if (value.length < 8) { App.toast("Parol kamida 8 ta belgidan iborat bo‘lishi kerak", "error"); return; }
          App.api.post("/auth/change-password", { current_password: App.store.password || "", new_password: value })
            .then(function () { App.toast("Parol yangilandi", "success"); document.getElementById("newPass").value = ""; })
            .catch(function (e) { App.toast(e.message, "error"); });
        },
      }),
    ]);
    view.appendChild(pw);
  }

  global.Pages = global.Pages || {};
  global.Pages.history = { render: renderHistory };
  global.Pages.profile = { render: renderProfile };
})(window);
