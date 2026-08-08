#! /usr/bin/env bash

set -euo pipefail

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi(), indent=2))" > ../frontend/openapi.json
cd ..
bunx biome format --write frontend/openapi.json
bun run --filter frontend generate-client
find frontend/src/client -type f -name '*.ts' -exec perl -pi -e 's/[ \t]+$//' {} +
bun run --filter frontend lint:check
