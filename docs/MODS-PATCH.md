# Patch Pak Mods

Estado: implementação estrutural disponível; teste em PalServer ARM64/FEX ainda obrigatório por mod.

Upload:

```text
/home/container/mods/patch/ModName/
├── mod.json          # opcional
├── ModName.pak
├── ModName.utoc      # opcional, mas exige o trio completo
└── ModName.ucas      # opcional, mas exige o trio completo
```

Formatos aceitos:

- `ModName.pak` sozinho.
- `ModName.pak + ModName.utoc + ModName.ucas`.

Sidecars isolados e trios incompletos são rejeitados/quarentenados logicamente. O deployment usa nomes gerenciados em `Pal/Content/Paks/~mods/`, não sobrescreve arquivos vanilla e é idempotente.

Procedimento: upload, Stop, Start, conferir `palmodctl status`, conectar e validar o comportamento. Não assuma server-side: use o manifesto somente quando o autor documentar a compatibilidade.
