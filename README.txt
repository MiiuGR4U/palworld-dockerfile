PALWORLD ARM64 — FEX ROOTFS FIX
================================

O egg atual NÃO precisa mudar.

Substitua no repositório da imagem:
  Dockerfile
  pterodactyl-entrypoint.sh

Depois faça rebuild/push da MESMA tag:

docker build --platform linux/arm64 --no-cache \
  -t ghcr.io/miiugr4u/palworld-arm64-pterodactyl:latest .

docker push ghcr.io/miiugr4u/palworld-arm64-pterodactyl:latest

O conserto principal é:
  export FEX_ROOTFS=/opt/fex-rootfs/Ubuntu_24_04

O script detecta o nome real da pasta dinamicamente.

Antes de abrir o manager, agora há um teste:
  FEXBash -c 'printf "FEX guest bootstrap OK\n"'

Log esperado:
  [PTERO-ARM64] FEX_ROOTFS=/opt/fex-rootfs/Ubuntu_24_04
  [PTERO-ARM64] Testing FEX RootFS...
  FEX guest bootstrap OK
  [PTERO-ARM64] FEX preflight: OK
  [PTERO-ARM64] Starting Supersunho manager...

NÃO é necessário Reinstall do Palworld para testar esta correção de runtime.
Depois do push da nova imagem, Stop -> Start é suficiente.
