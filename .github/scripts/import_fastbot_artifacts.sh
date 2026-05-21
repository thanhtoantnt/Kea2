#!/usr/bin/env bash
set -euo pipefail

FASTBOT_ANDROID_DIR="${FASTBOT_ANDROID_DIR:?FASTBOT_ANDROID_DIR is required}"
KEA2_REPO_DIR="${KEA2_REPO_DIR:?KEA2_REPO_DIR is required}"
FASTBOT3_REPOSITORY="${FASTBOT3_REPOSITORY:?FASTBOT3_REPOSITORY is required}"
FASTBOT3_COMMIT="${FASTBOT3_COMMIT:?FASTBOT3_COMMIT is required}"

ASSETS_DIR="$KEA2_REPO_DIR/kea2/assets"
FASTBOT_LIBS_DIR="$ASSETS_DIR/fastbot_libs"
ABIS=(armeabi-v7a arm64-v8a x86 x86_64)

copy_file() {
  local src="$1"
  local dst="$2"
  if [[ ! -f "$src" ]]; then
    echo "Required Fastbot artifact not found: $src" >&2
    exit 1
  fi
  install -D -m 0644 "$src" "$dst"
  echo "Imported $dst"
}

copy_optional_file() {
  local src="$1"
  local dst="$2"
  if [[ -f "$src" ]]; then
    install -D -m 0644 "$src" "$dst"
    echo "Imported $dst"
  else
    echo "Optional Fastbot artifact not found, skipping: $src"
  fi
}

copy_file "$FASTBOT_ANDROID_DIR/monkeyq.jar" "$ASSETS_DIR/monkeyq.jar"

if [[ -f "$FASTBOT_ANDROID_DIR/monkey/build/libs/kea2-thirdpart.jar" ]]; then
  copy_file "$FASTBOT_ANDROID_DIR/monkey/build/libs/kea2-thirdpart.jar" "$ASSETS_DIR/kea2-thirdpart.jar"
else
  copy_file "$FASTBOT_ANDROID_DIR/kea2-thirdpart.jar" "$ASSETS_DIR/kea2-thirdpart.jar"
fi

copy_optional_file "$FASTBOT_ANDROID_DIR/fastbot-thirdpart.jar" "$ASSETS_DIR/fastbot-thirdpart.jar"
copy_optional_file "$FASTBOT_ANDROID_DIR/framework.jar" "$ASSETS_DIR/framework.jar"

for abi in "${ABIS[@]}"; do
  copy_file \
    "$FASTBOT_ANDROID_DIR/libs/$abi/libfastbot_native.so" \
    "$FASTBOT_LIBS_DIR/$abi/libfastbot_native.so"
done

python3 - "$ASSETS_DIR/fastbot3-build.json" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

metadata_path = sys.argv[1]
metadata = {
    "fastbot3_repository": os.environ["FASTBOT3_REPOSITORY"],
    "fastbot3_commit": os.environ["FASTBOT3_COMMIT"],
    "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "artifacts": {
        "jars": [
            "kea2/assets/monkeyq.jar",
            "kea2/assets/kea2-thirdpart.jar",
            "kea2/assets/fastbot-thirdpart.jar",
            "kea2/assets/framework.jar",
        ],
        "native_libraries": [
            "kea2/assets/fastbot_libs/armeabi-v7a/libfastbot_native.so",
            "kea2/assets/fastbot_libs/arm64-v8a/libfastbot_native.so",
            "kea2/assets/fastbot_libs/x86/libfastbot_native.so",
            "kea2/assets/fastbot_libs/x86_64/libfastbot_native.so",
        ],
    },
}
with open(metadata_path, "w", encoding="utf-8") as output:
    json.dump(metadata, output, indent=2, sort_keys=True)
    output.write("\n")
PY
