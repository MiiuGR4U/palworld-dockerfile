# Mod Compatibility Memory

Última atualização: 2026-08-10.

| Categoria | Implementação | Prova local | Prova ARM64/FEX | Estado público |
| --- | --- | --- | --- | --- |
| Patch Pak | Scanner, trio, backup, transaction, clean | PASS | NOT RUN | Implementado; gate runtime pendente |
| Blueprint | LogicMods + BP loader + load order | PASS estrutural | NOT RUN | EXPERIMENTAL |
| Lua | `scripts/main.lua` + Mods/mods.txt | PASS estrutural | NOT RUN | EXPERIMENTAL |
| C++ Linux | ELF64 x86-64 ET_DYN + `libs/` | PASS estrutural | NOT RUN | EXPERIMENTAL/limitado |
| Windows DLL | Detecção/rejeição | PASS | NOT APPLICABLE | UNSUPPORTED |
| Quatro tipos juntos | Uma transação determinística | PASS estrutural | NOT RUN | EXPERIMENTAL |

UE4SS pinado: `v1.0.2-palworld-linux`. Better Base Range não foi instalado nem testado. Nenhum resultado local substitui o gate Player GUID/save.
