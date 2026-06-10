"""Spotify-OAuth (Authorization Code mit PKCE).

PKCE braucht kein Client-Secret — nur die Client-ID einer selbst angelegten
App auf https://developer.spotify.com/dashboard. Als Redirect-URI muss dort
http://127.0.0.1:8888/callback eingetragen sein.
"""

import base64
import hashlib
import http.server
import json
import logging
import secrets
import threading
import time
import urllib.parse
import webbrowser

import requests

from ..paths import TOKEN_PATH

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-library-read",
    "user-library-modify",
])


def load_token() -> dict | None:
    if TOKEN_PATH.exists():
        try:
            return json.loads(TOKEN_PATH.read_text())
        except Exception:
            return None
    return None


def save_token(token: dict):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(token, indent=2))
    TOKEN_PATH.chmod(0o600)


def clear_token():
    TOKEN_PATH.unlink(missing_ok=True)


def refresh_token(client_id: str, client_secret: str = "") -> dict | None:
    """Access-Token per Refresh-Token erneuern."""
    token = load_token()
    if not token or "refresh_token" not in token:
        return None
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        r = requests.post(TOKEN_URL, data=data, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.error("Spotify-Token-Refresh fehlgeschlagen: %s", e)
        return None
    new = r.json()
    new.setdefault("refresh_token", token["refresh_token"])
    new["expires_at"] = time.time() + new.get("expires_in", 3600)
    save_token(new)
    return new


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code = None
    error = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            _CallbackHandler.code = params["code"][0]
            body = "<h2>✅ Spotify verbunden!</h2><p>Du kannst dieses Fenster schließen.</p>"
        else:
            _CallbackHandler.error = params.get("error", ["unbekannt"])[0]
            body = f"<h2>❌ Fehler: {_CallbackHandler.error}</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body style='font-family:sans-serif'>{body}</body></html>".encode())

    def log_message(self, *args):
        pass


def login(client_id: str, client_secret: str = "",
          redirect_uri: str = "http://127.0.0.1:8888/callback",
          open_browser: bool = True, timeout: int = 180) -> dict:
    """Kompletten PKCE-Login durchführen. Gibt das Token-Dict zurück.

    Wirft RuntimeError bei Fehlern/Timeout.
    """
    if not client_id:
        raise RuntimeError("Keine Spotify Client-ID konfiguriert.")

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    port = urllib.parse.urlparse(redirect_uri).port or 8888
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    _CallbackHandler.code = None
    _CallbackHandler.error = None
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        if open_browser:
            webbrowser.open(url)
        print(f"Falls sich kein Browser öffnet, diese URL aufrufen:\n{url}\n")

        deadline = time.time() + timeout
        while time.time() < deadline:
            if _CallbackHandler.code or _CallbackHandler.error:
                break
            time.sleep(0.2)
    finally:
        server.shutdown()
        server.server_close()

    if _CallbackHandler.error:
        raise RuntimeError(f"Spotify-Login abgelehnt: {_CallbackHandler.error}")
    if not _CallbackHandler.code:
        raise RuntimeError("Spotify-Login: Zeitüberschreitung — kein Callback erhalten.")

    data = {
        "grant_type": "authorization_code",
        "code": _CallbackHandler.code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    r = requests.post(TOKEN_URL, data=data, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Token-Tausch fehlgeschlagen: {r.status_code} {r.text[:200]}")
    token = r.json()
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    save_token(token)
    log.info("Spotify-Login erfolgreich.")
    return token
