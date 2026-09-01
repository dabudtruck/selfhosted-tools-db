(function () {
  "use strict";

  var RESULT_CAP = 150;

  var state = {
    all: [],
    query: "",
    category: "all",
    catCounts: {},
  };

  var el = {
    q: document.getElementById("q"),
    chips: document.getElementById("chips"),
    countDial: document.getElementById("count-dial"),
    results: document.getElementById("results"),
    meta: document.getElementById("result-meta"),
  };

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var REPO = "dabudtruck/selfhosted-tools-db";

  function correctionUrl(tool) {
    var title = "Correction: " + tool.name;
    var body = [
      "**Tool:** " + tool.name,
      "**Current category:** " + tool.category,
      "**Current description:** " + (tool.description || "(none on record)"),
      "**Current URL:** " + (tool.url || "(none on record)"),
      "",
      "**What's wrong, or what should change:**",
      "",
      "",
      "_Opened from the Homelab Tools site._",
    ].join("\n");
    return (
      "https://github.com/" + REPO + "/issues/new?labels=correction&title=" +
      encodeURIComponent(title) + "&body=" + encodeURIComponent(body)
    );
  }

  function categoryLabel(cat) {
    if (cat === "other") return "Uncategorized";
    if (cat === "ai") return "AI";
    return cat.charAt(0).toUpperCase() + cat.slice(1).replace(/-/g, " ");
  }

  function computeCatCounts(tools) {
    var counts = {};
    tools.forEach(function (t) {
      counts[t.category] = (counts[t.category] || 0) + 1;
    });
    return counts;
  }

  function renderChips() {
    var entries = Object.keys(state.catCounts)
      .map(function (c) { return [c, state.catCounts[c]]; })
      .sort(function (a, b) { return b[1] - a[1]; });

    var html = '<span class="chip' + (state.category === "all" ? " active" : "") +
      '" data-cat="all">All <span class="count">' + state.all.length + "</span></span>";

    entries.forEach(function (entry) {
      var cat = entry[0], count = entry[1];
      html += '<span class="chip' + (state.category === cat ? " active" : "") +
        '" data-cat="' + escapeHtml(cat) + '">' + escapeHtml(categoryLabel(cat)) +
        ' <span class="count">' + count + "</span></span>";
    });

    el.chips.innerHTML = html;
  }

  function score(tool, q) {
    var name = tool.name.toLowerCase();
    var desc = (tool.description || "").toLowerCase();
    if (!q) return 1;
    if (name === q) return 100;
    if (name.indexOf(q) === 0) return 80;
    if (name.indexOf(q) !== -1) return 60;
    if (desc.indexOf(q) !== -1) return 30;
    return 0;
  }

  function search() {
    var q = state.query.trim().toLowerCase();
    var pool = state.all;

    if (state.category !== "all") {
      pool = pool.filter(function (t) { return t.category === state.category; });
    }

    var scored = pool
      .map(function (t) { return { t: t, s: score(t, q) }; })
      .filter(function (x) { return x.s > 0; });

    scored.sort(function (a, b) {
      if (b.s !== a.s) return b.s - a.s;
      if (b.t.mentionCount !== a.t.mentionCount) return b.t.mentionCount - a.t.mentionCount;
      return a.t.name.localeCompare(b.t.name);
    });

    return scored.map(function (x) { return x.t; });
  }

  function renderMentionList(mentions) {
    return mentions
      .slice()
      .reverse()
      .map(function (m) {
        var href = m.url ? escapeHtml(m.url) : "#";
        return (
          '<a href="' + href + '" target="_blank" rel="noopener">' +
          '<span class="show-tag">' + escapeHtml(m.show) + " #" + escapeHtml(m.episode) + "</span> — " +
          escapeHtml(m.title || "") +
          (m.date ? ' <span style="opacity:.6">(' + escapeHtml(m.date) + ")</span>" : "") +
          "</a>"
        );
      })
      .join("");
  }

  function renderResults() {
    var matches = search();
    var shown = matches.slice(0, RESULT_CAP);

    el.meta.innerHTML =
      "<strong>" + matches.length + "</strong> tool" + (matches.length === 1 ? "" : "s") +
      (state.query.trim() ? ' matching "' + escapeHtml(state.query.trim()) + '"' : "") +
      (state.category !== "all" ? " in " + escapeHtml(categoryLabel(state.category)) : "") +
      (state.query.trim() === "" ? " · sorted by most-discussed" : "");

    if (shown.length === 0) {
      el.results.innerHTML = '<div class="empty">No matches. Try a broader term — the show-notes descriptions aren’t exhaustive.</div>';
      return;
    }

    var html = shown
      .map(function (t) {
        var url = t.url ? escapeHtml(t.url) : "#";
        return (
          '<div class="row">' +
            '<div class="row-main">' +
              '<div class="row-title">' +
                '<a class="name" href="' + url + '" target="_blank" rel="noopener">' + escapeHtml(t.name) + "</a>" +
                '<span class="cat-tag">' + escapeHtml(categoryLabel(t.category)) + "</span>" +
                '<a class="fix-link" href="' + correctionUrl(t) + '" target="_blank" rel="noopener">Suggest a fix ↗</a>' +
              "</div>" +
              '<p class="row-desc">' + escapeHtml(t.description) + "</p>" +
            "</div>" +
            '<button class="mentions" type="button" aria-expanded="false">' +
              '<span class="big">' + t.mentionCount + "×</span>mentioned" +
            "</button>" +
            '<div class="mention-list">' + renderMentionList(t.mentions) + "</div>" +
          "</div>"
        );
      })
      .join("");

    el.results.innerHTML = html;

    if (matches.length > RESULT_CAP) {
      el.results.insertAdjacentHTML(
        "beforeend",
        '<div class="more-note">' + (matches.length - RESULT_CAP) + " more match" +
          (matches.length - RESULT_CAP === 1 ? "" : "es") + " not shown — narrow your search or pick a category to see them.</div>"
      );
    }
  }

  el.results.addEventListener("click", function (e) {
    var btn = e.target.closest(".mentions");
    if (!btn) return;
    var row = btn.closest(".row");
    row.classList.toggle("open");
    btn.setAttribute("aria-expanded", row.classList.contains("open") ? "true" : "false");
  });

  el.chips.addEventListener("click", function (e) {
    var chip = e.target.closest(".chip");
    if (!chip) return;
    state.category = chip.getAttribute("data-cat");
    renderChips();
    renderResults();
  });

  var debounceTimer;
  el.q.addEventListener("input", function () {
    state.query = el.q.value;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(renderResults, 60);
  });

  fetch("data/tools.json")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      state.all = data;
      state.catCounts = computeCatCounts(data);
      el.countDial.textContent = data.length.toLocaleString();
      renderChips();
      renderResults();
    })
    .catch(function (err) {
      el.results.innerHTML = '<div class="empty">Couldn’t load the tool catalog (' + escapeHtml(err.message) + "). Try refreshing.</div>";
    });
})();
