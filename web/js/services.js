/**
 * Cliente HTTP do IA VideoStudio — todas as chamadas à API do BFF (workshop.bff.lab_server).
 * Depende apenas de fetch; expõe LabApi no escopo global.
 */
(function (global) {
  "use strict";

  const CORR_STORAGE_KEY = "ivideostudio_correlation_id";

  function _mkCorrelationId() {
    // 16 bytes hex + timestamp curto: simples, único o suficiente para sessão
    const a = new Uint8Array(16);
    if (global.crypto && typeof global.crypto.getRandomValues === "function") {
      global.crypto.getRandomValues(a);
    } else {
      for (let i = 0; i < a.length; i++) a[i] = Math.floor(Math.random() * 256);
    }
    const hex = Array.from(a)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return `cid_${hex}_${Date.now().toString(36)}`;
  }

  function getCorrelationId() {
    try {
      const cur = String(global.localStorage.getItem(CORR_STORAGE_KEY) || "").trim();
      if (cur) return cur;
      const next = _mkCorrelationId();
      global.localStorage.setItem(CORR_STORAGE_KEY, next);
      return next;
    } catch (_) {
      return _mkCorrelationId();
    }
  }

  function _defaultHeaders(extra) {
    const h = { ...(extra || {}) };
    h["X-Correlation-Id"] = getCorrelationId();
    return h;
  }

  async function getJson(path) {
    const r = await fetch(path, { headers: _defaultHeaders() });
    if (!r.ok) throw new Error(`GET ${path} failed (${r.status})`);
    return await r.json();
  }

  async function postJson(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: _defaultHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`POST ${path} failed (${r.status}): ${t}`);
    }
    return await r.json();
  }

  /**
   * @param {{ tema?: string, useOllama?: boolean }} opts
   */
  function getAngles(opts) {
    const tema = (opts && opts.tema) || "";
    const qs = new URLSearchParams({ tema });
    if (opts && opts.useOllama === true) qs.set("use_ollama", "true");
    else if (opts && opts.useOllama === false) qs.set("use_ollama", "false");
    return getJson(`/api/angles?${qs.toString()}`);
  }

  /**
   * @param {{ keyword: string, region?: string, category_id?: string, youtube_n?: number, trends_days?: number }} body
   */
  function postResearchYoutubeTrends(body) {
    return postJson("/api/research_agent/youtube_trends", body);
  }

  /**
   * @param {{ tema?: string, angulo?: string, use_ollama?: boolean, youtube_context?: object }} body
   */
  function postRoteirizadorGenerate(body) {
    return postJson("/api/script_agent/generate", body);
  }

  /**
   * @param {{ scene: string, style?: string, prefer?: string, per_source?: number }} body
   */
  function postImageResearchSearch(body) {
    return postJson("/api/asset_agent/search", body);
  }

  /**
   * @param {{ image: string, scene_idx?: number, use_comfy?: boolean|null }} body
   */
  function postVisualAgentPreview(body) {
    return postJson("/api/visual_agent/preview", body);
  }

  /**
   * @param {{ script: string, job_token?: string, provider?: string, kokoro_voice?: string, kokoro_lang?: string, kokoro_speed?: number, piper_model?: string }} body
   */
  function postTtsAgentPreview(body) {
    return postJson("/api/tts_agent/preview", body);
  }

  function getTtsAgentOptions() {
    return getJson("/api/tts_agent/options");
  }

  /**
   * @param {{ job_token?: string, assets: { scene_idx: number, image: string }[], use_comfy?: boolean|null }} body
   */
  function postVisualAgentBatch(body) {
    return postJson("/api/visual_agent/batch", body);
  }

  function getLabUiConfig() {
    return getJson("/api/lab/ui_config");
  }

  /**
   * @param {{ job_token: string }} body
   */
  function postComposerAgentPreview(body) {
    return postJson("/api/composer_agent/preview", body);
  }

  function getHealth() {
    return getJson("/health");
  }

  function getHealthLive() {
    return getJson("/health/live");
  }

  function youtubeOauthStartUrl() {
    return "/api/youtube/oauth/start";
  }

  function getYoutubeChannels() {
    return getJson("/api/youtube/channels");
  }

  /**
   * @param {{ topic?: string, angle?: string, script: string, trending_data?: object }} body
   */
  function postMetadataAgentPreview(body) {
    return postJson("/api/metadata_agent/preview", body);
  }

  /**
   * @param {{ topic?: string, angle?: string, publico_alvo?: string, objetivo_video?: string, script: string, trending_data?: object, segments?: object[] }} body
   */
  function postPublishGrowthEnginePreview(body) {
    return postJson("/api/publish_growth_engine/preview", body);
  }

  /**
   * @param {{ job_token: string, template_id?: string, brand_color?: string, title?: string, logo_path?: string, logo_data_url?: string }} body
   */
  function postThumbnailCardAgentPreview(body) {
    return postJson("/api/thumbnail_card_agent/preview", body);
  }

  /**
   * @param {{ job_token: string, title: string, description?: string, tags_csv?: string, channel_id?: string }} body
   */
  function postYoutubeUpload(body) {
    return postJson("/api/youtube/upload", body);
  }

  /**
   * @param {{ job_token: string, model_size?: string, language?: string }} body
   */
  function postLabAsr(body) {
    return postJson("/api/lab/asr", body);
  }

  /**
   * @param {{ job_token: string, timeline_mode?: string }} body
   */
  function postLabSyncCompose(body) {
    return postJson("/api/lab/sync_compose", body);
  }

  global.LabApi = {
    getJson,
    postJson,
    getCorrelationId,
    getLabUiConfig,
    getAngles,
    postResearchYoutubeTrends,
    postRoteirizadorGenerate,
    postImageResearchSearch,
    postVisualAgentPreview,
    postTtsAgentPreview,
    postVisualAgentBatch,
    postComposerAgentPreview,
    getTtsAgentOptions,
    getHealth,
    getHealthLive,
    youtubeOauthStartUrl,
    getYoutubeChannels,
    postMetadataAgentPreview,
    postPublishGrowthEnginePreview,
    postThumbnailCardAgentPreview,
    postYoutubeUpload,
    postLabAsr,
    postLabSyncCompose,
  };
})(typeof window !== "undefined" ? window : globalThis);
