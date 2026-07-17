#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL="$ROOT_DIR/ACUSTEME_profile.xml"
ENGLISH="$ROOT_DIR/ACUSTEME_profile_EN.xml"
SCHEMA="$ROOT_DIR/profile.xsd"
TMP_ENGLISH="$(mktemp)"
trap 'rm -f "$TMP_ENGLISH"' EXIT

xmllint --noout --schema "$SCHEMA" "$CANONICAL"
xmllint --noout --schema "$SCHEMA" "$ENGLISH"

python3 - "$CANONICAL" "$TMP_ENGLISH" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding="utf-8")
generated = source.replace(
    "https://wiki.acusteme.org/it/",
    "https://wiki.acusteme.org/en/",
)
Path(sys.argv[2]).write_text(generated, encoding="utf-8")
PY

if ! cmp -s "$TMP_ENGLISH" "$ENGLISH"; then
    echo "ERROR: ACUSTEME_profile_EN.xml is stale; run tools/build_en_profile.py" >&2
    exit 1
fi

echo "OK: canonical and generated profiles are valid and synchronized"
