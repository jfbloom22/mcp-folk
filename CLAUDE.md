# Folk CRM MCP Server

MCP server providing Folk CRM functionality via Folk's REST API.

## Architecture

```
src/mcp_folk/
├── server.py      # MCP tools (FastMCP) + stdio entrypoint
├── api_client.py  # Async HTTP client for Folk API
└── api_models.py  # Pydantic models for API responses
```

## Critical

- Package name: `@nimblebraininc/folk` (npm-style, matches GitHub org)
- Manifest uses module execution: `python -m mcp_folk.server`
- Server needs both entrypoints:
  ```python
  app = mcp.http_app()  # HTTP deployment
  if __name__ == "__main__":
      mcp.run()  # Stdio for Claude Desktop / mpak
  ```

## user_config

API key configured via manifest `user_config`, not hardcoded:
```json
{
  "user_config": {
    "api_key": {
      "type": "string",
      "sensitive": true,
      "required": true
    }
  },
  "server": {
    "mcp_config": {
      "env": { "FOLK_API_KEY": "${user_config.api_key}" }
    }
  }
}
```

## Available Tools

AI-friendly tools designed for minimal token usage and intent-based operations.

### Search (Tier 1 - Use First)

| Tool | Purpose | Returns |
|------|---------|---------|
| `find_person(name)` | Find people by name | `{found, matches: [{id, name, email}], total}` |
| `find_company(name)` | Find companies by name | `{found, matches: [{id, name, industry}], total}` |

### Details (Tier 2 - After Finding)

| Tool | Purpose |
|------|---------|
| `get_person_details(person_id)` | Full person info after finding |
| `get_company_details(company_id)` | Full company info after finding |

### Browse (Tier 3 - Exploration)

| Tool | Purpose |
|------|---------|
| `browse_people(page, per_page)` | Paginated list of all people |
| `browse_companies(page, per_page)` | Paginated list of all companies |

### Actions (Tier 4 - Mutations)

| Tool | Purpose |
|------|---------|
| `add_person(first_name, ...)` | Create new person |
| `add_company(name, ...)` | Create new company |
| `update_person(person_id, ...)` | Update person fields |
| `update_company(company_id, ...)` | Update company fields |
| `delete_person(person_id)` | Delete a person |
| `delete_company(company_id)` | Delete a company |

### Notes & Reminders (Tier 5)

| Tool | Purpose |
|------|---------|
| `add_note(person_id, content)` | Add note to person |
| `get_notes(person_id)` | Get notes for person |
| `set_reminder(person_id, reminder, when)` | Set a reminder |
| `log_interaction(person_id, type, when)` | Log an interaction |

### Utility

| Tool | Purpose |
|------|---------|
| `whoami()` | Get current authenticated user |

## Design Principles

- **Minimal payloads**: Search returns `{id, name, email}` not full records
- **Two-phase lookup**: `find_person` then `get_person_details`
- **Boolean answers**: `{found: true/false}` for existence checks
- **Intent-based**: Tools match what AI wants to do, not REST operations

## Folk API Reference

- Base URL: `https://api.folk.app/v1`
- Auth: Bearer token in Authorization header
- Docs: https://developer.folk.app

## Commands

```bash
uv run pytest           # Test
uv run ruff format .    # Format
uv run ruff check .     # Lint
uv run mypy src/        # Type check
make check              # All checks
```

## Testing

```bash
# Unit tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ -v --cov=src/mcp_folk --cov-report=term-missing
```

## Releasing

Uses mcpb-pack v2 workflow. Releases trigger on `release: published`.

```bash
# New release
git tag v0.1.0 && git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0" --notes "- Initial release"
```

## Adding to Claude Code

```bash
# Configure API key
mpak config set @nimblebraininc/folk api_key=your_key_here

# From registry (published)
claude mcp add folk -- mpak run @nimblebraininc/folk

# Local development (after make pack)
claude mcp add folk -- mpak run --local /path/to/mcp-folk-0.1.0-darwin-arm64.mcpb
```

## Adding New Endpoints

1. Add response model to `api_models.py`
2. Add client method to `api_client.py`
3. Add MCP tool to `server.py`
4. Add unit test to `tests/`
