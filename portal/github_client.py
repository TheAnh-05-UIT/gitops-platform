import base64
from dataclasses import dataclass
from difflib import unified_diff
import hashlib
import re

import requests

from optimizer.kubernetes_snapshot import request_units

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
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


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
            allow_redirects=False,
            **kwargs,
        )
    except requests.RequestException as error:
        raise GitHubError("Không kết nối được với GitHub API.") from error

    if not 200 <= response.status_code < 300:
        raise GitHubError(f"GitHub API trả HTTP {response.status_code}.", response.status_code)
    try:
        return response.json()
    except ValueError as error:
        raise GitHubError("GitHub trả phản hồi không hợp lệ.") from error


REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
COMMIT = re.compile(r"[0-9a-f]{40}")
PLACEMENT_REGION = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]")


@dataclass(frozen=True)
class PlacementChange:
    repository: str
    base: str
    blob: str
    original: str
    updated: str
    replicas: int
    region: str
    diff: str

    @property
    def fingerprint(self):
        return hashlib.sha256(self.diff.encode("utf-8")).hexdigest()


def repository_url(repository):
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository) or repository.split("/")[1] in (".", ".."):
        raise GitHubError("Kho Config không hợp lệ.")
    return f"https://api.github.com/repos/{repository}"


def _fetch_values(repo_url, token, revision):
    try:
        values = github_request("GET", f"{repo_url}/contents/{VALUES_PATH}", token, params={"ref": revision})
        content = values["content"]
        if len(content) > 200_000 or not COMMIT.fullmatch(values["sha"]):
            raise ValueError("Invalid values content or blob")
        return values["sha"], base64.b64decode("".join(content.split()), validate=True).decode("utf-8")
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise GitHubError("GitHub trả nội dung cấu hình không hợp lệ.") from error


def _mapping_lines(values, name):
    block = re.search(rf"(?m)^{name}:[ \t]*\r?\n((?:[ \t][^\n]*\n?|\r?\n|#[^\n]*\n?)*)", values)
    if block is None:
        return []
    return [line for line in block[1].splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _placement_fields(values):
    # Fixed replica changes require the reviewed chart's canonical HPA block.
    # Fail closed for alternate top-level YAML keys, duplicate blocks and merges.
    top_level = [line for line in values.splitlines() if line and not line.startswith((" ", "#"))]
    if (any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*:.*", line) for line in top_level)
            or re.search(r"(?m)^\s*<<\s*:", values)):
        raise GitHubError("Định dạng values.yaml nằm ngoài hợp đồng của portal.")
    keys = [line.split(":", 1)[0] for line in top_level]
    settings = {}
    for line in _mapping_lines(values, "autoscaling"):
        field = re.fullmatch(r"  (enabled|minReplicas|maxReplicas|targetCPUUtilizationPercentage):[ \t]*(false|[0-9]+)[ \t]*(?:#.*)?", line)
        if field is None or field[1] in settings:
            raise GitHubError("Portal yêu cầu hợp đồng replica cố định với HPA tắt.")
        settings[field[1]] = field[2]
    if len(set(keys)) != len(keys) or settings.get("enabled") != "false":
        raise GitHubError("Portal yêu cầu hợp đồng replica cố định với HPA tắt.")
    replicas = list(REPLICA_LINE.finditer(values))
    region = list(REGION_LINE.finditer(values))
    selectors = _mapping_lines(values, "nodeSelector")
    if len(replicas) != 1 or len(region) != 1 or len(selectors) != 1:
        raise GitHubError("Thiếu trường replica hoặc nhãn vùng theo hợp đồng chart.")
    return int(replicas[0].group(2)), region[0].group(2)


@dataclass(frozen=True)
class PlacementBase:
    repository: str
    revision: str
    blob: str
    values: str
    replicas: int
    region: str
    requests: tuple[int, int]


def _placement_requests(values):
    sections = {}
    current = None
    for line in _mapping_lines(values, "resources"):
        header = re.fullmatch(r"  (requests|limits):[ \t]*(?:#.*)?", line)
        if header and header[1] not in sections:
            current = header[1]
            sections[current] = {}
            continue
        field = re.fullmatch(r"""    (cpu|memory):[ \t]*(?P<quote>['"]?)(?P<value>[0-9A-Za-z.+-]+)(?P=quote)[ \t]*(?:#.*)?""", line)
        if not field or current is None or field[1] in sections[current]:
            raise GitHubError("Requests/limits không khớp hợp đồng tài nguyên của portal.")
        value = field["value"]
        if not field["quote"] and re.fullmatch(r"0[0-9]+", value):
            raise GitHubError("Định dạng số của CPU hoặc memory request không rõ ràng.")
        sections[current][field[1]] = value
    if set(sections.get("requests", {})) != {"cpu", "memory"}:
        raise GitHubError("Cần CPU và memory requests rõ ràng trong values.yaml.")
    try:
        units = request_units(sections["requests"])
        if min(units) < 1:
            raise ValueError("empty request")
    except ValueError as error:
        raise GitHubError("CPU hoặc memory request không hợp lệ.") from error
    return units


def read_placement_base(repository, token):
    url = repository_url(repository)
    try:
        base = github_request("GET", f"{url}/git/ref/heads/{BASE_BRANCH}", token)["object"]["sha"]
        if not COMMIT.fullmatch(base):
            raise ValueError("Invalid base commit")
    except (ValueError, KeyError, TypeError) as error:
        raise GitHubError("GitHub trả revision không hợp lệ.") from error
    blob, values = _fetch_values(url, token, base)
    replicas, region = _placement_fields(values)
    return PlacementBase(repository, base, blob, values, replicas, region, _placement_requests(values))


def prepare_change(repository, token, replicas, region, *, previous_revision=None, source=None):
    source = source if source is not None else read_placement_base(repository, token)
    if source.repository != repository:
        raise GitHubError("Revision không khớp kho Config.")
    original = source.values
    if previous_revision is not None:
        if not COMMIT.fullmatch(previous_revision):
            raise GitHubError("Revision của lần triển khai trước không hợp lệ.")
        _, older_values = _fetch_values(repository_url(repository), token, previous_revision)
        replicas, region = _placement_fields(older_values)
    if type(replicas) is not int or replicas not in (1, 2, 3) or not isinstance(region, str) or not PLACEMENT_REGION.fullmatch(region):
        raise GitHubError("Số replica hoặc nhãn vùng nằm ngoài hợp đồng của portal.")
    updated = REPLICA_LINE.sub(lambda match: f"{match.group(1)}{replicas}", original, count=1)
    updated = REGION_LINE.sub(lambda match: f"{match.group(1)}{region}", updated, count=1)
    diff = "".join(unified_diff(original.splitlines(keepends=True), updated.splitlines(keepends=True),
                                fromfile=f"a/{VALUES_PATH}", tofile=f"b/{VALUES_PATH}"))
    return PlacementChange(repository, source.revision, source.blob, original, updated, replicas, region, diff)


def _verified_head(repo_url, token, head, change, bot_id):
    if not isinstance(head, str) or not COMMIT.fullmatch(head):
        raise GitHubError("Nhánh yêu cầu không có revision hợp lệ.")
    commit = github_request("GET", f"{repo_url}/commits/{head}", token)
    if (commit.get("sha") != head or (commit.get("author") or {}).get("id") != bot_id
            or [parent.get("sha") for parent in commit.get("parents", [])] != [change.base]
            or [(file.get("filename"), file.get("status")) for file in commit.get("files", [])] != [(VALUES_PATH, "modified")]
            or _fetch_values(repo_url, token, head)[1] != change.updated):
        raise GitHubError("Nhánh yêu cầu không khớp commit và phạm vi đã duyệt.")


def _pull_identity(pull, branch, marker, repository, bot_id):
    head, base = pull.get("head", {}), pull.get("base", {})
    if (head.get("ref") != branch or base.get("ref") != BASE_BRANCH
            or any((ref.get("repo") or {}).get("full_name", "").lower() != repository.lower() for ref in (head, base))
            or (pull.get("user") or {}).get("id") != bot_id
            or marker not in (pull.get("body") or "").splitlines()
            or type(pull.get("number")) is not int or pull["number"] <= 0):
        raise GitHubError("Yêu cầu GitOps nằm ngoài hợp đồng của portal.")
    return pull["number"], head.get("sha")


def find_request(repo_url, token, branch, marker, change, bot_id):
    owner = repo_url.split("/")[-2]
    requests = github_request("GET", f"{repo_url}/pulls", token,
                              params={"state": "all", "base": BASE_BRANCH, "head": f"{owner}:{branch}", "per_page": 10})
    if not isinstance(requests, list) or len(requests) > 1:
        raise GitHubError("Không thể đối chiếu yêu cầu GitOps.")
    if requests:
        number, head = _pull_identity(requests[0], branch, marker, change.repository, bot_id)
        _verified_head(repo_url, token, head, change, bot_id)
        return number
    return None


def submit_change(change, token, request_id, kind, bot_id):
    if not re.fullmatch(r"[0-9a-f]{32}", request_id) or kind not in ("placement", "rollback") or not change.diff:
        raise GitHubError("Yêu cầu GitOps không hợp lệ.")
    repo_url = repository_url(change.repository)
    branch = f"portal/workload-api-{request_id}"
    marker = f"<!-- idp-request:{request_id} -->"
    if type(bot_id) is not int or bot_id <= 0:
        raise GitHubError("Thiếu định danh bot ghi Config được duyệt.")
    existing = find_request(repo_url, token, branch, marker, change, bot_id)
    if existing is not None:
        return existing

    try:
        github_request("POST", f"{repo_url}/git/refs", token,
                       json={"ref": f"refs/heads/{branch}", "sha": change.base})
    except GitHubError as error:
        if error.status != 422:
            raise
        # Retry after interruption or concurrent submit. Check the branch before reuse.
        ref = github_request("GET", f"{repo_url}/git/ref/heads/{branch}", token)
        current = ref.get("object", {}).get("sha")
    else:
        current = change.base

    title = f"chore: {kind} workload-api to {change.region} with {change.replicas} replicas"
    if current == change.base:
        try:
            github_request("PUT", f"{repo_url}/contents/{VALUES_PATH}", token, json={
                "message": title, "branch": branch, "sha": change.blob,
                "content": base64.b64encode(change.updated.encode("utf-8")).decode("ascii"),
            })
        except GitHubError as error:
            if error.status not in (409, 422):
                raise

    head = github_request("GET", f"{repo_url}/git/ref/heads/{branch}", token).get("object", {}).get("sha")
    _verified_head(repo_url, token, head, change, bot_id)

    try:
        pull = github_request("POST", f"{repo_url}/pulls", token, json={
            "title": title, "head": branch, "base": BASE_BRANCH,
            "body": (f"{marker}\nPortal operation: {kind} ({request_id})\n"
                     f"Reviewed base: `{change.base}`\n"
                     "Independent Git review and policy checks are required."),
        })
    except GitHubError as error:
        if error.status != 422:
            raise
        existing = find_request(repo_url, token, branch, marker, change, bot_id)
        if existing is None:
            raise
        return existing
    number, created_head = _pull_identity(pull, branch, marker, change.repository, bot_id)
    if created_head != head:
        raise GitHubError("Nhánh đã thay đổi trong lúc ghi nhận PR. Cần kiểm tra lại.")
    return number
