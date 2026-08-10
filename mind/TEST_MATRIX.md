# Test Matrix — Palworld ARM64/FEX

Status values: `NOT RUN`, `PASS`, `FAIL`, `BLOCKED`, `NOT APPLICABLE`.

Automated static tests do not promote an experimental mod type to supported. Runtime rows require an ARM64 Wings-compatible environment and, where noted, a disposable copy of real saves.

| ID | Scenario | Required checks | Current status |
| --- | --- | --- | --- |
| A | Vanilla (`MODS_ENABLED=false`) | No deployment, no UE4SS, no `LD_PRELOAD`; join and stable runtime | NOT RUN |
| B | Patch only | Pak group validates/deploys; join behavior documented per mod | NOT RUN |
| C | UE4SS with no mods | Loader starts; no identity or save changes | NOT RUN |
| D | Lua Hello World | Static validation, deterministic deploy, expected server log | NOT RUN |
| E | Blueprint minimal | Loader/hook preflight and expected behavior | NOT RUN |
| F | C++ `.so` Hello World | ELF64 x86-64 shared object validation and expected behavior | NOT RUN |
| G | Patch + Lua | Deterministic load order, both active, stable join | NOT RUN |
| H | Patch + Blueprint + Lua | All expected loaders active, no silent skips | NOT RUN |
| I | Patch + Blueprint + Lua + C++ | Coexistence, deterministic inventory, stable restart | NOT RUN |
| J | Safe Mode after failure | Files preserved; no deploy/preload; vanilla starts | NOT RUN |
| K | Restart | Same inventory hash; no unnecessary backup/redeploy | NOT RUN |
| L | Graceful shutdown | Panel stop -> manager -> save -> PalServer exit; no early SIGKILL | NOT RUN |
| M | Palworld update | Saves/mod sources preserved; version mismatch warning | NOT RUN |
| N | Rollback | Current state preserved; deployment state restored; saves only explicitly | NOT RUN |
| O | Existing character join | Same SteamID, PlayerUID/GUID, file, guild, level, inventory, bases | NOT RUN |
| P | Save integrity | Pre/post hashes and successful reconnect/restart | NOT RUN |

## Baseline static checks

| Check | Baseline commit `8686f93` |
| --- | --- |
| Egg JSON/legacy validator | PASS |
| Shell syntax (`bash -n`) | PASS |
| Python compilation | PASS |
| INI preservation simulation | PASS |
| Patch transaction/idempotence/Safe Mode | PASS |
| UE4SS bundle/preload routing contract | PASS |
| Lua/Blueprint/C++ structural deployment | PASS |
| Four-type single transaction | PASS |
| DLL and renamed PE rejection | PASS |
| Docker build | NOT RUN — Docker unavailable on audit workstation |
| ARM64/FEX preflight | NOT RUN locally |

## Mandatory first-UE4SS identity record

Before activating UE4SS, copy the server to a non-production test target and record:

| Field | Before | UE4SS no mods | After restart |
| --- | --- | --- | --- |
| SteamID |  |  |  |
| PlayerUID/GUID |  |  |  |
| Save filename |  |  |  |
| Guild |  |  |  |
| Character level |  |  |  |
| Inventory sample |  |  |  |
| Base count/locations |  |  |  |

If any identity field changes, disable UE4SS, preserve logs and both states, perform only the explicitly approved rollback, and mark the tested backend/game/loader combination `INCOMPATIBLE`. Do not continue to Lua, Blueprint, C++, or Better Base Range.

## Better Base Range gate

1. Pass scenario A with the existing character.
2. Pass scenario C and the identity record above.
3. Pass a restart/reconnect with UE4SS and no mods.
4. Pass scenario D with a minimal Lua Hello World.
5. Back up saves/config/state.
6. Deploy Better Base Range manually from `/home/container/mods/lua/<ModName>/`.
7. Verify functional radius server-side and document that an unmodded client may still render the vanilla circle.
