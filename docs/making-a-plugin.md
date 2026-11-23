# Making a plugin

Plugins arrive with HolyArrs 1.2.1. A HolyArrs plugin is one small Go program (pure Go, no cgo) in your own public GitHub repo. We build it from your source, sign it and host it. HolyArrs will download it, check its fingerprint and run it in a sandbox on Linux (the Docker image included) on amd64, arm64 and armv7.

- How the pieces fit, and what a plugin can and can't do: [how plugins work](how-plugins-work.md).
- Working with a coding assistant? Give it [for-ai-assistants.md](for-ai-assistants.md).

## The steps

1. Write the program and its `holyarrs-plugin.json`.
2. Test it on your machine.
3. Tag a release.
4. Add your entry file to this repo.
5. Run our check.
6. Open a pull request.

## 1. Write it

Your plugin folder sits at the root of your repo or in a subfolder. It holds:

```
go.mod
main.go               (and any other .go files)
holyarrs-plugin.json
icon.svg              (optional logo, .svg or .png)
LICENSE               (at the repo root is fine)
```

No links (symlinks) and no special files. No prebuilt programs.

### The program

- Read your data folder from `HOLYARRS_PLUGIN_DATA`. It's the only place you can write.
- Read settings from `HOLYARRS_PLUGIN_SETTING_<KEY>`, with the key in capitals. A setting with key `api_key` arrives as `HOLYARRS_PLUGIN_SETTING_API_KEY`.
- Write logs to stdout or stderr. They show up in the HolyArrs log under your plugin's id.
- Stop cleanly on SIGTERM.
- Call only the websites you list in `access.hosts`.

A small start:

```go
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	data := os.Getenv("HOLYARRS_PLUGIN_DATA")
	mode := os.Getenv("HOLYARRS_PLUGIN_SETTING_MODE")
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stop()
	log.Printf("started, data in %s, mode %q", data, mode)
	t := time.NewTicker(time.Hour)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			log.Print("stopping")
			return
		case <-t.C:
			// your work here
		}
	}
}
```

### holyarrs-plugin.json, in full

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "author": "your-github-name",
  "description": "One line that says what it does.",
  "long_description": "A few sentences for the plugin's own page. What it does, what it needs, and anything people should know first.",
  "how_it_works": [
    "Install the plugin and open its settings.",
    "Paste your API key from example.com.",
    "Start it. It checks every hour."
  ],
  "whats_new": "First release.",
  "category": "Notifications",
  "developers": ["your-github-name"],
  "licence": "MIT",
  "repo": "https://github.com/your-github-name/holyarrs-my-plugin",
  "support_email": "me@example.com",
  "support_url": "https://github.com/your-github-name/holyarrs-my-plugin/issues",
  "icon_file": "icon.svg",
  "min_app_version": "1.2.1",
  "access": { "hosts": ["api.example.com"], "folders": [], "actions": [] },
  "settings": [
    { "key": "api_key", "label": "API key", "type": "secret", "help": "From your example.com account page." },
    { "key": "mode", "label": "Mode", "type": "select", "options": ["fast", "careful"], "default": "careful" },
    { "key": "every", "label": "Check every (minutes)", "type": "number", "default": 60 },
    { "key": "quiet", "label": "Quiet at night", "type": "toggle", "default": false },
    { "key": "tag", "label": "Tag to add", "type": "text" }
  ]
}
```

| Field | Needed | Rules |
|---|---|---|
| `id` | Yes | Lowercase letters, digits and dashes, up to 64. Same as your entry file |
| `name` | Yes | Up to 40 characters |
| `author` | Yes | Up to 40 characters |
| `description` | No | One line, up to 160 characters |
| `licence` | Yes | Like `MIT` or `AGPL-3.0` |
| `support_email` | Yes | An email address people can reach you at |
| `min_app_version` | Yes | `x.y.z`, 1.2.1 or newer |
| `access` | Yes | `hosts`, `folders`, `actions`. Can be empty lists |
| `long_description` | No | Up to 2000 characters |
| `how_it_works` | No | Up to 8 steps, 160 characters each |
| `whats_new` | No | Up to 300 characters |
| `category` | No | Up to 24 characters |
| `developers` | No | Up to 5 GitHub user names |
| `repo`, `support_url` | No | https links |
| `icon_file` or `icon_url` | No | A `.svg` or `.png` in the folder, or an https link |
| `settings` | No | Up to 20, see below |

All text is plain text. `<` and `>` aren't allowed.

**access**

- `hosts`: every website the code calls.
- `folders`: extra folders the owner approves, as a name (read-only) or `{"name", "mode": "read" | "read_write", "why", "required"}`.
- `actions`: the HolyArrs permissions it needs (1.3.0+), from [.github/scopes.json](../.github/scopes.json). Can be `[]`.

The rules for each list are in the [plugin reference](plugin-api.md#the-access-lists).

**resources** (optional, HolyArrs 1.3.0+): ask for more than the defaults of 512 MiB memory, 1 CPU, 256 processes and 1024 open files. For example `"resources": {"memory_mib": 2048, "cpus": 2}`. The keys are `memory_mib`, `cpus`, `processes` and `open_files`, all whole numbers. The owner sees anything above the defaults at install and approves it, and can change it later. HolyArrs won't give more than the server has. Set `min_app_version` to `1.3.0` or newer when you use it.

**settings**: up to 100. The rules for each field are in the [plugin reference](plugin-api.md#settings).

**Leave out** `version`, `sha256`, `platforms`, `size` and `icon`. The version comes from your tag, and we fill in the rest when we publish.

## 2. Test it

```sh
go vet ./...
mkdir -p /tmp/plugin-data
HOLYARRS_PLUGIN_DATA=/tmp/plugin-data HOLYARRS_PLUGIN_SETTING_MODE=fast go run .
```

On Windows PowerShell, set the variables first: `$env:HOLYARRS_PLUGIN_DATA="$env:TEMP\plugin-data"; $env:HOLYARRS_PLUGIN_SETTING_MODE="fast"; go run .`

Press Ctrl+C and check it stops cleanly. Then make sure it builds for all three CPU types the way we build it:

```sh
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -mod=readonly -o build/amd64/plugin .
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -mod=readonly -o build/arm64/plugin .
CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=7 go build -trimpath -mod=readonly -o build/armv7/plugin .
```

Keep `go.sum` in the repo so the build needs nothing outside it. Make sure it only writes inside `HOLYARRS_PLUGIN_DATA`, since the sandbox blocks everything else.

HolyArrs only installs plugins from our signed list. You can't load your own build into HolyArrs to try it first, so test it this way before you submit. The sandbox will refuse three things that work on your machine: writing outside `HOLYARRS_PLUGIN_DATA` and approved folders, calling a host that isn't in `access.hosts`, and UDP or listening for connections.

## 3. Tag a release

Use a plain version tag like `1.0.0`, with no `v`, up to 16 characters. That number is the version people see. (A tag like `v1.0.0` still works; we drop the `v`.)

```sh
git tag 1.0.0
git push origin 1.0.0
git rev-parse "1.0.0^{commit}"
```

The last line prints the full commit. Keep it for the next step. Never move a tag after you submit it.

## 4. Add your entry file

Your code stays in your own repo; `catalog/` only lists it, the same way it lists the plugins we make in `plugins/`. Fork this repo and copy [`template/plugin.json`](template/plugin.json) to `catalog/active/<id>.json`. The file name must match `id`. A full entry:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "description": "One line that says what it does.",
  "authors": ["your-github-name"],
  "repo": "https://github.com/your-github-name/holyarrs-my-plugin",
  "path": "plugin",
  "tag": "1.0.0",
  "commit": "3f9c2a7e1b4d5c6a8e0f1a2b3c4d5e6f7a8b9c0d",
  "icon_url": "https://raw.githubusercontent.com/your-github-name/holyarrs-my-plugin/1.0.0/plugin/icon.png",
  "min_app_version": "1.2.1"
}
```

| Field | What goes in it |
|---|---|
| `id` | Same as in `holyarrs-plugin.json` |
| `name` | Shown on the Plugins page, 2 to 40 characters |
| `description` | One line, 10 to 160 characters |
| `authors` | Your GitHub user names, at least one |
| `repo` | `https://github.com/<owner>/<repo>`, public |
| `path` | Optional. The plugin folder, if it isn't the repo root |
| `tag` | The release tag, up to 16 characters |
| `commit` | The full 40-character commit of that tag |
| `icon_url` | Optional. A direct https link to your logo |
| `min_app_version` | Optional here. 1.2.1 or newer |

No other keys are allowed. A repo that holds several plugins can tag each one as `<id>-v1.0.0` (our own plugins in [`plugins/`](../plugins/) do). The template values are fake on purpose, and the check refuses them. The rules for this file live in [`template/plugin.schema.json`](template/plugin.schema.json); see [how the schema is used](template/README.md#how-the-schema-is-used).

The logo can be PNG, JPEG, WebP or SVG, 16 to 4096 px a side, up to 2 MB. Square at 256 x 256 or larger looks best. We copy it to plugins.holyarrs.com, so HolyArrs never loads it from your link. Without one, the app shows your plugin's first letter.

Then update the plugin table in the README. Our check fails if you skip this:

```sh
python .github/scripts/readme_list.py
```

## 5. Run the check

From your fork, check your entry file and your plugin folder together. Our pull request check only tests the entry file, so run this yourself:

```sh
pip install "jsonschema==4.23.0"
python .github/scripts/check.py catalog/active/<id>.json --src /path/to/your/plugin
python .github/scripts/readme_list.py --check
```

Fix every line it prints until it passes.

## 6. Open a pull request

One plugin per pull request. We read your code at that exact commit and check:

- every website the code calls is in `access.hosts`
- nothing downloads or runs other code at run time
- no hidden tracking, keys or prebuilt programs
- the repo has a licence

We start publishing after the merge. Our publish workflow checks out your repo at that commit (the tag must still point there), builds all three CPU types, keeps a source archive, signs the list and uploads it to plugins.holyarrs.com.

## Updates

- **New version.** Push a new tag, then open a pull request that changes `tag` and `commit` in your entry file. Update `whats_new` in `holyarrs-plugin.json` too.
- **Published versions never change.** A fix always gets a new tag.
- **People update from the Plugins page.** Installing again takes the newest listed version.
- **Needs a newer HolyArrs?** Raise `min_app_version`. Older HolyArrs then won't offer that version.

## Pulling a plugin

To pull your own plugin, open an issue or a pull request that moves its file to `catalog/inactive/`. [What inactive and blocked mean](../catalog/inactive/README.md).

## When the check fails

| The check says | What to do |
|---|---|
| `file name must be <id>.json` | Rename the entry file to match `id` |
| `id is still the template value` (or `repo`, `commit`) | Put in your own values |
| `commit is a placeholder` | Use the full commit from `git rev-parse "<tag>^{commit}"` |
| `does not match '^[0-9a-f]{40}$'` | The commit must be 40 lowercase hex characters, not a short one |
| `Additional properties are not allowed` | Remove keys the entry file doesn't know, like `$schema` or `version` |
| `min_app_version must be 1.2.1 or newer` | Set it to `1.2.1` or later, as `x.y.z` |
| `name is 41 characters; the most is 40` | Shorten that field. The same message covers every length limit |
| `has < or >; plain text only` | Remove HTML or angle brackets from the text |
| `remove 'sha256'; we fill it in when publishing` | Drop `sha256`, `platforms`, `size` and `icon` from `holyarrs-plugin.json` |
| `access is required` | Add `"access": {"hosts": [], "folders": [], "actions": []}` |
| `unknown permission` | Use a name from `.github/scopes.json` |
| `access.actions needs min_app_version 1.3.0` | Set `min_app_version` to `1.3.0` |
| `key must match ^[a-z][a-z0-9_]{0,39}$` | Use a lowercase setting key that starts with a letter |
| `a secret can't have a default` | Remove `default` from that setting |
| `default is not one of its options` | Make the select's default one of `options` |
| `links are not allowed in the plugin folder` | Replace symlinks with real files |
| `go.mod: missing` | The folder must hold the Go program's `go.mod` |
| `id '…' is not the entry's '…'` | Use the same `id` in both files |
| `README.md plugin table is out of date` | Run `python .github/scripts/readme_list.py` and commit the change |

Still stuck? Ask on the [HolyArrs Community](https://community.holyarrs.com/c/help/6), [Discord](https://discord.com/invite/mthsvesKpC) or [open an issue](https://github.com/HolyArrs/HolyArrs-Plugins/issues).
