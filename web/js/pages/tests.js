/* Test list + dashboard: pick an exam, a block and a mode, then start. */
(function (global) {
  "use strict";
  var App = global.App;
  var el = App.el;

  function render(view, navigate) {
    var state = { exams: [], tests: [], loading: true, error: "" };
    var host = el("div");
    view.appendChild(host);
    host.innerHTML = '<div class="card"><span class="spinner"></span> Yuklanmoqda…</div>';

    App.api.get("/exams", { published_only: true })
      .then(function (exams) {
        state.exams = exams || [];
        state.tests = buildTests(state.exams);
        state.loading = false;
        draw();
      })
      .catch(function (err) {
        state.loading = false;
        state.error = err.message;
        draw();
      });

    function draw() {
      host.innerHTML = "";
      if (state.error) {
        host.appendChild(el("div", { class: "alert error", text: state.error }));
      }
      host.appendChild(el("div", { class: "page-head" }, [
        el("h1", { text: "Testlar" }),
        el("p", {
          class: "muted",
          text: "Har bir test alohida: 1-test 1–20, 2-test 21–40 savollar va " +
            "hokazo. Boshlash tugmasini bosing — test darhol boshlanadi, savollar " +
            "va javob variantlari tasodifiy tartibda beriladi.",
        }),
      ]));
      /* No resume banner: an unfinished attempt is not surfaced here. */
      var section = el("div", { class: "variant-section" }, [
        el("div", { class: "section-bar" }, [
          el("h2", { text: "Testlar (imtihon)" }),
          el("span", { class: "badge info", text: state.exams.length + " ta" }),
        ]),
      ]);

      if (state.loading) {
        section.appendChild(el("div", { class: "empty", text: "Yuklanmoqda…" }));
      } else if (!state.tests.length) {
        section.appendChild(el("div", {
          class: "empty",
          text: "Hozircha e’lon qilingan test yo‘q. Administrator bilan bog‘laning.",
        }));
      } else {
        var grid = el("div", { class: "variant-grid" });
        state.tests.forEach(function (t) {
          grid.appendChild(testCard(t, navigate));
        });
        section.appendChild(grid);
      }
      host.appendChild(section);
    }

    /* Each test is its own block of the bank: test 1 holds questions 1-20,
       test 2 holds 21-40 and so on, so a student works through the bank one
       numbered test at a time, each with its own card and start button. */
    function buildTests(exams) {
      var out = [];
      exams.forEach(function (exam) {
        var per = exam.questions_per_block || 20;
        var total = exam.question_count || 0;
        var blocks = total ? Math.ceil(total / per) : 0;
        for (var i = 1; i <= blocks; i++) {
          var from = (i - 1) * per + 1;
          var to = Math.min(i * per, total);
          out.push({
            exam: exam,
            block: i,
            title: exam.title || "Test",
            from: from,
            to: to,
            count: to - from + 1,
            per: per,
            time: exam.time_limit_minutes,
            pass: exam.pass_percent,
          });
        }
      });
      return out;
    }

    /* One card per numbered test, laid out like the reference design:
       a big title, a score ring, the key facts and a start button. Pressing
       "Boshlash" begins that test straight away — there is no settings
       dialog, so the card is the only thing a student has to interact with. */
    function testCard(t, navigate) {
      var score = t.exam.average_score;
      var ringCls = score === null || score === undefined
        ? "ring empty"
        : score >= t.pass ? "ring ok" : "ring bad";

      var startBtn = el("button", {
        class: "primary block card-start",
        type: "button",
        text: "Boshlash",
        onclick: function () { startTest(t, navigate, startBtn); },
      });

      /* --i staggers the entrance animation across the 51-card grid. */
      var card = el("div", { class: "variant-card", style: "--i:" + (t.block - 1) }, [
        el("div", { class: "variant-head" }, [
          el("div", {}, [
            el("h3", { class: "variant-title", text: t.block + "-TEST" }),
            el("div", {
              class: "variant-range",
              text: t.from + "–" + t.to + " savol",
            }),
          ]),
          el("button", {
            class: "icon-btn bookmark",
            type: "button",
            title: "Saqlash",
            "aria-label": "Saqlash",
            onclick: function (e) {
              e.currentTarget.classList.toggle("on");
            },
          }, [bookmarkIcon()]),
        ]),
        el("div", { class: "variant-body" }, [
          el("div", { class: ringCls }, [
            el("span", {
              class: "ring-label",
              text: score === null || score === undefined ? "—" : Math.round(score) + "%",
            }),
          ]),
          el("div", { class: "variant-facts" }, [
            fact("Savollar", t.count + " ta"),
            fact("Vaqt", t.time + " daqiqa"),
            fact("O‘tish chegarasi", t.pass + "%"),
            fact("Urinishlar", t.exam.attempt_count),
          ]),
        ]),
        startBtn,
      ]);
      return card;
    }

    function fact(label, value) {
      return el("div", { class: "fact" }, [
        el("span", { class: "fact-label", text: label + ":" }),
        el("b", { text: String(value) }),
      ]);
    }

    function bookmarkIcon() {
      var s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      s.setAttribute("viewBox", "0 0 24 24");
      s.setAttribute("width", "18");
      s.setAttribute("height", "18");
      s.setAttribute("fill", "none");
      s.setAttribute("stroke", "currentColor");
      s.setAttribute("stroke-width", "2");
      s.setAttribute("stroke-linecap", "round");
      s.setAttribute("stroke-linejoin", "round");
      var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", "M6 3h12v18l-6-5-6 5z");
      s.appendChild(p);
      return s;
    }

    /* Direct start: the card already names the test, so one click begins it.
       The exam's own settings decide everything else — questions and options
       are shuffled (the exam defaults), the timer and pass mark come from the
       exam, and answers are revealed after the attempt is submitted. Shuffle
       flags are sent as null so the backend keeps following the exam, which is
       what an administrator configured in the admin panel. */
    function startTest(t, navigate, btn) {
      if (btn.disabled) return;
      btn.disabled = true;
      btn.textContent = "Tayyorlanmoqda…";
      App.api.post("/attempts/start", {
        exam_id: t.exam.id,
        block_number: t.block,
        mode: "exam",
        shuffle_questions: null,
        shuffle_options: null,
      })
        .then(function (attempt) {
          global.Runner.open(attempt, navigate);
        })
        .catch(function (err) {
          App.toast(err.message, "error");
          btn.disabled = false;
          btn.textContent = "Boshlash";
        });
    }
  }

  global.Pages = global.Pages || {};
  global.Pages.tests = { render: render };
})(window);
