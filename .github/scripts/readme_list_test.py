"""Tests readme_list.py. Run: python .github/scripts/readme_list_test.py"""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import readme_list  # noqa: E402

REMOTE = {}
readme_list.fetch = REMOTE.get  # no network in tests

with tempfile.TemporaryDirectory() as t:
    d = pathlib.Path(t)
    (d / "b-plugin.json").write_text(json.dumps({"name": "Bee", "description": "Does a | thing.", "authors": ["x", "y"], "tag": "1.0.0"}))
    (d / "a-plugin.json").write_text(json.dumps({"name": "Ay", "description": "Does another.", "authors": ["z"], "tag": "2.0.0"}))
    (d / "README.md").write_text("ignored")
    out = readme_list.render("top\n<!-- plugins:start -->\nold\n<!-- plugins:end -->\nend\n", d)
    assert out.startswith("top\n<!-- plugins:start -->\n<table>\n<tr><th>Plugin</th>"), out
    assert out.endswith("<!-- plugins:end -->\nend\n"), out
    assert "old" not in out
    assert out.index("Ay") < out.index("Bee"), "rows are sorted by file name"
    assert "<td>Does a | thing.</td>" in out, "description lands in its own cell"
    assert "&nbsp;x</a>, <a" in out and "&nbsp;y</a>" in out, "every author is listed"
    assert '<td nowrap><a href="https://github.com/x"><img src="https://github.com/x.png?size=40" width="20" height="20" align="absmiddle" alt="">&nbsp;x</a>' in out,         "author picture and name share one link, joined by a no-break space"
    assert '<img src="docs/assets/plugin-glyph.svg" width="20" height="20" align="absmiddle" alt="Ay">&nbsp;Ay</a>' in out, "no logo file, generic glyph"
    row = next(line for line in out.splitlines() if "&nbsp;Ay<" in line)
    assert row.startswith("<tr><td nowrap><b>") and row.endswith("<td nowrap><code>2.0.0</code></td></tr>"), "one row per plugin, nowrap cells"
    (d / "a-plugin.png").write_bytes(b"png")
    withlogo = readme_list.render(out, d)
    assert '<a href="catalog/active/a-plugin.json"><img src="catalog/active/a-plugin.png" width="20" height="20" align="absmiddle" alt="Ay">&nbsp;Ay</a>' in withlogo,         "a checked-in logo shows on one line with the name"
    assert "b-plugin.png" not in withlogo
    (d / "a-plugin.png").unlink()
    raw = "https://raw.githubusercontent.com/o/r/" + "a" * 40 + "/p/"
    (d / "c-plugin.json").write_text(json.dumps({"name": "Cee", "repo": "https://github.com/o/r", "commit": "a" * 40,
                                                 "path": "p", "tag": "1.0.0"}))
    assert 'glyph.svg" width="20" height="20" align="absmiddle" alt="Cee"' in readme_list.render(out, d), "glyph when the source can't be read"
    REMOTE[raw + "holyarrs-plugin.json"] = json.dumps({"icon_file": "icon.svg"}).encode()
    assert 'glyph.svg" width="20" height="20" align="absmiddle" alt="Cee"' in readme_list.render(out, d), "glyph when the icon file doesn't load"
    REMOTE[raw + "icon.svg"] = b"<svg/>"
    assert f'<img src="{raw}icon.svg" width="20" height="20" align="absmiddle" alt="Cee">&nbsp;Cee</a>' in readme_list.render(out, d),         "the plugin's own icon at the pinned commit shows"
    REMOTE[raw + "holyarrs-plugin.json"] = json.dumps({"icon_file": "../x.svg"}).encode()
    assert 'glyph.svg" width="20" height="20" align="absmiddle" alt="Cee"' in readme_list.render(out, d), "icon paths can't leave the folder"
    (d / "c-plugin.json").unlink()
    g = readme_list.render("<!-- gallery:start -->\n<!-- gallery:end -->\n" + out, d)
    assert 'alt="Plugins you can install: Ay by z, version 2.0.0; Bee by x, y, version 1.0.0"' in g, g
    assert "plugins-dark-narrow.svg" in g, "phones get the narrow gallery"
    assert "<code>2.0.0</code>" in out
    assert readme_list.render(out, d) == out, "running twice changes nothing"
    (d / "a-plugin.json").write_text(json.dumps({"id": "a", "name": "Ay", "description": "Does another.", "authors": ["z"], "tag": "2.0.0"}))
    (d / "b-plugin.json").write_text(json.dumps({"id": "b", "name": "Bee", "description": "x", "authors": ["x"], "tag": "1.0.0"}))
    lv = readme_list.render("<!-- gallery:start -->\n<!-- gallery:end -->\n" + out, d, {"a"})
    assert "&nbsp;Ay<" in lv and "Bee" not in lv, "only plugins on the live list show"
    assert "No plugins yet" in readme_list.render(out, d, set()), "nothing live, nothing shown"
    st = pathlib.Path(t) / "lists.json"
    assert readme_list.gallery.live_ids(st) == set(), "no record, nothing live"
    st.write_text(json.dumps({"plugins.json": {"counter": 5, "sha256": "x"}}))
    assert readme_list.gallery.live_ids(st) == set(), "a record without ids, nothing live"
    st.write_text(json.dumps({"plugins.json": {"counter": 6, "sha256": "x", "ids": ["a"]}}))
    assert readme_list.gallery.live_ids(st) == {"a"}
    st.write_text(json.dumps({"languages.json": {"counter": 4, "sha256": "x", "released": ["1.3.0", "1.10.0"]}}))
    assert readme_list.gallery.released_languages(st) == "1.10.0", "newest released version"
    st.write_text(json.dumps({"languages.json": {"counter": 4, "sha256": "x", "released": []}}))
    assert readme_list.gallery.released_languages(st) == "", "test packs only, nothing released"
    cat = pathlib.Path(t) / "cat"
    (cat / "active").mkdir(parents=True)
    (cat / "active" / "language-packs.json").write_text(json.dumps({"name": "Language packs", "languages": [{"code": "ar"}, {"code": "de"}]}))
    base = "<!-- plugins:start -->\n<!-- plugins:end -->\n"
    assert "Language packs" not in readme_list.render(base, cat / "active", set(), ""), "no released packs, no row"
    lp = readme_list.render(base, cat / "active", set(), "1.3.0")
    assert "Language Packs" in lp and "<code>1.0.0</code>" in lp and "2 more languages" in lp, lp
    assert "No plugins yet" not in lp
    empty = pathlib.Path(t) / "empty"
    empty.mkdir()
    assert "No plugins yet" in readme_list.render(out, empty)
    try:
        readme_list.render("no markers", d)
        raise AssertionError("missing markers must fail")
    except SystemExit:
        pass

r = subprocess.run([sys.executable, str(HERE / "readme_list.py"), "--check"], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
print("readme_list tests pass")
