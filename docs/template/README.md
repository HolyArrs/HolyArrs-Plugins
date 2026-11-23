# The starter file and its rules

- [`plugin.json`](plugin.json) is the starter for your entry file. Copy it to `catalog/active/<id>.json` and fill it in. Its values are fake on purpose, and the check refuses them.
- [`plugin.schema.json`](plugin.schema.json) holds the rules for that entry file.

## How the schema is used

- **In your editor.** Add `"$schema": "https://raw.githubusercontent.com/HolyArrs/HolyArrs-Plugins/main/docs/template/plugin.schema.json"` while you write, or point your editor's JSON schema setting at this file. It then marks wrong fields as you type. Remove the `$schema` line before you open the pull request, because the entry file allows no extra keys.
- **In our check.** `.github/scripts/check.py` tests every entry file against the schema on each pull request, plus a few rules a schema can't say (the file name matches `id`, no template values, `min_app_version` is 1.2.1 or newer).
- **Authors never edit it.** Only we change the schema.

The schema covers the entry file only. Your `holyarrs-plugin.json` has its own rules, which `check.py --src` tests. Both files are explained in [how plugins work](../how-plugins-work.md#the-three-files).
