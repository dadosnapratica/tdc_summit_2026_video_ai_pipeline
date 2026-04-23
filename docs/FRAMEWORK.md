# Frameworks e componentes de runtime — visão de alto nível

Este documento resume **o que cada peça principal faz** no Video Pipeline / laboratório Ideias Factory e **como funciona**, sem substituir [`ARCHITECTURE.MD`](../ARCHITECTURE.MD), [`CONFIGURATION.md`](CONFIGURATION.md) ou o mapa do workshop em [`workshop/docs/ARCHITECTURE_WORKSHOP.md`](../workshop/docs/ARCHITECTURE_WORKSHOP.md).

---

## Orquestração e estado

### LangGraph (`langgraph`) + LangChain Core (`langchain-core`)

| Na arquitetura | Função |
|----------------|--------|
| Modela o pipeline como um **grafo orientado** de nós (`StateGraph`). Cada nó é um “agente” que recebe o estado e devolve atualizações imutáveis. | Define **ordem**, **contrato de dados** (`VideoState`) e extensibilidade futura (ramificações, checkpointers). |

**Funcionamento (resumo):** o estado percorre o grafo sequencialmente (fase 1); cada transição invoca uma função Python que lê o `TypedDict` do estado e retorna um dicionário com as chaves alteradas. O LangGraph encadeia os nós e pode ser compilado para execução única ou serviços que reinvocam o grafo.

---

## Camada HTTP do laboratório

### FastAPI + Uvicorn

| Na arquitetura | Função |
|----------------|--------|
| **FastAPI** expõe o BFF do lab (`workshop/bff/`): rotas REST, validação com Pydantic, OpenAPI. **Uvicorn** é o servidor ASGI que corre o processo HTTP. | Separa **UI estática** (`workshop/web/`) da **lógica** chamando `workshop/arm/*` e `workshop/backend/*`; fornece `/health`, Swagger e uploads temporários por `job_token`. |

**Funcionamento (resumo):** pedidos HTTP chegam ao worker ASGI; handlers chamam funções síncronas ou assíncronas do projeto; respostas são JSON ou ficheiros. O mesmo padrão serve validação na subida (`lifespan`) e documentação automática a partir dos modelos.

---

## Inferência de linguagem (LLM)

### Ollama

| Na arquitetura | Função |
|----------------|--------|
| Servidor **HTTP** que corre modelos LLM localmente (tipicamente na máquina com GPU no homelab). Os agentes no ARM ou no dev laptop **não** embutem o modelo: chamam `OLLAMA_BASE_URL` (ex.: `/api/chat`, `/api/tags`). | Centraliza **Llama/Qwen/Mistral** etc., acoplado ao nosso `LLMGateway` para prompts de research, script, curadoria de assets e metadata. |

**Funcionamento (resumo):** o binário Ollama carrega pesos e expõe uma API REST compatível com o cliente Python `ollama` ou chamadas `requests`. O pipeline só precisa de URL, modelo e timeouts — sem acoplamento ao formato interno do runtime CUDA.

---

## Geração visual e vídeo na GPU

### ComfyUI

| Na arquitetura | Função |
|----------------|--------|
| Interface e motor de grafos para **Stable Diffusion**, **img2img**, extensões como **AnimateDiff**. O `visual_agent` envia workflows JSON e recebe imagens/clipes; endereço em `COMFYUI_BASE_URL`. | Transforma stills do `asset_agent` em clipes ou frames estilizados antes do `composer_agent`. |

**Funcionamento (resumo):** cada pedido instancia um grafo de nós (checkpoint, LoRA, sampler, vídeo); a API HTTP fila execuções e devolve ficheiros ou IDs de resultado. O projeto mantém workflows base em JSON em `config/` e parametriza modelo/força via env.

### FFmpeg

| Na arquitetura | Função |
|----------------|--------|
| Ferramenta de linha de comando para **concat**, **overlay**, **encode** e normalização de áudio/vídeo. Usado pelo `composer_agent` e por caminhos de fallback no lab (clipes curtos a partir de imagens). | Produz **`final.mp4`** a partir da lista de clipes + `narration.wav`; NVENC quando disponível na GPU. |

**Funcionamento (resumo):** pipelines declarativos (`-i`, `-filter_complex`, codecs `h264_nvenc`/`aac`); o código Python gera comando ou listas `concat` e executa subprocess.

---

## Áudio (TTS)

### Kokoro (ONNX) e Piper

| Na arquitetura | Função |
|----------------|--------|
| **Kokoro-onnx:** síntese neural em CPU com modelos ONNX — qualidade útil para narração PT-BR no ARM. **Piper:** fallback leve via executável + `.onnx` + catálogo de vozes. | O `tts_agent` escolhe provider por env (`TTS_PROVIDER`); o lab lista opções Kokoro/Piper via BFF. |

**Funcionamento (resumo):** texto → onnxruntime / binário Piper → waveform → ficheiro WAV no `job_path`. Sem servidor separado obrigatório; paths de modelo vêm de `MODELS_BASE_PATH` / env.

---

## APIs externas e dados

### Google APIs — YouTube Data API v3 (+ OAuth)

| Na arquitetura | Função |
|----------------|--------|
| **Research:** vídeos em tendência, metadados de canal. **Publisher:** `videos.insert` com OAuth2 refresh token. | Integrações estáveis frente a scraping; o lab reutiliza as mesmas credenciais onde aplicável. |

**Funcionamento (resumo):** cliente `google-api-python-client`; pedidos autenticados com API key (leitura) ou fluxo OAuth (upload); quotas e scopes documentados na consola Google Cloud.

### `requests`

| Na arquitetura | Função |
|----------------|--------|
| Cliente HTTP síncrono para Pexels, Pixabay, Unsplash, NASA, Wikimedia, probes de health (`/api/tags`, ComfyUI, broker). | Base de todo I/O REST que não passa pelo SDK Google. |

**Funcionamento (resumo):** sessão simples GET/POST com timeouts e cabeçalhos; retry/backoff onde implementado nos providers.

### pytrends (experimental)

| Na arquitetura | Função |
|----------------|--------|
| Acesso não oficial a sinais **Google Trends** (`related_queries`, `interest_over_time`) para enriquecer o research no lab. | **Não** é garantia de produto; dependências de cookie/UA podem falhar; usado com fallback e logs. |

**Funcionamento (resumo):** biblioteca Python que simula pedidos ao Google; resultados entram em `trending_data` no estado quando disponíveis.

---

## Segurança e operação (workshop)

### PyJWT + broker JWT (processo opcional)

| Na arquitetura | Função |
|----------------|--------|
| **PyJWT:** assinatura e verificação HS256 no **broker** em `set-ambiente-workshop/server/gpu-edge/jwt_broker/`. Tokens com `scope` limitam acesso (ex.: proxy de chaves, validação no Nginx). | Desacopla segredos de APIs de stock do browser e suporta `auth_request` no edge. |

**Funcionamento (resumo):** broker emite JWT com TTL; rotas `/auth/verify` devolvem 204/401 para o Nginx; ver [GUIA-ADMIN-WORKSHOP-JWT.md](GUIA-ADMIN-WORKSHOP-JWT.md).

### python-dotenv

| Na arquitetura | Função |
|----------------|--------|
| Carrega `.env` na raiz e `workshop/.env` com prioridade no BFF e em scripts CLI. | Evita hardcode de hosts e chaves; suporta interpolação `${VAR}` no ficheiro (dotenv ≥ 1). |

---

## Testes

### pytest

| Na arquitetura | Função |
|----------------|--------|
| Corre `tests/` com fixtures (`conftest.py`), mocks de Ollama/HTTP e validação de `VideoState`/agentes. | Garante regressão sem subir GPU ou APIs reais quando os testes usam monkeypatch/fixtures. |

---

## Mapa rápido: “quem chama quem”

```text
Browser  →  FastAPI (BFF)  →  workshop/arm + backend  →  Ollama / APIs / FFmpeg
                                         ↓
                              LangGraph (pipeline)  →  mesmo stack + ComfyUI na GPU
```

Para detalhes de pastas e nós do grafo, ver [workshop/backend/core/pipeline.py](../workshop/backend/core/pipeline.py) e os diagramas em `workshop/docs/diagrams/`.
