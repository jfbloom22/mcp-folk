"""Tests for Folk API models."""

from mcp_folk.api_models import (
    Company,
    Group,
    Note,
    Person,
    Reminder,
    User,
    Visibility,
)


def test_person_model() -> None:
    """Test Person model parsing."""
    data = {
        "id": "per_123",
        "firstName": "John",
        "lastName": "Doe",
        "fullName": "John Doe",
        "emails": ["john@example.com"],
        "phones": ["+1234567890"],
        "jobTitle": "Engineer",
        "groups": [],
        "companies": [],
        "addresses": [],
        "urls": [],
        "customFieldValues": {},
    }
    person = Person(**data)
    assert person.id == "per_123"
    assert person.first_name == "John"
    assert person.last_name == "Doe"
    assert person.full_name == "John Doe"
    assert person.emails == ["john@example.com"]


def test_company_model() -> None:
    """Test Company model parsing."""
    data = {
        "id": "com_456",
        "name": "Acme Inc",
        "description": "A test company",
        "industry": "Technology",
        "groups": [],
        "addresses": [],
        "emails": [],
        "phones": [],
        "urls": [],
        "customFieldValues": {},
    }
    company = Company(**data)
    assert company.id == "com_456"
    assert company.name == "Acme Inc"
    assert company.industry == "Technology"


def test_note_model() -> None:
    """Test Note model parsing."""
    data = {
        "id": "note_789",
        "content": "This is a test note",
        "visibility": "public",
    }
    note = Note(**data)
    assert note.id == "note_789"
    assert note.content == "This is a test note"
    assert note.visibility == Visibility.PUBLIC


def test_reminder_model() -> None:
    """Test Reminder model parsing."""
    data = {
        "id": "rem_abc",
        "name": "Follow up",
        "visibility": "private",
        "assignedUsers": [],
    }
    reminder = Reminder(**data)
    assert reminder.id == "rem_abc"
    assert reminder.name == "Follow up"
    assert reminder.visibility == Visibility.PRIVATE


def test_group_model() -> None:
    """Test Group model parsing."""
    data = {
        "id": "grp_xyz",
        "name": "Sales Pipeline",
    }
    group = Group(**data)
    assert group.id == "grp_xyz"
    assert group.name == "Sales Pipeline"


def test_user_model() -> None:
    """Test User model parsing."""
    data = {
        "id": "usr_123",
        "fullName": "Jane Smith",
        "email": "jane@example.com",
    }
    user = User(**data)
    assert user.id == "usr_123"
    assert user.full_name == "Jane Smith"
    assert user.email == "jane@example.com"
