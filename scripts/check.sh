#!/usr/bin/env bash
# Full local gate: lint, format, types, unit tests. Fails on the first problem.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q -m "not golden and not network" "$@"
