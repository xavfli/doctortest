/* Exam runner: question navigation, timer, answer selection and submit. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;
  var KEYS = ["A", "B", "C", "D", "E", "F"];

  var session = null;   // { attempt, index, answers, flags, timerId }
  var host = null;
  var navigate = null;

  function open(attempt, nav) {
    session = {
      attempt: attempt,
      index: 0,
      answers: {},
      flags: {},
      timerId: null,
      remaining: attempt.time_limit_minutes * 60,
    };
    (attempt.questions || []).forEach(function (q) {
      if (q.selected_index !== null && q.selected_index !== undefined) {
        session.answers[q.question_id] = q.selected_index;
      }
    });
    if (nav) navigate = nav;
    global.location.hash = "#/run/" + attempt.id;
    draw();
    startTimer();
  }

  function current() {
    var qs = session.attempt.questions || [];
    return qs[session.index];
  }

  function startTimer() {
    stopTimer();
    session.timerId = setInterval(function () {
      session.remaining -= 1;
      var box = document.getElementById("qTimer");
      if (box) {
        box.textContent = App.fmtDuration(session.remaining);
        box.className = "q-timer" +
          (session.remaining <= 60 ? " danger" : session.remaining <= 300 ? " warn" : "");
      }
      if (session.remaining <= 0) {
        stopTimer();
        submit(true);
      }
    }, 1000);
  }

  function stopTimer() {
    if (session && session.timerId) {
      clearInterval(session.timerId);
      session.timerId = null;
    }
  }

  function draw() {
    var view = document.getElementById("view");
    if (!view || !session) return;
    var q = current();
    if (!q) { submit(true); return; }
    var reveal = session.attempt.mode === "practice" || session.attempt.status !== "in_progress";
    view.innerHTML = "";
    host = el("div", { class: "runner-grid" }, [
      el("div", { class: "q-card" }, [
        el("div", { class: "q-head" }, [
          el("span", {
            class: "q-num",
            text: "Savol " + (session.index + 1) + " / " + session.attempt.total_questions,
          }),
          el("span", {
            id: "qTimer",
            class: "q-timer" + (session.remaining <= 60 ? " danger" : session.remaining <= 300 ? " warn" : ""),
            text: App.fmtDuration(session.remaining),
          }),
        ]),
        el("div", { class: "q-text", text: q.text }),
        optionList(q, reveal),
        el("div", { class: "runner-foot" }, [
          el("button", {
            text: "◀ Oldingi",
            disabled: session.index === 0,
            onclick: function () { go(session.index - 1); },
          }),
          el("div", { class: "row" }, [
            el("button", {
              class: "ghost sm",
              text: session.flags[q.question_id] ? "⚑ Belgilangan" : "⚐ Belgilash",
              onclick: function () {
                session.flags[q.question_id] = !session.flags[q.question_id];
                draw();
              },
            }),
            !reveal ? el("button", {
              class: "sm",
              text: "Javobni ko‘rsatish",
              onclick: function () {
                session.attempt.questions[session.index].revealed = true;
                draw();
              },
            }) : null,
          ]),
          el("button", {
            class: "primary",
            text: session.index === session.attempt.total_questions - 1 ? "Topshirish ✓" : "Keyingi ▶",
            onclick: function () {
              if (session.index === session.attempt.total_questions - 1) submit(false);
              else go(session.index + 1);
            },
          }),
        ]),
      ]),
      sidePanel(q),
    ]);
    view.appendChild(host);
  }

  function optionList(q, reveal) {
    var list = el("div", { class: "opt-list" });
    var shown = q.revealed || (q.is_correct !== null && q.is_correct !== undefined) ||
      (q.answer_index !== null && q.answer_index !== undefined && q.is_gradable === false);
    var isPractice = session.attempt.mode === "practice";
    var showResult = isPractice || (reveal && (q.revealed || q.is_correct !== null));

    q.options.forEach(function (text, i) {
      var chosen = session.answers[q.question_id] === i;
      var cls = "opt";
      if (showResult && q.answer_index !== null && q.answer_index !== undefined) {
        if (i === q.answer_index) cls += " correct";
        else if (chosen) cls += " wrong";
      } else if (chosen) {
        cls += " selected";
      }
      list.appendChild(el("button", {
        class: cls,
        onclick: function () {
          if (session.attempt.status !== "in_progress") return;
          session.answers[q.question_id] = i;
          if (isPractice) {
            var right = q.answer_index;
            q.answer_index = i;
            q.is_correct = right === null || right === undefined ? null : right === i;
            q.answer_index = right;
          }
          draw();
        },
      }, [
        el("span", { class: "key", text: KEYS[i] || String(i + 1) }),
        el("span", { text: text }),
      ]));
    });

    if (isPractice || (q.revealed && q.answer_index !== null && q.answer_index !== undefined)) {
      if (!q.is_gradable) {
        list.appendChild(el("div", {
          class: "opt-note",
          text: "Bu savol uchun javob kalitida mavjud emas — u ballga hisoblanmaydi.",
        }));
      } else {
        list.appendChild(el("div", {
          class: "opt-note",
          text: "To‘g‘ri javob: " + (KEYS[q.answer_index] || (q.answer_index + 1)) +
            (q.notes ? " · " + q.notes : ""),
        }));
      }
    }
    return list;
  }

  function sidePanel(q) {
    var grid = el("div", { class: "nav-grid" });
    (session.attempt.questions || []).forEach(function (item, i) {
      var cls = "nav-btn";
      if (i === session.index) cls += " current";
      if (session.answers[item.question_id] !== undefined) cls += " answered";
      if (session.flags[item.question_id]) cls += " flagged";
      grid.appendChild(el("button", {
        class: cls,
        text: String(i + 1),
        onclick: function () { go(i); },
      }));
    });

    var answered = Object.keys(session.answers).length;
    var total = session.attempt.total_questions;
    return el("div", { class: "side-panel" }, [
      el("div", { class: "card" }, [
        el("h3", { text: session.attempt.title }),
        el("p", { class: "small muted", text: session.attempt.block_number + "-bo‘lim" }),
        el("div", { class: "divider" }),
        el("div", { class: "progress-label", text: answered + " / " + total + " javob berilgan" }),
        el("div", { class: "progress" }, [
          el("i", { style: "width:" + Math.round((answered / total) * 100) + "%" }),
        ]),
        el("div", { class: "divider" }),
        grid,
        el("div", { class: "row mt" }, [
          el("button", {
            class: "primary block",
            text: "Topshirish",
            onclick: function () { confirmSubmit(); },
          }),
        ]),
        /* Leaving the runner on purpose. The attempt is marked "abandoned" on the
           server so it is graded with the answers given so far instead of
           staying "in progress" forever; abandoned attempts are not listed in
           the history (that shows submitted ones only), so the student returns
           to the page they came from. */
        el("div", { class: "row mt" }, [
          el("button", {
            class: "ghost block back-btn",
            text: "Testni tashlab chiqish",
            onclick: function () { confirmAbandon(); },
          }),
        ]),
      ]),
    ]);
  }

  function go(i) {
    var total = session.attempt.total_questions;
    if (i < 0 || i >= total) return;
    session.index = i;
    draw();
  }

  function confirmSubmit() {
    var unanswered = session.attempt.total_questions - Object.keys(session.answers).length;
    var msg = unanswered > 0
      ? unanswered + " ta savolga javob bermadingiz. topshirasizmi?"
      : "Topshirasizmi?";
    if (window.confirm(msg)) submit(false);
  }

  /* Leaving the runner on purpose. The attempt is marked abandoned so it is
     graded with the answers given so far and does not stay "in progress" on the
     server; the student then lands back on the page they came from. */
  function confirmAbandon() {
    var msg = "Testni tashlab chiqasizmi? Berilgan javoblar bo‘yicha baholanadi.";
    if (!window.confirm(msg)) return;
    var id = session.attempt.id;
    stopTimer();
    App.api.post("/attempts/" + id + "/abandon", {})
      .then(function () {
        session = null;
        App.toast("Test tashlab qoldirildi", "error");
        var target = App.previousRoute() || "#/tests";
        if (navigate) navigate(target);
        else global.location.hash = target;
      })
      .catch(function (err) {
        App.toast(err.message, "error");
        startTimer();
      });
  }

  function submit(auto) {
    if (!session) return;
    stopTimer();
    var payload = {
      answers: (session.attempt.questions || []).map(function (q) {
        return {
          question_id: q.question_id,
          position: q.position,
          selected_index: session.answers[q.question_id] === undefined
            ? null : session.answers[q.question_id],
          time_spent_seconds: 0,
        };
      }),
      time_spent_seconds: session.attempt.time_limit_minutes * 60 - session.remaining,
    };
    var btn = document.querySelector(".side-panel button.primary");
    if (btn) { btn.disabled = true; btn.textContent = "Yuborilmoqda…"; }
    App.api.post("/attempts/" + session.attempt.id + "/submit", payload)
      .then(function (result) {
        session = null;
        if (auto) App.toast("Vaqt tugadi — urinish avtomatik topshirildi", "error");
        if (navigate) navigate("#/result/" + result.id);
        else global.location.hash = "#/result/" + result.id;
      })
      .catch(function (err) {
        App.toast(err.message, "error");
        if (btn) { btn.disabled = false; btn.textContent = "Topshirish"; }
        startTimer();
      });
  }

  function resume(attemptId) {
    return App.api.get("/attempts/" + attemptId)
      .then(function (attempt) { open(attempt); });
  }

  function leave() {
    stopTimer();
    session = null;
  }

  global.Runner = { open: open, resume: resume, leave: leave, has: function () { return !!session; } };
})(window);
