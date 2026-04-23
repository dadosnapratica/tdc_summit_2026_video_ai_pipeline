/**
 * Dados fictícios para a demo offline — estruturas alinhadas ao OpenAPI do BFF (bff/api_schemas)
 * e ao payload de research_agent.build_research_pack, script_agent.generate_script
 * e asset_agent.search_assets_for_scene.
 *
 * Os objetos em `requests` exemplificam corpos/query usados nas chamadas reais;
 * `responses` são os JSON de retorno usados pela UI desta pasta (sem backend).
 */
(function (global) {
  "use strict";

  /** Pré-visualização sem BFF: narração gerada em assets (voz PT); vídeo CC0 MDN (flor). */
  var DEMO_SAMPLE_AUDIO = "assets/demo_narration.mp3";
  var DEMO_SAMPLE_VIDEO =
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4";

  /** @type {VideoStudioOfflineMockDataShape} */
  global.VideoStudioOfflineMockData = {
    meta: {
      version: 3,
      scenario:
        "Apresentação comercial — nicho ciência/astronomia (dados totalmente fictícios ou anonimizados).",
      sourceNote:
        "Gerado para espelhar formas reais observadas na API; não substitui capturas de produção. v2: stubs LabApi alinhados a TTS Piper, metadata, upload YouTube e ASR (sem executar backend).",
      capturedAt: "2026-04-22",
    },

    requests: {
      getHealth: { method: "GET", path: "/health" },
      getHealthLive: { method: "GET", path: "/health/live" },
      getAngles: {
        method: "GET",
        path: "/api/angles",
        query: { tema: "astronomia", use_ollama: "false" },
      },
      postResearchYoutubeTrends: {
        method: "POST",
        path: "/api/research_agent/youtube_trends",
        body: {
          keyword: "astronomia",
          region: "BR",
          category_id: "28",
          youtube_n: 10,
          trends_days: 7,
        },
      },
      postRoteirizadorGenerate: {
        method: "POST",
        path: "/api/script_agent/generate",
        body: {
          tema: "astronomia",
          angulo: "Do mito ao dado: o que já medimos sobre buracos negros",
          use_ollama: false,
          youtube_context: null,
        },
      },
      postImageResearchSearch: {
        method: "POST",
        path: "/api/asset_agent/search",
        body: {
          scene:
            "Milky way core over desert observatory, long exposure, subtle purple nebula, cinematic wide",
          style: "cinematic documentary, realistic lighting, high detail",
          per_source: 5,
        },
      },
    },

    responses: {
      getHealth: {
        service: "ia_videostudio_bff",
        status: "ok",
        checks: {
          ollama: {
            status: "ok",
            base_url: "http://gpu-server-01:11434",
            latency_ms: 42,
            http_status: 200,
            detail: null,
          },
          pytrends: { status: "ok", detail: "import OK" },
          youtube_api: { status: "ok", configured: true, detail: null },
          image_search_keys: {
            status: "ok",
            sources: { pexels: true, pixabay: true, unsplash: true },
            detail: null,
          },
        },
        errors: [],
      },

      getHealthLive: { status: "ok" },

      getAngles: {
        tema: "astronomia",
        angles: [
          "Buracos negros explicados sem matemática pesada",
          "Descobertas recentes em ondas gravitacionais",
          "Como o James Webb mudou o que sabemos sobre galáxias",
          "Mitos comuns sobre o Big Bang — e o que a ciência diz",
        ],
      },

      postResearchYoutubeTrends: {
        keyword: "astronomia",
        region: "BR",
        category_id: "28",
        trends: {
          geo: "BR",
          timeframe: "now 7-d",
          related_queries: {
            astronomia: {
              rising: [
                { query: "eclipse solar 2026", value: "Breakout" },
                { query: "buraco negro sombra", value: 92 },
                { query: "telescópio james webb novidades", value: 78 },
              ],
              top: [
                { query: "astronomia para iniciantes", value: 100 },
                { query: "constelações visíveis hoje", value: 86 },
                { query: "planetas do sistema solar", value: 74 },
              ],
            },
          },
          interest_over_time: (function () {
            const rows = [];
            const start = new Date("2026-03-25T00:00:00Z");
            for (let i = 0; i < 14; i++) {
              const d = new Date(start);
              d.setUTCDate(d.getUTCDate() + i);
              const iso = d.toISOString().slice(0, 10);
              rows.push({
                date: iso,
                astronomia: 35 + ((i * 7) % 45) + (i % 3) * 3,
              });
            }
            return rows;
          })(),
        },
        youtube_videos: [],
        video_suggestions: [
          {
            kind: "youtube_video",
            source: "youtube",
            rank: 1,
            score: 3,
            ranker_reason: "heuristic (demo)",
            title: "Astronomia em 10 minutos: como começar a observar o céu",
            subtitle: "Canal Demo Educação",
            views: "1240000",
            video_id: "dQw4w9WgXcQ",
            video_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            description:
              "Neste vídeo fictício para demo, reunimos dicas de equipamento básico, apps de mapa estelar e segurança ao observar eclipses. Texto longo para testar expansão de descrição na UI do laboratório.",
            payload: {
              tema: "astronomia",
              angulo: "Inspirado no vídeo popular: Astronomia em 10 minutos: como começar a observar o céu",
              youtube_context: {
                video_id: "dQw4w9WgXcQ",
                video_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                channel_url: "https://www.youtube.com/channel/UCdemo",
                views: "1240000",
                title: "Astronomia em 10 minutos: como começar a observar o céu",
                description:
                  "Neste vídeo fictício para demo, reunimos dicas de equipamento básico, apps de mapa estelar e segurança ao observar eclipses.",
              },
            },
          },
          {
            kind: "youtube_video",
            source: "youtube",
            rank: 2,
            score: 2,
            ranker_reason: "heuristic (demo)",
            title: "O que acontece se você cair em um buraco negro?",
            subtitle: "Ciência em 8 minutos",
            views: "892000",
            video_id: "9bZkp7q19f0",
            video_url: "https://www.youtube.com/watch?v=9bZkp7q19f0",
            description:
              "Analogias, limites do modelo clássico e por que 'singularidade' não é mágica — roteiro fictício para demonstração.",
            payload: {
              tema: "astronomia",
              angulo: "Inspirado no vídeo popular: O que acontece se você cair em um buraco negro?",
              youtube_context: {
                video_id: "9bZkp7q19f0",
                video_url: "https://www.youtube.com/watch?v=9bZkp7q19f0",
                channel_url: "https://www.youtube.com/channel/UCdemo2",
                views: "892000",
                title: "O que acontece se você cair em um buraco negro?",
                description:
                  "Analogias, limites do modelo clássico e por que 'singularidade' não é mágica — roteiro fictício para demonstração.",
              },
            },
          },
        ],
        trends_panel: {
          seed_keyword: "astronomia",
          geo: "BR",
          timeframe: "now 7-d",
          trending_searches: [],
          related_rising: [
            { query: "eclipse solar 2026", value: "Breakout" },
            { query: "buraco negro sombra", value: 92 },
            { query: "telescópio james webb novidades", value: 78 },
          ],
          related_top: [
            { query: "astronomia para iniciantes", value: 100 },
            { query: "constelações visíveis hoje", value: 86 },
            { query: "planetas do sistema solar", value: 74 },
          ],
          interest_over_time: [],
        },
        suggestions: [],
        ranker: "heuristic",
      },

      postRoteirizadorGenerate: {
        tema: "astronomia",
        angulo: "Do mito ao dado: o que já medimos sobre buracos negros",
        youtube_context: {},
        roteiro_base:
          "[hook] Gancho com pergunta sobre o que 'realmente' acontece perto do horizonte de eventos.\n" +
          "[corpo] Três evidências observacionais (lente gravitacional, ondas gravitacionais, sombra).\n" +
          "[fechamento] Convite à curiosidade responsável: onde buscar fontes confiáveis.",
        partes: [
          { id: "hook", title: "Abertura — promessa e pergunta central" },
          { id: "corpo", title: "Evidências que mudaram o jogo" },
          { id: "fechamento", title: "O que ainda não sabemos" },
        ],
        textos: [
          {
            id: "hook",
            text:
              "Será que cair num buraco negro é como nos filmes? Vamos separar ficção do que já foi medido por telescópios e detectores de ondas gravitacionais.",
          },
          {
            id: "corpo",
            text:
              "Primeiro: curvatura da luz ao redor de massas enormes. Segundo: fusões de estrelas de neutrons observadas em interferômetros. Terceiro: imagens da sombra em M87* e Sagittarius A* — não é arte conceitual, é dado.",
          },
          {
            id: "fechamento",
            text:
              "Ainda há debates sobre informação e singularidades. Se quiser aprofundar, prefira revisão por pares e divulgação ligada a instituições científicas. Que pergunta você quer que a gente explore no próximo vídeo?",
          },
        ],
        timing: [],
        scenes: [
          {
            scene_idx: 0,
            part_id: "hook",
            start: "00:00",
            end: "00:18",
            prompt:
              "Wide shot: night sky with Milky Way, subtle telescope silhouette, cinematic documentary lighting",
          },
          {
            scene_idx: 1,
            part_id: "corpo",
            start: "00:18",
            end: "01:10",
            prompt:
              "Scientific visualization: gravitational lensing distortion around a black sphere, clean labels in English",
          },
          {
            scene_idx: 2,
            part_id: "corpo",
            start: "01:10",
            end: "02:05",
            prompt:
              "LIGO-style interferometer schematic, waves propagating, dark blue tech palette",
          },
          {
            scene_idx: 3,
            part_id: "fechamento",
            start: "02:05",
            end: "02:40",
            prompt:
              "Observatory dome opening at dusk, soft purple horizon, no text overlay",
          },
        ],
        provider: "template",
      },

      postImageResearchSearch: {
        scene_prompt:
          "Milky way core over desert observatory, long exposure, subtle purple nebula, cinematic wide",
        style_guide: "cinematic documentary, realistic lighting, high detail",
        query: "milky way observatory night sky",
        enabled_sources: ["pexels", "pixabay", "unsplash", "nasa", "wikimedia"],
        assets: [
          {
            asset_type: "image",
            url: "https://images.pexels.com/photos/1257860/pexels-photo-1257860.jpeg",
            preview_url: "https://images.pexels.com/photos/1257860/pexels-photo-1257860.jpeg",
            source: "pexels",
            license: "Pexels License (free to use)",
            author: "Demo",
            text: "night sky stars milky way",
            query: "milky way observatory night sky",
          },
          {
            asset_type: "image",
            url: "https://cdn.pixabay.com/photo/2016/11/29/05/45/astronomy-1867616_1280.jpg",
            preview_url: "https://cdn.pixabay.com/photo/2016/11/29/05/45/astronomy-1867616_1280.jpg",
            source: "pixabay",
            license: "Pixabay License",
            author: "Demo",
            text: "astronomy galaxy night",
            query: "milky way observatory night sky",
          },
          {
            asset_type: "image",
            url: "https://images.unsplash.com/photo-1444703686981-a3abbc4d4fe3?w=800",
            preview_url: "https://images.unsplash.com/photo-1444703686981-a3abbc4d4fe3?w=800",
            source: "unsplash",
            license: "Unsplash License",
            author: "Demo",
            text: "starry sky night",
            query: "milky way observatory night sky",
          },
        ],
        selected_idx: 0,
        selected_asset: {
          asset_type: "image",
          url: "https://images.pexels.com/photos/1257860/pexels-photo-1257860.jpeg",
          preview_url: "https://images.pexels.com/photos/1257860/pexels-photo-1257860.jpeg",
          source: "pexels",
          license: "Pexels License (free to use)",
          author: "Demo",
          text: "night sky stars milky way",
          query: "milky way observatory night sky",
        },
        ranker: "heuristic",
        reason: "Sobreposição lexical com o prompt e bônus por preview disponível (demo).",
      },

      getTtsAgentOptions: {
        providers: ["kokoro", "piper"],
        tts_lab: {
          TTS_PROVIDER: "kokoro,piper",
          TTS_PROVIDER_DEFAULT: "kokoro",
        },
        kokoro: {
          available: true,
          voices: ["pf_dora", "pm_alex", "pm_santa"],
          langs: ["pt-br", "en-us"],
          env: {
            KOKORO_MODEL: "kokoro-v0_19.onnx",
            KOKORO_VOICES: "",
            KOKORO_VOICE: "",
            KOKORO_LANG: "pt-br",
            KOKORO_SPEED: "1.0",
          },
        },
        piper: {
          available: true,
          models: [
            {
              value: "/demo/piper/pt_BR-faber-medium.onnx",
              label: "pt_BR-faber-medium (demo offline)",
            },
          ],
          env: { PIPER_MODEL: "/demo/piper/pt_BR-faber-medium.onnx" },
          PIPER_VOICES_DIR: "/demo/piper",
          catalog_path: "workshop/tts_experiments/data/piper_hf_voice_catalog.json",
        },
        selected: { provider: "kokoro" },
      },

      postTtsAgentPreview: {
        ok: true,
        provider: "kokoro",
        audio_path: "/demo/nfs/jobs/demo_offline/narration.wav",
        job_token: "demo_offline_job",
        narration_url: DEMO_SAMPLE_AUDIO,
        detail: null,
      },

      postVisualAgentPreview: {
        ok: true,
        mode: "mock_mp4",
        result_url: DEMO_SAMPLE_VIDEO,
        warnings: [],
        clip_path: "/demo/nfs/jobs/demo_offline/clips/scene_00.mp4",
        token: "demo_visual_token",
        detail: "ComfyUI simulado (offline).",
      },

      postVisualAgentBatch: {
        ok: true,
        mode: "mock",
        job_token: "demo_offline_job",
        clips: [DEMO_SAMPLE_VIDEO],
      },

      postComposerAgentPreview: {
        ok: true,
        job_token: "demo_offline_job",
        video_path: "/demo/nfs/jobs/demo_offline/final.mp4",
        video_url: DEMO_SAMPLE_VIDEO,
      },

      postMetadataAgentPreview: {
        ok: true,
        metadata: {
          title: "Astronomia — buracos negros medidos (demo offline)",
          description: "Metadados fictícios gerados para espelhar POST /api/metadata_agent/preview.",
          tags: ["demo", "astronomia", "pipeline"],
          title_variants: [
            "Buracos negros — o que já medimos",
            "Do horizonte de eventos ao Nobel",
          ],
          description_options: [
            { label: "Curta", text: "Descrição compacta para mobile." },
            { label: "Completa", text: "Descrição com bullet points fictícios." },
          ],
        },
      },

      getLabUiConfig: {
        visual_use_comfyui_default: true,
      },

      postPublishGrowthEnginePreview: {
        ok: true,
        metadata: {
          title: "Buracos negros — do mito à medição (demo Growth)",
          description:
            "Descrição fictícia do Growth Engine para demo offline.\n\nCapítulos estimados para narrativa.",
          tags: ["demo", "growth", "astronomia"],
        },
        growth: {
          title_variants: [
            "Buracos negros explicados em poucos minutos",
            "O que já medimos sobre singularidades?",
          ],
          description_options: [
            { label: "Curta", text: "Versão curta para descrição YouTube." },
            { label: "Completa", text: "Versão com capítulos para desktop." },
          ],
          thumbnail_concepts: [
            {
              template_id: "logo_brand",
              texto_curto: "Sombras cósmicas",
            },
            {
              template_id: "impact_number",
              texto_curto: "99% desconhecido?",
            },
          ],
        },
      },

      postThumbnailCardAgentPreview: {
        ok: true,
        thumbnail_url: "",
        thumbnail_path: "",
        thumbnail: {},
      },

      postLabSyncCompose: {
        ok: true,
        job_token: "demo_offline_job",
        video_url: DEMO_SAMPLE_VIDEO,
        timeline_url: "",
      },

      getYoutubeChannels: {
        status: "ok",
        channels: [
          {
            id: "UCdemo",
            title: "Canal Demo Offline",
            custom_url: "",
            published_at: "2020-01-01T00:00:00Z",
          },
        ],
      },

      postYoutubeUpload: {
        ok: true,
        video_id: "demo_offline_yt_id",
        publish_status: "uploaded:demo_offline_yt_id",
        privacy: "private",
      },

      postLabAsr: {
        ok: true,
        job_token: "demo_offline_job",
        language: "pt",
        duration_s: 42.5,
        vtt_url: "/api/lab/job/demo_offline_job/narration_asr.vtt",
        srt_url: "/api/lab/job/demo_offline_job/narration_asr.srt",
        json_url: "/api/lab/job/demo_offline_job/asr_words.json",
      },
    },
  };

  const pack = global.VideoStudioOfflineMockData.responses.postResearchYoutubeTrends;
  pack.trends_panel.interest_over_time = pack.trends.interest_over_time;
  pack.suggestions = pack.video_suggestions;

  /**
   * Continuação fictícia do LangGraph após asset_agent — alinhado ao contrato VideoState (.cursorrules).
   * Não chama GPU/TTS/ffmpeg; apenas deriva paths e metadados a partir do que a UI já tem (roteiro + image research).
   */
  function slugifyNiche(niche) {
    const s = String(niche || "demo")
      .trim()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
    return (s || "demo").slice(0, 20);
  }

  function scenePromptsFromRoteiro(scenes) {
    if (!Array.isArray(scenes) || !scenes.length) {
      return ["Wide shot: night sky with Milky Way, cinematic documentary (demo offline)"];
    }
    return scenes.map((s) => String(s && s.prompt ? s.prompt : "").trim()).filter(Boolean);
  }

  function scriptFromTextos(textos, roteiroBase) {
    if (Array.isArray(textos) && textos.length) {
      const parts = textos
        .filter((p) => p && p.id && p.text)
        .map((p) => `[${p.id}] ${String(p.text).trim()}`);
      if (parts.length) return parts.join("\n\n");
    }
    const rb = String(roteiroBase || "").trim();
    return rb || "Narração PT-BR fictícia para demo offline.";
  }

  function buildRawAssets(imageSearch, scenePrompts) {
    const out = [];
    const assets = imageSearch && Array.isArray(imageSearch.assets) ? imageSearch.assets : [];
    const selIdx =
      imageSearch && Number.isFinite(Number(imageSearch.selected_idx)) ? Number(imageSearch.selected_idx) : 0;
    const primary = imageSearch && imageSearch.selected_asset ? imageSearch.selected_asset : assets[selIdx] || null;
    const n = Math.max(1, scenePrompts.length);

    for (let i = 0; i < n; i++) {
      const a = i === 0 && primary ? primary : assets[i % Math.max(1, assets.length)] || primary;
      if (!a) {
        out.push({
          scene_idx: i,
          url: "",
          local_path: "",
          source: "demo",
          license: "n/a",
        });
        continue;
      }
      const url = String(a.url || a.preview_url || "").trim();
      out.push({
        scene_idx: i,
        url,
        local_path: `/demo/nfs/assets/scene_${String(i).padStart(2, "0")}_raw.jpg`,
        source: String(a.source || "unknown"),
        license: String(a.license || ""),
      });
    }
    return out;
  }

  function buildTrendingSnapshot(researchPack) {
    const titles = [];
    const views = [];
    const sug = (researchPack && (researchPack.video_suggestions || researchPack.suggestions)) || [];
    for (const it of sug) {
      if (it && it.title) titles.push(String(it.title));
      if (it && (it.views != null || (it.payload && it.payload.youtube_context && it.payload.youtube_context.views))) {
        views.push(String(it.views || (it.payload && it.payload.youtube_context && it.payload.youtube_context.views) || ""));
      }
    }
    return {
      top_titles: titles.slice(0, 5),
      top_views: views.slice(0, 5),
      trend_score: 42,
    };
  }

  global.VideoStudioOfflinePipelineMock = {
    /** @param {{ channel_niche?: string, tema?: string, angulo?: string, roteiro?: object, imageSearch?: object, researchPack?: object }} opts */
    buildVideoStateTail(opts) {
      const channel_niche = String((opts && opts.channel_niche) || (opts && opts.tema) || "astronomia e espaço").trim();
      const tema = String((opts && opts.tema) || "astronomia").trim();
      const angulo = String((opts && opts.angulo) || "Ângulo demo offline").trim();
      const roteiro = (opts && opts.roteiro) || {};
      const scenePrompts = scenePromptsFromRoteiro(roteiro.scenes);
      const n = scenePrompts.length;
      const slug = slugifyNiche(channel_niche);
      const job_path = `/mnt/nas/video-pipeline/jobs/${slug}_demo_20260414_120000`;
      const imageSearch = opts && opts.imageSearch;
      const raw_assets = buildRawAssets(imageSearch, scenePrompts);
      const clips = Array.from({ length: n }, (_, i) => `${job_path}/clips/scene_${String(i).padStart(2, "0")}.mp4`);
      const audio_file = `${job_path}/narration.wav`;
      const video_file = `${job_path}/final.mp4`;
      const trending_data = buildTrendingSnapshot(opts && opts.researchPack);
      const script = scriptFromTextos(roteiro.textos, roteiro.roteiro_base);
      const titleBase = tema.length > 48 ? `${tema.slice(0, 45)}…` : tema;
      const metadata = {
        title: `${titleBase} — ${angulo.length > 40 ? angulo.slice(0, 37) + "…" : angulo} (demo)`,
        description:
          `Vídeo fictício gerado na demo offline.\n\nTema: ${tema}\nÂngulo: ${angulo}\n\nClipes: ${n} · Narração simulada (Kokoro/Piper no pipeline real).`,
        tags: ["demo", "ideias-factory", slug, "astronomia", "pipeline-mock"],
      };

      return {
        channel_niche,
        topic: tema,
        angle: angulo,
        trending_data,
        script,
        scenes: scenePrompts,
        raw_assets,
        clips,
        audio_file,
        video_file,
        metadata,
        publish_status: "uploaded:demo_offline_video_id",
        job_path,
      };
    },
  };
})(typeof window !== "undefined" ? window : globalThis);
