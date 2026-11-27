"""Exercise real loopback TLS using a disposable synthetic token endpoint."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import threading
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, HTTPCookieProcessor, ProxyHandler, Request
import urllib.error
from werkzeug.serving import WSGIRequestHandler, make_server

scratch = Path(os.environ["VERIFY_TMP"])
for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    os.environ.pop(key, None)
os.environ["REQUESTS_CA_BUNDLE"] = str(scratch / "review-cert.pem")
from portal.app import create_app

def encode(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

transactions = {}
class Provider(BaseHTTPRequestHandler):
    def do_POST(self):
        form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        verifier = form["code_verifier"][0]
        from hashlib import sha256
        asserted = base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        assert self.path == "/token"
        assert self.headers["Authorization"] == "Basic " + base64.b64encode(b"verify-client:verify-secret").decode()
        code = form["code"][0]
        txn = transactions.pop(code)
        assert asserted == txn["code_challenge"][0]
        now = int(time.time())
        fields = {"iss": issuer, "aud": "verify-client", "iat": now, "exp": now + 120,
                  "sub": "owner", "nonce": txn["nonce"][0]}
        data = json.dumps({"id_token": encode({"alg": "RS256"}) + "." + encode(fields) + ".AA"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *args):
        pass

class QuietRequest(WSGIRequestHandler):
    def log(self, *args):
        pass


class ManualRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None

def running(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t

server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
server_tls.load_cert_chain(scratch/"review-cert.pem", scratch/"review-key.pem")
idp = ThreadingHTTPServer(("127.0.0.1",0), Provider)
idp.socket = server_tls.wrap_socket(idp.socket, server_side=True)
issuer = f"https://127.0.0.1:{idp.server_port}"
acl = scratch / "review-acl.json"
with acl.open("x", encoding="utf-8") as stream:
    stream.write('{"subjects":{"owner":{"workload-api":"viewer"}}}')
portal = make_server("127.0.0.1", 0, lambda env, start: app(env,start), ssl_context=server_tls, request_handler=QuietRequest)
url = f"https://127.0.0.1:{portal.server_port}"
app = create_app({"SECRET_KEY":"fixture-only-"*4, "PORTAL_ACL_FILE":str(acl),
                  "PORTAL_OIDC_ISSUER":issuer, "PORTAL_OIDC_AUTHORIZE_URL":issuer+"/authorize",
                  "PORTAL_OIDC_TOKEN_URL":issuer+"/token", "PORTAL_OIDC_REDIRECT_URI":url+"/auth/callback",
                  "PORTAL_OIDC_CLIENT_ID":"verify-client", "PORTAL_OIDC_CLIENT_SECRET":"verify-secret"})
threads = [running(idp),running(portal)]
client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=os.environ["REQUESTS_CA_BUNDLE"])),
                      HTTPCookieProcessor(http.cookiejar.CookieJar()), ManualRedirect())
def request(path, expected, data=None):
    try:
        result = client.open(Request(url+path, data=data), timeout=4)
    except urllib.error.HTTPError as error:
        result = error
    with result:
        assert result.code == expected, (path, result.code, expected)
        return result.headers, result.read()
try:
    request("/catalog",401)
    hdr,_ = request("/auth/login",302)
    assert "Secure" in hdr["Set-Cookie"] and "HttpOnly" in hdr["Set-Cookie"]
    transactions["fixture-code"] = parse_qs(urlsplit(hdr["Location"]).query)
    state = transactions["fixture-code"]["state"][0]
    request("/auth/callback?code=fixture-code&state="+state,302)
    _,page = request("/catalog",200)
    assert b"workload-api" in page
    request("/",403,data=b"action=submit")
    request("/auth/callback?code=fixture-code&state="+state,400)
    print("PASS loopback TLS portal + controlled OIDC token endpoint, PKCE, cookies, catalog, role, replay rejection")
finally:
    for svc,t in zip((idp,portal),threads):
        svc.shutdown()
        svc.server_close()
        t.join(3)
