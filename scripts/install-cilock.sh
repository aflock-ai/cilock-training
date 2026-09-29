#!/usr/bin/env bash
# Build cilock from aflock-ai/rookery source at a pinned commit into ./bin.
#
# Why source: the lesson uses flags (--material-manifest on `cilock run`,
# --offline on `cilock verify` and `cilock sign`) that are newer than the
# current packaged release. Once a release includes them, install that instead.
#
# Needs: git and Go (version from rookery's cilock/go.mod).
#   scripts/install-cilock.sh              # pinned commit
#   ROOKERY_REF=<sha> scripts/install-cilock.sh
set -euo pipefail

ROOKERY_REF="${ROOKERY_REF:-a824a9c39703ec3e3bed1904710f751bcc6104a6}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/.rookery"
EXE=""
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) EXE=.exe ;; esac

if [[ ! -d $SRC/.git ]]; then
    git clone --quiet --filter=blob:none https://github.com/aflock-ai/rookery.git "$SRC"
fi
git -C "$SRC" fetch --quiet origin "$ROOKERY_REF"
git -C "$SRC" checkout --quiet --detach "$ROOKERY_REF"

mkdir -p "$ROOT/bin"
(cd "$SRC/cilock" && CGO_ENABLED=0 go build -trimpath -o "$ROOT/bin/cilock$EXE" ./cmd/cilock)
echo "built $ROOT/bin/cilock$EXE from aflock-ai/rookery@$ROOKERY_REF"
"$ROOT/bin/cilock$EXE" version | head -1
