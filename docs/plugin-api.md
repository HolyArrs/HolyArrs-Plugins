# Plugin reference

This page shows what a plugin gets from HolyArrs 1.3.0, and what it does not get.

## The short version

A plugin is one Linux program. HolyArrs starts it, keeps it in a sandbox, and stops it. A plugin gets its settings and its data folder through environment variables and writes logs to its output.

It talks to HolyArrs over plain HTTP, never by listening on a port:

- **API calls.** `HOLYARRS_PLUGIN_TARGET` is HolyArrs' local address and `HOLYARRS_PLUGIN_TOKEN` a key that's new on every start. Send `Authorization: Bearer $HOLYARRS_PLUGIN_TOKEN`. Only the routes covered by its approved permissions (`access.actions`) answer; everything else is 403. Calls are rate-limited and logged on the plugin's card.
- **Hooks.** A plugin that is a download client, search source, metadata source, MCP tool, page, widget or event listener long-polls `GET /api/v1/plugin-hooks/<hook>` for work and answers with `POST`. Each hook needs its own permission.
- **Acting for a person.** `POST /api/v1/plugin-hooks/link` returns a code to show the person; they enter it in My account → Linked plugins. Then send `X-Holyarrs-For-User` on request, limit and follow calls; each needs both the plugin's permission and that person's own.

## What happens when

| Moment | What HolyArrs does |
|---|---|
| Install | Downloads the newest listed version for this CPU type. Checks the list signature, the list and blocklist counters, the file hash and `min_app_version`. Saves it and starts it. |
| Start | Hashes the program again, copies it to a fresh run file and starts that copy in the sandbox. |
| Save settings | Writes the values. If the plugin runs, stops it and starts it again so it reads the new values. |
| Stop | Kills the plugin and everything it started. The plugin stays off until the owner starts it. |
| Ends on its own | Logged as "stopped on its own" and turned off. HolyArrs does not restart it. |
| Update | Same as install. A plugin the owner stopped stays stopped after the update. |
| Blocked | Checked at start and every 6 hours. A blocked version is stopped and turned off, and the Plugins page shows it's on the blocklist. If plugins.holyarrs.com can't be reached, nothing changes until the next check. |
| HolyArrs starts | Starts every plugin that was on. In safe mode (`HOLYARRS_SAFE_MODE=1` or `--safe-mode`) no plugin starts, so you can remove one that breaks things. |
| Remove | Stops it and deletes its folder, which holds its program, its data and its saved settings and secrets. Folders the owner approved for it are not touched. |

Only the owner, signed in, can install, start, stop or change plugins. API keys can't.

## Environment variables

The plugin gets only these. Everything else from HolyArrs' own environment is left out.

| Variable | Value |
|---|---|
| `HOLYARRS_PLUGIN_DATA` | Full path of the plugin's data folder |
| `HOME` | Same path as the data folder |
| `PATH`, `TZ` | Copied from HolyArrs when set |
| `HOLYARRS_PLUGIN_SETTING_<KEY>` | One per setting, key in capitals. Saved value, or the default |
| `HOLYARRS_PLUGIN_FOLDER_<NAME>` | One per approved folder, name in capitals |
| `HOLYARRS_PLUGIN_FOLDERS` | The names of all approved folders |
| `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY`, `NO_PROXY` (and lowercase) | The plugin's own proxy, when it lists hosts. Go's `net/http` uses them on its own |
| `HOLYARRS_PLUGIN_NO_UDP` | Always `1`: UDP is blocked |

Example for a setting with key `api_url`:

```sh
HOLYARRS_PLUGIN_DATA=/config/plugins/my-plugin/data
HOLYARRS_PLUGIN_SETTING_API_URL=https://example.com
```

The working folder is the data folder too.

The Tailscale plugin, which we make, gets two more: `HOLYARRS_PLUGIN_TARGET` (HolyArrs's own address on `127.0.0.1`, the one extra place it may connect to) and `HOLYARRS_PLUGIN_MARK` (a tag it puts on every visit it passes on, so HolyArrs treats those visits as coming from outside and still asks for sign-in). It gets no other rights: no UDP, no listening, the same sandbox.

## Settings

A plugin lists its settings in the manifest under `settings`. Up to 20. The Plugins page builds the form from them. These are the limits our check enforces when you submit. This table is the only copy; other pages link here.

| Field | Rule |
|---|---|
| `key` | Lowercase letters, digits and `_`, starts with a letter, up to 40 characters, unique |
| `label` | Up to 48 characters, plain text |
| `type` | `text`, `number`, `toggle`, `select` or `secret` |
| `default` | Optional. Write it as the value: text in quotes, a number like `30`, a toggle as `true` or `false`. A `select` default is one of its options. A `secret` has none |
| `options` | For `select` only. 1 to 12 choices, up to 40 characters each |
| `help` | Optional. Up to 160 characters |

| Type | On the page | Value the plugin gets |
|---|---|---|
| `text` | Text box, under Connection | The text |
| `number` | Short number box, under Connection | The number as text |
| `select` | Drop-down, under Connection | One of the options. With no default, the first one |
| `toggle` | Checkbox, under Permissions | `true` or `false`. With no default, `false` |
| `secret` | Password box, under Security | The text. Stored encrypted, never shown again, can't have a default |

A saved value can be up to 2000 characters. Secrets are stored encrypted, but the plugin gets them as plain text. It can send them only to its listed hosts, and it must never print them, because its output goes to the HolyArrs log.

```json
"settings": [
  { "key": "api_url", "label": "Server address", "type": "text", "default": "https://example.com" },
  { "key": "every", "label": "Check every (minutes)", "type": "number", "default": 30 },
  { "key": "mode", "label": "Mode", "type": "select", "options": ["fast", "careful"] },
  { "key": "verbose", "label": "More log lines", "type": "toggle" },
  { "key": "token", "label": "Access token", "type": "secret", "help": "From your account page." }
]
```

## The data folder

Each plugin has one folder it may read and write: `plugins/<id>/data` inside the HolyArrs config folder. It survives restarts and updates. It goes when the plugin is removed.

## The access lists

The manifest has three lists. The Plugins page shows all three before install.

| List | What it means |
|---|---|
| `access.hosts` | Up to 100. The only hosts it can reach, once the owner approves: names or `*.` wildcards, through a per-plugin proxy on 443 and 80. No raw IPs, no LAN unless the owner adds the host (up to 100, may give a port), no UDP, no listening. |
| `access.folders` | Folders the owner picks and approves, read or read-write. A name or `{"name", "mode", "why", "required"}`; each arrives as `HOLYARRS_PLUGIN_FOLDER_<NAME>`, all in `HOLYARRS_PLUGIN_FOLDERS`. |
| `access.actions` | HolyArrs 1.3.0+: the HolyArrs permissions it needs, from [.github/scopes.json](../.github/scopes.json). Shown to the owner by group, with red warnings for deletes, file changes, forwarding and acting as a download client. The plugin calls `HOLYARRS_PLUGIN_TARGET` with `Authorization: Bearer $HOLYARRS_PLUGIN_TOKEN`; anything outside its permissions answers 403. |

Hosts and folders can't contain `..` or `\`. Folder names have no `/` or `:`. An update that asks for more access waits for the owner.

## Logs

Every line the plugin writes to stdout or stderr goes to the HolyArrs log as `plugin <id>: <line>`.

| Limit | Value |
|---|---|
| Line length | 64 KB, longer lines end with `[line cut]` |
| Lines | 200 per 10 seconds, then a note says how many were dropped |

## Health

HolyArrs knows two things: running or not, and why it stopped. When the program ends, the reason shows on the Plugins page and the plugin turns off. A plugin that wants to stay up must keep running.

## The sandbox

| Limit | Value |
|---|---|
| Runs on | Linux only, which includes the Docker image |
| Files | Read and write its data folder and approved folders. Read its own program and `/etc/ssl/certs`, `/etc/resolv.conf`, `/etc/hosts`, `/dev/null`, `/dev/urandom`. Nothing else |
| Memory | 512 MiB |
| Processor | 1 CPU core |
| Processes | 256 |
| Open files | 1024 |
| Other | No new privileges, no core dumps, own process group, `GO*` variables removed |
| Newer kernels | Can't signal processes or reach abstract sockets outside its sandbox |
| Network | Listed hosts only, through the proxy. Needs kernel 5.9+ |

The file lock uses Landlock, and the memory, processor and process caps need cgroups v2. Without them, see [when the sandbox is weaker](#when-the-sandbox-is-weaker).

<a id="when-the-sandbox-is-weaker"></a>
## When the sandbox is weaker

The locks need features of the Linux kernel. When the file lock or the network lock is missing, the Plugins page says so, and plugins start without it only if the owner allows that there, once for all plugins. HolyArrs logs every start without a lock. Without cgroups v2, plugins start without the caps and the page doesn't warn.

| Missing | Needed for | What the plugin can do without it |
|---|---|---|
| Kernel 5.9 or newer | The network lock | Open TCP connections to any address, including your LAN and HolyArrs itself. UDP and raw sockets stay blocked |
| Landlock | The file lock | Read and write every file HolyArrs can, including your media and the HolyArrs database. The other limits stay on |
| cgroups v2 | Memory, processor and process caps | Use as much memory and CPU as it likes. Stop still kills its whole process group |

Allowing a start without a lock means trusting that plugin as much as HolyArrs itself. The sandbox lowers risk; it is not a promise. A listed host gets everything the plugin sends it.

## What a plugin can't do

The full can and can't list is in [how plugins work](how-plugins-work.md#what-a-plugin-can-and-cant-do). In short: nothing outside its approved permissions, nothing in the always-closed areas (the plugin system, accounts and sign-in, passwords and connection secrets, server settings and controls), no restarting itself, and no Windows or macOS.
