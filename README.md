# Palworld ARM64 para Pterodactyl / Hydrodactyl

## Recomendado: build pelo GitHub Actions

1. Crie um repositório novo, por exemplo `palworld-arm64-pterodactyl`.
2. Envie TODO o conteúdo deste ZIP para a raiz do repositório.
3. Faça push na branch `main`.
4. Abra `Actions` e aguarde `Build ARM64 Pterodactyl Image`.
5. A imagem ficará em:

   `ghcr.io/SEU_USUARIO_EM_MINUSCULO/palworld-arm64-pterodactyl:latest`

6. No GitHub, abra o Package criado e mude a visibilidade para **Public**.
7. Abra `egg-palworld-arm64-custom-image.json`.
8. Substitua AS DUAS ocorrências de:

   `ghcr.io/your-github-user/palworld-arm64-pterodactyl:latest`

   pela sua imagem real.

9. Importe o egg no Hydrodactyl.
10. Crie/recrie o servidor e clique em **Reinstall**.

## Build manual na VPS ARM64

Login no GHCR:

```bash
echo "SEU_GITHUB_PAT" | docker login ghcr.io -u SEU_USUARIO --password-stdin
```

Build:

```bash
docker build \
  --platform linux/arm64 \
  -t ghcr.io/seu_usuario/palworld-arm64-pterodactyl:latest \
  .
```

Push:

```bash
docker push ghcr.io/seu_usuario/palworld-arm64-pterodactyl:latest
```

Depois deixe o Package público e altere o JSON do egg.

## O que esta imagem corrige

O upstream Supersunho assume `/home/steam`, mas Wings roda o processo sem root.

Na imagem customizada:

- `/home/steam/palworld_server` -> `/home/container`
- `/home/steam/backups` -> `/home/container/backups`
- `/home/steam/logs` -> `/home/container/logs`
- `/home/steam/steamcmd` -> `/home/container/.steamcmd`
- `/home/steam/Steam` -> `/home/container/Steam`

O wrapper cria os destinos graváveis ANTES do entrypoint original rodar.

O FEX, RootFS Ubuntu x86_64 e manager continuam sendo os do Supersunho.

## Installer

O installer não executa `apt` ou `dpkg`.

DepotDownloader ARM64 e o bootstrap do SteamCMD já estão dentro da imagem.

Fluxo esperado:

```text
[1/5] Checking ARM64 environment
[2/5] Preparing Pterodactyl server volume
[3/5] Installing Palworld Dedicated Server
[4/5] Seeding writable SteamCMD
[5/5] Final verification
Installation completed...
```

## Primeiro boot

Deve começar com:

```text
[PTERO-ARM64] Preparing writable Wings filesystem...
[PTERO-ARM64] UID:GID=... ARCH=aarch64
```

e depois:

```text
=== Palworld Server Entrypoint ===
Architecture: aarch64
...
```

Se falhar, envie o log desde a primeira linha `[PTERO-ARM64]`.
