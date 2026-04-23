"""
Providers ("tools") de busca de assets para o experimento do asset_agent.

Cada provider expõe `search(query, cfg) -> List[Dict[str, Any]]` e devolve assets
normalizados com chaves como:
  - asset_type: "image" | "video"
  - url / preview_url
  - source / license / author / tags|text
  - width / height (quando disponível)
"""

