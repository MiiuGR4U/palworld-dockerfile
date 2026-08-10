# Current State — Palworld ARM64 Pterodactyl/Hydrodactyl

Last verified: 2026-08-10

## Audited baseline

- Branch/commit: `dev` at `8686f93c26ef94bf9b359067acb5f238a1a9cab4`
- Worktree before Phase 2: clean
- Egg safety validator: PASS (real Egg plus 11 unit tests)
- Shell syntax validator: PASS (recursive discovery)
- Existing INI preservation smoke test: PASS
- Docker/ARM64 runtime test: NOT RUN on the audit workstation (Docker unavailable)
- Full audit: `docs/BASELINE-AUDIT.md`

## Functional architecture

- Host/panel: non-root Pterodactyl or Hydrodactyl Wings on ARM64/aarch64.
- Image: `ghcr.io/miiugr4u/palworld-arm64-pterodactyl:latest`.
- Base: `supersunho/palworld-server:latest-arm64` pinned to digest `sha256:8a396f03…a285` for reproducible rebuilds.
- Guest: Linux x86_64 PalServer under FEX with an Ubuntu 24.04 RootFS discovered below `/opt/fex-rootfs`.
- Persistent/mutable root: `/home/container` only.
- Installer root: `/mnt/server`.
- Initial download: native ARM64 DepotDownloader, App ID `2394010`, Linux x86_64 payload.
- Runtime manager: `cd /app && python -m src.server_manager` with the upstream entrypoint bypassed.

## Protected working behavior

- `FEX_ROOTFS` is exported and the `FEXBash` guest bootstrap preflight succeeds in the known deployment.
- `SERVER_PORT` drives `-port` and `PUBLIC_PORT`; `QUERY_PORT` is separate.
- REST `8212` and RCON `25575` remain internal by default.
- `USE_AUTH=false` avoids the observed `Invalid AppTicket` disconnect.
- Hydrodactyl booleans use `required|string|in:true,false`; reserved panel variables are not declared.
- Installer/runtime avoid package-manager operations and upstream `/home/steam` permission logic.
- Saves/configs live in the Pterodactyl persistent volume.

## Mod subsystem status

- Patch Pak: scanner/validator/transaction implemented; ARM64 runtime gate NOT RUN.
- Blueprint: structural deployment and pinned BP loader implemented; EXPERIMENTAL, runtime gate NOT RUN.
- Lua: structural deployment implemented; EXPERIMENTAL, runtime gate NOT RUN.
- C++ Linux x86_64 `.so`: ELF validation and `libs/` deployment implemented; EXPERIMENTAL/limited, runtime gate NOT RUN.
- Windows `.dll`: UNSUPPORTED and rejected, including PE renamed to `.so`.
- UE4SS Linux: `v1.0.2-palworld-linux` pin/checksum and guest-only routing implemented; GUID/save gate NOT RUN.
- `MODS_ENABLED=false` remains the required baseline behavior.

## Immediate engineering focus

The remaining work is runtime proof on an ARM64 Wings test server: vanilla regression, Linux signal propagation, UE4SS no-mod Player GUID/save comparison, then Lua/Blueprint/C++ Hello World and four-type coexistence. The fixed-delay INI guard remains an explicit risk; base/loader changes now require an explicit pin update.

## Phase results

- Phase 0–1 audit: PASS (static/local evidence; runtime limits documented).
- Phase 2 memory/docs: PASS.
- Phase 3 validation: PASS — Egg, shell, INI smoke test, and 11 Egg validator unit tests.
- Phase 4 entrypoint refactor: PASS locally — shell syntax, port derivation, duplicate-port rejection, query validation, secret redaction, and Linux-only signal test definition. ARM64/Wings runtime remains NOT RUN.
- Phases 5–7 mod core/Patch/Safe Mode/backup/rollback: PASS in unit tests.
- Phases 8, 10–13 structural UE4SS/Lua/Blueprint/C++/coexistence: PASS in unit tests; runtime compatibility remains EXPERIMENTAL/NOT RUN.
