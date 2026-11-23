# Language packs

Every HolyArrs language other than English, as signed packs the app installs
from plugins.holyarrs.com. English is built into the app.

- `<code>.json`: one language (`{lang, app, fit, values}`), as the HolyArrs build
  writes it to `app/frontend/lang-out`. All files are for one app version (`app`).
- `source/en.json`: the English lines of that same build, used to check that every
  translation keeps English's `{slots}` and tags.
- `catalog/active/language-packs.json` (repo root): the index of these files. Rebuild it with
  `python3 .github/scripts/languages.py index`; `check` must pass before publishing.

The "HolyArrs Plugins - Publish (id language-packs)" workflow packs each file as
`languages/<code>/<app>.json.bz2` and signs `languages.json`. A published pack
never changes: new text needs a new app version.
