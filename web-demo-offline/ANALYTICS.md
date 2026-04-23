# Analytics — demo offline (IA VideoStudio)

## Typeform — embed num site genérico (instruções oficiais)

Resumo da [ajuda Typeform](https://www.typeform.com/help/) para colar o formulário num site que não seja WordPress/Webflow/etc. dedicado:

1. **Site builder** — Inicia sessão no teu construtor de sites. Abre a página ou o bloco onde queres o typeform. Pode existir uma ferramenta para incorporar um elemento externo.
2. **Vista de código** — Abre a vista de código (ícone `</>` ou «Editor HTML»). Cola o código de incorporação do Typeform onde o formulário deve aparecer. Guarda e/ou publica a página.
3. **Documentação do builder** — Consulta o help center do teu site builder para o passo a passo exato de embeds HTML.
4. **Partilha e atualizações** — Depois de configurares o embed, encontras-o no painel esquerdo na página **Share** do Typeform. Alterações de design no Typeform atualizam o embed automaticamente — **não** precisas de voltar a colar o código.

**Snippet típico (Next / generic sites):**

```html
<div data-tf-live="SEU_ID_AQUI"></div>
<script src="//embed.typeform.com/next/embed.js"></script>
```

**Nesta repo (`web-demo-offline`):** não colas o HTML à mão no corpo da página. Define `typeformLiveId` em `window.__VIDEO_STUDIO_DEMO_CONFIG` no `index.html`; o `js/demo_analytics.js` injeta o `div` e o script na primeira abertura do painel de feedback (evita problemas de altura com o painel oculto). O ID obténs em Typeform → **Share** → incorporar.

---

## PostHog (integrado em `js/demo_analytics.js`)

### 1. Criar projeto

1. Conta em [posthog.com](https://posthog.com) (cloud US ou EU).
2. Criar um projeto (ex.: `videostudio-demo-offline`).
3. Em **Project settings** copiar o **Project API Key** (começa por `phc_`).

### 2. Configurar a demo

No `index.html`, dentro de `window.__VIDEO_STUDIO_DEMO_CONFIG`, defina:

| Chave | Exemplo | Notas |
|--------|---------|--------|
| `posthogKey` | `"phc_xxxxxxxx"` | Obrigatório para enviar eventos. |
| `posthogApiHost` | `"https://us.i.posthog.com"` | **US cloud** (padrão). Para **UE**: `https://eu.i.posthog.com`. |
| `collectMetrics` | `true` | `false` desliga métricas locais **e** PostHog. |

### 3. O que é enviado

- `autocapture` e `capture_pageview` estão **desligados** — só eventos explícitos da demo.
- Cada chamada a `track()` gera um evento `demo_<tipo>` (ex.: `demo_session_start`, `demo_tab`, `demo_action`, `demo_tour`, `demo_feedback_open`).
- Propriedade comum: `demo_source: web-demo-offline`.
- Registo de grupo: `demo_session_id` (alinhado ao ID da sessão em `sessionStorage`).

### 4. Onde ver os dados

PostHog → **Activity** / **Insights** → filtrar por eventos `demo_*`.

### 5. RGPD / consentimento

Para uso com visitantes na UE, avalia banner de cookies, base legal e política de privacidade. PostHog permite [configuração de consentimento](https://posthog.com/docs/privacy) conforme o vosso DPO.

---

## Google Analytics 4 (GA4) — incluir depois

Não está no código por defeito (evita duplicar envios com PostHog sem necessidade). Para **adicionar GA4 em paralelo**:

### 1. Criar propriedade GA4

1. [Google Analytics](https://analytics.google.com) → Admin → Criar propriedade → **GA4**.
2. Criar um **fluxo de dados** → **Web** → obter o **Measurement ID** (`G-XXXXXXXXXX`).

### 2. Inserir o snippet gtag

No `<head>` do `index.html` da demo ( **antes** de `demo_analytics.js`), cola o snippet que o GA fornece em **Admin → Fluxos de dados → teu site → Ver instruções de etiqueta**. Exemplo genérico:

```html
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

Substituir `G-XXXXXXXXXX` pelo teu Measurement ID.

### 3. Eventos alinhados com a demo (opcional)

Para espelhar os mesmos momentos no GA4, podes adicionar no final de `demo_analytics.js` (ou num ficheiro `ga4_bridge.js` carregado depois) chamadas `gtag('event', ...)` dentro de `track`, **ou** usar [GA4 Measurement Protocol](https://developers.google.com/analytics/devguides/collection/protocol/ga4) no servidor (não aplicável a HTML estático puro).

Exemplo mínimo de evento personalizado após carregar gtag:

```javascript
if (typeof gtag === 'function') {
  gtag('event', 'demo_tab', { tab_name: 'research' });
}
```

Nomes sugeridos (consistentes com PostHog): `demo_session_start`, `demo_tab`, `demo_action`, `demo_tour`, `demo_feedback_open`.

### 4. Dupla contagem

Se usares PostHog **e** GA4, os dois receberão tráfego — útil para comparar dashboards; configura cada ferramenta para não misturar propriedades de produção com a demo (projeto GA4 / PostHog só para esta pasta).

### 5. Privacidade

GA4 em sites na UE costuma exigir **consentimento** (Consent Mode v2). Consulta a documentação Google e o teu jurídico.

---

## Resumo

| Ferramenta | Estado na repo | Ação |
|------------|----------------|------|
| **PostHog** | Integrado (`posthogKey` + `posthogApiHost`) | Colar API key no `index.html`. |
| **Métricas locais** | `localStorage` + export JSON | Sempre ativo se `collectMetrics !== false`. |
| **GA4** | Não incluído | Seguir secção acima quando quiseres. |
