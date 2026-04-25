#!/bin/zsh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
python3 "$ROOT/scripts/configure.py"
