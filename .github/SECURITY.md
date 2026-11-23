# Security

## Reporting a harmful plugin or a key leak

Please report it privately through [GitHub security advisories](https://github.com/HolyArrs/HolyArrs/security/advisories/new) on the main HolyArrs repo, not in a public issue.

Tell us the plugin id, the version and, if you have it, the sha256 of the plugin file. If you think the signing key has leaked, say so in the title.

## What's covered

- The signed lists: `plugins.json` and `blocklist.json`.
- The plugin files and plugin details on plugins.holyarrs.com.
- The workflows that sign and publish them.

## What happens next

We block a confirmed harmful version. From 1.2.1, HolyArrs will refuse to install it and switch off running copies at its next check, within 6 hours.

If the signing key leaks, we re-sign the lists with the offline backup key, and a new main key ships in the next HolyArrs release. The steps are in [the plugin signing key](https://github.com/HolyArrs/HolyArrs/blob/main/docs/plugin-signing-key.md).
