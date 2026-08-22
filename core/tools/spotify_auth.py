"""One-time local helper for obtaining an Olympus Spotify refresh token."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import secrets
import threading
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser

import httpx


REDIRECT_URI = "http://127.0.0.1:8787/callback"
SCOPES = "user-read-currently-playing user-read-playback-state"


class CallbackHandler(BaseHTTPRequestHandler):
    server: "CallbackServer"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        query = parse_qs(urlparse(self.path).query)
        self.server.code = query.get("code", [None])[0]
        self.server.returned_state = query.get("state", [None])[0]
        self.send_response(200 if self.server.code else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        message = (
            "Spotify connected to Olympus. You can close this window."
            if self.server.code
            else "Spotify did not return an authorization code."
        )
        self.wfile.write(message.encode())
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, _format: str, *_args: object) -> None:
        return


class CallbackServer(HTTPServer):
    code: str | None = None
    returned_state: str | None = None


def main() -> None:
    client_id = os.getenv("OLYMPUS_SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("OLYMPUS_SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "Set OLYMPUS_SPOTIFY_CLIENT_ID and OLYMPUS_SPOTIFY_CLIENT_SECRET first."
        )

    state = secrets.token_urlsafe(24)
    authorization_url = "https://accounts.spotify.com/authorize?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "scope": SCOPES,
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "show_dialog": "true",
        }
    )
    server = CallbackServer(("127.0.0.1", 8787), CallbackHandler)
    print("Opening Spotify authorization in your browser…")
    print(authorization_url)
    webbrowser.open(authorization_url)

    server.serve_forever()
    server.server_close()
    if server.code is None or server.returned_state != state:
        raise SystemExit("Authorization failed or returned an invalid state.")

    response = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": server.code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
        timeout=10,
    )
    response.raise_for_status()
    refresh_token = response.json().get("refresh_token")
    if not refresh_token:
        raise SystemExit("Spotify did not return a refresh token.")

    print("\nAdd this value to core/.env:")
    print(f"OLYMPUS_SPOTIFY_REFRESH_TOKEN={refresh_token}")


if __name__ == "__main__":
    main()
