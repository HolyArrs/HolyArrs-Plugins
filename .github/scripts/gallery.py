"""Draws the plugin gallery picture for the README, in a dark and a light version.

    python .github/scripts/gallery.py [--stats stats.json] [--out docs/assets]
    python .github/scripts/gallery.py --alt     print the picture's alt text

Reads catalog/active/*.json and, if given, stats.json (download counts). Writes
plugins-{dark,light}.svg and a narrow -narrow.svg pair for phones. The picture holds no outside links or
pictures (GitHub blocks those inside SVG) and no time stamp, so the file only
changes when a plugin, a picture or a download count changes. The plugin logo and each maker's GitHub
avatar are fetched once while drawing and embedded as data: links; the logo falls back to the generic
docs/assets/plugin-glyph.svg, an avatar to the maker's initial when it can't be fetched.
"""
import argparse
import base64
import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pixel_glyphs import GLYPHS  # noqa: E402
from xml.sax.saxutils import escape

root = pathlib.Path(__file__).resolve().parents[2]
MAX_ROWS = 12
W, ROW, TOP = 880, 76, 60

# holyarrs.com tokens (retro.css)
THEMES = {
    "dark": dict(bg="#1C1F22", vig="#16181B", card="#25292D", line="#EDEDEA", rule="#454B51", text="#EDEDEA",
                 muted="#B8BCC1", accent="#E5483C", on="#0B0D10", chip="#16181B", dither="#2C3135", icon="#3A4045",
                 scan="#000000", scano=".22", dto=".8", grain=".09"),
    "light": dict(bg="#F3F3F1", vig="#E9E9E6", card="#FFFFFF", line="#0B0D10", rule="#C9C9C5", text="#0B0D10",
                  muted="#4A4E55", accent="#C9271D", on="#FFFFFF", chip="#E9E9E6", dither="#D6D6D2", icon="#C4C4BF",
                  scan="#0B0D10", scano=".035", dto=".6", grain=".07"),
}
ICONS = {  # small pixel pictures scattered on the background, as on holyarrs.com
    "note": ["...####", "...#..#", "...#..#", "...#..#", ".###.##", "####.##", ".##...."],
    "star": ["...#...", "..###..", "#######", ".#####.", ".##.##.", "##...##"],
    "play": ["#....", "###..", "#####", "###..", "#...."],
    "tv": [".#...#.", "..#.#..", "#######", "#.....#", "#.....#", "#######"],
}


def x(s):
    return escape(str(s), {'"': "&quot;"})


def cut(s, n=90):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1].rstrip(" ,.;") + "…"


def count(n):
    for size, unit in ((1_000_000, "M"), (1000, "k")):
        if n >= size:
            return f"{n / size:.1f}".rstrip("0").rstrip(".") + unit
    return str(n)


GLYPH = root / "docs" / "assets" / "plugin-glyph.svg"
MAX_PIC = 20_000


def fetch(url):
    """The bytes at url, or None."""
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def data(raw, kind):
    """A data: link for small PNG, JPEG, WebP or SVG bytes, else ""."""
    if not raw or len(raw) > MAX_PIC:
        return ""
    mime = ("image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg" if raw[:3] == b"\xff\xd8\xff"
            else "image/webp" if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
            else "image/svg+xml" if kind == "svg" and b"<svg" in raw[:400] and b"<script" not in raw.lower() else "")
    return f"data:{mime};base64," + base64.b64encode(raw).decode() if mime else ""


def logo(folder, f, e):
    """The plugin's logo: a checked-in <id>.png/.svg, its icon at the pinned commit, or the generic glyph."""
    for ext in ("png", "svg"):
        q = pathlib.Path(folder) / f"{f.stem}.{ext}"
        if q.exists():
            d = data(q.read_bytes(), ext)
            if d:
                return d
    import readme_list  # reads the icon_file at the pinned commit
    url = readme_list.remote_logo(e)
    d = data(fetch(url), url.rsplit(".", 1)[-1]) if url else ""
    return d or (data(GLYPH.read_bytes(), "svg") if GLYPH.exists() else "")


def avatar(login):
    if not all(ch.isalnum() or ch == "-" for ch in login) or not login:
        return ""
    return data(fetch(f"https://github.com/{login}.png?size=64"), "png")


def version(e):
    """The plugin's own version, from its tag: 1.0.0, v1.0.0 or <id>-v1.0.0."""
    t = str(e.get("tag") or "")
    pid = str(e.get("id") or "")
    if pid and t.startswith(pid + "-"):
        t = t[len(pid) + 1:]
    return t.removeprefix("v")


STATE = pathlib.Path(__file__).resolve().parents[1] / "state" / "lists.json"


def live_ids(state=STATE):
    """The plugin ids on the live signed list, as recorded after every publish in .github/state/lists.json.
    A missing file, or a record without ids, means nothing is live."""
    try:
        rec = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))
        return set(rec.get("plugins.json", {}).get("ids") or [])
    except Exception:
        return set()


LANGS = "language-packs.json"  # Language packs sit in catalog/active like a plugin, with their own list


def released_languages(state=STATE):
    """The newest released language pack version on the live languages.json, or "" when only test packs are live."""
    try:
        vs = json.loads(pathlib.Path(state).read_text(encoding="utf-8")).get("languages.json", {}).get("released") or []
    except Exception:
        return ""
    return max(vs, key=lambda v: [int(x) if x.isdigit() else 0 for x in str(v).split(".")]) if vs else ""


def language_entry(catalog, ver):
    """Language packs as a catalog-style entry, from catalog/active/language-packs.json, for a released version."""
    try:
        n = len(json.loads((pathlib.Path(catalog) / LANGS).read_text(encoding="utf-8")).get("languages") or [])
    except Exception:
        return None
    if not ver or not n:
        return None
    return {"id": "language-packs", "name": "Language Packs", "authors": ["CoderLuii"], "tag": ver,
            "description": f"HolyArrs in {n} more languages. Pick one during setup or under System > Plugins."}


def load(folder, stats, live=None, langs=""):
    """The catalog entries to show. With live (a set of ids), only plugins on the live signed list.
    With langs (a released language pack version), Language packs is added at the end."""
    out = []
    lang = language_entry(folder, langs)
    for f in sorted(x for x in pathlib.Path(folder).glob("*.json") if x.name != LANGS) + ([None] if lang else []):
        if f is None:
            e, f = lang, pathlib.Path(folder) / "language-packs.json"
            s = stats.get("language-packs") if isinstance(stats, dict) else None
            d = s.get("downloads", 0) if isinstance(s, dict) else 0
            out.append(dict(name=e["name"], desc=e["description"], authors=e["authors"], tag=e["tag"],
                            downloads=d if isinstance(d, int) else 0, logo=logo(folder, f, e),
                            avatar=avatar(e["authors"][0])))
            continue
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(e, dict):
            continue
        if live is not None and e.get("id", f.stem) not in live:
            continue
        s = stats.get(e.get("id", f.stem)) if isinstance(stats, dict) else None
        d = s.get("downloads", 0) if isinstance(s, dict) else 0
        authors = [str(a) for a in e.get("authors") or []]
        out.append(dict(name=str(e.get("name", f.stem)), desc=e.get("description", ""),
                        authors=authors, tag=version(e),
                        downloads=d if isinstance(d, int) else 0,
                        logo=logo(folder, f, e), avatar=avatar(authors[0]) if authors else ""))
    return out


def alt(plugins):
    if not plugins:
        return "Plugins you can install: none yet"
    return "Plugins you can install: " + "; ".join(
        f"{p['name']} by {', '.join(p['authors']) or 'unknown'}, version {p['tag']}" for p in plugins)


def wrap(s, n, lines):
    """Splits s into at most `lines` lines of about n characters, cutting the last one."""
    words, out, cur = " ".join(str(s).split()).split(" "), [], ""
    for i, w in enumerate(words):
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
            if len(out) == lines:
                return out[:-1] + [cut(out[-1] + " " + " ".join(words[i:]), n)]
        else:
            cur = (cur + " " + w).strip()
    return out + [cur] if cur else out


def pixel(text, x0, y, size, fill, used, anchor="start"):
    """Pixel-font text drawn as outline paths (no font file); None when a character has no glyph."""
    t = str(text).upper()
    if not t or any(ch not in GLYPHS for ch in t):
        return None
    k, track = size / 100, size * .16
    adv = [GLYPHS[ch][0] * k + track for ch in t]
    width = sum(adv) - track
    cx = x0 - (width / 2 if anchor == "middle" else width if anchor == "end" else 0)
    out = []
    for ch, a in zip(t, adv):
        if GLYPHS[ch][1]:
            used.add(ch)
            out.append(f'<use href="#p{ord(ch)}" transform="translate({cx:.1f} {y:.1f}) scale({k:.2f})"/>')
        cx += a
    return f'<g fill="{fill}">' + "".join(out) + "</g>", width


def icon(name, x0, y, s, col):
    d = "".join(f"M{cx} {r}h1v1h-1z" for r, row in enumerate(ICONS[name]) for cx, ch in enumerate(row) if ch == "#")
    return f'<path transform="translate({x0} {y}) scale({s})" d="{d}" fill="{col}" shape-rendering="crispEdges"/>'


def background(w, h, c):
    """The holyarrs.com backdrop: 4px dither, scanlines, a soft vignette, a faint grain and pixel pictures."""
    defs = (f'<pattern id="dt" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 0h2v2H0zM2 2h2v2H2z" fill="{c["dither"]}" fill-opacity="{c["dto"]}"/></pattern>'
            f'<pattern id="sl" width="3" height="3" patternUnits="userSpaceOnUse"><rect y="2" width="3" height="1" fill="{c["scan"]}" fill-opacity="{c["scano"]}"/></pattern>'
            f'<radialGradient id="v" cx=".5" cy=".45" r=".75"><stop offset=".5" stop-color="{c["vig"]}" stop-opacity="0"/><stop offset="1" stop-color="{c["vig"]}" stop-opacity=".9"/></radialGradient>'
            '<filter id="gr" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="7" stitchTiles="stitch"/>'
            '<feColorMatrix values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 2.2 0 0 0 -1"/><feComposite in="SourceGraphic" operator="in"/></filter>')
    body = [f'<rect width="{w}" height="{h}" rx="6" fill="{c["bg"]}"/>', f'<rect width="{w}" height="{h}" rx="6" fill="url(#dt)"/>',
            f'<rect width="{w}" height="{h}" rx="6" fill="url(#v)"/>', f'<rect width="{w}" height="{h}" rx="6" fill="url(#sl)"/>',
            f'<rect width="{w}" height="{h}" rx="6" fill="{c["text"]}" filter="url(#gr)" opacity="{c["grain"]}"/>']
    names = ("star", "note", "play", "tv")
    spots = [(names[i % 4], round(w * f), 5) for i, f in enumerate((.18, .47, .81))]
    spots += [(names[(i + 2) % 4], round(w * f), h - 19) for i, f in enumerate((.09, .56, .9))]
    body += [icon(n, sx, sy, 2, c["icon"]) for n, sx, sy in spots]
    return defs, body


def chip(label, tx, y, c, used):
    """Chunky pixel version tag: red block with an ink offset shadow."""
    pt = pixel(label, 0, 0, 13, "#FFFFFF", set())
    bw = (pt[1] if pt else 7.5 * len(label)) + 16
    o = [f'<rect x="{tx + 3:.0f}" y="{y + 3}" width="{bw:.0f}" height="22" fill="{c["line"]}"/>',
         f'<rect x="{tx:.0f}" y="{y}" width="{bw:.0f}" height="22" fill="{c["accent"]}"/>']
    if pt:
        o.append(pixel(label, tx + bw / 2, y + 16, 13, "#FFFFFF", used, "middle")[0])
    else:
        o.append(f'<text x="{tx + bw / 2:.0f}" y="{y + 15.5}" text-anchor="middle" class="v" fill="#FFFFFF">{x(label)}</text>')
    return o


def svg(plugins, theme, narrow=False):
    c = THEMES[theme]
    w = 440 if narrow else W
    lines = 3 if narrow else 2
    per = 46 if narrow else 84
    shown = plugins[:MAX_ROWS]
    more = len(plugins) - len(shown)
    rowh = 58 + lines * 21 + (24 if narrow else 0)
    pad, gap = 24, 16
    h = pad + max(len(shown), 1) * (rowh + gap) + (44 if more else 0) + pad - gap + 4
    used, rows = set(), []
    if not shown:
        rows.append(f'<text x="{w / 2}" y="{pad + rowh / 2 + 6:.0f}" text-anchor="middle" class="nm" fill="{c["muted"]}">No plugins yet</text>')
    for i, p in enumerate(shown):
        y = pad + i * (rowh + gap)
        cw = w - 2 * pad - 4
        name = cut(p["name"], 22 if narrow else 28)
        tag = cut(p["tag"], 16)
        rows += [f'<g class="r" style="animation-delay:{i * 80}ms">',
                 f'<rect x="{pad + 4}" y="{y + 4}" width="{cw}" height="{rowh}" fill="{c["accent"]}"/>',
                 f'<rect x="{pad + .75}" y="{y + .75}" width="{cw - 1.5}" height="{rowh - 1.5}" fill="{c["card"]}" stroke="{c["line"]}" stroke-width="1.5"/>',
                 f'<rect x="{pad + 15.5}" y="{y + 13.5}" width="31" height="31" fill="{c["chip"]}" stroke="{c["line"]}"/>']
        if p.get("logo", "").startswith("data:"):
            rows.append(f'<image x="{pad + 18}" y="{y + 16}" width="26" height="26" href="{x(p["logo"])}"/>')
        else:
            rows += [f'<rect x="{pad + 16}" y="{y + 14}" width="30" height="30" fill="{c["accent"]}"/>',
                     f'<text x="{pad + 31}" y="{y + 35}" text-anchor="middle" class="i" fill="{c["on"]}">{x((p["name"] or "?")[0].upper())}</text>']
        nx = pad + 60
        pt = pixel(name, nx, y + 37, 20, c["text"], used)
        if pt:
            rows.append(pt[0])
            nw = pt[1]
        else:
            rows.append(f'<text x="{nx}" y="{y + 37}" class="nm" fill="{c["text"]}">{x(name)}</text>')
            nw = len(name) * 10
        if tag:
            rows += chip("V" + tag if tag[:1].isdigit() else tag, nx + nw + 14, y + 17, c, used)
        for j, ln in enumerate(wrap(p["desc"], per, lines)):
            rows.append(f'<text x="{pad + 18}" y="{y + 70 + j * 21}" class="d" fill="{c["muted"]}">{x(ln)}</text>')
        by = x(cut(", ".join(p["authors"]), 24))
        dl = f"{count(p['downloads'])} downloads" if p["downloads"] > 0 else ""
        if narrow:
            meta = " · ".join(v for v in (f"by {by}" if by else "", dl) if v)
            rows.append(f'<text x="{pad + 18}" y="{y + rowh - 16}" class="d" fill="{c["text"]}">{meta}</text>')
        else:
            ex = w - pad - 22
            rows.append(f'<text x="{ex}" y="{y + 35}" text-anchor="end" class="d" fill="{c["text"]}">{by}</text>')
            bx = ex - 8.4 * len(by) - 20
            if by and p.get("avatar", "").startswith("data:"):
                rows += [f'<image x="{bx - 11:.0f}" y="{y + 18}" width="22" height="22" href="{x(p["avatar"])}"/>',
                         f'<rect x="{bx - 11.5:.0f}" y="{y + 17.5}" width="23" height="23" fill="none" stroke="{c["line"]}"/>']
            elif by:
                rows += [f'<rect x="{bx - 11.5:.0f}" y="{y + 17.5}" width="23" height="23" fill="{c["chip"]}" stroke="{c["line"]}"/>',
                         f'<text x="{bx:.0f}" y="{y + 33.5}" text-anchor="middle" class="v" fill="{c["text"]}">{x(by[0].upper())}</text>']
            if dl:
                rows.append(f'<text x="{bx - 20:.0f}" y="{y + 35}" text-anchor="end" class="d" fill="{c["muted"]}">{dl} ·</text>')
        rows.append("</g>")
    if more:
        y = pad + len(shown) * (rowh + gap)
        rows.append(f'<text x="{w / 2}" y="{y + 24}" text-anchor="middle" class="d" fill="{c["muted"]}">+{more} more on the list</text>')
    bdefs, back = background(w, h, c)
    glyphs = "".join(f'<path id="p{ord(ch)}" d="{GLYPHS[ch][1]}"/>' for ch in sorted(used))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{x(alt(plugins))}">',
         "<style>text{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",system-ui,\"Noto Sans\",Ubuntu,sans-serif}"
         ".nm{font-size:19px;font-weight:600}.d{font-size:16px}.v{font-size:13px;font-weight:700}.i{font-size:15px;font-weight:700}"
         "@media (prefers-reduced-motion:no-preference){.r{animation:in .3s steps(3,end) backwards}}"
         "@keyframes in{from{opacity:.4;transform:translateY(6px)}}</style>",
         f"<defs>{glyphs}{bdefs}</defs>", *back, *rows, "</svg>"]
    return "\n".join(o) + "\n"


def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument("--stats")
    a.add_argument("--out", default=str(root / "docs" / "assets"))
    a.add_argument("--plugins", default=str(root / "catalog" / "active"))
    a.add_argument("--alt", action="store_true")
    a.add_argument("--state", default=str(STATE), help="the record of the live lists; only plugins on it are drawn")
    o = a.parse_args(argv)
    stats = {}
    if o.stats and pathlib.Path(o.stats).exists():
        try:
            stats = json.loads(pathlib.Path(o.stats).read_text(encoding="utf-8"))
        except Exception:
            stats = {}
    plugins = load(o.plugins, stats, live_ids(o.state), released_languages(o.state))
    if o.alt:
        print(alt(plugins))
        return
    out = pathlib.Path(o.out)
    out.mkdir(parents=True, exist_ok=True)
    for t in THEMES:
        (out / f"plugins-{t}.svg").write_text(svg(plugins, t), encoding="utf-8", newline="\n")
        (out / f"plugins-{t}-narrow.svg").write_text(svg(plugins, t, narrow=True), encoding="utf-8", newline="\n")
    print(f"gallery: {len(plugins)} plugin(s) drawn to {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
