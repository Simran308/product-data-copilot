#!/usr/bin/env bash
# Clones Databricks' official agent app template into ./app and drops in this project's agent and bundle config.
# Prereqs: uv, Node 20 (nvm), Databricks CLI logged in (databricks auth login --host <workspace-url> --profile DEFAULT)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -d app ]; then
  git clone --depth 1 https://github.com/databricks/app-templates.git /tmp/app-templates-$$
  cp -R /tmp/app-templates-$$/agent-openai-agents-sdk app
  rm -rf /tmp/app-templates-$$
fi
cp agent_server/agent.py app/agent_server/agent.py
cp databricks.yml app/databricks.yml
cd app
uv python pin 3.12
echo
echo "Next:"
echo "  1. Fill in <genie-space-id>, <sql-warehouse-id> and <your-workspace-url> in app/databricks.yml"
echo "  2. cd app && uv run quickstart"
echo "  3. Append the lines from .env.example to app/.env"
echo "  4. uv run start-app   (local, http://localhost:8000)"
echo "  5. databricks bundle deploy && databricks bundle run product_data_copilot"
