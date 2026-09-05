"""
Google OAuth for Search Console, read-only.

The refresh token lives in a signed httpOnly cookie rather than a database:
this app has no datastore, and adding one for a single string is not worth
it. The cost is that a connection is per-browser, which the UI states rather
than leaving it to be discovered.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

COOKIE_NAME = "gsc_token"
STATE_TTL_SECONDS = 600  # generous, because client clock skew is real


class OAuthError(Exception):
    """Anything the user needs told plainly rather than as a stack trace."""


def _secret() -> bytes:
    # Reuse an existing server secret; fall back to the client secret, which
    # is already private to the deployment.
    raw = (os.getenv("GTMP") or os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if not raw:
        raise OAuthError("Server is missing GOOGLE_CLIENT_SECRET.")
    return raw.encode()


def _client() -> tuple:
    cid = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    csec = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if not cid or not csec:
        raise OAuthError("Google sign-in is not configured on this deployment.")
    return cid, csec


def configured() -> bool:
    return bool((os.getenv("GOOGLE_CLIENT_ID") or "").strip()
                and (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip())


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: bytes) -> str:
    mac = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return f"{_b64e(payload)}.{_b64e(mac)}"


def _unsign(token: str) -> bytes:
    try:
        body, mac = token.split(".", 1)
    except ValueError:
        raise OAuthError("Malformed token.")
    payload = _b64d(body)
    expected = hmac.new(_secret(), payload, hashlib.sha256).digest()
    # Constant-time: a timing leak here would let a forged value be guessed.
    if not hmac.compare_digest(_b64d(mac), expected):
        raise OAuthError("Token signature does not match.")
    return payload


def make_state() -> str:
    return _sign(json.dumps({"n": _b64e(os.urandom(12)), "t": int(time.time())}).encode())


def check_state(state: str) -> None:
    """Without this, an attacker can complete a flow into someone's session."""
    if not state:
        raise OAuthError("Missing state.")
    data = json.loads(_unsign(state))
    if time.time() - data.get("t", 0) > STATE_TTL_SECONDS:
        raise OAuthError("That sign-in link expired. Try connecting again.")


def seal_refresh_token(refresh_token: str) -> str:
    return _sign(json.dumps({"r": refresh_token}).encode())


def open_refresh_token(cookie: str) -> str:
    token = json.loads(_unsign(cookie)).get("r")
    if not token:
        raise OAuthError("No refresh token stored.")
    return token


def auth_url(redirect_uri: str) -> str:
    cid, _ = _client()
    return AUTH_URL + "?" + urlencode({
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        # Without prompt=consent Google omits the refresh token on repeat
        # authorisations, and the connection silently fails to persist.
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": make_state(),
    })


def exchange_code(code: str, redirect_uri: str) -> str:
    cid, csec = _client()
    r = httpx.post(TOKEN_URL, timeout=30, data={
        "code": code, "client_id": cid, "client_secret": csec,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code",
    })
    if r.status_code != 200:
        raise OAuthError(f"Google rejected the sign-in ({r.status_code}).")
    refresh = r.json().get("refresh_token")
    if not refresh:
        raise OAuthError("Google did not return a refresh token. Disconnect the app "
                         "in your Google account and connect again.")
    return refresh


def access_token(refresh_token: str) -> str:
    cid, csec = _client()
    r = httpx.post(TOKEN_URL, timeout=30, data={
        "refresh_token": refresh_token, "client_id": cid,
        "client_secret": csec, "grant_type": "refresh_token",
    })
    if r.status_code == 400 and "invalid_grant" in r.text:
        # The likeliest cause in Testing mode: refresh tokens expire after
        # 7 days. Say reconnect, not "something went wrong".
        raise OAuthError("Your Search Console connection expired. Connect again.")
    if r.status_code != 200:
        raise OAuthError(f"Could not refresh Google access ({r.status_code}).")
    return r.json()["access_token"]


def list_sites(token: str) -> list:
    r = httpx.get("https://www.googleapis.com/webmasters/v3/sites",
                  headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        raise OAuthError(f"Could not list your Search Console properties ({r.status_code}).")
    return [
        {"url": e.get("siteUrl"), "permission": e.get("permissionLevel")}
        for e in r.json().get("siteEntry", [])
        if e.get("permissionLevel") != "siteUnverifiedUser"
    ]


def query_search_analytics(token: str, site_url: str, days: int, dimension: str = "query") -> dict:
    """
    Returns the shape parse_gsc produces, so the table, filters, sorting and
    selection all work without a second rendering path.
    """
    import datetime as _dt
    end = _dt.date.today() - _dt.timedelta(days=2)  # GSC data lags ~2 days
    start = end - _dt.timedelta(days=days)

    from urllib.parse import quote
    r = httpx.post(
        f"https://www.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/searchAnalytics/query",
        headers={"Authorization": f"Bearer {token}"}, timeout=60,
        json={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": [dimension],
            # The API caps at 25,000 per request. Ask for the top 1,000 and
            # say so, rather than paging silently or truncating quietly.
            "rowLimit": 1000,
        },
    )
    if r.status_code == 403:
        raise OAuthError("That account cannot read this property in Search Console.")
    if r.status_code != 200:
        raise OAuthError(f"Search Console returned {r.status_code}.")

    rows = [{
        "key": (row.get("keys") or [""])[0],
        "clicks": row.get("clicks"),
        "impressions": row.get("impressions"),
        "ctr": row.get("ctr"),
        "position": row.get("position"),
    } for row in r.json().get("rows", [])]

    warnings = [f"{start.isoformat()} to {end.isoformat()}. "
                "Search Console data lags about two days."]
    if len(rows) == 1000:
        warnings.append("Showing the top 1,000 rows by clicks; there may be more.")

    return {
        "source": "gsc_api",
        "key_kind": "query" if dimension == "query" else "page",
        "row_count": len(rows),
        "columns_found": ["clicks", "ctr", "impressions", "position"],
        "warnings": warnings,
        "rows": rows,
        "site_url": site_url,
    }
