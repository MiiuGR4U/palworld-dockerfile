# Sistema de Mods

## Compatibilidade

| Tipo | Loader | Linux/FEX | Cliente obrigatório | Estado |
| --- | --- | --- | --- | --- |
| Patch Pak | Unreal | Estruturalmente compatível | Depende do mod | Implementado; gate runtime pendente |
| Blueprint | UE4SS + BPModLoaderMod | Experimental | Depende do mod | EXPERIMENTAL |
| Lua | UE4SS Linux | Experimental | Depende do script | EXPERIMENTAL |
| C++ | UE4SS Linux | Experimental | Depende do módulo | EXPERIMENTAL/limitado |
| Windows DLL | Windows UE4SS | Incompatível | — | UNSUPPORTED |

Suporte estrutural significa que o scanner, a validação e o deployment conhecem o formato. Não significa que qualquer mod daquele tipo funciona na build atual do Palworld.

## Source of truth

```text
/home/container/mods/
├── patch/
├── blueprint/
├── lua/
├── cpp/
├── configs/
├── disabled/
├── quarantine/
├── manifests/
├── state/
├── cache/
└── backups/
```

Os diretórios do jogo e `/home/container/Mods` são targets gerenciados. Não são a fonte dos uploads. Updates e Safe Mode podem limpar cópias gerenciadas sem apagar `mods/`.

## Feature flags

- `MODS_ENABLED=false`: baseline vanilla; sem loader/preload.
- `MODS_SAFE_MODE=false`: botão de emergência. Quando `true`, remove apenas deployment gerenciado, preserva fontes e inicia vanilla.
- `MODS_SERVER_SIDE_ONLY=true`: rejeita `client_required=true`; compatibilidade não documentada gera warning por padrão.
- `MODS_BACKUP_ON_CHANGE=true`: backup quando o SHA256 do inventário muda.
- `MODS_FAIL_ON_ERROR=true`: impede startup modded após erro comprovado.
- `ENABLE_PATCH_MODS=true`.
- `ENABLE_BLUEPRINT_MODS=false`.
- `ENABLE_LUA_MODS=false`.
- `ENABLE_CPP_MODS=false`.
- `MODS_STRICT_VERSION_CHECK=false`: quando habilitado, UE4SS exige correspondência comprovável de build.
- `MODS_UE4SS_TEST_MODE=false`: carrega o loader pinado sem mods de usuário para o gate obrigatório de identidade.

Todos os booleanos do Egg são strings Hydrodactyl: `required|string|in:true,false`.

## Manifesto opcional

```json
{
  "id": "better-base-range",
  "name": "Better Base Range",
  "type": "lua",
  "enabled": true,
  "server_side": true,
  "client_required": false,
  "client_optional": true,
  "priority": 100,
  "requires": ["ue4ss-linux"]
}
```

O manifesto não substitui inspeção dos arquivos. ID, tipo, booleans, plataforma, payload e dependências são validados.

## Load order

Menor `priority` carrega primeiro. Empates são ordenados por ID e tipo. A lista final é impressa no startup. Conflitos declarados produzem aviso; `palmodctl` não escolhe um vencedor arbitrariamente.

## Comandos

```bash
/opt/palworld-mod-runtime/palmodctl scan
/opt/palworld-mod-runtime/palmodctl list
/opt/palworld-mod-runtime/palmodctl validate
/opt/palworld-mod-runtime/palmodctl doctor
/opt/palworld-mod-runtime/palmodctl deploy
/opt/palworld-mod-runtime/palmodctl status
/opt/palworld-mod-runtime/palmodctl enable MOD_ID
/opt/palworld-mod-runtime/palmodctl disable MOD_ID
/opt/palworld-mod-runtime/palmodctl quarantine MOD_ID "motivo"
/opt/palworld-mod-runtime/palmodctl quarantine MOD_ID --clear
```

Scan e validação são estáticos: nenhum `.lua`, `.so`, `.dll` ou código de mod é executado.
