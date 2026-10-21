/**
 * Productify — index page logic.
 *
 * Flow: take/choose a photo -> resize it client-side -> pick a tone ->
 * POST /api/pitch -> poll GET /api/pitch/{slug} until the logo is ready.
 *
 * No framework, no build step. Everything below runs as a plain script tag.
 */
(function () {
  "use strict";

  // ---------- DOM refs ----------
  var previewFrame = document.getElementById("preview-frame");
  var previewImg = document.getElementById("preview-img");
  var photoInput = document.getElementById("photo-input");
  var photoControls = document.getElementById("photo-controls");
  var chooseAnotherBtn = document.getElementById("choose-another-btn");
  var sizeNote = document.getElementById("size-note");

  var toneGrid = document.getElementById("tone-grid");

  var submitBtn = document.getElementById("submit-btn");

  var progressCard = document.getElementById("progress-card");
  var progressSteps = document.getElementById("progress-steps");

  var resultCard = document.getElementById("result-card");
  var resultBrand = document.getElementById("result-brand");
  var resultTagline = document.getElementById("result-tagline");
  var logoStatusNote = document.getElementById("logo-status-note");
  var openPitchLink = document.getElementById("open-pitch-link");
  var tryAnotherBtn = document.getElementById("try-another-btn");

  var errorCard = document.getElementById("error-card");
  var errorMessage = document.getElementById("error-message");
  var retryBtn = document.getElementById("retry-btn");

  var counterText = document.getElementById("counter-text");

  // ---------- Constants ----------
  var TONE_ORDER = window.PRODUCTIFY_TONE_ORDER || [
    "vc",
    "luxury",
    "infomercial",
    "kickstarter",
  ];
  var MAX_EDGE = 1280;
  var JPEG_QUALITY = 0.8;
  var SS_TONE_KEY = "productify_tone";
  var SS_PHOTO_KEY = "productify_photo";

  // ---------- State ----------
  var resizedBlob = null; // the Blob we actually upload
  var selectedTone = "vc";
  var inFlight = false;
  var pollTimer = null;
  var pollVisibilityHandler = null;
  var pollDone = false; // true once the logo resolved or we gave up — do not resume

  // ============================================================
  // Photo capture + client-side resize
  // ============================================================

  photoInput.addEventListener("change", function (e) {
    var file = e.target.files && e.target.files[0];
    if (file) {
      handleNewPhoto(file);
    }
  });

  chooseAnotherBtn.addEventListener("click", function () {
    photoInput.click();
  });

  function handleNewPhoto(file) {
    hideError();

    // Step 1: show the preview immediately from the original file — the
    // resize below must never delay what the user sees on screen.
    var originalSize = file.size;
    setPreviewImage(URL.createObjectURL(file));
    photoControls.hidden = false;
    sizeNote.textContent = "Original " + humanSize(originalSize) + " · preparing upload…";

    // Step 2: resize in the background before it's ever sent anywhere. The
    // submit button stays disabled for this brief window (usually well
    // under a second) so a tap can't race ahead of resizedBlob existing.
    resizedBlob = null;
    submitBtn.disabled = true;
    resizeForUpload(file).then(function (blob) {
      resizedBlob = blob;
      sizeNote.textContent =
        "Original " + humanSize(originalSize) + " → Upload " + humanSize(blob.size);
      submitBtn.disabled = false;
      savePhotoToSession(blob);
    });
  }

  var currentPreviewObjectUrl = null;
  function setPreviewImage(url) {
    if (currentPreviewObjectUrl) {
      URL.revokeObjectURL(currentPreviewObjectUrl);
    }
    currentPreviewObjectUrl = url;
    previewImg.src = url;
    previewImg.hidden = false;
    previewFrame.classList.add("has-photo");
  }

  function humanSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  // Resize to a longest edge of MAX_EDGE px, re-encode as JPEG at
  // JPEG_QUALITY. Never blocks the upload: any failure along the way falls
  // back to uploading the original file untouched.
  async function resizeForUpload(file) {
    try {
      var source = await loadDrawableSource(file);
      var scale = Math.min(1, MAX_EDGE / Math.max(source.width, source.height));
      var targetW = Math.max(1, Math.round(source.width * scale));
      var targetH = Math.max(1, Math.round(source.height * scale));
      var canvas = document.createElement("canvas");
      canvas.width = targetW;
      canvas.height = targetH;
      var ctx = canvas.getContext("2d");
      ctx.drawImage(source.drawable, 0, 0, targetW, targetH);
      if (source.cleanup) source.cleanup();
      var blob = await new Promise(function (resolve) {
        canvas.toBlob(
          function (b) {
            resolve(b);
          },
          "image/jpeg",
          JPEG_QUALITY
        );
      });
      return blob || file;
    } catch (err) {
      console.warn("[productify] client-side resize failed, uploading original file", err);
      return file;
    }
  }

  // Decodes `file` into something drawImage() can use, correcting EXIF
  // rotation via createImageBitmap's `imageOrientation: 'from-image'` option
  // where supported. Safari's support for that option has historically been
  // inconsistent — sometimes rejecting the promise, sometimes throwing
  // synchronously on the call itself — so real try/catch (not just promise
  // .catch) wraps the option, and browsers lacking createImageBitmap
  // altogether fall back to a plain <img> element (which will not correct
  // EXIF rotation, but never blocks the upload).
  async function loadDrawableSource(file) {
    if (typeof createImageBitmap === "function") {
      try {
        var bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
        return wrapBitmap(bitmap);
      } catch (e1) {
        try {
          var bitmap2 = await createImageBitmap(file);
          return wrapBitmap(bitmap2);
        } catch (e2) {
          // fall through to the <img> fallback below
        }
      }
    }
    return loadViaImageElement(file);
  }

  function wrapBitmap(bitmap) {
    return {
      drawable: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      cleanup: function () {
        if (bitmap.close) bitmap.close();
      },
    };
  }

  function loadViaImageElement(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        resolve({
          drawable: img,
          width: img.naturalWidth,
          height: img.naturalHeight,
          cleanup: function () {
            URL.revokeObjectURL(url);
          },
        });
      };
      img.onerror = function (e) {
        URL.revokeObjectURL(url);
        reject(e);
      };
      img.src = url;
    });
  }

  // ============================================================
  // Tone selection
  // ============================================================

  toneGrid.addEventListener("change", function (e) {
    if (e.target && e.target.classList.contains("tone-radio")) {
      selectedTone = e.target.value;
      saveTone(selectedTone);
    }
  });

  function selectToneProgrammatically(tone) {
    var radio = toneGrid.querySelector('.tone-radio[value="' + tone + '"]');
    if (radio) {
      radio.checked = true;
      selectedTone = tone;
    }
  }

  // ============================================================
  // sessionStorage — only the tone and the photo, nothing else
  // ============================================================

  function saveTone(tone) {
    try {
      sessionStorage.setItem(SS_TONE_KEY, tone);
    } catch (e) {
      /* sessionStorage unavailable (private mode etc.) — non-critical */
    }
  }

  function loadTone() {
    try {
      return sessionStorage.getItem(SS_TONE_KEY);
    } catch (e) {
      return null;
    }
  }

  function savePhotoToSession(blob) {
    try {
      var reader = new FileReader();
      reader.onload = function () {
        try {
          sessionStorage.setItem(SS_PHOTO_KEY, reader.result);
        } catch (e) {
          /* likely quota exceeded — the demo still works, just without reload-survival */
        }
      };
      reader.readAsDataURL(blob);
    } catch (e) {
      /* non-critical */
    }
  }

  function loadPhotoFromSession() {
    var dataUrl;
    try {
      dataUrl = sessionStorage.getItem(SS_PHOTO_KEY);
    } catch (e) {
      return Promise.resolve(null);
    }
    if (!dataUrl) return Promise.resolve(null);
    return fetch(dataUrl)
      .then(function (resp) {
        return resp.blob();
      })
      .catch(function () {
        return null;
      });
  }

  // ============================================================
  // Progress steps
  //
  // SIMULATED ON ELAPSED TIME. The backend answers POST /api/pitch with one
  // single response — it does not emit per-stage events, so this code has no
  // real way to know when the server moves from "looking at the photo" to
  // "designing the brand". The four thresholds below are plausible guesses,
  // roughly evenly spaced, tuned by eye against the /api/stats avg_elapsed_ms
  // figure from the contract. The instant the real POST response arrives —
  // success or failure, whichever comes first — every step snaps straight to
  // "done" (see completeAllSteps()) rather than let the guess run on past
  // reality. Given more time, the correct fix is Server-Sent Events (SSE)
  // from the backend with this code simply reflecting the real stream.
  // ============================================================

  var SIM_THRESHOLDS_MS = [0, 1400, 3400, 6000];
  var simTimer = null;

  function startProgressSimulation() {
    var startTs = Date.now();
    setStepState(0, "active");
    setStepState(1, "pending");
    setStepState(2, "pending");
    setStepState(3, "pending");
    simTimer = setInterval(function () {
      var elapsed = Date.now() - startTs;
      var activeIndex = 0;
      for (var i = SIM_THRESHOLDS_MS.length - 1; i >= 0; i--) {
        if (elapsed >= SIM_THRESHOLDS_MS[i]) {
          activeIndex = i;
          break;
        }
      }
      for (var s = 0; s < 4; s++) {
        if (s < activeIndex) setStepState(s, "done");
        else if (s === activeIndex) setStepState(s, "active");
        else setStepState(s, "pending");
      }
    }, 200);
  }

  function stopProgressSimulation() {
    if (simTimer) {
      clearInterval(simTimer);
      simTimer = null;
    }
  }

  function completeAllSteps() {
    for (var i = 0; i < 4; i++) setStepState(i, "done");
  }

  function setStepState(index, state) {
    var li = progressSteps.querySelector('li[data-step="' + index + '"]');
    if (!li) return;
    li.classList.remove("is-pending", "is-active", "is-done");
    li.classList.add("is-" + state);
  }

  // ============================================================
  // Submit flow
  // ============================================================

  submitBtn.addEventListener("click", function () {
    submitPitch(selectedTone);
  });

  retryBtn.addEventListener("click", function () {
    if (lastRetry) lastRetry();
  });

  tryAnotherBtn.addEventListener("click", function () {
    // Single click: cycle to a different tone and resubmit immediately,
    // reusing the same in-memory photo blob — no re-prompt for a photo.
    var idx = TONE_ORDER.indexOf(selectedTone);
    var nextTone = TONE_ORDER[(idx + 1) % TONE_ORDER.length];
    selectToneProgrammatically(nextTone);
    saveTone(nextTone);
    submitPitch(nextTone);
  });

  var lastRetry = null;

  function submitPitch(tone) {
    // Guard against double-submit: a second tap/click while a request is
    // already in flight must not fire a second request.
    if (inFlight) return;
    if (!resizedBlob) {
      showError("Take a photo first.", null);
      return;
    }

    stopPolling();
    inFlight = true;
    setBusy(true);
    hideError();
    hideResult();
    showProgress();
    startProgressSimulation();

    postPitch(resizedBlob, tone)
      .then(function (data) {
        stopProgressSimulation();
        completeAllSteps();
        showResult(data);
        startPolling(data.slug);
      })
      .catch(function (err) {
        stopProgressSimulation();
        hideProgress();
        lastRetry = function () {
          submitPitch(tone);
        };
        showError(err.message, lastRetry);
      })
      .then(function () {
        inFlight = false;
        setBusy(false);
      });
  }

  function setBusy(busy) {
    submitBtn.disabled = busy || !resizedBlob;
    tryAnotherBtn.disabled = busy;
    retryBtn.disabled = busy;
    chooseAnotherBtn.disabled = busy;
  }

  // contracts/api.md promises `detail` is a human-readable string, but FastAPI's
  // own 422 handler answers with a list of validation objects. Stringifying that
  // naively puts "[object Object]" on screen, which is worse than a stack trace.
  function detailToMessage(detail) {
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) {
      var parts = detail
        .map(function (d) { return d && typeof d.msg === "string" ? d.msg : null; })
        .filter(Boolean);
      if (parts.length) return parts.join(". ");
    }
    return "Something went wrong. Try again.";
  }

  function postPitch(blob, tone) {
    var form = new FormData();
    // Field name is "image" per contracts/api.md — not "photo".
    form.append("image", blob, "photo.jpg");
    form.append("tone", tone);

    return fetch("/api/pitch", { method: "POST", body: form })
      .catch(function () {
        var e = new Error("Can't reach the server. Check that it's running and try again.");
        e.kind = "network";
        throw e;
      })
      .then(function (resp) {
        if (resp.status === 502) {
          var e502 = new Error("The model had a bad moment — try again.");
          e502.kind = "bad-moment";
          throw e502;
        }
        if (!resp.ok) {
          return resp
            .json()
            .catch(function () {
              return {};
            })
            .then(function (body) {
              var e = new Error(detailToMessage(body && body.detail));
              e.kind = "http-" + resp.status;
              throw e;
            });
        }
        return resp.json();
      });
  }

  // ============================================================
  // Polling GET /api/pitch/{slug} for logo_status
  // ============================================================

  function startPolling(slug) {
    stopPolling();
    pollDone = false;
    var startTs = Date.now();
    var INTERVAL_MS = 1500;
    var MAX_MS = 40000;

    logoStatusNote.hidden = false;
    logoStatusNote.textContent = "Logo is still rendering…";

    function tick() {
      if (Date.now() - startTs > MAX_MS) {
        logoStatusNote.textContent = "Still working on the logo — the pitch page works either way.";
        stopPolling();
        return;
      }
      fetch("/api/pitch/" + encodeURIComponent(slug))
        .then(function (resp) {
          if (!resp.ok) return null;
          return resp.json();
        })
        .then(function (data) {
          if (!data) return;
          if (data.tagline) {
            resultTagline.textContent = data.tagline;
            resultTagline.hidden = false;
          }
          if (data.logo_status === "ready") {
            logoStatusNote.textContent = "Logo is ready.";
            stopPolling();
          } else if (data.logo_status === "failed") {
            logoStatusNote.textContent = "The logo didn't render this time — the page still works.";
            stopPolling();
          }
        })
        .catch(function () {
          /* transient network hiccup while polling — try again next tick */
        });
    }

    pollTimer = setInterval(tick, INTERVAL_MS);
    // Pause while the tab is hidden so we don't hammer the backend, but RESUME
    // when it comes back. "Open the pitch" opens a new tab, which hides this
    // one — without the resume the status would stay stuck on "still
    // rendering" forever even after the logo landed.
    pollVisibilityHandler = function () {
      if (document.hidden) {
        pausePolling();
      } else if (!pollTimer && !pollDone) {
        pollTimer = setInterval(tick, INTERVAL_MS);
        tick();
      }
    };
    document.addEventListener("visibilitychange", pollVisibilityHandler);
    tick();
  }

  // Clears the timer but keeps the visibilitychange listener, so polling can
  // pick up again when the tab is refocused.
  function pausePolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function stopPolling() {
    pollDone = true;
    pausePolling();
    if (pollVisibilityHandler) {
      document.removeEventListener("visibilitychange", pollVisibilityHandler);
      pollVisibilityHandler = null;
    }
  }

  // ============================================================
  // UI panel helpers
  // ============================================================

  function showProgress() {
    progressCard.hidden = false;
  }
  function hideProgress() {
    progressCard.hidden = true;
  }

  function showResult(data) {
    resultCard.hidden = false;
    // Field names are the PitchSummary of contracts/api.md: brand, tagline,
    // pitch_url. The slug fallback keeps the link usable even if a field is
    // missing — an "Open the pitch" button that goes nowhere kills the demo.
    resultBrand.textContent = data.brand || "Your new company";
    resultTagline.textContent = data.tagline || "";
    resultTagline.hidden = !data.tagline;
    logoStatusNote.hidden = true;
    openPitchLink.href = data.pitch_url || "/pitch/" + encodeURIComponent(data.slug);
  }
  function hideResult() {
    resultCard.hidden = true;
  }

  function showError(message, retryFn) {
    errorCard.hidden = false;
    errorMessage.textContent = message;
    if (retryFn) {
      retryBtn.hidden = false;
    } else {
      retryBtn.hidden = true;
    }
  }
  function hideError() {
    errorCard.hidden = true;
    errorMessage.textContent = "";
  }

  // ============================================================
  // Best-effort top counter (non-blocking, degrades quietly)
  // ============================================================

  function loadStatsCounter() {
    fetch("/api/stats")
      .then(function (resp) {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then(function (data) {
        if (data && typeof data.pitches_total === "number") {
          counterText.textContent =
            data.pitches_total + (data.pitches_total === 1 ? " company founded so far" : " companies founded so far");
        }
      })
      .catch(function () {
        /* keep the default "View the gallery" text */
      });
  }

  // ============================================================
  // Init
  // ============================================================

  function init() {
    loadStatsCounter();

    var savedTone = loadTone();
    if (savedTone && TONE_ORDER.indexOf(savedTone) !== -1) {
      selectToneProgrammatically(savedTone);
    }

    loadPhotoFromSession().then(function (blob) {
      if (!blob) return;
      resizedBlob = blob;
      var url = URL.createObjectURL(blob);
      setPreviewImage(url);
      sizeNote.textContent = "Photo restored from your last session (" + humanSize(blob.size) + ")";
      photoControls.hidden = false;
      submitBtn.disabled = false;
    });
  }

  init();
})();
