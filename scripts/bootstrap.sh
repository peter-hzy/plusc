#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: ./scripts/bootstrap.sh <workspace>" >&2
  exit 2
fi

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3.11 -m venv "$REPO_ROOT/.venv"
"$REPO_ROOT/.venv/bin/python" -m pip install -e "$REPO_ROOT[excel]"
"$REPO_ROOT/.venv/bin/inbound-leads" doctor
"$REPO_ROOT/.venv/bin/inbound-leads" init --workspace "$1"

