"""Authentication and service authorization for the Flask portal."""
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import time
from urllib.parse import quote_plus, urlencode, urlsplit

import requests
from flask import Flask, abort, redirect, render_template, request, session, url_for

OIDC_KEYS = ("ISSUER", "AUTHORIZE_URL", "TOKEN_URL", "CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI")
SESSION_SECONDS = 900
LOGIN_SECONDS = 300


def _https_url(value):
    if not value.isascii() or re.search(r"[\s\\]", value):
        raise ValueError("Malformed HTTPS URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError("Expected a configured HTTPS URL without query or credentials")
    return parsed.hostname, parsed.port or 443


def _oidc_settings(app):
    settings = {name: app.config.get(f"PORTAL_OIDC_{name}") for name in OIDC_KEYS}
    if not all(isinstance(value, str) and value for value in settings.values()):
        abort(503)
    try:
        origin = _https_url(settings["ISSUER"])
        endpoints = (settings["AUTHORIZE_URL"], settings["TOKEN_URL"])
        if any(_https_url(url) != origin for url in endpoints):
            raise ValueError("OIDC endpoints must share the issuer origin")
        _https_url(settings["REDIRECT_URI"])
        if urlsplit(settings["REDIRECT_URI"]).path != url_for("oidc_callback"):
            raise ValueError("OIDC callback does not match the portal route")
    except ValueError:
        abort(503)
    return settings


def _base64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_segment(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Malformed token")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _matches(expected, actual):
    return isinstance(actual, str) and secrets.compare_digest(expected.encode(), actual.encode())


def _verify_claims(token, settings, transaction, now):
    # OIDC Core 3.1.3.7 permits TLS server validation for an ID token retrieved
    # directly from the configured token endpoint in the Authorization Code Flow.
    if not isinstance(token, str) or len(token) > 16384:
        raise ValueError("Invalid ID token")
    header, payload, signature = token.split(".")
    algorithm = json.loads(_decode_segment(header))
    claims = json.loads(_decode_segment(payload))
    _decode_segment(signature)
    if (not isinstance(algorithm, dict) or algorithm.get("alg") != "RS256"
            or "crit" in algorithm or not isinstance(claims, dict)):
        raise ValueError("Unsupported ID token")
    client = settings["CLIENT_ID"]
    if (claims.get("iss") != settings["ISSUER"] or claims.get("aud") not in (client, [client])
            or claims.get("azp", client) != client or not _matches(transaction["nonce"], claims.get("nonce"))):
        raise ValueError("ID token binding failed")
    issued, expires, subject = claims.get("iat"), claims.get("exp"), claims.get("sub")
    if (type(issued) is not int or type(expires) is not int or issued > now + 30
            or issued < transaction["started"] - 30 or expires <= max(now, issued)):
        raise ValueError("ID token expired or issuance time invalid")
    if not isinstance(subject, str) or not subject or len(subject) > 255 or not subject.isascii() or not subject.isprintable():
        raise ValueError("ID token subject invalid")
    return subject, min(expires, now + SESSION_SECONDS)


def require_role(app, *, write=False):
    if not app.secret_key:
        abort(503)
    subject = session.get("subject")
    if (not subject or session.get("expires", 0) <= int(time.time())
            or session.get("issuer") != app.config.get("PORTAL_OIDC_ISSUER")):
        session.clear()
        abort(401)
    path = app.config.get("PORTAL_ACL_FILE")
    if not path:
        abort(503)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        role = data["subjects"].get(subject, {}).get("workload-api")
    except (AttributeError, KeyError, OSError, ValueError, TypeError):
        abort(503)
    if role not in ("viewer", "deployer") or (write and role != "deployer"):
        abort(403)
    return role


def check_csrf():
    token = session.get("csrf_token")
    if not token or not _matches(token, request.form.get("csrf_token")):
        abort(400)


def install_identity(app: Flask):
    @app.get("/auth/login")
    def oidc_login():
        if not app.secret_key:
            abort(503)
        settings = _oidc_settings(app)
        transaction = {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32),
                       "verifier": secrets.token_urlsafe(48), "started": int(time.time())}
        session.clear()
        session["oidc_login"] = transaction
        authorization = urlencode({
            "response_type": "code",
            "scope": "openid",
            "client_id": settings["CLIENT_ID"],
            "redirect_uri": settings["REDIRECT_URI"],
            "state": transaction["state"],
            "nonce": transaction["nonce"],
            "code_challenge": _base64url(hashlib.sha256(transaction["verifier"].encode()).digest()),
            "code_challenge_method": "S256",
        })
        return redirect(f'{settings["AUTHORIZE_URL"]}?{authorization}')

    @app.get("/auth/callback")
    def oidc_callback():
        if not app.secret_key:
            abort(503)
        settings = _oidc_settings(app)
        transaction = session.pop("oidc_login", None)
        now = int(time.time())
        if (not transaction or now - transaction["started"] > LOGIN_SECONDS
                or not _matches(transaction["state"], request.args.get("state"))):
            abort(400)
        codes = request.args.getlist("code")
        if len(codes) != 1 or not 0 < len(codes[0]) <= 8192 or "error" in request.args or "id_token" in request.args:
            abort(400)
        try:
            response = requests.post(
                settings["TOKEN_URL"],
                auth=(quote_plus(settings["CLIENT_ID"]), quote_plus(settings["CLIENT_SECRET"])),
                data={"grant_type": "authorization_code", "code": codes[0],
                      "redirect_uri": settings["REDIRECT_URI"], "code_verifier": transaction["verifier"]},
                timeout=(3, 8), allow_redirects=False,
            )
        except requests.RequestException:
            abort(503)
        if response.status_code != 200:
            abort(401)
        try:
            subject, expires = _verify_claims(response.json()["id_token"], settings, transaction, int(time.time()))
        except (KeyError, TypeError, ValueError):
            abort(401)
        session.clear()
        session.update(subject=subject, issuer=settings["ISSUER"], expires=expires, csrf_token=secrets.token_urlsafe(32))
        return redirect(url_for("catalog"))

    @app.post("/auth/logout")
    def logout():
        check_csrf()
        session.clear()
        return render_template("logout.html")
