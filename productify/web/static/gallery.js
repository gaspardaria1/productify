/**
 * Productify — gallery page logic.
 *
 * Fetches GET /api/gallery, renders a card grid with tone filter chips and a
 * big "founded today" counter, and auto-refreshes every 10s so the wall
 * fills up live during a demo.
 */
(function () {
  "use strict";

  var grid = document.getElementById("gallery-grid");
  var statusBox = document.getElementById("gallery-status");
  var statusMessage = document.getElementById("gallery-status-message");
  var retryBtn = document.getElementById("gallery-retry-btn");
  var heroNumber = document.getElementById("hero-counter-number");
  var heroLabel = document.getElementById("hero-counter-label");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));

  var REFRESH_MS = 10000;
  var SKELETON_COUNT = 6;
  var PREFERS_REDUCED_MOTION =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var TONE_LABELS = window.PRODUCTIFY_TONE_LABELS || {
    vc: "Silicon Valley Startup",
    luxury: "Luxury Brand",
    infomercial: "Late-Night Infomercial",
    kickstarter: "Kickstarter Campaign",
  };

  var items = [];
  var previousSlugs = new Set();
  var firstLoadDone = false;
  var currentFilter = "all";

  // ---------- relative time ----------
  function relativeTime(iso) {
    var then = new Date(iso).getTime();
    if (isNaN(then)) return "";
    var diffSec = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (diffSec < 5) return "just now";
    if (diffSec < 60) return diffSec + "s ago";
    var min = Math.round(diffSec / 60);
    if (min < 60) return min + (min === 1 ? " minute ago" : " minutes ago");
    var hr = Math.round(min / 60);
    if (hr < 24) return hr + (hr === 1 ? " hour ago" : " hours ago");
    var day = Math.round(hr / 24);
    return day + (day === 1 ? " day ago" : " days ago");
  }

  function isToday(iso) {
    var d = new Date(iso);
    var now = new Date();
    return d.toDateString() === now.toDateString();
  }

  // ---------- skeleton ----------
  function renderSkeleton() {
    grid.classList.remove("is-empty");
    grid.innerHTML = "";
    for (var i = 0; i < SKELETON_COUNT; i++) {
      var card = document.createElement("div");
      card.className = "gallery-card skeleton";

      var thumb = document.createElement("div");
      thumb.className = "thumb-frame skeleton-block";
      card.appendChild(thumb);

      var body = document.createElement("div");
      body.className = "gallery-card-body";
      body.appendChild(makeSkeletonLine("w-70"));
      body.appendChild(makeSkeletonLine("w-40"));
      body.appendChild(makeSkeletonLine("w-90"));
      card.appendChild(body);

      grid.appendChild(card);
    }
  }

  function makeSkeletonLine(widthClass) {
    var line = document.createElement("div");
    line.className = "skeleton-line " + widthClass;
    return line;
  }

  // ---------- card building (DOM APIs, not innerHTML, so brand/tagline
  // text from the model can never be interpreted as markup) ----------
  function buildCard(item) {
    var toneLabel = TONE_LABELS[item.tone] || item.tone;

    var article = document.createElement("article");
    article.className = "gallery-card";
    article.dataset.slug = item.slug;

    var thumbFrame = document.createElement("div");
    thumbFrame.className = "thumb-frame";
    var img = document.createElement("img");
    img.loading = "lazy";
    img.alt = "";
    // A missing thumbnail must not put a broken-image glyph on the projector.
    img.addEventListener("error", function () {
      img.hidden = true;
      thumbFrame.classList.add("thumb-frame-empty");
    });
    if (item.thumb_url) img.src = item.thumb_url;
    else thumbFrame.classList.add("thumb-frame-empty");
    thumbFrame.appendChild(img);
    article.appendChild(thumbFrame);

    var body = document.createElement("div");
    body.className = "gallery-card-body";

    var top = document.createElement("div");
    top.className = "gallery-card-top";

    var h3 = document.createElement("h3");
    h3.className = "gallery-brand";
    h3.textContent = item.brand || "Unnamed";
    top.appendChild(h3);

    var badge = document.createElement("span");
    badge.className = "tone-badge tone-badge-" + item.tone;
    badge.textContent = toneLabel;
    top.appendChild(badge);

    body.appendChild(top);

    var tagline = document.createElement("p");
    tagline.className = "gallery-tagline";
    tagline.textContent = item.tagline || "";
    body.appendChild(tagline);

    var time = document.createElement("p");
    time.className = "gallery-time";
    time.textContent = relativeTime(item.created_at);
    body.appendChild(time);

    var actions = document.createElement("div");
    actions.className = "gallery-actions";

    var openLink = document.createElement("a");
    // PitchSummary calls it pitch_url (contracts/api.md); fall back to the slug.
    openLink.href = item.pitch_url || "/pitch/" + encodeURIComponent(item.slug);
    openLink.target = "_blank";
    openLink.rel = "noopener";
    openLink.className = "btn btn-ghost btn-small";
    openLink.textContent = "Open";
    actions.appendChild(openLink);

    var dlLink = document.createElement("a");
    dlLink.href = item.download_url || "/pitch/" + encodeURIComponent(item.slug) + "/download";
    dlLink.setAttribute("download", "");
    dlLink.className = "btn btn-ghost btn-small";
    dlLink.textContent = "Download .html";
    actions.appendChild(dlLink);

    body.appendChild(actions);
    article.appendChild(body);
    return article;
  }

  // Cards already on screen, by slug, so a refresh can reuse them.
  var cardBySlug = Object.create(null);

  // Reconciles the grid against `items` instead of clearing innerHTML. The
  // gallery refreshes every 10s while projected; rebuilding every card made
  // thumbnails re-decode and flash, disturbed scrolling, and dropped keyboard
  // focus from Open/Download links mid-interaction.
  function renderGrid() {
    var filtered =
      currentFilter === "all" ? items : items.filter(function (i) { return i.tone === currentFilter; });

    if (filtered.length === 0) {
      cardBySlug = Object.create(null);
      grid.innerHTML = "";
      grid.classList.add("is-empty");
      var empty = document.createElement("div");
      empty.className = "empty-state";
      var emoji = document.createElement("div");
      emoji.className = "empty-emoji";
      emoji.textContent = "🌱";
      var text = document.createElement("p");
      text.textContent = items.length === 0 ? "No startups founded yet" : "No pitches with this tone yet";
      empty.appendChild(emoji);
      empty.appendChild(text);
      grid.appendChild(empty);
      return;
    }

    // Drop the empty state / skeletons if they are what's currently in there.
    if (grid.classList.contains("is-empty") || grid.querySelector(".skeleton")) {
      grid.innerHTML = "";
      cardBySlug = Object.create(null);
    }
    grid.classList.remove("is-empty");

    var wanted = Object.create(null);
    filtered.forEach(function (item) {
      wanted[item.slug] = true;
    });

    // Remove cards that are gone or filtered out.
    Object.keys(cardBySlug).forEach(function (slug) {
      if (!wanted[slug]) {
        var stale = cardBySlug[slug];
        if (stale && stale.parentNode) stale.parentNode.removeChild(stale);
        delete cardBySlug[slug];
      }
    });

    // Insert new cards and fix ordering, reusing existing nodes untouched.
    filtered.forEach(function (item, index) {
      var card = cardBySlug[item.slug];
      if (!card) {
        card = buildCard(item);
        cardBySlug[item.slug] = card;
        if (firstLoadDone && !previousSlugs.has(item.slug)) {
          card.classList.add("is-new");
          var cleanupDelay = PREFERS_REDUCED_MOTION ? 2200 : 1800;
          setTimeout(function () {
            card.classList.remove("is-new");
          }, cleanupDelay);
        }
      }
      if (grid.children[index] !== card) {
        grid.insertBefore(card, grid.children[index] || null);
      }
    });
  }

  function updateCounts() {
    var counts = { all: items.length, vc: 0, luxury: 0, infomercial: 0, kickstarter: 0 };
    items.forEach(function (i) {
      if (counts[i.tone] !== undefined) counts[i.tone]++;
    });
    chips.forEach(function (chip) {
      var tone = chip.dataset.tone;
      var countEl = chip.querySelector(".chip-count");
      if (countEl) countEl.textContent = String(counts[tone] || 0);
    });
  }

  // Counts every pitch in the gallery, matching the "All" chip. Filtering to
  // today's date made the two numbers disagree: a pre-generated backup gallery
  // or a fixture-seeded pitch (the committed bundles carry a fixed created_at)
  // showed visible cards while the big counter read 0.
  function updateHeroCounter() {
    heroNumber.textContent = String(items.length);
    if (heroLabel) {
      var anyOlder = items.some(function (i) {
        return i.created_at && !isToday(i.created_at);
      });
      heroLabel.textContent = anyOlder
        ? items.length === 1 ? "company founded" : "companies founded"
        : items.length === 1 ? "company founded today" : "companies founded today";
    }
  }

  function showStatus(message) {
    statusBox.hidden = false;
    statusMessage.textContent = message;
  }
  function hideStatus() {
    statusBox.hidden = true;
    statusMessage.textContent = "";
  }

  // On the very first load, a skeleton alone would look like it's stuck
  // loading forever once the fetch has actually failed — so replace it with
  // an explicit message too. On later (auto-refresh) failures we leave
  // already-rendered cards alone and only show the banner above them.
  function renderGridError(message) {
    if (firstLoadDone) return;
    grid.classList.add("is-empty");
    grid.innerHTML = "";
    var wrap = document.createElement("div");
    wrap.className = "empty-state";
    var emoji = document.createElement("div");
    emoji.className = "empty-emoji";
    emoji.textContent = "⚠️";
    var text = document.createElement("p");
    text.textContent = message;
    wrap.appendChild(emoji);
    wrap.appendChild(text);
    grid.appendChild(wrap);
  }

  function fetchGallery() {
    return fetch("/api/gallery")
      .catch(function () {
        var msg = "Can't reach the server. Retrying automatically…";
        showStatus(msg);
        renderGridError(msg);
        return null;
      })
      .then(function (resp) {
        if (!resp) return null;
        if (!resp.ok) {
          var msg = "The gallery is temporarily unavailable (server said " + resp.status + "). Retrying automatically…";
          showStatus(msg);
          renderGridError(msg);
          return null;
        }
        return resp.json().catch(function () {
          var msg = "Got a strange response from the server. Retrying automatically…";
          showStatus(msg);
          renderGridError(msg);
          return null;
        });
      })
      .then(function (data) {
        if (data === null) return;
        hideStatus();
        // GET /api/gallery answers {count, items} per contracts/api.md.
        if (data && Array.isArray(data.items)) items = data.items.slice();
        else if (Array.isArray(data)) items = data.slice();
        else items = [];
        // Newest first is guaranteed by the API, but sort defensively.
        items.sort(function (a, b) {
          return new Date(b.created_at) - new Date(a.created_at);
        });
        updateCounts();
        updateHeroCounter();
        renderGrid();
        previousSlugs = new Set(items.map(function (i) { return i.slug; }));
        firstLoadDone = true;
      });
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      chips.forEach(function (c) {
        c.classList.remove("is-active");
        c.setAttribute("aria-pressed", "false");
      });
      chip.classList.add("is-active");
      chip.setAttribute("aria-pressed", "true");
      currentFilter = chip.dataset.tone;
      renderGrid();
    });
  });

  retryBtn.addEventListener("click", function () {
    fetchGallery();
  });

  renderSkeleton();
  fetchGallery();
  setInterval(fetchGallery, REFRESH_MS);
})();
