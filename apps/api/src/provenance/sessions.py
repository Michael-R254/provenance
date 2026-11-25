"""Short-lived signed session tokens, issued only after a Cloudflare Turnstile check."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx2 as httpx

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class InvalidSessionError(Exception):
    pass


@dataclass(frozen=True)
class Session:
    session_id: str
    expires_at: int


class SessionSigner:
    def __init__(
        self, secret: str, ttl_seconds: int, clock: Callable[[], float] = time.time
    ) -> None:
        if not secret:
            raise ValueError("session secret must not be empty")
        self._key = secret.encode()
        self._ttl = ttl_seconds
        self._clock = clock

    def issue(self) -> tuple[str, Session]:
        session = Session(secrets.token_urlsafe(16), int(self._clock()) + self._ttl)
        body = _b64(json.dumps({"sid": session.session_id, "exp": session.expires_at}).encode())
        return f"{body}.{self._sign(body)}", session

    def verify(self, token: str) -> Session:
        body, _, signature = token.partition(".")
        if not body or not hmac.compare_digest(signature, self._sign(body)):
            raise InvalidSessionError("bad signature")
        try:
            data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            session = Session(str(data["sid"]), int(data["exp"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidSessionError("malformed token") from exc
        if session.expires_at < self._clock():
            raise InvalidSessionError("expired")
        return session

    def _sign(self, body: str) -> str:
        return _b64(hmac.new(self._key, body.encode(), hashlib.sha256).digest())


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def hash_client(salt: str, kind: str, value: str, now: datetime | None = None) -> str:
    """Salted, day-scoped hash so raw IPs are never stored and hashes do not link across days."""
    day = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{salt}|{day}|{kind}|{value}".encode()).hexdigest()


class TurnstileVerifier(Protocol):
    async def verify(self, token: str, remote_ip: str | None) -> bool: ...


class CloudflareTurnstile:
    def __init__(self, secret: str, timeout_seconds: float = 5.0) -> None:
        self._secret = secret
        self._timeout = timeout_seconds

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        form = {"secret": self._secret, "response": token}
        if remote_ip:
            form["remoteip"] = remote_ip
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(TURNSTILE_VERIFY_URL, data=form)
                response.raise_for_status()
                return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            return False  # fail closed
