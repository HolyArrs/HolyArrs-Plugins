"""Plugin logos and developer pictures for plugins.holyarrs.com.

HolyArrs never loads a picture from github.com or an author's site in a
user's browser. This step fetches each picture once, checks it, resizes it
and writes small WebP copies into the site tree; the app reads them from
there through its own server.

  images.py logo    --id ID (--url URL | --file PATH) --out SITE
        writes SITE/images/<id>/icon-128.webp and icon-256.webp
  images.py avatars --out SITE LOGIN...
        writes SITE/images/avatars/<login>-64.webp from github.com/<login>.png
  images.py authors ROOT
        prints every GitHub login named in ROOT/catalog/active/*.json

Accepted: PNG, JPEG, WebP and SVG, up to 2 MB and 4096 x 4096. SVG is drawn
to pixels (scripts, links and outside files are never followed), so only
plain pixels reach the site. Needs Pillow and CairoSVG.
"""
import argparse
import io
import json
import os
import pathlib
import re
import sys
import urllib.request

from PIL import Image

MAX_BYTES = 2 << 20
MAX_SIDE = 4096
OUT_MAX = 256 << 10            # the app refuses anything larger
LOGO_SIZES = (128, 256)
AVATAR_SIZE = 64
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
Image.MAX_IMAGE_PIXELS = MAX_SIDE * MAX_SIDE


class Bad(Exception):
    pass


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise Bad(f"redirect to {newurl} is not https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    """GETs an https picture, at most MAX_BYTES."""
    if not url.startswith("https://"):
        raise Bad("the picture address must start with https://")
    opener = urllib.request.build_opener(_HttpsOnly)
    req = urllib.request.Request(url, headers={"User-Agent": "holyarrs-plugins"})
    with opener.open(req, timeout=30) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise Bad("the picture is larger than 2 MB")
    return data


def kind(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:4096].lower()):
        return "svg"
    raise Bad("the picture must be PNG, JPEG, WebP or SVG")


def open_picture(data):
    k = kind(data)
    if k == "svg":
        low = data.lower()
        if b"<!doctype" in low or b"<!entity" in low:
            raise Bad("the SVG may not use DOCTYPE or ENTITY")
        # Everything must be drawn inside the SVG: no outside pictures, fonts or styles.
        if re.search(rb"(?:href|src)\s*=\s*[\"']\s*(?!#)|url\(\s*[\"']?\s*(?![#\"'])|@import", low):
            raise Bad("the SVG links to an outside file; draw everything inside the SVG")
        import cairosvg  # only needed for SVG; unsafe=False never reads files or the network
        try:
            data = cairosvg.svg2png(bytestring=data, output_width=512, output_height=512, unsafe=False)
        except Exception as err:
            raise Bad(f"the SVG could not be drawn ({err.__class__.__name__})") from None
    try:
        im = Image.open(io.BytesIO(data))
        if im.format not in ("PNG", "JPEG", "WEBP"):
            raise Bad("the picture must be PNG, JPEG, WebP or SVG")
        if max(im.size) > MAX_SIDE or min(im.size) < 16:
            raise Bad("the picture must be between 16 and 4096 pixels on each side")
        im.seek(0)  # an animated picture keeps its first frame
        im.load()
    except Bad:
        raise
    except Exception as err:  # broken or hostile file
        raise Bad(f"the picture could not be read ({err.__class__.__name__})") from None
    return im.convert("RGBA")


def square(im, size):
    """Fits the picture into a size x size transparent square, centred."""
    im = im.copy()
    im.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return canvas


def webp(im):
    for q in (88, 75, 60):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)  # no EXIF or other metadata is written
        if buf.tell() <= OUT_MAX:
            return buf.getvalue()
    raise Bad("the picture is still too large after compressing")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"wrote {path.as_posix()} ({len(data)} bytes)")


def logo(pid, data, out):
    if not ID_RE.match(pid):
        raise Bad("bad plugin id")
    im = open_picture(data)
    for s in LOGO_SIZES:
        write(pathlib.Path(out) / "images" / pid / f"icon-{s}.webp", webp(square(im, s)))


def avatar(login, data, out):
    if not LOGIN_RE.match(login):
        raise Bad(f"{login!r} is not a GitHub login")
    write(pathlib.Path(out) / "images" / "avatars" / f"{login}-{AVATAR_SIZE}.webp", webp(square(open_picture(data), AVATAR_SIZE)))


def authors(root):
    seen = []
    for f in sorted((pathlib.Path(root) / "catalog" / "active").glob("*.json")):
        if f.name == "language-packs.json":
            continue
        for a in json.loads(f.read_text(encoding="utf-8")).get("authors") or []:
            if LOGIN_RE.match(a) and a not in seen:
                seen.append(a)
    return seen


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("logo")
    lp.add_argument("--id", required=True)
    g = lp.add_mutually_exclusive_group(required=True)
    g.add_argument("--url")
    g.add_argument("--file")
    lp.add_argument("--out", required=True)
    vp = sub.add_parser("avatars")
    vp.add_argument("--out", required=True)
    vp.add_argument("logins", nargs="*")
    ap_ = sub.add_parser("authors")
    ap_.add_argument("root")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "logo":
            logo(a.id, fetch(a.url) if a.url else open(a.file, "rb").read(), a.out)
        elif a.cmd == "avatars":
            failed = 0
            for login in a.logins:
                try:
                    avatar(login, fetch(f"https://github.com/{login}.png?size=128"), a.out)
                except Exception as err:  # one missing picture never stops the rest; the app shows a letter
                    failed += 1
                    print(f"{login}: skipped ({err})")
            if a.logins and failed == len(a.logins):
                return 1
        else:
            print("\n".join(authors(a.root)))
    except Bad as err:
        print(f"refused: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
