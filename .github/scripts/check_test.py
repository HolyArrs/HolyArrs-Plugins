"""Tests check.py on one entry file plus a plugin folder. Run: python .github/scripts/check_test.py"""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
GOOD = {
    "id": "demo-plugin", "name": "Demo", "author": "someone", "description": "Shows a demo.",
    "licence": "MIT", "support_email": "me@example.com", "min_app_version": "1.2.1", "icon_file": "icon.svg",
    "access": {"hosts": ["api.example.com"], "folders": [], "actions": []},
    "settings": [{"key": "api_key", "label": "API key", "type": "secret"},
                 {"key": "mode", "label": "Mode", "type": "select", "options": ["a", "b"], "default": "a"}],
}


def run(meta, extra=None, entry_extra=None):
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        entry = {"id": "demo-plugin", "name": "Demo", "description": "Shows a demo plugin.", "authors": ["someone"],
                 "repo": "https://github.com/someone/demo", "tag": "v1.0.0", "commit": "a" * 40, "min_app_version": "1.2.1"}
        (t / "demo-plugin.json").write_text(json.dumps({**entry, **(entry_extra or {})}))
        src = t / "src"
        src.mkdir()
        (src / "go.mod").write_text("module demo\n")
        (src / "holyarrs-plugin.json").write_text(json.dumps(meta))
        (src / "icon.svg").write_text("<svg/>")
        if extra:
            extra(t, src)
        r = subprocess.run([sys.executable, str(HERE / "check.py"), str(t / "demo-plugin.json"), "--src", str(src)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout


code, out = run(GOOD)
assert code == 0, out
code, out = run({**GOOD, "access": {"hosts": [], "folders": ["books", {"name": "music", "mode": "read_write", "why": "Tags files", "required": True}], "actions": []}})
assert code == 0, out
for change, want in [
    ({"name": "x" * 41}, "name is 41 characters"),
    ({"description": "a <b> tag"}, "plain text only"),
    ({"licence": ""}, "licence is required"),
    ({"sha256": "0" * 64}, "we fill it in when publishing"),
    ({"access": {"hosts": [], "folders": ["../up"], "actions": []}}, "unsafe folder"),
    ({"access": {"hosts": [], "folders": [{"name": "music", "mode": "write"}], "actions": []}}, "read or read_write"),
    ({"access": {"hosts": [], "folders": ["a/b"], "actions": []}}, "unsafe folder"),
    ({"access": {"hosts": [], "folders": [], "actions": ["library.read"]}}, "access.actions needs min_app_version 1.3.0"),
    ({"access": {"hosts": [], "folders": [], "actions": ["settings.change"]}, "min_app_version": "1.3.0"}, "unknown permission"),
    ({"access": {"hosts": [], "folders": [], "actions": ["library.read", "library.read"]}, "min_app_version": "1.3.0"}, "twice"),
    ({"settings": [{"key": "1abc", "label": "L", "type": "text"}]}, "starts with a letter"),
    ({"settings": [{"key": "pw", "label": "L", "type": "secret", "default": "x"}]}, "can't have a default"),
    ({"min_app_version": "1.1.0"}, "1.2.1 or newer"),
    ({"resources": {"memory_mib": 2048}}, "resources needs min_app_version 1.3.0"),
    ({"resources": {"gpu": 1}, "min_app_version": "1.3.0"}, "unknown keys"),
    ({"resources": {"cpus": 0}, "min_app_version": "1.3.0"}, "resources.cpus must be a whole number"),
    ({"resources": {"memory_mib": "2G"}, "min_app_version": "1.3.0"}, "resources.memory_mib must be a whole number"),
    ({"resources": {}, "min_app_version": "1.3.0"}, "resources must be an object"),
]:
    code, out = run({**GOOD, **change})
    assert code == 1 and want in out, (change, out)
code, out = run({**GOOD, "min_app_version": "1.3.0", "resources": {"memory_mib": 2048, "cpus": 2, "processes": 512, "open_files": 4096}})
assert code == 0, out
code, out = run({**GOOD, "min_app_version": "1.3.0", "access": {"hosts": [], "folders": [], "actions": ["library.read", "library.music.read", "network.forward"]}})
assert code == 0, out
code, out = run(GOOD, entry_extra={"version": "1.0.0"})
assert code == 0, out
code, out = run(GOOD, entry_extra={"version": "2.0.0"})
assert code == 1 and "is not the tag's version" in out, out
code, out = run(GOOD, entry_extra={"source": "holyarrs"})
assert code == 1 and "source" in out, out
code, out = run(GOOD, entry_extra={"tag": "demo-plugin-v1.0.0", "version": "1.0.0"})
assert code == 0, out
code, out = run(GOOD, entry_extra={"tag": "other-v1.0.0"})
assert code == 1 and "tag must be a version" in out, out
for icon in ["../x.png", "/etc/x.png", "a\b.png", "c:x.png", "a b.png", "a/../../x.png"]:
    code, out = run({**GOOD, "icon_file": icon})
    assert code == 1 and "unsafe icon_file" in out, (icon, out)


def png(t, src):
    (src / "logo.png").write_bytes(b"x")


code, out = run({**GOOD, "icon_file": "logo.png"}, png)
assert code == 0, out

try:
    def link_icon(t, src):
        (t / "outside.png").write_bytes(b"x")
        (src / "logo.png").symlink_to(t / "outside.png")

    def link_any(t, src):
        (src / "key").symlink_to(t)

    code, out = run({**GOOD, "icon_file": "logo.png"}, link_icon)
    assert code == 1 and "links are not allowed" in out, out
    code, out = run(GOOD, link_any)
    assert code == 1 and "links are not allowed" in out, out
except OSError as err:  # Windows without symlink rights
    print("symlink cases skipped:", err)
no_logo = {k: v for k, v in GOOD.items() if k != "icon_file"}
code, out = run(no_logo)
assert code == 1 and "a logo is required" in out, out
code, out = run({**no_logo, "icon_url": "https://example.com/logo.png"})
assert code == 0, out
code, out = run(no_logo, entry_extra={"icon_url": "https://example.com/logo.png"})
assert code == 0, out
print("check.py tests passed")
