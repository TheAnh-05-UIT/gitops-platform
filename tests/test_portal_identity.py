import base64
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from portal.app import create_app

ISSUER = "https://id.example.test"


def compact(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


class PortalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.acl = Path(self.tmp.name) / "acl.json"
        self.acl.write_text(json.dumps({"subjects": {"owner": {"workload-api": "deployer"},
                                                       "observer": {"workload-api": "viewer"}}}))
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "fixture-" * 8,
            "PORTAL_ACL_FILE": str(self.acl),
            "PORTAL_OIDC_ISSUER": ISSUER,
            "PORTAL_OIDC_AUTHORIZE_URL": ISSUER + "/authorize",
            "PORTAL_OIDC_TOKEN_URL": ISSUER + "/token",
            "PORTAL_OIDC_CLIENT_ID": "fixture-client",
            "PORTAL_OIDC_CLIENT_SECRET": "fixture-client-secret",
            "PORTAL_OIDC_REDIRECT_URI": "https://portal.example.test/auth/callback",
        })
        self.client = self.app.test_client()

    def start(self):
        redirect = self.client.get("/auth/login")
        self.assertEqual(redirect.status_code, 302)
        return parse_qs(urlsplit(redirect.location).query)

    def callback(self, params, **changes):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": "fixture-client", "sub": "owner", "nonce": params["nonce"][0],
                  "iat": now, "exp": now + 180, **changes}
        with patch("portal.identity.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "id_token": ".".join((compact({"alg": "RS256"}), compact(claims), "c2lnbmF0dXJl")),
                "access_token": "fixture-sensitive-token",
            }
            response = self.client.get("/auth/callback", query_string={"state": params["state"][0], "code": "fixture"})
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
        return response

    def test_anonymous_cannot_use_catalog_or_deployment(self):
        self.assertEqual(self.client.get("/catalog").status_code, 401)
        with patch("portal.app.submit_change") as write:
            self.assertEqual(self.client.post("/", data={"replicas": 2}).status_code, 401)
            write.assert_not_called()

    def test_oidc_binds_state_pkce_nonce_and_session(self):
        params = self.start()
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(self.callback(params).status_code, 302)
        self.assertIn(b"workload-api", self.client.get("/catalog").data)
        with self.client.session_transaction() as session:
            self.assertEqual(session["subject"], "owner")
            self.assertNotIn("access_token", session)

    def test_wrong_nonce_issuer_audience_or_expiration_are_rejected(self):
        changes = [{"nonce": "wrong"}, {"iss": ISSUER + "/other"}, {"aud": ["other", "fixture-client"]},
                   {"exp": int(time.time()) - 5}, {"azp": "other"}]
        for claim in changes:
            with self.subTest(claim=claim):
                params = self.start()
                self.assertEqual(self.callback(params, **claim).status_code, 401)

    def test_wrong_state_never_reaches_token_endpoint(self):
        self.start()
        with patch("portal.identity.requests.post") as post:
            response = self.client.get("/auth/callback?state=wrong&code=fixture")
            self.assertEqual(response.status_code, 400)
            post.assert_not_called()

    def test_viewer_denied_writes_and_revocation_applies_on_next_request(self):
        self.callback(self.start(), sub="observer")
        with self.client.session_transaction() as session:
            csrf = session["csrf_token"]
        with patch("portal.app.submit_change") as write:
            result = self.client.post("/", data={"csrf_token": csrf, "action": "submit"})
            self.assertEqual(result.status_code, 403)
            write.assert_not_called()
        self.acl.write_text('{"subjects": {}}')
        self.assertEqual(self.client.get("/catalog").status_code, 403)

    def test_cross_origin_token_endpoint_is_rejected(self):
        self.app.config["PORTAL_OIDC_TOKEN_URL"] = "https://other.example.test/token"
        self.assertEqual(self.client.get("/auth/login").status_code, 503)

    def test_logout_clears_portal_session_without_restarting_sso(self):
        self.callback(self.start())
        with self.client.session_transaction() as session:
            csrf = session["csrf_token"]
        response = self.client.post("/auth/logout", data={"csrf_token": csrf})
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            self.assertNotIn("subject", session)
            self.assertNotIn("oidc_login", session)
