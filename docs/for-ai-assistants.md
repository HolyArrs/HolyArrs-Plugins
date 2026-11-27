# Make a HolyArrs plugin

> Written for coding assistants helping a person make a plugin. Follow it in order.
> The person usually reached this file through the prompt `Read https://holyarrs.com/ai/plugin.md and help me make a HolyArrs plugin. My idea: ...`.

HolyArrs is a self-hosted media app. A plugin is one small Go program that HolyArrs downloads from its own signed list, checks and runs in a sandbox. Plugins arrive with HolyArrs 1.3.0 and run on Linux, the Docker image included.

## 0. Ground rules for you, the assistant

- Ask the person first, and wait for a clear yes, before you: create a GitHub repo, push code or tags, open the pull request, add a `secret` setting, or declare any host or folder.
- Never put real keys, tokens or passwords in code, files, commits or chat. Ask for them as `secret` settings.
- Do not say a step worked until its command passed or the person confirmed it.
- If something fails, say which steps are done and which are left.
- Do not change the person's own tools or settings (editor, git config, shell profile, AI agent config).

## 1. Ask before you write code

Skip anything the idea already answers:

1. What should the plugin do, in one sentence?
2. Which outside websites or services does it talk to?
3. What does the server owner fill in (settings)? Is any of it a password or key?
4. Does it keep anything between runs (files in its data folder)?
5. Where will the code live (their GitHub account and repo name)?

Then show a one-screen plan: files you will create, settings, hosts, and what it will not do. Ask "Shall I start?" and wait.

## 2. What a plugin can and can't do

Be exact with the person. Do not promise more than this.

A plugin **can**:

- Run as one pure-Go program built with `CGO_ENABLED=0`, for linux-amd64, linux-arm64 and linux-arm-v7.
- Read and write its own data folder. The path is in `HOLYARRS_PLUGIN_DATA`; `HOME` points there too.
- Read its settings from environment variables `HOLYARRS_PLUGIN_SETTING_<KEY>` (key in capitals). Toggles are `true` or `false`. Secrets arrive already decrypted. Saved values are at most 2000 characters. Saving settings restarts the plugin.
- Read TLS certificates and DNS files (`/etc/ssl/certs`, `/etc/resolv.conf`, `/etc/hosts`), and use `/dev/null` and `/dev/urandom`.
- Make network calls, but only to the hosts in `access.hosts` (see below).
- Call HolyArrs through the permissions it lists in `access.actions` (HolyArrs 1.3.0+), once the owner approves them. It gets `HOLYARRS_PLUGIN_TARGET` (HolyArrs' local address) and `HOLYARRS_PLUGIN_TOKEN` (a key that's new on every start) and sends `Authorization: Bearer $HOLYARRS_PLUGIN_TOKEN`. Every route outside its permissions answers 403.

A plugin **can't**:

- Read or write any other path. On Linux, Landlock denies everything else.
- Go past 256 processes, 512 MiB of memory and 1 CPU (when the host has cgroup v2), or 1024 open files (always).
- See other environment variables (it gets only `HOLYARRS_PLUGIN_*`, `PATH`, `TZ` and `HOME`), gain privileges, or signal anything outside itself.
- Use any HolyArrs route outside its approved permissions. **Always closed to every plugin**: installing, approving or blocking plugins; accounts, invites, two-factor and API keys; passwords and connection secrets (adding or editing download clients, sources, media servers, subtitle sites); server settings, backups, restores, imports from other apps and restarts.

**Enforced** (Linux kernel 5.9 or newer; otherwise a plugin with hosts starts only if the owner allows it without the lock):

- `access.hosts`: the only websites it can reach, up to 100 plain names or `*.example.com` wildcards. All traffic goes through a HolyArrs proxy on ports 443 and 80. Raw IP addresses, LAN addresses (unless the owner adds the host), UDP and listening sockets are refused. Go's standard `net/http` uses the proxy on its own.
- `access.folders`: extra folders, up to 100. Each is a name, or `{"name": "music", "mode": "read" | "read_write", "why": "...", "required": true}`. The owner picks the real folder and approves it; it arrives as `HOLYARRS_PLUGIN_FOLDER_<NAME>`. A plain name means read-only.
- An update that asks for more hosts or folders waits until the owner approves it.
- `access.actions`: the HolyArrs permissions it needs (HolyArrs 1.3.0+; set `min_app_version` to `1.3.0`). The full list is in [.github/scopes.json](https://github.com/HolyArrs/HolyArrs-Plugins/blob/main/.github/scopes.json). Names are `<area>[.<part>].<read|change|control|delete>`, and a parent covers its children: `library.read` includes `library.music.read`. Ask for the fewest you need. The owner sees them at install, grouped as Library, Discover, Requests, Downloads, Media files, Alerts, Media servers and Network and pages. Deleting, changing media files, `network.forward`, `sources.downloader` and `sources.botcheck` show a red warning. An update that asks for more waits for the owner.
- `resources` (optional, 1.3.0+): `memory_mib`, `cpus`, `processes`, `open_files` above the defaults, approved by the owner.

The plugin must stop cleanly on SIGTERM and should write its state to files in its data folder.

## 3. Files and fields

The plugin lives in the person's own **public** GitHub repo (the repo root, or a folder inside it):

```text
go.mod
main.go                # plus any other .go files
holyarrs-plugin.json   # the plugin's details, below
icon.svg or icon.png   # optional logo
README.md              # short: what it does, settings, hosts
```

`holyarrs-plugin.json` example:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "github-login",
  "description": "One line that says what it does.",
  "licence": "MIT",
  "repo": "https://github.com/github-login/holyarrs-my-plugin",
  "support_email": "me@example.com",
  "min_app_version": "1.3.0",
  "access": { "hosts": ["api.example.com"], "folders": [], "actions": [] },
  "settings": [
    { "key": "api_key", "label": "API key", "type": "secret", "help": "From your example.com account page." }
  ]
}
```

Limits (characters unless it says entries). These are the stricter publish limits. Stay inside them.

| Field | Rule |
|---|---|
| `id` | `^[a-z0-9][a-z0-9-]{0,63}$`, same as the entry file name |
| version (the tag) | tag up to 16 characters from `A-Z a-z 0-9 . _ -`; the tag minus a leading `v` must be a version like `1.0.0` (a suffix like `-beta.1` is allowed); a published version is never reused |
| `version` in `holyarrs-plugin.json` | required, the tag's version (`1.0.0` for tag `1.0.0` or `v1.0.0`); developer mode refuses the file without it; publishing uses the tag |
| `name` | required, up to 40 |
| `author` | required, up to 40 |
| `description` | one line, up to 160 |
| `long_description` | optional, up to 2000 |
| `whats_new` | optional, up to 300 |
| `how_it_works` | optional, up to 8 steps of 160 |
| `developers` | optional, up to 5 GitHub logins |
| `category` | optional, up to 24 |
| `licence` | **required**, for example `MIT` or `AGPL-3.0` |
| `support_email` | **required**; `support_url` optional, https only |
| `repo` | https link to the public repo |
| `icon_file` | optional, `.svg` or `.png` in the same folder |
| `icon_url` | optional, direct https link to a logo, 16 to 4096 px a side, up to 2 MB; we copy it |
| `min_app_version` | required, `x.y.z`, `1.3.0` or newer for new plugins |
| `access.hosts` | up to 100 entries of 80; no empty value, `..` or `\` |
| `access.folders` | up to 100; a name (40 max, no `/`, `..`, `\` or `:`) or an object with `name`, `mode` (`read`/`read_write`), `why`, `required` |
| `access.actions` | permissions from `.github/scopes.json`; needs `min_app_version` 1.3.0 |
| `settings` | up to 100 fields |
| setting `key` | `^[a-z][a-z0-9_]{0,39}$`: starts with a letter, unique |
| setting `label` / `help` | label required, up to 48 / help up to 160 |
| setting `type` | `text`, `number`, `toggle`, `select` (1 to 12 `options` of 40), `secret` (no `default`) |

No text field may contain `<` or `>`.

**Never write these**, the publish workflow sets them: `sha256`, `platforms`, `size`, `icon`. It also replaces `icon_url` with its own copy on plugins.holyarrs.com.

## 4. The entry file

The pull request adds one file to this repo, `catalog/active/<id>.json`. Start from [docs/template/plugin.json](https://github.com/HolyArrs/HolyArrs-Plugins/blob/main/docs/template/plugin.json) and replace every template value; the check fails on `id`, `repo` or `commit` left as in the template.

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "description": "One line that says what it does.",
  "authors": ["github-login"],
  "repo": "https://github.com/github-login/holyarrs-my-plugin",
  "tag": "1.0.0",
  "commit": "<full 40-character commit the tag points to>",
  "min_app_version": "1.3.0"
}
```

Optional: `path` (the plugin folder inside the repo, when it isn't the root) and `icon_url`. `version` is optional and must match the tag. No other keys are allowed. The entry `name` must also stay within 40 characters. The tag is the version that gets published, like `1.0.0`. Our tags have no `v`; a leading `v` still works and is dropped. A repo that holds several plugins can tag `<id>-v1.0.0`.

## 5. Test it locally

Run these and show the person the output:

```sh
go vet ./...
go test ./...
mkdir -p /tmp/plugin-data
HOLYARRS_PLUGIN_DATA=/tmp/plugin-data go run .
```

Set any `HOLYARRS_PLUGIN_SETTING_<KEY>` it needs before `go run`. Stop it with Ctrl+C and check it exits cleanly.

Build all three CPU types:

```sh
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -mod=readonly -o build/amd64/plugin .
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -mod=readonly -o build/arm64/plugin .
CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=7 go build -trimpath -mod=readonly -o build/armv7/plugin .
```

## 6. Run the check

From a clone of this repo, with the entry file in place:

```sh
pip install "jsonschema==4.23.0"
python .github/scripts/check.py catalog/active/<id>.json --src /path/to/the/plugin/folder
```

It applies the same strict limits as the publish workflow. The pull request check only tests the entry file, so `--src` must be run locally. Fix every line it prints and run it again until it says the files look right. Common messages:

| Message | Fix |
|---|---|
| `... is N characters; the most is M` | Shorten that field |
| `... has < or >; plain text only` | Remove markup |
| `licence is required` / `support_email is required` | Add the field |
| `remove 'sha256'; we fill it in when publishing` | Delete that field |
| `key must match ^[a-z][a-z0-9_]{0,39}$` | Rename the key: lowercase, starts with a letter |
| `a secret can't have a default` | Remove the `default` |
| `unknown permission` | Use a name from `.github/scopes.json` |
| `access.actions needs min_app_version 1.3.0` | Set `"min_app_version": "1.3.0"` |
| `unsafe host` / `unsafe folder` | Use a plain host name or a relative folder |
| `... is still the template value` | Replace the template value in the entry file |
| `file name must be <id>.json` | Rename the entry file to match `id` |

## 7. Forbidden

- Hidden telemetry, tracking or ads.
- Downloading and running code or programs at run time.
- Writing outside the data folder, or trying to get around the sandbox.
- Network calls to hosts that are not in `access.hosts`, or without a reason the owner can see.
- Keys, tokens or passwords in the repo.
- Reusing a version number. A published version never changes; a fix is a new tag.

## 8. Submit (ask first)

1. Ask before pushing. Then push the code and a release tag, for example `1.0.0`.
2. Get the exact commit: `git rev-parse "1.0.0^{commit}"`, and put it in the entry file.
3. Show the person the entry file. **Only after they say yes**, fork https://github.com/HolyArrs/HolyArrs-Plugins and open **one** pull request there that adds only `catalog/active/<id>.json`.
4. Explain what happens next: our check tests the entry file, and we read the code at that exact commit. We start publishing after the merge: the publish workflow checks out the repo at that commit (the tag must still point there), builds all three CPU types, keeps a source archive, signs the list and puts it on plugins.holyarrs.com. The author uploads nothing.
5. A new version is a new pull request that changes `tag` and `commit`.

## 9. Done report

End with this report, filled in:

```text
Plugin: <id> <version>
Made: <files created>
Tests: go vet <pass/fail>, go test <pass/fail>, local run <ok/what happened>, 3 builds <ok/fail>
Check: check.py <passed / the lines it printed>
Pull request: <link, or "not opened yet">
Left to do: <anything not done, or "nothing">
```

## 10. Every permission

The full list, HolyArrs 1.3.0. Put the names you need in `access.actions`. A parent covers its children: `library.read` includes every `library.*.read`. Anything ending in `.delete`, any `files.*.change`, `network.forward` and `sources.downloader` show a red warning at install. Ask for the fewest you need; reviewers refuse permissions the code doesn't use.

### Library

Your movies, shows and music, with collections, tags, hidden and never-add lists, metadata and artwork.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `library.read` | Read every title in your library: movies, shows, seasons, episodes and albums, with status, files, copies, subtitles, cast, releases found and library stats, including what’s been watched. Includes every library.*.read below. | A Trakt sync reading what you have |
| `library.change` | Add movies and shows, edit them and their seasons and episodes, follow or unfollow them, move and rename their files, rescan, refresh or search for them, manage versions and leftover files, and set which subtitles you want. Includes every library.*.change below. | A list importer that adds titles |
| `library.delete` | Red warning. Delete a title, remove one version of a title, or remove a whole collection. | A cleanup tool for watched movies |
| `library.artwork.read` | Load the posters and other artwork HolyArrs has stored. | A screensaver of your posters |
| `library.artwork.set` | Save a poster or other artwork for a title. | A custom poster plugin |
| `library.collections.read` | List collections, like a film series, and see what’s in each. | Finding the missing film in a series |
| `library.extras.read` | Find and play trailers and other extras. | A trailer reel |
| `library.hidden.read` | See the titles you’ve hidden. | A sync that skips hidden titles |
| `library.hidden.change` | Hide a title or unhide it. | Hiding titles by rating |
| `library.metadata.read` | Look up any movie, show, season or album, with reviews, related titles and anime details, and see if it’s followed. Also checks the title info service is up. | Looking a title up before adding it |
| `library.metadata.change` | Follow or unfollow any movie, show or album, even one that isn’t in your library yet. | A watchlist sync |
| `library.music.read` | Browse music: artists, albums, tracks, covers and genres. | Matching scrobbles to your albums |
| `library.music.change` | Add an artist and edit an album. | An artist importer |
| `library.never-add.read` | See your never-add list. | A list sync that respects it |
| `library.never-add.change` | Put a title on the never-add list or take it off. | Blocking a title for good |
| `library.tags.read` | Read your tags. | A report grouped by tag |
| `library.tags.change` | Create, edit and delete your own tags. | Tagging titles by where they came from |

### Discover

Explore, New & Popular, people, outside lists and the calendar.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `calendar.read` | Read the calendar of upcoming releases. | An “out this week” message |
| `discover.home.read` | Read what Home shows. | A dashboard mirroring Home |
| `discover.explore.read` | Browse Explore: trending, top 10s, new releases, genres, streaming services and music charts. | A “what’s popular” digest |
| `discover.lists.read` | See the outside lists you follow. | A list status report |
| `discover.lists.change` | Add, edit, sync and remove outside lists. | Linking a list from another site |
| `discover.people.read` | Search actors and crew, see popular people, read their pages, and preview up to 100 of a person’s movies. | A “more from this director” feature |

### Requests

Requests, request limits, and the names of people on the server.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `requests.read` | Read requests and their parts, who asked, request limits, and turned-down titles. | A daily request digest |
| `requests.change` | Make a request, cancel one, and clear turned-down titles. | A chat bot that takes requests |
| `requests.approve.change` | Approve, turn down or remove other people’s requests. | Auto-approving trusted friends |
| `requests.limits.read` | See each person’s request limit. | A limits report |
| `requests.limits.change` | Change a person’s request limit. | Raising limits on weekends |
| `requests.users.read` | See the names of people on your server, and nothing else about them. | Showing who asked in a chat bot |

### Downloads

Downloads, held releases, decisions, release search and pick rules. Download clients and sources are read-only and never show their passwords or keys.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `downloads.read` | Read the download queue and each download’s details, files and peers, plus matches waiting. | A queue widget |
| `downloads.change` | Import a finished download, mark one failed, pick its files or edition, run and pick matches, pause or resume everything, and clear finished downloads now. | Importing stuck downloads |
| `downloads.control` | Pause, resume, recheck or reannounce one download, or move it to the top. | Pausing during quiet hours |
| `downloads.delete` | Red warning. Remove a download. | Clearing stalled downloads |
| `downloads.held.read` | See releases HolyArrs found but is holding back, for example while it waits out a delay. | A report of what’s waiting |
| `downloads.held.change` | Drop held releases, one or all. No files are deleted. | Dropping releases you no longer want |
| `downloads.decisions.read` | See downloads that need a person to choose before HolyArrs carries on. | A reminder to decide |
| `downloads.decisions.change` | Decide on one of them. | Deciding from a chat message |
| `downloads.clients.read` | List your download clients and their categories and attempts, and read each item’s details, files and peers. Not their passwords. | A client health report |
| `downloads.clients.control` | Pause, resume, reorder or change the priority of one item inside a download client. | Moving one item to the top |
| `downloads.releases.read` | Read the result of a release check. |  |
| `downloads.releases.change` | Check a release or a release name, choose one, or turn one down. | Grabbing a release picked in chat |
| `downloads.rules.read` | Read your pick rules and the TRaSH Guides profiles. |  |
| `downloads.rules.change` | Create, edit and delete pick rules, and apply a TRaSH Guides profile to one. | Keeping rules in step with a guide |
| `downloads.search.read` | Search, and see past searches. |  |
| `downloads.search.change` | Start a search for missing titles, for better copies, or for new items in source feeds. | A nightly “search missing” run |
| `downloads.sources.read` | List your search sources and their stats. Not their passwords. | A source stats report |
| `downloads.sources.control` | Pause, resume or test one search source, or run a test search on every enabled source. | Pausing a source that keeps failing |
| `sources.releases` | Add a search source of its own, like an indexer. | A plugin for a new site |
| `sources.downloader` | Red warning. Act as a download client. | A plugin that downloads from a new service |

### Media files

Library folders, the holding folder, renaming, imports, subtitles and streaming.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `files.change` | Red warning. Pick, choose or translate the subtitles for a file. | A subtitle translator |
| `files.delete` | Red warning. Permanently delete media files, including emptying the holding folder. | A cleanup plugin that empties the holding folder after 30 days |
| `files.folders.read` | See your library folders and what tidying them would change. It can’t change them. | A disk space report |
| `files.holding.read` | See deleted media files waiting in the holding folders, like a recycle bin. | A report of what’s waiting to be emptied |
| `files.holding.change` | Put deleted media files back from the holding folders. | Restoring something deleted by mistake |
| `files.import.read` | See past imports. |  |
| `files.import.change` | Scan a folder and import files from it by hand. | An importer for a drop folder |
| `files.rename.read` | Preview how files would be renamed. |  |
| `files.rename.change` | Rename files. |  |
| `files.subtitles.read` | See subtitle languages and which titles are missing subtitles. |  |
| `files.subtitles.change` | Search for subtitles, and sync, clean or turn down a subtitle. | A subtitle fixer |
| `files.subtitle-sites.read` | List your subtitle sites. Not their passwords. |  |
| `media.stream` | Play a file from a folder you approved. From a plugin page, ask HolyArrs to play it: HolyArrs shows its own player and your page controls it. Only the owner can play from plugin pages in 1.3.0. | A media player page |

### Alerts

Events, messages, reports and sending alerts.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `alerts.read` | List your alert connections. Adding or editing them stays closed. |  |
| `alerts.events.read` | Read the list of things that happened. | An activity feed |
| `alerts.events.subscribe` | Hear about things as they happen, like a new title. | A post when a movie arrives |
| `alerts.messages.read` | Read messages. |  |
| `alerts.messages.change` | Mark messages as read. |  |
| `alerts.reports.read` | Read reports. |  |
| `alerts.reports.change` | File a report, mark it fixed, or reopen it. | Reporting a file with bad audio |
| `alerts.webhooks.send` | Send a webhook. | A home automation trigger |

### Media servers

What's playing, and starting a library scan.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `media-servers.read` | List your media servers, their libraries, and watch links. Not their passwords. | A “watch now” link |
| `media-servers.change` | Choose which libraries on a media server HolyArrs uses. |  |

### Network and pages

Forwarding, plugin pages, Home widgets, title page sections, MCP tools, metadata sources and system info.

| Permission | What it lets a plugin do | Example |
|---|---|---|
| `pages.add` | Add a page under Plugins. | A stats page |
| `pages.home-widget` | Add a widget to Home. | A disk space widget |
| `pages.title-section` | Add a section to title pages. | Ratings from another site |
| `assistant.tools` | Add your own tools to HolyArrs’ MCP connection. They show up in your AI client next to the built-in ones, only for people allowed to use them. | A Trakt plugin that adds “find similar on Trakt” |
| `network.forward` | Red warning. Make HolyArrs reachable from outside your home network, as Tailscale does. | A remote access plugin |
| `sources.metadata` | Add a place HolyArrs gets title info from. | An extra anime info source |
| `system.health.read` | Read health checks, their states, and disk space. | A health widget |
| `system.health.change` | Run the health checks now. |  |
| `system.jobs.read` | See running and past jobs. | A progress bar |
| `system.languages.read` | List languages and read a language pack. |  |
| `system.languages.change` | Add or remove a language. |  |
| `system.logs.read` | Read the logs. | Sending logs to your own log store |
| `system.schedules.read` | See scheduled jobs. |  |
| `system.schedules.change` | Change when a scheduled job runs. |  |
| `system.schedules.run` | Run a scheduled job now. | A “refresh now” button |

### Never granted

No plugin can reach these, whatever it asks for: installing, approving, blocking or signing plugins; users, invites, sign-in, two-factor and API keys; adding, editing or testing download clients, sources, media servers and subtitle sites, and any outside-service keys; server settings, backups and restore, imports from other apps, restarts and controls; library folder setup; each person's own Explore history. A request to any of them answers 403.

## 11. Provider hooks

For the `sources.*`, `assistant.tools`, `pages.*`, `alerts.*`, `requests.users.read`, `media.stream` and `library.artwork.set` permissions, the plugin talks to these routes on `HOLYARRS_PLUGIN_TARGET` with its Bearer token. It never listens on a port.

**Work queues** (long-poll): `GET /api/v1/plugin-hooks/<hook>` waits for a job and returns `{"id", "op", "payload"}`, or `204` when none came (ask again). Answer with `POST /api/v1/plugin-hooks/<hook>` and `{"job": "<id>", "data": ...}` or `{"job": "<id>", "error": "..."}`. A plugin that polled in the last 90 seconds counts as live.

| Hook | Permission | What HolyArrs sends | What the plugin does |
|---|---|---|---|
| `downloader` | `sources.downloader` | grabs (the .torrent/.nzb file or a magnet, never the indexer link), queue and control requests | acts as a download client; the owner adds it under Download clients → From a plugin |
| `releases` | `sources.releases` | searches | returns results; files are fetched back through the plugin |
| `metadata` | `sources.metadata` | title lookups | returns extra title info, such as scores |
| `botcheck` | `sources.botcheck` | HolyArrs 1.3.2+: op `open`, `{"url", "proxy"}`, a Source page behind a bot check (key included) | opens it in a browser (FlareSolverr, for example) within 75 seconds and answers `{"url", "status", "body", "cookies": [{"name", "value"}], "user_agent"}`; HolyArrs checks the site and keeps the cookies |
| `tools` | `assistant.tools` | tool calls, each with a short token limited to what the tool declared and the person holds | answers the call; declare tools first with `PUT /api/v1/plugin-hooks/tools` (`[{"name", "about", "scopes", "input"}]`, every tool needs at least one scope). Tools show as `plugin.<plugin id>.<name>` and their output is marked as untrusted plugin text |
| `pages` | `pages.add` | page file requests | serves the files; declare pages with `PUT /api/v1/plugin-hooks/pages` (`[{"id", "title", "file"}]`). Pages run in a sandboxed frame with no cookies and talk to HolyArrs only by `postMessage` |
| `sections` | `pages.title-section` | a `title_id` when someone opens a title page | returns a card `{"title", "rows": [{"text", "sub", "title_id", "link"}]}`; the install screen says the plugin sees which titles people open |
| `events` | `alerts.events.subscribe` | events, only for areas the plugin can read, with ids only and no IPs or sign-in data | reacts; no answer needed |

**One-shot calls:**

| Route | Permission | Body | Does |
|---|---|---|---|
| `PUT /api/v1/plugin-hooks/home-widget` | `pages.home-widget` | a card `{"title", "rows": [...]}` | shows a widget on Home, drawn by HolyArrs |
| `POST /api/v1/plugin-hooks/artwork` | `library.artwork.set` | `{"title_id": 12, "kind": "poster", "image": "<base64 JPEG or PNG>"}` | saves artwork for a title |
| `POST /api/v1/plugin-hooks/notify` | `alerts.webhooks.send` | `{"subject", "text"}` | sends through the alerts the owner set up |
| `POST /api/v1/plugin-hooks/stream` | `media.stream` | `{"file_id": 123}`, a file in a folder granted to the plugin | returns a short-lived link that only plays in a signed-in browser on the same network path (no proxy), never from elsewhere |
| `GET /api/v1/plugin-hooks/users` | `requests.users.read` | | lists the names of people on the server, nothing else |
| `POST /api/v1/plugin-hooks/link` | `requests.users.read` | | returns a code; the person enters it in My account → Linked plugins |

**Playing media from a plugin page.** The page never gets a stream link. HolyArrs draws its own player; the page drives it with `postMessage` to its parent window. HolyArrs checks `media.stream`, `pages.add`, that the file is in a folder granted to the plugin and that the viewer is the owner (only the owner can play from plugin pages in 1.3.0).

Page to HolyArrs (`id` is a string or number you choose, required; a message that doesn't match is ignored):

```js
{ id, player: "play", file_id: 123 }      // a positive integer
{ id, player: "pause" }
{ id, player: "resume" }
{ id, player: "seek", time: 42.5 }        // seconds, a finite number >= 0
{ id, player: "close" }
```

HolyArrs answers each one with `{ id, status: 200 | 403, body: null }`. Only `play` can return `403` (refused); `pause`, `resume` and `seek` answer `200` even when no video is open.

HolyArrs to the page, as things happen:

```js
{ player: "event", type: "play" }
{ player: "event", type: "pause" }
{ player: "event", type: "ended" }
{ player: "event", type: "closed" }       // the person closed it, or the page sent close
{ player: "event", type: "time", time: 12.3, duration: 5400 }   // seconds; duration 0 if unknown
{ player: "event", type: "error", reason: "refused" }           // or "media"
```

**Acting for a person.** After a person links, send `X-Holyarrs-For-User: <their user id>` (from `GET /api/v1/plugin-hooks/users`) on request, request limit and follow calls. Each call needs the plugin's permission and that person's own; it follows their limits and auto-approve and is recorded as made through the plugin. Without a link those calls answer 403.

**Limits.** About 600 calls a minute per plugin (heavy routes like a full search count more) and 8 at once. Over that answers `429`. Every call shows in the plugin's activity log.
