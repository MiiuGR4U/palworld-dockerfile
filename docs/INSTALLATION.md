# Installation Guide — Palworld ARM64 for Pterodactyl / Hydrodactyl

## Prerequisites
- Pterodactyl Panel (or Hydrodactyl Panel)
- Pterodactyl Wings running on an ARM64 (`aarch64`) node (e.g., Ampere Altra, Oracle ARM, Raspberry Pi 5 8GB).

## Step-by-Step Installation

### 1. Import the Egg
1. Open your Pterodactyl Admin Panel.
2. Go to **Nests** -> **Import Egg**.
3. Select `egg-palworld-arm64.json`.
4. Associated Nest: Select **SteamCMD** or create a **Palworld** nest.
5. Click **Import**.

### 2. Create a Server
1. Go to **Servers** -> **Create New**.
2. Select your ARM64 Node.
3. Under **Egg Settings**, select **Palworld ARM64 - Pterodactyl**.
4. Assign Allocations:
   - **Primary Allocation**: Primary UDP game port (e.g., `25565/UDP` or `8211/UDP`).
   - **Additional Allocation (Recommended)**: Secondary UDP query port (e.g., `27018/UDP`).
5. Configure Server Variables:
   - Set `SERVER_NAME`, `ADMIN_PASSWORD`.
   - Ensure `USE_AUTH` is set to `false` for ARM64 compatibility.
   - If using an additional allocation for query, set `QUERY_PORT` to match that allocation's port.
6. Click **Create Server**.

### 3. Automatic Installation Process
When the server is created, Pterodactyl automatically executes the installer:
1. Validates ARM64 node architecture.
2. Prepares `/mnt/server` directory tree.
3. Invokes native ARM64 `DepotDownloader` to pull Steam App ID `2394010` (Palworld Dedicated Server).
4. Seeds writable `SteamCMD` to `/home/container/.steamcmd`.
5. Verifies executable integrity.

### 4. Starting the Server
Click **Start** in the Pterodactyl console. The server bootstrap will:
- Detect the embedded FEX RootFS.
- Run FEX guest preflight verification.
- Derive the game port automatically from `SERVER_PORT`.
- Launch Palworld.
