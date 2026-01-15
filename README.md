# Folk CRM MCP Server

An MCP (Model Context Protocol) server that provides access to [Folk CRM](https://folk.app) functionality, allowing AI assistants to manage contacts, companies, notes, reminders, and more.

## Features

- **People Management**: List, create, update, delete, and search people
- **Company Management**: List, create, update, delete, and search companies
- **Notes**: Create and manage notes on people and companies
- **Reminders**: Set up and manage reminders with recurrence support
- **Groups**: List workspace groups
- **Users**: List workspace users and get current user
- **Deals**: List deals in groups
- **Interactions**: Log interactions with contacts

## Installation

### Using mpak (Recommended)

```bash
# Configure your Folk API key
mpak config set @nimblebraininc/folk FOLK_API_KEY=your_api_key_here

# Run the server
mpak bundle run @nimblebraininc/folk
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/NimbleBrainInc/mcp-folk.git
cd mcp-folk

# Install dependencies with uv
uv sync

# Set your API key
export FOLK_API_KEY=your_api_key_here

# Run the server
uv run python -m mcp_folk.server
```

## Configuration

### Getting Your Folk API Key

1. Log in to your Folk workspace
2. Go to **Settings > API**
3. Create a new API key
4. Copy the key and configure it as shown above

### Claude Desktop Configuration

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "folk": {
      "command": "mpak",
      "args": ["run", "@nimblebraininc/folk"]
    }
  }
}
```

## Available Tools

### People
- `list_people` - List people in the workspace
- `get_person` - Get a specific person by ID
- `create_person` - Create a new person
- `update_person` - Update an existing person
- `delete_person` - Delete a person
- `search_people` - Search people by name

### Companies
- `list_companies` - List companies in the workspace
- `get_company` - Get a specific company by ID
- `create_company` - Create a new company
- `update_company` - Update an existing company
- `delete_company` - Delete a company
- `search_companies` - Search companies by name

### Notes
- `list_notes` - List notes (optionally filtered by entity)
- `get_note` - Get a specific note
- `create_note` - Create a note on a person or company
- `update_note` - Update an existing note
- `delete_note` - Delete a note

### Reminders
- `list_reminders` - List reminders
- `get_reminder` - Get a specific reminder
- `create_reminder` - Create a reminder
- `update_reminder` - Update an existing reminder
- `delete_reminder` - Delete a reminder

### Other
- `list_groups` - List workspace groups
- `list_users` - List workspace users
- `get_current_user` - Get the current authenticated user
- `get_user` - Get a specific user by ID
- `list_deals` - List deals in a group
- `create_interaction` - Log an interaction with a person or company

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest tests/ -v

# Format code
uv run ruff format src/ tests/

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Run all checks
make check
```

## API Reference

This server uses the [Folk REST API](https://developer.folk.app). Key endpoints:

- Base URL: `https://api.folk.app/v1`
- Authentication: Bearer token
- Rate limits apply (see Folk documentation)

## License

MIT
