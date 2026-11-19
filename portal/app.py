import os
import secrets

from flask import Flask, abort, render_template, request, session

from portal.github_client import GitHubError, create_replica_pull_request

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


@app.route("/", methods=["GET", "POST"])
def deploy():
    csrf_token = session.setdefault("csrf_token", secrets.token_hex(32))

    if request.method == "GET":
        return render_template("deploy.html", csrf_token=csrf_token)

    if not secrets.compare_digest(
        csrf_token, request.form.get("csrf_token", "")
    ):
        abort(400)

    replicas = request.form.get("replicas", type=int)
    if replicas not in (1, 2, 3):
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error="Số replica phải là 1, 2 hoặc 3.",
        ), 400

    repository = os.environ.get("GITOPS_CONFIG_REPO")
    token = os.environ.get("PORTAL_GITHUB_TOKEN")

    if not repository or not token:
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            error="Thiếu GITOPS_CONFIG_REPO hoặc PORTAL_GITHUB_TOKEN.",
        ), 500

    try:
        pull_request = create_replica_pull_request(repository, token, replicas)
    except GitHubError as error:
        return render_template(
            "deploy.html", csrf_token=csrf_token, error=str(error)
        ), 502

    if pull_request is None:
        return render_template(
            "deploy.html",
            csrf_token=csrf_token,
            notice="Nhánh main đã có số replica này.",
        )

    return render_template(
        "deploy.html", csrf_token=csrf_token, pull_request=pull_request
    )