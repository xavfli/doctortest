/* Result screen: score summary and a per-question review. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;
  var KEYS = ["A", "B", "C", "D", "E", "F"];

  /* Signature matches every other page: renderOnly() always calls
     page.render(view, navigate, args), with the route parameters in `args`.
     Taking them in a different order here made `attemptId` receive the
     navigate function, and the request went out as "/attempts/function
     navigate..." which the server rejected as an invalid integer. */
  function renderResult(view, navigate, args) {
    var attemptId = (args && args[0]) || "";
    if (!attemptId) {
      view.appendChild(el("div", { class: "card" }, [
        el("div", { class: "alert error", text: "Natija topilmadi" }),
      ]));
      return;
    }

    var host = el("div", { class: "card" }, [
      el("div", { class: "row" }, [el("span", { class: "spinner" }), " Natija yuklanmoqda…"]),
    ]);
    view.appendChild(host);

    App.api.get("/attempts/" + encodeURIComponent(attemptId))
      .then(function (attempt) { draw(attempt); })
      .catch(function (err) {
        host.innerHTML = "";
        host.appendChild(el("div", { class: "alert error", text: err.message }));
      });

    function draw(attempt) {
      host.innerHTML = "";
      var pct = attempt.score_percent || 0;
      var passed = attempt.passed;

      var ring = el("div", { class: "score-ring", style: "--pct:" + pct }, [
        el("span", { class: "val", text: pct + "%" }),
      ]);

      host.appendChild(el("div", { class: "result-hero" }, [
        ring,
        el("div", { class: "grow" }, [
          el("h1", { text: attempt.title }),
          el("p", { class: "muted", text: attempt.block_number + "-bo‘lim · " + attempt.total_questions + " savol" }),
          el("div", { class: "row" }, [
            passed ? el("span", { class: "badge ok", text: "O‘tdi" }) : el("span", { class: "badge bad", text: "O‘tmadi" }),
            el("span", { class: "badge info", text: attempt.correct_answers + " / " + attempt.total_questions + " to‘g‘ri" }),
            el("span", { class: "badge neutral", text: "Vaqt: " + App.fmtDuration(attempt.time_spent_seconds) }),
          ]),
        ]),
        el("div", { class: "row" }, [
          /* Back sits next to "Yana o'tish" so both ways out are visible
             together; it returns to the page the student came from and falls
             back to the test list when the result was opened directly. */
          App.backButton(navigate, "#/tests"),
          el("button", { class: "primary", text: "Yana o‘tish", onclick: function () { navigate("#/tests"); } }),
        ]),
      ]));

      host.appendChild(el("div", { class: "divider" }));
      host.appendChild(el("h2", { text: "Savollar bo‘yicha ko‘rib chiqish" }));

      (attempt.questions || []).forEach(function (q) {
        host.appendChild(reviewItem(q));
      });
    }

    function reviewItem(q) {
      var graded = q.is_gradable !== false;
      var skipped = q.selected_index === null || q.selected_index === undefined;
      var cls = "review-item " + (!graded ? "skipped" : skipped ? "skipped" : q.is_correct ? "ok" : "bad");
      var badge = !graded
        ? el("span", { class: "badge neutral", text: "javobsiz" })
        : skipped
          ? el("span", { class: "badge warn", text: "javobsiz qoldirilgan" })
          : q.is_correct
            ? el("span", { class: "badge ok", text: "to‘g‘ri" })
            : el("span", { class: "badge bad", text: "noto‘g‘ri" });

      var opts = el("div", { class: "review-opts" });
      (q.options || []).forEach(function (text, i) {
        var oc = "";
        var mark = "";
        if (q.answer_index !== null && q.answer_index !== undefined) {
          if (i === q.answer_index) { oc = "correct"; mark = "✓"; }
          else if (i === q.selected_index) { oc = "chosen-wrong"; mark = "✕"; }
        } else if (i === q.selected_index) {
          mark = "•";
        }
        opts.appendChild(el("div", { class: "review-opt " + oc }, [
          el("span", { class: "mark", text: mark }),
          el("span", { text: (KEYS[i] || (i + 1)) + ". " + text }),
        ]));
      });

      return el("div", { class: cls }, [
        el("div", { class: "row-between review-q" }, [
          el("span", { text: (q.position + 1) + ". " + q.text }),
          badge,
        ]),
        opts,
        q.notes ? el("div", { class: "review-note", text: "Izoh: " + q.notes }) : null,
      ]);
    }
  }

  global.Pages = global.Pages || {};
  global.Pages.result = { render: renderResult };
})(window);
