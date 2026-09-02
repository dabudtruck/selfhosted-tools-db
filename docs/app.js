(function () {
  "use strict";

  var RESULT_CAP = 150;

  var state = {
    all: [],
    query: "",
    category: "all",
    catCounts: {},
    fullOnly: false,
  };

  var el = {
    q: document.getElementById("q"),
    chips: document.getElementById("chips"),
    countDial: document.getElementById("count-dial"),
    results: document.getElementById("results"),
    meta: document.getElementById("result-meta"),
    sizeToggle: document.getElementById("size-toggle"),
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
    if (state.fullOnly) {
      pool = pool.filter(function (t) { return t.size === "FULL"; });
    }

    var scored = pool
      .map(function (t) { return { t: t, s: score(t, q) }; })
      .filter(function (x) { return x.s > 0; });

    scored.sort(function (a, b) {
      if (b.s !== a.s) return b.s - a.s;
      if (b.t.mentionCount !== a.t.mentionCount) return b.t.mentionCount - a.t.mentionCount;
      return a.t.name.localeCompare(b.t.name);
    });

    return scored;
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

  // When both a family's parent and one or more of its members match the
  // same search, nest the members under the parent instead of showing them
  // as separate flat rows — that's the whole fix for e.g. a "nextcloud"
  // search surfacing a dozen near-duplicate rows. A member searched on its
  // own (its parent doesn't match) still shows normally at the top level.
  // Only nests when the parent itself is a real name match (score >= 60),
  // not merely an incidental description mention — otherwise a query that
  // directly names a child (e.g. "hacs") could bury it a click deeper under
  // a parent that only turned up because its blurb happens to mention it.
  var NAME_MATCH_SCORE = 60;

  function groupFamilies(scoredList) {
    var presentParents = {};
    scoredList.forEach(function (x) {
      if (x.t.family && x.t.isFamilyParent && x.s >= NAME_MATCH_SCORE) presentParents[x.t.family] = x.t;
    });

    var topLevel = [];
    var childrenOf = {};
    scoredList.forEach(function (x) {
      var t = x.t;
      if (t.family && !t.isFamilyParent && presentParents[t.family]) {
        (childrenOf[t.family] = childrenOf[t.family] || []).push(t);
      } else {
        topLevel.push(t);
      }
    });

    return { topLevel: topLevel, childrenOf: childrenOf };
  }

  function renderFamilyList(children) {
    return children
      .slice()
      .sort(function (a, b) { return b.mentionCount - a.mentionCount || a.name.localeCompare(b.name); })
      .map(function (c) {
        var url = c.url ? escapeHtml(c.url) : "#";
        return (
          '<div class="family-item">' +
            '<a class="name" href="' + url + '" target="_blank" rel="noopener">' + escapeHtml(c.name) + "</a>" +
            '<span class="cat-tag">' + escapeHtml(categoryLabel(c.category)) + "</span>" +
            '<a class="fix-link" href="' + correctionUrl(c) + '" target="_blank" rel="noopener">Suggest a fix ↗</a>' +
            '<p class="row-desc">' + escapeHtml(c.description) + "</p>" +
          "</div>"
        );
      })
      .join("");
  }

  function renderResults() {
    var matches = search();
    var grouped = groupFamilies(matches);
    var shown = grouped.topLevel.slice(0, RESULT_CAP);

    el.meta.innerHTML =
      "<strong>" + grouped.topLevel.length + "</strong> tool" + (grouped.topLevel.length === 1 ? "" : "s") +
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
        var children = t.family && t.isFamilyParent ? grouped.childrenOf[t.family] : null;
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
            (children && children.length
              ? '<button class="family-toggle" type="button" aria-expanded="false">' +
                  "+ " + children.length + " related " + escapeHtml(t.familyLabel) + " app" + (children.length === 1 ? "" : "s") + " ↓" +
                "</button>" +
                '<div class="family-list">' + renderFamilyList(children) + "</div>"
              : "") +
          "</div>"
        );
      })
      .join("");

    el.results.innerHTML = html;

    if (grouped.topLevel.length > RESULT_CAP) {
      el.results.insertAdjacentHTML(
        "beforeend",
        '<div class="more-note">' + (grouped.topLevel.length - RESULT_CAP) + " more match" +
          (grouped.topLevel.length - RESULT_CAP === 1 ? "" : "es") + " not shown — narrow your search or pick a category to see them.</div>"
      );
    }
  }

  el.results.addEventListener("click", function (e) {
    var mentionsBtn = e.target.closest(".mentions");
    if (mentionsBtn) {
      var row = mentionsBtn.closest(".row");
      row.classList.toggle("open");
      mentionsBtn.setAttribute("aria-expanded", row.classList.contains("open") ? "true" : "false");
      return;
    }
    var famBtn = e.target.closest(".family-toggle");
    if (famBtn) {
      famBtn.classList.toggle("open");
      famBtn.setAttribute("aria-expanded", famBtn.classList.contains("open") ? "true" : "false");
      famBtn.nextElementSibling.classList.toggle("open");
    }
  });

  el.chips.addEventListener("click", function (e) {
    var chip = e.target.closest(".chip");
    if (!chip) return;
    state.category = chip.getAttribute("data-cat");
    renderChips();
    renderResults();
  });

  el.sizeToggle.addEventListener("click", function () {
    state.fullOnly = !state.fullOnly;
    el.sizeToggle.classList.toggle("on", state.fullOnly);
    el.sizeToggle.setAttribute("aria-pressed", state.fullOnly ? "true" : "false");
    state.catCounts = computeCatCounts(state.fullOnly ? state.all.filter(function (t) { return t.size === "FULL"; }) : state.all);
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
