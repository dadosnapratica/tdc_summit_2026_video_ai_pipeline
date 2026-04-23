# Configuração — variáveis de ambiente (laboratório & monorepo)

Este guia está **alinhado** ao documento da raiz do repositório: **[`docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md)**. Aí está a lista canónica; aqui repetimos o essencial com **referências ao layout do projeto** (`workshop/` + código canónico em `workshop/backend` e `workshop/gpu`; a raiz `agents/` / `core/` mantém *re-exports* para compatibilidade).

## Onde ficam os ficheiros de configuração

| Ficheiro | Função |
|----------|--------|
| [`../.env.example`](../.env.example) | Template **auto-contido** quando `workshop/` é a raiz do repositório (copiar para `workshop/.env`). |
| [`../../.env.example`](../../.env.example) na raiz do monorepo | Template canónico — copiar para `.env` na raiz (nunca commitar segredos). |
| `workshop/.env` (opcional) | Sobrescreve valores para o workshop; o BFF carrega **`workshop/.env` primeiro**, depois `../../.env`. |
| [`../../set-ambiente-workshop/.env.example`](../../set-ambiente-workshop/.env.example) | SSH para `cluster_infra_setup` (`CLUSTER_SSH_*`). |
| [`../../set-ambiente-workshop/server/gpu-edge/jwt_broker/.env.example`](../../set-ambiente-workshop/server/gpu-edge/jwt_broker/.env.example) | Broker JWT (stack `gpu-edge`; ver [CONFIGURATION.md](../../set-ambiente-workshop/server/gpu-edge/jwt_broker/CONFIGURATION.md)). |
| [`../../scripts/cluster_nodes.env.example`](../../scripts/cluster_nodes.env.example) | Identidade dos nós do cluster (GPU, Pi5, paths remotos). |

**Carregamento no laboratório:** `workshop/bff/lab_server.py` usa `python-dotenv` com prioridade para `workshop/.env`, depois `.env` na raiz do monorepo.

**Carregamento geral:** vários scripts na raiz leem `.env` na raiz. O script `scripts/cluster_infra_setup.py` carrega, por ordem: `.env` na raiz; `set-ambiente-workshop/.env` (se existir); `scripts/cluster_nodes.env` (se existir). Leituras posteriores **não** sobrepõem variáveis já definidas no `.env` da raiz.

---

## Bases e interpolação (`.env`)

Igual à raiz: variáveis-base `${LOCAL_SERVICES_BASE_URL}`, `${PROJECT_BASE_PATH}`, `${NAS_MOUNT_PATH}`, `${MODELS_BASE_PATH}` — ver capítulo inicial em **[`docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md)**.

---

## Caminhos no código (pacote `workshop`)

Os caminhos nos documentos da raiz referem por vezes `core/` e `agents/` na raiz do monorepo. No pacote **workshop**, a implementação canónica está em:

| Referência na doc da raiz | Implementação workshop |
|---------------------------|-------------------------|
| `core/llm_gateway.py`, `core/paths.py`, `core/state.py` | `workshop/backend/core/` |
| `agents/*_agent.py`, `agents/asset_providers/` | `workshop/backend/agents/` |
| `agents/visual_agent.py`, `composer_agent.py` | `workshop/gpu/agents/` |

Variáveis de ambiente são **as mesmas** (o runtime resolve os mesmos nomes).

---

## Secções por área

Use o documento da raiz para as tabelas completas:

1. **Globais e infraestrutura** — LLM, jobs, ffmpeg, Trends.  
2. **Por agente (pipeline)** — research, asset, visual, TTS, composer, metadata, publisher, thumbnail.  
3. **Laboratório (BFF e `workshop/arm`)** — rankers, OAuth YouTube, matplotlib.  
4. **Scripts de cluster** — SSH, `CLUSTER_*`.  
5. **Legado e aliases** — tabelas no [guia completo](../../docs/CONFIGURATION.md).

---

## Validação remota (Mac ou CI, env do workshop)

Para confirmar que **`JWT_BROKER_PUBLIC_URL`**, **`OLLAMA_BASE_URL`** e **`COMFYUI_BASE_URL`** (tipicamente `${JWT_BROKER_PUBLIC_URL}/v1/proxy/ollama` e `.../comfyui`) e o token **funcionam** antes de subir o BFF:

**Pré-requisitos:** `workshop/.env` com `WORKSHOP_ACCESS_TOKEN` (Bearer para URLs que contêm `/v1/proxy/`). No GPU, ComfyUI tem de aceitar ligações no IP usado pelo broker (`COMFYUI_LISTEN=0.0.0.0` — ver [`set-ambiente-workshop/server/comfyui/CONFIGURACAO.md`](../../set-ambiente-workshop/server/comfyui/CONFIGURACAO.md) §7).

Na **raiz do monorepo**, com venv activo:

```bash
# Broker /health/live, GET Ollama /api/tags, GET ComfyUI /system_stats (Authorization automático para proxy)
python -m workshop.backend.remote_services_probe

# Inclui POST /upload/image (multipart, PNG mínimo) — mesmo contrato que COMFYUI_INPUT_METHOD=upload
python -m workshop.backend.remote_services_probe --upload
```

Validação estruturada em JSON (paths locais + HTTP, inclui Bearer nos proxies):

```bash
python scripts/validate_workshop_config.py
python scripts/validate_workshop_config.py --strict
```

**Verificação directa na LAN** (sem JWT), a partir de qualquer máquina que alcance o GPU:

```bash
LAN_IP=192.168.15.150   # ajustar
curl -sS -o /dev/null -w '%{http_code}\n' "http://${LAN_IP}:8188/system_stats"
```

Esperado: **200** quando o listen e o encaminhamento LAN↔WSL estão correctos.

---

## Referências do projeto

- **Variáveis e stack (visão ampla):** [ARCHITECTURE.MD](../../ARCHITECTURE.MD) (secção de variáveis e infra).
- **Decisões de arquitetura (ADRs):** [ARQUITETURA_ADRS.md](ARQUITETURA_ADRS.md) (este pacote) · [guia canónico](../../docs/ARQUITETURA_ADRS.md).
- **Mapa do pacote `workshop/`:** [ARCHITECTURE_WORKSHOP.md](ARCHITECTURE_WORKSHOP.md).
- **Infra do cluster (comandos):** `scripts/cluster_infra_setup.py`, `scripts/cluster_nodes.env.example`.

---

*Manter este ficheiro coerente com [`docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md); alterações às variáveis devem refletir-se nos dois sítios quando afetarem o laboratório.*
