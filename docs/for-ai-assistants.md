# Make a HolyArrs plugin

> Written for coding assistants helping a person make a plugin. Follow it in order.
> The person usually reached this file through the prompt `Read https://holyarrs.com/ai/plugin.md and help me make a HolyArrs plugin. My idea: ...`.

HolyArrs is a self-hosted media app. A plugin is one small Go program that HolyArrs downloads from its own signed list, checks and runs in a sandbox. Plugins arrive with HolyArrs 1.2.1 (not released yet) and run on Linux, the Docker image included. Until 1.2.1 ships, the person can build, test and submit a plugin, but can't install it in HolyArrs.

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

## 2. What a plugin can and can't do today

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

**Enforced from 1.2.1** (Linux kernel 5.9 or newer; otherwise a plugin with hosts starts only if the owner allows it without the lock):

- `access.hosts`: the only websites it can reach, up to 100 plain names or `*.example.com` wildcards. All traffic goes through a HolyArrs proxy on ports 443 and 80. Raw IP addresses, LAN addresses (unless the owner adds the host), UDP and listening sockets are refused. Go's standard `net/http` uses the proxy on its own.
- `access.folders`: extra folders, up to 100. Each is a name, or `{"name": "music", "mode": "read" | "read_write", "why": "...", "required": true}`. The owner picks the real folder and approves it; it arrives as `HOLYARRS_PLUGIN_FOLDER_<NAME>`. A plain name means read-only.
- An update that asks for more hosts or folders waits until the owner approves it.
- `access.actions`: the HolyArrs permissions it needs (HolyArrs 1.3.0+; set `min_app_version` to `1.3.0`). The full list is in [.github/scopes.json](https://github.com/HolyArrs/HolyArrs-Plugins/blob/main/.github/scopes.json). Names are `<area>[.<part>].<read|change|control|delete>`, and a parent covers its children: `library.read` includes `library.music.read`. Ask for the fewest you need. The owner sees them at install, grouped as Library, Discover, Requests, Downloads, Media files, Alerts, Media servers and Network and pages. Deleting, changing media files, `network.forward` and `sources.downloader` show a red warning. An update that asks for more waits for the owner.
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
  "author": "github-login",
  "description": "One line that says what it does.",
  "licence": "MIT",
  "repo": "https://github.com/github-login/holyarrs-my-plugin",
  "support_email": "me@example.com",
  "min_app_version": "1.2.1",
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
| `min_app_version` | required, `x.y.z`, `1.2.1` or newer |
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
  "min_app_version": "1.2.1"
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
