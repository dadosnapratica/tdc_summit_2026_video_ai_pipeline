/**
 * Métricas locais (sem servidor) + widget flutuante de feedback (Typeform / Google Forms / link).
 *
 * Configuração opcional em index.html ANTES deste script:
 *   window.__VIDEO_STUDIO_DEMO_CONFIG = {
 *     typeformLiveId: "01XXXX...",           // Typeform Next: código em Share → incorporar (data-tf-live)
 *     feedbackEmbedUrl: "https://...",      // alternativa: iframe clássico (Google Forms ou URL Typeform)
 *     feedbackFallbackUrl: "https://...",   // abre em nova aba se não houver embed
 *     posthogKey: "phc_...",                // Project API Key (PostHog Cloud)
 *     posthogApiHost: "https://us.i.posthog.com", // ou https://eu.i.posthog.com (UE)
 *     collectMetrics: true                   // false desliga localStorage + PostHog
 *   };
 * Typeform Next — «Generic sites» (Share → incorporar): o mesmo que
 *   <div data-tf-live="SEU_ID"></div>
 *   <script src="//embed.typeform.com/next/embed.js"></script>
 * Aqui o div é injetado ao abrir o painel (evita altura 0 com painel hidden) e o script é carregado depois.
 * Se typeformLiveId estiver definido, usa esse embed (prioridade sobre iframe).
 * PostHog: ver ANALYTICS.md na pasta desta demo.
 */
(function (global) {
  "use strict";

  var STORAGE_KEY = "videostudio_demo_metrics_v1";
  var SESSION_KEY = "videostudio_demo_session_id";
  var MAX_SESSIONS = 25;
  var MAX_EVENTS_PER_SESSION = 250;

  /** Eventos à espera de posthog.init (script async). */
  var pendingPosthog = [];

  var posthogLoadStarted = false;

  function cfg() {
    return global.__VIDEO_STUDIO_DEMO_CONFIG || {};
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function safeJsonParse(s, fallback) {
    if (s == null || s === "") return fallback;
    try {
      var v = JSON.parse(s);
      if (v === null || typeof v !== "object" || Array.isArray(v)) {
        return fallback;
      }
      return v;
    } catch (e) {
      return fallback;
    }
  }

  function loadStore() {
    var raw = localStorage.getItem(STORAGE_KEY);
    var data = safeJsonParse(raw, { version: 1, sessions: [] });
    if (!data || typeof data !== "object") {
      return { version: 1, sessions: [] };
    }
    if (!Array.isArray(data.sessions)) {
      data.sessions = [];
    }
    return data;
  }

  function saveStore(data) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  function getOrCreateSessionId() {
    try {
      var id = sessionStorage.getItem(SESSION_KEY);
      if (id) return id;
      id =
        "s_" +
        Date.now().toString(36) +
        "_" +
        Math.random().toString(36).slice(2, 10);
      sessionStorage.setItem(SESSION_KEY, id);
      return id;
    } catch (e) {
      return "s_anon_" + Date.now();
    }
  }

  function getOrAppendSession(store) {
    var sid = getOrCreateSessionId();
    var i;
    for (i = 0; i < store.sessions.length; i++) {
      if (store.sessions[i].id === sid) return store.sessions[i];
    }
    var s = {
      id: sid,
      startedAt: nowIso(),
      userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "",
      events: [],
    };
    store.sessions.push(s);
    while (store.sessions.length > MAX_SESSIONS) {
      store.sessions.shift();
    }
    return s;
  }

  function track(type, payload) {
    if (cfg().collectMetrics === false) return;
    var store = loadStore();
    var s = getOrAppendSession(store);
    var ev = { t: nowIso(), type: type, payload: payload || {} };
    if (!s.events) s.events = [];
    s.events.push(ev);
    while (s.events.length > MAX_EVENTS_PER_SESSION) {
      s.events.shift();
    }
    saveStore(store);
    forwardToPosthog(type, payload || {});
  }

  function posthogEventName(type) {
    return "demo_" + String(type || "event").replace(/[^a-zA-Z0-9_]/g, "_");
  }

  function forwardToPosthog(type, payload) {
    if (cfg().collectMetrics === false) return;
    var key = (cfg().posthogKey || "").trim();
    if (!key) return;
    var name = posthogEventName(type);
    var props = Object.assign({ demo_source: "web-demo-offline" }, payload || {});
    try {
      if (global.posthog && typeof global.posthog.capture === "function") {
        global.posthog.capture(name, props);
      } else {
        pendingPosthog.push([name, props]);
      }
    } catch (e) {}
  }

  function flushPendingPosthog() {
    if (!global.posthog || typeof global.posthog.capture !== "function") return;
    while (pendingPosthog.length) {
      var x = pendingPosthog.shift();
      try {
        global.posthog.capture(x[0], x[1]);
      } catch (e) {}
    }
  }

  function ensurePosthog() {
    if (cfg().collectMetrics === false) return;
    var key = (cfg().posthogKey || "").trim();
    if (!key || posthogLoadStarted) return;
    posthogLoadStarted = true;
    var host = (cfg().posthogApiHost || "https://us.i.posthog.com").replace(/\/$/, "");
    var s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = host + "/static/array.js";
    s.onload = function () {
      try {
        if (!global.posthog || typeof global.posthog.init !== "function") return;
        global.posthog.init(key, {
          api_host: host,
          autocapture: false,
          capture_pageview: false,
          persistence: "localStorage",
        });
        global.posthog.register({
          demo_session_id: getOrCreateSessionId(),
        });
        flushPendingPosthog();
      } catch (e) {}
    };
    s.onerror = function () {
      posthogLoadStarted = false;
    };
    document.head.appendChild(s);
  }

  function wireUiHooks() {
    document.querySelectorAll(".tab[data-tab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        track("tab", { tab: btn.getAttribute("data-tab") || "" });
      });
    });
    var map = [
      ["btn-research", "research_submit"],
      ["btn-angles", "angles_click"],
      ["btn-generate", "roteiro_generate"],
      ["btn-search", "image_search"],
      ["btn-use-first-scene", "use_first_scene"],
      ["btn-tour-start", "tour_manual_start"],
    ];
    map.forEach(function (pair) {
      var el = document.getElementById(pair[0]);
      if (el) {
        el.addEventListener("click", function () {
          track("action", { id: pair[1] });
        });
      }
    });
    document.addEventListener("videostudio-demo-tour", function (e) {
      var d = (e && e.detail) || {};
      track("tour", { phase: d.phase || "" });
    });
  }

  function getExportPayload() {
    var store = loadStore();
    return {
      exportedAt: nowIso(),
      schemaVersion: 1,
      note:
        "Métricas guardadas apenas neste navegador. Envie este JSON à equipa após reuniões ou testes com prospects.",
      sessions: store.sessions,
    };
  }

  /** Mesmo URL que o snippet «Generic sites» do Typeform (protocol-relative → http ou https). */
  var TYPEFORM_EMBED_SRC = "//embed.typeform.com/next/embed.js";

  function isSafeTypeformLiveId(s) {
    return typeof s === "string" && /^[a-zA-Z0-9]{12,64}$/.test(s);
  }

  function ensureTypeformEmbedScript() {
    if (document.querySelector('script[src*="embed.typeform.com/next/embed.js"]')) return;
    var s = document.createElement("script");
    s.src = TYPEFORM_EMBED_SRC;
    s.async = true;
    document.body.appendChild(s);
  }

  function exportJsonDownload() {
    var text = JSON.stringify(getExportPayload(), null, 2);
    var name = "videostudio-demo-metrics-" + nowIso().slice(0, 10) + ".json";
    var blob = new Blob([text], { type: "application/json;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    track("metrics_export", {});
  }

  function buildFeedbackUi() {
    var root = document.createElement("div");
    root.id = "demo_feedback_widget";
    root.setAttribute("aria-live", "polite");

    var c = cfg();
    var liveId = (c.typeformLiveId || "").trim();
    var embedUrl = (c.feedbackEmbedUrl || "").trim();
    var fallbackUrl = (c.feedbackFallbackUrl || embedUrl || "").trim();

    /** Typeform Next: não colocar data-tf-live enquanto o painel está hidden — o embed falha com altura 0. Montamos na 1.ª abertura (ver openPanel). */
    var embedSection = "";
    if (liveId && isSafeTypeformLiveId(liveId)) {
      embedSection =
        '<div class="demo-feedback-embed-wrap demo-feedback-embed-wrap--typeform" id="demo_typeform_mount">' +
        '<p class="muted demo-typeform-hint" style="margin:0;padding:12px;font-size:13px;line-height:1.45">A carregar formulário…</p>' +
        "</div>";
    } else if (embedUrl) {
      embedSection =
        '<div class="demo-feedback-embed-wrap">' +
        '<iframe id="demo_feedback_iframe" class="demo-feedback-iframe" title="Formulário de feedback" src="" allow="microphone; camera"></iframe>' +
        "</div>";
    } else {
      embedSection =
        '<div class="demo-feedback-placeholder card" style="padding:14px">' +
        "<strong>Configure o formulário</strong>" +
        '<p class="muted" style="margin:8px 0 0;font-size:13px;line-height:1.5">No <code>index.html</code>, defina <code>typeformLiveId</code> (embed Next) ou <code>feedbackEmbedUrl</code> (iframe).</p>' +
        (fallbackUrl
          ? '<p style="margin-top:10px"><a class="btn" href="' +
            escapeAttr(fallbackUrl) +
            '" target="_blank" rel="noopener noreferrer">Abrir formulário</a></p>'
          : "") +
        "</div>";
    }

    root.innerHTML =
      '<button type="button" class="demo-fab" id="demo_fab_btn" aria-expanded="false" aria-controls="demo_feedback_panel" title="Dar feedback — a sua opinião">' +
      '  <span class="demo-fab-inner" aria-hidden="true">' +
      '    <svg class="demo-fab-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" focusable="false" aria-hidden="true">' +
      '      <path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m3 11 18-5v12L3 13v-2Z"/>' +
      '      <path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>' +
      "    </svg>" +
      '    <span class="demo-fab-label">Feedback</span>' +
      "  </span>" +
      '  <span class="demo-fab-pulse" aria-hidden="true"></span>' +
      "</button>" +
      '<aside id="demo_feedback_panel" class="demo-feedback-panel" hidden role="dialog" aria-label="Feedback">' +
      '  <div class="demo-feedback-head">' +
      '    <div class="demo-feedback-title">Feedback</div>' +
      '    <button type="button" class="btn btn-ghost demo-feedback-close" id="demo_feedback_close">Fechar</button>' +
      "  </div>" +
      '  <p class="demo-feedback-lead muted">A sua opinião ajuda a priorizar o produto. As respostas são guardadas no Typeform (ou no serviço configurado).</p>' +
      embedSection +
      "</aside>";

    document.body.appendChild(root);

    var panel = document.getElementById("demo_feedback_panel");
    var fab = document.getElementById("demo_fab_btn");
    var closeBtn = document.getElementById("demo_feedback_close");
    var iframe = document.getElementById("demo_feedback_iframe");

    if (iframe && embedUrl) {
      iframe.src = embedUrl;
    }

    var typeformMounted = false;
    var feedbackOpenedOnce = false;
    var feedbackAttentionTimer = null;

    function clearFeedbackAttention() {
      if (feedbackAttentionTimer !== null) {
        clearTimeout(feedbackAttentionTimer);
        feedbackAttentionTimer = null;
      }
      if (fab) {
        fab.classList.remove("demo-fab--attention", "demo-fab--nudge");
      }
    }

    function scheduleFeedbackAttention() {
      feedbackAttentionTimer = setTimeout(function () {
        feedbackAttentionTimer = null;
        if (feedbackOpenedOnce || !fab) return;
        fab.classList.add("demo-fab--attention", "demo-fab--nudge");
      }, 6000);
    }

    function mountTypeformEmbed() {
      if (typeformMounted) return;
      if (!liveId || !isSafeTypeformLiveId(liveId)) return;
      var mount = document.getElementById("demo_typeform_mount");
      if (!mount || mount.querySelector("[data-tf-live]")) return;
      mount.innerHTML =
        '<div data-tf-live="' + escapeAttr(liveId) + '"></div>';
      typeformMounted = true;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          ensureTypeformEmbedScript();
        });
      });
    }

    function openPanel() {
      if (!panel) return;
      feedbackOpenedOnce = true;
      clearFeedbackAttention();
      panel.hidden = false;
      fab.setAttribute("aria-expanded", "true");
      mountTypeformEmbed();
      track("feedback_open", {});
    }

    function closePanel() {
      if (!panel) return;
      panel.hidden = true;
      fab.setAttribute("aria-expanded", "false");
    }

    if (fab) {
      fab.addEventListener("click", function () {
        if (panel && !panel.hidden) closePanel();
        else openPanel();
      });
    }
    if (closeBtn) closeBtn.addEventListener("click", closePanel);

    scheduleFeedbackAttention();
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  }

  document.addEventListener("DOMContentLoaded", function () {
    ensurePosthog();
    if (cfg().collectMetrics !== false) {
      track("session_start", { path: location.pathname || "/" });
      wireUiHooks();
    } else {
      wireUiHooks();
    }
    buildFeedbackUi();
  });

  global.VideoStudioDemoAnalytics = {
    track: track,
    exportJsonDownload: exportJsonDownload,
    getExportPayload: getExportPayload,
  };
})(typeof window !== "undefined" ? window : globalThis);
