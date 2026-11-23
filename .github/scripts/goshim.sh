#!/usr/bin/env bash
# Stands in for "go" in the sign job, so publish.py never compiles anything there.
# It answers "go build ... -o DEST ." by copying the build job's checked file for
# GOOS/GOARCH/GOARM from $PREBUILT/<platform>/plugin. Anything else fails.
set -euo pipefail
[ "${1:-}" = build ] || { echo "goshim: only go build is allowed here" >&2; exit 1; }
dest=
while [ $# -gt 0 ]; do
  [ "$1" = -o ] && { dest=${2:?}; shift; }
  shift
done
[ -n "$dest" ] || { echo "goshim: no -o" >&2; exit 1; }
case "${GOOS:-}/${GOARCH:-}/${GOARM:-}" in
  linux/amd64/) plat=linux-amd64 ;;
  linux/arm64/) plat=linux-arm64 ;;
  linux/arm/7) plat=linux-arm-v7 ;;
  *) echo "goshim: unknown target ${GOOS:-}/${GOARCH:-}/${GOARM:-}" >&2; exit 1 ;;
esac
src="${PREBUILT:?}/$plat/plugin"
[ -f "$src" ] && [ ! -L "$src" ] || { echo "goshim: $src missing" >&2; exit 1; }
cp -- "$src" "$dest"
