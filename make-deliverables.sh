#!/usr/bin/env bash
#
# make-deliverables.sh — produces the two supervisor deliverables:
#
#   1. sothema-source-code.zip  — clean source (git-tracked files only, no secrets/artifacts)
#   2. sothema-package-final.zip — turnkey deployable: saved Docker images + compose + env template
#
# Usage:   ./make-deliverables.sh
# Output:  ./deliverables/
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/deliverables"
PROJECT="sothema"
STAMP="$(date +%Y%m%d)"

rm -rf "$OUT"
mkdir -p "$OUT"

echo "==> [1/2] Source code archive (git-tracked files only)"
git -C "$ROOT" archive --format=zip \
  --prefix=sothema-ai-compliance-platform/ \
  -o "$OUT/sothema-source-code-$STAMP.zip" HEAD
echo "    written: deliverables/sothema-source-code-$STAMP.zip"

echo "==> [2/2] Final package (Docker images + compose)"
STAGE="$OUT/package"
mkdir -p "$STAGE"

echo "    building images (this can take several minutes)..."
docker compose -p "$PROJECT" -f "$ROOT/docker/docker-compose.yml" build

echo "    saving images to tarball..."
IMAGES="$(docker compose -p "$PROJECT" -f "$ROOT/docker/docker-compose.yml" config --images)"
# shellcheck disable=SC2086
docker save -o "$STAGE/sothema-images.tar" $IMAGES

cp "$ROOT/docker/docker-compose.yml" "$STAGE/docker-compose.yml"
cp "$ROOT/docker/.env.example"        "$STAGE/.env.example"

cat > "$STAGE/LOAD-ME.md" <<'EOF'
# Sothema AI Compliance Platform — Final Package

Turnkey deployable build. No source compilation needed — the Docker images are pre-built.

## Prerequisites
- Docker Desktop / Docker Engine with Compose v2

## Steps
1. Load the pre-built images:
       docker load -i sothema-images.tar

2. Create your environment file from the template and fill in the values:
       cp .env.example .env
       # edit .env — set SA_PASSWORD, AI_SERVICE_API_KEY, and your LLM provider keys

3. Start everything:
       docker compose -p sothema up -d

## Access
- Frontend ....... http://localhost:3000
- Backend API .... http://localhost:5001 (Swagger at /swagger)
- AI service ..... http://localhost:8000 (health at /api/health)
- SQL Server ..... localhost:1433

## Stop
    docker compose -p sothema down          # keep data
    docker compose -p sothema down -v       # also remove DB + FAISS volumes
EOF

echo "    bundling package zip..."
( cd "$STAGE" && zip -qr "../sothema-package-final-$STAMP.zip" . )
rm -rf "$STAGE"
echo "    written: deliverables/sothema-package-final-$STAMP.zip"

echo
echo "==> Done. Deliverables in: $OUT"
ls -lh "$OUT"
