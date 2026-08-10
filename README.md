# Palworld ARM64 para Pterodactyl/Hydrodactyl

Imagem e Egg para executar o Palworld Dedicated Server Linux x86_64 em nós ARM64 através do FEX-Emu, sem root, privileged, FUSE, Wine, Proton, QEMU, Box64 ou Box32 no runtime.

O baseline funcional permanece:

```text
Wings ARM64 -> container non-root -> manager Supersunho -> FEX -> PalServer Linux x86_64
```

O sistema de mods é opt-in. Com `MODS_ENABLED=false`, nenhum loader ou `LD_PRELOAD` é injetado. A porta do jogo sempre vem da Primary Allocation (`SERVER_PORT`); `QUERY_PORT` usa uma allocation UDP extra.

## Estado de suporte

| Tipo | Estado | Observação |
| --- | --- | --- |
| Patch Pak | Implementado; gate runtime pendente | `.pak` ou trio `.pak/.utoc/.ucas`; requisito de cliente depende do mod |
| Blueprint | EXPERIMENTAL | UE4SS Linux + BP loader; hooks podem variar por build |
| Lua | EXPERIMENTAL | UE4SS Linux; scripts Windows-specific podem não funcionar |
| C++ | EXPERIMENTAL/limitado | Apenas ELF x86_64 `.so` em Linux |
| Windows DLL | UNSUPPORTED | Rejeitada explicitamente |

Não declare “full mod support” até a matriz ARM64/FEX, GUID e integridade de saves estar completa.

## Início rápido

1. Importe `egg-palworld-arm64.json`.
2. Escolha uma Primary Allocation UDP para o jogo.
3. Opcionalmente adicione uma allocation UDP extra e configure `QUERY_PORT`.
4. Mantenha `USE_AUTH=false` no backend ARM64/FEX.
5. Instale e inicie vanilla antes de habilitar mods.
6. Leia [docs/MODS.md](docs/MODS.md) e [docs/UE4SS-LINUX.md](docs/UE4SS-LINUX.md) antes da primeira ativação de UE4SS.

## Validação local

```bash
python scripts/validate_egg.py
python scripts/validate-shell.py
python scripts/test_ini_preservation.py
python -m unittest discover -s tests -v
bash tests/test_entrypoint.sh
bash tests/test_fex_wrapper.sh
```

Arquitetura e auditoria do baseline: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [docs/BASELINE-AUDIT.md](docs/BASELINE-AUDIT.md).
