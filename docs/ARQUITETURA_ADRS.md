# ADRs — workshop / laboratório (Ideias Factory)

Este ficheiro no pacote **`workshop/docs/`** resume os ADRs relevantes ao **lab e demos** e remete ao documento canónico na raiz: **[`docs/ARQUITETURA_ADRS.md`](../../docs/ARQUITETURA_ADRS.md)**. Alterações formais aos ADRs devem ser feitas primeiro no canónico e reflectidas aqui quando afetarem o workshop.

Para **defesa das decisões**: contexto · decisão · consequências. Complementa [ARCHITECTURE_WORKSHOP.md](ARCHITECTURE_WORKSHOP.md); visão global do pipeline em [ARCHITECTURE.MD](../../ARCHITECTURE.MD).

---

## Nota sobre o termo ADR

- **ADR** significa habitualmente **Architecture Decision *Records*** (registos que documentam **uma** decisão tomada), no sentido de Michael Nygard e da comunidade [adr.github.io](https://adr.github.io/).
- **“Architecture Decision Rules”** não é o termo consensual na literatura; se a equipa quiser usar *rules* internamente, convém explicitar que são **regras derivadas** das decisões registadas, não o nome do padrão ADR.

Cada ADR abaixo segue: **estado** · **contexto** · **decisão** · **consequências** (e, quando útil, alternativas rejeitadas).

---

## Forças de contexto (drivers)

Estas **não** são ADRs: são restrições ou objetivos que **motivam** os ADRs seguintes.

| Driver | Descrição |
|--------|-----------|
| **D1** | Orquestração explícita de um fluxo multi‑etapa (research → … → publisher) com dependências entre etapas. |
| **D2** | Contrato único de estado (`VideoState`) entre nós; imutabilidade entre invocações de cada agente. |
| **D3** | Separação CPU vs GPU: inferência pesada e vídeo na máquina com GPU; resto em nós ARM/CPU. |
| **D4** | LLM e geração visual sob controlo local quando possível (custo, latência, dados). |
| **D5** | Integrações externas estáveis onde há compromisso de fiabilidade (ex.: YouTube Data API v3); sinais exploratórios (Trends) isolados. |
| **D6** | Artefactos de job em paths absolutos partilháveis (NFS no homelab). |
| **D7** | Laboratório para demo/QA sem substituir o orquestrador; evolução desacoplada. |
| **D8** | Observabilidade mínima sem expor segredos (`/health`). |
| **D9** | Publicação segura por defeito até HITL (ex.: `privacyStatus: private`). |

---

## Índice de ADRs

| ID | Título |
|----|--------|
| [ADR-001](#adr-001--langgraph-stategroup-como-orquestrador) | LangGraph `StateGraph` como orquestrador |
| [ADR-002](#adr-002--arquitetura-híbrida-on-prem--apis-vs-cloud-native-única) | Arquitetura híbrida (on‑prem + APIs) vs cloud‑native única |
| [ADR-003](#adr-003--llmgateway-com-ollama-na-gpu) | `LLMGateway` com Ollama na GPU |
| [ADR-004](#adr-004--pacotes-experimentsbackend-vs-experimentsgpu) | Pacotes `workshop/backend` vs `workshop/gpu` |
| [ADR-005](#adr-005--laboratório-fastapi-bff--spa-estática) | Laboratório: FastAPI (BFF) + SPA estática |
| [ADR-006](#adr-006--experimentsarm-como-camada-de-laboratório) | `workshop/arm` como camada de laboratório |
| [ADR-007](#adr-007--imutabilidade-do-videostate-entre-nós) | Imutabilidade do `VideoState` entre nós |

---

### ADR-001 — LangGraph (`StateGraph`) como orquestrador

- **Estado:** Aceite  
- **Contexto:** D1, D2 — vários agentes, ordem fixa na fase 1, estado comum.  
- **Decisão:** Usar **LangGraph** com `StateGraph(VideoState)` e arestas explícitas entre nós.  
- **Alternativas consideradas:** Orquestração ad‑hoc em Python; apenas LangChain sem grafo; workflows só no CI.  
- **Consequências:** Dependência `langgraph` / `langchain-core`; evolução para `add_conditional_edges` na fase 2; testes por nó como funções puras.

---

### ADR-002 — Arquitetura híbrida (on‑prem + APIs) vs cloud‑native única

- **Estado:** Aceite  
- **Contexto:** Homelab IHL; D3, D4, D6 — GPU e NFS locais.  
- **Decisão:** **Híbrido:** compute e armazenamento **on‑prem** onde há controlo de custo e dados; **APIs SaaS** (stock, YouTube, opcional ElevenLabs) como bordas.  
- **Alternativas consideradas:** Stack maioritariamente cloud gerida (Step Functions, S3, etc.); tudo self‑hosted sem SaaS.  
- **Consequências:** Operação de rede (túneis, firewall); manutenção de Ollama/ComfyUI/ffmpeg; documentação de deploy por nó.

---

### ADR-003 — `LLMGateway` com Ollama na GPU

- **Estado:** Aceite  
- **Contexto:** D4; agentes em CPU chamam LLM via HTTP para o serviço na GPU.  
- **Decisão:** **`LLMGateway`** com `OLLAMA_BASE_URL`; extensível a OpenAI/Anthropic por env.  
- **Consequências:** Troca de provider sem reescrever cada agente; parsing de JSON centralizado.

---

### ADR-004 — Pacotes `workshop/backend` vs `workshop/gpu`

- **Estado:** Aceite  
- **Contexto:** D3 — clareza entre ComfyUI/ffmpeg e lógica CPU.  
- **Decisão:** Agentes **visual** e **composer** em `workshop/gpu`; `core` e restantes agentes em `workshop/backend`.  
- **Consequências:** O grafo importa ambos; binários pesados só no nó GPU.

---

### ADR-005 — Laboratório: FastAPI (BFF) + SPA estática

- **Estado:** Aceite  
- **Contexto:** D7; OpenAPI, `/health`, UI de workshop.  
- **Decisão:** **FastAPI** para API + estáticos; sem framework full‑stack server‑rendered.  
- **Consequências:** Contrato HTTP explícito (`LabApi`); estado de UI no cliente.

---

### ADR-006 — `workshop/arm` como camada de laboratório

- **Estado:** Aceite  
- **Contexto:** D7 — adaptadores para o BFF sem confundir com o nó LangGraph canónico.  
- **Decisão:** Módulos alinhados aos **nomes** dos agentes para o lab; implementação do grafo em `backend`/`gpu`.  
- **Consequências:** Nome `arm` não implica só hardware ARM; ver [ARCHITECTURE_WORKSHOP.md](ARCHITECTURE_WORKSHOP.md).

---

### ADR-007 — Imutabilidade do `VideoState` entre nós

- **Estado:** Aceite  
- **Contexto:** D2.  
- **Decisão:** Cada agente devolve novo dicionário derivado do estado (`{**state, ...}`), sem mutar o recebido in‑place.  
- **Consequências:** Menos efeitos colaterais; testes mais simples por nó.

---

## Rastreabilidade: drivers → ADRs

| Drivers | ADRs |
|---------|------|
| D1, D2 | ADR-001, ADR-007 |
| D3, D4 | ADR-002, ADR-003, ADR-004 |
| D5 | ADR implícito em providers + docs de Trends |
| D6 | ADR-002 (NFS/paths) |
| D7 | ADR-005, ADR-006 |
| D8 | `/health` no BFF |
| D9 | `PUBLISH_PRIVACY_STATUS`, HITL na roadmap |

---

## Evolução e riscos

- **Fase 2:** ramos no grafo — ADR-001 mantém-se se o estado continuar central (ver [ARCHITECTURE.MD](../../ARCHITECTURE.MD)).  
- **Riscos:** dependência de APIs externas; mitigação: timeouts, fixtures em testes.  
- **Risco operacional:** homelab indisponível; mitigação: health checks, `web-demo-offline`.

---

## Referências internas

- [ARCHITECTURE.MD](../../ARCHITECTURE.MD) — pipeline, cluster, laboratório, stack.  
- [ARCHITECTURE_WORKSHOP.md](ARCHITECTURE_WORKSHOP.md) — camadas lógicas/físicas.  
- [CONFIGURATION.md](CONFIGURATION.md) — variáveis de ambiente (este pacote); guia completo em [`../../docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md).

---

*O ficheiro legado `ARQUITETURA_ASRS_E_DECISOES.md` (uso incorreto do termo “ASR”) foi substituído pelo documento canónico na raiz. O acrónimo **ASR** no código/UI do projeto refere‑se a *Automatic Speech Recognition* (ex.: `POST /api/lab/asr`), não a requisitos arquiteturais.*
