"""Tests for images.py: run with python3 .github/scripts/images_test.py"""
import io, os, pathlib, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import images
from PIL import Image


def pic(fmt, size=(300, 200), mode="RGBA"):
    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30)).save(buf, fmt)
    return buf.getvalue()


def refused(fn, *a):
    try:
        fn(*a)
    except images.Bad:
        return True
    return False


out = pathlib.Path(tempfile.mkdtemp())
for fmt, mode in (("PNG", "RGBA"), ("JPEG", "RGB"), ("WEBP", "RGBA")):
    images.logo("disk-guard", pic(fmt, mode=mode), out)
    for s in (128, 256):
        f = out / "images" / "disk-guard" / f"icon-{s}.webp"
        im = Image.open(f)
        assert im.format == "WEBP" and im.size == (s, s), (fmt, im.format, im.size)
        assert f.stat().st_size <= images.OUT_MAX
        assert not im.info.get("exif"), "metadata must be dropped"

images.avatar("CoderLuii", pic("PNG", (460, 460)), out)
assert Image.open(out / "images" / "avatars" / "CoderLuii-64.webp").size == (64, 64)

# Refused: not a picture, HTML posing as one, too big, too small, bad names, plain http.
assert refused(images.logo, "x", b"<html><script>alert(1)</script>", out)
assert refused(images.logo, "x", b"GIF89a" + b"\0" * 40, out)
assert refused(images.logo, "x", pic("PNG", (8, 8)), out)
assert refused(images.logo, "x", pic("PNG", (5000, 20)), out)
assert refused(images.logo, "x", b"\x89PNG\r\n\x1a\n" + b"broken" * 10, out)
assert refused(images.logo, "../evil", pic("PNG"), out)
assert refused(images.avatar, "bad/login", pic("PNG"), out)
assert refused(images.fetch, "http://example.com/a.png")
assert refused(images.open_picture, b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]><svg/>')
assert images.kind(b"  <svg xmlns='http://www.w3.org/2000/svg'/>") == "svg"
# Outside links are refused before drawing; links inside the SVG (#id) are fine to reach the drawing step.
for bad in (b'<svg><image href="https://evil.example/a.png"/></svg>', b"<svg><image xlink:href='file:///etc/passwd'/></svg>",
            b'<svg><style>@import "https://evil.example/a.css";</style></svg>', b'<svg><rect fill="url(https://evil.example/p.svg#a)"/></svg>'):
    assert refused(images.open_picture, bad), bad

try:
    import cairosvg  # noqa: F401
except Exception:
    print("cairosvg missing here: SVG drawing checked in the workflow only")
else:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0f766e"/><script>alert(1)</script></svg>'
    images.logo("svg-one", svg, out)
    assert Image.open(out / "images" / "svg-one" / "icon-256.webp").size == (256, 256)
    outside = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="https://evil.example/a.png" width="64" height="64"/></svg>'
    assert refused(images.logo, "svg-two", outside, out)

root = pathlib.Path(tempfile.mkdtemp())
(root / "catalog" / "active").mkdir(parents=True)
(root / "catalog" / "active" / "a.json").write_text('{"authors": ["CoderLuii", "x/y"]}')
(root / "catalog" / "active" / "b.json").write_text('{"authors": ["CoderLuii", "Other-One"]}')
assert images.authors(root) == ["CoderLuii", "Other-One"]
print("images ok")
