#!/usr/bin/env bash
# render.py가 쓰는 woff2를 npm 레지스트리에서 받아 tools/fonts/에 넣는다.
# 사용: bash tools/fetch-fonts.sh   (요구: node/npm, tar)
set -euo pipefail

TOOLS="$(cd "$(dirname "$0")" && pwd)"
DEST="$TOOLS/fonts"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"
cd "$TMP"
npm pack pretendard@1.3.9 @fontsource/ibm-plex-mono@5.0.13 >/dev/null

mkdir -p p m
cd "$TMP/p" && tar -xzf ../pretendard-1.3.9.tgz \
  package/dist/web/static/woff2/Pretendard-Regular.woff2 \
  package/dist/web/static/woff2/Pretendard-Medium.woff2 \
  package/dist/web/static/woff2/Pretendard-SemiBold.woff2 \
  package/dist/web/static/woff2/Pretendard-Bold.woff2
cd "$TMP/m" && tar -xzf ../fontsource-ibm-plex-mono-5.0.13.tgz \
  package/files/ibm-plex-mono-latin-400-normal.woff2 \
  package/files/ibm-plex-mono-latin-500-normal.woff2

cp "$TMP/p/package/dist/web/static/woff2/"*.woff2 "$DEST/"
cp "$TMP/m/package/files/"*.woff2 "$DEST/"
ls -1 "$DEST"
echo "폰트 준비 완료 → tools/fonts/"
