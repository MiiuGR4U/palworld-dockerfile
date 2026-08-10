# Lua Mods

Estado: `EXPERIMENTAL` no backend Linux x86_64/FEX.

Upload:

```text
/home/container/mods/lua/ModName/
├── mod.json
└── scripts/
    └── main.lua
```

O source exige exatamente `scripts/main.lua` com case correto. O deployment adapta para o diretório `Mods/<id>/Scripts/main.lua` esperado pelo loader pinado e atualiza somente o bloco gerenciado de `Mods/mods.txt`. Validação nunca executa Lua.

## Ordem de testes

1. Vanilla com o personagem existente.
2. UE4SS sem mods e teste completo de GUID/save.
3. Restart e reconexão sem mods.
4. Lua mínimo: `print('[palmodctl] Lua Hello World')`.
5. Somente depois, um mod real.

## Better Base Range

Não é baixado nem instalado automaticamente. Após passar os quatro passos acima, faça backup, envie o diretório do mod e valide raio funcional, inventário, guild, bases e persistência após restart. Um cliente sem mod pode continuar exibindo o círculo visual vanilla mesmo quando o raio funcional é server-side.

Scripts escritos especificamente para UE4SS Windows podem depender de APIs ou binários ausentes no port Linux.
