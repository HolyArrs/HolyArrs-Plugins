#!/usr/bin/env bash
# Hands the build job's output to the sign job without trusting it.
#   artifact.sh links DIR      fail on any link, special file or hard-linked file under DIR
#                              (.git is skipped)
#   artifact.sh sums DIR       write DIR/SHA256SUMS over every file and print its sha256
#   artifact.sh verify DIR SHA DIR/SHA256SUMS must have sha256 SHA, list exactly the
#                              files in DIR (nothing more, nothing less) and match them all
#   artifact.sh paths DIR ID VERSION
#                              fail on any file outside bin/<platform>/plugin, meta/, source/ID/VERSION.tar.xz,
#                              and site/images/ID/icon-{128,256}.webp (no developer pictures)
set -euo pipefail
cmd=${1:?command}; dir=${2:?dir}
[ -d "$dir" ] || { echo "$dir is not a folder"; exit 1; }
cd "$dir"

list() { find . -path ./.git -prune -o -type f ! -name SHA256SUMS -print | LC_ALL=C sort; }

case "$cmd" in
links)
  bad=$(find . -path ./.git -prune -o \( -type l -o \( ! -type f ! -type d \) -o \( -type f -links +1 \) \) -print)
  [ -z "$bad" ] || { echo "links or special files are not allowed:"; echo "$bad"; exit 1; }
  echo "no links or special files" ;;
sums)
  list | while IFS= read -r f; do sha256sum -- "$f"; done > SHA256SUMS
  sha256sum SHA256SUMS | cut -d' ' -f1 ;;
verify)
  want=${3:?sha256 of SHA256SUMS}
  [[ "$want" =~ ^[0-9a-f]{64}$ ]] || { echo "bad sha256"; exit 1; }
  [ -f SHA256SUMS ] && [ ! -L SHA256SUMS ] || { echo "SHA256SUMS missing"; exit 1; }
  got=$(sha256sum SHA256SUMS | cut -d' ' -f1)
  [ "$got" = "$want" ] || { echo "SHA256SUMS is $got, the build job said $want"; exit 1; }
  bad=$(find . \( -type l -o \( ! -type f ! -type d \) -o \( -type f -links +1 \) \) -print)
  [ -z "$bad" ] || { echo "links or special files in the artifact:"; echo "$bad"; exit 1; }
  diff <(list) <(cut -c67- SHA256SUMS | LC_ALL=C sort) || { echo "file list differs from SHA256SUMS"; exit 1; }
  sha256sum --strict --quiet -c SHA256SUMS
  echo "all $(wc -l < SHA256SUMS) files match" ;;
paths)
  id=${3:?id}; ver=${4:?version}
  [[ "$id" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]] || { echo "bad id"; exit 1; }
  [[ "$ver" =~ ^[0-9A-Za-z.+-]{1,32}$ ]] || { echo "bad version"; exit 1; }
  declare -A ok=([./SHA256SUMS]=1 ["./source/$id/$ver.tar.xz"]=1 ["./site/images/$id/icon-128.webp"]=1 ["./site/images/$id/icon-256.webp"]=1)
  bad=0
  while IFS= read -r f; do
    if [ -n "${ok[$f]:-}" ] || [[ "$f" =~ ^\./bin/linux-[a-z0-9-]+/plugin$ ]] || [[ "$f" == ./meta/* ]]; then continue; fi
    echo "not allowed in the artifact: $f"; bad=1
  done < <(find . -type f | LC_ALL=C sort)
  [ "$bad" = 0 ] || exit 1
  echo "artifact paths ok" ;;
*) echo "unknown command $cmd"; exit 2 ;;
esac
