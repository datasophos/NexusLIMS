## Welcome to version 2.9.0 of NexusLIMS!

### Highlights

NexusLIMS is now configured using a persistent configuration file, rather than using a `.env` file in the working directory, with tools to inspect and migrate settings. This release also adds metadata extraction and previews for Asylum Research AFM IBW files, developed with sponsorship from the University of Pennsylvania's Singh Center.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### Upgrade Instructions

> [!CAUTION]
> Configuration changes are required when upgrading if you rely on a `.env` file in the working directory. NexusLIMS no longer loads that file automatically; migrate it using the instructions below or select your existing `.env` file explicitly with `NX_CONFIG_FILE`.

#### Migrate an existing `.env` configuration

NexusLIMS no longer automatically reads `.env` from the working directory. After upgrading to 2.9.0, run the following from the directory containing your existing `.env` file to create a user-level `config.toml`:

```bash
backup=$(mktemp "${TMPDIR:-/tmp}/nexuslims-config.XXXXXX")
NX_CONFIG_FILE="$PWD/.env" nexuslims config dump --output "$backup" &&
env -u NX_CONFIG_FILE nexuslims config load "$backup" \
  --config-path "$HOME/.config/nexuslims/config.toml"

# if you want a system level configuration, replace "$HOME/.config/nexuslims/config.toml"
# with "/etc/nexuslims/config.toml" in the above command
```

See the updated [configuration guide](https://datasophos.github.io/NexusLIMS/stable/user_guide/configuration.html) for more details.

### New Features

**Persistent configuration** ([#136](https://github.com/datasophos/NexusLIMS/pull/136))

- NexusLIMS is now configured by default through `~/.config/nexuslims/config.toml` or `/etc/nexuslims/config.toml`, independently of the working directory.
- The new `nexuslims config status` command shows which configuration file is selected and which environment variables override it.
- Configuration commands support `--config-path` for selecting a file; the older `--env-path` argument remains supported.
- The configuration editor shows which file is being edited and warns when an explicitly chosen file is inactive.

**Asylum Research AFM files** ([#133](https://github.com/datasophos/NexusLIMS/pull/133))

- Metadata extraction and previews are available for image and force-curve IBW files.
- The image previews use line-by-line background flattening to enhance contrast.
- We are immensely grateful for sponsorship from the University of Pennsylvania's Singh Center Development of the AFM extractor.

### Documentation Improvements

- Moved individual configuration settings to a dedicated reference page. ([#136](https://github.com/datasophos/NexusLIMS/pull/136))
- Pull request documentation previews are now built on Cloudflare. ([#135](https://github.com/datasophos/NexusLIMS/pull/135))
- The [NexusLIMS-CDCS frontend guide](https://datasophos.github.io/NexusLIMS-CDCS/stable/) has been moved to CDCS project. ([#138](https://github.com/datasophos/NexusLIMS/pull/138))

### Installation

```bash
# Upgrade an existing uv tool install:
uv tool upgrade nexuslims

# New installation:
uv tool install nexuslims==2.9.0

# Or:
pip install nexuslims==2.9.0

# Or, if installed from source:
git fetch
git checkout v2.9.0
uv sync
```

### Full changelog

[Changes from v2.8.0 to v2.9.0](https://github.com/datasophos/NexusLIMS/compare/v2.8.0...v2.9.0)
