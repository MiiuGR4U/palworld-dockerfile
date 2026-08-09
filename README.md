# PATCH v2 — Palworld ARM64 / Pterodactyl

## O erro corrigido

A v1 ainda executava o entrypoint original do Supersunho:

```bash
exec /entrypoint-upstream.sh "$@"
```

O entrypoint original SEMPRE chama `setup_permissions()` e essa função possui
`/home/steam/...` hardcoded.

No Wings o runtime é não-root, então isso termina em:

```text
mkdir: cannot create directory '/home/steam': Permission denied
```

## O que a v2 faz

A v2 NÃO executa mais o entrypoint original.

Ela usa diretamente:

```bash
cd /app
exec python -m src.server_manager
```

O próprio manager do Supersunho usa os paths configuráveis:

```text
SERVER_DIR=/home/container
BACKUP_DIR=/home/container/backups
LOG_DIR=/home/container/logs
STEAMCMD_DIR=/home/container/.steamcmd
```

Também criamos:

```text
/home/container/.fex-emu/Config.json
```

apontando diretamente para o RootFS já embutido em:

```text
/opt/fex-rootfs/...
```

Assim FEX também não depende do home do usuário `steam`.

## O que fazer

Se este ZIP estiver sendo usado para atualizar o repositório EXISTENTE:

1. Substitua no GitHub:
   - `Dockerfile`
   - `pterodactyl-entrypoint.sh`
   - `.github/workflows/build.yml`

2. Faça commit/push na `main`.

3. Aguarde o GitHub Actions ficar verde.

4. Confira que foi publicada:
   `ghcr.io/miiugr4u/palworld-arm64-pterodactyl:v2`

   e também atualizada:
   `ghcr.io/miiugr4u/palworld-arm64-pterodactyl:latest`

5. No Pterodactyl/Hydrodactyl:
   - NÃO precisa trocar de URL se já usa `:latest`.
   - faça `Reinstall` para testar o installer.
   - depois Start.

Se quiser evitar cache/tag, pode importar `egg-palworld-arm64-v2.json`
ou trocar temporariamente a imagem para:

`ghcr.io/miiugr4u/palworld-arm64-pterodactyl:v2`

## Log esperado no boot

Agora deve começar:

```text
[PTERO-ARM64/v2] Wings-native Palworld bootstrap
[PTERO-ARM64/v2] UID:GID=999:987 ARCH=aarch64
[PTERO-ARM64/v2] SERVER_DIR=/home/container
[PTERO-ARM64/v2] STEAMCMD_DIR=/home/container/.steamcmd
[PTERO-ARM64/v2] FEX RootFS=/opt/fex-rootfs/...
[PTERO-ARM64/v2] Starting Supersunho manager WITHOUT upstream entrypoint...
```

NÃO deve mais aparecer:

```text
[INFO] === Palworld Server Entrypoint ===
[INFO] Setting up directory permissions...
mkdir: cannot create directory '/home/steam'
```

Depois o Python manager deve seguir para:

```text
Downloading/updating server files...
Generating server settings...
Starting Palworld server...
```

Se falhar, envie todo o log desde `[PTERO-ARM64/v2]`.
