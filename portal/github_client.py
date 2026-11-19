import base64
import re
from uuid import uuid4

import requests

VALUES_PATH = "apps/workload-api/values.yaml"
BASE_BRANCH = "main"

REPLICA_LINE = re.compile(
    r"^(replicaCount:[ \t]*)([0-9]+)(?=[ \t]*(?:#[^\r\n]*)?\r?$)",
    flags=re.MULTILINE,
)

REGION_LINE = re.compile(
    r"^(nodeSelector:[ \t]*\r?\n[ \t]+idp\.example\.com/region:[ \t]*)"
    r"([a-z0-9-]+)(?=[ \t]*(?:#[^\r\n]*)?\r?$)",
    flags=re.MULTILINE,
)


class GitHubError(Exception):
    pass


def github_request(method, url, token, **kwargs):
    try:
        response = requests.request(
            method,
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=15,
            **kwargs,
        )
    except requests.RequestException as error:
        raise GitHubError("Không kết nối được với GitHub API.") from error

    if not response.ok:
        try:
            message = response.json().get("message", "Yêu cầu thất bại.")
        except ValueError:
            message = "GitHub trả về phản hồi không đọc được."

        raise GitHubError(f"GitHub API {response.status_code}: {message}")

    return response.json()


def create_placement_pull_request(repository, token, replicas, region):
    repo_url = f"https://api.github.com/repos/{repository}"
    file_url = f"{repo_url}/contents/{VALUES_PATH}"

    base_ref = github_request(
        "GET",
        f"{repo_url}/git/ref/heads/{BASE_BRANCH}",
        token,
    )
    base_sha = base_ref["object"]["sha"]

    values_file = github_request(
        "GET",
        file_url,
        token,
        params={"ref": base_sha},
    )
    original = base64.b64decode(values_file["content"]).decode("utf-8")

    replica_matches = list(REPLICA_LINE.finditer(original))
    region_matches = list(REGION_LINE.finditer(original))

    if len(replica_matches) != 1 or len(region_matches) != 1:
        raise GitHubError(
            "values.yaml cần có đúng một dòng replicaCount dạng số và "
            "một nhãn idp.example.com/region trong nodeSelector."
        )

    current_replicas = int(replica_matches[0].group(2))
    current_region = region_matches[0].group(2)

    if current_replicas == replicas and current_region == region:
        return None

    updated = REPLICA_LINE.sub(
        lambda match: f"{match.group(1)}{replicas}",
        original,
        count=1,
    )
    updated = REGION_LINE.sub(
        lambda match: f"{match.group(1)}{region}",
        updated,
        count=1,
    )

    branch = f"portal/workload-api-placement-{uuid4().hex[:8]}"
    title = f"chore: place workload API in {region} with {replicas} replicas"

    github_request(
        "POST",
        f"{repo_url}/git/refs",
        token,
        json={
            "ref": f"refs/heads/{branch}",
            "sha": base_sha,
        },
    )

    try:
        github_request(
            "PUT",
            file_url,
            token,
            json={
                "message": title,
                "content": base64.b64encode(updated.encode("utf-8")).decode("ascii"),
                "sha": values_file["sha"],
                "branch": branch,
            },
        )

        return github_request(
            "POST",
            f"{repo_url}/pulls",
            token,
            json={
                "title": title,
                "head": branch,
                "base": BASE_BRANCH,
                "body": (
                    f"Requested from the Developer Portal: "
                    f"{replicas} replica(s) in {region}."
                ),
            },
        )
    except GitHubError as error:
        raise GitHubError(
            f"{error} Kiểm tra nhánh {branch} trên GitHub trước khi gửi lại."
        ) from error