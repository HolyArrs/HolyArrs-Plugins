"""languages.py with a throwaway key: index, check and sign."""
import base64
import bz2
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import languages  # noqa: E402


def signed(sk, body):
    p = json.dumps(body).encode()
    return json.dumps({"payload": base64.b64encode(p).decode(), "signature": base64.b64encode(sk.sign(p)).decode()})


class LanguagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.root = self.tmp.name
        os.makedirs(os.path.join(d, languages.SOURCE_DIR), exist_ok=True)
        os.makedirs(os.path.join(d, "catalog", "active"))
        self.site = os.path.join(d, "site")
        os.makedirs(self.site)
        self.sk = Ed25519PrivateKey.generate()
        raw = self.sk.private_bytes_raw()
        self.key, self.pub = os.path.join(d, "k"), os.path.join(d, "k.pub")
        open(self.key, "w").write(base64.b64encode(raw).decode())
        open(self.pub, "w").write(base64.b64encode(self.sk.public_key().public_bytes_raw()).decode())
        open(os.path.join(self.site, "blocklist.json"), "w").write(signed(self.sk, {"kind": "blocklist", "counter": 3, "entries": []}))
        keys = ["a.hello", "a.name"]
        self.fit = hashlib.sha256(json.dumps(keys, separators=(",", ":")).encode()).hexdigest()[:12]
        os.makedirs(os.path.join(d, languages.SOURCE_DIR, "source"))
        with open(os.path.join(d, languages.SOURCE_DIR, "source", "en.json"), "w") as f:
            json.dump({"lang": "en", "fit": self.fit, "keys": keys, "values": ["Hello", "Hi <b>{name}</b>"]}, f)
        self.write("1.3.0")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, app, text="Hallo", second=None):
        for c in ("de", "pt-br"):
            with open(os.path.join(self.root, languages.SOURCE_DIR, c + ".json"), "w") as f:
                json.dump({"lang": c, "app": app, "fit": self.fit, "values": [text, second]}, f)

    def test_refuses_other_tags_or_slots(self):
        for bad in ("Hallo <i>{name}</i>", "Hallo <b>{nom}</b>", "Hallo {name}"):
            self.write("1.3.0", second=bad)
            self.assertIn("other slots or tags", self.sign()[1], bad)
        self.write("1.3.0", second="<b>{name}</b> hallo")
        self.assertEqual(self.sign()[0], 0)

    def test_blocklist_entry_without_version_blocks_every_version(self):
        for entry in ({"id": "lang-de"}, {"id": "lang-de", "version": None}, {"id": "lang-de", "version": ""}):
            open(os.path.join(self.site, "blocklist.json"), "w").write(
                signed(self.sk, {"kind": "blocklist", "counter": 3, "entries": [entry]}))
            self.assertIn("on the blocklist", self.sign()[1], entry)
        open(os.path.join(self.site, "blocklist.json"), "w").write(
            signed(self.sk, {"kind": "blocklist", "counter": 3, "entries": [{"id": "lang-de", "version": "1.2.0"}]}))
        self.assertEqual(self.sign()[0], 0)

    def rotate_site(self, plugin_entries=()):
        open(os.path.join(self.site, "blocklist.json"), "w").write(
            signed(Ed25519PrivateKey.generate(), {"kind": "blocklist", "counter": 3, "entries": []}))
        for n in languages.PLUGIN_LISTS:
            open(os.path.join(self.site, n), "w").write(signed(Ed25519PrivateKey.generate(), {
                "kind": "plugins", "counter": 4, "min_blocklist_counter": 3, "entries": list(plugin_entries)}))
        return self.run_cmd("rotate", "--out", self.site, "--key", self.key)

    def test_rotate_resigns_empty_lists_one_up(self):
        self.assertEqual(self.rotate_site()[0], 0)
        for n in languages.PLUGIN_LISTS:
            p = json.loads(base64.b64decode(json.load(open(os.path.join(self.site, n)))["payload"]))
            self.assertEqual((p["counter"], p["min_blocklist_counter"], p["entries"]), (5, 4, []))
        self.assertEqual(self.sign()[0], 0)  # the new blocklist verifies with the pinned key

    def test_rotate_refuses_lists_with_entries(self):
        self.assertIn("only replaces empty lists", self.rotate_site([{"id": "x", "version": "1.0.0"}])[1])

    def run_cmd(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = languages.main([*args, "--root", self.root, "--pub", self.pub])
        return code, err.getvalue()

    def sign(self):
        return self.run_cmd("sign", "--out", self.site, "--key", self.key, "--live-url", "")

    def listed(self):
        raw = json.load(open(os.path.join(self.site, "languages.json")))
        return json.loads(base64.b64decode(raw["payload"]))

    def test_index_and_check(self):
        self.assertEqual(self.run_cmd("check")[0], 1)
        self.assertEqual(self.run_cmd("index")[0], 0)
        self.assertEqual(self.run_cmd("check")[0], 0)
        idx = json.load(open(os.path.join(self.root, "catalog", "active", "language-packs.json")))
        self.assertEqual((idx["app"], [x["code"] for x in idx["languages"]]), ("1.3.0", ["de", "pt-br"]))
        self.write("1.3.0", text="Anders")
        self.assertEqual(self.run_cmd("check")[0], 1)

    def test_sign_counter_and_immutability(self):
        self.assertEqual(self.sign()[0], 0)
        p = self.listed()
        self.assertEqual((p["kind"], p["counter"], p["min_blocklist_counter"]), ("languages", 1, 3))
        packed = open(os.path.join(self.site, "languages", "de", "1.3.0.json.bz2"), "rb").read()
        self.assertEqual(json.loads(bz2.decompress(packed))["lang"], "de")
        self.assertEqual(p["entries"][0]["size"], len(packed))
        self.assertIn("nothing to sign", self.sign()[1])
        self.write("1.3.0", text="Anders")
        self.assertIn("never changes", self.sign()[1])
        self.write("1.3.1")
        self.assertEqual(self.sign()[0], 0)
        self.assertEqual((self.listed()["counter"], len(self.listed()["entries"])), (2, 4))

    def test_refuses_another_key(self):
        other = Ed25519PrivateKey.generate()
        open(self.key, "w").write(base64.b64encode(other.private_bytes_raw()).decode())
        self.assertIn("not the pinned key", self.sign()[1])
        self.assertFalse(os.path.exists(os.path.join(self.site, "languages.json")))

    def test_refuses_bad_file(self):
        with open(os.path.join(self.root, languages.SOURCE_DIR, "fr.json"), "w") as f:
            json.dump({"lang": "de", "app": "1.3.0", "fit": "x", "values": ["a"]}, f)
        self.assertIn("needs lang", self.sign()[1])


if __name__ == "__main__":
    unittest.main()
