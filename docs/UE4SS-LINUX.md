# UE4SS Linux no backend FEX

Estado: `EXPERIMENTAL` até os gates reais de identidade/save.

## Versão pinada

- Fonte: `BlackBookOfficial/ue4ss-linux-palworld`.
- Release: `v1.0.2-palworld-linux`.
- Commit: `4bf136e55d7773db5e21e0ee2b9b93c0a08937e1`.
- Archive SHA256: `9c472b62a633877acddf2dcaf61826583f0d50b2c4e11723c71da5a4ea81abd9`.
- Build upstream: Ubuntu 24.04 x86_64, GCC 13.3.

O loader é baixado somente no build da imagem. Startup não consulta `latest` e não baixa código.

## Preload guest-only

```text
manager ARM64
  -> FEXBash shim ARM64
  -> reconhece somente o comando PalServer.sh
  -> FEXBash real
  -> LD_PRELOAD=/home/container/libUE4SS.so no guest x86_64
  -> PalServer x86_64
```

SteamCMD, preflight e outros processos FEX passam pela shim sem preload. Não existe `ENV LD_PRELOAD` nem export global no ambiente ARM64.

## Preflight

Antes do deployment, `palmodctl` exige `libUE4SS.so` ELF64 x86-64, `UE4SS-settings.ini`, `MemberVariableLayout.ini`, `version.json` e componentes Blueprint quando necessários. `MODS_STRICT_VERSION_CHECK=true` recusa uma build de jogo não comprovada pela metadata.

## Gate obrigatório de Player GUID

Use uma cópia não produtiva dos saves. Antes de ligar UE4SS, registre SteamID, PlayerUID/GUID, nome do save, guild, level, inventário e bases. Defina `MODS_ENABLED=true`, `MODS_UE4SS_TEST_MODE=true` e mantenha Blueprint/Lua/C++ desligados. Entre, compare, reinicie, reconecte e compare de novo.

Se qualquer identidade mudar: habilite Safe Mode, preserve logs/estados, execute rollback somente com decisão explícita e marque a combinação Palworld/loader/backend como incompatível. Não prossiga para Lua, Blueprint, C++ ou Better Base Range.

O backend Windows futuro (`FEX -> Wine/Proton -> Windows PalServer -> Windows UE4SS`) pode ampliar compatibilidade com DLLs, mas não é implementado neste projeto.
