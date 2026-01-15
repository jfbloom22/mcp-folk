"""Folk CRM MCP Server - FastMCP Implementation."""

import logging
import os
import sys
from typing import Any

from fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_folk.api_client import FolkAPIError, FolkClient
from mcp_folk.api_models import (
    Company,
    Deal,
    Group,
    Interaction,
    Note,
    Person,
    Reminder,
    User,
)

# Debug logging for container diagnostics
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_folk")

logger.info("Folk server module loading...")

# Create MCP server
mcp = FastMCP("Folk")

# Global client instance
_client: FolkClient | None = None


def get_client(ctx: Context | None = None) -> FolkClient:
    """Get or create the API client instance."""
    global _client
    if _client is None:
        api_key = os.environ.get("FOLK_API_KEY")
        if not api_key:
            msg = "FOLK_API_KEY environment variable is required"
            if ctx:
                ctx.error(msg)
            raise ValueError(msg)
        _client = FolkClient(api_key=api_key)
    return _client


# Health endpoint for HTTP transport
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring."""
    return JSONResponse({"status": "healthy", "service": "mcp-folk"})


# ============================================================================
# People Tools
# ============================================================================


@mcp.tool()
async def list_people(
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> list[Person]:
    """List people in the Folk workspace.

    Args:
        limit: Number of people to return (1-100, default 20)
        cursor: Pagination cursor for next page
        ctx: MCP context

    Returns:
        List of people in the workspace
    """
    client = get_client(ctx)
    try:
        return await client.list_people(limit=limit, cursor=cursor)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def get_person(
    person_id: str,
    ctx: Context | None = None,
) -> Person:
    """Get a specific person by ID.

    Args:
        person_id: The person's ID
        ctx: MCP context

    Returns:
        The person details
    """
    client = get_client(ctx)
    try:
        return await client.get_person(person_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def create_person(
    first_name: str | None = None,
    last_name: str | None = None,
    emails: list[str] | None = None,
    phones: list[str] | None = None,
    job_title: str | None = None,
    description: str | None = None,
    group_ids: list[str] | None = None,
    company_ids: list[str] | None = None,
    ctx: Context | None = None,
) -> Person:
    """Create a new person in Folk.

    Args:
        first_name: Person's first name
        last_name: Person's last name
        emails: List of email addresses
        phones: List of phone numbers
        job_title: Job title
        description: Description or notes about the person
        group_ids: List of group IDs to add the person to
        company_ids: List of company IDs to associate with
        ctx: MCP context

    Returns:
        The created person
    """
    client = get_client(ctx)
    try:
        return await client.create_person(
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=phones,
            job_title=job_title,
            description=description,
            group_ids=group_ids,
            company_ids=company_ids,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def update_person(
    person_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    emails: list[str] | None = None,
    phones: list[str] | None = None,
    job_title: str | None = None,
    description: str | None = None,
    ctx: Context | None = None,
) -> Person:
    """Update an existing person in Folk.

    Args:
        person_id: The person's ID to update
        first_name: New first name
        last_name: New last name
        emails: New list of email addresses
        phones: New list of phone numbers
        job_title: New job title
        description: New description
        ctx: MCP context

    Returns:
        The updated person
    """
    client = get_client(ctx)
    try:
        return await client.update_person(
            person_id=person_id,
            first_name=first_name,
            last_name=last_name,
            emails=emails,
            phones=phones,
            job_title=job_title,
            description=description,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def delete_person(
    person_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Delete a person from Folk.

    Args:
        person_id: The person's ID to delete
        ctx: MCP context

    Returns:
        Confirmation of deletion
    """
    client = get_client(ctx)
    try:
        await client.delete_person(person_id)
        return {"deleted": True, "person_id": person_id}
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Company Tools
# ============================================================================


@mcp.tool()
async def list_companies(
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> list[Company]:
    """List companies in the Folk workspace.

    Args:
        limit: Number of companies to return (1-100, default 20)
        cursor: Pagination cursor for next page
        ctx: MCP context

    Returns:
        List of companies in the workspace
    """
    client = get_client(ctx)
    try:
        return await client.list_companies(limit=limit, cursor=cursor)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def get_company(
    company_id: str,
    ctx: Context | None = None,
) -> Company:
    """Get a specific company by ID.

    Args:
        company_id: The company's ID
        ctx: MCP context

    Returns:
        The company details
    """
    client = get_client(ctx)
    try:
        return await client.get_company(company_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def create_company(
    name: str,
    description: str | None = None,
    industry: str | None = None,
    emails: list[str] | None = None,
    phones: list[str] | None = None,
    urls: list[str] | None = None,
    group_ids: list[str] | None = None,
    ctx: Context | None = None,
) -> Company:
    """Create a new company in Folk.

    Args:
        name: Company name (required)
        description: Company description
        industry: Industry sector
        emails: List of email addresses
        phones: List of phone numbers
        urls: List of website URLs
        group_ids: List of group IDs to add the company to
        ctx: MCP context

    Returns:
        The created company
    """
    client = get_client(ctx)
    try:
        return await client.create_company(
            name=name,
            description=description,
            industry=industry,
            emails=emails,
            phones=phones,
            urls=urls,
            group_ids=group_ids,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def update_company(
    company_id: str,
    name: str | None = None,
    description: str | None = None,
    industry: str | None = None,
    emails: list[str] | None = None,
    phones: list[str] | None = None,
    urls: list[str] | None = None,
    ctx: Context | None = None,
) -> Company:
    """Update an existing company in Folk.

    Args:
        company_id: The company's ID to update
        name: New company name
        description: New description
        industry: New industry sector
        emails: New list of email addresses
        phones: New list of phone numbers
        urls: New list of website URLs
        ctx: MCP context

    Returns:
        The updated company
    """
    client = get_client(ctx)
    try:
        return await client.update_company(
            company_id=company_id,
            name=name,
            description=description,
            industry=industry,
            emails=emails,
            phones=phones,
            urls=urls,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def delete_company(
    company_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Delete a company from Folk.

    Args:
        company_id: The company's ID to delete
        ctx: MCP context

    Returns:
        Confirmation of deletion
    """
    client = get_client(ctx)
    try:
        await client.delete_company(company_id)
        return {"deleted": True, "company_id": company_id}
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Note Tools
# ============================================================================


@mcp.tool()
async def list_notes(
    limit: int = 20,
    cursor: str | None = None,
    entity_id: str | None = None,
    ctx: Context | None = None,
) -> list[Note]:
    """List notes in the Folk workspace.

    Args:
        limit: Number of notes to return (1-100, default 20)
        cursor: Pagination cursor for next page
        entity_id: Filter notes by entity ID (person or company)
        ctx: MCP context

    Returns:
        List of notes
    """
    client = get_client(ctx)
    try:
        return await client.list_notes(limit=limit, cursor=cursor, entity_id=entity_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def get_note(
    note_id: str,
    ctx: Context | None = None,
) -> Note:
    """Get a specific note by ID.

    Args:
        note_id: The note's ID
        ctx: MCP context

    Returns:
        The note details
    """
    client = get_client(ctx)
    try:
        return await client.get_note(note_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def create_note(
    entity_id: str,
    content: str,
    visibility: str = "public",
    ctx: Context | None = None,
) -> Note:
    """Create a new note on a person or company.

    Args:
        entity_id: The entity ID (person or company) to attach the note to
        content: The note content (1-100,000 characters)
        visibility: Note visibility ("public" or "private")
        ctx: MCP context

    Returns:
        The created note
    """
    client = get_client(ctx)
    try:
        return await client.create_note(
            entity_id=entity_id,
            content=content,
            visibility=visibility,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def update_note(
    note_id: str,
    content: str | None = None,
    visibility: str | None = None,
    ctx: Context | None = None,
) -> Note:
    """Update an existing note.

    Args:
        note_id: The note's ID to update
        content: New note content
        visibility: New visibility ("public" or "private")
        ctx: MCP context

    Returns:
        The updated note
    """
    client = get_client(ctx)
    try:
        return await client.update_note(
            note_id=note_id,
            content=content,
            visibility=visibility,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def delete_note(
    note_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Delete a note.

    Args:
        note_id: The note's ID to delete
        ctx: MCP context

    Returns:
        Confirmation of deletion
    """
    client = get_client(ctx)
    try:
        await client.delete_note(note_id)
        return {"deleted": True, "note_id": note_id}
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Reminder Tools
# ============================================================================


@mcp.tool()
async def list_reminders(
    limit: int = 20,
    cursor: str | None = None,
    entity_id: str | None = None,
    ctx: Context | None = None,
) -> list[Reminder]:
    """List reminders in the Folk workspace.

    Args:
        limit: Number of reminders to return (1-100, default 20)
        cursor: Pagination cursor for next page
        entity_id: Filter reminders by entity ID
        ctx: MCP context

    Returns:
        List of reminders
    """
    client = get_client(ctx)
    try:
        return await client.list_reminders(limit=limit, cursor=cursor, entity_id=entity_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def get_reminder(
    reminder_id: str,
    ctx: Context | None = None,
) -> Reminder:
    """Get a specific reminder by ID.

    Args:
        reminder_id: The reminder's ID
        ctx: MCP context

    Returns:
        The reminder details
    """
    client = get_client(ctx)
    try:
        return await client.get_reminder(reminder_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def create_reminder(
    entity_id: str,
    name: str,
    trigger_time: str,
    visibility: str = "public",
    recurrence_rule: str | None = None,
    assigned_user_ids: list[str] | None = None,
    ctx: Context | None = None,
) -> Reminder:
    """Create a new reminder on a person or company.

    Args:
        entity_id: The entity ID (person or company) to attach the reminder to
        name: Reminder name/title (max 255 chars)
        trigger_time: When to trigger (ISO 8601 datetime)
        visibility: Reminder visibility ("public" or "private")
        recurrence_rule: iCalendar recurrence rule (RFC 5545)
        assigned_user_ids: List of user IDs to assign the reminder to
        ctx: MCP context

    Returns:
        The created reminder
    """
    client = get_client(ctx)
    try:
        return await client.create_reminder(
            entity_id=entity_id,
            name=name,
            trigger_time=trigger_time,
            visibility=visibility,
            recurrence_rule=recurrence_rule,
            assigned_user_ids=assigned_user_ids,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def update_reminder(
    reminder_id: str,
    name: str | None = None,
    trigger_time: str | None = None,
    visibility: str | None = None,
    recurrence_rule: str | None = None,
    ctx: Context | None = None,
) -> Reminder:
    """Update an existing reminder.

    Args:
        reminder_id: The reminder's ID to update
        name: New reminder name
        trigger_time: New trigger time (ISO 8601)
        visibility: New visibility ("public" or "private")
        recurrence_rule: New recurrence rule
        ctx: MCP context

    Returns:
        The updated reminder
    """
    client = get_client(ctx)
    try:
        return await client.update_reminder(
            reminder_id=reminder_id,
            name=name,
            trigger_time=trigger_time,
            visibility=visibility,
            recurrence_rule=recurrence_rule,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def delete_reminder(
    reminder_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Delete a reminder.

    Args:
        reminder_id: The reminder's ID to delete
        ctx: MCP context

    Returns:
        Confirmation of deletion
    """
    client = get_client(ctx)
    try:
        await client.delete_reminder(reminder_id)
        return {"deleted": True, "reminder_id": reminder_id}
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Group Tools
# ============================================================================


@mcp.tool()
async def list_groups(
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> list[Group]:
    """List groups in the Folk workspace.

    Args:
        limit: Number of groups to return (1-100, default 20)
        cursor: Pagination cursor for next page
        ctx: MCP context

    Returns:
        List of groups
    """
    client = get_client(ctx)
    try:
        return await client.list_groups(limit=limit, cursor=cursor)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# User Tools
# ============================================================================


@mcp.tool()
async def list_users(
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> list[User]:
    """List users in the Folk workspace.

    Args:
        limit: Number of users to return (1-100, default 20)
        cursor: Pagination cursor for next page
        ctx: MCP context

    Returns:
        List of users
    """
    client = get_client(ctx)
    try:
        return await client.list_users(limit=limit, cursor=cursor)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def get_current_user(
    ctx: Context | None = None,
) -> User:
    """Get the current authenticated user.

    Args:
        ctx: MCP context

    Returns:
        The current user details
    """
    client = get_client(ctx)
    try:
        return await client.get_current_user()
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def get_user(
    user_id: str,
    ctx: Context | None = None,
) -> User:
    """Get a specific user by ID.

    Args:
        user_id: The user's ID
        ctx: MCP context

    Returns:
        The user details
    """
    client = get_client(ctx)
    try:
        return await client.get_user(user_id)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Deal Tools
# ============================================================================


@mcp.tool()
async def list_deals(
    group_id: str,
    object_type: str,
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> list[Deal]:
    """List deals in a Folk group.

    Args:
        group_id: The group ID (from list_groups)
        object_type: The deal object type name (from group custom fields)
        limit: Number of deals to return (1-100, default 20)
        cursor: Pagination cursor for next page
        ctx: MCP context

    Returns:
        List of deals in the group
    """
    client = get_client(ctx)
    try:
        return await client.list_deals(
            group_id=group_id,
            object_type=object_type,
            limit=limit,
            cursor=cursor,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Interaction Tools
# ============================================================================


@mcp.tool()
async def create_interaction(
    entity_id: str,
    interaction_type: str,
    occurred_at: str,
    ctx: Context | None = None,
) -> Interaction:
    """Create a new interaction with a person or company.

    Args:
        entity_id: The entity ID (person or company)
        interaction_type: Type of interaction (e.g., "email", "meeting", "call")
        occurred_at: When the interaction occurred (ISO 8601 datetime)
        ctx: MCP context

    Returns:
        The created interaction
    """
    client = get_client(ctx)
    try:
        return await client.create_interaction(
            entity_id=entity_id,
            interaction_type=interaction_type,
            occurred_at=occurred_at,
        )
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# ============================================================================
# Search Tools
# ============================================================================


@mcp.tool()
async def search_people(
    query: str,
    limit: int = 20,
    ctx: Context | None = None,
) -> list[Person]:
    """Search for people by name or email.

    Args:
        query: Search query (matches name or email)
        limit: Maximum results to return
        ctx: MCP context

    Returns:
        List of matching people
    """
    client = get_client(ctx)
    try:
        # Use filter to search
        filters = {"fullName": {"contains": query}}
        return await client.list_people(limit=limit, filters=filters)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


@mcp.tool()
async def search_companies(
    query: str,
    limit: int = 20,
    ctx: Context | None = None,
) -> list[Company]:
    """Search for companies by name.

    Args:
        query: Search query (matches company name)
        limit: Maximum results to return
        ctx: MCP context

    Returns:
        List of matching companies
    """
    client = get_client(ctx)
    try:
        # Use filter to search
        filters = {"name": {"contains": query}}
        return await client.list_companies(limit=limit, filters=filters)
    except FolkAPIError as e:
        if ctx:
            ctx.error(f"API error: {e.message}")
        raise


# Create ASGI application for HTTP deployment
app = mcp.http_app()

# Stdio entrypoint for Claude Desktop / mpak
if __name__ == "__main__":
    logger.info("Running in stdio mode")
    mcp.run()
