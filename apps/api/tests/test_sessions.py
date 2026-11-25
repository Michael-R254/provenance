from datetime import UTC, datetime

import pytest

from provenance.sessions import InvalidSessionError, SessionSigner, hash_client


def test_issued_token_verifies() -> None:
    signer = SessionSigner("s" * 32, ttl_seconds=60, clock=lambda: 1000.0)
    token, session = signer.issue()
    assert signer.verify(token) == session
    assert session.expires_at == 1060


def test_tampered_or_foreign_tokens_are_rejected() -> None:
    signer = SessionSigner("s" * 32, ttl_seconds=60)
    token, _ = signer.issue()
    body, _, signature = token.partition(".")
    with pytest.raises(InvalidSessionError):
        signer.verify(body + "x." + signature)
    with pytest.raises(InvalidSessionError):
        SessionSigner("t" * 32, ttl_seconds=60).verify(token)
    with pytest.raises(InvalidSessionError):
        signer.verify("garbage")


def test_expired_tokens_are_rejected() -> None:
    now = [1000.0]
    signer = SessionSigner("s" * 32, ttl_seconds=60, clock=lambda: now[0])
    token, _ = signer.issue()
    now[0] = 1061.0
    with pytest.raises(InvalidSessionError):
        signer.verify(token)


def test_client_hashes_are_salted_and_change_daily() -> None:
    day1 = datetime(2026, 1, 1, tzinfo=UTC)
    day2 = datetime(2026, 1, 2, tzinfo=UTC)
    a = hash_client("salt", "ip", "203.0.113.9", day1)
    assert "203.0.113.9" not in a
    assert a == hash_client("salt", "ip", "203.0.113.9", day1)
    assert a != hash_client("salt", "ip", "203.0.113.9", day2)
    assert a != hash_client("other", "ip", "203.0.113.9", day1)
