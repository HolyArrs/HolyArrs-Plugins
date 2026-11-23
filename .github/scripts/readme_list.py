"""Keeps the plugin table in README.md in step with the plugins people can install: the entries in
catalog/active/*.json whose id is on the live signed list (recorded in .github/state/lists.json after
every publish, block or removal). A plugin in catalog/active that isn't published yet doesn't show.
Language packs (catalog/active/language-packs.json) shows only when a released pack version is live, never for test packs.

    python .github/scripts/readme_list.py          rewrite the table in README.md
    python .github/scripts/readme_list.py --check  exit 1 if the table is out of date (the pull request check runs this)

The table sits between <!-- plugins:start --> and <!-- plugins:end -->, the gallery picture between
<!-- gallery:start --> and <!-- gallery:end -->. Nobody edits either by hand.
The logo is catalog/active/<id>.png or .svg when checked in, else the icon_file from the plugin's own
holyarrs-plugin.json at the entry's pinned commit (raw.githubusercontent.com), used only when it loads,
so the row never shows a broken picture; with no logo the generic docs/assets/plugin-glyph.svg shows.
The table is plain HTML with nowrap cells (GitHub keeps nowrap), so picture and name never wrap apart.
"""
import json
import pathlib
import re
import sys
import urllib.request

root = pathlib.Path(__file__).resolve().parents[2]
START, END = "<!-- plugins:start -->", "<!-- plugins:end -->"
GSTART, GEND = "<!-- gallery:start -->", "<!-- gallery:end -->"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gallery  # noqa: E402


def fetch(url):
    """The bytes at url, or None. Raw commit links never change."""
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def remote_logo(e):
    """The raw link of icon_file at the entry's pinned commit, when it loads."""
    m = re.fullmatch(r"https://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(\.git)?", str(e.get("repo") or ""))
    commit, path = str(e.get("commit") or ""), str(e.get("path") or "").strip("/")
    if not m or not re.fullmatch(r"[0-9a-f]{40}", commit) or ".." in path.split("/"):
        return ""
    base = f"https://raw.githubusercontent.com/{m.group(1)}/{commit}/" + (path + "/" if path else "")
    try:
        icon = str(json.loads(fetch(base + "holyarrs-plugin.json") or b"{}").get("icon_file") or "")
    except ValueError:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._/-]+\.(svg|png)", icon) or ".." in icon.split("/"):
        return ""
    return base + icon if fetch(base + icon) else ""


GLYPH = "docs/assets/plugin-glyph.svg"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", " ").strip()


def pic(src, alt):
    return f'<img src="{src}" width="20" height="20" align="absmiddle" alt="{alt}">'


def item(href, src, alt, text):
    """Picture and name in one link, in a nowrap cell, so they always stay on one line."""
    return f'<a href="{href}">{pic(src, alt)}&nbsp;{text}</a>'


def table(folder, live=None, langs=""):
    rows = []
    lang = gallery.language_entry(folder, langs)
    for f in sorted(x for x in folder.glob("*.json") if x.name != gallery.LANGS) + ([None] if lang else []):
        if f is None:
            rows.append(f'<tr><td nowrap><b>{item("plugins/language-packs/", GLYPH, "Language packs", "Language packs")}</b></td>'
                        f"<td>{esc(lang['description'])}</td>"
                        f'<td nowrap>{item("https://github.com/CoderLuii", "https://github.com/CoderLuii.png?size=40", "", "CoderLuii")}</td>'
                        f"<td nowrap><code>{esc(langs)}</code></td></tr>")
            continue
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(e, dict):
            continue
        if live is not None and e.get("id", f.stem) not in live:
            continue
        who = ", ".join(item(f"https://github.com/{esc(a)}", f"https://github.com/{esc(a)}.png?size=40", "", esc(a))
                        for a in e.get("authors") or [])
        name = esc(e.get("name", f.stem))
        logo = next((f"catalog/active/{p.name}" for p in (folder / f"{f.stem}.png", folder / f"{f.stem}.svg")
                     if p.exists()), "") or remote_logo(e) or GLYPH
        rows.append(f'<tr><td nowrap><b>{item(f"catalog/active/{f.name}", logo, name, name)}</b></td>'
                    f"<td>{esc(e.get('description', ''))}</td><td nowrap>{who}</td>"
                    f"<td nowrap><code>{esc(gallery.version(e))}</code></td></tr>")
    if not rows:
        rows.append('<tr><td colspan="4">No plugins yet</td></tr>')
    return ("<table>\n<tr><th>Plugin</th><th>What it does</th><th>Made by</th><th>Version</th></tr>\n"
            + "\n".join(rows) + "\n</table>")


def picture(folder, live=None, langs=""):
    alt = gallery.alt(gallery.load(folder, {}, live, langs)).replace('"', "&quot;")
    return ('<a href="catalog/active/"><picture>'
            '<source media="(max-width: 600px) and (prefers-color-scheme: light)" srcset="docs/assets/plugins-light-narrow.svg">'
            '<source media="(max-width: 600px)" srcset="docs/assets/plugins-dark-narrow.svg">'
            '<source media="(prefers-color-scheme: light)" srcset="docs/assets/plugins-light.svg">'
            f'<img src="docs/assets/plugins-dark.svg" width="100%" alt="{alt}"></picture></a>')


def swap(text, start, end, body):
    a, b = text.find(start), text.find(end)
    if a < 0 or b < a:
        raise SystemExit(f"README.md needs {start} and {end}")
    return text[:a + len(start)] + "\n" + body + "\n" + text[b:]


def render(text, folder, live=None, langs=""):
    text = swap(text, START, END, table(folder, live, langs))
    if GSTART in text:
        text = swap(text, GSTART, GEND, picture(folder, live, langs))
    return text


def main():
    readme = root / "README.md"
    old = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
    new = render(old, root / "catalog" / "active", gallery.live_ids(), gallery.released_languages())
    if "--check" in sys.argv:
        if new != old:
            print("README.md plugin table is out of date. Run: python .github/scripts/readme_list.py")
            sys.exit(1)
        print("README.md plugin table is up to date")
        return
    if new != old:
        readme.write_text(new, encoding="utf-8", newline="\n")
        print("README.md plugin table updated")
    else:
        print("README.md plugin table already up to date")


if __name__ == "__main__":
    main()
