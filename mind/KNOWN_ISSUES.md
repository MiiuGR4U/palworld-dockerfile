# Known Issues & Troubleshooting History — Palworld ARM64

## Historical Issues & Solutions

### 1. `mkdir: cannot create directory '/home/steam': Permission denied`
- **Root Cause**: Base image entrypoint (`/entrypoint.sh`) executed `setup_permissions()` trying to modify `/home/steam`.
- **Solution**: Bypassed upstream entrypoint in `Dockerfile` and invoked Python server manager directly from `/pterodactyl-entrypoint.sh`.

### 2. `Current RootFS path set to '' / RootFS path doesn't exist`
- **Root Cause**: `FEX_ROOTFS_PATH` was set instead of `FEX_ROOTFS`, which FEX-Emu guest bootstrap requires.
- **Solution**: Set `export FEX_ROOTFS="${ROOTFS_DIR}"` pointing to `/opt/fex-rootfs/Ubuntu_24_04` and auto-generated `/home/container/.fex-emu/Config.json`.

### 3. `kicked by AUTH. Error: Invalid AppTicket`
- **Root Cause**: `bUseAuth=True` combined with x86_64 `steamclient.so` under FEX emulation causes Steam ticket validation failure upon client handshake.
- **Solution**: Keep `USE_AUTH=false` as default Egg setting for ARM64 deployment.

### 4. `ca-certificates / dpkg error code (1) during installation`
- **Root Cause**: Running `apt-get` or `dpkg` inside Pterodactyl installation script under restricted non-root container permissions.
- **Solution**: Package all required tools (`DepotDownloader`, `steamcmd` seed) inside the Docker image during `docker build`.

### 5. `Palworld listening on 8211 instead of SERVER_PORT`
- **Root Cause**: Upstream server manager passed query options but omitted `-port=`.
- **Solution**: Append `-port=${GAME_PORT}` via `ADDITIONAL_SERVER_OPTIONS` in entrypoint.

### 6. Egg import failed on `HOME` variable declaration
- **Root Cause**: Declaring Pterodactyl-reserved environment variable `HOME` in Egg JSON `variables`.
- **Solution**: Remove `HOME` from Egg variables list; set `export HOME=/home/container` inside container entrypoint.

## Active risks and unresolved issues

### 7. Quiet log pipeline can weaken graceful shutdown
- **Status**: MITIGATED IN CODE / RUNTIME TEST REQUIRED.
- **Cause**: The manager is the left process of a shell pipeline and is not the entrypoint PID when `QUIET_MONITORING=true`.
- **Mitigation**: The refactored entrypoint supervises manager/helper/filter PIDs and translates `SIGTERM`/`SIGINT` into manager `SIGINT`; the filter no longer owns the pipeline exit status.
- **Required evidence**: Linux CI signal test plus an ARM64 Wings test from panel stop through manager, REST/RCON save, FEX process group, and PalServer exit.

### 8. Manual INI preservation is timing-based
- **Status**: OPEN / HIGH.
- **Cause**: The helper restores a whole-file backup after a fixed two-second delay.
- **Risk**: Race with manager generation, stale backup reuse, or loss of newly introduced settings.
- **Constraint**: Do not remove the protection until a safer transactional replacement passes regression tests.

### 9. Mutable published tags and SteamCMD seed
- **Status**: PARTIALLY MITIGATED / MEDIUM.
- **Mitigation**: The Supersunho base is pinned by OCI digest; DepotDownloader and UE4SS archives are pinned by version and SHA-256.
- **Remaining risk**: Published custom `:latest`/`:dev` tags are intentionally mutable, and Valve's SteamCMD seed URL does not expose a repository-pinned checksum.
- **Control**: Prefer immutable commit tags for rollback and treat changes to the SteamCMD seed as a build provenance event.

### 10. UE4SS player identity/save risk
- **Status**: OPEN / CRITICAL.
- **Symptoms reported in the ecosystem**: changed PlayerUID/GUID, new-character prompt, duplicated saves, refused connections.
- **Control**: Keep off by default, take a backup before first activation, run the mandatory no-mod GUID test, and stop if identity changes.

### 11. Blueprint hooks on stripped Linux binaries
- **Status**: OPEN / EXPERIMENTAL.
- **Cause**: Dedicated Linux binaries may lack symbols or require build-specific address resolution.
- **Control**: Never report Blueprint mods active when the loader/hook preflight is unresolved.

### 12. Windows DLL mods
- **Status**: UNSUPPORTED on the current backend.
- **Message**: Windows DLL detected. Current backend: Linux x86_64 under FEX. Required: Linux x86_64 `.so`.

### 13. Update semantics are unclear
- **Status**: OPEN.
- **Cause**: The Egg exposes `UPDATE_ON_START=true`, while the audited upstream manager skips SteamCMD if `PalServer.sh` exists unless `FORCE_UPDATE=true`.
- **Required evidence**: Integration test against the exact pinned image version.

### 14. RootFS selection ambiguity
- **Status**: MITIGATED IN CODE / IMAGE TEST REQUIRED.
- **Mitigation**: The entrypoint prefers `/opt/fex-rootfs/Ubuntu_24_04`; without it, exactly one valid candidate is accepted and multiple candidates fail closed.
- **Required evidence**: Confirm the pinned image contains the expected RootFS and completes FEX preflight on ARM64.
