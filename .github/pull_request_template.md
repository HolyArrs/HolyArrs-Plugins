## Plugin

- Id:
- Repo:
- Tag and commit:
- Websites it calls:

## Checklist

- [ ] One file in `catalog/active/`, named `<id>.json`, copied from `docs/template/plugin.json`
- [ ] `commit` is the full commit the tag points to
- [ ] The repo is public and has a licence
- [ ] `access.hosts` lists every website the code calls (nothing else is reachable from 1.2.1); each folder says its `mode` and `why`; `actions` is empty
- [ ] `python .github/scripts/check.py catalog/active/<id>.json --src <plugin folder>` passed
- [ ] I ran it locally with `go run` and it stopped cleanly
