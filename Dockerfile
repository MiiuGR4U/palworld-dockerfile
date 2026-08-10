# syntax=docker/dockerfile:1.7
ARG DEPOT_DOWNLOADER_VERSION=3.4.0
ARG DEPOT_DOWNLOADER_SHA256=d9fb612ccebc1db8eeea3b4045d2221ec70431381393ce908fb72f01d4f9c812
ARG UE4SS_VERSION=v1.0.2-palworld-linux
ARG UE4SS_ARCHIVE_SHA256=9c472b62a633877acddf2dcaf61826583f0d50b2c4e11723c71da5a4ea81abd9
ARG PALWORLD_BASE_IMAGE=supersunho/palworld-server:latest-arm64@sha256:8a396f03c98f0c476275499b1ff663d7208286f37ded0c0446e7c0495c79a285

# ------------------------------------------------------------------------------
# Stage 1: Build Tools & Native Binaries
# ------------------------------------------------------------------------------
FROM --platform=$TARGETPLATFORM alpine:3.22 AS tools
ARG DEPOT_DOWNLOADER_VERSION
ARG DEPOT_DOWNLOADER_SHA256
ARG UE4SS_VERSION
ARG UE4SS_ARCHIVE_SHA256
ARG TARGETARCH

RUN apk add --no-cache ca-certificates curl unzip tar

RUN test "${TARGETARCH}" = "arm64"

RUN mkdir -p /out/depotdownloader /out/steamcmd \
 && curl -fL --retry 5 --retry-delay 2 \
    "https://github.com/SteamRE/DepotDownloader/releases/download/DepotDownloader_${DEPOT_DOWNLOADER_VERSION}/DepotDownloader-linux-arm64.zip" \
    -o /tmp/depotdownloader.zip \
 && echo "${DEPOT_DOWNLOADER_SHA256}  /tmp/depotdownloader.zip" | sha256sum -c - \
 && unzip -q /tmp/depotdownloader.zip -d /out/depotdownloader \
 && chmod 0755 /out/depotdownloader/DepotDownloader \
 && curl -fL --retry 5 --retry-delay 2 \
    "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" \
    -o /tmp/steamcmd.tar.gz \
 && tar -xzf /tmp/steamcmd.tar.gz -C /out/steamcmd \
 && chmod 0755 /out/steamcmd/steamcmd.sh \
 && rm -rf /tmp/*

RUN mkdir -p "/out/ue4ss/${UE4SS_VERSION}" \
 && curl -fL --retry 5 --retry-delay 2 \
    "https://github.com/BlackBookOfficial/ue4ss-linux-palworld/releases/download/${UE4SS_VERSION}/ue4ss-linux-palworld-${UE4SS_VERSION}.tar.gz" \
    -o /tmp/ue4ss.tar.gz \
 && echo "${UE4SS_ARCHIVE_SHA256}  /tmp/ue4ss.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/ue4ss.tar.gz -C "/out/ue4ss/${UE4SS_VERSION}" \
 && chmod 0644 "/out/ue4ss/${UE4SS_VERSION}/libUE4SS.so" \
 && rm -f /tmp/ue4ss.tar.gz

COPY runtime/ue4ss/version.json "/out/ue4ss/${UE4SS_VERSION}/version.json"

# ------------------------------------------------------------------------------
# Stage 2: Final ARM64 Pterodactyl Runtime Image
# ------------------------------------------------------------------------------
FROM ${PALWORLD_BASE_IMAGE}
ARG UE4SS_VERSION

USER root

LABEL org.opencontainers.image.title="Palworld ARM64 Pterodactyl Runtime" \
      org.opencontainers.image.description="Non-root ARM64/FEX Palworld runtime with opt-in palmodctl" \
      io.palworld.mods.status="experimental" \
      io.palworld.ue4ss.version="v1.0.2-palworld-linux"

# Copy tools from stage 1
COPY --from=tools /out/depotdownloader /opt/depotdownloader
COPY --from=tools /out/steamcmd /opt/steamcmd-seed
COPY --chmod=0755 pterodactyl-entrypoint.sh /pterodactyl-entrypoint.sh
COPY --chmod=0755 scripts/log_filter.py /scripts/log_filter.py
COPY --chmod=0755 scripts/palworld_helper.py /scripts/palworld_helper.py
COPY modsystem /opt/palworld-mod-runtime/modsystem
COPY --chmod=0755 scripts/palmodctl /opt/palworld-mod-runtime/palmodctl
COPY --chmod=0755 scripts/FEXBash /opt/palworld-mod-runtime/bin/FEXBash
COPY --from=tools /out/ue4ss /opt/palworld-mod-runtime/ue4ss
COPY runtime/metadata/version.json /opt/palworld-mod-runtime/metadata/version.json

RUN ln -s "${UE4SS_VERSION}" /opt/palworld-mod-runtime/ue4ss/current

# Writable directory environment specifications for Pterodactyl volume
ENV SERVER_DIR=/home/container \
    BACKUP_DIR=/home/container/backups \
    LOG_DIR=/home/container/logs \
    STEAMCMD_DIR=/home/container/.steamcmd \
    PYTHONPATH=/opt/palworld-mod-runtime:/app

WORKDIR /home/container

USER steam

ENTRYPOINT ["/pterodactyl-entrypoint.sh"]
CMD ["--start-server"]
