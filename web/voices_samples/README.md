# Amostras de voz (Compor vídeo)

Ficheiros servidos como estáticos: `/static/voices_samples/{kokoro|piper}/{nome}.mp3`

- **Kokoro:** `kokoro/{voice_id}.mp3` (ex.: `pf_dora.mp3`)
- **Piper:** `piper/{stem_do_onnx}.mp3` (ex.: `pt_BR-faber-medium.mp3`)

Texto gravado: `Olá, eu sou a voz {nome}.`

Geração na raiz do repositório:

```bash
python scripts/generate_voice_samples.py
```

Requer `ffmpeg` no PATH, variáveis Kokoro/Piper no `.env` e modelos Piper descobertos por `PIPER_VOICES_DIR` / `PIPER_MODEL`.
