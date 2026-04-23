"""Tests for HTTP auth, rate limiting, and token propagation."""

from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_folk import server


def build_request(
    path: str,
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    """Build a minimal Starlette request for middleware unit tests."""
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": encoded_headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.fixture(autouse=True)
def reset_server_client() -> Iterator[None]:
    """Reset the global client so tests do not share auth state."""
    original_client = server._client
    server._client = None
    try:
        yield
    finally:
        server._client = original_client


@pytest.fixture
async def middleware(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[server.HTTPPassthroughAuthAndRateLimitMiddleware]:
    """Create middleware with predictable limits for tests."""
    monkeypatch.setenv("MCP_HTTP_RATE_LIMIT_PER_MIN", "2")
    monkeypatch.setenv("MCP_HTTP_NOAUTH_RATE_LIMIT_PER_MIN", "2")
    monkeypatch.setenv("MCP_HTTP_MAX_BODY_BYTES", "5")
    yield server.HTTPPassthroughAuthAndRateLimitMiddleware(app=MagicMock())


@pytest.mark.asyncio
async def test_health_endpoint_skips_auth(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    request = build_request("/health")
    call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_authorization_returns_401(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    request = build_request("/mcp")
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_authorization_returns_401(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    request = build_request("/mcp", headers={"authorization": "Token nope"})
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_oversized_body_returns_413(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    request = build_request(
        "/mcp",
        headers={
            "authorization": "Bearer folk-token",
            "content-length": "6",
        },
    )
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 413
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_request_token_is_available_during_dispatch(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    request = build_request("/mcp", headers={"authorization": "Bearer folk-token"})

    async def call_next(_: Request) -> Response:
        assert server._get_request_folk_token() == "folk-token"
        return JSONResponse({"ok": True})

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert server._get_request_folk_token() is None


@pytest.mark.asyncio
async def test_unauthorized_rate_limit_uses_ip_bucket(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    request = build_request("/mcp")
    call_next = AsyncMock()

    first = await middleware.dispatch(request, call_next)
    second = await middleware.dispatch(request, call_next)
    third = await middleware.dispatch(request, call_next)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


@pytest.mark.asyncio
async def test_authorized_rate_limit_is_separate_from_noauth_bucket(
    middleware: server.HTTPPassthroughAuthAndRateLimitMiddleware,
) -> None:
    no_auth_request = build_request("/mcp")
    auth_request = build_request("/mcp", headers={"authorization": "Bearer folk-token"})

    async def ok_response(_: Request) -> Response:
        return JSONResponse({"ok": True})

    assert (await middleware.dispatch(no_auth_request, ok_response)).status_code == 401
    assert (await middleware.dispatch(no_auth_request, ok_response)).status_code == 401
    assert (await middleware.dispatch(auth_request, ok_response)).status_code == 200
    assert (await middleware.dispatch(auth_request, ok_response)).status_code == 200
    assert (await middleware.dispatch(auth_request, ok_response)).status_code == 429


@pytest.mark.asyncio
async def test_get_client_uses_env_api_key_without_request_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOLK_API_KEY", "env-token")
    client = server.get_client()
    client._session = MagicMock()
    client._session.request.return_value.__aenter__ = AsyncMock(return_value=MagicMock(status=204))
    client._session.request.return_value.__aexit__ = AsyncMock(return_value=None)

    await client._request("DELETE", "/people/per_test")

    request_headers = client._session.request.call_args.kwargs["headers"]
    assert request_headers["Authorization"] == "Bearer env-token"


@pytest.mark.asyncio
async def test_get_client_prefers_request_token_over_env_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOLK_API_KEY", "env-token")
    token_ctx = server._REQUEST_FOLK_TOKEN.set("request-token")
    try:
        client = server.get_client()
        client._session = MagicMock()
        client._session.request.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(status=204)
        )
        client._session.request.return_value.__aexit__ = AsyncMock(return_value=None)

        await client._request("DELETE", "/people/per_test")

        request_headers = client._session.request.call_args.kwargs["headers"]
        assert request_headers["Authorization"] == "Bearer request-token"
    finally:
        server._REQUEST_FOLK_TOKEN.reset(token_ctx)


@pytest.mark.asyncio
async def test_browse_people_uses_cursor_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.list_people_page = AsyncMock(
        return_value=(
            [
                MagicMock(
                    id="per_1",
                    first_name="Jane",
                    last_name="Doe",
                    full_name=None,
                    emails=["jane@example.com"],
                    job_title="Engineer",
                )
            ],
            "next-token",
        )
    )
    monkeypatch.setattr(server, "get_client", lambda ctx=None: fake_client)

    result = await server.browse_people(cursor="start-token", limit=5)

    assert result["cursor"] == "start-token"
    assert result["next_cursor"] == "next-token"
    assert result["limit"] == 5
    assert result["has_more"] is True
    assert result["people"] == [
        {
            "id": "per_1",
            "name": "Jane Doe",
            "email": "jane@example.com",
            "job_title": "Engineer",
        }
    ]


@pytest.mark.asyncio
async def test_browse_companies_uses_cursor_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.list_companies_page = AsyncMock(
        return_value=([SimpleNamespace(id="com_1", name="Acme Inc", industry="Technology")], None)
    )
    monkeypatch.setattr(server, "get_client", lambda ctx=None: fake_client)

    result = await server.browse_companies(cursor=None, limit=10)

    assert result["cursor"] is None
    assert result["next_cursor"] is None
    assert result["limit"] == 10
    assert result["has_more"] is False
    assert result["companies"] == [
        {
            "id": "com_1",
            "name": "Acme Inc",
            "industry": "Technology",
        }
    ]
