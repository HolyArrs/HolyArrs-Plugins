# How plugins work

This page shows how the pieces fit: the files you write, what our workflow adds, and what a plugin may do once HolyArrs runs it.

To make one step by step, see [making a plugin](making-a-plugin.md). Every detail a plugin gets is in the [plugin reference](plugin-api.md).

<a id="review"></a>
## How a plugin is checked before you get it

The steps a plugin passes are in the [review chart on the README](../README.md#signing). The build details behind them:

The build job has no secrets. The signing key lives only in a separate job that never runs plugin code. The build uses Go from the HolyArrs repo (`GOTOOLCHAIN=local`), `-mod=readonly`, and fetches modules through proxy.golang.org with the checksum database on, so `go.sum` decides every module version.

<a id="the-three-files"></a>
## Ours and the community's

The `plugins/` folder in this repo holds only the plugins we make ourselves. Community plugins stay in their authors' own repos and are listed in `catalog/` the same way ours are. Every plugin, ours included, goes through the same review and signing.

## The three files

| File | Where it lives | Who writes it | What it's for |
|---|---|---|---|
| `holyarrs-plugin.json` | Your plugin folder, next to `go.mod` | You | Everything people see on the Plugins page: name, author, descriptions, steps, category, licence, support, logo, the websites it calls, its settings and the oldest HolyArrs it needs. |
| `catalog/active/<id>.json` | This repo | You, through a pull request | The pointer: where your code lives and which tag and commit we build. |
| `docs/template/plugin.schema.json` | This repo | Us only | The rules for the entry file. Your editor and our check use it. It doesn't cover `holyarrs-plugin.json`; `check.py --src` tests that one. |

## What you write and what we add

| | You write | The publish workflow adds |
|---|---|---|
| Version | The tag in your entry file, like `1.0.0` | The published version, the tag without a leading `v` |
| Files | Source only | Builds for linux amd64, arm64 and armv7, a source archive, fingerprints (`sha256`) |
| Details | All fields in `holyarrs-plugin.json` | `platforms`, `size`, `sha256`, and your logo copied to plugins.holyarrs.com |
| Trust | Nothing | Your version in the signed list for each CPU type |

Never put `sha256`, `platforms`, `size` or `icon` in `holyarrs-plugin.json`. The check refuses them, because we fill them in.

A published version never changes. A fix gets a new tag and a new pull request.

## What happens in HolyArrs

Install, start, settings, crashes, updates and blocks are covered step by step in the [plugin reference](plugin-api.md#what-happens-when). In short: HolyArrs checks the signature and fingerprint before it installs, checks the file again before every start, restarts the plugin when you save its settings, and leaves it off if it stops on its own.

<a id="what-a-plugin-can-and-cant-do"></a>
## What a plugin can and can't do

| | Can | Can't |
|---|---|---|
| 📂 Files | Read and write its own data folder. Read its own program, `/etc/ssl/certs`, `/etc/resolv.conf`, `/etc/hosts`, `/dev/null` and `/dev/urandom`. | Touch any other path. Your media is out of reach unless you approve its folder; the HolyArrs database always is. |
| 🌐 Websites | Call the websites it lists in `access.hosts`, once you approve them, plus up to 100 addresses you add. Every call goes through its own proxy. | Reach any other website, open its own connections or use UDP. Reviewers also refuse code that hides network use. |
| 🔌 HolyArrs | Use the HolyArrs permissions it lists in `access.actions`, once you approve them (1.3.0+). | Touch the always-closed areas: the plugin system, accounts and sign-in, passwords and connection secrets, server settings and controls. |
| 📁 Extra folders | Use each folder in `access.folders` that you approve, read-only or read and write. Each arrives as `HOLYARRS_PLUGIN_FOLDER_<NAME>`. | Reach system folders or HolyArrs's own config. An update that asks for more waits for your OK. |
| ⚙️ Settings | Read up to 100 settings as `HOLYARRS_PLUGIN_SETTING_<KEY>`. | Read other plugins' settings or HolyArrs's own. |
| 🧬 Processes | Start helper processes inside its own limits. | Gain more rights, signal processes outside itself (on newer kernels), or outlive a stop. |
| 📤 Output | Write to stdout and stderr. Both land in the HolyArrs log under the plugin's id. | Show its own pages inside HolyArrs. |
| 📦 Code | Run the Go program we built from your source. | Download and run other code at run time, or ship prebuilt programs. |

These rules hold when the host has every sandbox feature. On older kernels some locks can be missing; [what changes then](plugin-api.md#when-the-sandbox-is-weaker). The exact variables and limits are in the [plugin reference](plugin-api.md#the-sandbox).

Plugins we retire or pull move to `catalog/inactive/`; see [what that means](../catalog/inactive/README.md).
