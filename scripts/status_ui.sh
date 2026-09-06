#!/bin/sh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
exec "$ROOT/cmc" dashboard "$@"
