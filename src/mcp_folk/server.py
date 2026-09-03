"""Folk CRM MCP Server - AI-Friendly Interface.

This server provides intent-based tools optimized for AI assistants:
- Minimal response payloads (tokens are expensive)
- Two-phase lookup (find first, get details second)
- Natural language search (fuzzy name matching)
- Compound operations where useful
"""

import logging
import os
import re
import sys
import time
from collections import deque
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from hashlib import sha256
from importlib.resources import files
from typing import Any

from fastmcp import Context, FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_folk.api_client import FolkAPIError, FolkClient
from mcp_folk.api_models import Company, Group, Person

# Folk ID format: prefix + UUID v4 (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
_FOLK_ID_RE = re.compile(
    r"^[a-z]{2,4}_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _report_api_error(ctx: Context | None, e: FolkAPIError) -> None:
    """Report safe error context without leaking API payload details."""
    if ctx:
        ctx.error(f"Folk API request failed (status={e.status})")


_REQUEST_FOLK_TOKEN: ContextVar[str | None] = ContextVar("request_folk_token", default=None)


def _get_request_folk_token() -> str | None:
    """Get Folk token from current request context for stateless passthrough mode."""
    return _REQUEST_FOLK_TOKEN.get()


def _extract_bearer_token(header_value: str | None) -> str | None:
    """Extract bearer token from Authorization header."""
    if not header_value:
        return None
    parts = header_value.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


class HTTPPassthroughAuthAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Stateless auth: require inbound Folk bearer token and forward it upstream."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.auth_rate_limit = max(1, int(os.environ.get("MCP_HTTP_RATE_LIMIT_PER_MIN", "120")))
        self.no_auth_rate_limit = max(
            1, int(os.environ.get("MCP_HTTP_NOAUTH_RATE_LIMIT_PER_MIN", "40"))
        )
        self.max_body_bytes = max(1, int(os.environ.get("MCP_HTTP_MAX_BODY_BYTES", "1048576")))
        self._requests: dict[str, deque[float]] = {}

    def _is_rate_limited(self, key: str, limit: int) -> bool:
        """Apply rolling per-minute limit for a given key."""
        now = time.monotonic()
        window = self._requests.setdefault(key, deque())
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= limit:
            return True
        window.append(now)
        return False

    def _has_oversized_body(self, request: Request) -> bool:
        """Use Content-Length guard to reject oversized requests early."""
        content_length = request.headers.get("content-length")
        if not content_length:
            return False
        try:
            return int(content_length) > self.max_body_bytes
        except ValueError:
            return True

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == "/health":
            return await call_next(request)
        if self._has_oversized_body(request):
            return JSONResponse({"error": "Request too large"}, status_code=413)

        client_ip = request.client.host if request.client else "unknown"
        token = _extract_bearer_token(request.headers.get("authorization"))
        if not token:
            if self._is_rate_limited(f"noauth:{client_ip}", self.no_auth_rate_limit):
                return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        token_hash = sha256(token.encode("utf-8")).hexdigest()[:16]
        if self._is_rate_limited(f"auth:{client_ip}:{token_hash}", self.auth_rate_limit):
            return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

        token_ctx = _REQUEST_FOLK_TOKEN.set(token)
        try:
            return await call_next(request)
        finally:
            _REQUEST_FOLK_TOKEN.reset(token_ctx)


def _validate_folk_id(value: str, entity: str = "entity") -> None:
    """Validate that a string matches the Folk ID format (prefix_uuid).

    Raises McpError with an actionable message if the ID is invalid.
    """
    if not _FOLK_ID_RE.match(value):
        raise ValueError(
            f"Invalid {entity} ID '{value}'. "
            f"Folk IDs are prefix + UUID v4 format (e.g., 'per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'). "
            f"Call find_person or find_company first to get the correct ID from the search results."
        )


def _person_display_name(person: Person) -> str:
    """Build a stable display name for a person."""
    if person.full_name:
        return person.full_name

    parts = [part for part in (person.first_name, person.last_name) if part]
    return " ".join(parts) if parts else "Unknown"


def _company_display_name(company: Company) -> str:
    """Build a stable display name for a company."""
    return company.name or "Unknown"


def _resolve_group_by_name(groups: list[Group], group_name: str) -> Group | None:
    """Resolve a group by exact or fuzzy name match."""
    normalized = group_name.lower()
    return next((g for g in groups if g.name.lower() == normalized), None) or next(
        (g for g in groups if normalized in g.name.lower()),
        None,
    )


# Configure logging to stderr (stdout is for MCP JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_folk")
logger.info("Folk server module loading...")

# Create MCP server
mcp = FastMCP(
    "Folk",
    instructions=(
        "Before using Folk CRM tools, read the skill://folk/usage resource "
        "for tool routing, ID format rules, and situational handling patterns."
    ),
)


SKILL_CONTENT = files("mcp_folk").joinpath("SKILL.md").read_text()


@mcp.resource("skill://folk/usage")
def folk_skill() -> str:
    """How to effectively use Folk CRM tools: ID format, group queries, situational handling."""
    return SKILL_CONTENT


# Global client instance
_client: FolkClient | None = None


def get_client(ctx: Context | None = None) -> FolkClient:
    """Get or create the API client instance."""
    global _client
    if _client is None:
        # Fallback key is only for stdio/local execution; HTTP mode is bearer passthrough.
        _client = FolkClient(
            api_key=os.environ.get("FOLK_API_KEY"),
            token_provider=_get_request_folk_token,
        )
    if not _client.api_key and not _get_request_folk_token():
        msg = "FOLK_API_KEY or inbound Authorization bearer token is required"
        if ctx:
            ctx.error(msg)
        raise ValueError(msg)
    return _client


# Health endpoint for HTTP transport
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring."""
    return JSONResponse({"status": "healthy", "service": "mcp-folk"})


# =============================================================================
# TIER 1: Search/Find Tools (Most Used)
# These return minimal payloads for quick lookups
# =============================================================================


@mcp.tool()
async def find_person(
    name: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find people by name in the CRM.

    Use this to check if someone exists or to get their ID for further operations.
    Returns minimal info to save tokens - use get_person_details for full info.

    Args:
        name: Name to search for (first name, last name, or full name)

    Returns:
        {
            "found": true/false,
            "matches": [{"id": "...", "name": "Full Name", "email": "..."}],
            "total": number of matches
        }
    """
    client = get_client(ctx)
    try:
        # Search by fullName using 'like' operator (Folk API's contains equivalent)
        filters = {"fullName": {"like": name}}
        people = await client.list_people(limit=10, filters=filters)

        matches = []
        for person in people:
            matches.append(
                {
                    "id": person.id,
                    "name": _person_display_name(person),
                    "email": person.emails[0] if person.emails else None,
                }
            )

        return {
            "found": len(matches) > 0,
            "matches": matches,
            "total": len(matches),
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def find_company(
    name: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find companies by name in the CRM.

    Use this to check if a company exists or to get its ID for further operations.
    Returns minimal info - use get_company_details for full info.

    Args:
        name: Company name to search for

    Returns:
        {
            "found": true/false,
            "matches": [{"id": "...", "name": "Company Name", "industry": "..."}],
            "total": number of matches
        }
    """
    client = get_client(ctx)
    try:
        # Search by name using 'like' operator (Folk API's contains equivalent)
        filters = {"name": {"like": name}}
        companies = await client.list_companies(limit=10, filters=filters)

        matches = []
        for company in companies:
            matches.append(
                {
                    "id": company.id,
                    "name": _company_display_name(company),
                    "industry": company.industry,
                }
            )

        return {
            "found": len(matches) > 0,
            "matches": matches,
            "total": len(matches),
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# =============================================================================
# TIER 2: Detail Tools
# Get full information after finding the right entity
# =============================================================================


@mcp.tool()
async def get_person_details(
    person_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get full details for a person by their ID.

    IMPORTANT: You must call find_person first to get the person_id.
    Folk IDs are prefix + UUID v4 format (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)

    Returns:
        Full person details including all fields, notes count, etc.
    """
    _validate_folk_id(person_id, "person")
    client = get_client(ctx)
    try:
        person = await client.get_person(person_id)
        return {
            "id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "full_name": person.full_name,
            "emails": person.emails or [],
            "phones": person.phones or [],
            "job_title": person.job_title,
            "description": person.description,
            "created_at": person.created_at,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def get_company_details(
    company_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get full details for a company by its ID.

    IMPORTANT: You must call find_company first to get the company_id.
    Folk IDs are prefix + UUID v4 format (e.g., "com_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        company_id: Exact Folk ID from find_company results (prefix + UUID format)

    Returns:
        Full company details including all fields.
    """
    _validate_folk_id(company_id, "company")
    client = get_client(ctx)
    try:
        company = await client.get_company(company_id)
        return {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "industry": company.industry,
            "emails": company.emails or [],
            "phones": company.phones or [],
            "urls": company.urls or [],
            "created_at": company.created_at,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# =============================================================================
# TIER 3: Browse Tools
# For exploring the CRM when you don't know what you're looking for
# =============================================================================


@mcp.tool()
async def browse_people(
    cursor: str | None = None,
    limit: int = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Browse people in the CRM using Folk cursor pagination.

    Use this to explore contacts when you don't have a specific name to search.
    Returns minimal info per person plus the next cursor when available.

    Args:
        cursor: Cursor from a previous browse response, or None for the first page
        limit: Results per page (max 50)

    Returns:
        {
            "people": [{"id": "...", "name": "...", "email": "..."}],
            "cursor": input cursor,
            "next_cursor": cursor for the next page, if any,
            "limit": results per page,
            "has_more": whether more pages exist
        }
    """
    client = get_client(ctx)
    try:
        limit = min(max(limit, 1), 50)
        people, next_cursor = await client.list_people_page(limit=limit, cursor=cursor)

        results = []
        for person in people:
            results.append(
                {
                    "id": person.id,
                    "name": _person_display_name(person),
                    "email": person.emails[0] if person.emails else None,
                    "job_title": person.job_title,
                }
            )

        return {
            "people": results,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "limit": limit,
            "has_more": next_cursor is not None,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def browse_companies(
    cursor: str | None = None,
    limit: int = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Browse companies in the CRM using Folk cursor pagination.

    Use this to explore companies when you don't have a specific name to search.
    Returns minimal info per company plus the next cursor when available.

    Args:
        cursor: Cursor from a previous browse response, or None for the first page
        limit: Results per page (max 50)

    Returns:
        {
            "companies": [{"id": "...", "name": "...", "industry": "..."}],
            "cursor": input cursor,
            "next_cursor": cursor for the next page, if any,
            "limit": results per page,
            "has_more": whether more pages exist
        }
    """
    client = get_client(ctx)
    try:
        limit = min(max(limit, 1), 50)
        companies, next_cursor = await client.list_companies_page(limit=limit, cursor=cursor)

        results = []
        for company in companies:
            results.append(
                {
                    "id": company.id,
                    "name": _company_display_name(company),
                    "industry": company.industry,
                }
            )

        return {
            "companies": results,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "limit": limit,
            "has_more": next_cursor is not None,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# =============================================================================
# TIER 4: Group Tools
# Query groups and filter contacts within groups
# =============================================================================


@mcp.tool()
async def list_groups(
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List all groups in the Folk workspace.

    Use this to discover what groups exist when you don't know the group name.
    For querying people/companies in a known group, use find_people_in_group directly.

    Returns:
        {
            "groups": [{"id": "grp_xxx", "name": "Demos Management"}, ...],
            "total": number of groups
        }
    """
    client = get_client(ctx)
    try:
        groups = await client.list_groups(limit=100)

        return {
            "groups": [{"id": g.id, "name": g.name} for g in groups],
            "total": len(groups),
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def find_people_in_group(
    group_name: str,
    status: str | None = None,
    custom_field: str | None = None,
    custom_value: str | None = None,
    limit: int = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find people in a group, optionally filtered by custom fields like Status.

    This is the primary tool for querying contacts within Folk groups/views.
    Custom fields like "Status" are group-specific in Folk.

    Args:
        group_name: Name of the group (e.g., "Demos Management", "Clients", "Leads")
        status: Filter by "Status" custom field value (e.g., "Follow up 1", "Active", "Won")
        custom_field: Name of a different custom field to filter by
        custom_value: Value to match for the custom_field
        limit: Maximum results to return (default 20, max 50)

    Returns:
        {
            "found": true/false,
            "people": [{"id": "...", "name": "...", "email": "...", "status": "...", "custom_fields": {...}}],
            "total": number of matches,
            "group_name": "Demos Management"
        }

    Examples:
        - Find leads needing follow-up: find_people_in_group("Demos Management", status="Follow up 1")
        - Find active clients: find_people_in_group("Clients", status="Active")
        - Filter by custom field: find_people_in_group("Leads", custom_field="Priority", custom_value="High")
    """
    client = get_client(ctx)
    try:
        limit = min(max(limit, 1), 50)

        # Resolve group name to ID
        groups = await client.list_groups(limit=100)
        group = _resolve_group_by_name(groups, group_name)

        if not group:
            available = [g.name for g in groups[:10]]
            return {
                "found": False,
                "error": f"Group '{group_name}' not found",
                "available_groups": available,
                "hint": "Check the group name or use list_groups to see all available groups",
            }

        group_id = group.id

        # Build filters
        filters: dict[str, Any] = {
            "groups": {"in": {"id": group_id}},
        }

        # Add status filter if provided (Status uses 'in' operator for select fields)
        if status:
            filters[f"customFieldValues.{group_id}.Status"] = {"in": status}

        # Add custom field filter if provided (use 'in' for select fields, 'like' for text)
        if custom_field and custom_value:
            filters[f"customFieldValues.{group_id}.{custom_field}"] = {"in": custom_value}

        people = await client.list_people(limit=limit, filters=filters)

        results = []
        for person in people:
            # Extract custom fields for this group
            group_custom_fields = person.custom_field_values.get(group_id, {})

            results.append(
                {
                    "id": person.id,
                    "name": _person_display_name(person),
                    "email": person.emails[0] if person.emails else None,
                    "job_title": person.job_title,
                    "status": group_custom_fields.get("Status"),
                    "custom_fields": group_custom_fields,
                }
            )

        return {
            "found": len(results) > 0,
            "people": results,
            "total": len(results),
            "group_name": group.name,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def find_companies_in_group(
    group_name: str,
    status: str | None = None,
    custom_field: str | None = None,
    custom_value: str | None = None,
    limit: int = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find companies in a group, optionally filtered by custom fields like Status.

    This is the primary tool for querying companies within Folk groups/views.

    Args:
        group_name: Name of the group (e.g., "Target Accounts", "Partners")
        status: Filter by "Status" custom field value
        custom_field: Name of a different custom field to filter by
        custom_value: Value to match for the custom_field
        limit: Maximum results to return (default 20, max 50)

    Returns:
        {
            "found": true/false,
            "companies": [{"id": "...", "name": "...", "status": "...", "custom_fields": {...}}],
            "total": number of matches,
            "group_name": "..."
        }
    """
    client = get_client(ctx)
    try:
        limit = min(max(limit, 1), 50)

        # Resolve group name to ID
        groups = await client.list_groups(limit=100)
        group = _resolve_group_by_name(groups, group_name)

        if not group:
            available = [g.name for g in groups[:10]]
            return {
                "found": False,
                "error": f"Group '{group_name}' not found",
                "available_groups": available,
                "hint": "Check the group name or use list_groups to see all available groups",
            }

        group_id = group.id

        # Build filters
        filters: dict[str, Any] = {
            "groups": {"in": {"id": group_id}},
        }

        # Add status filter if provided (Status uses 'in' operator for select fields)
        if status:
            filters[f"customFieldValues.{group_id}.Status"] = {"in": status}

        # Add custom field filter if provided (use 'in' for select fields, 'like' for text)
        if custom_field and custom_value:
            filters[f"customFieldValues.{group_id}.{custom_field}"] = {"in": custom_value}

        companies = await client.list_companies(limit=limit, filters=filters)

        results = []
        for company in companies:
            # Extract custom fields for this group
            group_custom_fields = company.custom_field_values.get(group_id, {})

            results.append(
                {
                    "id": company.id,
                    "name": _company_display_name(company),
                    "industry": company.industry,
                    "status": group_custom_fields.get("Status"),
                    "custom_fields": group_custom_fields,
                }
            )

        return {
            "found": len(results) > 0,
            "companies": results,
            "total": len(results),
            "group_name": group.name,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# =============================================================================
# TIER 5: Action Tools
# Create, update, and manage CRM data
# =============================================================================


@mcp.tool()
async def add_person(
    first_name: str,
    last_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    job_title: str | None = None,
    notes: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Add a new person to the CRM.

    Args:
        first_name: Person's first name (required)
        last_name: Person's last name
        email: Email address
        phone: Phone number
        job_title: Job title or role
        notes: Initial notes about this person

    Returns:
        {"id": "...", "name": "...", "created": true}
    """
    client = get_client(ctx)
    try:
        emails = [email] if email else None
        phones = [phone] if phone else None

        person = await client.create_person(
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=phones,
            job_title=job_title,
            description=notes,
        )

        full_name = f"{first_name} {last_name}".strip() if last_name else first_name

        return {
            "id": person.id,
            "name": full_name,
            "created": True,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def add_company(
    name: str,
    industry: str | None = None,
    website: str | None = None,
    notes: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Add a new company to the CRM.

    Args:
        name: Company name (required)
        industry: Industry or sector
        website: Company website URL
        notes: Initial notes about this company

    Returns:
        {"id": "...", "name": "...", "created": true}
    """
    client = get_client(ctx)
    try:
        urls = [website] if website else None

        company = await client.create_company(
            name=name,
            industry=industry,
            urls=urls,
            description=notes,
        )

        return {
            "id": company.id,
            "name": company.name,
            "created": True,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def update_person(
    person_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    job_title: str | None = None,
    group_id: str | None = None,
    custom_field_values: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Update an existing person's information.

    IMPORTANT: You must call find_person first to get the person_id.
    Folk IDs are prefix + UUID v4 format (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)
        first_name: New first name (or None to keep existing)
        last_name: New last name
        email: New email (replaces existing)
        phone: New phone (replaces existing)
        job_title: New job title
        group_id: Group containing the custom fields being updated. Required with
            custom_field_values; the person must already belong to this group.
        custom_field_values: Values to set for fields in group_id. For example,
            to set a single-select Status field, use group_id="grp_..." and
            custom_field_values={"Status": "Active"}. This is sent to Folk as
            {"customFieldValues": {"grp_...": {"Status": "Active"}}}.

    Returns:
        {"id": "...", "name": "...", "updated": true}
    """
    _validate_folk_id(person_id, "person")
    if custom_field_values is None and group_id is not None:
        raise ValueError("group_id can only be used together with custom_field_values.")
    if custom_field_values is not None:
        if group_id is None:
            raise ValueError("group_id is required when updating group-scoped custom fields.")
        _validate_folk_id(group_id, "group")
        if not custom_field_values:
            raise ValueError("custom_field_values must contain at least one field value.")
        if any(not isinstance(name, str) or not name.strip() for name in custom_field_values):
            raise ValueError("custom_field_values keys must be non-empty custom field names.")

    client = get_client(ctx)
    try:
        emails = [email] if email else None
        phones = [phone] if phone else None
        group_ids: list[str] | None = None
        custom_fields: dict[str, Any] | None = None

        if custom_field_values is not None:
            # Folk validates that every customFieldValues group ID is also sent in
            # groups. Fetch current membership and send the complete list so this
            # update cannot remove the person's other group memberships.
            existing_person = await client.get_person(person_id)
            group_ids = [group.id for group in existing_person.groups]
            if group_id not in group_ids:
                raise ValueError(
                    f"Person '{person_id}' is not a member of group '{group_id}'. "
                    "Add the person to that group before updating its custom fields."
                )
            custom_fields = {group_id: custom_field_values}

        person = await client.update_person(
            person_id=person_id,
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=phones,
            job_title=job_title,
            group_ids=group_ids,
            custom_fields=custom_fields,
        )

        return {
            "id": person.id,
            "name": _person_display_name(person),
            "updated": True,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def update_company(
    company_id: str,
    name: str | None = None,
    industry: str | None = None,
    website: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Update an existing company's information.

    IMPORTANT: You must call find_company first to get the company_id.
    Folk IDs are prefix + UUID v4 format (e.g., "com_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        company_id: Exact Folk ID from find_company results (prefix + UUID format)
        name: New company name
        industry: New industry
        website: New website URL

    Returns:
        {"id": "...", "name": "...", "updated": true}
    """
    _validate_folk_id(company_id, "company")
    client = get_client(ctx)
    try:
        urls = [website] if website else None

        company = await client.update_company(
            company_id=company_id,
            name=name,
            industry=industry,
            urls=urls,
        )

        return {
            "id": company.id,
            "name": _company_display_name(company),
            "updated": True,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def delete_person(
    person_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Delete a person from the CRM. This action cannot be undone.

    IMPORTANT: You must call find_person first to get the person_id.
    Folk IDs are prefix + UUID v4 format (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)

    Returns:
        {"id": "...", "deleted": true}
    """
    _validate_folk_id(person_id, "person")
    client = get_client(ctx)
    try:
        await client.delete_person(person_id)
        return {"id": person_id, "deleted": True}
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def delete_company(
    company_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Delete a company from the CRM. This action cannot be undone.

    IMPORTANT: You must call find_company first to get the company_id.
    Folk IDs are prefix + UUID v4 format (e.g., "com_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        company_id: Exact Folk ID from find_company results (prefix + UUID format)

    Returns:
        {"id": "...", "deleted": true}
    """
    _validate_folk_id(company_id, "company")
    client = get_client(ctx)
    try:
        await client.delete_company(company_id)
        return {"id": company_id, "deleted": True}
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# =============================================================================
# TIER 6: Notes & Reminders
# Attach context to contacts
# =============================================================================


@mcp.tool()
async def add_note(
    person_id: str,
    content: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Add a note to a person.

    IMPORTANT: You must call find_person first to get the person_id.
    Folk IDs are prefix + UUID v4 format (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)
        content: Note content

    Returns:
        {"id": "...", "added": true}
    """
    _validate_folk_id(person_id, "person")
    client = get_client(ctx)
    try:
        note = await client.create_note(
            entity_id=person_id,
            content=content,
            visibility="public",
        )
        return {"id": note.id, "added": True}
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def get_notes(
    person_id: str,
    limit: int = 10,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get notes for a person.

    IMPORTANT: You must call find_person first to get the person_id.

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)
        limit: Maximum notes to return (default 10)

    Returns:
        {"notes": [{"id": "...", "content": "...", "created_at": "..."}]}
    """
    _validate_folk_id(person_id, "person")
    limit = min(max(limit, 1), 50)
    client = get_client(ctx)
    try:
        notes = await client.list_notes(limit=limit, entity_id=person_id)
        return {
            "notes": [
                {
                    "id": note.id,
                    "content": note.content,
                    "created_at": note.created_at,
                }
                for note in notes
            ]
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def set_reminder(
    person_id: str,
    reminder: str,
    when: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Set a reminder for a person.

    IMPORTANT: You must call find_person first to get the person_id.
    Folk IDs are prefix + UUID v4 format (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)
        reminder: What to be reminded about
        when: When to trigger (ISO 8601 datetime, e.g., "2026-01-28T09:00:00Z")

    Returns:
        {"id": "...", "set": true}
    """
    _validate_folk_id(person_id, "person")
    client = get_client(ctx)
    try:
        result = await client.create_reminder(
            entity_id=person_id,
            name=reminder,
            trigger_time=when,
            visibility="public",
        )
        return {"id": result.id, "set": True}
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


@mcp.tool()
async def log_interaction(
    person_id: str,
    interaction_type: str,
    when: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Log an interaction with a person.

    IMPORTANT: You must call find_person first to get the person_id.
    Folk IDs are prefix + UUID v4 format (e.g., "per_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").

    Args:
        person_id: Exact Folk ID from find_person results (prefix + UUID format)
        interaction_type: Type of interaction (e.g., "email", "meeting", "call")
        when: When it occurred (ISO 8601 datetime)

    Returns:
        {"id": "...", "logged": true}
    """
    _validate_folk_id(person_id, "person")
    client = get_client(ctx)
    try:
        interaction_title = interaction_type.replace("_", " ").title()
        interaction_content = f"{interaction_title} logged at {when}."
        result = await client.create_interaction(
            entity_id=person_id,
            interaction_type=interaction_type,
            occurred_at=when,
            title=interaction_title,
            content=interaction_content,
        )
        return {"id": result.id, "logged": True}
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# =============================================================================
# Utility Tools
# =============================================================================


@mcp.tool()
async def whoami(
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get information about the current authenticated user.

    Returns:
        {"id": "...", "name": "...", "email": "..."}
    """
    client = get_client(ctx)
    try:
        user = await client.get_current_user()
        return {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
        }
    except FolkAPIError as e:
        _report_api_error(ctx, e)
        raise


# Create ASGI application for HTTP deployment
app = mcp.http_app()
app.add_middleware(HTTPPassthroughAuthAndRateLimitMiddleware)

# Stdio entrypoint for Claude Desktop / mpak
if __name__ == "__main__":
    logger.info("Running in stdio mode")
    mcp.run()
