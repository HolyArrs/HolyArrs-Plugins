#!/usr/bin/env python3
"""HolyArrs language packs: the readable files in languages/ become the signed
languages.json and the bzip2 packs on plugins.holyarrs.com.

    languages.py index    rewrite catalog/active/language-packs.json from languages/*.json
    languages.py check    languages/ and catalog/active/language-packs.json agree
    languages.py sign --out SITE --key FILE [--live-url URL] [--pub FILE]

languages/<code>.json is one language as the app's build writes it
({lang, app, fit, values}: app/frontend/lang-out). sign packs each as
SITE/languages/<code>/<app>.json.bz2 (where the app fetches it) and signs
SITE/languages.json: kind "languages", its own counter one above the tree's and
never below the live one, min_blocklist_counter at the current blocklist.
Entries for older app versions are kept. A published pack never changes: the
same pack again is skipped, another file for the same language and app version
is refused. SITE must already hold the live lists (live.sh seed).
Needs the cryptography package for signing. Never prints the key.
"""
import argparse
import base64
import bz2
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

# The committed source folder (one place to rename it). Served paths never change.
SOURCE_DIR = "plugins/language-packs"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODE_RE = re.compile(r"^[a-z]{2,3}(-[a-z]{2})?$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$")


class Fail(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read_sources(root):
    """Every languages/<code>.json, checked the way the app checks a pack."""
    src = os.path.join(root, SOURCE_DIR)
    out = []
    for name in sorted(os.listdir(src)) if os.path.isdir(src) else []:
        if not name.endswith(".json"):
            continue
        code = name[:-5]
        raw = open(os.path.join(src, name), "rb").read()
        head = json.loads(raw)
        if not CODE_RE.match(code) or head.get("lang") != code or not SEMVER_RE.match(str(head.get("app"))) \
                or not head.get("fit") or not head.get("values"):
            raise Fail(f"{SOURCE_DIR}/{name}: needs lang {code!r}, app (X.Y.Z), fit and values")
        out.append((code, head, raw))
    if not out:
        raise Fail(f"{SOURCE_DIR}/ holds no language files")
    if len({h["app"] for _, h, _ in out}) != 1:
        raise Fail(f"{SOURCE_DIR}/ files are for more than one app version")
    return out


MARK_RE = re.compile(r"\{\w+\}|</?\w+>", re.ASCII)  # ASCII \w, as in the build's JavaScript check


def marks(text):
    return " ".join(sorted(MARK_RE.findall(text)))


def blocked(b, eid, ver, digest):
    """The app's blockedPack rule: by hash, or by id with no version (every version) or this one."""
    return bool((b.get("sha256") and b["sha256"] == digest) or
                (b.get("id") and b["id"] == eid and b.get("version") in (None, "", ver)))


def check_marks(root, srcs):
    """Every line keeps English's {slots} and <tags> (the build's own pack-lang check).
    English is languages/source/en.json, from the same build (its fit must match)."""
    p = os.path.join(root, SOURCE_DIR, "source", "en.json")
    if not os.path.exists(p):
        raise Fail(f"{SOURCE_DIR}/source/en.json is missing; the slot and tag check needs English")
    en = json.load(open(p, encoding="utf-8"))
    fit = sha(json.dumps(en["keys"], separators=(",", ":"), ensure_ascii=False).encode())[:12]
    if fit != en.get("fit") or len(en["keys"]) != len(en["values"]):
        raise Fail(f"{SOURCE_DIR}/source/en.json does not match its own key list")
    wrong = []
    for code, head, _ in srcs:
        if head["fit"] != en["fit"] or len(head["values"]) != len(en["values"]):
            raise Fail(f"{SOURCE_DIR}/{code}.json is for fit {head['fit']}, English is {en['fit']}")
        for k, e, v in zip(en["keys"], en["values"], head["values"]):
            if isinstance(v, str) and marks(v) != marks(e):
                wrong.append(f"{code} {k}: {marks(e) or '-'} vs {marks(v) or '-'}")
    if wrong:
        raise Fail(f"{len(wrong)} lines have other slots or tags than English:\n  " + "\n  ".join(wrong[:50]))


def make_index(srcs):
    # Shaped like a plugin's entry (id, name, description, authors, version, path), plus the app build the packs fit.
    return {"id": "language-packs", "name": "Language Packs",
            "description": "Shows HolyArrs in your language. Install the languages you want; English is always there.",
            "authors": ["CoderLuii"], "repo": "https://github.com/HolyArrs/HolyArrs-Plugins", "path": SOURCE_DIR,
            "version": "1.0.0", "min_app_version": "1.3.0",
            "app": srcs[0][1]["app"], "fit": srcs[0][1]["fit"], "languages": [
        {"code": c, "file": f"{SOURCE_DIR}/{c}.json", "lines": len(h["values"]),
         "translated": sum(v is not None for v in h["values"]), "sha256": sha(raw)} for c, h, raw in srcs]}


def dump(obj):
    return json.dumps(obj, indent=2) + "\n"


def index_path(root):
    return os.path.join(root, "catalog", "active", "language-packs.json")


def cmd_index(a):
    with open(index_path(a.root), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(make_index(read_sources(a.root))))
    print("wrote catalog/active/language-packs.json")


def cmd_check(a):
    srcs = read_sources(a.root)
    check_marks(a.root, srcs)
    want = dump(make_index(srcs))
    p = index_path(a.root)
    have = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    if want != have:
        raise Fail("catalog/active/language-packs.json is out of date: run .github/scripts/languages.py index")
    print(f"catalog/active/language-packs.json matches {SOURCE_DIR}/")


# ---------- signing ----------

def payload(raw, pub, kind, name):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    sl = json.loads(raw)
    p, s = base64.b64decode(sl["payload"]), base64.b64decode(sl["signature"])
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(s, p)
    except InvalidSignature:
        raise Fail(f"{name}: signature does not match the pinned key")
    body = json.loads(p)
    if body.get("kind") != kind:
        raise Fail(f"{name}: kind {body.get('kind')!r}, want {kind!r}")
    return body


def fetch(base, rel):
    if not base:
        return None
    if base.startswith("https://"):
        req = urllib.request.Request(base.rstrip("/") + "/" + rel,
                                     headers={"Cache-Control": "no-cache", "User-Agent": "holyarrs-release-tools"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise Fail(f"fetching {rel}: HTTP {e.code}")
    p = os.path.join(base, *rel.split("/"))
    return open(p, "rb").read() if os.path.exists(p) else None


def released_tag(ver):
    """Whether HolyArrs/HolyArrs has the release tag ver."""
    import subprocess
    out = subprocess.run(["git", "ls-remote", "--tags", "https://github.com/HolyArrs/HolyArrs", f"refs/tags/{ver}", f"refs/tags/v{ver}"],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise Fail("can't check HolyArrs' release tags")
    return bool(out.stdout.strip())


def cmd_sign(a):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    pub = base64.b64decode(open(a.pub, encoding="utf-8").read().strip())
    srcs = read_sources(a.root)
    check_marks(a.root, srcs)
    braw = fetch(a.out, "blocklist.json")
    if braw is None:
        raise Fail("blocklist.json is not in --out; run live.sh seed first")
    bl = payload(braw, pub, "blocklist", "blocklist.json")
    raw = fetch(a.out, "languages.json")
    old = payload(raw, pub, "languages", "languages.json") if raw else {}
    have = old.get("counter", 0)
    live_raw = fetch(a.live_url, "languages.json")
    if live_raw:
        live = payload(live_raw, pub, "languages", "live languages.json")
        if live["counter"] > have:
            raise Fail(f"languages.json: live counter {live['counter']} is ahead of the tree's {have}; the tree is stale")
        if live["counter"] == have and live != old:
            raise Fail(f"languages.json: live and tree both have counter {have} but differ")
    entries = list(old.get("entries") or [])
    redo = getattr(a, "replace_unreleased", "") or ""
    if redo:
        # Only before that HolyArrs version is released: no server can have its packs yet.
        if released_tag(redo):
            raise Fail(f"HolyArrs {redo} is released; its packs can no longer change")
        entries = [e for e in entries if e.get("version") != redo]
        print(f"replacing every {redo} pack (HolyArrs {redo} is not released yet)")
    new_files = []
    for code, head, src in srcs:
        ver, eid = head["app"], "lang-" + code
        packed = bz2.compress(src, 9)
        rel = f"languages/{code}/{ver}.json.bz2"
        same = [e for e in entries if e["id"] == eid and e["version"] == ver]
        if same and same[0]["sha256"] == sha(packed):
            print(f"{eid} {ver}: already listed, skipped")
            continue
        if same:
            raise Fail(f"{eid} {ver} is already listed with another file; a published pack never changes")
        for base in (a.out, a.live_url) if ver != redo else ():
            got = fetch(base, rel)
            if got is not None and got != packed:
                raise Fail(f"{rel} already exists with other bytes; a published pack never changes")
        for b in bl.get("entries") or []:
            if blocked(b, eid, ver, sha(packed)):
                raise Fail(f"{eid} {ver} is on the blocklist")
        entries.append({"id": eid, "version": ver, "sha256": sha(packed), "size": len(packed)})
        new_files.append((rel, packed))
    if not new_files:
        raise Fail("every pack is already listed; nothing to sign")
    body = {"kind": "languages", "counter": have + 1,
            "min_blocklist_counter": max(old.get("min_blocklist_counter") or 0, bl["counter"]), "entries": entries}
    p = json.dumps(body, separators=(",", ":")).encode()
    sk = Ed25519PrivateKey.from_private_bytes(base64.b64decode(open(a.key, encoding="utf-8").read().strip()))
    if sk.public_key().public_bytes_raw() != pub:
        raise Fail(f"the signing key is not the pinned key in {a.pub}")
    signed = json.dumps({"payload": base64.b64encode(p).decode(),
                         "signature": base64.b64encode(sk.sign(p)).decode()}).encode()
    payload(signed, pub, "languages", "new languages.json")
    for rel, data in new_files:  # packs first, the list that names them last
        dest = os.path.join(a.out, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        print("wrote", rel)
    with open(os.path.join(a.out, "languages.json"), "wb") as f:
        f.write(signed)
    print(f"languages.json: counter {body['counter']}, {len(new_files)} new packs, {len(entries)} entries")


PLUGIN_LISTS = ("plugins.json", "plugins-linux-arm64.json", "plugins-linux-arm-v7.json")


def sign_body(sk, body):
    p = json.dumps(body, separators=(",", ":")).encode()
    return json.dumps({"payload": base64.b64encode(p).decode(), "signature": base64.b64encode(sk.sign(p)).decode()}).encode()


def cmd_rotate(a):
    """One time: re-signs the empty live lists with the pinned key, counters one up.
    Only while every list is empty, so no plugin or block is ever dropped."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    pub = base64.b64decode(open(a.pub, encoding="utf-8").read().strip())
    sk = Ed25519PrivateKey.from_private_bytes(base64.b64decode(open(a.key, encoding="utf-8").read().strip()))
    if sk.public_key().public_bytes_raw() != pub:
        raise Fail(f"the signing key is not the pinned key in {a.pub}")
    old = {}
    for name in ("blocklist.json",) + PLUGIN_LISTS:
        raw = fetch(a.out, name)
        if raw is None:
            raise Fail(f"{name} is not in --out; run live.sh seed first")
        body = json.loads(base64.b64decode(json.loads(raw)["payload"]))  # old key is gone: read, not trust
        if body.get("entries"):
            raise Fail(f"{name} has {len(body['entries'])} entries; rotation only replaces empty lists")
        old[name] = body
    if fetch(a.out, "languages.json") is not None:
        raise Fail("languages.json is already live; rotate before the first language publish")
    blc = old["blocklist.json"]["counter"] + 1
    pc = max(old[n]["counter"] for n in PLUGIN_LISTS) + 1
    files = {"blocklist.json": sign_body(sk, {"kind": "blocklist", "counter": blc, "entries": []})}
    for n in PLUGIN_LISTS:
        files[n] = sign_body(sk, {"kind": "plugins", "counter": pc, "min_blocklist_counter": blc, "entries": []})
    for n, b in files.items():
        payload(b, pub, "blocklist" if n == "blocklist.json" else "plugins", n)
        with open(os.path.join(a.out, n), "wb") as f:
            f.write(b)
    print(f"rotated: blocklist counter {blc}, plugin lists counter {pc}, signed with the pinned key")


def cmd_resign(a):
    """After a key change: re-signs every live list with the pinned key, counters one up,
    entries unchanged. Each list must check with the pinned key or the previous one."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    pub = base64.b64decode(open(a.pub, encoding="utf-8").read().strip())
    prev = base64.b64decode(open(a.previous_pub, encoding="utf-8").read().strip())
    sk = Ed25519PrivateKey.from_private_bytes(base64.b64decode(open(a.key, encoding="utf-8").read().strip()))
    if sk.public_key().public_bytes_raw() != pub:
        raise Fail(f"the signing key is not the pinned key in {a.pub}")

    def read(name, kind):
        raw = fetch(a.out, name)
        if raw is None:
            return None
        try:
            return payload(raw, pub, kind, name)
        except Fail:
            return payload(raw, prev, kind, name + " (previous key)")

    bl = read("blocklist.json", "blocklist")
    if bl is None:
        raise Fail("blocklist.json is not in --out; run live.sh seed first")
    blc = bl["counter"] + 1
    files = {"blocklist.json": sign_body(sk, dict(bl, counter=blc))}
    for n in PLUGIN_LISTS:
        p = read(n, "plugins")
        if p is None:
            raise Fail(f"{n} is not in --out; run live.sh seed first")
        files[n] = sign_body(sk, dict(p, counter=p["counter"] + 1, min_blocklist_counter=blc))
    lang = read("languages.json", "languages")
    if lang is not None:
        files["languages.json"] = sign_body(sk, dict(lang, counter=lang["counter"] + 1, min_blocklist_counter=blc))
    for n, b in files.items():
        kind = "blocklist" if n == "blocklist.json" else "languages" if n == "languages.json" else "plugins"
        body = payload(b, pub, kind, n)
        with open(os.path.join(a.out, n), "wb") as f:
            f.write(b)
        print(f"{n}: re-signed, counter {body['counter']}, {len(body.get('entries') or [])} entries")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["index", "check", "sign", "rotate", "resign"])
    ap.add_argument("--root", default=ROOT, help="the plugins repo (default: this checkout)")
    ap.add_argument("--out")
    ap.add_argument("--key")
    ap.add_argument("--live-url", default="https://plugins.holyarrs.com/")
    ap.add_argument("--replace-unreleased", default="", help="re-sign every pack of this app version, only while HolyArrs hasn't released it")
    ap.add_argument("--pub", default=os.path.join(ROOT, ".github", "keys", "main.pub"))
    ap.add_argument("--previous-pub", default=os.path.join(ROOT, ".github", "keys", "previous.pub"))
    a = ap.parse_args(argv)
    if a.command in ("sign", "rotate", "resign") and not (a.out and a.key):
        ap.error("sign needs --out and --key")
    try:
        {"index": cmd_index, "check": cmd_check, "sign": cmd_sign, "rotate": cmd_rotate, "resign": cmd_resign}[a.command](a)
    except Fail as e:
        print("error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
