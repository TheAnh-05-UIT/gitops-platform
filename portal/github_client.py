import base64
import re
from uuid import uuid4

import requests

VALUES_PATH = "apps/workload-api/values.yaml"
BASE_BRANCH = "main"
REPLICA_LINE = re.compile(
    r"^(replicaCount:[ \t]*)([0-9]+)(?=[ \t]*(?:#.*)?$)",
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


def create_replica_pull_request(repository, token, replicas):
    repo_url = f"https://api.github.com/repos/{repository}"
    file_url = f"{repo_url}/contents/{VALUES_PATH}"

    base_ref = github_request(
        "GET", f"{repo_url}/git/ref/heads/{BASE_BRANCH}", token
    )
    base_sha = base_ref["object"]["sha"]

    values_file = github_request(
        "GET", file_url, token, params={"ref": base_sha}
    )
    original = base64.b64decode(values_file["content"]).decode("utf-8")
    matches = list(REPLICA_LINE.finditer(original))

    if len(matches) != 1:
        raise GitHubError("Cần đúng một dòng replicaCount dạng số trong values.yaml.")

    if int(matches[0].group(2)) == replicas:
        return None

    updated = REPLICA_LINE.sub(
        lambda match: f"{match.group(1)}{replicas}", original, count=1
    )
    branch = f"portal/workload-api-replicas-{uuid4().hex[:8]}"

    github_request(
        "POST",
        f"{repo_url}/git/refs",
        token,
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )

    title = f"chore: scale workload API to {replicas} replicas"
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
                "body": f"Requested from the Developer Portal: {replicas} replicas.",
            },
        )
    except GitHubError as error:
        raise GitHubError(
            f"{error} Kiểm tra nhánh {branch} trên GitHub trước khi gửi lại."
        ) from error