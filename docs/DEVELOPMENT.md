# Developer Guide & Local Testing — Palworld ARM64

## Repository Structure

```text
.
├── Dockerfile                    # Multi-stage ARM64 Docker build
├── pterodactyl-entrypoint.sh     # Modular non-root entrypoint script
├── egg-palworld-arm64.json       # Pterodactyl / Hydrodactyl Egg manifest
├── scripts/
│   ├── validate-egg.py           # Automated Egg configuration auditor
│   └── validate-shell.py         # Cross-platform shell syntax validator
├── docs/                         # Technical documentation suite
└── mind/                         # Persistent project memory state
```

## Running Local Validations

Before submitting changes or committing to `main`/`dev` branches, run automated validations:

```bash
# 1. Audit Egg JSON configuration
python scripts/validate-egg.py

# 2. Audit Shell Script syntax
python scripts/validate-shell.py
```

## Branching Strategy

- **`main`**: Production release branch. Triggers GitHub Actions build pushing image to `:latest` and `:${SHA}`.
- **`dev`**: Active development branch. Triggers GitHub Actions build pushing image to `:dev` and `:dev-${SHA}`.

## Building Image Locally (ARM64 Node)

```bash
docker build -t palworld-arm64-pterodactyl:local .
```

## Testing Entrypoint Container Locally

```bash
docker run --rm -it \
  -e SERVER_PORT=25565 \
  -e QUERY_PORT=27018 \
  -e USE_AUTH=false \
  palworld-arm64-pterodactyl:local --shell
```
