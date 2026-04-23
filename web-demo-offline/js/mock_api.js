/**
 * Cliente falso compatível com LabApi (services.js) — usa apenas mock_data.js.
 * Não realiza fetch; aplica atraso leve para simular rede.
 */
(function (global) {
  "use strict";

  var D = global.VideoStudioOfflineMockData;
  if (!D || !D.responses) {
    throw new Error("mock_data.js deve ser carregado antes de mock_api.js");
  }

  var PM = global.VideoStudioOfflinePipelineMock;
  if (!PM || typeof PM.buildVideoStateTail !== "function") {
    throw new Error("VideoStudioOfflinePipelineMock ausente: verifique mock_data.js");
  }

  var NET_MS = 260;

  function delay(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function clone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  global.__VIDEO_STUDIO_DEMO__ = {
    offline: true,
    helpHref: "help.html",
    scenario: D.meta && D.meta.scenario,
  };

  async function notImplemented() {
    throw new Error("Use os métodos nomeados do LabApi (demo offline).");
  }

  var CID = "cid_demo_offline_" + Date.now().toString(36);

  global.LabApi = {
    getJson: notImplemented,
    postJson: notImplemented,

    getCorrelationId: function () {
      return CID;
    },

    getLabUiConfig: async function () {
      await delay(40);
      return clone(D.responses.getLabUiConfig || { visual_use_comfyui_default: true });
    },

    getAngles: async function () {
      await delay(NET_MS);
      return clone(D.responses.getAngles);
    },

    postResearchYoutubeTrends: async function () {
      await delay(NET_MS + 100);
      return clone(D.responses.postResearchYoutubeTrends);
    },

    postRoteirizadorGenerate: async function (body) {
      await delay(NET_MS + 180);
      var out = clone(D.responses.postRoteirizadorGenerate);
      if (body && typeof body === "object") {
        if (body.tema) out.tema = String(body.tema);
        if (body.angulo !== undefined) out.angulo = String(body.angulo || "");
        if (body.youtube_context) out.youtube_context = body.youtube_context;
      }
      return out;
    },

    postImageResearchSearch: async function (body) {
      await delay(NET_MS + 90);
      var out = clone(D.responses.postImageResearchSearch);
      if (body && typeof body === "object" && body.scene) {
        out.scene_prompt = String(body.scene);
      }
      return out;
    },

    getHealth: async function () {
      await delay(70);
      return clone(D.responses.getHealth);
    },

    getHealthLive: async function () {
      await delay(35);
      return clone(D.responses.getHealthLive);
    },

    getTtsAgentOptions: async function () {
      await delay(NET_MS);
      return clone(D.responses.getTtsAgentOptions);
    },

    postTtsAgentPreview: async function (body) {
      await delay(NET_MS + 120);
      var out = clone(D.responses.postTtsAgentPreview);
      if (body && body.provider === "piper") {
        out.provider = "piper";
        if (body.piper_model) out.detail = "piper_model=" + String(body.piper_model).slice(0, 80);
      }
      return out;
    },

    postVisualAgentPreview: async function () {
      await delay(NET_MS + 200);
      return clone(D.responses.postVisualAgentPreview);
    },

    postVisualAgentBatch: async function () {
      await delay(NET_MS + 240);
      return clone(D.responses.postVisualAgentBatch);
    },

    postComposerAgentPreview: async function () {
      await delay(NET_MS + 300);
      return clone(D.responses.postComposerAgentPreview);
    },

    postMetadataAgentPreview: async function () {
      await delay(NET_MS + 140);
      return clone(D.responses.postMetadataAgentPreview);
    },

    postPublishGrowthEnginePreview: async function () {
      await delay(NET_MS + 220);
      return clone(D.responses.postPublishGrowthEnginePreview);
    },

    postThumbnailCardAgentPreview: async function () {
      await delay(NET_MS + 160);
      return clone(D.responses.postThumbnailCardAgentPreview);
    },

    postLabSyncCompose: async function () {
      await delay(NET_MS + 380);
      return clone(D.responses.postLabSyncCompose);
    },

    getYoutubeChannels: async function () {
      await delay(NET_MS);
      return clone(D.responses.getYoutubeChannels);
    },

    postYoutubeUpload: async function () {
      await delay(NET_MS + 400);
      return clone(D.responses.postYoutubeUpload);
    },

    postLabAsr: async function () {
      await delay(NET_MS + 500);
      return clone(D.responses.postLabAsr);
    },

    youtubeOauthStartUrl: function () {
      return "/api/youtube/oauth/start";
    },

    /**
     * Simula visual_agent → tts_agent → composer_agent → metadata_agent → publisher_agent.
     */
    simulatePipelineAfterAssets: async function (opts) {
      var body = opts && typeof opts === "object" ? opts : {};
      var stepMs = Number(body.stepDelayMs);
      if (!Number.isFinite(stepMs) || stepMs < 0) stepMs = 320;
      var onStep = typeof body.onStep === "function" ? body.onStep : null;

      var base = PM.buildVideoStateTail({
        channel_niche: body.channel_niche,
        tema: body.tema,
        angulo: body.angulo,
        roteiro: body.roteiro,
        imageSearch: body.imageSearch,
        researchPack: body.researchPack,
      });

      var steps = [];
      var acc = {
        channel_niche: base.channel_niche,
        job_path: base.job_path,
        topic: base.topic,
        angle: base.angle,
        trending_data: base.trending_data,
        script: base.script,
        scenes: base.scenes,
        raw_assets: base.raw_assets,
      };

      async function run(agent, detail, patch) {
        Object.assign(acc, patch);
        steps.push({ agent: agent, detail: detail, at: Date.now(), state_patch: patch });
        if (onStep) onStep({ agent: agent, detail: detail }, clone(acc), steps.length);
        await delay(stepMs);
      }

      await run(
        "visual_agent",
        "ComfyUI img2img + AnimateDiff (GPU) — clipes .mp4 por cena (simulado).",
        { clips: base.clips },
      );

      await run("tts_agent", "Kokoro/Piper (ARM) — narração .wav a partir do script (simulado).", { audio_file: base.audio_file });

      await run(
        "composer_agent",
        "ffmpeg + NVENC (GPU) — concatena clipes + áudio → final.mp4 (simulado).",
        { video_file: base.video_file },
      );

      await run(
        "metadata_agent",
        "Ollama + trending_data — título, descrição e tags (simulado a partir do contexto da demo).",
        { metadata: base.metadata },
      );

      await run(
        "publisher_agent",
        "YouTube Data API v3 — upload privacyStatus=private (simulado).",
        { publish_status: base.publish_status },
      );

      return { state: clone(base), steps: clone(steps) };
    },
  };
})(typeof window !== "undefined" ? window : globalThis);
