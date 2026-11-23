#!/usr/bin/env bash
# Tests artifact.sh and goshim.sh. Run: bash .github/scripts/artifact_test.sh
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
fail() { echo "FAIL: $*"; exit 1; }

mkdir -p "$t/a/bin/linux-amd64" "$t/a/meta"
echo bin > "$t/a/bin/linux-amd64/plugin"; echo '{}' > "$t/a/meta/holyarrs-plugin.json"
bash "$here/artifact.sh" links "$t/a" >/dev/null
sum=$(bash "$here/artifact.sh" sums "$t/a")
bash "$here/artifact.sh" verify "$t/a" "$sum" >/dev/null || fail "good artifact rejected"

cp -r "$t/a" "$t/b"; echo evil > "$t/b/bin/linux-amd64/plugin"
! bash "$here/artifact.sh" verify "$t/b" "$sum" >/dev/null 2>&1 || fail "changed file passed"
cp -r "$t/a" "$t/c"; echo extra > "$t/c/meta/extra"
! bash "$here/artifact.sh" verify "$t/c" "$sum" >/dev/null 2>&1 || fail "extra file passed"
cp -r "$t/a" "$t/d"; rm "$t/d/meta/holyarrs-plugin.json"
! bash "$here/artifact.sh" verify "$t/d" "$sum" >/dev/null 2>&1 || fail "missing file passed"
cp -r "$t/a" "$t/e"; echo x >> "$t/e/SHA256SUMS"
! bash "$here/artifact.sh" verify "$t/e" "$sum" >/dev/null 2>&1 || fail "changed SHA256SUMS passed"
! bash "$here/artifact.sh" verify "$t/a" "$(printf '0%.0s' {1..64})" >/dev/null 2>&1 || fail "wrong sum passed"

cp -r "$t/a" "$t/f"; ln -s /etc/passwd "$t/f/meta/link"
(cd "$t/f" && sha256sum ./bin/linux-amd64/plugin ./meta/holyarrs-plugin.json > SHA256SUMS)
fs=$(sha256sum "$t/f/SHA256SUMS" | cut -d' ' -f1)
! bash "$here/artifact.sh" verify "$t/f" "$fs" >/dev/null 2>&1 || fail "symlink in the artifact passed verify"
cp -r "$t/a" "$t/g"; ln "$t/g/bin/linux-amd64/plugin" "$t/g/twin"
(cd "$t/g" && sha256sum ./bin/linux-amd64/plugin ./meta/holyarrs-plugin.json ./twin > SHA256SUMS)
gs=$(sha256sum "$t/g/SHA256SUMS" | cut -d' ' -f1)
! bash "$here/artifact.sh" verify "$t/g" "$gs" >/dev/null 2>&1 || fail "hard link in the artifact passed verify"

mkdir -p "$t/p/bin/linux-arm64" "$t/p/meta/img" "$t/p/source/tailscale" "$t/p/site/images/tailscale"
touch "$t/p/bin/linux-arm64/plugin" "$t/p/meta/img/logo.png" "$t/p/source/tailscale/1.0.0.tar.xz" "$t/p/SHA256SUMS"   "$t/p/site/images/tailscale/icon-128.webp" "$t/p/site/images/tailscale/icon-256.webp"
bash "$here/artifact.sh" paths "$t/p" tailscale 1.0.0 >/dev/null || fail "good artifact paths rejected"
mkdir -p "$t/p/site/images/avatars"; touch "$t/p/site/images/avatars/CoderLuii-64.webp"
! bash "$here/artifact.sh" paths "$t/p" tailscale 1.0.0 >/dev/null 2>&1 || fail "avatar in the artifact passed"
! bash "$here/artifact.sh" paths "$t/p" tailscale 1.0.0 CoderLuii >/dev/null 2>&1 || fail "avatar passed with a login named"
rm -r "$t/p/site/images/avatars"
mkdir -p "$t/p/site/plugins"; touch "$t/p/site/plugins.json"
! bash "$here/artifact.sh" paths "$t/p" tailscale 1.0.0 >/dev/null 2>&1 || fail "site/plugins.json passed"
rm "$t/p/site/plugins.json"; mkdir -p "$t/p/site/images/other"; touch "$t/p/site/images/other/icon-128.webp"
! bash "$here/artifact.sh" paths "$t/p" tailscale 1.0.0 >/dev/null 2>&1 || fail "another plugin's logo passed"

mkdir -p "$t/s/sub"; echo x > "$t/s/sub/f"
bash "$here/artifact.sh" links "$t/s" >/dev/null || fail "plain tree rejected"
ln -s /etc/passwd "$t/s/sub/l"
! bash "$here/artifact.sh" links "$t/s" >/dev/null 2>&1 || fail "symlink passed"
rm "$t/s/sub/l"; ln "$t/s/sub/f" "$t/s/hard"
! bash "$here/artifact.sh" links "$t/s" >/dev/null 2>&1 || fail "hard link passed"
rm "$t/s/hard"; mkfifo "$t/s/fifo"
! bash "$here/artifact.sh" links "$t/s" >/dev/null 2>&1 || fail "fifo passed"

PREBUILT="$t/a/bin" GOOS=linux GOARCH=amd64 bash "$here/goshim.sh" build -trimpath -ldflags "-s -w" -o "$t/out" .
[ "$(cat "$t/out")" = bin ] || fail "goshim copied the wrong file"
! PREBUILT="$t/a/bin" GOOS=linux GOARCH=arm64 bash "$here/goshim.sh" build -o "$t/out2" . 2>/dev/null || fail "goshim missing file passed"
! PREBUILT="$t/a/bin" bash "$here/goshim.sh" generate ./... 2>/dev/null || fail "goshim ran generate"
echo "artifact tests passed"
