# Adding a plugin

A pull request adds one file, `catalog/active/<id>.json`, for one plugin. The guide is [docs/making-a-plugin.md](../docs/making-a-plugin.md).

Before you open it, run the check on your entry file and your plugin folder:

```sh
python .github/scripts/check.py catalog/active/<id>.json --src /path/to/your/plugin
```

Your plugin folder needs `go.mod` and a `holyarrs-plugin.json` with at least `id`, `name`, `author`, `licence`, `support_email`, `min_app_version` and `access`. To list it, fork this repo, add `catalog/active/<id>.json` and open one pull request. A new version is a new pull request that changes `tag` and `commit`.
