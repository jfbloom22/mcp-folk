"""Tests for group-scoped custom-field updates through the MCP tool."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_folk.api_models import GroupReference, Person
from mcp_folk.server import update_person

PERSON_ID = "per_12345678-1234-1234-1234-123456789abc"
GROUP_ID = "grp_12345678-1234-1234-1234-123456789abc"
OTHER_GROUP_ID = "grp_87654321-4321-4321-4321-cba987654321"


def _person(*, groups: list[GroupReference]) -> Person:
    return Person(id=PERSON_ID, firstName="Ada", lastName="Lovelace", groups=groups)


@pytest.mark.asyncio
async def test_update_person_sends_group_scoped_single_select_and_preserves_groups() -> None:
    client = AsyncMock()
    client.get_person.return_value = _person(
        groups=[
            GroupReference(id=GROUP_ID, name="Leads"),
            GroupReference(id=OTHER_GROUP_ID, name="Customers"),
        ]
    )
    client.update_person.return_value = _person(groups=[])

    with patch("mcp_folk.server.get_client", return_value=client):
        result = await update_person(
            person_id=PERSON_ID,
            group_id=GROUP_ID,
            custom_field_values={"Status": "Active"},
        )

    assert result == {"id": PERSON_ID, "name": "Ada Lovelace", "updated": True}
    client.get_person.assert_awaited_once_with(PERSON_ID)
    client.update_person.assert_awaited_once_with(
        person_id=PERSON_ID,
        first_name=None,
        last_name=None,
        emails=None,
        phones=None,
        job_title=None,
        group_ids=[GROUP_ID, OTHER_GROUP_ID],
        custom_fields={GROUP_ID: {"Status": "Active"}},
    )


@pytest.mark.asyncio
async def test_update_person_rejects_custom_fields_without_group_id() -> None:
    with pytest.raises(ValueError, match="group_id is required"):
        await update_person(person_id=PERSON_ID, custom_field_values={"Status": "Active"})


@pytest.mark.asyncio
async def test_update_person_rejects_group_not_on_person() -> None:
    client = AsyncMock()
    client.get_person.return_value = _person(groups=[])

    with patch("mcp_folk.server.get_client", return_value=client):
        with pytest.raises(ValueError, match="is not a member"):
            await update_person(
                person_id=PERSON_ID,
                group_id=GROUP_ID,
                custom_field_values={"Status": "Active"},
            )

    client.update_person.assert_not_awaited()
