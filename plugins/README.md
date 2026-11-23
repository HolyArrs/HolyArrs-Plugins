# Our plugins

This folder holds the plugins the HolyArrs team makes itself, one folder each (for example [`tailscale/`](tailscale/)).

We build, review and sign them the same way as everyone's. Each one has an entry in [`../catalog/`](../catalog/), just like a community plugin. Community plugins live in their authors' own repos and are listed in the catalog too.

Each of ours is released with its own tag, named after the folder and the version, like `tailscale-v1.0.0`. The catalog entry points at that tag and its commit.

## Build and test one

Every plugin is one Go program. From its folder:

```sh
cd tailscale
go vet ./...
go test ./...
go build -trimpath .
```

To make your own, start with [making a plugin](../docs/making-a-plugin.md).
