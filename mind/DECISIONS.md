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
