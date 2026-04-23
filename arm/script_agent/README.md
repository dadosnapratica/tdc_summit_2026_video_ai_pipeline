# script_agent (`workshop.arm.script_agent`)

Geração de roteiro (PT-BR) e cenas (EN), alinhada a `agents.script_agent`.

## Como rodar

```bash
python workshop/arm/script_agent/generate.py --tema "astronomia" --angulo "Mitos comuns sobre buracos negros"
```

Com Ollama (opcional):

```bash
export USE_OLLAMA=1
export OLLAMA_BASE_URL="http://192.168.15.150:11434"
export OLLAMA_MODEL="llama3"
python workshop/arm/script_agent/generate.py --tema "astronomia" --angulo "O que mudou na astronomia nos últimos 10 anos"
```
