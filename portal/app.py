"""Authenticated portal for reviewed workload changes."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat

from flask import Flask, abort, current_app, render_template, request, session
from itsdangerous import BadData, URLSafeTimedSerializer
from pulp import PulpSolverError

from optimizer.placement import solve_ilp
from optimizer.snapshot import build_snapshot_model, explain, timestamp
from portal.github_client import (
    COMMIT, GitHubError, prepare_change, submit_change,
)
from portal.identity import OIDC_KEYS, check_csrf, install_identity, require_role
from portal.status import desired_revisions, observed_status

PREVIEW_SECONDS = 300
FIXTURE = Path(__file__).resolve().parents[1] / "optimizer/data/placement_snapshot_v1.json"
SETTINGS = (
    "GITOPS_CONFIG_REPO", "PORTAL_GITHUB_READ_TOKEN", "PORTAL_GITHUB_TOKEN",
    "PORTAL_ACL_FILE", "PORTAL_ARGO_ORIGIN", "PORTAL_ARGO_READ_TOKEN", "PORTAL_SNAPSHOT_FILE",
    "PORTAL_SNAPSHOT_AS_OF", "PORTAL_GITHUB_BOT_ID", "PORTAL_AUDIT_FILE",
)


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("PORTAL_SESSION_SECRET"),
        SESSION_COOKIE_NAME="__Host-idp-session",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=16 * 1024,
        PORTAL_WRITES_ENABLED=os.environ.get("PORTAL_WRITES_ENABLED") == "1",
        PORTAL_ALLOW_SIMULATION_PROPOSALS=os.environ.get("PORTAL_ALLOW_SIMULATION_PROPOSALS") == "1",
        **{key: os.environ.get(key) for key in SETTINGS},
        **{f"PORTAL_OIDC_{key}": os.environ.get(f"PORTAL_OIDC_{key}") for key in OIDC_KEYS},
    )
    app.config.update(config or {})
    if not isinstance(app.secret_key, str) or len(app.secret_key.encode()) < 32:
        app.secret_key = None
    install_identity(app)
    app.add_url_rule("/catalog", view_func=catalog)
    app.add_url_rule("/history", view_func=history)
    app.add_url_rule("/", view_func=deploy, methods=["GET", "POST"])

    @app.after_request
    def protect_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        if response.status_code in (400, 401, 403) and request.endpoint in {
            "catalog", "deploy", "history", "logout", "oidc_callback",
        }:
            audit("request_denied", endpoint=request.endpoint, status=response.status_code)
        return response

    return app


def audit(event, request_id=None, *, durable=False, **details):
    subject = session.get("subject")
    actor = hmac.new(current_app.secret_key.encode(), f"audit-actor:{subject}".encode(),
                     hashlib.sha256).hexdigest()[:24] if subject and current_app.secret_key else None
    record = {"event": event, "actor": actor, "request_id": request_id, "service": "workload-api", **details}
    line = json.dumps(record, sort_keys=True)
    current_app.logger.warning("portal_audit %s", line)
    if durable:
        path = current_app.config.get("PORTAL_AUDIT_FILE")
        if not path or not Path(path).is_absolute() or Path(path).is_symlink():
            raise OSError("Protected audit path required")
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "ab") as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode)
                    or (os.name == "posix" and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077))):
                raise OSError("Protected audit file required")
            stream.write((line + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())


def catalog():
    role = require_role(current_app)
    return render_template("catalog.html", role=role, csrf_token=session["csrf_token"])


def _read_settings():
    config = current_app.config
    repository, token = config["GITOPS_CONFIG_REPO"], config["PORTAL_GITHUB_READ_TOKEN"]
    if not repository or not token:
        abort(503)
    return repository, token


def history():
    role = require_role(current_app)
    repository, token = _read_settings()
    config = current_app.config
    try:
        revisions = desired_revisions(repository, token)
    except GitHubError:
        return render_template("history.html", error="Không đọc được lịch sử Config."), 502
    observed = observed_status(config["PORTAL_ARGO_ORIGIN"], config["PORTAL_ARGO_READ_TOKEN"], repository)
    return render_template("history.html", revisions=revisions, observed=observed,
                           can_request=role == "deployer", csrf_token=session["csrf_token"])


def _page(status=200, **details):
    return render_template("deploy.html", csrf_token=session["csrf_token"], **details), status


def _snapshot_placement(replicas, max_rtt_ms):
    configured = current_app.config["PORTAL_SNAPSHOT_FILE"]
    snapshot = json.loads(Path(configured or FIXTURE).read_text(encoding="utf-8"))
    if not configured:
        as_of = timestamp("2026-11-26T12:01:00Z")
    elif snapshot.get("mode") == "simulation":
        as_of = timestamp(current_app.config["PORTAL_SNAPSHOT_AS_OF"])
    else:
        as_of = datetime.now(timezone.utc)
    tasks = [item for item in snapshot["workloads"] if item["name"] == "workload-api"]
    if len(tasks) != 1:
        raise ValueError("Snapshot must define workload-api once")
    tasks[0].update(replicas=replicas, max_rtt_ms=max_rtt_ms)
    compiled = build_snapshot_model(snapshot, as_of, max_age_seconds=300)
    status, proposed = solve_ilp(compiled.model, time_limit=3)
    return status, explain(compiled, proposed)


def _signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="idp-proposal-v1")


def _preview(repository, token, action):
    previous = None
    evidence = None
    replicas = None
    rtt = None
    region = None
    kind = "rollback" if action == "rollback" else "placement"
    try:
        if action == "rollback":
            previous = request.form.get("revision", "")
            if not COMMIT.fullmatch(previous) or previous not in desired_revisions(repository, token):
                return _page(400, error="Chọn một revision trong lịch sử đã duyệt của Config.")
        else:
            replicas = request.form.get("replicas", type=int)
            rtt = request.form.get("max_rtt_ms", type=int)
            if replicas not in (1, 2, 3) or rtt is None or not 1 <= rtt <= 10000:
                return _page(400, error="Chọn 1–3 replica và ngưỡng RTT từ 1 đến 10.000 ms.")
            status, evidence = _snapshot_placement(replicas, rtt)
            if status == "Infeasible":
                return _page(422, error="Không tìm được phương án khả thi.", evidence=evidence)
            if status != "Optimal":
                return _page(503, error="Bộ giải chưa chứng minh được phương án tối ưu.")
            region = evidence["workloads"]["workload-api"]["placement_region"]
        change = prepare_change(repository, token, replicas, region, previous_revision=previous)
    except GitHubError:
        audit("preview_unavailable", kind=kind)
        return _page(502, error="Không xác minh được hợp đồng values.yaml hoặc revision.")
    except (KeyError, TypeError, ValueError, OSError, PulpSolverError):
        audit("snapshot_unavailable")
        return _page(503, error="Không đọc được dữ liệu placement hiện tại.")
    if not change.diff:
        return _page(notice="Cấu hình đã khớp với yêu cầu.", evidence=evidence)
    proposal = {
        "actor": session["subject"], "repository": repository, "base": change.base,
        "fingerprint": change.fingerprint, "id": secrets.token_hex(16), "kind": kind,
        "replicas": change.replicas, "region": change.region, "previous": previous,
        "rtt": rtt,
        "source": evidence["source_mode"] if evidence else "git-history",
    }
    audit("previewed", proposal["id"], kind=kind, base=change.base)
    return _page(proposal=_signer().dumps(proposal), diff=change.diff, evidence=evidence)


def _submit(repository, read_token):
    config = current_app.config
    if config["PORTAL_WRITES_ENABLED"] is not True or not config["PORTAL_GITHUB_TOKEN"]:
        audit("submission_disabled")
        abort(403)
    try:
        proposal = _signer().loads(request.form.get("proposal", ""), max_age=PREVIEW_SECONDS)
    except BadData:
        audit("invalid_preview")
        abort(400)
    if proposal["actor"] != session["subject"] or proposal["repository"] != repository:
        audit("preview_scope_denied")
        abort(403)
    if proposal["source"] == "simulation" and config["PORTAL_ALLOW_SIMULATION_PROPOSALS"] is not True:
        audit("simulation_submission_denied", proposal["id"])
        abort(403)

    try:
        bot_id = int(config["PORTAL_GITHUB_BOT_ID"])
        observed = observed_status(config["PORTAL_ARGO_ORIGIN"], config["PORTAL_ARGO_READ_TOKEN"], repository)
        if not observed:
            return _page(503, error="Cần xác minh nguồn Argo CD trước khi gửi đề xuất.")
        if proposal["source"] != "git-history":
            status, evidence = _snapshot_placement(proposal["replicas"], proposal["rtt"])
            selected = evidence["workloads"].get("workload-api", {})
            if (status != "Optimal" or evidence["source_mode"] != proposal["source"]
                    or selected.get("placement_region") != proposal["region"]):
                return _page(409, error="Dữ liệu placement đã thay đổi. Hãy xem trước lại.")
        change = prepare_change(repository, read_token, proposal["replicas"], proposal["region"],
                                previous_revision=proposal["previous"])
        if (change.base, change.fingerprint) != (proposal["base"], proposal["fingerprint"]):
            audit("stale_preview", proposal["id"])
            return _page(409, error="Cấu hình đã thay đổi. Hãy xem trước lại.")
        audit("submit_started", proposal["id"], durable=True, kind=proposal["kind"], base=change.base)
        number = submit_change(change, config["PORTAL_GITHUB_TOKEN"], proposal["id"], proposal["kind"], bot_id)
        audit("submit_confirmed", proposal["id"], durable=True, pull=number)
    except GitHubError:
        audit("submit_unconfirmed", proposal["id"])
        # The same signed preview retries with the same branch and request marker.
        return _page(502, error="Chưa xác nhận được PR. Kiểm tra lại cùng đề xuất.",
                     proposal=request.form["proposal"])
    except (KeyError, TypeError, ValueError, OSError, PulpSolverError):
        audit("submission_inputs_unavailable", proposal["id"])
        return _page(503, error="Chưa xác minh được điều kiện để gửi đề xuất.")
    return _page(pull_request={"number": number, "html_url": f"https://github.com/{repository}/pull/{number}"})


def deploy():
    write = request.method == "POST"
    role = require_role(current_app, write=write)
    if not write:
        return _page(can_request=role == "deployer")
    check_csrf()
    repository, token = _read_settings()
    action = request.form.get("action")
    if action == "submit":
        return _submit(repository, token)
    if action in ("preview", "rollback"):
        return _preview(repository, token, action)
    abort(400)


app = create_app()
