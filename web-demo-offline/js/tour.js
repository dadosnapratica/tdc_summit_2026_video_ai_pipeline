/**
 * Tour guiado leve (sem dependências externas) para a demo offline.
 */
(function (global) {
  "use strict";

  var STORAGE_KEY = "video_studio_demo_tour_done_v2";

  /**
   * Cada passo pode incluir:
   * - tab: nome da aba principal (setActiveTab no app.js)
   * - researchSub: "videos" | "trends" (sub-abas do Research)
   * - assetsMode: "auto" | "manual" (Image Research)
   */
  var STEPS = [
    {
      title: "Bem-vindo à demo IA VideoStudio",
      body:
        "Esta versão corre só no navegador com dados fictícios em mock_data.js — útil para vendas e onboarding sem backend. Use «Seguinte» para percorrer cada aba ou «Saltar».",
      target: null,
    },
    {
      title: "Modo demonstração",
      body:
        "O aviso no topo indica que não há servidor: health e APIs são simulados por LabApi em mock_api.js.",
      target: "#demo_banner",
    },
    {
      title: "Navegação por abas",
      body:
        "Oito áreas: Fluxo, Research, Roteirizador, Scenes, Image Research, Visual (GPU), Compor vídeo e Publicar. O tour abre cada uma em sequência.",
      target: ".tabs",
    },
    {
      title: "Fluxo — grafo do pipeline",
      tab: "fluxo",
      body:
        "Visão LangGraph: START → research → script → assets → visual → TTS → composer → metadata/thumbnail → publisher. O ramo tracejado à direita é o refino opcional do laboratório (ASR → segmentação → vídeo sincronizado). Passe o rato nos retângulos para ver tooltips.",
      target: "#flow_graph_wrap",
    },
    {
      title: "Research — contexto da busca",
      tab: "research",
      body:
        "Keyword para YouTube + Trends, região e categoria alinham-se ao contrato do BFF. Os valores alimentam «Buscar sugestões» e cartões fictícios.",
      target: "#research_kw",
    },
    {
      title: "Research — disparar pesquisa",
      tab: "research",
      body:
        "«Buscar sugestões» devolve vídeos em mock_data e painéis Trends — mesmo formato que o laboratório quando ligado ao cluster.",
      target: "#btn-research",
    },
    {
      title: "Research — resultados em vídeos",
      tab: "research",
      researchSub: "videos",
      body:
        "Separador Vídeos: cartões com título, canal e métricas de exemplo — útil para escolher ângulo e citar tendências na reunião.",
      target: "#research_videos",
    },
    {
      title: "Research — Google Trends",
      tab: "research",
      researchSub: "trends",
      body:
        "Separador Trends: queries relacionadas e interesse ao longo do tempo (gráficos Chart.js no lab; aqui dados de exemplo).",
      target: "#research_trends",
    },
    {
      title: "Roteirizador — duração e perfil",
      tab: "roteiro",
      body:
        "Tema, ângulo e «Duração (narração alvo)» orientam o tamanho do roteiro e o número de partes/cenas. «Sugerir ângulos» e «Gerar» usam mock_api.",
      target: "#duration-tier",
    },
    {
      title: "Roteirizador — gerar texto",
      tab: "roteiro",
      body:
        "«Sugerir ângulos» preenche sugestões; «Gerar» produz roteiro PT-BR, textos por parte e prompts de cena. Opcional «Usar Ollama» só no backend real.",
      target: "#btn-generate",
    },
    {
      title: "Roteirizador — saída",
      tab: "roteiro",
      body:
        "«Roteiro base» e «Textos por parte» espelham o contrato do script_agent. Botões copiar ajudam a colar em docs ou CRM.",
      target: "#roteiro_base",
    },
    {
      title: "Scenes — prompts por tempo",
      tab: "scenes",
      body:
        "Lista janelas de narração com prompt visual EN por cena. «Usar 1ª cena no Image Research» envia o primeiro prompt para a aba seguinte.",
      target: "#btn-use-first-scene",
    },
    {
      title: "Scenes — lista de cenas",
      tab: "scenes",
      body:
        "Cada cartão é uma cena editável (scene_idx, texto, prompt). É a ponte entre roteiro e assets visuais.",
      target: "#scenes",
    },
    {
      title: "Image Research — busca em massa",
      tab: "assets",
      assetsMode: "auto",
      body:
        "Modo automático: style guide, preferência vídeo/imagem e «Pesquisar para todas as cenas» simula asset_agent multi-fonte e ranker.",
      target: "#btn-search-all",
    },
    {
      title: "Image Research — seleções e próximo passo",
      tab: "assets",
      assetsMode: "auto",
      body:
        "«Selecionados por cena» resume o audit trail; «Gerar vídeo» salta para Compor vídeo (wizard) quando quiser narrar o fluxo ao cliente.",
      target: "#btn-go-composer",
    },
    {
      title: "Image Research — modo manual",
      tab: "assets",
      assetsMode: "manual",
      body:
        "Por cena: escolha a cena, ajuste prompt e «Pesquisar». «Selecionado» e «Candidatos» mostram curadoria e lista completa para compliance.",
      target: "#btn-search",
    },
    {
      title: "Visual (GPU) — clipe por imagem",
      tab: "visual",
      body:
        "URL da imagem, scene_idx, opção ComfyUI/AnimateDiff e «Gerar clipe (preview)» espelham visual_agent. «Usar imagem selecionada» traz o asset escolhido no Image Research.",
      target: "#btn-visual-preview",
    },
    {
      title: "Compor vídeo — visão geral",
      tab: "composer",
      body:
        "Aqui você encena o pipeline de ponta a ponta num «job». A lógica real roda no BFF/cluster; nesta demo é mock — o objetivo é mostrar o fluxo e as saídas.",
      target: "#btn-composer-tts",
    },
    {
      title: "Compor vídeo — passos 1 a 5",
      tab: "composer",
      body:
        "1) Gerar TTS: cria a narração. 2) Gerar clipes: gera 1 MP4 por cena. 3) Gerar vídeo final: concatena clipes + áudio. 4) ASR: gera VTT/SRT e words. 5) Sincronismo: refino avançado por timeline (lab).",
      target: "#btn-composer-visual",
    },
    {
      title: "Compor vídeo — sessão",
      tab: "composer",
      body:
        "«Novo job» reinicia o token; após cada passo simulado aparecem pré-visualizações de áudio/vídeo quando aplicável.",
      target: "#composer_job_token",
    },
    {
      title: "Publicar — metadados",
      tab: "publish",
      body:
        "LLM e Growth Engine geram título, descrição com capítulos e tags — payloads de exemplo. «Salvar metadados» mantém o rascunho na sessão.",
      target: "#btn-pub-llm-meta",
    },
    {
      title: "Publicar — thumbnail",
      tab: "publish",
      body:
        "Templates SVG, campos editáveis e «Gerar thumbnail» (canvas local na demo). Alinha-se ao thumbnail_card_agent no pipeline real.",
      target: "#btn-generate-thumb",
    },
    {
      title: "Publicar — YouTube",
      tab: "publish",
      body:
        "«Conectar YouTube» / «Carregar canais» simulam OAuth; «Enviar ao YouTube» e «Simular publicação» cobrem upload real vs mock.",
      target: "#btn-youtube-upload-real",
    },
    {
      title: "Estado dos serviços",
      body:
        "O indicador reflecte GET /health simulado. Clique para ver JSON no modal — no laboratório real abre /health num separador.",
      target: "#header_health",
    },
    {
      title: "OpenAPI",
      body:
        "«OpenAPI» não abre Swagger aqui (sem host). Com uvicorn no BFF use /swagger — ex.: http://127.0.0.1:8092/swagger.",
      target: "#link_openapi_hint",
    },
    {
      title: "Navegue e aproveite",
      body:
        "Agora é contigo: navegue pelas abas, teste os botões e use isto como narrativa (pipeline → outputs) para explicar a solução. Depois de explorar, deixa um feedback rápido — ajuda a priorizar o que entra no produto.",
      wrapup: true,
      target: null,
    },
    {
      title: "Feedback (após explorar)",
      body:
        "Quando terminar de explorar a demo, clique em «Feedback» (canto inferior direito) e diga: o que faltou, o que confundiu e o que mais impressionou. Esse retorno é o mais valioso para evoluirmos o workshop.",
      wrapup: true,
      target: "#demo_fab_btn",
    },
    {
      title: "Pronto",
      body:
        "Repita o tour com «Tour guiado». Integração técnica: workshop/bff/lab_server.py e workshop/web/js/services.js.",
      target: null,
    },
  ];

  function $(sel) {
    return document.querySelector(sel);
  }

  /** Alinha UI do app.js antes de medir rects (painéis inativos estão em display:none). */
  function prepareStepContext(step) {
    try {
      if (step.tab && typeof global.setActiveTab === "function") {
        global.setActiveTab(step.tab);
      }
      if (step.researchSub && typeof global.setResearchSubTab === "function") {
        global.setResearchSubTab(step.researchSub);
      }
      if (step.assetsMode && typeof global.setAssetsMode === "function") {
        global.setAssetsMode(step.assetsMode);
      }
    } catch (e) {}
  }

  function ensureOverlay() {
    var root = $("#tour_root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "tour_root";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.innerHTML =
      '<div class="tour-backdrop" id="tour_backdrop"></div>' +
      '<div class="tour-card" id="tour_card">' +
      '  <div class="tour-card-head">' +
      '    <div class="tour-step-label" id="tour_step_label"></div>' +
      '    <button type="button" class="btn btn-ghost tour-skip" id="tour_skip">Saltar</button>' +
      "  </div>" +
      '  <div class="tour-title" id="tour_title"></div>' +
      '  <div class="tour-body" id="tour_body"></div>' +
      '  <div class="tour-actions">' +
      '    <button type="button" class="btn btn-ghost" id="tour_prev">Anterior</button>' +
      '    <button type="button" class="btn" id="tour_next">Seguinte</button>' +
      "  </div>" +
      "</div>" +
      '<div class="tour-spotlight" id="tour_spotlight" hidden></div>';
    document.body.appendChild(root);
    return root;
  }

  var idx = 0;
  var active = false;

  function placeCard(step) {
    var card = $("#tour_card");
    var spot = $("#tour_spotlight");
    if (!card || !spot) return;

    if (!step || !step.target) {
      spot.hidden = true;
      card.classList.add("tour-card--center");
      card.style.left = "50%";
      card.style.top = "45%";
      card.style.transform = "translate(-50%, -50%)";
      return;
    }

    var el = $(step.target);
    card.classList.remove("tour-card--center");
    if (!el) {
      spot.hidden = true;
      card.classList.add("tour-card--center");
      card.style.left = "50%";
      card.style.top = "45%";
      card.style.transform = "translate(-50%, -50%)";
      return;
    }

    var r = el.getBoundingClientRect();
    var pad = 8;
    spot.hidden = false;
    spot.style.left = r.left - pad + "px";
    spot.style.top = r.top - pad + "px";
    spot.style.width = r.width + pad * 2 + "px";
    spot.style.height = r.height + pad * 2 + "px";

    var cw = card.offsetWidth || 340;
    var ch = card.offsetHeight || 200;
    var left = r.left + r.width / 2 - cw / 2;
    var top = r.bottom + 12;
    if (top + ch > window.innerHeight - 16) {
      top = r.top - ch - 12;
    }
    left = Math.max(12, Math.min(left, window.innerWidth - cw - 12));
    top = Math.max(12, Math.min(top, window.innerHeight - ch - 12));
    card.style.left = left + "px";
    card.style.top = top + "px";
    card.style.transform = "none";

    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function emitTour(detail) {
    try {
      document.dispatchEvent(new CustomEvent("videostudio-demo-tour", { detail: detail }));
    } catch (e) {}
  }

  function firstWrapupIndex() {
    var i;
    for (i = 0; i < STEPS.length; i++) {
      if (STEPS[i] && STEPS[i].wrapup) return i;
    }
    return -1;
  }

  function isInWrapup() {
    var s = STEPS[idx];
    return !!(s && s.wrapup);
  }

  function renderStep() {
    var step = STEPS[idx];
    prepareStepContext(step);
    $("#tour_step_label").textContent = "Passo " + (idx + 1) + " / " + STEPS.length;
    $("#tour_title").textContent = step.title;
    $("#tour_body").textContent = step.body;
    $("#tour_prev").disabled = idx === 0;
    $("#tour_next").textContent = idx === STEPS.length - 1 ? "Concluir" : "Seguinte";

    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        placeCard(step);
      });
    });
  }

  function openTour() {
    ensureOverlay();
    active = true;
    idx = 0;
    emitTour({ phase: "started" });
    $("#tour_root").style.display = "block";
    document.body.classList.add("tour-open");
    renderStep();

    $("#tour_next").onclick = function () {
      if (idx >= STEPS.length - 1) {
        closeTour(true);
        return;
      }
      idx += 1;
      renderStep();
    };
    $("#tour_prev").onclick = function () {
      if (idx <= 0) return;
      idx -= 1;
      renderStep();
    };
    $("#tour_skip").onclick = function () {
      closeTour(false);
    };
    $("#tour_backdrop").onclick = function () {
      closeTour(false);
    };

    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKey);
  }

  function onResize() {
    if (!active) return;
    renderStep();
  }

  function onKey(ev) {
    if (!active) return;
    if (ev.key === "Escape") closeTour(false);
  }

  function closeTour(markDone) {
    // Se o utilizador saltar antes do fim, ainda mostramos as mensagens finais (navegação + feedback).
    if (!markDone && active && !isInWrapup()) {
      var wi = firstWrapupIndex();
      if (wi >= 0) {
        idx = wi;
        emitTour({ phase: "wrapup" });
        renderStep();
        return;
      }
    }

    active = false;
    emitTour({ phase: markDone ? "completed" : "skipped" });
    var root = $("#tour_root");
    if (root) root.style.display = "none";
    document.body.classList.remove("tour-open");
    window.removeEventListener("resize", onResize);
    window.removeEventListener("keydown", onKey);
    if (markDone) {
      try {
        global.localStorage.setItem(STORAGE_KEY, "1");
      } catch (e) {}
    }
  }

  function maybeOfferFirstVisit() {
    try {
      if (global.localStorage.getItem(STORAGE_KEY)) return;
    } catch (e) {}
    setTimeout(function () {
      if (!confirm("Quer um tour rápido pelas áreas principais da demo?")) {
        emitTour({ phase: "offer_declined" });
        try {
          global.localStorage.setItem(STORAGE_KEY, "1");
        } catch (e) {}
      } else {
        emitTour({ phase: "offer_accepted" });
        openTour();
      }
    }, 600);
  }

  global.VideoStudioDemoTour = {
    start: openTour,
    offerOnFirstVisit: maybeOfferFirstVisit,
  };
})(typeof window !== "undefined" ? window : globalThis);
