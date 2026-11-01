"""Clean up Pages preview deployments for closed pull requests."""

import http.client
import json
import os
import sys
from urllib.parse import urlsplit

ACCOUNT = "c924686e1dae7243fe6e51e23e6a9735"
PROJECT = "nexuslims-docs"
CF = "https://api.cloudflare.com/client/v4"
GH = "https://api.github.com/repos/datasophos/NexusLIMS"
PREFIX = f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}"


def branch_of(deployment):
    """Read the source branch from a deployment."""
    return deployment.get("deployment_trigger", {}).get("metadata", {}).get("branch")


def make_plan(prs, deployments):
    """Select closed-PR previews, excluding branches used by an open PR."""
    opened = {pr["head"]["ref"] for pr in prs if pr["state"] == "open"}
    closed = {pr["head"]["ref"] for pr in prs if pr["state"] == "closed"} - opened
    return [
        d["id"]
        for d in deployments
        if d.get("environment") == "preview" and branch_of(d) in closed
    ]


def request(url, token, method="GET", body=None):
    """Send a request to a trusted HTTPS API endpoint."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.github.com",
        "api.cloudflare.com",
    }:
        msg = "Unexpected API endpoint"
        raise ValueError(msg)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "nexuslims-preview-reconciler",
    }
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=30)
    try:
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        if response.status >= http.client.BAD_REQUEST:
            msg = f"{method} {url}: HTTP {response.status}: {raw.decode()}"
            raise RuntimeError(msg)
        result = json.loads(raw)
    finally:
        connection.close()
    if isinstance(result, dict) and result.get("success") is False:
        msg = f"{method} {url}: {result.get('errors')}"
        raise RuntimeError(msg)
    return result


def pages(url, token, *, cloudflare=False):
    """Fetch every page of results or fail closed on excessive pagination."""
    results = []
    per_page = 25 if cloudflare else 100
    for page in range(1, 1001):
        sep = "&" if "?" in url else "?"
        data = request(f"{url}{sep}per_page={per_page}&page={page}", token)
        items = data["result"] if cloudflare else data
        results.extend(items)
        if cloudflare and data.get("result_info", {}).get("total_pages") is not None:
            if page >= data["result_info"]["total_pages"]:
                return results
        elif len(items) < per_page:
            return results
    msg = f"Pagination limit reached: {url}"
    raise RuntimeError(msg)


def main():
    """Delete preview deployments belonging exclusively to closed PRs."""
    cf_token = os.environ["CLOUDFLARE_PREVIEW_TOKEN"]
    gh_token = os.environ["GH_TOKEN"]
    prs = pages(f"{GH}/pulls?state=all", gh_token)
    prs = [
        pr
        for pr in prs
        if (pr["head"].get("repo") or {}).get("full_name") == "datasophos/NexusLIMS"
    ]
    deployments = pages(
        f"{CF}{PREFIX}/deployments?env=preview", cf_token, cloudflare=True
    )
    plan = make_plan(prs, deployments)
    for deployment_id in plan:
        request(
            f"{CF}{PREFIX}/deployments/{deployment_id}?force=true", cf_token, "DELETE"
        )
    sys.stdout.write(f"Deleted {len(plan)} preview deployments.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, OSError) as exc:
        sys.stderr.write(f"Preview reconciliation failed: {exc}\n")
        sys.exit(1)
