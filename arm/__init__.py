"""Bibliotecas Python do laboratório alinhadas aos agentes ARM (CPU/I/O).

Pacotes (nomes iguais aos nós do grafo de produção):

- ``research_agent`` — pacote agregado YouTube + Trends (lab); produção: ``agents.research_agent``.
- ``script_agent`` — geração de roteiro e cenas (lab); produção: ``agents.script_agent``.
- ``asset_agent`` — busca multi-fonte por cena (lab); produção: ``agents.asset_agent``.
- ``visual_agent`` — clipe a partir de imagem (lab; ComfyUI/ffmpeg); produção: ``agents.visual_agent``.
- ``tts_agent`` — narração WAV (lab); produção: ``agents.tts_agent``.
- ``composer_agent`` — vídeo final (lab); produção: ``agents.composer_agent``.

O BFF (``workshop.bff``) e a UI estática (``workshop.web``) ficam **fora**
deste pacote.
"""
