"""Microsoft account login and refresh-token storage for the launcher."""
from __future__ import annotations

import http.server
import threading
import time
import webbrowser
from typing import Any

from minecraft_launcher_lib import microsoft_account

SERVICE_NAME = "ECM Launcher"
REDIRECT_HOST = "localhost"


class AccountError(RuntimeError):
    """A safe account-related message for the UI."""


def _keyring():
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
    except Exception as exc:
        raise AccountError("Secure credential storage is unavailable. Install and unlock a desktop keyring, "
                           "then restart the launcher.") from exc
    backend = keyring.get_keyring()
    if isinstance(backend, FailKeyring) or getattr(backend, "priority", 0) <= 0:
        raise AccountError("No secure desktop keyring is available. Unlock GNOME Keyring, KWallet, or another "
                           "Secret Service compatible keyring before saving an online account.")
    return keyring


def _normalize_profile(profile: dict[str, Any]) -> dict[str, str]:
    username = str(profile.get("name", "")).strip()
    raw_id = str(profile.get("id", "")).replace("-", "").strip()
    access_token = str(profile.get("access_token", "")).strip()
    refresh_token = str(profile.get("refresh_token", "")).strip()
    if not username or not raw_id or not access_token or not refresh_token:
        raise AccountError("Microsoft returned an incomplete Minecraft profile. Confirm that this account owns "
                           "Minecraft Java Edition, then try again.")
    try:
        import uuid
        player_uuid = str(uuid.UUID(raw_id))
    except ValueError as exc:
        raise AccountError("Microsoft returned an invalid Minecraft profile ID.") from exc
    return {"id": raw_id.lower(), "name": username, "uuid": player_uuid,
            "access_token": access_token, "refresh_token": refresh_token}


def login(client_id: str, timeout: int = 300) -> dict[str, str]:
    """Open Microsoft sign-in in the system browser and complete OAuth PKCE locally."""
    client_id = (client_id or "").strip()
    if not client_id:
        raise AccountError("Enter your Microsoft public-client application ID first. A client secret is not used.")
    keyring = _keyring()
    result: dict[str, str] = {}
    received = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            callback_url = f"http://{REDIRECT_HOST}:{self.server.server_port}{self.path}"
            try:
                code = microsoft_account.parse_auth_code_url(callback_url, expected_state)
                result["code"] = code
                body = ("<!doctype html><meta charset='utf-8'><title>ECM Launcher</title>"
                        "<p>Microsoft sign-in returned to ECM Launcher. You can close this tab.</p>").encode()
                self.send_response(200)
            except Exception:
                body = ("<!doctype html><meta charset='utf-8'><title>ECM Launcher</title>"
                        "<p>Sign-in could not be verified. Return to ECM Launcher and try again.</p>").encode()
                self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            received.set()

        def log_message(self, _format, *_args):
            return

    try:
        callback_server = http.server.HTTPServer((REDIRECT_HOST, 0), CallbackHandler)
    except OSError as exc:
        raise AccountError(f"Could not start the local sign-in callback: {exc}") from exc

    redirect_uri = f"http://{REDIRECT_HOST}:{callback_server.server_port}"
    login_url, expected_state, verifier = microsoft_account.get_secure_login_data(client_id, redirect_uri)
    # Capture the expected OAuth state in the callback handler's closure.
    callback_server.timeout = timeout
    if not webbrowser.open(login_url, new=1, autoraise=True):
        callback_server.server_close()
        raise AccountError("Could not open a web browser. Set a default browser and try again.")

    try:
        deadline = time.monotonic() + timeout
        while not received.is_set():
            callback_server.timeout = max(0.1, min(1.0, deadline - time.monotonic()))
            callback_server.handle_request()
            if time.monotonic() >= deadline:
                break
        if not received.is_set():
            raise AccountError("Microsoft sign-in timed out. Try again and finish the browser steps within "
                               f"{timeout // 60} minutes.")
        completed = microsoft_account.complete_login(client_id, None, redirect_uri, result["code"], verifier)
        account = _normalize_profile(completed)
        keyring.set_password(SERVICE_NAME, f"refresh:{account['id']}", account["refresh_token"])
        return {key: account[key] for key in ("id", "name", "uuid")}
    except AccountError:
        raise
    except Exception as exc:
        message = str(exc).strip()
        if "AzureAppNotPermitted" in type(exc).__name__ or "not permitted" in message.lower():
            raise AccountError("Microsoft sign-in worked, but this public client ID does not have the required "
                               "Xbox/Minecraft permission. Use an app registration configured for public-client "
                               "browser sign-in and Minecraft Java access.") from exc
        if "AccountNotOwnMinecraft" in type(exc).__name__ or "does not own" in message.lower():
            raise AccountError("This Microsoft account does not have a Minecraft Java Edition profile.") from exc
        raise AccountError(f"Microsoft sign-in failed: {message or type(exc).__name__}") from exc
    finally:
        callback_server.server_close()


def refresh(account: dict[str, str], client_id: str) -> dict[str, str]:
    """Exchange the saved refresh token for a fresh Minecraft access token."""
    keyring = _keyring()
    try:
        refresh_token = keyring.get_password(SERVICE_NAME, f"refresh:{account['id']}")
    except Exception as exc:
        raise AccountError("Could not read the saved Microsoft session from the desktop keyring.") from exc
    if not refresh_token:
        raise AccountError(f"The saved session for {account['name']} is missing. Remove it and sign in again.")
    if not client_id:
        raise AccountError("Set your Microsoft public-client application ID before refreshing this session.")
    try:
        profile = _normalize_profile(microsoft_account.complete_refresh(client_id, None, None, refresh_token))
        keyring.set_password(SERVICE_NAME, f"refresh:{account['id']}", profile["refresh_token"])
        profile.update({key: account[key] for key in ("id", "name", "uuid")})
        return profile
    except AccountError:
        raise
    except Exception as exc:
        raise AccountError(f"Could not refresh {account['name']}'s Microsoft session. Sign in again. "
                           f"({str(exc).strip() or type(exc).__name__})") from exc


def forget(account_id: str) -> None:
    """Remove a saved Microsoft refresh token from the OS credential store."""
    keyring = _keyring()
    try:
        keyring.delete_password(SERVICE_NAME, f"refresh:{account_id}")
    except Exception as exc:
        # Removing stale metadata should still be possible if the key was already deleted.
        if "password was not found" not in str(exc).lower() and "not found" not in type(exc).__name__.lower():
            raise AccountError("Could not remove the saved session from the desktop keyring.") from exc
