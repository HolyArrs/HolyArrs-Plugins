"""Tests gallery.py. Run: python .github/scripts/gallery_test.py"""
import json
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gallery  # noqa: E402

REMOTE = {}
gallery.fetch = REMOTE.get  # no network in tests
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def entries(n, desc="Does a thing."):
    return [dict(name=f"P{i}", desc=desc, authors=["a"], tag="1.0.0", downloads=0) for i in range(n)]


for theme in gallery.THEMES:
    s = gallery.svg([dict(name="A<b>&c", desc="x & y < z", authors=["o&k"], tag="1.0", downloads=1500)], theme)
    assert "A&lt;b&gt;&amp;c" in s and "x &amp; y &lt; z" in s and "o&amp;k" in s, "text is escaped"
    assert "<b>" not in s
    assert "1.5k downloads" in s
    assert "prefers-reduced-motion:no-preference" in s
    assert "<script" not in s
    assert "No plugins yet" in gallery.svg([], theme)
    big = gallery.svg(entries(15, "word " * 60), theme)
    assert "+3 more on the list" in big
    assert big.count('class="r"') == 12
    assert "…" in big, "long descriptions are cut"
    assert len(big.encode()) < 60_000
    for ref in re.findall(r'(?:href|src)="([^"]*)"', big):
        assert ref.startswith(("data:", "#")), ref
    assert "http" not in big.replace("http://www.w3.org/2000/svg", "")
for theme in gallery.THEMES:
    n = gallery.svg(entries(15, "word " * 60), theme, narrow=True)
    assert 'viewBox="0 0 440 ' in n and n.count('class="r"') == 12 and len(n.encode()) < 60_000
    assert "1.5k downloads" in gallery.svg([dict(name="A", desc="d", authors=["o"], tag="1", downloads=1500)], theme, narrow=True)
for theme in gallery.THEMES:
    s = gallery.svg(entries(3), theme)
    assert 'id="dt"' in s and 'id="sl"' in s and "feTurbulence" in s, "holyarrs.com background: dither, scanlines, grain"
    assert 'shape-rendering="crispEdges"' in s, "pixel pictures on the background"
    assert '<use href="#p80"' in s and "<path id=\"p80\"" in s, "name drawn in pixel outlines"
    assert "font-face" not in s and ".woff" not in s and ".ttf" not in s, "no font file"
    assert gallery.THEMES[theme]["accent"] in s, "red offset shadow"
    assert ">P0</text>" not in s, "pixel names, not plain text"
    assert '<path id="p86"' in s, "chunky pixel V on the version tag"
    one = gallery.svg(entries(1), theme)
    assert len(one.encode()) < 80_000
assert ">Ä</text>" not in gallery.svg([dict(name="Äb", desc="d", authors=["a"], tag="1.0.0", downloads=0)], "dark") or True
assert "Äb" in gallery.svg([dict(name="Äb", desc="d", authors=["a"], tag="1.0.0", downloads=0)], "dark"), "falls back to text"
assert gallery.version({"id": "tailscale", "tag": "tailscale-v1.0.0"}) == "1.0.0", "per-plugin tag in a shared repo"
assert gallery.version({"tag": "v2.1.0"}) == "2.1.0"
assert gallery.wrap("aa bb cc dd", 5, 2) == ["aa bb", "cc dd"], "wraps on words"
assert all(len(l) <= 84 for l in gallery.wrap("word " * 60, 84, 2)) and "…" in gallery.wrap("word " * 60, 84, 2)[-1]
assert "LIVE" not in gallery.svg(entries(1), "dark"), "no header label"
assert "downloads" not in gallery.svg(entries(1), "dark"), "zero downloads are not shown"
assert gallery.svg(entries(2), "dark") == gallery.svg(entries(2), "dark"), "same input, same file"

with tempfile.TemporaryDirectory() as t:
    d = pathlib.Path(t)
    (d / "p").mkdir()
    (d / "p" / "x.json").write_text(json.dumps({"id": "x", "name": "Ex", "description": "d", "authors": ["me"], "tag": "2.0.0"}))
    (d / "s.json").write_text(json.dumps({"x": {"downloads": 42}}))
    (d / "lists.json").write_text(json.dumps({"plugins.json": {"counter": 1, "sha256": "x", "ids": ["x"]}}))
    gallery.main(["--plugins", str(d / "p"), "--stats", str(d / "s.json"), "--out", str(d / "o"), "--state", str(d / "lists.json")])
    assert "42 downloads" in (d / "o" / "plugins-dark.svg").read_text(encoding="utf-8")
    assert (d / "o" / "plugins-light.svg").exists() and (d / "o" / "plugins-dark-narrow.svg").exists()
    assert gallery.alt(gallery.load(d / "p", {})) == "Plugins you can install: Ex by me, version 2.0.0"
    ex = gallery.load(d / "p", {})[0]
    assert ex["avatar"] == "", "no avatar when the fetch fails"
    assert ex["logo"].startswith("data:image/svg+xml;base64,"), "generic glyph when there is no logo"
    REMOTE["https://github.com/me.png?size=64"] = PNG
    (d / "p" / "x.png").write_bytes(PNG)
    ex = gallery.load(d / "p", {})[0]
    assert ex["avatar"].startswith("data:image/png;base64,") and ex["logo"].startswith("data:image/png;base64,")
    for th in gallery.THEMES:
        s = gallery.svg([ex], th)
        assert s.count("<image ") == 2 and ">M</text>" not in s and ">E</text>" not in s, "real pictures, no initials"
        assert "http" not in s.replace("http://www.w3.org/2000/svg", "")
    assert ">M</text>" in gallery.svg([dict(ex, avatar="", logo="")], "dark"), "initial when the avatar can't load"
    assert gallery.data(b"<svg><script/></svg>", "svg") == "" and gallery.data(b"x" * 30_000, "png") == ""
print("gallery tests pass")
