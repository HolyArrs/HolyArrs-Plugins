import datetime as dt, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import stats

d = tempfile.mkdtemp(); st, out, rows = (os.path.join(d, n) for n in ("s.json", "o.json", "r.json"))


def row(n, path, date="2026-11-20"):
    return {"count": n, "dimensions": {"clientRequestPath": path, "date": date}}


json.dump([
    row(3, "/plugins/tailscale/1.0.0/plugin"),
    row(2, "/plugins/tailscale/1.0.0/linux-arm64/plugin"),
    row(4, "/plugins/tailscale/1.1.0/linux-arm-v7/plugin"),
    row(7, "/plugins/tailscale/1.0.0/manifest.json"),
    row(9, "/plugins.json"),
    row(5, "/source/tailscale/1.0.0.tar.xz"),
    row(1, "/plugins/other-one/2.0.0/plugin"),
], open(rows, "w"))
t = dt.datetime(2026, 11, 20, 10, 30, tzinfo=dt.timezone.utc)
U = "2026-11-20T10:30:00Z"
stats.main("apply", st, out, rows, now=t, stars={"tailscale": 12, "starred-only": 3}, root=d)
o = json.load(open(out))
assert o == {"other-one": {"downloads": 1, "week": 1, "updated": U},
             "starred-only": {"downloads": 0, "week": 0, "stars": 3, "updated": U},
             "tailscale": {"downloads": 9, "week": 9, "stars": 12, "updated": U}}, o
assert json.load(open(st))["through"] == "2026-11-20T09:00:00Z"
# same hour again: nothing new counted
stats.main("apply", st, out, rows, now=t, root=d)
assert json.load(open(out))["tailscale"]["downloads"] == 9
# next hour adds on top; no stars given means none shown
stats.main("apply", st, out, rows, now=t + dt.timedelta(hours=1), root=d)
assert json.load(open(out))["tailscale"] == {"downloads": 18, "week": 18, "updated": "2026-11-20T11:30:00Z"}
# 8 days later the old day bucket leaves the week, totals stay
stats.main("apply", st, out, rows, now=t + dt.timedelta(days=8), root=d)
o, s = json.load(open(out)), json.load(open(st))
assert o["tailscale"]["downloads"] == 27 and o["tailscale"]["week"] == 0, o
assert s["days"] == {}, s["days"]
# a day 6 days back still counts, 7 days back does not
s2 = {"days": {"2026-11-14": {"x": 5}, "2026-11-13": {"x": 7}}}
assert stats.week(s2, t) == {"x": 5} and list(s2["days"]) == ["2026-11-14"]
# long gap is capped
s, e = stats.window({"through": "2026-01-01T00:00:00Z"}, t)
assert e - s == stats.MAX_BACK
# a path without the leading slash still counts
s3 = {}; stats.add(s3, [row(2, "plugins/x/1.0.0/plugin")]); assert s3["totals"] == {"x": 2}
# listing files give owner/repo; broken files are skipped
r = tempfile.mkdtemp()
for sub in ("active", "inactive"):
    os.makedirs(os.path.join(r, "catalog", sub))
json.dump({"id": "a", "repo": "https://github.com/o/holyarrs-a"}, open(os.path.join(r, "catalog", "active", "a.json"), "w"))
json.dump({"id": "b", "repo": "https://github.com/o/b.git"}, open(os.path.join(r, "catalog", "inactive", "b.json"), "w"))
json.dump({"id": "c", "repo": "https://example.com/o/c"}, open(os.path.join(r, "catalog", "active", "c.json"), "w"))
open(os.path.join(r, "catalog", "active", "bad.json"), "w").write("{")
assert stats.listed_repos(r) == {"a": "o/holyarrs-a", "b": "o/b"}, stats.listed_repos(r)
# "listed" comes from the first git add of catalog/active/<id>.json and stays put
import subprocess
g = tempfile.mkdtemp(); os.makedirs(os.path.join(g, "catalog", "active"))
git = lambda *a, **e: subprocess.run(["git", "-C", g, "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True,
                                    capture_output=True, env={**os.environ, **e})
git("init", "-q")
json.dump({"id": "a", "repo": "https://github.com/o/a"}, open(os.path.join(g, "catalog", "active", "a.json"), "w"))
git("add", "."); git("commit", "-qm", "a", GIT_COMMITTER_DATE="2026-11-01T12:00:00Z")
json.dump({"id": "a", "repo": "https://github.com/o/a", "x": 1}, open(os.path.join(g, "catalog", "active", "a.json"), "w"))
json.dump({"id": "n", "repo": "https://github.com/o/n"}, open(os.path.join(g, "catalog", "active", "n.json"), "w"))
git("add", "."); git("commit", "-qm", "b", GIT_COMMITTER_DATE="2026-11-15T08:00:00Z")
gs = os.path.join(g, "s.json"); json.dump([], open(rows, "w"))
stats.main("apply", gs, out, rows, now=t, stars={}, root=g)
o = json.load(open(out))
assert o["a"]["listed"] == "2026-11-01T12:00:00Z" and o["n"]["listed"] == "2026-11-15T08:00:00Z", o
# a plugin with no git history gets "now"; once stored, the date never moves
s4 = {"listed": {"a": "2025-01-01T00:00:00Z"}}
assert stats.listed(s4, ["a", "z"], g, t) == {"a": "2025-01-01T00:00:00Z", "z": U}
# empty start
os.remove(st); json.dump([], open(rows, "w")); stats.main("apply", st, out, rows, now=t, root=d)
assert json.load(open(out)) == {}
print("ok")
