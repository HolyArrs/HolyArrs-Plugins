"""Checks plugin files.

    python .github/scripts/check.py
        every file in catalog/active and catalog/inactive (what the pull request check runs)
    python .github/scripts/check.py catalog/active/<id>.json [--src FOLDER]
        one entry file; with --src also the plugin folder (holyarrs-plugin.json, go.mod, logo)
        against the same strict limits our publish step uses

Needs: pip install "jsonschema==4.23.0". Prints every problem, exits 1 if there is one.
"""
import argparse
import json
import os
import pathlib
import re
import sys

from jsonschema import Draft202012Validator

root = pathlib.Path(__file__).resolve().parents[2]
SCOPES = set(json.loads((root / ".github/scopes.json").read_text(encoding="utf-8"))["scopes"])
schema = json.loads((root / "docs/template/plugin.schema.json").read_text(encoding="utf-8"))
template = json.loads((root / "docs/template/plugin.json").read_text(encoding="utf-8"))
validator = Draft202012Validator(schema)

# The publish step's limits (holyarrs deploy/release/plugins/publish.py), in characters or entries.
# The app accepts a little more; a listing must stay inside these.
LIMITS = {
    "name": 40, "author": 40, "description": 160, "long_description": 2000, "whats_new": 300, "category": 24,
    "step": 160, "steps": 8, "developers": 5,
    "host": 80, "hosts": 100, "folder": 60, "folders": 100, "actions": 200,
    "settings": 100, "label": 48, "help": 160, "option": 40, "options": 12,
}
# resources: optional per-plugin limits above the defaults; these are sanity bounds only.
# these are only sanity bounds. The real ceiling is the server's own total (checked by the app).
RESOURCES = {"memory_mib": (64, 65536), "cpus": (1, 64), "processes": (16, 4096), "open_files": (64, 65536)}
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
EMAIL_RE = re.compile(r"^[^\s@<>\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
VER_RE = re.compile(r"^\d+\.\d+\.\d+$")
TYPES = ("text", "number", "toggle", "select", "secret")
# Filled in when publishing, never by the author.
FILLED_ON_PUBLISH = ("sha256", "platforms", "size", "icon")


ICON_RE = re.compile(r"[A-Za-z0-9._/-]+")


def ver(s):
    return tuple(int(x) for x in s.split("."))


def tag_version(e):
    """The version a tag names: 1.0.0, v1.0.0, or <id>-v1.0.0 (for a repo that holds several plugins)."""
    t = str(e.get("tag") or "")
    pid = str(e.get("id") or "")
    if pid and t.startswith(pid + "-"):
        t = t[len(pid) + 1:]
    return t.removeprefix("v")


def check_entry(f, bad, seen):
    rel = f.relative_to(root).as_posix() if f.is_relative_to(root) else str(f)
    try:
        e = json.loads(f.read_text(encoding="utf-8"))
    except Exception as err:
        bad.append(f"{rel}: not valid JSON ({err})")
        return None
    for err in validator.iter_errors(e):
        where = "/".join(str(p) for p in err.absolute_path) or "(file)"
        bad.append(f"{rel}: {where}: {err.message}")
    if not isinstance(e, dict):
        return None
    pid = e.get("id")
    if isinstance(pid, str) and f.stem != pid:
        bad.append(f"{rel}: file name must be {pid}.json")
    if pid in seen:
        bad.append(f"{rel}: id is also used by {seen[pid]}")
    seen.setdefault(pid, rel)
    for k in ("id", "repo", "commit"):
        if e.get(k) == template.get(k):
            bad.append(f"{rel}: {k} is still the template value")
    if any(part in (".", "..") for part in str(e.get("path", "")).split("/")):
        bad.append(f"{rel}: path must not use . or ..")
    if re.fullmatch(r"0{40}", str(e.get("commit", ""))):
        bad.append(f"{rel}: commit is a placeholder")
    tv = tag_version(e)
    if isinstance(e.get("tag"), str) and not VER_RE.fullmatch(tv):
        bad.append(f"{rel}: tag must be a version like 1.0.0 (v1.0.0 and <id>-v1.0.0 also work)")
    if e.get("version") and e.get("version") != tv:
        bad.append(f"{rel}: version {e.get('version')} is not the tag's version {tv}; leave version out or match the tag")
    m = e.get("min_app_version")
    if isinstance(m, str) and VER_RE.fullmatch(m) and ver(m) < (1, 2, 1):
        bad.append(f"{rel}: min_app_version must be 1.2.1 or newer")
    return e


def check_source(src, entry, bad):
    """holyarrs-plugin.json and the folder, with the publish step's strict limits."""
    where = "holyarrs-plugin.json"
    path = src / where
    if not path.is_file():
        bad.append(f"{path}: missing")
        return
    # Links could point the build or the logo copy outside the folder.
    before = len(bad)
    for q in sorted(src.rglob("*")):
        if ".git" in q.relative_to(src).parts:
            continue
        if q.is_symlink():
            bad.append(f"{q.relative_to(src).as_posix()}: links are not allowed in the plugin folder")
        elif not (q.is_dir() or q.is_file()):
            bad.append(f"{q.relative_to(src).as_posix()}: only plain files and folders are allowed")
    if len(bad) > before:
        return
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except Exception as err:
        bad.append(f"{where}: not valid JSON ({err})")
        return
    if not isinstance(m, dict):
        bad.append(f"{where}: must be a JSON object")
        return
    if not (src / "go.mod").is_file():
        bad.append(f"{src / 'go.mod'}: missing (the plugin is one Go program)")

    def text(what, v, most):
        if v is None:
            return
        if not isinstance(v, str):
            bad.append(f"{where}: {what} must be text")
        elif len(v) > most:
            bad.append(f"{where}: {what} is {len(v)} characters; the most is {most}")
        elif "<" in v or ">" in v:
            bad.append(f"{where}: {what} has < or >; plain text only")

    def items(what, v, most):
        if v is None:
            return []
        if not isinstance(v, list):
            bad.append(f"{where}: {what} must be a list")
            return []
        if len(v) > most:
            bad.append(f"{where}: {what} has {len(v)} entries; the most is {most}")
        return v

    for k in FILLED_ON_PUBLISH:
        if k in m:
            bad.append(f"{where}: remove {k!r}; we fill it in when publishing")
    for k in ("name", "author", "min_app_version", "licence", "support_email"):
        if not m.get(k):
            bad.append(f"{where}: {k} is required")
    if entry and m.get("id", entry.get("id")) != entry.get("id"):
        bad.append(f"{where}: id {m.get('id')!r} is not the entry's {entry.get('id')!r}")
    for k in ("name", "author", "description", "long_description", "whats_new", "category"):
        text(k, m.get(k), LIMITS[k])
    for i, st in enumerate(items("how_it_works", m.get("how_it_works"), LIMITS["steps"])):
        text(f"how_it_works step {i + 1}", st, LIMITS["step"])
    for d in items("developers", m.get("developers"), LIMITS["developers"]):
        if not isinstance(d, str) or not LOGIN_RE.fullmatch(d):
            bad.append(f"{where}: developer {d!r} is not a GitHub login")
    mv = m.get("min_app_version")
    if mv and (not isinstance(mv, str) or not VER_RE.fullmatch(mv) or ver(mv) < (1, 2, 1)):
        bad.append(f"{where}: min_app_version must be x.y.z, 1.2.1 or newer")
    if m.get("support_email") and not EMAIL_RE.fullmatch(str(m["support_email"])):
        bad.append(f"{where}: support_email is not an email address")
    for k in ("support_url", "repo", "icon_url"):
        if m.get(k) and not str(m[k]).startswith("https://"):
            bad.append(f"{where}: {k} must be an https link")
    icon = m.get("icon_file")
    if icon:
        icon = str(icon)
        if (not ICON_RE.fullmatch(icon) or ".." in icon.split("/") or icon.startswith("/")
                or "//" in icon):
            bad.append(f"{where}: unsafe icon_file {icon!r} (plain relative path, no .., \\, : or spaces)")
        elif os.path.splitext(icon)[1].lower() not in (".svg", ".png"):
            bad.append(f"{where}: icon_file must be .svg or .png")
        else:
            p = src / icon
            inside = src.resolve() in p.resolve().parents
            if p.is_symlink():
                bad.append(f"{where}: icon_file {icon!r} must not be a link")
            elif not inside:
                bad.append(f"{where}: icon_file {icon!r} is outside the folder")
            elif not p.is_file():
                bad.append(f"{where}: icon_file {icon!r} is not in the folder")
    if not icon and not m.get("icon_url") and not (entry or {}).get("icon_url"):
        bad.append(f"{where}: a logo is required: add icon_file (a .svg or .png in the folder) or icon_url")

    acc = m.get("access")
    if not isinstance(acc, dict):
        bad.append(f'{where}: access is required, for example {{"hosts": [], "folders": [], "actions": []}}')
        acc = {}
    for h in items("access.hosts", acc.get("hosts"), LIMITS["hosts"]):
        if not isinstance(h, str) or not h.strip() or ".." in h or "\\" in h:
            bad.append(f"{where}: unsafe host {h!r}")
        else:
            text(f"access host {h[:30]!r}", h, LIMITS["host"])
    for fo in items("access.folders", acc.get("folders"), LIMITS["folders"]):
        # A plain name (read-only) or {"name", "mode", "why", "required"}, as the app takes it.
        if isinstance(fo, dict):
            extra = set(fo) - {"name", "mode", "why", "required"}
            if extra:
                bad.append(f"{where}: folder has unknown keys {sorted(extra)}")
            if fo.get("mode", "read") not in ("read", "read_write"):
                bad.append(f"{where}: folder mode must be read or read_write")
            if not isinstance(fo.get("required", False), bool):
                bad.append(f"{where}: folder required must be true or false")
            if "why" in fo:
                text("access folder why", fo["why"], LIMITS["step"])
            fo = fo.get("name")
        if (not isinstance(fo, str) or not fo.strip() or ".." in fo or "\\" in fo or ":" in fo
                or "/" in fo or len(fo) > 40):
            bad.append(f"{where}: unsafe folder {fo!r} (a name of up to 40, no /, .., \\ or :)")
    res = m.get("resources")
    if res is not None:
        # Optional, HolyArrs 1.3.0+: more than the defaults (512 MiB, 1 CPU, 256 processes,
        # 1024 open files). The owner approves anything above them at install; the
        # app refuses more than the server has.
        if not isinstance(res, dict) or not res:
            bad.append(f"{where}: resources must be an object, for example {{\"memory_mib\": 1024}}")
            res = {}
        extra = set(res) - set(RESOURCES)
        if extra:
            bad.append(f"{where}: resources has unknown keys {sorted(extra)}; use {', '.join(RESOURCES)}")
        for k, (lo, hi) in RESOURCES.items():
            if k in res and (not isinstance(res[k], int) or isinstance(res[k], bool) or not lo <= res[k] <= hi):
                bad.append(f"{where}: resources.{k} must be a whole number from {lo} to {hi}")
        if res and (not isinstance(mv, str) or not VER_RE.fullmatch(mv) or ver(mv) < (1, 3, 0)):
            bad.append(f"{where}: resources needs min_app_version 1.3.0 or newer")
    acts = items("access.actions", acc.get("actions"), LIMITS["actions"])
    for act in acts:
        if not isinstance(act, str) or act not in SCOPES:
            bad.append(f"{where}: unknown permission {act!r}; the list is in .github/scopes.json")
    if acts and len(set(map(str, acts))) != len(acts):
        bad.append(f"{where}: access.actions lists a permission twice")
    if acts and (not isinstance(mv, str) or not VER_RE.fullmatch(mv) or ver(mv) < (1, 3, 0)):
        bad.append(f"{where}: access.actions needs min_app_version 1.3.0 or newer")

    seen = set()
    for s in items("settings", m.get("settings"), LIMITS["settings"]):
        if not isinstance(s, dict):
            bad.append(f"{where}: every setting must be an object")
            continue
        key = s.get("key")
        name = f"setting {key!r}"
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            bad.append(f"{where}: {name}: key must match ^[a-z][a-z0-9_]{{0,39}}$ (starts with a letter)")
        elif key in seen:
            bad.append(f"{where}: {name}: key is used twice")
        seen.add(key)
        if not str(s.get("label") or "").strip():
            bad.append(f"{where}: {name}: label is required")
        text(f"{name} label", s.get("label"), LIMITS["label"])
        text(f"{name} help", s.get("help"), LIMITS["help"])
        typ, default = s.get("type"), s.get("default")
        if typ not in TYPES:
            bad.append(f"{where}: {name}: type must be one of {', '.join(TYPES)}")
        if typ == "secret" and default not in (None, ""):
            bad.append(f"{where}: {name}: a secret can't have a default")
        if typ == "toggle" and default not in (None, "", "true", "false", True, False):
            bad.append(f"{where}: {name}: default must be true or false")
        if typ == "number" and default not in (None, ""):
            try:
                float(default)
            except (TypeError, ValueError):
                bad.append(f"{where}: {name}: default is not a number")
        if typ == "select":
            opts = items(f"{name} options", s.get("options"), LIMITS["options"])
            if not opts:
                bad.append(f"{where}: {name}: a select needs 1 to {LIMITS['options']} options")
            for o in opts:
                if not isinstance(o, str) or not o.strip():
                    bad.append(f"{where}: {name}: empty option")
                else:
                    text(f"{name} option {o[:20]!r}", o, LIMITS["option"])
            if default not in (None, "") and default not in opts:
                bad.append(f"{where}: {name}: default is not one of its options")


def main():
    ap = argparse.ArgumentParser(description="Checks HolyArrs plugin files.")
    ap.add_argument("entry", nargs="?", help="one entry file, for example catalog/active/<id>.json")
    ap.add_argument("--src", help="the plugin folder (holds holyarrs-plugin.json)")
    a = ap.parse_args()
    bad, seen = [], {}
    if a.entry:
        f = pathlib.Path(a.entry).resolve()
        if not f.is_file():
            sys.exit(f"{a.entry}: not found")
        entry = check_entry(f, bad, seen)
        if a.src:
            check_source(pathlib.Path(a.src).resolve(), entry, bad)
    else:
        if a.src:
            sys.exit("--src needs an entry file")
        for state in ("active", "inactive"):
            for f in sorted((root / "catalog" / state).iterdir()):
                if f.name in ("README.md", ".gitkeep", "language-packs.json"):  # Language packs: checked by languages.py check
                    continue
                if f.suffix != ".json" or not f.is_file():
                    bad.append(f"{f.relative_to(root).as_posix()}: only <id>.json plugin files go here")
                    continue
                check_entry(f, bad, seen)
    print("\n".join(bad) if bad else f"{len(seen)} plugin file(s) look right" + (" and the plugin folder too" if a.src else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
