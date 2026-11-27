"""Read desired history and observed Argo status without mutation permissions."""
from datetime import datetime

import requests

from portal.github_client import BASE_BRANCH, COMMIT, VALUES_PATH, GitHubError, github_request, repository_url
from portal.identity import _https_url


def desired_revisions(repository, token, *, base=BASE_BRANCH):
    url = repository_url(repository)
    commits = github_request("GET", f"{url}/commits", token,
                             params={"sha": base, "path": VALUES_PATH, "per_page": 20})
    if not isinstance(commits, list):
        raise GitHubError("Không đọc được lịch sử Config.")
    return [entry["sha"] for entry in commits[:20]
            if isinstance(entry, dict) and isinstance(entry.get("sha"), str) and COMMIT.fullmatch(entry["sha"])]


def _expected_source(source, repository):
    return (set(source) == {"repoURL", "path", "targetRevision"}
            and source["repoURL"].removesuffix(".git").lower() == f"https://github.com/{repository}".lower()
            and source["path"] == "apps/workload-api" and source["targetRevision"] == BASE_BRANCH)


def _last_sync(history, repository):
    matches = []
    for item in history:
        try:
            revision, deployed_at = item["revision"], item["deployedAt"]
            when = datetime.fromisoformat(deployed_at)
            if (when.tzinfo is not None and COMMIT.fullmatch(revision) and not item.get("sources")
                    and _expected_source(item["source"], repository)):
                matches.append((when, revision, deployed_at))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return max(matches)[1:] if matches else (None, None)


def observed_status(origin, token, repository):
    """Use an App-scoped read token. Report status only for the expected source."""
    if not origin or not token:
        return None
    try:
        _https_url(origin)
        response = requests.get(
            origin.rstrip("/") + "/api/v1/applications/workload-api",
            headers={"Authorization": f"Bearer {token}"}, timeout=(3, 5), allow_redirects=False,
        )
        if response.status_code != 200:
            return None
        app = response.json()
        spec = app["spec"]
        if (app["metadata"]["name"] != "workload-api" or spec["project"] != "workload-lab"
                or spec.get("sources") or not _expected_source(spec["source"], repository)
                or spec["destination"] != {"namespace": "workloads", "server": "https://kubernetes.default.svc"}):
            return None
        status = app["status"]
        revision = status["sync"]["revision"]
        if not isinstance(revision, str) or not COMMIT.fullmatch(revision):
            return None
        sync = status["sync"]["status"]
        health = status["health"]["status"]
        last_revision, last_at = _last_sync(status.get("history", []), repository)
        return {
            "compared_revision": revision, "reconciled_at": status.get("reconciledAt"),
            "last_synced_revision": last_revision, "last_synced_at": last_at,
            "sync": sync if sync in ("Synced", "OutOfSync") else "Unknown",
            "health": health if health in ("Healthy", "Progressing", "Degraded", "Suspended", "Missing") else "Unknown",
        }
    except (AttributeError, KeyError, TypeError, ValueError, requests.RequestException):
        return None
