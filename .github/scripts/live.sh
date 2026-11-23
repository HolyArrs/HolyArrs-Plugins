#!/usr/bin/env bash
# Shared R2 steps for plugins.holyarrs.com (bucket holyarrs-plugins).
#   live.sh seed DIR           copy the live lists into DIR; any missing or
#                              unreadable list fails the run
#   live.sh trust DIR STATE    the seeded signed lists must match the record in
#                              STATE (.github/state/lists.json): same sha256, counters
#                              never lower
#   live.sh upload DIR         upload DIR: new version files and language
#                              packs first (never overwritten), then
#                              block-reasons.txt, blocklist.json,
#                              languages.json, the plugin lists
#   live.sh images DIR         upload DIR/images/** (logos, developer pictures)
#                              when they differ from the live copy; these may
#                              change, so they are never part of the never-overwrite step
#   live.sh check DIR          read the live lists back and compare with DIR
#   live.sh record DIR STATE   write counter + sha256 (+ plugin ids) of DIR's signed
#                              lists to STATE; refuses if a counter would go down
# Needs AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, R2_ACCOUNT_ID for upload.
set -euo pipefail
LIVE=https://plugins.holyarrs.com
BUCKET=holyarrs-plugins
LISTS="plugins.json plugins-linux-arm64.json plugins-linux-arm-v7.json"
SIGNED="$LISTS blocklist.json languages.json"
cmd=${1:?command}; dir=${2:?folder}
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

# Prints a JSON object {name: {counter, sha256}} for the signed lists in $1.
# The plugin lists also get "ids": the plugin ids they list, and languages.json gets "released":
# its released pack versions. The README follows both.
summary() {
  python3 - "$1" $SIGNED <<'PY'
import base64, hashlib, json, os, sys
d, out = sys.argv[1], {}
for n in sys.argv[2:]:
    p = os.path.join(d, n)
    if not os.path.exists(p):
        continue
    raw = open(p, "rb").read()
    body = json.loads(base64.b64decode(json.loads(raw)["payload"]))
    c = body["counter"]
    if not isinstance(c, int) or c < 0:
        sys.exit(f"{n}: bad counter")
    out[n] = {"counter": c, "sha256": hashlib.sha256(raw).hexdigest()}
    if n.startswith("plugins"):
        out[n]["ids"] = sorted({str(e.get("id")) for e in body.get("entries") or [] if isinstance(e, dict) and e.get("id")})
    if n == "languages.json":
        # Released pack versions (no "-test" style suffix); the README shows Language packs only when one exists.
        out[n]["released"] = sorted({str(e.get("version")) for e in body.get("entries") or []
                                     if isinstance(e, dict) and e.get("version") and "-" not in str(e.get("version"))})
print(json.dumps(out, indent=2, sort_keys=True))
PY
}

case "$cmd" in
seed)
  mkdir -p "$dir"
  for f in $SIGNED block-reasons.txt; do
    code=$(curl -sS -H 'Cache-Control: no-cache' -o "$dir/$f" -w '%{http_code}' "$LIVE/$f?r=$RANDOM") || code=000
    case "$code" in
      200) echo "seeded $f" ;;
      404)
        rm -f "$dir/$f"
        # block-reasons.txt first appears with the first block and
        # languages.json with the first language packs, so they may be
        # missing; the other signed lists must always be there.
        if [ "$f" != block-reasons.txt ] && [ "$f" != languages.json ]; then
          echo "$f is missing on the live site"; exit 1
        fi
        echo "$f not published yet" ;;
      *) echo "fetching $f: HTTP $code"; exit 1 ;;
    esac
  done ;;
trust)
  state=${3:?state file}
  if [ ! -f "$state" ]; then
    echo "$state is missing; there is no trusted record of the live lists"; exit 1
  fi
  summary "$dir" > "$dir/.live-summary.json"
  python3 - "$state" "$dir/.live-summary.json" <<'PY'
import json, sys
rec, live = (json.load(open(p)) for p in sys.argv[1:3])
bad = []
for n, r in rec.items():
    l = live.get(n)
    if l is None:
        bad.append(f"{n}: recorded but not live")
    elif l["counter"] < r["counter"]:
        bad.append(f"{n}: live counter {l['counter']} is below the recorded {r['counter']} (rollback)")
    elif l["sha256"] != r["sha256"]:
        bad.append(f"{n}: live file differs from the recorded sha256")
for n in live:
    if n not in rec:
        bad.append(f"{n}: live but not in the record")
if bad:
    sys.exit("live lists do not match .github/state/lists.json:\n  " + "\n  ".join(bad))
print("live lists match the trusted record")
PY
  rm -f "$dir/.live-summary.json" ;;
record)
  state=${3:?state file}
  mkdir -p "$(dirname "$state")"
  summary "$dir" > "$state.new"
  if [ -f "$state" ]; then
    python3 - "$state" "$state.new" <<'PY'
import json, sys
old, new = (json.load(open(p)) for p in sys.argv[1:3])
for n, r in old.items():
    if n not in new or new[n]["counter"] < r["counter"]:
        sys.exit(f"{n}: the new record would lower or drop the counter")
PY
  fi
  mv "$state.new" "$state"
  echo "recorded:"; cat "$state" ;;
upload)
  export AWS_DEFAULT_REGION=auto
  EP="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  cd "$dir"
  mutable=" $SIGNED block-reasons.txt "
  err=$(mktemp)
  # 1. Version files and source archives: a published file never changes.
  #    The write itself refuses to replace an existing key (If-None-Match: *).
  while read -r key; do
    case "$mutable" in *" $key "*) continue ;; esac
    case "$key" in images/*) continue ;; esac
    # An unreleased app version's language packs may be replaced (REPLACE_UNRELEASED,
    # checked by languages.py against HolyArrs' release tags); nothing else ever is.
    nonematch=(--if-none-match '*')
    if [ -n "${REPLACE_UNRELEASED:-}" ]; then
      case "$key" in languages/*/"$REPLACE_UNRELEASED".json.bz2) nonematch=() ;; esac
    fi
    if aws s3api put-object --endpoint-url "$EP" --bucket "$BUCKET" --key "$key" \
        --body "$key" "${nonematch[@]}" \
        --cache-control "public, max-age=31536000, immutable" >/dev/null 2>"$err"; then
      echo "uploaded $key"
    elif grep -q 'PreconditionFailed\|(412)' "$err"; then
      echo "$key is already on R2; a published file never changes"; exit 1
    else
      echo "uploading $key failed:"; cat "$err"; exit 1
    fi
  done < <(find . -type f ! -name '.*' | sed 's|^\./||' | sort)
  bash "$SELF" images .
  # 2. The lists last, so they never name a file that is not there yet.
  for key in block-reasons.txt blocklist.json languages.json $LISTS; do
    [ -f "$key" ] || continue
    if [ "$key" = block-reasons.txt ]; then ct=text/plain; else ct=application/json; fi
    aws s3 cp --endpoint-url "$EP" --no-progress --cache-control "no-cache" --content-type "$ct" "$key" "s3://$BUCKET/$key"
  done ;;
images)
  export AWS_DEFAULT_REGION=auto
  EP="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  [ -d "$dir/images" ] || { echo "no images"; exit 0; }
  cd "$dir"
  L=$(mktemp)
  while read -r key; do
    [[ "$key" =~ ^images/([a-z0-9][a-z0-9-]{0,63}/icon-(128|256)|avatars/[A-Za-z0-9][A-Za-z0-9-]{0,38}-64)\.webp$ ]] || { echo "$key: not a picture path the app reads"; exit 1; }
    if curl -fsS -H 'Cache-Control: no-cache' "$LIVE/$key?r=$RANDOM" -o "$L" 2>/dev/null && cmp -s "$L" "$key"; then
      continue
    fi
    aws s3 cp --endpoint-url "$EP" --no-progress --cache-control "public, max-age=3600" --content-type image/webp "$key" "s3://$BUCKET/$key"
  done < <(find images -type f -name '*.webp' | sort)
  rm -f "$L" ;;
check)
  L=$(mktemp -d)
  for _ in $(seq 1 15); do
    ok=1
    for f in $SIGNED; do
      [ -f "$dir/$f" ] || continue
      if ! { curl -fsS -H 'Cache-Control: no-cache' "$LIVE/$f?r=$RANDOM" -o "$L/$f" && cmp -s "$L/$f" "$dir/$f"; }; then ok=0; fi
    done
    [ $ok = 1 ] && { echo "live lists match"; exit 0; }
    sleep 20
  done
  echo "the live lists still differ after 5 minutes"; exit 1 ;;
*) echo "unknown command $cmd"; exit 1 ;;
esac
