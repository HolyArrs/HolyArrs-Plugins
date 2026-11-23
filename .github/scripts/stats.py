"""Plugin download counts for plugins.holyarrs.com.

Counts edge requests (cache hits included, status 200) on plugin binaries
(plugins/<id>/<version>/plugin and plugins/<id>/<version>/<platform>/plugin)
from the holyarrs.com zone HTTP analytics, and keeps running totals and
per-day buckets in a state file, because analytics keeps only a short time.

  stats.py fetch  STATE OUT             query Cloudflare (CF_API_TOKEN, CF_ZONE_ID)
  stats.py apply  STATE OUT ROWS.json   same, from saved rows (tests)

Each run counts the whole hours between state["through"] and one hour ago,
adds them to state["totals"] and state["days"], moves "through" on, and writes
OUT: {"<id>": {"downloads": N, "week": N, "stars": N, "updated": "<iso>"}}.
"week" is the last 7 days (today included); "stars" is the stargazer count of
the repo in the plugin's listing file, left out when it can't be read; "listed" is
when catalog/active/<id>.json first landed in git (stored in state["listed"]
so it never moves once set; the app shows its "New" tag from it).
"""
import datetime as dt, json, os, re, subprocess, sys, urllib.request

KEY_RE = re.compile(r"^plugins/([a-z0-9][a-z0-9-]{0,63})/[^/]+/(?:[^/]+/)?plugin$")
REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?$")
HOST = "plugins.holyarrs.com"
MAX_BACK = dt.timedelta(days=1)   # free-plan zone analytics keep about a day of queryable range
LAG = dt.timedelta(hours=1)       # analytics can arrive late

QUERY = """query($zone: String!, $f: ZoneHttpRequestsAdaptiveGroupsFilter_InputObject!) {
  viewer { zones(filter: {zoneTag: $zone}) {
    httpRequestsAdaptiveGroups(limit: 10000, filter: $f) {
      count dimensions { clientRequestPath date }
    } } } }"""


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def window(state, now):
    end = now.replace(minute=0, second=0, microsecond=0) - LAG
    start = end - dt.timedelta(hours=1)
    if state.get("through"):
        start = dt.datetime.strptime(state["through"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return max(start, end - MAX_BACK), end


def add(state, rows):
    totals, days = state.setdefault("totals", {}), state.setdefault("days", {})
    for r in rows:
        dims = r.get("dimensions", {})
        m = KEY_RE.match((dims.get("clientRequestPath") or "").lstrip("/"))
        if m:
            pid, n = m.group(1), int(r["count"])
            totals[pid] = totals.get(pid, 0) + n
            day = days.setdefault(dims.get("date") or "unknown", {})
            day[pid] = day.get(pid, 0) + n


def week(state, now):
    """Sums the last 7 days (today included) and drops older day buckets."""
    keep = {(now.date() - dt.timedelta(days=k)).isoformat() for k in range(7)}
    days = state.get("days", {})
    for d in list(days):
        if d not in keep:
            del days[d]
    out = {}
    for d in days.values():
        for pid, n in d.items():
            out[pid] = out.get(pid, 0) + n
    return out


def fetch(start, end):
    f = {"clientRequestHTTPHost": HOST, "edgeResponseStatus": 200, "requestSource": "eyeball",
         "clientRequestPath_like": "/plugins/%/plugin",
         "datetime_geq": iso(start), "datetime_lt": iso(end)}
    body = json.dumps({"query": QUERY, "variables": {"zone": os.environ["CF_ZONE_ID"], "f": f}}).encode()
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/graphql", body, {
        "Authorization": "Bearer " + os.environ["CF_API_TOKEN"], "Content-Type": "application/json"})
    out = json.load(urllib.request.urlopen(req, timeout=60))
    if out.get("errors"):
        sys.exit(f"graphql: {out['errors']}")
    zones = out["data"]["viewer"]["zones"]
    return zones[0]["httpRequestsAdaptiveGroups"] if zones else []


def listed_repos(root, subs=("active", "inactive")):
    """{id: "owner/name"} from the listing files in catalog/active and catalog/inactive."""
    out = {}
    for sub in subs:
        folder = os.path.join(root, "catalog", sub)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            try:
                e = json.load(open(os.path.join(folder, name), encoding="utf-8"))
            except (OSError, ValueError):
                continue
            m = REPO_RE.match(e.get("repo") or "") if isinstance(e, dict) else None
            if m and e.get("id"):
                out[e["id"]] = m.group(1)
    return out


def first_added(root, pid):
    """Commit time (UTC) when catalog/active/<pid>.json was first added, or None."""
    try:
        out = subprocess.run(["git", "-C", root, "log", "--diff-filter=A", "--format=%ct", "--",
                              f"catalog/active/{pid}.json"], capture_output=True, text=True, timeout=60).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    return iso(dt.datetime.fromtimestamp(int(out[-1]), dt.timezone.utc)) if out else None


def listed(state, ids, root, now):
    """Fills state["listed"] for new ids (git history, else now) and returns it; set dates never change."""
    seen = state.setdefault("listed", {})
    for pid in ids:
        if pid not in seen:
            seen[pid] = first_added(root, pid) or iso(now)
    return seen


def github_stars(repos):
    """{id: stargazers} using GITHUB_TOKEN; a repo that can't be read is left out."""
    out, tok = {}, os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "holyarrs-plugin-stats"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    for pid, repo in repos.items():
        try:
            req = urllib.request.Request("https://api.github.com/repos/" + repo, headers=h)
            out[pid] = int(json.load(urllib.request.urlopen(req, timeout=30))["stargazers_count"])
        except Exception as e:  # stars are optional
            print(f"stars for {pid} ({repo}) skipped: {e}")
    return out


def main(cmd, state_path, out_path, rows_path=None, now=None, stars=None, root="."):
    now = now or dt.datetime.now(dt.timezone.utc)
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    start, end = window(state, now)
    if end > start:
        rows = json.load(open(rows_path)) if cmd == "apply" else fetch(start, end)
        add(state, rows)
        state["through"] = iso(end)
    repos = listed_repos(root, ("active",))
    if stars is None:
        stars = github_stars(listed_repos(root)) if cmd == "fetch" else {}
    first = listed(state, sorted(repos), root, now)
    wk, totals, stamp = week(state, now), state.get("totals", {}), iso(now)
    stats = {}
    for pid in sorted(set(totals) | set(stars) | set(repos)):
        stats[pid] = {"downloads": totals.get(pid, 0), "week": wk.get(pid, 0), "updated": stamp}
        if pid in stars:
            stats[pid]["stars"] = stars[pid]
        if pid in first:
            stats[pid]["listed"] = first[pid]
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True); f.write("\n")
    with open(out_path, "w") as f:
        json.dump(stats, f, sort_keys=True); f.write("\n")
    print(f"counted {state.get('through')}; {len(stats)} plugins")


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] not in ("fetch", "apply"):
        sys.exit(__doc__)
    main(*sys.argv[1:])
