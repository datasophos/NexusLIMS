"""Tests for selecting obsolete Cloudflare preview deployments."""

from scripts.cloudflare_previews import make_plan


def test_cleanup_only_closed_branches_without_an_open_pr():
    """Keep production, unknown, and branches shared with an open PR."""
    prs = [
        {"state": "closed", "head": {"ref": "finished"}},
        {"state": "closed", "head": {"ref": "shared"}},
        {"state": "open", "head": {"ref": "shared"}},
    ]

    def deployment(identifier, branch, environment="preview"):
        return {
            "id": identifier,
            "environment": environment,
            "deployment_trigger": {"metadata": {"branch": branch}},
        }

    deployments = [
        deployment("delete", "finished"),
        deployment("keep", "shared"),
        deployment("unknown", "other"),
        deployment("production", "finished", "production"),
    ]
    assert make_plan(prs, deployments) == ["delete"]
