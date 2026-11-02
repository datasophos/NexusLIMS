# Documentation Previews

NexusLIMS uses Cloudflare Pages to build documentation previews for pull
requests. The Cloudflare GitHub integration posts a link to the preview on the
pull request and updates it when changes are pushed to the branch. Published
release and development documentation is hosted on GitHub Pages; the version
switcher links to those published versions.

## Preview Builds

Cloudflare builds previews independently of the GitHub Actions integration
tests. Preview builds use the documentation and code from the pull request
branch, with the following exceptions:

- The database schema PNG and terminal demonstration media come from the
  published `latest` documentation. Changes to these images appear after the
  full documentation build regenerates them.
- The Mermaid database schema diagram is generated from the preview branch.

Cloudflare Pages does not build previews for pull requests from forks. A
maintainer can push a branch to the NexusLIMS repository to make a preview
available for a fork contribution.

## Cloudflare Configuration

The `nexuslims-docs` Pages project is connected to the
`datasophos/NexusLIMS` GitHub repository. Its build configuration is:

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Automatic production deployments | Disabled |
| Preview deployments | All non-production branches |
| Pull request comments | Enabled |
| Build command | `bash scripts/build_cloudflare_docs.sh` |
| Build output directory | `_build` |
| Build environment variables | `PYTHON_VERSION=3.11`, `SKIP_DEPENDENCY_INSTALL=1` |

The build command installs the dependencies, generates the version switcher,
restores the published images, and builds the documentation in strict mode.

## Preview Cleanup

The preview reconciliation workflow removes Cloudflare deployments for closed
pull requests. It runs on pull request events and every 15 minutes, using code
from the default branch. A branch is excluded from cleanup while it is used by
an open pull request.

The workflow uses the `CLOUDFLARE_PREVIEW_TOKEN` GitHub Actions secret, which
contains an account-scoped Cloudflare API token with Pages edit permission. The
account ID and project name in `scripts/cloudflare_previews.py` must match the
Cloudflare project.
