# Technical Decisions & Rationale — Palworld ARM64

## Architectural Decisions

### 1. Why FEX-Emu over Box64 / Box32 / QEMU
- **Decision**: Use FEX-Emu with pre-baked Ubuntu 24.04 RootFS (`/opt/fex-rootfs/Ubuntu_24_04`).
- **Rationale**: Palworld Dedicated Server requires high multithreaded performance and specific x86_64 glibc features. FEX-Emu provides superior JIT caching and static register allocation stability on ARM64 compared to Box64 for this specific workload.

### 2. Why DepotDownloader ARM64 for Installation
- **Decision**: Download App ID `2394010` during installation using native ARM64 DepotDownloader binary.
- **Rationale**: SteamCMD inside ARM64 container requires x86_64 emulation for downloading, which increases installation time and failure rates. DepotDownloader executes natively on ARM64 without emulation overhead.

### 3. Why `/home/container` Storage Isolation
- **Decision**: Direct all mutable runtime paths (`SERVER_DIR`, `LOG_DIR`, `BACKUP_DIR`, `STEAMCMD_DIR`, `FEX_APP_CONFIG_LOCATION`, `XDG_*`, `TMPDIR`) exclusively to `/home/container`.
- **Rationale**: Pterodactyl Wings mounts `/home/container` as the sole writable volume for non-root containers. Any writes to `/home/steam` or `/root` fail with `Permission denied`.

### 4. Why `USE_AUTH=false` by Default
- **Decision**: Keep Steam authentication disabled (`bUseAuth=false`) by default for ARM64.
- **Rationale**: Steam AppTicket validation relies on native `steamclient.so` IPC calls through FEX emulation, which causes players to be kicked with `Invalid AppTicket`. Disabling Steam auth allows seamless connections while preserving server password security.

### 5. Why `SERVER_PORT` is Automatic
- **Decision**: Derive `-port=${SERVER_PORT}` automatically from the Pterodactyl primary allocation.
- **Rationale**: Manual port settings lead to mismatches between Pterodactyl Wings port forwards and Palworld listening ports, causing connection timeouts.

### 6. Why `QUERY_PORT` Needs a Separate Allocation
- **Decision**: Keep `QUERY_PORT` configurable (default 27018) and document that an extra UDP allocation is required for Steam server browser visibility.
- **Rationale**: Pterodactyl cannot automatically map secondary allocations to specific application functions without explicit configuration.

### 7. Why the Upstream Entrypoint Remains Bypassed
- **Decision**: Do not call the Supersunho `/entrypoint.sh` from Wings runtime.
- **Rationale**: Its permission bootstrap creates and changes ownership under `/home/steam` and assumes root/gosu. Wings supplies a non-root UID/GID and only `/home/container` is persistent and writable.

### 8. Why the Linux PalServer Backend Remains Primary
- **Decision**: Keep `ARM64 -> FEX -> Linux x86_64 PalServer` as the only implemented backend.
- **Rationale**: It is the production-tested baseline. A Windows server through Wine/Proton would materially change startup, compatibility, performance, and save-risk characteristics and is deferred.

### 9. Why Mods Use `/home/container/mods` as Source of Truth
- **Decision**: User mod inputs and manager state will live under `/home/container/mods`; game and UE4SS paths are deployment targets only.
- **Rationale**: Updates/reinstalls can replace deployment targets. A persistent source tree allows deterministic redeployment, inventory, rollback, and safe mode without deleting user uploads.

### 10. Why UE4SS Is Optional and Off by Default
- **Decision**: `MODS_ENABLED=false` must inject no loader or preload. UE4SS may be activated only for enabled Blueprint, Lua, or C++ categories after validation and backup.
- **Rationale**: Patch Paks do not inherently require UE4SS, and Palworld dedicated-server reports include player GUID/save identity risks when UE4SS is introduced.

### 11. Why Windows DLLs Are Rejected
- **Decision**: The C++ backend accepts only Linux x86_64 ELF shared objects (`.so`). `.dll` and PE binaries are quarantined or rejected without execution.
- **Rationale**: The guest process is Linux x86_64 under FEX. Renaming a Windows DLL cannot make it a Linux shared object, and native mod code runs with the server user's permissions.

### 12. Why Scanning Is Static
- **Decision**: `palmodctl scan` and `validate` inspect names, manifests, structure, hashes, and binary headers only.
- **Rationale**: Executing imports, scripts, or native initialization during discovery would turn an administrative inventory operation into arbitrary code execution.

### 13. Why Save Rollback Is Explicit
- **Decision**: A mod rollback restores deployment state by default; save/config restoration requires an explicit operator option.
- **Rationale**: Automatically replacing saves after a mod error could roll back legitimate player progress and compound an incident.

### 14. Why Loader Versions Belong in the Image
- **Decision**: UE4SS Linux must be pinned and installed during image build, with version/checksum metadata. Startup never downloads `latest`.
- **Rationale**: Loader drift is unsafe after Palworld updates and runtime downloads weaken reproducibility and supply-chain control.
