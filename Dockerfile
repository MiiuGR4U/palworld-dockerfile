# syntax=docker/dockerfile:1.7
ARG DEPOT_DOWNLOADER_VERSION=3.4.0

# Native ARM64 install tools, baked into the final image.
FROM --platform=$TARGETPLATFORM alpine:3.22 AS tools
ARG DEPOT_DOWNLOADER_VERSION

RUN apk add --no-cache ca-certificates curl unzip tar

RUN mkdir -p /out/depotdownloader /out/steamcmd \
 && curl -fL --retry 5 --retry-delay 2 \
    "https://github.com/SteamRE/DepotDownloader/releases/download/DepotDownloader_${DEPOT_DOWNLOADER_VERSION}/DepotDownloader-linux-arm64.zip" \
    -o /tmp/depotdownloader.zip \
 && unzip -q /tmp/depotdownloader.zip -d /out/depotdownloader \
 && chmod 0755 /out/depotdownloader/DepotDownloader \
 && curl -fL --retry 5 --retry-delay 2 \
    "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" \
    -o /tmp/steamcmd.tar.gz \
 && tar -xzf /tmp/steamcmd.tar.gz -C /out/steamcmd \
 && chmod 0755 /out/steamcmd/steamcmd.sh

# Keep all of Supersunho's ARM64/FEX/Palworld Python manager stack.
FROM supersunho/palworld-server:latest-arm64

USER root

COPY --from=tools /out/depotdownloader /opt/depotdownloader
COPY --from=tools /out/steamcmd /opt/steamcmd-seed
COPY --chmod=0755 pterodactyl-entrypoint.sh /pterodactyl-entrypoint.sh

# IMPORTANT:
# We do NOT call /entrypoint.sh from the upstream image at runtime.
# That script hardcodes /home/steam in setup_permissions(), which cannot work
# under Wings' non-root runtime.
ENV SERVER_DIR=/home/container \
    BACKUP_DIR=/home/container/backups \
    LOG_DIR=/home/container/logs \
    STEAMCMD_DIR=/home/container/.steamcmd \
    FEX_ROOTFS_PATH=/opt/fex-rootfs

WORKDIR /home/container

ENTRYPOINT ["/pterodactyl-entrypoint.sh"]
CMD ["--start-server"]
