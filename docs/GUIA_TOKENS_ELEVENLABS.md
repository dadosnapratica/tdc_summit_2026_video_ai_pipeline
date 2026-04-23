# Guia de créditos e “tokens” — ElevenLabs (TTS experiments)

Documento ao nível do repositório (`docs/`). Contexto de uso: pacote `workshop/tts_experiments/` e fixtures em `workshop/fixtures/04_tts/elevenlabs/`.

Este guia consolida o que aprendemos ao gerar fixtures em `workshop/fixtures/04_tts/elevenlabs/` com o modelo **`eleven_multilingual_v2`** (texto simples e SSML via `enable_ssml_parsing`).

## Terminologia

| Termo | Significado |
|--------|-------------|
| **Caracteres** | Contagem UTF-8 do input enviado à API (`wc -m` nos ficheiros em `01_scripts/`). |
| **Créditos (dashboard)** | Unidade de quota que a ElevenLabs desconta por pedido; **não** é o mesmo que “tokens” de LLM. O erro `quota_exceeded` reporta créditos **necessários** vs **restantes**. |
| **USD / fatura** | Para TTS API, a página pública cita preço **por 1k caracteres** em modelos Multilingual (ver secção Preço). O valor na fatura final depende do plano, rollover e impostos. |

## Fixtures — contagens de caracteres (referência)

Ficheiros em `workshop/fixtures/01_scripts/`:

| Ficheiro | Caracteres (`wc -m`) |
|----------|----------------------|
| `script_cleaned.txt` | 1772 |
| `script_ssml_simple.xml` | 2119 |
| `script_ssml_advanced.xml` | 3407 |

O batch `python -m tts_experiments.scripts.generate_fixture_tts_batch --only elevenlabs` faz **6** pedidos: Carolina + Lucas × (cleaned, SSML simple, SSML advanced).

Soma de caracteres enviados (6 pedidos): **2 × (1772 + 2119 + 3407) = 14 596** caracteres.

## Créditos por pedido — valores observados na API

Com uma chave em quota baixa, a API devolve `401` com `quota_exceeded` e indica **quantos créditos aquele pedido exige**. Valores **reais** capturados para o mesmo conjunto de textos:

| Variante | Caracteres no input | Créditos exigidos (mensagem API) |
|----------|---------------------|----------------------------------|
| cleaned (plain) | 1772 | **886** |
| SSML simple | 2119 | **932** |
| SSML advanced | 3407 | **957** |

**Total para as 6 gerações (2 vozes × 3 variantes):**

`2 × (886 + 932 + 957) = 2 × 2775 =` **5550 créditos**

### Insights

1. **Texto limpo (~1772 chars):** créditos ≈ **metade** dos caracteres (886 ≈ 1772 / 2) para este modelo/contexto — útil para estimar rapidamente pedidos “plain”.
2. **SSML:** o payload é mais longo (tags, `break`, `prosody`); os créditos **não** escalam linearmente só com o texto visível — o XML completo conta.
3. **Quota de teste (ex.: 1000 créditos/mês):** um único pedido “full” de ~1,7k caracteres já pode exigir **~886** créditos; **não** cabe gerar as 6 fixtures completas sem subir plano, comprar créditos ou usar outra chave.

## Preço em dinheiro (estimativa)

- Página oficial API (Multilingual v2/v3): **~USD 0,10 por 1000 caracteres** (consultar [ElevenLabs API Pricing](https://elevenlabs.io/pricing/api); valores podem mudar).
- Estimativa linear só por caracteres:  
  `14 596 / 1000 × 0,10 ≈ **USD 1,46**` (antes de impostos; planos com caracteres incluídos podem custar **0 USD marginal** até esgotar o incluído).

## API — cotação antes do pedido?

- **Não** há endpoint documentado no nosso fluxo que devolva “este texto custará X créditos” antes do `POST`.
- **Depois do facto:** uso agregado pode ser consultado via API de utilização (ex. documentação ElevenLabs: character stats / billing), com intervalo de datas.

## Como gerar as fixtures

Na raiz do repositório `video_ai_pipeline`:

```bash
./workshop/tts_experiments/.venv/bin/python -m tts_experiments.scripts.generate_fixture_tts_batch --only elevenlabs
```
(Na raiz do repo, com `PYTHONPATH=workshop` se não usares o venv do pacote.)

- Se `elevenlabs_carolina_script_cleaned_text.mp3` já existir e não quiseres regenerar (~886 créditos):  
  `--elevenlabs-skip-carolina-cleaned` (5 ficheiros, **~4664 créditos**).

- **Texto completo:** não passar `--elevenlabs-max-chars`; garantir **≥ ~5550 créditos** disponíveis no período (ou equivalente no plano).
- **Pré-visualização curta** (menos créditos por pedido; nomes de ficheiro com sufixo `_preview`):

  ```bash
  PYTHONPATH=workshop python -m tts_experiments.scripts.generate_fixture_tts_batch --only elevenlabs --elevenlabs-max-chars 400
  ```

  Ou `ELEVENLABS_FIXTURE_MAX_CHARS=400` no `workshop/tts_experiments/.env`.

## Checklist quando `quota_exceeded`

1. Confirmar no painel ElevenLabs: **créditos restantes** e nome da chave (ex. `videostudio_experiment`).
2. Adicionar créditos / subir tier / nova chave com quota suficiente.
3. Voltar a correr o comando acima (sem limite para saídas finais sem `_preview`).

---

*Última atualização: análise alinhada aos fixtures em `01_scripts/` e respostas de erro `quota_exceeded` da API ElevenLabs (modelo `eleven_multilingual_v2`).*
