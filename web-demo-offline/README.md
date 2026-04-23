# Demo offline (IA VideoStudio)

SPA autónoma para vendas e onboarding: **sem BFF** — `mock_api.js` expõe o mesmo contrato que `workshop/web/js/services.js` e lê respostas de `mock_data.js`.

## Paridade com o laboratório

- A UI (markup, `app.js` e `css/styles.css`) segue a versão do laboratório em `workshop/web/`, com a faixa de aviso no topo, `tour.js` e `demo_analytics.js` específicos da demo.
- Não executa Ollama, ComfyUI, Whisper, OAuth real, YouTube real, nem leitura de ficheiros no NFS. O áudio do TTS em mock usa `assets/demo_narration.mp3` (frase extraída do roteiro fictício em PT); o vídeo de pré-visualização usa um clip CC0 (MDN `flower.mp4`) — ver `DEMO_SAMPLE_*` em `mock_data.js`. Sirva a pasta com HTTP estático (`python -m http.server`) para caminhos relativos a `assets/` funcionarem de forma fiável.
- `postThumbnailCardAgentPreview` devolve `thumbnail_url` vazio de propósito: a app cai no desenho de thumbnail em canvas (como no lab sem Pillow/ffmpeg).
- **OpenAPI / Swagger** no host do BFF: com `uvicorn workshop.bff.lab_server:app` (ex. `http://127.0.0.1:8092/swagger`). O link «OpenAPI» no header da demo é informativo (sem servidor local no `index.html`).

## Ficheiros

| Ficheiro | Papel |
|----------|--------|
| `index.html` | UI alinhada ao lab + scripts de mock e tour |
| `js/mock_data.js` | Corpos de resposta JSON |
| `js/mock_api.js` | `LabApi` falso (incl. `getLabUiConfig`, Growth, ASR, `postLabSyncCompose`, `simulatePipelineAfterAssets`, etc.) |
| `js/tour.js` | Tour guiado (chave de `localStorage` v2); requer CSS `#tour_*` em `css/styles.css` |
| `assets/demo_narration.mp3` | Narração curta PT-BR para preview TTS (ex.: gerada com `say` + `ffmpeg` no macOS) |
| `js/demo_analytics.js` | PostHog / métricas opcionais — ver `ANALYTICS.md` |

Para o fluxo com APIs reais, GPUs e OAuth, use o laboratório: `python -m uvicorn workshop.bff.lab_server:app`.

