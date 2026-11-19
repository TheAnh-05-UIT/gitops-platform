import os
import secrets

from flask import Flask, abort, render_template, request, session
from pulp import PulpSolverError

from optimizer.ilp import read_csv, solve_placement
from portal.github_client import GitHubError, create_placement_pull_request

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


@app.route("/", methods=["GET", "POST"])
def deploy():
    csrf_token = session.setdefault("csrf_token", secrets.token_hex(32))

    if request.method == "GET":
        return render_template("deploy.html", csrf_token=csrf_token)

    submitted_token = request.form.get("csrf_token", "")
    if not secrets.compare_digest(
        csrf_token.encode("utf-8"),
        submitted_token.encode("utf-8"),
    ):
        abort(400)

    replicas = request.form.get("replicas", type=int)
    max_rtt_ms = request.form.get("max_rtt_ms", type=int)

    if replicas not in (1, 2, 3) or max_rtt_ms is None or max_rtt_ms <= 0:
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error="Số replica phải là 1, 2 hoặc 3 và RTT tối đa phải lớn hơn 0 ms.",
        ), 400

    try:
        regions = read_csv("regions.csv", "region")
        latency = read_csv("latency.csv", "region")
        service = read_csv("services.csv", "service")["workload-api"]

        placement = solve_placement(
            regions,
            latency,
            cpu_mcpu=int(service["cpu_mcpu_per_replica"]) * replicas,
            memory_mib=int(service["memory_mib_per_replica"]) * replicas,
            max_rtt_ms=max_rtt_ms,
        )
    except (OSError, KeyError, ValueError, PulpSolverError):
        app.logger.exception("Placement optimization failed")
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error="Không chạy được bộ tối ưu. Kiểm tra dữ liệu CSV và log Flask.",
        ), 500

    if placement["status"] == "Infeasible":
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error="Không có region đáp ứng yêu cầu.",
            rejected=placement["rejected"],
        ), 422

    if placement["status"] != "Optimal":
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error=f"Bộ giải trả về trạng thái {placement['status']}.",
        ), 503

    repository = os.environ.get("GITOPS_CONFIG_REPO")
    token = os.environ.get("PORTAL_GITHUB_TOKEN")

    if not repository or not token:
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error="Thiếu GITOPS_CONFIG_REPO hoặc PORTAL_GITHUB_TOKEN.",
        ), 500

    try:
        pull_request = create_placement_pull_request(
            repository=repository,
            token=token,
            replicas=replicas,
            region=placement["region"],
        )
    except GitHubError as error:
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            placement=placement,
            error=str(error),
        ), 502

    return render_template(
        "deploy.html",
        csrf_token=csrf_token,
        placement=placement,
        pull_request=pull_request,
        notice=(
            "Nhánh main đã có cùng số replica và region."
            if pull_request is None
            else None
        ),
    )