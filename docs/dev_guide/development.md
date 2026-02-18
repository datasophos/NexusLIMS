(development)=
# Development introduction

If you are interested in learning about how the NexusLIMS back-end works or
adding new features, these instructions should get you up and running with a
development environment that will allow you to modify how the code operates.

Currently, running the NexusLIMS record building back-end code is supported and tested on Linux and MacOS. It does not currently work on Windows due to some specific
implementation choices (although contributions would be accepted for this if it's an important platform for your use case).

## Installation

NexusLIMS uses the [uv](https://docs.astral.sh/uv/) framework
to manage dependencies and create reproducible deployments. This means that
installing the `nexusLIMS` package will require
[installing](https://docs.astral.sh/uv/getting-started/installation/)
`uv`. `uv` will automatically manage Python versions for you, so you don't need
to install Python separately. NexusLIMS requires Python 3.11 or 3.12.
Installing `uv` is usually as simple as:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```{danger}
Never run code downloaded straight from the internet just because someone
tells you to! Make sure to download and inspect the script to ensure it
doesn't do anything nasty before you run it.
```

Once `uv` is installed, clone the NexusLIMS [repository](https://github.com/datasophos/NexusLIMS) using `git`,
and then change to the root folder of the repository. Running the following
`sync`  command will make `uv` install the dependencies specified
in the `uv.lock` file into a local python virtual environment (so they
don't interfere with other Python installations on your system). It will also
install the `nexusLIMS` Python package in "editable" mode so you can make
changes locally for development purposes and still run things.

```bash
$ uv sync
```

```{note}
`uv` automatically creates virtual environments in a local `.venv` folder
by default, keeping all project files in one directory. This eliminates the need
for additional configuration that was required with other package managers.
To see information about your current environment, you can run
`$ uv python list` to see available Python versions or `$ uv pip list`
to see installed packages. This approach keeps the project
files all in one directory, rather than having the Python virtualenv in your
user folder somewhere else on the system. `uv` manages this automatically
without requiring additional configuration.
```

## Setting up the environment

```{note}
**For Development:** If you're just developing NexusLIMS and running the test suite, you **do not need** a full production environment. The integration tests include dockerized versions of all external dependencies (NEMO, CDCS, etc.), so you can develop and test without real credentials or infrastructure.
```

### Production Environment Setup

To interact with the remote systems from which NexusLIMS harvests information in a **production deployment**,
it is necessary to provide credentials for authentication and the paths in which
to search for new data files and where to write dataset previews, as well as
the path to the {doc}`NexusLIMS database <database>`.
These values should be set by copying the `.env.example` file from the git
repository into a file named `.env` in the base directory (in the same folder
as the `README.md` and `pyproject.toml` files).
`nexusLIMS` makes use of the
[dotenv](https://pypi.org/project/python-dotenv/) library to dynamically
load variables from this file when running any `nexusLIMS` code.
As an example, the  `.env` file content should look something like the
following (substituting real credentials, of course). See {ref}`configuration`
for a complete reference of all environment variables.

```bash
NX_CDCS_TOKEN='your-api-token-here'
NX_INSTRUMENT_DATA_PATH='/path/to/mmfnexus/mount'
NX_DATA_PATH='/path/to/nexusLIMS/mount/mmfnexus'
NX_DB_PATH='/path/to/nexusLIMS/nexuslims_db.sqlite'
NX_NEMO_ADDRESS_1='https://path.to.nemo.com/api/'
NX_NEMO_TOKEN_1='authentication_token'
NX_NEMO_STRFTIME_FMT_1="%Y-%m-%dT%H:%M:%S%z"
NX_NEMO_STRPTIME_FMT_1="%Y-%m-%dT%H:%M:%S%z"
NX_NEMO_TZ_1="America/New_York"
```

### Development Environment

For development and testing, the test suite handles environment setup automatically:

- **Unit tests** mock external dependencies and don't require any configuration
- **Integration tests** use Docker Compose to spin up temporary instances of NEMO, CDCS, and other services
- All test fixtures create isolated temporary directories and databases

Simply run:
```bash
./scripts/run_tests.sh
```

No `.env` file or production credentials required!

## Getting into the environment

Once the package is installed using `uv`, the code can be used
like any other Python library within the resulting virtual environment.

`uv` allows you to run a single command inside that environment by
using the `uv run` command from the repository:

```bash
$ uv run python
```

To use other commands in the NexusLIMS environment, you can also "activate"
the environment using the `$ source .venv/bin/activate` command from within the cloned
repository. This will activate the virtual environment that ensures all commands will have
access to the installed packages and environment variables set appropriately.

## Pre-commit Hooks

To ensure code quality and consistency, NexusLIMS uses [pre-commit](https://pre-commit.com/) hooks that automatically run linting checks before each commit. This prevents commits with linting errors from being pushed to the repository.

### Installing Pre-commit Hooks

Pre-commit is included as a dev dependency, so it's already installed when you run `uv sync`. To set up the git hooks:

```bash
$ uv run pre-commit install
```

From now on, linting checks will run automatically whenever you attempt to commit code. If linting errors are found, the commit will be blocked until you fix them.

### Running Pre-commit Manually

To run linting checks on all files without committing:

```bash
$ uv run pre-commit run --all-files
```

To run checks on specific files:

```bash
$ uv run pre-commit run --files <file1> <file2>
```

### Bypassing Pre-commit (Not Recommended)

If you need to bypass the pre-commit hooks in exceptional cases:

```bash
$ git commit --no-verify
```

```{warning}
Only use `--no-verify` in exceptional cases. Pre-commit hooks exist to maintain code quality standards across the project.
```

(testing)=
## Testing and Documentation

### Unit Testing

To run the complete unit test suite, use the provided shell script:

```bash
$ ./scripts/run_tests.sh
```

This will run all unit tests with coverage reporting. To run specific tests:

```bash
$ uv run pytest tests/unit/test_extractors.py
```

To run a specific test:

```bash
$ uv run pytest tests/unit/test_extractors.py::TestClassName::test_method_name
```

To generate matplotlib baseline figures for image comparison tests, run:

```bash
$ ./scripts/generate_mpl_baseline.sh
```

### Integration Testing

Integration tests validate end-to-end workflows using real Docker services (NEMO, CDCS, PostgreSQL, etc.) instead of mocks. These tests ensure the complete system works together correctly.

```bash
# run unit and integration tests together using the included script (requires Docker)
$ ./scripts/run_tests.sh --integration

# Run integration tests (requires Docker)
$ uv run pytest tests/integration/ -v

# Run with coverage
$ uv run pytest tests/integration/ -v --cov=nexusLIMS
```

For detailed information about integration testing, setup, architecture, and best practices, see the {doc}`Integration Testing Guide <testing/integration-tests>`.

**Note:** Integration tests require Docker and Docker Compose to be installed and running. Unit tests do not require Docker and can be run independently.

(documentation)=
### Documentation

To build the documentation for the project, run:

```bash
$ ./scripts/build_docs.sh
```

The documentation will then be present in the `./_build/` directory.

## Building new records

The most basic feature of the NexusLIMS back-end is to check the
{doc}`database <database>` for any logs (typically inserted by the
NEMO harvester) with a status of
`'TO_BE_BUILT'`. This can be accomplished simply by running the
{py:mod}`~nexusLIMS.builder.record_builder` module directly via:

```bash
$ uv run nexuslims build-records
```

This command will find any records that need to be built, build their .xml
files, and then upload them to the front-end CDCS instance. Consult the
record building {doc}`documentation <../user_guide/record_building>` for more details.

## Using other features of the library

Once you are in a python interpreter (such as `python`, `ipython`,
`jupyter`, etc.) from the `uv` environment, you can access the
code of this library through the `nexusLIMS` package if you want to do other
tasks, such as extracting metadata or building previews images, etc.

For example, to extract the metadata from a `.tif` file saved on the
FEI Quanta, run the following code using the
{py:func}`~nexusLIMS.extractors.plugins.quanta_tif.get_quanta_metadata` function:

```python
from nexusLIMS.extractors.plugins.quanta_tif import get_quanta_metadata
meta = get_quanta_metadata("path_to_file.tif")
```

The `meta` variable will then contain a dictionary with the extracted
metadata from the file.


## Contributing

### AI Policy

AI-assisted development is allowed and used extensively in NexusLIMS itself.
We find it a useful tool when applied with care and judgment. That said, a few
expectations apply to AI-assisted contributions:

- **Disclose AI use** in your pull request description. A brief note is fine —
  just be honest about which parts were AI-assisted.
- **You are responsible for the code you submit.** AI output must be reviewed,
  understood, and tested by you before submitting. The same code review
  standards apply regardless of how the code was written.
- **Automated contributions are not accepted.** Pull requests generated and
  submitted by an AI agent without meaningful human involvement will be closed.
  A human must be the author and must stand behind the contribution.

### How to contribute

To contribute, please fork the repository, develop your addition on a
[feature branch](https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow)
within your forked repo, and submit a pull request to the `main`
branch to have it included in the project. Contributing to the package
requires that every line of code is covered by a test case. This project uses
testing through the [pytest](https://docs.pytest.org/en/latest/) library,
and features that do not pass the test cases or decrease coverage will not be
accepted until suitable tests are included (see the `tests` directory
for examples) and that the coverage of any new features is 100%.

For example, the following output is shown when running the full test suite, which will highlight any lines that are not covered:

```bash
$ cd <path_to_repo>
$ uv run ./scripts/run_tests.sh --integration
```

```text
Running unit and integration tests...
====================================== test session starts ===========================================
platform darwin -- Python 3.11.14, pytest-9.0.1, pluggy-1.6.0
Matplotlib: 3.10.7
Freetype: 2.6.1
rootdir: /Users/josh/git_repos/datasophos/NexusLIMS
configfile: pyproject.toml
plugins: docker-3.2.5, timeout-2.4.0, mpl-0.17.0, cov-7.0.0
collected 993 items

tests/integration/test_cdcs_integration.py .....................................                [  3%]
tests/integration/test_cli.py ..........                                                        [  4%]
tests/integration/test_end_to_end_workflow.py ....                                              [  5%]
tests/integration/test_fileserver.py ....                                                       [  5%]
tests/integration/test_fixtures_smoke.py ............                                           [  6%]
tests/integration/test_nemo_integration.py .......................................              [ 10%]
tests/integration/test_nemo_multi_instance.py ................                                  [ 12%]
tests/integration/test_partial_failure_recovery.py .....                                        [ 12%]
tests/unit/cli/test_process_records.py ............................                             [ 15%]
tests/unit/test___init__.py ........                                                            [ 16%]
tests/unit/test___main__.py .                                                                   [ 16%]
tests/unit/test_cdcs.py .............                                                           [ 17%]
tests/unit/test_config.py ...................                                                   [ 19%]
tests/unit/test_extractors/test_basic_metadata.py ..                                            [ 19%]
tests/unit/test_extractors/test_digital_micrograph.py ................................          [ 23%]
tests/unit/test_extractors/test_edax.py ...                                                     [ 23%]
tests/unit/test_extractors/test_extractor_module.py ..........................................  [ 27%]
tests/unit/test_extractors/test_fei_emi.py .........................                            [ 30%]
tests/unit/test_extractors/test_instrument_profile_modules.py ...................               [ 32%]
tests/unit/test_extractors/test_orion_HIM.py ................................                   [ 35%]
tests/unit/test_extractors/test_plugins.py ....................................                 [ 38%]
tests/unit/test_extractors/test_profiles.py .................................                   [ 42%]
tests/unit/test_extractors/test_quanta_tif.py ................                                  [ 43%]
tests/unit/test_extractors/test_registry.py ................................................... [ 52%]
tests/unit/test_extractors/test_schemas.py ...................................                  [ 56%]
tests/unit/test_extractors/test_tescan_tif.py ........................................          [ 60%]
tests/unit/test_extractors/test_thumbnail_generator.py ....................................     [ 63%]
tests/unit/test_extractors/test_utils.py ...                                                    [ 64%]
tests/unit/test_extractors/test_xml_serialization.py ...................                        [ 66%]
tests/unit/test_harvesters/test_init.py ..                                                      [ 66%]
tests/unit/test_harvesters/test_nemo_api.py .........................................           [ 70%]
tests/unit/test_harvesters/test_nemo_connector.py .........................                     [ 72%]
tests/unit/test_harvesters/test_nemo_utils.py .........                                         [ 73%]
tests/unit/test_harvesters/test_reservation_event.py ......                                     [ 74%]
tests/unit/test_instruments.py .................                                                [ 76%]
tests/unit/test_network_resilience.py ...............                                           [ 77%]
tests/unit/test_record_builder/test_activity.py .............                                   [ 78%]
tests/unit/test_record_builder/test_record_builder.py .........................                 [ 81%]
tests/unit/test_schemas/test_em_glossary.py ............................................        [ 85%]
tests/unit/test_schemas/test_metadata.py ...............................................        [ 90%]
tests/unit/test_schemas/test_pint_types.py .................                                    [ 92%]
tests/unit/test_schemas/test_units.py ..................................                        [ 95%]
tests/unit/test_sessions.py ........                                                            [ 96%]
tests/unit/test_utils.py .................................                                      [ 99%]
tests/unit/test_version.py .                                                                    [100%]

====================================== tests coverage ================================================
____________________ coverage: platform darwin, python 3.11.14-final-0 _______________________________

Name                                                                  Stmts   Miss  Cover   Missing
------------------------------------------------------------------------------------------------------
nexusLIMS/__init__.py                                                    18      0   100%
nexusLIMS/__main__.py                                                     3      0   100%
nexusLIMS/builder/__init__.py                                             0      0   100%
nexusLIMS/builder/record_builder.py                                     199      0   100%
nexusLIMS/cdcs.py                                                       117      0   100%
nexusLIMS/cli/__init__.py                                                 0      0   100%
nexusLIMS/cli/process_records.py                                        144      0   100%
nexusLIMS/config.py                                                     153      0   100%
nexusLIMS/db/__init__.py                                                  7      0   100%
nexusLIMS/db/session_handler.py                                          98      0   100%
nexusLIMS/extractors/__init__.py                                        168      0   100%
nexusLIMS/extractors/base.py                                             38      0   100%
nexusLIMS/extractors/plugins/__init__.py                                  1      0   100%
nexusLIMS/extractors/plugins/basic_metadata.py                           27      0   100%
nexusLIMS/extractors/plugins/digital_micrograph.py                      350      0   100%
nexusLIMS/extractors/plugins/edax.py                                    106      0   100%
nexusLIMS/extractors/plugins/fei_emi.py                                 271      0   100%
nexusLIMS/extractors/plugins/orion_HIM_tif.py                           199      0   100%
nexusLIMS/extractors/plugins/preview_generators/__init__.py               4      0   100%
nexusLIMS/extractors/plugins/preview_generators/hyperspy_preview.py     358      0   100%
nexusLIMS/extractors/plugins/preview_generators/image_preview.py         62      0   100%
nexusLIMS/extractors/plugins/preview_generators/text_preview.py          86      0   100%
nexusLIMS/extractors/plugins/profiles/__init__.py                        47      0   100%
nexusLIMS/extractors/plugins/profiles/fei_titan_stem_643.py              25      0   100%
nexusLIMS/extractors/plugins/profiles/fei_titan_tem_642.py               53      0   100%
nexusLIMS/extractors/plugins/profiles/jeol_jem_642.py                    22      0   100%
nexusLIMS/extractors/plugins/quanta_tif.py                              353      0   100%
nexusLIMS/extractors/plugins/tescan_tif.py                              248      0   100%
nexusLIMS/extractors/profiles.py                                         29      0   100%
nexusLIMS/extractors/registry.py                                        226      0   100%
nexusLIMS/extractors/utils.py                                           195      0   100%
nexusLIMS/extractors/xml_serialization.py                                48      0   100%
nexusLIMS/harvesters/__init__.py                                          5      0   100%
nexusLIMS/harvesters/nemo/__init__.py                                    36      0   100%
nexusLIMS/harvesters/nemo/connector.py                                  256      0   100%
nexusLIMS/harvesters/nemo/exceptions.py                                   2      0   100%
nexusLIMS/harvesters/nemo/utils.py                                       68      0   100%
nexusLIMS/harvesters/reservation_event.py                               130      0   100%
nexusLIMS/instruments.py                                                 91      0   100%
nexusLIMS/schemas/__init__.py                                             5      0   100%
nexusLIMS/schemas/activity.py                                           216      0   100%
nexusLIMS/schemas/em_glossary.py                                        111      0   100%
nexusLIMS/schemas/metadata.py                                           101      0   100%
nexusLIMS/schemas/pint_types.py                                          41      0   100%
nexusLIMS/schemas/units.py                                              102      0   100%
nexusLIMS/utils.py                                                      222      0   100%
nexusLIMS/version.py                                                      2      0   100%
------------------------------------------------------------------------------------------------------
TOTAL                                                                  5043      0   100%
Coverage HTML written to dir tests/coverage
Coverage XML written to file coverage.xml
================================ 993 passed in 146.72s (0:02:26) =====================================
```


## Release Process

This section describes how to create a new release of NexusLIMS.

### Quick Start

```bash
# Standard release
./scripts/release.sh "2.0.0"

# Preview what will happen (dry-run)
./scripts/release.sh "2.0.1" --dry-run

# Auto-approve prompts
./scripts/release.sh "2.0.2" --yes
```

### Prerequisites

1. **Clean working directory**: Commit or stash any uncommitted changes
2. **Towncrier fragments**: Add changelog fragments to `docs/changes/` for all changes since last release
3. **Branch**: Typically on `main` branch (or your release branch)
4. **Tests passing**: Ensure all tests pass with `./scripts/run_tests.sh`
5. **Linting passing**: Ensure linting passes with `./scripts/run_lint.sh`

### Creating Towncrier Fragments

Before releasing, create changelog fragments for all notable changes:

```bash
# Fragment naming: <number>.<type>.md or +<number>.<type>.md
# Use <number> to link to GitHub issue #<number>
# Use +<number> for fragments without issue links
# Types: feature, bugfix, enhancement, doc, misc, removal

# Example fragments:
echo "Added new NEMO harvester for multi-instance support" > docs/changes/42.feature.md
echo "Fixed metadata extraction for FEI TIFF files" > docs/changes/43.bugfix.md
echo "Improved performance of file clustering algorithm" > docs/changes/+44.enhancement.md
```

Fragment types correspond to sections in the changelog:

- **feature**: New features
- **bugfix**: Bug fixes
- **enhancement**: Enhancements
- **doc**: Documentation improvements
- **misc**: Miscellaneous/Development changes
- **removal**: Deprecations and/or Removals

### Release Workflow

#### 1. Prepare the Release

```bash
# Ensure you're on the correct branch
git checkout main
git pull origin main

# Run tests
./scripts/run_tests.sh

# Run linting
./scripts/run_lint.sh

# Preview the changelog
./scripts/release.sh "2.0.0" --draft
```

#### 2. Create the Release

```bash
# Interactive release (recommended for first time)
./scripts/release.sh "2.0.0"

# Or with auto-confirmation
./scripts/release.sh "2.0.0" --yes
```

The script will:

1. ✓ Update version in `pyproject.toml`
2. ✓ Generate changelog from towncrier fragments (adds to `docs/changelog.md`)
3. ✓ Delete consumed changelog fragments
4. ✓ Commit changes
5. ✓ Create git tag for the version
6. ✓ Push to remote (with confirmation)

#### 3. Monitor Automated Process

Once the tag is pushed, GitHub Actions automatically:

1. Builds distribution packages (wheel and sdist)
2. Publishes to PyPI
3. Creates GitHub Release with auto-generated notes
4. Deploys versioned documentation to GitHub Pages

Monitor progress at: [https://github.com/datasophos/NexusLIMS/actions](https://github.com/datasophos/NexusLIMS/actions)

### Script Options

```text
./scripts/release.sh [VERSION] [OPTIONS]

Options:
  -h, --help    Show help message
  -d, --dry-run Run without making changes (preview only)
  -y, --yes     Skip confirmation prompts
  --no-push     Don't push to remote (tag locally only)
  --draft       Generate draft changelog without committing
```

### Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (X.0.0): Breaking changes, incompatible API changes
- **Minor** (x.Y.0): New features, backwards-compatible
- **Patch** (x.y.Z): Bug fixes, backwards-compatible

Pre-release versions:

- `2.0.0-alpha1`: Alpha releases
- `2.0.0-beta1`: Beta releases
- `2.0.0-rc1`: Release candidates

### Troubleshooting

#### "Working directory is not clean"

Commit or stash your changes:

```bash
git status
git add .
git commit -m "Your changes"
```

#### "No towncrier fragments found"

Add at least one changelog fragment:

```bash
echo "Your change description" > docs/changes/+1.misc.md
```

#### Need to fix a release tag

If you need to redo a release:

```bash
# Delete local tag
git tag -d v2.0.0

# Delete remote tag (CAUTION!)
git push origin :refs/tags/v2.0.0

# Re-run release script
./scripts/release.sh 2.0.0
```

#### Release workflow failed on GitHub

Check the Actions tab for error details. Common issues:

- PyPI credentials not configured (requires trusted publishing setup)
- Package build errors (test locally with `uv build`)
- Documentation build errors (test with `./scripts/build_docs.sh`)

### Manual Release (Without Script)

If you need to release manually:

```bash
# 1. Update version
sed -i 's/version = ".*"/version = "2.0.0"/' pyproject.toml

# 2. Generate changelog
uv run towncrier build --version=2.0.0 --yes

# 3. Commit and tag
git add pyproject.toml docs/
git commit -m "Release v2.0.0"
git tag -a v2.0.0 -m "Release 2.0.0"

# 4. Push
git push origin main
git push origin v2.0.0
```

### Post-Release Checklist

- Verify package on PyPI: [https://pypi.org/project/nexusLIMS/](https://pypi.org/project/nexusLIMS/)
- Check GitHub Release: [https://github.com/datasophos/NexusLIMS/releases](https://github.com/datasophos/NexusLIMS/releases)
- Verify documentation: [https://datasophos.github.io/NexusLIMS/stable/](https://datasophos.github.io/NexusLIMS/stable/)
- Test installation: `pip install nexusLIMS==2.0.0`
- Announce release (if applicable)
- Update dependent projects/deployments
