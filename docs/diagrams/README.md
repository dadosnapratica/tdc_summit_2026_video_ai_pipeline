# Diagramas Mermaid (fonte) e PNG (export)

- Ficheiros `.mmd` — editar aqui; são a fonte canónica.
- Ficheiros `.png` — gerados para slides e leitura offline.

Regenerar todos (exemplo):

```bash
cd workshop/docs/diagrams
for f in logical_layers physical_homelab pipeline_langgraph_order sequence_pipeline_invoke sequence_lab_bff_asset sequence_lab_bff_script; do
  npx --yes @mermaid-js/mermaid-cli@11.4.0 -i "${f}.mmd" -o "${f}.png" -w 2000 -H 1400 -b white
done
```

Ajuste `-w` e `-H` por diagrama se o texto cortar.
