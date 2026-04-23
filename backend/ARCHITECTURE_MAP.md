# Mapa backend vs GPU (workshop)

Camada didática alinhada ao homelab: **ARM/CPU (backend)** vs **GPU**.

## `workshop/backend/`

| Origem (monorepo) | Destino |
|-------------------|---------|
| `core/*` | `workshop/backend/core/` |
| `agents/research_agent.py`, `script_agent.py`, `asset_agent.py`, `asset_sources*.py`, `asset_providers/`, `tts_agent.py`, `metadata_agent.py`, `publisher_agent.py`, `thumbnail_card_agent.py`, `trends_signals.py`, `youtube_client.py`, `prompt_loader.py` | `workshop/backend/agents/` |

## `workshop/gpu/`

| Origem | Destino |
|--------|---------|
| `agents/visual_agent.py`, `composer_agent.py`, `comfy_client.py` | `workshop/gpu/agents/` |

## Raiz do monorepo (`core/`, `agents/`)

Mantém **re-exports** finos para `scripts/run_pipeline.py`, testes e ferramentas que ainda importam `from core.*` / `from agents.*`.

## Config e prompts

Prompts por agente: canónico em `prompts/<agent>/` na raiz; cópia em `workshop/prompts/` via `python scripts/sync_workshop_config.py`. `prompt_loader` usa `workshop/prompts/` primeiro, depois `{monorepo}/prompts/`.

## Documentação workshop (camadas lógicas / físicas / sequências)

Ver [workshop/docs/ARCHITECTURE_WORKSHOP.md](../docs/ARCHITECTURE_WORKSHOP.md) e imagens em [workshop/docs/diagrams/](../docs/diagrams/). ADRs: [workshop/docs/ARQUITETURA_ADRS.md](../docs/ARQUITETURA_ADRS.md) · canónico na raiz: [docs/ARQUITETURA_ADRS.md](../../docs/ARQUITETURA_ADRS.md).
