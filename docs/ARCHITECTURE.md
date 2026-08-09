# Architecture Overview — Palworld ARM64 for Pterodactyl

## High-Level Execution Stack

```text
+-------------------------------------------------------------+
|                     Pterodactyl Wings                       |
|          (Runs container under non-root UID:GID)            |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                Custom Docker Image (ARM64)                  |
|    Base: supersunho/palworld-server:latest-arm64             |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                         FEX-Emu                             |
|          Fast x86_64 Binary Emulation for ARM64             |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                     Embedded RootFS                         |
|                Ubuntu 24.04 LTS (x86_64)                    |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Palworld Dedicated Server                      |
|                Linux x86_64 (AppID 2394010)                 |
+-------------------------------------------------------------+
```

## Key Components

1. **Pterodactyl Wings**:
   - Manages non-root execution container runtime.
   - Restricts writable disk access exclusively to `/home/container`.
   - Injects environment variables (`SERVER_PORT`, `SERVER_IP`, `SERVER_MEMORY`, `SERVER_UUID`).

2. **Native DepotDownloader ARM64**:
   - Placed at `/opt/depotdownloader/DepotDownloader`.
   - Used during server installation phase (`/mnt/server`) to pull x86_64 Palworld files without package manager overhead or emulation performance hits.

3. **SteamCMD Seed**:
   - Placed at `/opt/steamcmd-seed`.
   - Automatically copied into `/home/container/.steamcmd` on first boot for runtime update management.

4. **FEX-Emu & RootFS**:
   - Embedded RootFS located at `/opt/fex-rootfs/Ubuntu_24_04`.
   - Runtime configured via `FEX_ROOTFS` environment variable.
   - User configuration stored in `/home/container/.fex-emu/Config.json`.

5. **Process Manager**:
   - Python-based server manager from Supersunho invoked via `cd /app && exec python -m src.server_manager`.
