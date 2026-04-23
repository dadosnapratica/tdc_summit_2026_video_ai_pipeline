const $ = (id) => document.getElementById(id);

/** Lista de vídeos: id novo `research_videos`; fallback `research_out` evita crash se HTML/JS estiverem dessincronizados (cache). */
function researchVideosHost() {
  return $("research_videos") || $("research_out");
}

function researchTrendsHost() {
  return $("research_trends");
}

function setActiveTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("is-active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("is-active", p.id === `tab-${name}`));
  if (name === "composer") refreshComposerPrereq();
}

function setResearchSubTab(name) {
  const key = name === "trends" ? "trends" : "videos";
  document.querySelectorAll("[data-research-sub]").forEach((b) => {
    b.classList.toggle("is-active", (b.getAttribute("data-research-sub") || "") === key);
  });
  const v = researchVideosHost();
  const t = researchTrendsHost();
  if (v) v.classList.toggle("is-active", key === "videos");
  if (t) t.classList.toggle("is-active", key === "trends");
}

function setAssetsMode(name) {
  const key = name === "manual" ? "manual" : "auto";
  document.querySelectorAll("[data-assets-mode]").forEach((b) => {
    b.classList.toggle("is-active", (b.getAttribute("data-assets-mode") || "") === key);
  });
  const a = $("assets_mode_auto");
  const m = $("assets_mode_manual");
  if (a) a.classList.toggle("is-active", key === "auto");
  if (m) m.classList.toggle("is-active", key === "manual");
}

function buildChaptersFromTiming(textos, timing) {
  const tmap = buildTimingMap(timing);
  const lines = [];
  (textos ?? []).forEach((p) => {
    if (!p?.id || p.id === "title") return;
    const t = tmap[p.id];
    if (!t) return;
    const tc = fmtTimecodeFromSeconds(t.start_s);
    // título simples por id
    const label = p.id === "hook" ? "Abertura" : p.id === "context" ? "Contexto" : p.id === "close" ? "Encerramento" : p.id;
    lines.push(`${tc} ${label}`);
  });
  return lines.join("\n");
}

function ensurePublishDraft() {
  if (!lastGenerate) lastGenerate = {};
  if (!lastGenerate.publish_draft) lastGenerate.publish_draft = {};
  if (!lastGenerate.thumbnail_draft) lastGenerate.thumbnail_draft = {};

  const md = lastGenerate.metadata || {};
  const title = String(lastGenerate.publish_draft.title || md.title || "").trim();
  const tagsArr = Array.isArray(md.tags) ? md.tags : [];
  const tags = String(lastGenerate.publish_draft.tags || tagsArr.join(", ") || "").trim();
  const chapters = buildChaptersFromTiming(lastGenerate.textos || [], lastGenerate.timing || []);
  const baseDesc = String(md.description || "").trim();
  const desc = String(lastGenerate.publish_draft.description || (chapters ? `${chapters}\n\n${baseDesc}`.trim() : baseDesc)).trim();

  lastGenerate.publish_draft.title = title;
  lastGenerate.publish_draft.description = desc;
  lastGenerate.publish_draft.tags = tags;
  lastGenerate.publish_draft.channel_id = String(lastGenerate.publish_draft.channel_id || "").trim();
  lastGenerate.publish_draft.channel_title = String(lastGenerate.publish_draft.channel_title || "").trim();

  // thumbnail defaults
  lastGenerate.thumbnail_draft.template_id = lastGenerate.thumbnail_draft.template_id || "logo_brand";
  lastGenerate.thumbnail_draft.brand_color = lastGenerate.thumbnail_draft.brand_color || "#7c5cff";
  lastGenerate.thumbnail_draft.title = lastGenerate.thumbnail_draft.title || (title ? title.slice(0, 60) : "");
  lastGenerate.thumbnail_draft.mode = lastGenerate.thumbnail_draft.mode || "auto_template";
}

function renderYoutubeChannels(channels) {
  const sel = $("pub_channel");
  if (!sel) return;
  sel.innerHTML = "";
  const list = Array.isArray(channels) ? channels : [];
  if (!list.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— Conecte e carregue seus canais —";
    sel.appendChild(opt);
    return;
  }
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Selecione…";
  sel.appendChild(empty);
  list.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = String(c.id || "");
    opt.textContent = String(c.title || c.custom_url || c.id || "");
    sel.appendChild(opt);
  });
  ensurePublishDraft();
  if (lastGenerate.publish_draft.channel_id) sel.value = lastGenerate.publish_draft.channel_id;
}

function renderPublishDraft() {
  const variantsSel = $("pub_title_variants");
  const descVariantsSel = $("pub_description_variants");
  const title = $("pub_title");
  const desc = $("pub_description");
  const tags = $("pub_tags");
  const channel = $("pub_channel");
  const tmpl = $("thumb_template");
  const brand = $("thumb_brand_color");
  const ttitle = $("thumb_title");
  const preview = $("thumb_preview");

  if (!title || !desc || !tags || !channel || !tmpl || !brand || !ttitle || !preview) return;
  ensurePublishDraft();

  title.value = lastGenerate.publish_draft.title || "";
  desc.value = lastGenerate.publish_draft.description || "";
  tags.value = lastGenerate.publish_draft.tags || "";
  channel.value = lastGenerate.publish_draft.channel_id || "";

  tmpl.value = lastGenerate.thumbnail_draft.template_id || "logo_brand";
  brand.value = lastGenerate.thumbnail_draft.brand_color || "#7c5cff";
  ttitle.value = lastGenerate.thumbnail_draft.title || "";
  syncThumbTemplateGridSelection();

  // Atualiza dropdown de variantes (se existir) sem sobrescrever o input manual.
  if (variantsSel) {
    syncPublishTitleVariantsUi({
      variants: lastGenerate?.publish_draft?.title_variants || lastGenerate?.growth?.title_variants || [],
      selected: title.value,
    });
  }
  if (descVariantsSel) {
    syncPublishDescriptionVariantsUi({
      variants: lastGenerate?.publish_draft?.description_variants || [],
      selectedText: desc.value,
    });
  }

  syncThumbConceptSelectUi();

  if (lastGenerate.thumbnail_draft.preview_data_url) {
    preview.src = lastGenerate.thumbnail_draft.preview_data_url;
  }
}

function syncPublishTitleVariantsUi({ variants, selected }) {
  const sel = $("pub_title_variants");
  if (!sel) return;

  const list = Array.isArray(variants) ? variants.map((x) => String(x || "").trim()).filter(Boolean) : [];
  const current = String(selected || "").trim();

  // Re-render se mudou (evita resetar selection a cada keystroke).
  const prevSig = String(sel.getAttribute("data-sig") || "");
  const sig = list.join("\n");
  if (sig !== prevSig) {
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = list.length ? "— Selecione um título sugerido —" : "— Gere metadados (LLM ou Growth) para ver sugestões —";
    sel.appendChild(opt0);

    list.forEach((t) => {
      const o = document.createElement("option");
      o.value = t;
      o.textContent = t;
      sel.appendChild(o);
    });
    sel.setAttribute("data-sig", sig);
  }

  // Mantém selecionado se o valor atual existir entre as opções; senão, volta para placeholder.
  const match = list.includes(current) ? current : "";
  if (sel.value !== match) sel.value = match;
}

function _descriptionVariantToString(x) {
  if (x == null) return "";
  if (typeof x === "string") return x.trim();
  if (typeof x === "object") {
    const t = x.text != null ? String(x.text).trim() : "";
    if (t) return t;
    return x.label != null ? String(x.label).trim() : "";
  }
  return String(x).trim();
}

function syncPublishDescriptionVariantsUi({ variants, selectedText }) {
  const sel = $("pub_description_variants");
  if (!sel) return;

  const list = Array.isArray(variants)
    ? variants.map(_descriptionVariantToString).filter(Boolean)
    : [];
  const cur = String(selectedText || "").trim();

  const prevSig = String(sel.getAttribute("data-sig") || "");
  const sig = list.join("\u0001");
  if (sig !== prevSig) {
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = list.length ? "— Escolha uma descrição sugerida —" : "— Gere metadados para ver textos completos —";
    sel.appendChild(opt0);

    list.forEach((text, idx) => {
      const o = document.createElement("option");
      o.value = String(idx);
      const preview = text.replace(/\s+/g, " ").trim();
      o.textContent = preview.length > 140 ? `${preview.slice(0, 140)}…` : preview;
      o.title = text;
      sel.appendChild(o);
    });
    sel.setAttribute("data-sig", sig);
  }

  let matchIdx = list.findIndex((t) => t === cur);
  matchIdx = matchIdx >= 0 ? String(matchIdx) : "";
  if (sel.value !== matchIdx) sel.value = matchIdx;
}

/** Modelos do card (paths relativos a ``/static/``). */
const THUMB_TEMPLATE_OPTIONS = [
  { id: "logo_brand", label: "logo_brand", img: "img/thumb-template-previews/logo_brand.svg" },
  { id: "big_title_left", label: "big_title_left", img: "img/thumb-template-previews/big_title_left.svg" },
  { id: "big_title_bottom", label: "big_title_bottom", img: "img/thumb-template-previews/big_title_bottom.svg" },
  { id: "badge_corner", label: "badge_corner", img: "img/thumb-template-previews/badge_corner.svg" },
  { id: "face_reaction", label: "face_reaction", img: "img/thumb-template-previews/face_reaction.svg" },
  { id: "impact_number", label: "impact_number", img: "img/thumb-template-previews/impact_number.svg" },
  { id: "split_layout", label: "split_layout", img: "img/thumb-template-previews/split_layout.svg" },
  { id: "arrow_focus", label: "arrow_focus", img: "img/thumb-template-previews/arrow_focus.svg" },
];

function syncThumbTemplateGridSelection() {
  const hidden = $("thumb_template");
  const grid = $("thumb_template_grid");
  if (!hidden || !grid) return;
  const v = hidden.value || "logo_brand";
  grid.querySelectorAll("[data-thumb-template]").forEach((btn) => {
    const on = btn.getAttribute("data-thumb-template") === v;
    btn.classList.toggle("is-selected", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

function wireThumbTemplatePicker() {
  const grid = $("thumb_template_grid");
  const hidden = $("thumb_template");
  if (!grid || !hidden) return;
  grid.innerHTML = "";
  THUMB_TEMPLATE_OPTIONS.forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "thumb-template-option";
    btn.setAttribute("data-thumb-template", opt.id);
    btn.setAttribute("aria-pressed", "false");
    btn.setAttribute("title", opt.id);
    const im = document.createElement("img");
    im.src = opt.img;
    im.alt = "";
    im.width = 72;
    im.height = 40;
    im.loading = "lazy";
    const lab = document.createElement("span");
    lab.className = "thumb-template-option-label";
    lab.textContent = opt.label;
    btn.appendChild(im);
    btn.appendChild(lab);
    btn.onclick = () => {
      hidden.value = opt.id;
      if (!lastGenerate) lastGenerate = {};
      ensurePublishDraft();
      lastGenerate.thumbnail_draft.template_id = opt.id;
      syncThumbTemplateGridSelection();
    };
    grid.appendChild(btn);
  });
  syncThumbTemplateGridSelection();
}

/** Mapeia template_id do Growth para valores do campo ``thumb_template`` (hidden). */
function normalizeThumbTemplateForUi(raw) {
  const s = String(raw || "").trim().toLowerCase();
  const allowed = new Set([
    "logo_brand",
    "big_title_left",
    "big_title_bottom",
    "badge_corner",
    "face_reaction",
    "impact_number",
    "split_layout",
    "arrow_focus",
  ]);
  if (allowed.has(s)) return s;
  return "impact_number";
}

function syncThumbConceptSelectUi() {
  const sel = $("thumb_concept");
  if (!sel) return;
  const concepts = Array.isArray(lastGenerate?.growth?.thumbnail_concepts)
    ? lastGenerate.growth.thumbnail_concepts.filter((c) => c && typeof c === "object")
    : [];
  const sig = JSON.stringify(
    concepts.map((c) => ({
      t: c.template_id,
      x: c.texto_curto,
    })),
  );
  const prevSig = String(sel.getAttribute("data-sig") || "");
  if (sig !== prevSig) {
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = concepts.length
      ? "— Escolha um conceito (ou edite template/texto abaixo) —"
      : "— Gere metadados no Growth Engine para ver conceitos —";
    sel.appendChild(opt0);
    concepts.slice(0, 3).forEach((c, i) => {
      const tid = String(c.template_id || "?").trim();
      const short = String(c.texto_curto || "").trim().slice(0, 48);
      const o = document.createElement("option");
      o.value = String(i);
      o.textContent = `${i + 1}. ${tid}${short ? ` · ${short}` : ""}`;
      sel.appendChild(o);
    });
    sel.setAttribute("data-sig", sig);
  }
  const idx = lastGenerate?.thumbnail_draft?.concept_idx;
  const want = Number.isFinite(idx) && idx >= 0 && idx < concepts.length ? String(idx) : "";
  if (sel.value !== want) sel.value = want;
}

function applyThumbnailConceptIndex(idx) {
  if (!lastGenerate) lastGenerate = {};
  ensurePublishDraft();
  const concepts = Array.isArray(lastGenerate.growth?.thumbnail_concepts)
    ? lastGenerate.growth.thumbnail_concepts.filter((c) => c && typeof c === "object")
    : [];
  if (!concepts.length || idx < 0 || idx >= concepts.length) return;
  const c = concepts[idx];
  const tmpl = normalizeThumbTemplateForUi(c.template_id);
  const txt = String(c.texto_curto || "").trim().slice(0, 60);
  lastGenerate.thumbnail_draft.template_id = tmpl;
  if (txt) lastGenerate.thumbnail_draft.title = txt;
  lastGenerate.thumbnail_draft.concept_idx = idx;
  const elTmpl = $("thumb_template");
  const elTitle = $("thumb_title");
  const elConcept = $("thumb_concept");
  if (elTmpl) elTmpl.value = tmpl;
  if (elTitle && txt) elTitle.value = txt;
  if (elConcept) elConcept.value = String(idx);
  syncThumbTemplateGridSelection();
}

function drawThumbnailMock({ templateId, brandColor, titleText, logoDataUrl, bgDataUrl }) {
  const canvas = document.createElement("canvas");
  canvas.width = 1280;
  canvas.height = 720;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const drawBase = () => {
    // background
    if (!bgDataUrl) {
      const g = ctx.createLinearGradient(0, 0, 1280, 720);
      g.addColorStop(0, "rgba(124,92,255,0.22)");
      g.addColorStop(1, "rgba(0,212,255,0.16)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 1280, 720);
    } else {
      // CORS-safe: só dataURL (upload)
      // desenhar será feito no onload
    }

    // dark overlay bottom
    const og = ctx.createLinearGradient(0, 0, 0, 720);
    og.addColorStop(0.0, "rgba(0,0,0,0.0)");
    og.addColorStop(1.0, "rgba(0,0,0,0.72)");
    ctx.fillStyle = og;
    ctx.fillRect(0, 0, 1280, 720);

    // accent bar
    ctx.fillStyle = brandColor || "#7c5cff";
    ctx.fillRect(42, 720 - 240, 14, 200);

    // title
    ctx.font = "bold 64px system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(245,247,255,0.98)";
    ctx.strokeStyle = "rgba(0,0,0,0.75)";
    ctx.lineWidth = 10;
    const maxW = 1180;
    const words = String(titleText || "").trim().split(/\s+/).filter(Boolean);
    const lines = [];
    let cur = "";
    for (const w of words) {
      const cand = (cur + " " + w).trim();
      if (ctx.measureText(cand).width <= maxW || !cur) cur = cand;
      else {
        lines.push(cur);
        cur = w;
      }
      if (lines.length >= 4) break;
    }
    if (cur && lines.length < 5) lines.push(cur);
    let y = 720 - 230;
    for (const ln of lines) {
      ctx.strokeText(ln, 80, y);
      ctx.fillText(ln, 80, y);
      y += 74;
    }

    // template variations (very light)
    if (templateId === "big_title_bottom") {
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(0, 720 - 200, 1280, 200);
    }
    if (templateId === "badge_corner") {
      ctx.fillStyle = brandColor || "#7c5cff";
      ctx.fillRect(980, 52, 250, 64);
      ctx.fillStyle = "rgba(245,247,255,0.98)";
      ctx.font = "800 28px system-ui, -apple-system, Segoe UI, Roboto";
      ctx.fillText("TOP", 1050, 68);
    }
  };

  const finalize = () => canvas.toDataURL("image/png");

  if (!bgDataUrl && !logoDataUrl) {
    drawBase();
    return finalize();
  }

  // Load images sequentially if present
  const loadImg = (dataUrl) =>
    new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = dataUrl;
    });

  return (async () => {
    let bg = null;
    let logo = null;
    if (bgDataUrl) bg = await loadImg(bgDataUrl);
    if (logoDataUrl) logo = await loadImg(logoDataUrl);

    if (bg) {
      // cover crop
      const ar = bg.width / bg.height;
      const tar = 1280 / 720;
      let sx = 0,
        sy = 0,
        sw = bg.width,
        sh = bg.height;
      if (ar > tar) {
        sw = Math.floor(bg.height * tar);
        sx = Math.floor((bg.width - sw) / 2);
      } else {
        sh = Math.floor(bg.width / tar);
        sy = Math.floor((bg.height - sh) / 2);
      }
      ctx.drawImage(bg, sx, sy, sw, sh, 0, 0, 1280, 720);
    }

    drawBase();

    if (logo) {
      const maxW = 240,
        maxH = 120;
      const scale = Math.min(maxW / logo.width, maxH / logo.height, 1);
      const w = Math.floor(logo.width * scale);
      const h = Math.floor(logo.height * scale);
      ctx.drawImage(logo, 40, 40, w, h);
    }

    return finalize();
  })();
}

if (!window.LabApi) {
  throw new Error("LabApi não encontrado: carregue services.js antes de app.js");
}
/** @type {typeof window.LabApi} */
const LabApi = window.LabApi;

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function sanitizeYouTubeId(id) {
  const s = String(id ?? "").trim();
  return /^[a-zA-Z0-9_-]{11}$/.test(s) ? s : "";
}

function extractYouTubeId(videoUrl, hintedId) {
  const h = sanitizeYouTubeId(hintedId);
  if (h) return h;
  const u = String(videoUrl || "");
  const m = u.match(/(?:[?&]v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  return m ? sanitizeYouTubeId(m[1]) : "";
}

function formatViewCountPt(raw) {
  const n = parseInt(String(raw).replace(/\D/g, ""), 10);
  if (!Number.isFinite(n) || n < 0) return raw ? String(raw) : "";
  if (n >= 1_000_000) {
    const x = n / 1_000_000;
    const s = x >= 10 ? String(Math.round(x)) : String(x.toFixed(1)).replace(/\.0$/, "");
    return `${s} mi de visualizações`;
  }
  if (n >= 1_000) {
    const x = n / 1_000;
    const s = x >= 10 ? String(Math.round(x)) : String(x.toFixed(1)).replace(/\.0$/, "");
    return `${s} mil visualizações`;
  }
  return `${n} visualizações`;
}

/** Resumo em uma linha + texto completo (com quebras) para expandir. */
function summarizeDescriptionForCard(text, maxLen = 160) {
  const full = String(text || "").replace(/\r\n/g, "\n").trim();
  const singleLine = full.replace(/\s+/g, " ").trim();
  if (!singleLine) return { preview: "", full: "", needsToggle: false };
  if (singleLine.length <= maxLen && !full.includes("\n"))
    return { preview: singleLine, full, needsToggle: false };
  if (singleLine.length <= maxLen && full.includes("\n"))
    return { preview: singleLine, full, needsToggle: true };
  let cut = singleLine.slice(0, maxLen);
  const sp = cut.lastIndexOf(" ");
  if (sp > Math.floor(maxLen * 0.45)) cut = cut.slice(0, sp);
  return { preview: `${cut}…`, full, needsToggle: true };
}

function wireResearchUseRoteiro(btn, payload) {
  btn.onclick = () => {
    const tema = (payload.tema || $("research_kw").value || "astronomia").trim();
    const angulo = (payload.angulo || "").trim();
    $("tema").value = tema;
    if (angulo) $("angulo").value = angulo;
    youtubeContext = payload.youtube_context || null;
    setActiveTab("roteiro");
  };
}

function wireTrendTemaOnly(btn, tema) {
  btn.onclick = () => {
    $("tema").value = (tema || $("research_kw").value || "astronomia").trim();
    $("angulo").value = "";
    youtubeContext = null;
    setActiveTab("roteiro");
  };
}

/** Linhas visíveis no preview da tabela e no gráfico de barras (evita sobreposição no eixo Y). */
const TRENDS_TABLE_PREVIEW = 10;

/** Garante array de { query, value } (API / cache podem variar chaves ou formato). */
function normalizeTrendRows(raw) {
  if (raw == null) return [];
  const arr = Array.isArray(raw) ? raw : typeof raw === "object" ? Object.values(raw) : [];
  const out = [];
  for (const r of arr) {
    if (!r || typeof r !== "object") continue;
    const q = r.query ?? r.Query ?? r.term ?? "";
    const v = r.value ?? r.Value;
    const qs = String(q).trim();
    if (!qs) continue;
    out.push({ query: qs, value: v });
  }
  return out;
}

function destroyResearchTrendCharts(root) {
  const ChartLib = typeof window !== "undefined" ? window.Chart : undefined;
  if (!ChartLib) return;
  root.querySelectorAll("canvas").forEach((canvas) => {
    const ch = ChartLib.getChart(canvas);
    if (ch) ch.destroy();
  });
}

function parseTrendNumericForChart(val) {
  if (val === null || val === undefined) return null;
  const s = String(val).trim();
  const low = s.toLowerCase();
  if (low.includes("breakout") || low.includes("alta repentina")) return -1;
  const cleaned = s.replace(/[^\d.,+-]/g, "").replace(",", ".");
  const n = Number.parseFloat(cleaned);
  if (Number.isFinite(n) && n > 0) return n;
  if (Number.isFinite(n) && n === 0) return 0.01;
  return null;
}

function buildRelatedChartSeries(rows) {
  const labels = [];
  const values = [];
  const raw = (rows || []).filter((r) => r && String(r.query || "").trim());
  for (const r of raw) {
    let q = String(r.query).trim();
    if (q.length > 52) q = `${q.slice(0, 51)}…`;
    labels.push(q);
    const pv = parseTrendNumericForChart(r.value);
    if (pv === -1) values.push(-1);
    else if (pv !== null) values.push(pv);
    else values.push(1);
  }
  let maxV = Math.max(...values.filter((v) => v > 0), 1);
  const hasBreak = values.some((v) => v === -1);
  if (hasBreak) {
    maxV = Math.max(maxV * 1.2, 100);
    for (let i = 0; i < values.length; i++) if (values[i] === -1) values[i] = maxV;
  }
  return { labels, values };
}

function mountRelatedBarChartH(canvas, labels, values) {
  const ChartLib = typeof window !== "undefined" ? window.Chart : undefined;
  if (!ChartLib || !labels.length) return;
  const grid = "rgba(36,48,76,0.75)";
  const tick = "#a9b4d6";
  const tc = "#eaf0ff";
  new ChartLib(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Peso relativo (normalizado)",
          data: values,
          backgroundColor: labels.map((_, i) => `hsla(${218 + (i % 8) * 14}, 72%, 58%, 0.72)`),
          borderWidth: 0,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { left: 2, right: 10, top: 6, bottom: 4 } },
      datasets: {
        bar: {
          categoryPercentage: 0.92,
          barPercentage: 0.88,
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: { titleColor: tc, bodyColor: tick },
      },
      scales: {
        x: {
          ticks: { color: tick, maxRotation: 45, minRotation: 45, font: { size: 10 } },
          grid: { color: grid },
          title: { display: true, text: "Comparação relativa", color: tick, font: { size: 11 } },
        },
        y: {
          ticks: {
            color: tick,
            font: { size: 11 },
            autoSkip: false,
            padding: 8,
            maxRotation: 0,
          },
          grid: { color: grid },
        },
      },
    },
  });
}

function formatIotAxisLabel(raw) {
  const s = String(raw ?? "");
  if (s.length >= 10 && /^\d{4}-\d{2}-\d{2}/.test(s)) return `${s.slice(8, 10)}/${s.slice(5, 7)}`;
  if (s.length >= 16) return `${s.slice(8, 10)}/${s.slice(5, 7)} ${s.slice(11, 16)}`;
  return s.slice(0, 14);
}

function mountInterestHistogram(canvas, iot) {
  const ChartLib = typeof window !== "undefined" ? window.Chart : undefined;
  if (!ChartLib || !Array.isArray(iot) || !iot.length) return;
  const sample = iot[0];
  if (!sample || typeof sample !== "object") return;
  let dateKey = "date";
  if (!(dateKey in sample)) dateKey = "index" in sample ? "index" : Object.keys(sample)[0];
  const cols = Object.keys(sample).filter((k) => k !== "isPartial" && k !== dateKey);
  if (!cols.length) return;
  const seriesKey = cols[0];
  const rows = iot.slice(-48);
  const labels = rows.map((r) => formatIotAxisLabel(r[dateKey]));
  const values = rows.map((r) => {
    const v = r[seriesKey];
    const n = typeof v === "number" ? v : Number.parseFloat(String(v).replace(",", "."));
    return Number.isFinite(n) ? n : 0;
  });
  const grid = "rgba(36,48,76,0.75)";
  const tick = "#a9b4d6";
  new ChartLib(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: seriesKey,
          data: values,
          backgroundColor: "rgba(124, 92, 255, 0.55)",
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: tick } },
        tooltip: { titleColor: "#eaf0ff", bodyColor: tick },
      },
      scales: {
        x: {
          ticks: { color: tick, maxRotation: 45, minRotation: 45, font: { size: 9 } },
          grid: { color: grid },
        },
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { color: tick },
          grid: { color: grid },
          title: { display: true, text: "Interesse (0–100)", color: tick, font: { size: 11 } },
        },
      },
    },
  });
}

function appendTrendTableBlock(container, title, rows, suffix, { showChart }) {
  const list = (rows || []).filter((r) => r && String(r.query || "").trim());
  if (!list.length) return;

  const sec = document.createElement("section");
  sec.className = "trends-section";
  const h = document.createElement("h3");
  h.className = "trends-section-title";
  h.textContent = title;
  sec.appendChild(h);

  if (showChart && typeof window !== "undefined" && window.Chart) {
    const chartSlice = list.slice(0, TRENDS_TABLE_PREVIEW);
    const { labels, values } = buildRelatedChartSeries(chartSlice);
    if (labels.length) {
      const cw = document.createElement("div");
      cw.className = "trends-chart-wrap trends-chart-wrap--related";
      const canvas = document.createElement("canvas");
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", title);
      cw.appendChild(canvas);
      sec.appendChild(cw);
      requestAnimationFrame(() => mountRelatedBarChartH(canvas, labels, values));
    }
  }

  const table = document.createElement("table");
  table.className = "trends-data-table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>#</th><th>Termo</th><th>Métrica</th><th></th></tr>";
  table.appendChild(thead);
  const tbVis = document.createElement("tbody");
  const tbMore = document.createElement("tbody");
  tbMore.className = "trends-tbody-more";
  tbMore.hidden = true;

  list.forEach((row, i) => {
    const tr = document.createElement("tr");
    const q = String(row.query).trim();
    const metric =
      row.value === undefined || row.value === null || String(row.value).trim() === "" ? "—" : String(row.value);
    tr.innerHTML = `<td>${i + 1}</td><td class="trends-td-q">${escapeHtml(q)}</td><td class="trends-td-m">${escapeHtml(metric)}</td><td></td>`;
    const tdAct = tr.querySelector("td:last-child");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-ghost trends-use-btn-sm";
    btn.textContent = "Roteiro";
    wireTrendTemaOnly(btn, q);
    tdAct.appendChild(btn);
    if (i < TRENDS_TABLE_PREVIEW) tbVis.appendChild(tr);
    else tbMore.appendChild(tr);
  });
  table.appendChild(tbVis);
  table.appendChild(tbMore);
  sec.appendChild(table);

  if (list.length > TRENDS_TABLE_PREVIEW) {
    const rowBtn = document.createElement("div");
    rowBtn.className = "trends-ver-tudo-row";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-ghost trends-ver-tudo";
    btn.textContent = "Ver tudo";
    let open = false;
    btn.onclick = () => {
      open = !open;
      tbMore.hidden = !open;
      btn.textContent = open ? "Ver menos" : "Ver tudo";
    };
    rowBtn.appendChild(btn);
    sec.appendChild(rowBtn);
  }

  container.appendChild(sec);
}

function parseInterestTableMeta(iot) {
  if (!Array.isArray(iot) || !iot.length) return null;
  const sample = iot[0];
  if (!sample || typeof sample !== "object") return null;
  let dateKey = "date";
  if (!(dateKey in sample)) dateKey = "index" in sample ? "index" : Object.keys(sample)[0];
  const cols = Object.keys(sample).filter((k) => k !== "isPartial" && k !== dateKey);
  if (!cols.length) return null;
  return { dateKey, cols, rows: iot };
}

function appendInterestHistogramBlock(container, iot) {
  const meta = parseInterestTableMeta(iot);
  if (!meta) return;
  const { dateKey, cols, rows } = meta;

  const sec = document.createElement("section");
  sec.className = "trends-section";
  const h = document.createElement("h3");
  h.className = "trends-section-title";
  h.textContent = "Interesse ao longo do tempo (Google Trends)";
  sec.appendChild(h);

  if (typeof window !== "undefined" && window.Chart) {
    const cw = document.createElement("div");
    cw.className = "trends-chart-wrap";
    const canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "Histograma de interesse ao longo do tempo");
    cw.appendChild(canvas);
    sec.appendChild(cw);
    requestAnimationFrame(() => mountInterestHistogram(canvas, rows));
  }

  const wrap = document.createElement("div");
  wrap.className = "trends-iot-wrap";
  const table = document.createElement("table");
  table.className = "trends-iot-table";
  const thead = document.createElement("thead");
  const trh = document.createElement("tr");
  trh.innerHTML = `<th>${escapeHtml(dateKey)}</th>` + cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
  thead.appendChild(trh);
  table.appendChild(thead);
  const tbVis = document.createElement("tbody");
  const tbMore = document.createElement("tbody");
  tbMore.className = "trends-tbody-more";
  tbMore.hidden = true;

  rows.forEach((row, i) => {
    const tr = document.createElement("tr");
    const cells = [row[dateKey], ...cols.map((c) => row[c])];
    tr.innerHTML = cells.map((v) => `<td>${escapeHtml(String(v ?? ""))}</td>`).join("");
    if (i < TRENDS_TABLE_PREVIEW) tbVis.appendChild(tr);
    else tbMore.appendChild(tr);
  });
  table.appendChild(tbVis);
  table.appendChild(tbMore);
  wrap.appendChild(table);
  sec.appendChild(wrap);

  if (rows.length > TRENDS_TABLE_PREVIEW) {
    const rowBtn = document.createElement("div");
    rowBtn.className = "trends-ver-tudo-row";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-ghost trends-ver-tudo";
    btn.textContent = "Ver tudo";
    let open = false;
    btn.onclick = () => {
      open = !open;
      tbMore.hidden = !open;
      btn.textContent = open ? "Ver menos" : "Ver tudo";
    };
    rowBtn.appendChild(btn);
    sec.appendChild(rowBtn);
  }

  container.appendChild(sec);
}

function renderTrendsPanel(panel) {
  const el = researchTrendsHost();
  if (!el) return;
  destroyResearchTrendCharts(el);
  el.innerHTML = "";
  const inner = document.createElement("div");
  inner.className = "trends-panel-inner";

  if (panel && panel.error) {
    const a = document.createElement("div");
    a.className = "trends-alert";
    a.textContent = `Trends: ${String(panel.error)}${panel.error_detail ? " — " + String(panel.error_detail) : ""}`;
    inner.appendChild(a);
  }

  appendTrendTableBlock(inner, "Pesquisas relacionadas — Em alta", normalizeTrendRows(panel?.related_rising), "rising", {
    showChart: true,
  });
  appendTrendTableBlock(inner, "Pesquisas relacionadas — Top", normalizeTrendRows(panel?.related_top), "top", { showChart: true });

  const ts = (panel?.trending_searches || []).filter(Boolean);
  appendTrendTableBlock(
    inner,
    "Buscas em alta (feed regional Google)",
    ts.map((t) => ({ query: String(t), value: "" })),
    "trending",
    { showChart: false },
  );

  appendInterestHistogramBlock(inner, panel?.interest_over_time);

  if (!inner.querySelector(".trends-section")) {
    const empty = document.createElement("div");
    empty.className = "trends-empty";
    empty.textContent =
      "Nenhuma série ou pesquisa relacionada retornada para esta keyword, região e período. Os dados do Google Trends são exploratórios (pytrends), não garantia editorial — tente outro termo ou verifique se o pytrends está instalado e acessível.";
    inner.appendChild(empty);
  }

  el.appendChild(inner);
}

function buildYoutubeResearchCard(it) {
  const div = document.createElement("div");
  div.className = "yt-feed-card";
  const payload = it.payload || {};
  const yc = payload.youtube_context || {};
  const videoUrl = String(it.video_url || yc.video_url || "").trim();
  const videoId = extractYouTubeId(videoUrl, it.video_id || yc.video_id);
  const safeId = sanitizeYouTubeId(videoId);
  const rawDesc = String(it.description ?? yc.description ?? "").trim();
  const viewsStr = formatViewCountPt(it.views || yc.views || "");
  const rank = it.rank ? `<span class="badge">rank ${escapeHtml(it.rank)}</span>` : "";
  const thumbSrc = safeId ? `https://i.ytimg.com/vi/${safeId}/hqdefault.jpg` : "";

  div.innerHTML = `
    <div class="yt-feed-head">
      <div class="yt-feed-head-left">
        <span class="yt-feed-badge">${escapeHtml(it.kind || "")} · ${escapeHtml(it.source || "")}</span>
        ${rank}
      </div>
      <button class="icon-btn" type="button" data-help-anchor="research" title="Ajuda">?</button>
    </div>
    <div class="yt-feed-body">
      <div class="yt-thumb-col">
        <div class="yt-thumb-wrap">
          ${thumbSrc ? `<img class="yt-thumb-img" alt="" loading="lazy" src="${escapeHtml(thumbSrc)}" />` : `<div class="yt-thumb-fallback"></div>`}
          <button type="button" class="yt-play-btn" ${safeId ? "" : "disabled"} aria-label="Reproduzir no card">
            <span class="yt-play-icon" aria-hidden="true"></span>
          </button>
          <div class="yt-embed-frame" hidden></div>
        </div>
        <button type="button" class="btn btn-ghost yt-close-player" hidden>Fechar player</button>
      </div>
      <div class="yt-feed-meta">
        <a class="yt-feed-title" href="${escapeHtml(videoUrl)}" target="_blank" rel="noreferrer">${escapeHtml(it.title || "")}</a>
        <div class="yt-feed-sub">${escapeHtml(it.subtitle || "")}${viewsStr ? ` · ${escapeHtml(viewsStr)}` : ""}</div>
        <div class="yt-desc-box">
          <div class="yt-desc-label">Descrição</div>
          <p class="yt-desc-preview"></p>
          <div class="yt-desc-full" hidden></div>
          <button type="button" class="yt-desc-toggle btn btn-ghost" hidden>Ver mais</button>
        </div>
        <div class="yt-feed-actions">
          <button type="button" class="btn btn-ghost yt-use-roteiro">Usar no roteirizador</button>
        </div>
      </div>
    </div>
  `;

  const thumbWrap = div.querySelector(".yt-thumb-wrap");
  const img = div.querySelector(".yt-thumb-img");
  const playBtn = div.querySelector(".yt-play-btn");
  const embedSlot = div.querySelector(".yt-embed-frame");
  const closePlayer = div.querySelector(".yt-close-player");
  const toggleDesc = div.querySelector(".yt-desc-toggle");
  const prevEl = div.querySelector(".yt-desc-preview");
  const fullEl = div.querySelector(".yt-desc-full");

  const { preview, full, needsToggle } = summarizeDescriptionForCard(rawDesc);
  if (prevEl && fullEl) {
    if (!rawDesc) {
      prevEl.textContent = "Sem descrição retornada pelo YouTube para este vídeo.";
      fullEl.textContent = "";
      fullEl.hidden = true;
      if (toggleDesc) toggleDesc.hidden = true;
    } else {
      prevEl.textContent = preview;
      fullEl.textContent = full;
      fullEl.hidden = true;
      if (toggleDesc) {
        if (needsToggle) {
          toggleDesc.hidden = false;
          toggleDesc.textContent = "Ver mais";
          let expanded = false;
          toggleDesc.onclick = () => {
            expanded = !expanded;
            prevEl.hidden = expanded;
            fullEl.hidden = !expanded;
            toggleDesc.textContent = expanded ? "Ver menos" : "Ver mais";
          };
        } else {
          toggleDesc.hidden = true;
        }
      }
    }
  }

  if (safeId && playBtn) {
    playBtn.onclick = () => {
      embedSlot.innerHTML = `<iframe class="yt-iframe" src="https://www.youtube.com/embed/${escapeHtml(safeId)}?autoplay=1&rel=0" title="YouTube video player" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>`;
      embedSlot.hidden = false;
      if (img) img.hidden = true;
      const fb = div.querySelector(".yt-thumb-fallback");
      if (fb) fb.hidden = true;
      playBtn.hidden = true;
      closePlayer.hidden = false;
      thumbWrap.classList.add("is-playing");
    };
  }

  if (closePlayer) {
    closePlayer.onclick = () => {
      embedSlot.innerHTML = "";
      embedSlot.hidden = true;
      if (img) img.hidden = false;
      const fb = div.querySelector(".yt-thumb-fallback");
      if (fb) fb.hidden = false;
      playBtn.hidden = false;
      closePlayer.hidden = true;
      thumbWrap.classList.remove("is-playing");
    };
  }

  wireResearchUseRoteiro(div.querySelector(".yt-use-roteiro"), payload);
  return div;
}

let lastGenerate = null;
let lastImageSearch = null;
let assetsSelectedSceneIdx = null;
let youtubeContext = null;
/** Token de sessão partilhado no BFF (TTS + visual + composer). */
let composerJobToken = "";
/** Secção «Áudio» só após TTS bem-sucedido (passo 1). */
let composerHasNarration = false;
/** Passo 2: clipes gerados no job. */
let composerHasClips = false;
/** Secção «Vídeo final» só após composer (passo 3). */
let composerHasFinalVideo = false;
/** Passo 4 ASR concluído nesta sessão (permite sincronismo avançado). */
let composerHasAsrOk = false;
/** Passo 5: existe final_synced.mp4 para preview. */
let composerHasSyncedVideo = false;
/** Pré-escuta da voz (sem controlos na UI). */
let composerVoicePreviewAudio = null;
/** Debounce ao mexer na velocidade (evita múltiplos play durante o digitar). */
let composerSpeedPreviewTimer = null;
/** Último pacote Research (para metadata_agent). */
let lastResearchPack = null;

function openHelp(anchor) {
  const dlg = $("help_dialog");
  const frame = $("help_frame");
  const raw = String(anchor || "").trim().replace(/^#/, "");
  const safe = raw.replace(/[^a-zA-Z0-9_-]/g, "");
  const hash = safe ? `#${safe}` : "";
  frame.src = `help.html${hash}`;
  if (typeof dlg.showModal === "function") dlg.showModal();
  else window.open(frame.src, "_blank", "noopener,noreferrer");
}

function renderAngles(angles) {
  const el = $("angles");
  el.classList.remove("is-hidden");
  el.innerHTML = "";
  angles.forEach((a) => {
    const div = document.createElement("div");
    div.className = "angle";
    div.innerHTML = `
      <div class="angle-row">
        <div class="angle-text"></div>
        <button class="icon-btn" type="button" data-help-anchor="roteiro" title="Ajuda">?</button>
      </div>
    `;
    div.querySelector(".angle-text").textContent = a;
    div.querySelector(".angle-text").onclick = () => {
      $("angulo").value = a;
      // Ao selecionar uma sugestão, esconda as demais.
      el.classList.add("is-hidden");
      el.innerHTML = "";
    };
    el.appendChild(div);
  });
}

function fmtTimecodeFromSeconds(s) {
  const n = Math.max(0, Number(s) || 0);
  const m = Math.floor(n / 60);
  const sec = Math.floor(n % 60);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

function buildTimingMap(timing) {
  const map = {};
  (timing ?? []).forEach((t) => {
    if (!t?.id) return;
    if (t.id === "_total") return;
    if (typeof t.start_s !== "number" || typeof t.end_s !== "number") return;
    map[t.id] = { start_s: t.start_s, end_s: t.end_s };
  });
  return map;
}

function renderTextos(textos, timing) {
  const el = $("textos");
  el.innerHTML = "";
  const tmap = buildTimingMap(timing);
  (textos ?? []).forEach((p) => {
    if (!p?.id || !p?.text) return;
    const t = tmap[p.id];
    const tc = t ? `[${fmtTimecodeFromSeconds(t.start_s)}–${fmtTimecodeFromSeconds(t.end_s)}]` : "";
    const div = document.createElement("div");
    div.className = "block";
    div.innerHTML = `
      <div class="suggestion-head">
        <div>
          <div class="k">[${escapeHtml(p.id)}]</div>
          ${tc ? `<div class="part-meta">${escapeHtml(tc)}</div>` : ""}
        </div>
        <div class="head-actions">
          <button class="icon-btn" type="button" data-edit-part="${escapeHtml(p.id)}" title="Editar">✎</button>
          <button class="icon-btn" type="button" data-help-anchor="roteiro" title="Ajuda">?</button>
        </div>
      </div>
      <div class="block-text" data-part-text="${escapeHtml(p.id)}">${escapeHtml(p.text)}</div>
    `;
    const editBtn = div.querySelector("[data-edit-part]");
    if (editBtn) {
      editBtn.onclick = () => {
        const pid = p.id;
        const host = div.querySelector(`[data-part-text=\"${CSS.escape(String(pid))}\"]`);
        if (!host) return;
        const current = String(p.text || "");
        host.outerHTML = `
          <div class="block-edit" data-part-edit="${escapeHtml(pid)}">
            <textarea class="textarea block-edit-textarea">${escapeHtml(current)}</textarea>
            <div class="edit-actions">
              <button class="btn btn-ghost" type="button" data-cancel-part="${escapeHtml(pid)}">Cancelar</button>
              <button class="btn" type="button" data-save-part="${escapeHtml(pid)}">Salvar</button>
            </div>
          </div>
        `;
        const save = div.querySelector(`[data-save-part=\"${CSS.escape(String(pid))}\"]`);
        const cancel = div.querySelector(`[data-cancel-part=\"${CSS.escape(String(pid))}\"]`);
        const area = div.querySelector(`[data-part-edit=\"${CSS.escape(String(pid))}\"] textarea`);
        if (cancel) {
          cancel.onclick = () => {
            // Re-render completo para voltar ao estado anterior
            renderTextos(lastGenerate?.textos || [], lastGenerate?.timing || []);
          };
        }
        if (save) {
          save.onclick = () => {
            const next = area ? String(area.value || "") : current;
            if (!lastGenerate || !Array.isArray(lastGenerate.textos)) return;
            const idx = lastGenerate.textos.findIndex((x) => x && x.id === pid);
            if (idx >= 0) lastGenerate.textos[idx].text = next;
            // mantém o estado atualizado e re-renderiza
            renderTextos(lastGenerate.textos || [], lastGenerate.timing || []);
          };
        }
      };
    }
    el.appendChild(div);
  });
}

function renderScenes(scenes) {
  const el = $("scenes");
  el.innerHTML = "";
  (scenes ?? []).forEach((s) => {
    const div = document.createElement("div");
    div.className = "block";
    div.innerHTML = `
      <div class="scene-head">
        <div class="scene-meta">[${escapeHtml(s.start)}–${escapeHtml(s.end)}] part=${escapeHtml(s.part_id)}</div>
        <div class="head-actions">
          <button class="icon-btn" type="button" data-edit-scene="${escapeHtml(String(s.scene_idx ?? ""))}" title="Editar">✎</button>
          <button class="icon-btn" type="button" data-help-anchor="scenes" title="Ajuda">?</button>
        </div>
      </div>
      <div class="block-text" data-scene-text="${escapeHtml(String(s.scene_idx ?? ""))}">${escapeHtml(s.prompt)}</div>
      <div class="row">
        <button class="btn btn-ghost" type="button" data-use-scene="1">Usar no Image Research</button>
      </div>
    `;
    div.querySelector("[data-use-scene]").onclick = () => {
      $("scene").value = s.prompt || "";
      setActiveTab("assets");
    };

    const editBtn = div.querySelector("[data-edit-scene]");
    if (editBtn) {
      editBtn.onclick = () => {
        const idx = Number(String(s.scene_idx ?? "").trim());
        if (!Number.isFinite(idx)) return;
        const host = div.querySelector(`[data-scene-text=\"${CSS.escape(String(idx))}\"]`);
        if (!host) return;
        const current = String(s.prompt || "");
        host.outerHTML = `
          <div class="block-edit" data-scene-edit="${escapeHtml(String(idx))}">
            <textarea class="textarea block-edit-textarea">${escapeHtml(current)}</textarea>
            <div class="edit-actions">
              <button class="btn btn-ghost" type="button" data-cancel-scene="${escapeHtml(String(idx))}">Cancelar</button>
              <button class="btn" type="button" data-save-scene="${escapeHtml(String(idx))}">Salvar</button>
            </div>
          </div>
        `;
        const save = div.querySelector(`[data-save-scene=\"${CSS.escape(String(idx))}\"]`);
        const cancel = div.querySelector(`[data-cancel-scene=\"${CSS.escape(String(idx))}\"]`);
        const area = div.querySelector(`[data-scene-edit=\"${CSS.escape(String(idx))}\"] textarea`);

        if (cancel) {
          cancel.onclick = () => renderScenes(lastGenerate?.scenes || []);
        }
        if (save) {
          save.onclick = () => {
            const next = area ? String(area.value || "") : current;
            if (!lastGenerate || !Array.isArray(lastGenerate.scenes)) return;
            const sIdx = lastGenerate.scenes.findIndex((x) => Number(x?.scene_idx) === idx);
            if (sIdx >= 0) lastGenerate.scenes[sIdx].prompt = next;
            renderScenes(lastGenerate.scenes || []);
          };
        }
      };
    }

    el.appendChild(div);
  });
}

function renderSelected(selected, reason) {
  const el = $("selected");
  el.innerHTML = "";
  if (!selected) {
    el.innerHTML = `
      <div class="block">
        <div class="suggestion-head">
          <div class="v">Nenhum asset selecionado.</div>
          <button class="icon-btn" type="button" data-help-anchor="assets" title="Ajuda">?</button>
        </div>
        <div class="v muted" style="margin-top:8px">Rode uma busca para ver o candidato escolhido pelo ranker.</div>
      </div>
    `;
    return;
  }
  const url = selected.url || "";
  const div = document.createElement("div");
  div.className = "block asset";
  const userPick = selected && selected.__selected_by_user === true;
  div.innerHTML = `
    <div class="suggestion-head">
      <div class="k">[${escapeHtml(selected.source)}] ${escapeHtml(selected.asset_type)} <span class="badge">${escapeHtml(selected.license || "")}</span></div>
      <button class="icon-btn" type="button" data-help-anchor="assets" title="Ajuda">?</button>
    </div>
    <div class="v muted" style="margin-top:6px">${userPick ? "Selecionado manualmente pelo usuário." : "Melhor candidato segundo o ranker configurado no servidor."}</div>
    <div class="v"><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a></div>
    ${reason ? `<div class="v"><span class="badge">ranker reason</span> ${escapeHtml(reason)}</div>` : ""}
  `;
  el.appendChild(div);
}

function persistImageSelection(scenePrompt, assets, selectedIdx, selectedAsset) {
  if (!lastGenerate) lastGenerate = {};
  if (!lastGenerate.image_research) lastGenerate.image_research = {};
  const key = String(scenePrompt || "").trim();
  if (!key) return;
  lastGenerate.image_research[key] = {
    selected_idx: selectedIdx,
    selected_asset: selectedAsset,
    assets,
    updated_at: new Date().toISOString(),
  };
}

function persistImageSelectionByIdx(sceneIdx, payload) {
  if (!lastGenerate) lastGenerate = {};
  if (!lastGenerate.image_research_by_scene_idx) lastGenerate.image_research_by_scene_idx = {};
  const k = String(sceneIdx);
  if (!k) return;
  lastGenerate.image_research_by_scene_idx[k] = {
    ...payload,
    updated_at: new Date().toISOString(),
  };
}

function getFirstSelectedImageUrl() {
  if (!lastGenerate?.image_research_by_scene_idx) return "";
  const store = lastGenerate.image_research_by_scene_idx;
  const keys = Object.keys(store)
    .map((k) => Number(k))
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => a - b);
  for (const k of keys) {
    const a = store[String(k)]?.selected_asset;
    // Preferir URL direta (preview_url) — page URL (ex. pexels.com/photo/...) pode dar 403.
    const u = a?.preview_url || a?.url;
    if (u) return String(u).trim();
  }
  return "";
}

function buildNarrationScript() {
  if (!lastGenerate) return "";
  const textos = lastGenerate.textos;
  if (Array.isArray(textos) && textos.length) {
    return textos
      .map((p) => String(p && p.text ? p.text : "").trim())
      .filter(Boolean)
      .join("\n\n")
      .trim();
  }
  const rb = lastGenerate.roteiro_base;
  if (rb && String(rb).trim()) return String(rb).trim();
  const el = $("roteiro_base");
  if (el && el.textContent) return String(el.textContent).trim();
  return "";
}

/**
 * Remove marcadores típicos de cópia a partir da UI do laboratório (IDs de parte, timecodes, ícones)
 * ou texto colado que as inclua — útil para TTS / exportação.
 */
function stripRoteiroUiMarkers(raw) {
  const lines = String(raw || "").split(/\r?\n/);
  const cleaned = [];
  for (const line of lines) {
    const t = line.trim();
    if (!t) {
      cleaned.push("");
      continue;
    }
    if (/^\[[\w.-]+\]$/.test(t)) continue;
    if (/^\[\d{1,2}:\d{2}[–-]\d{1,2}:\d{2}\]/.test(t)) continue;
    if (t === "✎" || t === "?") continue;
    cleaned.push(line);
  }
  return cleaned.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function narrationScriptForExport() {
  return stripRoteiroUiMarkers(buildNarrationScript());
}

async function copyTextToClipboard(label, text) {
  const s = String(text || "").trim();
  if (!s) {
    alert(`Nada para copiar${label ? ` (${label})` : ""}. Gere ou edite o roteiro primeiro.`);
    return;
  }
  try {
    await navigator.clipboard.writeText(s);
    alert("Copiado para a área de transferência.");
  } catch (e) {
    alert(`Não foi possível copiar: ${e && e.message ? e.message : e}`);
  }
}

function buildVisualBatchAssets() {
  if (!lastGenerate?.image_research_by_scene_idx) return [];
  const store = lastGenerate.image_research_by_scene_idx;
  const keys = Object.keys(store)
    .map((k) => Number(k))
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => a - b);
  const assets = [];
  for (const k of keys) {
    const a = store[String(k)]?.selected_asset;
    const t = String(a?.asset_type || "").toLowerCase();
    const url = String(a?.url || "").trim();
    const prev = String(a?.preview_url || "").trim();
    // Robustez: às vezes `asset_type` pode vir vazio/inconsistente. Se o url é mp4/webm/mov, tratar como vídeo.
    const urlLooksVideo = /\.(mp4|webm|mov|m4v)(\?|#|$)/i.test(url);
    const isVideo = t === "video" || urlLooksVideo;
    // Se for vídeo, mande o URL do mp4 (não o preview/thumbnail).
    // Se for imagem, preferir preview_url (geralmente direto e com menos bloqueios).
    const pick = isVideo ? url : prev || url;
    if (pick) assets.push({ scene_idx: k, image: pick });
  }
  return assets;
}

function composerPrereqSummary() {
  const script = buildNarrationScript();
  const assets = buildVisualBatchAssets();
  const nScenes = Array.isArray(lastGenerate?.scenes) ? lastGenerate.scenes.length : 0;
  const a = `Narração: ${script.length ? `${script.length} caracteres` : "falta (gere o roteiro)"}`;
  const b = `Imagens: ${assets.length} cena(s) com seleção${nScenes ? ` (roteiro: ${nScenes} cena(s))` : ""}`;
  return `${a} · ${b}`;
}

function refreshComposerPrereq() {
  const el = $("composer_prereq");
  if (el) el.textContent = composerPrereqSummary();
}

function updateComposerOutputVisibility() {
  const audioSec = $("composer_audio_section");
  const videoSec = $("composer_video_section");
  const syncedSec = $("composer_synced_section");
  if (audioSec) audioSec.style.display = composerHasNarration ? "" : "none";
  if (videoSec) videoSec.style.display = composerHasFinalVideo ? "" : "none";
  if (syncedSec) syncedSec.style.display = composerHasSyncedVideo ? "" : "none";

  // Mini-workflow: só libera o próximo passo após o anterior.
  const btnTts = $("btn-composer-tts");
  const btnVisual = $("btn-composer-visual");
  const btnFinal = $("btn-composer-final");
  const btnAsr = $("btn-composer-asr");
  const btnSync = $("btn-composer-sync");

  // 1. TTS: sempre disponível (se houver script)
  if (btnTts) btnTts.disabled = false;
  // 2. Visual: exige TTS concluído (narration.wav + job_token)
  if (btnVisual) btnVisual.disabled = !composerJobToken || !composerHasNarration;
  // 3. Final: exige TTS + clipes
  if (btnFinal) btnFinal.disabled = !composerJobToken || !composerHasNarration || !composerHasClips;
  // 4. ASR: por UX, só após vídeo final (mesmo que tecnicamente baste narration.wav)
  if (btnAsr) btnAsr.disabled = !composerJobToken || !composerHasFinalVideo;
  // 5. Sincronismo avançado: após vídeo final + ASR (script_lab + asr_words.json no servidor)
  if (btnSync) btnSync.disabled = !composerJobToken || !composerHasFinalVideo || !composerHasAsrOk;

  // Publicar: thumbnail exige final.mp4 (composer passo 3)
  const btnThumb = $("btn-generate-thumb");
  if (btnThumb) btnThumb.disabled = !composerJobToken || !composerHasFinalVideo;
}

/** Stem do ficheiro .onnx (igual a `Path.stem` no gerador de amostras). */
function piperOnnxStemFromSelect(value) {
  const s = String(value || "").trim();
  if (!s) return "";
  const fn = s.split(/[/\\]/).pop() || s;
  return fn.replace(/\.onnx$/i, "");
}

/** Toca amostra estática em /static/voices_samples/... (sem controlos). */
function playComposerVoiceSample() {
  const prov = String($("tts_provider")?.value || "kokoro").toLowerCase();
  const raw = String($("tts_voice")?.value || "").trim();
  if (!raw) return;
  let rel;
  if (prov === "kokoro") {
    rel = `voices_samples/kokoro/${encodeURIComponent(raw)}.mp3`;
  } else {
    const stem = piperOnnxStemFromSelect(raw);
    if (!stem) return;
    rel = `voices_samples/piper/${encodeURIComponent(stem)}.mp3`;
  }
  const url = `/static/${rel}`;
  try {
    if (composerVoicePreviewAudio) {
      composerVoicePreviewAudio.pause();
      composerVoicePreviewAudio.src = "";
      composerVoicePreviewAudio = null;
    }
    const a = new Audio(url);
    composerVoicePreviewAudio = a;
    const sp = $("tts_speed");
    if (sp && !sp.disabled) {
      const r = parseFloat(sp.value);
      if (Number.isFinite(r)) a.playbackRate = Math.min(2, Math.max(0.5, r));
      else a.playbackRate = 1;
    } else {
      a.playbackRate = 1;
    }
    a.play().catch(() => {});
  } catch (_) {}
}

/** Novo preview ao alterar velocidade (Kokoro; Piper tem o campo desativado). */
function schedulePlayComposerVoiceSampleOnSpeed() {
  const sp = $("tts_speed");
  if (!sp || sp.disabled) return;
  if (composerSpeedPreviewTimer) clearTimeout(composerSpeedPreviewTimer);
  composerSpeedPreviewTimer = setTimeout(() => {
    composerSpeedPreviewTimer = null;
    playComposerVoiceSample();
  }, 280);
}

function fillSelect(sel, items, current) {
  if (!sel) return;
  const cur = current != null ? String(current) : "";
  sel.innerHTML = "";
  (items || []).forEach((it) => {
    const o = document.createElement("option");
    o.value = String(it.value ?? it);
    o.textContent = String(it.label ?? it);
    if (cur && o.value === cur) o.selected = true;
    sel.appendChild(o);
  });
}

async function refreshTtsOptionsUi() {
  const prov = $("tts_provider");
  const lang = $("tts_lang");
  const voice = $("tts_voice");
  const speed = $("tts_speed");
  const langLabel = $("tts_lang_label");
  const langWrap = $("tts_lang_wrap");
  const voiceLabel = $("tts_voice_label");
  try {
    const data = await LabApi.getTtsAgentOptions();
    const selectedProvider = String((prov && prov.value) || data?.selected?.provider || "kokoro").toLowerCase();
    fillSelect(prov, (data.providers || []).map((p) => ({ value: p, label: p })), selectedProvider);

    const k = data.kokoro || {};
    const p = data.piper || {};

    const isKokoro = String((prov && prov.value) || selectedProvider) === "kokoro";
    if (lang) lang.disabled = !isKokoro;
    if (voice) voice.disabled = false; // piper usa o mesmo select como "modelo"
    if (speed) speed.disabled = !isKokoro;
    // Piper: idioma vem do modelo ONNX (PIPER_MODEL); o select de idioma não aplica — ocultamos o bloco.
    if (langWrap) langWrap.style.display = isKokoro ? "" : "none";
    if (langLabel) langLabel.textContent = "Idioma";
    if (voiceLabel) voiceLabel.textContent = isKokoro ? "Voz" : "Modelo (Piper)";

    if (isKokoro) {
      fillSelect(lang, (k.langs || []).map((l) => ({ value: l, label: l })), k?.env?.KOKORO_LANG || "pt-br");
      fillSelect(
        voice,
        (k.voices || []).map((v) => ({ value: v, label: v })),
        k?.env?.KOKORO_VOICE || "pf_dora",
      );
      if (speed && k?.env?.KOKORO_SPEED) speed.value = String(k.env.KOKORO_SPEED);
    } else {
      const models = (p.models || []).map((m) =>
        typeof m === "string" ? { value: m, label: m } : { value: m.value, label: m.label || m.value },
      );
      const envPm = (p.env && p.env.PIPER_MODEL) || "";
      let cur =
        (models.find((m) => m.value === envPm || (envPm && m.value.endsWith(envPm))) || {}).value ||
        (models.find((m) => envPm && m.label && m.label.indexOf(envPm) >= 0) || {}).value ||
        "";
      if (!cur && models.length) cur = models[0].value;
      fillSelect(voice, models, cur);
    }
  } catch (_) {
    const isKokoro = String((prov && prov.value) || "kokoro").toLowerCase() === "kokoro";
    if (langWrap) langWrap.style.display = isKokoro ? "" : "none";
  }
}

function setComposerJobToken(t) {
  const next = (t && String(t).trim()) || "";
  if (!next) {
    composerHasNarration = false;
    composerHasClips = false;
    composerHasFinalVideo = false;
    composerHasAsrOk = false;
    composerHasSyncedVideo = false;
    updateComposerOutputVisibility();
  }
  composerJobToken = next;
  const inp = $("composer_job_token");
  if (inp) inp.value = composerJobToken;
  const pubJt = $("pub_job_token");
  if (pubJt) pubJt.value = composerJobToken;
  const btnFinal = $("btn-composer-final");
  if (btnFinal) btnFinal.disabled = !composerJobToken;
  updateComposerOutputVisibility();
}

function getSceneOptions() {
  const scenes = (lastGenerate && Array.isArray(lastGenerate.scenes) ? lastGenerate.scenes : []) || [];
  const seen = new Set();
  const opts = [];
  for (const s of scenes) {
    const idx = Number(s?.scene_idx);
    if (!Number.isFinite(idx) || seen.has(idx)) continue;
    seen.add(idx);
    const label = `[${s.start || ""}–${s.end || ""}] ${s.part_id || ""}`;
    opts.push({ idx, label, prompt: s.prompt || "" });
  }
  return opts.sort((a, b) => a.idx - b.idx);
}

function refreshScenePicker() {
  const sel = $("scene_picker");
  if (!sel) return;
  const opts = getSceneOptions();
  sel.innerHTML = "";
  opts.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = String(o.idx);
    opt.textContent = `${o.idx + 1}. ${o.label}`;
    sel.appendChild(opt);
  });
  if (assetsSelectedSceneIdx == null && opts.length) assetsSelectedSceneIdx = opts[0].idx;
  if (assetsSelectedSceneIdx != null) sel.value = String(assetsSelectedSceneIdx);
}

function loadManualSceneFromPicker() {
  const sel = $("scene_picker");
  if (!sel) return;
  const idx = Number(sel.value);
  if (!Number.isFinite(idx)) return;
  assetsSelectedSceneIdx = idx;
  const scenes = (lastGenerate && Array.isArray(lastGenerate.scenes) ? lastGenerate.scenes : []) || [];
  const s = scenes.find((x) => Number(x?.scene_idx) === idx);
  if (s) $("scene").value = s.prompt || "";

  const saved = lastGenerate?.image_research_by_scene_idx?.[String(idx)];
  if (saved && saved.selected_asset) {
    renderSelected(saved.selected_asset, saved.reason || "");
    renderAssets(saved.assets || [], saved.selected_idx);
  } else {
    $("selected").innerHTML = "";
    $("assets").innerHTML = "";
  }
}

function renderAutoSelectedList() {
  const host = $("auto_selected_list");
  if (!host) return;
  host.innerHTML = "";
  const opts = getSceneOptions();
  const store = lastGenerate?.image_research_by_scene_idx || {};
  if (!opts.length) {
    host.innerHTML = `<div class="muted">Gere cenas primeiro para usar o modo automático.</div>`;
    return;
  }
  for (const o of opts) {
    const saved = store[String(o.idx)] || null;
    const picked = saved?.selected_asset || null;
    const url = picked?.url || "";
    const row = document.createElement("div");
    row.className = "block asset";
    row.innerHTML = `
      <div class="suggestion-head">
        <div class="k">Cena ${o.idx + 1} · ${escapeHtml(o.label)}</div>
        <button class="btn btn-ghost" type="button" data-edit-auto="${o.idx}">Editar</button>
      </div>
      <div class="v muted" style="margin-top:6px">${picked ? "Selecionado" : "Sem seleção ainda"}</div>
      ${picked ? `<div class="v"><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a></div>` : ""}
    `;
    row.querySelector("[data-edit-auto]").onclick = () => {
      setAssetsMode("manual");
      const sp = $("scene_picker");
      if (sp) sp.value = String(o.idx);
      loadManualSceneFromPicker();
    };
    host.appendChild(row);
  }
}

function renderAssets(assets, selectedIdx) {
  const el = $("assets");
  el.innerHTML = "";
  (assets ?? []).forEach((a, idx) => {
    const url = a.url || "";
    const div = document.createElement("div");
    div.className = "block asset";
    const chosen = selectedIdx === idx ? " <span class='badge'>selecionado</span>" : "";
    div.innerHTML = `
      <div class="suggestion-head">
        <div class="k">#${idx + 1} ${chosen} [${escapeHtml(a.source)}] ${escapeHtml(a.asset_type)} <span class="badge">${escapeHtml(a.license || "")}</span></div>
        <button class="icon-btn" type="button" data-help-anchor="assets" title="Ajuda">?</button>
      </div>
      <div class="v muted" style="margin-top:6px">Candidato retornado pela busca (inspeção/auditoria).</div>
      <div class="v"><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a></div>
      <div class="row" style="justify-content:flex-end">
        <button class="btn btn-ghost" type="button" data-select-asset="${idx}">Selecionar</button>
      </div>
    `;
    const selectBtn = div.querySelector("[data-select-asset]");
    if (selectBtn) {
      selectBtn.onclick = () => {
        const scenePrompt = $("scene")?.value || "";
        const picked = { ...(a || {}), __selected_by_user: true };
        lastImageSearch = {
          ...(lastImageSearch || {}),
          scene: scenePrompt,
          assets: assets || [],
          selected_idx: idx,
          selected_asset: picked,
          reason: "",
        };
        persistImageSelection(scenePrompt, assets || [], idx, picked);
        if (assetsSelectedSceneIdx != null) {
          persistImageSelectionByIdx(assetsSelectedSceneIdx, {
            selected_idx: idx,
            selected_asset: picked,
            assets: assets || [],
            reason: "",
            mode: "manual",
          });
          renderAutoSelectedList();
        }
        renderSelected(picked, "");
        renderAssets(assets || [], idx);
      };
    }
    el.appendChild(div);
  });
}

function renderResearchVideos(items) {
  const el = researchVideosHost();
  if (!el) {
    console.error("[research] Elemento #research_videos (ou #research_out) não encontrado no DOM.");
    return;
  }
  el.innerHTML = "";
  el.classList.add("research-feed");
  (items ?? []).forEach((it) => {
    if (it.kind === "youtube_video") el.appendChild(buildYoutubeResearchCard(it));
  });
}

function renderResearchPack(data) {
  renderResearchVideos(data.video_suggestions || data.suggestions || []);
  renderTrendsPanel(data.trends_panel || {});
  setResearchSubTab("videos");
}

const HEALTH_POLL_MS = 90_000;

function refreshHeaderHealth() {
  const dot = $("health_dot");
  const btn = $("header_health");
  if (!dot || !btn) return;
  LabApi.getHealth()
    .then((h) => {
      const st = h.status === "ok" ? "ok" : "degraded";
      dot.dataset.status = st;
      const errs = Array.isArray(h.errors) ? h.errors.filter(Boolean).join(", ") : "";
      const parts = [`Estado: ${h.status === "ok" ? "ok" : "degradado"}`];
      if (errs) parts.push(`Com problemas: ${errs}`);
      btn.title = parts.join(" · ");
      btn.setAttribute(
        "aria-label",
        h.status === "ok" && !errs ? "Status dos serviços: ok" : `Status dos serviços: degradado. ${errs || ""}`.trim(),
      );
    })
    .catch(() => {
      dot.dataset.status = "error";
      btn.title = "Não foi possível obter /health (rede ou servidor).";
      btn.setAttribute("aria-label", "Status dos serviços: erro ao consultar");
    });
}

function wireDurationTierUi() {
  const sel = $("duration-tier");
  const wrap = $("duration_custom_wrap");
  if (!sel || !wrap) return;
  const toggle = () => {
    wrap.style.display = sel.value === "custom" ? "" : "none";
  };
  sel.addEventListener("change", toggle);
  toggle();
}

function wireDurationPopover() {
  const btn = document.querySelector("[data-duration-info]");
  const pop = $("duration_popover");
  if (!btn || !pop) return;

  const hide = () => pop.setAttribute("aria-hidden", "true");
  const show = () => pop.setAttribute("aria-hidden", "false");
  const isOpen = () => pop.getAttribute("aria-hidden") === "false";

  btn.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    if (isOpen()) {
      hide();
      return;
    }
    const sg = $("styleguide_popover");
    if (sg) sg.setAttribute("aria-hidden", "true");
    const r = btn.getBoundingClientRect();
    // posiciona abaixo do botão, alinhado à direita
    const top = window.scrollY + r.bottom + 8;
    const left = window.scrollX + Math.max(12, r.right - pop.offsetWidth);
    pop.style.top = `${top}px`;
    pop.style.left = `${left}px`;
    show();
  });

  document.addEventListener("click", () => hide());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hide();
  });
}

function wireStyleGuidePopover() {
  const buttons = document.querySelectorAll("[data-styleguide-info]");
  const pop = $("styleguide_popover");
  if (!buttons.length || !pop) return;

  const hide = () => pop.setAttribute("aria-hidden", "true");
  const show = () => pop.setAttribute("aria-hidden", "false");
  const isOpen = () => pop.getAttribute("aria-hidden") === "false";

  pop.addEventListener("click", (e) => e.stopPropagation());

  buttons.forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (isOpen()) {
        hide();
        return;
      }
      const dp = $("duration_popover");
      if (dp) dp.setAttribute("aria-hidden", "true");
      const r = btn.getBoundingClientRect();
      const top = window.scrollY + r.bottom + 8;
      const left = window.scrollX + Math.max(12, r.right - pop.offsetWidth);
      pop.style.top = `${top}px`;
      pop.style.left = `${left}px`;
      show();
    });
  });

  document.addEventListener("click", () => hide());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hide();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  (async () => {
    try {
      const c = await LabApi.getLabUiConfig();
      const def = !!c.visual_use_comfyui_default;
      const cb = $("composer_visual_use_comfy");
      if (cb) cb.checked = def;
      const vb = $("visual_preview_use_comfy");
      if (vb) vb.checked = def;
    } catch (_) {
      /* BFF indisponível: mantém o atributo checked do HTML */
    }
  })();

  refreshHeaderHealth();
  setInterval(refreshHeaderHealth, HEALTH_POLL_MS);

  const healthBtn = $("header_health");
  if (healthBtn) {
    healthBtn.onclick = () => {
      const demo = typeof window !== "undefined" && window.__VIDEO_STUDIO_DEMO__;
      if (demo && demo.offline) {
        const pre = $("demo_health_pre");
        const dlg = $("demo_health_dialog");
        if (pre && dlg && typeof dlg.showModal === "function") {
          LabApi.getHealth()
            .then((h) => {
              pre.textContent = JSON.stringify(h, null, 2);
              dlg.showModal();
            })
            .catch((e) => {
              pre.textContent = String(e && e.message ? e.message : e);
              dlg.showModal();
            });
          return;
        }
      }
      window.open("/health", "_blank", "noopener,noreferrer");
    };
  }

  wireDurationTierUi();
  wireDurationPopover();
  wireStyleGuidePopover();
  wireThumbTemplatePicker();
  document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => setActiveTab(b.dataset.tab)));
  document.querySelectorAll("[data-research-sub]").forEach((b) => {
    b.onclick = () => setResearchSubTab(b.getAttribute("data-research-sub") || "videos");
  });
  // Image Research: modo auto/manual
  setAssetsMode("auto");
  document.querySelectorAll("[data-assets-mode]").forEach((b) => {
    b.onclick = () => setAssetsMode(b.getAttribute("data-assets-mode") || "auto");
  });
  setActiveTab("fluxo");

  $("help_close").onclick = () => {
    const dlg = $("help_dialog");
    if (typeof dlg.close === "function") dlg.close();
  };

  document.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    const btn = t.closest("[data-help-anchor]");
    if (!btn) return;
    const anchor = btn.getAttribute("data-help-anchor") || "";
    openHelp(anchor);
  });

  $("btn-research").onclick = async () => {
    $("btn-research").disabled = true;
    try {
      const keyword = $("research_kw").value.trim();
      if (!keyword) return alert("Informe uma keyword/tema.");
      const region = String($("research_region").value || "BR").trim() || "BR";
      const category_id = String($("research_cat").value || "28").trim() || "28";
      const data = await LabApi.postResearchYoutubeTrends({
        keyword,
        region,
        category_id,
        youtube_n: 10,
        trends_days: 7,
      });
      lastResearchPack = data;
      renderResearchPack(data);
    } catch (e) {
      alert(e.message);
    } finally {
      $("btn-research").disabled = false;
    }
  };

  $("btn-angles").onclick = async () => {
    try {
      const tema = $("tema").value.trim() || "astronomia";
      const useOllama = $("use-ollama").checked;
      const data = await LabApi.getAngles({ tema, useOllama });
      renderAngles(data.angles || []);

      // Ao sugerir novos ângulos, esconda/limpe resultados anteriores (evita “misturar” sugestões antigas).
      $("roteiro_base").textContent = "";
      $("textos").innerHTML = "";
      $("scenes").innerHTML = "";
      lastGenerate = null;
    } catch (e) {
      alert(e.message);
    }
  };

  $("btn-generate").onclick = async () => {
    $("btn-generate").disabled = true;
    try {
      const tema = $("tema").value.trim() || "astronomia";
      const angulo = $("angulo").value.trim() || "";
      const useOllama = $("use-ollama").checked;
      const tierEl = $("duration-tier");
      const duration_tier = (tierEl && tierEl.value) || "medium";
      const body = { tema, angulo, use_ollama: useOllama, duration_tier };
      if (duration_tier === "custom") {
        const raw = $("duration-custom-minutes") && $("duration-custom-minutes").value;
        const min = Number(String(raw).trim());
        if (!Number.isFinite(min) || min < 1 || min > 60) {
          alert("Duração personalizada: informe minutos entre 1 e 60.");
          return;
        }
        body.target_narration_minutes = min;
      }
      if (youtubeContext) body.youtube_context = youtubeContext;
      const data = await LabApi.postRoteirizadorGenerate(body);
      lastGenerate = data;
      $("roteiro_base").textContent = data.roteiro_base || "";
      renderTextos(data.textos || [], data.timing || []);
      renderScenes(data.scenes || []);
      assetsSelectedSceneIdx = null;
      refreshScenePicker();
      loadManualSceneFromPicker();
      renderAutoSelectedList();
      refreshComposerPrereq();
      setActiveTab("scenes");
    } catch (e) {
      alert(e.message);
    } finally {
      $("btn-generate").disabled = false;
    }
  };

  const btnCopyRoteiroClean = $("btn-copy-roteiro-clean");
  if (btnCopyRoteiroClean) {
    btnCopyRoteiroClean.onclick = () => copyTextToClipboard("roteiro", narrationScriptForExport());
  }
  const btnCopyTextosClean = $("btn-copy-textos-clean");
  if (btnCopyTextosClean) {
    btnCopyTextosClean.onclick = () => copyTextToClipboard("textos", narrationScriptForExport());
  }

  $("btn-use-first-scene").onclick = () => {
    if (!lastGenerate?.scenes?.length) return alert("Gere um roteiro primeiro.");
    $("scene").value = lastGenerate.scenes[0].prompt || "";
    setAssetsMode("manual");
    assetsSelectedSceneIdx = Number(lastGenerate.scenes[0].scene_idx || 0);
    refreshScenePicker();
    loadManualSceneFromPicker();
    setActiveTab("assets");
  };

  const scenePicker = $("scene_picker");
  if (scenePicker) scenePicker.onchange = () => loadManualSceneFromPicker();

  $("btn-search").onclick = async () => {
    $("btn-search").disabled = true;
    try {
      const scene = $("scene").value.trim();
      if (!scene) return alert("Cole um prompt de cena.");
      const style = $("style").value.trim();
      const prefer = ($("prefer") && $("prefer").value) || "video_first";
      const per_source = Number($("per_source").value || "5");
      const data = await LabApi.postImageResearchSearch({ scene, style, prefer, per_source });
      lastImageSearch = { ...data, scene, style, prefer, per_source };
      renderSelected(data.selected_asset, data.reason);
      renderAssets(data.assets || [], data.selected_idx);
      if (assetsSelectedSceneIdx != null) {
        persistImageSelectionByIdx(assetsSelectedSceneIdx, {
          selected_idx: data.selected_idx,
          selected_asset: data.selected_asset,
          assets: data.assets || [],
          reason: data.reason || "",
          mode: "manual",
        });
        renderAutoSelectedList();
      }
      refreshComposerPrereq();
    } catch (e) {
      alert(e.message);
    } finally {
      $("btn-search").disabled = false;
    }
  };

  const btnAll = $("btn-search-all");
  if (btnAll) {
    btnAll.onclick = async () => {
      if (!lastGenerate?.scenes?.length) return alert("Gere cenas primeiro.");
      btnAll.disabled = true;
      try {
        const style = $("style_auto")?.value.trim() || "";
        const prefer = ($("prefer_auto") && $("prefer_auto").value) || "video_first";
        const per_source = Number($("per_source_auto")?.value || "5");
        const scenes = getSceneOptions();
        for (const s of scenes) {
          const data = await LabApi.postImageResearchSearch({ scene: s.prompt, style, prefer, per_source });
          persistImageSelectionByIdx(s.idx, {
            selected_idx: data.selected_idx,
            selected_asset: data.selected_asset,
            assets: data.assets || [],
            reason: data.reason || "",
            mode: "auto",
          });
        }
        renderAutoSelectedList();
        refreshComposerPrereq();
      } catch (e) {
        alert(e.message);
      } finally {
        btnAll.disabled = false;
      }
    };
  }

  const goComposer = $("btn-go-composer");
  if (goComposer) goComposer.onclick = () => setActiveTab("composer");

  const btnVisualFill = $("btn-visual-fill");
  const btnVisualPreview = $("btn-visual-preview");
  const visualStatus = $("visual_status");
  const visualVideo = $("visual_video");
  if (btnVisualFill && $("visual_image_url")) {
    btnVisualFill.onclick = () => {
      const u = getFirstSelectedImageUrl();
      if (!u) return alert("Nenhuma imagem selecionada no Image Research. Rode uma busca e escolha um asset.");
      $("visual_image_url").value = u;
      const sid = $("visual_scene_idx");
      if (sid && lastGenerate?.image_research_by_scene_idx) {
        const keys = Object.keys(lastGenerate.image_research_by_scene_idx)
          .map((x) => Number(x))
          .filter((n) => Number.isFinite(n))
          .sort((a, b) => a - b);
        if (keys.length) sid.value = String(keys[0]);
      }
    };
  }
  if (btnVisualPreview && visualStatus && visualVideo) {
    btnVisualPreview.onclick = async () => {
      const image = ($("visual_image_url") && $("visual_image_url").value) || "";
      const trimmed = String(image).trim();
      if (!trimmed) return alert("Informe a URL da imagem.");
      const sceneIdx = Number(($("visual_scene_idx") && $("visual_scene_idx").value) || 0);
      btnVisualPreview.disabled = true;
      visualStatus.textContent = "A processar… (pode demorar se a GPU estiver ocupada)";
      visualVideo.style.display = "none";
      visualVideo.removeAttribute("src");
      try {
        const useComfy = $("visual_preview_use_comfy") ? !!$("visual_preview_use_comfy").checked : true;
        const data = await LabApi.postVisualAgentPreview({
          image: trimmed,
          scene_idx: sceneIdx,
          use_comfy: useComfy,
        });
        if (!data.ok) {
          visualStatus.textContent = `Falha: ${data.error || "desconhecido"} · mode=${data.mode || "?"}`;
          return;
        }
        const rel = (data.result_url || "").trim();
        if (!rel) {
          visualStatus.textContent = "Resposta sem result_url.";
          return;
        }
        const parts = [];
        parts.push(`ok · mode=${data.mode || "?"}`);
        if (Array.isArray(data.warnings) && data.warnings.length) parts.push(data.warnings.join("; "));
        visualStatus.textContent = parts.join(" · ");
        visualVideo.src = `${rel}?t=${Date.now()}`;
        visualVideo.style.display = "block";
        visualVideo.play().catch(() => {});
      } catch (e) {
        alert(e.message);
        visualStatus.textContent = "";
      } finally {
        btnVisualPreview.disabled = false;
      }
    };
  }

  const audio = $("tts_audio");
  const status = $("composer_status");
  const btnComposerNew = $("btn-composer-new-job");
  const btnComposerTts = $("btn-composer-tts");
  const btnComposerVisual = $("btn-composer-visual");
  const btnComposerFinal = $("btn-composer-final");
  const composerVideo = $("composer_video");

  const composerVideoSynced = $("composer_video_synced");

  if (btnComposerNew) {
    btnComposerNew.onclick = () => {
      composerHasNarration = false;
      composerHasClips = false;
      composerHasFinalVideo = false;
      composerHasAsrOk = false;
      composerHasSyncedVideo = false;
      updateComposerOutputVisibility();
      setComposerJobToken("");
      if (status) status.textContent = "Novo job: execute os passos 1 → 2 → 3.";
      if (audio) audio.removeAttribute("src");
      if (composerVideo) {
        composerVideo.style.display = "none";
        composerVideo.removeAttribute("src");
      }
      if (composerVideoSynced) {
        composerVideoSynced.style.display = "none";
        composerVideoSynced.removeAttribute("src");
      }
      refreshComposerPrereq();
    };
  }

  if (btnComposerTts && audio && status) {
    btnComposerTts.onclick = async () => {
      const script = buildNarrationScript();
      if (!script.trim()) return alert("Gere um roteiro com textos antes (aba Roteirizador).");
      btnComposerTts.disabled = true;
      status.textContent = "Gerando TTS (servidor)…";
      try {
        const provider = $("tts_provider")?.value || "";
        const isKokoro = String(provider || "kokoro") === "kokoro";
        const kokoro_lang = isKokoro ? $("tts_lang")?.value || "" : "";
        const kokoro_voice = isKokoro ? $("tts_voice")?.value || "" : "";
        const kokoro_speed = isKokoro ? Number($("tts_speed")?.value || "1.0") : NaN;
        const piper_model =
          !isKokoro && $("tts_voice")?.value ? String($("tts_voice").value).trim() : "";
        const body = {
          script,
          job_token: composerJobToken || undefined,
          provider: provider || undefined,
          kokoro_lang: isKokoro && kokoro_lang ? kokoro_lang : undefined,
          kokoro_voice: isKokoro && kokoro_voice ? kokoro_voice : undefined,
          kokoro_speed: isKokoro && Number.isFinite(kokoro_speed) ? kokoro_speed : undefined,
          piper_model: !isKokoro && piper_model ? piper_model : undefined,
        };
        const data = await LabApi.postTtsAgentPreview(body);
        if (data.job_token) setComposerJobToken(data.job_token);
        if (!data.ok) {
          status.textContent = `TTS falhou: ${data.error || "desconhecido"}`;
          return;
        }
        const nu = (data.narration_url || "").trim();
        if (!nu) {
          status.textContent = "TTS ok mas sem narration_url.";
          return;
        }
        audio.src = `${nu}?t=${Date.now()}`;
        // Força recarregar mesmo quando o URL “parece” o mesmo (range cache / player state).
        audio.load();
        composerHasNarration = true;
        composerHasFinalVideo = false;
        composerHasAsrOk = false;
        composerHasSyncedVideo = false;
        if (composerVideoSynced) {
          composerVideoSynced.style.display = "none";
          composerVideoSynced.removeAttribute("src");
        }
        updateComposerOutputVisibility();
        status.textContent = "TTS gerado. Passe ao passo 2 (clipes) quando as imagens estiverem prontas.";
      } catch (e) {
        alert(e.message);
        status.textContent = "";
      } finally {
        btnComposerTts.disabled = false;
        updateComposerOutputVisibility();
      }
    };
  }

  if (btnComposerVisual && status) {
    btnComposerVisual.onclick = async () => {
      const assets = buildVisualBatchAssets();
      if (!assets.length) return alert("Selecione imagens no Image Research (modo automático ou manual).");
      btnComposerVisual.disabled = true;
      status.textContent = "Gerando clipes (visual_agent)… pode demorar.";
      try {
        const useComfy = $("composer_visual_use_comfy") ? !!$("composer_visual_use_comfy").checked : true;
        const body = { assets, job_token: composerJobToken || undefined, use_comfy: useComfy };
        const data = await LabApi.postVisualAgentBatch(body);
        if (data.job_token) setComposerJobToken(data.job_token);
        if (!data.ok) {
          status.textContent = `Visual falhou: ${data.error || "desconhecido"} · mode=${data.mode || "?"}`;
          return;
        }
        composerHasClips = Array.isArray(data.clips) && data.clips.length > 0;
        composerHasFinalVideo = false;
        composerHasSyncedVideo = false;
        if (composerVideoSynced) {
          composerVideoSynced.style.display = "none";
          composerVideoSynced.removeAttribute("src");
        }
        updateComposerOutputVisibility();
        status.textContent = `Clipes: ${(data.clips || []).length} · mode=${data.mode || "?"} · Use o passo 3 após TTS + clipes.`;
      } catch (e) {
        alert(e.message);
        status.textContent = "";
      } finally {
        btnComposerVisual.disabled = false;
        updateComposerOutputVisibility();
      }
    };
  }

  if (btnComposerFinal && status && composerVideo) {
    btnComposerFinal.onclick = async () => {
      if (!composerJobToken) return alert("Execute primeiro o passo 1 (TTS) para obter um job.");
      btnComposerFinal.disabled = true;
      status.textContent = "Compondo vídeo final (ffmpeg)…";
      composerHasFinalVideo = false;
      composerHasSyncedVideo = false;
      if (composerVideoSynced) {
        composerVideoSynced.style.display = "none";
        composerVideoSynced.removeAttribute("src");
      }
      updateComposerOutputVisibility();
      composerVideo.style.display = "none";
      composerVideo.removeAttribute("src");
      try {
        const data = await LabApi.postComposerAgentPreview({ job_token: composerJobToken });
        if (!data.ok) {
          status.textContent = `Composer falhou: ${data.error || "desconhecido"}`;
          return;
        }
        const vu = (data.video_url || "").trim();
        if (!vu) {
          status.textContent = "Composer ok mas sem video_url.";
          return;
        }
        status.textContent = "Vídeo final pronto.";
        composerHasFinalVideo = true;
        updateComposerOutputVisibility();
        composerVideo.src = `${vu}?t=${Date.now()}`;
        composerVideo.style.display = "block";
        composerVideo.play().catch(() => {});
      } catch (e) {
        alert(e.message);
        status.textContent = "";
      } finally {
        btnComposerFinal.disabled = !composerJobToken;
        updateComposerOutputVisibility();
      }
    };
  }

  const btnComposerAsr = $("btn-composer-asr");
  const asrLinks = $("asr_links");
  if (btnComposerAsr && status) {
    btnComposerAsr.onclick = async () => {
      if (!composerJobToken) return alert("Execute primeiro o passo 1 (TTS) para obter narration.wav.");
      btnComposerAsr.disabled = true;
      status.textContent = "ASR (Whisper) em execução… pode demorar.";
      if (asrLinks) asrLinks.textContent = "";
      try {
        const data = await LabApi.postLabAsr({ job_token: composerJobToken });
        if (!data.ok) {
          status.textContent = `ASR falhou: ${data.detail || "desconhecido"}`;
          return;
        }
        status.textContent = `ASR ok · idioma=${data.language || "?"} · duração≈${(data.duration_s || 0).toFixed(1)}s`;
        composerHasAsrOk = true;
        if (asrLinks) {
          const b = window.location.origin;
          asrLinks.innerHTML = [
            `<a href="${b}${data.vtt_url}" target="_blank" rel="noopener">VTT</a>`,
            `<a href="${b}${data.srt_url}" target="_blank" rel="noopener">SRT</a>`,
            `<a href="${b}${data.json_url}" target="_blank" rel="noopener">JSON</a>`,
          ].join(" · ");
        }
      } catch (e) {
        alert(e.message);
        status.textContent = "";
      } finally {
        btnComposerAsr.disabled = false;
        updateComposerOutputVisibility();
      }
    };
  }

  const btnComposerSync = $("btn-composer-sync");
  if (btnComposerSync && status && composerVideoSynced) {
    btnComposerSync.onclick = async () => {
      if (!composerJobToken) return alert("Sem job.");
      btnComposerSync.disabled = true;
      status.textContent = "Sincronismo avançado (timeline + ffmpeg)… pode demorar vários minutos.";
      composerHasSyncedVideo = false;
      updateComposerOutputVisibility();
      composerVideoSynced.style.display = "none";
      composerVideoSynced.removeAttribute("src");
      try {
        const data = await LabApi.postLabSyncCompose({ job_token: composerJobToken, timeline_mode: "auto" });
        if (!data.ok) {
          status.textContent = `Sincronismo falhou: ${data.detail || "desconhecido"}`;
          return;
        }
        const vu = (data.video_url || "").trim();
        if (!vu) {
          status.textContent = "Ok mas sem video_url.";
          return;
        }
        status.textContent = "Vídeo sincronizado pronto.";
        composerHasSyncedVideo = true;
        updateComposerOutputVisibility();
        composerVideoSynced.src = `${vu}?t=${Date.now()}`;
        composerVideoSynced.style.display = "block";
        composerVideoSynced.play().catch(() => {});
      } catch (e) {
        alert(e.message);
        status.textContent = "";
      } finally {
        btnComposerSync.disabled = false;
        updateComposerOutputVisibility();
      }
    };
  }

  refreshComposerPrereq();
  refreshTtsOptionsUi();
  updateComposerOutputVisibility();

  const ttsProvider = $("tts_provider");
  const ttsVoiceEl = $("tts_voice");
  if (ttsProvider) {
    ttsProvider.onchange = async () => {
      await refreshTtsOptionsUi();
      playComposerVoiceSample();
    };
  }
  if (ttsVoiceEl) {
    ttsVoiceEl.addEventListener("change", () => playComposerVoiceSample());
  }
  const ttsSpeedEl = $("tts_speed");
  if (ttsSpeedEl) {
    ttsSpeedEl.addEventListener("input", schedulePlayComposerVoiceSampleOnSpeed);
    ttsSpeedEl.addEventListener("change", schedulePlayComposerVoiceSampleOnSpeed);
  }

  // Publicar (YouTube real + thumbnail real; publish do vídeo ainda pode ser mock conforme UI)
  const btnSaveMeta = $("btn-pub-save-meta");
  const btnGenThumb = $("btn-generate-thumb");
  const btnPub = $("btn-publish-video");
  const pubStatus = $("publish_status");
  const ytStatus = $("yt_status");
  const btnYtConnect = $("btn-yt-connect");
  const btnYtRefresh = $("btn-yt-refresh");
  const pubChannel = $("pub_channel");
  const logoInput = $("thumb_logo_file");
  const uploadInput = $("thumb_upload_file");
  const btnGrowthMeta = $("btn-pub-growth-meta");

  const pubTitleVariantsSel = $("pub_title_variants");
  const pubTitleInput = $("pub_title");
  const thumbConceptSel = $("thumb_concept");

  const readFileAsDataUrl = (f) =>
    new Promise((resolve) => {
      if (!f) return resolve("");
      const r = new FileReader();
      r.onload = () => resolve(String(r.result || ""));
      r.onerror = () => resolve("");
      r.readAsDataURL(f);
    });

  const refreshPublish = () => {
    if (!lastGenerate) return;
    renderPublishDraft();
  };

  // UI: dropdown de variantes de título (Growth Engine) → copia para o input editável.
  if (pubTitleVariantsSel && pubTitleInput) {
    pubTitleVariantsSel.onchange = () => {
      const next = String(pubTitleVariantsSel.value || "").trim();
      if (!next) return;
      pubTitleInput.value = next;
      if (!lastGenerate) lastGenerate = {};
      ensurePublishDraft();
      lastGenerate.publish_draft.title = next;
      // Por UX, também atualiza o default do título curto do thumbnail (o usuário pode editar depois).
      if (!lastGenerate.thumbnail_draft) lastGenerate.thumbnail_draft = {};
      if (!String(lastGenerate.thumbnail_draft.title || "").trim()) {
        lastGenerate.thumbnail_draft.title = next.slice(0, 60);
      }
    };
  }

  // Mantém estado local coerente quando o usuário edita manualmente o título.
  if (pubTitleInput) {
    pubTitleInput.addEventListener("input", () => {
      if (!lastGenerate) return;
      ensurePublishDraft();
      lastGenerate.publish_draft.title = String(pubTitleInput.value || "").trim();
      // Não força atualizar thumb_title aqui (evita sobrescrever edições da thumbnail).
      // Apenas mantém o dropdown em sync quando a edição coincidir com uma variante.
      if (pubTitleVariantsSel) {
        syncPublishTitleVariantsUi({
          variants: lastGenerate?.publish_draft?.title_variants || lastGenerate?.growth?.title_variants || [],
          selected: pubTitleInput.value,
        });
      }
    });
  }

  const pubDescVariantsSel = $("pub_description_variants");
  const pubDescInput = $("pub_description");

  if (pubDescVariantsSel && pubDescInput) {
    pubDescVariantsSel.onchange = () => {
      const raw = pubDescVariantsSel.value;
      if (raw === "") return;
      const i = parseInt(raw, 10);
      if (!lastGenerate) lastGenerate = {};
      ensurePublishDraft();
      const list = lastGenerate.publish_draft.description_variants || [];
      if (!Number.isFinite(i) || !list[i]) return;
      pubDescInput.value = list[i];
      lastGenerate.publish_draft.description = list[i];
    };
  }

  if (pubDescInput) {
    pubDescInput.addEventListener("input", () => {
      if (!lastGenerate) return;
      ensurePublishDraft();
      lastGenerate.publish_draft.description = String(pubDescInput.value || "").trim();
      if (pubDescVariantsSel) {
        syncPublishDescriptionVariantsUi({
          variants: lastGenerate.publish_draft.description_variants || [],
          selectedText: pubDescInput.value,
        });
      }
    });
  }

  // Conceitos de thumbnail do Growth Engine → template + título curto.
  if (thumbConceptSel) {
    thumbConceptSel.onchange = () => {
      const raw = String(thumbConceptSel.value || "").trim();
      if (raw === "") return;
      const i = parseInt(raw, 10);
      if (!Number.isFinite(i)) return;
      applyThumbnailConceptIndex(i);
    };
  }

  async function refreshYoutube() {
    if (!ytStatus) return;
    const badge = $("yt_conn_badge");
    const setConnUi = (status, msg) => {
      if (badge) {
        badge.setAttribute("data-yt-status", status);
        badge.textContent = msg;
      }
      if (btnYtConnect) {
        btnYtConnect.textContent = status === "connected" ? "Reconectar YouTube" : "Conectar YouTube";
      }
    };

    setConnUi("unknown", "Verificando…");
    ytStatus.textContent = "Carregando canais…";
    try {
      const data = await LabApi.getYoutubeChannels();
      if (data.status === "not_connected") {
        setConnUi("disconnected", "Não conectado");
        ytStatus.textContent = "Não conectado. Clique em “Conectar YouTube”, autorize no Google, depois “Carregar canais”.";
        renderYoutubeChannels([]);
        return;
      }
      if (data.status !== "ok") {
        setConnUi("error", "Erro");
        ytStatus.textContent = `Erro ao carregar canais: ${data.detail ? String(data.detail) : "desconhecido"}`;
        renderYoutubeChannels([]);
        return;
      }
      renderYoutubeChannels(data.channels || []);
      setConnUi("connected", "Conectado");
      ytStatus.textContent = `Canais carregados: ${(data.channels || []).length}.`;
    } catch (e) {
      setConnUi("error", "Erro");
      ytStatus.textContent = `Erro ao consultar /api/youtube/channels: ${e.message || e}`;
      renderYoutubeChannels([]);
    }
  }

  if (btnYtConnect) {
    btnYtConnect.onclick = () => {
      // abre o consentimento em nova aba/janela
      window.open(LabApi.youtubeOauthStartUrl(), "_blank", "noopener,noreferrer");
      if (ytStatus) ytStatus.textContent = "Abra a janela do Google, autorize, volte e clique em “Carregar canais”.";
    };
  }

  if (btnYtRefresh) btnYtRefresh.onclick = () => refreshYoutube();

  if (pubChannel) {
    pubChannel.onchange = () => {
      if (!lastGenerate) lastGenerate = {};
      ensurePublishDraft();
      const id = String(pubChannel.value || "").trim();
      lastGenerate.publish_draft.channel_id = id;
      const selected = pubChannel.options[pubChannel.selectedIndex];
      lastGenerate.publish_draft.channel_title = selected ? String(selected.textContent || "").trim() : "";
      if (ytStatus) ytStatus.textContent = id ? `Canal selecionado: ${lastGenerate.publish_draft.channel_title}` : "Selecione um canal para publicar.";
    };
  }

  if (btnSaveMeta) {
    btnSaveMeta.onclick = () => {
      if (!lastGenerate) return alert("Gere o roteiro primeiro.");
      ensurePublishDraft();
      lastGenerate.publish_draft.title = $("pub_title")?.value?.trim() || "";
      lastGenerate.publish_draft.description = $("pub_description")?.value?.trim() || "";
      lastGenerate.publish_draft.tags = $("pub_tags")?.value?.trim() || "";
      if (pubStatus) pubStatus.textContent = "Metadados salvos no estado local.";
    };
  }

  const btnPubLlm = $("btn-pub-llm-meta");
  if (btnPubLlm) {
    btnPubLlm.onclick = async () => {
      const script = buildNarrationScript();
      if (!script.trim()) return alert("Gere o roteiro com textos antes.");
      btnPubLlm.disabled = true;
      if (pubStatus) pubStatus.textContent = "Gerando metadados (LLM)…";
      try {
        const tp = $("tema")?.value?.trim() || "";
        const ang = $("angulo")?.value?.trim() || "";
        const td = lastResearchPack && lastResearchPack.trends_panel ? lastResearchPack.trends_panel : undefined;
        const data = await LabApi.postMetadataAgentPreview({
          topic: tp,
          angle: ang,
          script,
          trending_data: td && typeof td === "object" ? td : undefined,
        });
        const md = data.metadata || {};
        if ($("pub_title") && md.title) $("pub_title").value = String(md.title);
        if ($("pub_description") && md.description) $("pub_description").value = String(md.description);
        if ($("pub_tags") && Array.isArray(md.tags)) $("pub_tags").value = md.tags.join(", ");
        if (lastGenerate) {
          lastGenerate.metadata = md;
          ensurePublishDraft();
          const tvm = Array.isArray(md.title_variants) ? md.title_variants : [];
          lastGenerate.publish_draft.title_variants = tvm.length ? tvm : [];
          const dopts = Array.isArray(md.description_options) ? md.description_options : [];
          lastGenerate.publish_draft.description_variants = dopts;
          lastGenerate.growth = null;
          if (lastGenerate.thumbnail_draft && "concept_idx" in lastGenerate.thumbnail_draft) {
            delete lastGenerate.thumbnail_draft.concept_idx;
          }
          if (pubTitleVariantsSel)
            syncPublishTitleVariantsUi({ variants: lastGenerate.publish_draft.title_variants, selected: $("pub_title")?.value || "" });
          syncPublishDescriptionVariantsUi({
            variants: lastGenerate.publish_draft.description_variants || [],
            selectedText: $("pub_description")?.value || "",
          });
          syncThumbConceptSelectUi();
          ensurePublishDraft();
        }
        if (pubStatus) pubStatus.textContent = "Metadados gerados pelo metadata_agent.";
      } catch (e) {
        alert(e.message);
        if (pubStatus) pubStatus.textContent = "";
      } finally {
        btnPubLlm.disabled = false;
      }
    };
  }

  if (btnGrowthMeta) {
    btnGrowthMeta.onclick = async () => {
      const script = buildNarrationScript();
      if (!script.trim()) return alert("Gere o roteiro com textos antes.");
      btnGrowthMeta.disabled = true;
      if (pubStatus) pubStatus.textContent = "Gerando metadados (Growth Engine)…";
      try {
        const tp = $("tema")?.value?.trim() || "";
        const ang = $("angulo")?.value?.trim() || "";
        const publico = $("pub_publico_alvo")?.value?.trim() || "";
        const objetivo = $("pub_objetivo_video")?.value?.trim() || "";
        const td = lastResearchPack && lastResearchPack.trends_panel ? lastResearchPack.trends_panel : undefined;
        const data = await LabApi.postPublishGrowthEnginePreview({
          topic: tp,
          angle: ang,
          publico_alvo: publico,
          objetivo_video: objetivo,
          script,
          trending_data: td && typeof td === "object" ? td : undefined,
          // timeline/segments ainda não existe no lab web; pode ser adicionado depois
        });
        const md = data.metadata || {};
        if ($("pub_title") && md.title) $("pub_title").value = String(md.title);
        if ($("pub_description") && md.description) $("pub_description").value = String(md.description);
        if ($("pub_tags") && Array.isArray(md.tags)) $("pub_tags").value = md.tags.join(", ");
        if (lastGenerate) {
          lastGenerate.metadata = md;
          lastGenerate.growth = data.growth || null;
          ensurePublishDraft();
          const variants = Array.isArray(data?.growth?.title_variants) ? data.growth.title_variants : [];
          lastGenerate.publish_draft.title_variants = variants;
          if (pubTitleVariantsSel) syncPublishTitleVariantsUi({ variants, selected: $("pub_title")?.value || "" });
          const dopts = Array.isArray(data?.growth?.description_options) ? data.growth.description_options : [];
          lastGenerate.publish_draft.description_variants = dopts;
          syncPublishDescriptionVariantsUi({
            variants: dopts,
            selectedText: $("pub_description")?.value || "",
          });
          const tc = Array.isArray(data?.growth?.thumbnail_concepts) ? data.growth.thumbnail_concepts : [];
          if (tc.length) applyThumbnailConceptIndex(0);
          else if (lastGenerate.thumbnail_draft && "concept_idx" in lastGenerate.thumbnail_draft) {
            delete lastGenerate.thumbnail_draft.concept_idx;
          }
          syncThumbConceptSelectUi();
          ensurePublishDraft();
        }
        if (pubStatus) pubStatus.textContent = "Metadados gerados pelo Growth Engine.";
      } catch (e) {
        alert(e.message);
        if (pubStatus) pubStatus.textContent = "";
      } finally {
        btnGrowthMeta.disabled = false;
      }
    };
  }

  const dlgUpload = $("dialog_youtube_upload");
  const uploadSummary = $("upload_confirm_summary");
  const btnUploadCancel = $("btn_upload_cancel");
  const btnUploadConfirm = $("btn_upload_confirm");
  const btnYtReal = $("btn-youtube-upload-real");

  if (btnUploadCancel && dlgUpload) {
    btnUploadCancel.onclick = () => {
      if (typeof dlgUpload.close === "function") dlgUpload.close();
    };
  }

  if (btnYtReal && dlgUpload && uploadSummary) {
    btnYtReal.onclick = () => {
      if (!lastGenerate) return alert("Gere o roteiro primeiro.");
      ensurePublishDraft();
      const jt = String($("pub_job_token")?.value || composerJobToken || "").trim();
      if (!jt) return alert("Sem job_token — execute TTS e compositor na aba Compor vídeo.");
      const ch = String($("pub_channel")?.value || "").trim();
      if (!ch) return alert("Selecione um canal.");
      const title = String($("pub_title")?.value || "").trim();
      if (!title) return alert("Preencha o título.");
      const desc = String($("pub_description")?.value || "").trim();
      const tags = String($("pub_tags")?.value || "").trim();
      uploadSummary.textContent = [
        `Job: ${jt}`,
        `Canal: ${ch}`,
        `Título: ${title}`,
        `Descrição (início): ${desc.slice(0, 240)}${desc.length > 240 ? "…" : ""}`,
        `Tags: ${tags || "(nenhuma)"}`,
        "Ficheiro: final.mp4 deste job no servidor.",
        "Privacidade: conforme PUBLISH_PRIVACY_STATUS no BFF (tipicamente private).",
        "",
        "Confirme apenas se o vídeo e os metadados estão corretos.",
      ].join("\n");
      if (typeof dlgUpload.showModal === "function") dlgUpload.showModal();
    };
  }

  if (btnUploadConfirm && dlgUpload) {
    btnUploadConfirm.onclick = async () => {
      const jt = String($("pub_job_token")?.value || composerJobToken || "").trim();
      const ch = String($("pub_channel")?.value || "").trim();
      const title = String($("pub_title")?.value || "").trim();
      if (!jt || !ch || !title) {
        alert("Dados incompletos.");
        return;
      }
      btnUploadConfirm.disabled = true;
      if (pubStatus) pubStatus.textContent = "Enviando vídeo ao YouTube…";
      try {
        const data = await LabApi.postYoutubeUpload({
          job_token: jt,
          title,
          description: String($("pub_description")?.value || ""),
          tags_csv: String($("pub_tags")?.value || ""),
          channel_id: ch,
        });
        if (typeof dlgUpload.close === "function") dlgUpload.close();
        if (pubStatus)
          pubStatus.textContent = `Upload ok · video_id=${data.video_id || "?"} · ${data.publish_status || ""}`;
      } catch (e) {
        alert(e.message);
        if (pubStatus) pubStatus.textContent = "";
      } finally {
        btnUploadConfirm.disabled = false;
      }
    };
  }

  if (btnGenThumb) {
    btnGenThumb.onclick = async () => {
      if (!lastGenerate) return alert("Gere o roteiro primeiro.");
      ensurePublishDraft();
      lastGenerate.thumbnail_draft.template_id = $("thumb_template")?.value || "logo_brand";
      lastGenerate.thumbnail_draft.brand_color = $("thumb_brand_color")?.value || "#7c5cff";
      lastGenerate.thumbnail_draft.title = $("thumb_title")?.value || "";

      if (!composerJobToken) return alert("Você precisa compor o vídeo (final.mp4) antes de gerar thumbnail.");
      if (!composerHasFinalVideo) return alert("Ainda não existe final.mp4 nesse job. Vá em “Compor vídeo” e execute o passo 3 (Compor).");

      btnGenThumb.disabled = true;
      if (pubStatus) pubStatus.textContent = "Gerando thumbnail…";
      try {
        const logoUrl = String(lastGenerate.thumbnail_draft.logo_data_url || "").trim();
        const thumbPayload = {
          job_token: composerJobToken,
          template_id: lastGenerate.thumbnail_draft.template_id,
          brand_color: lastGenerate.thumbnail_draft.brand_color,
          title: lastGenerate.thumbnail_draft.title || lastGenerate.publish_draft.title || "",
        };
        if (logoUrl) thumbPayload.logo_data_url = logoUrl;
        const resp = await LabApi.postThumbnailCardAgentPreview(thumbPayload);
        const url = (resp && resp.thumbnail_url) ? String(resp.thumbnail_url) : "";
        if (!url) throw new Error("Resposta sem thumbnail_url");
        // bust cache
        const bust = url + (url.includes("?") ? "&" : "?") + "t=" + Date.now();
        lastGenerate.thumbnail_draft.preview_data_url = bust;
        lastGenerate.thumbnail_draft.mode = "auto_template";
        renderPublishDraft();
        if (pubStatus) pubStatus.textContent = "Thumbnail gerada no servidor e disponível no job.";
      } catch (e) {
        // fallback para mock (mantém UX para quem não tem ffmpeg/Pillow)
        const bgDataUrl = lastGenerate.thumbnail_draft.upload_data_url || "";
        const logoDataUrl = lastGenerate.thumbnail_draft.logo_data_url || "";
        const res = drawThumbnailMock({
          templateId: lastGenerate.thumbnail_draft.template_id,
          brandColor: lastGenerate.thumbnail_draft.brand_color,
          titleText: lastGenerate.thumbnail_draft.title || lastGenerate.publish_draft.title || "",
          logoDataUrl,
          bgDataUrl,
        });
        const dataUrl = typeof res === "string" ? res : await res;
        lastGenerate.thumbnail_draft.preview_data_url = dataUrl;
        lastGenerate.thumbnail_draft.mode = bgDataUrl ? "uploaded" : "auto_template";
        renderPublishDraft();
        if (pubStatus) pubStatus.textContent = `Falha ao gerar no servidor; usando mock local. (${e.message || e})`;
      } finally {
        btnGenThumb.disabled = false;
      }
    };
  }

  if (logoInput) {
    logoInput.onchange = async () => {
      if (!lastGenerate) return;
      ensurePublishDraft();
      const f = logoInput.files && logoInput.files[0];
      lastGenerate.thumbnail_draft.logo_data_url = await readFileAsDataUrl(f);
      if (pubStatus) pubStatus.textContent = "Logo/foto carregado. Clique em “Gerar thumbnail”.";
    };
  }

  if (uploadInput) {
    uploadInput.onchange = async () => {
      if (!lastGenerate) return;
      ensurePublishDraft();
      const f = uploadInput.files && uploadInput.files[0];
      lastGenerate.thumbnail_draft.upload_data_url = await readFileAsDataUrl(f);
      // também atualiza preview direto
      lastGenerate.thumbnail_draft.preview_data_url = lastGenerate.thumbnail_draft.upload_data_url || "";
      lastGenerate.thumbnail_draft.mode = "uploaded";
      renderPublishDraft();
      if (pubStatus) pubStatus.textContent = "Thumbnail enviada e persistida no estado local.";
    };
  }

  if (btnPub) {
    btnPub.onclick = async () => {
      if (!lastGenerate) return alert("Gere o roteiro primeiro.");
      ensurePublishDraft();
      if (!lastGenerate.publish_draft.channel_id) {
        alert("Selecione um canal do YouTube (obrigatório). Clique em “Conectar YouTube” e “Carregar canais”.");
        return;
      }
      btnPub.disabled = true;
      if (pubStatus) pubStatus.textContent = "Publicando (mock)…";
      await new Promise((r) => setTimeout(r, 700));
      lastGenerate.publish_draft.status = "published_mock";
      btnPub.disabled = false;
      if (pubStatus)
        pubStatus.textContent = `Publicado (mock) no canal ${lastGenerate.publish_draft.channel_title || lastGenerate.publish_draft.channel_id}. Estado local atualizado.`;
    };
  }

  // Atualiza campos ao entrar/atualizar estado
  const oldSetActiveTab = setActiveTab;
  setActiveTab = (name) => {
    oldSetActiveTab(name);
    if (name === "publish") {
      refreshPublish();
      // tenta carregar (não bloqueia) — se não estiver conectado, mostra status.
      refreshYoutube();
    }
  };
});

