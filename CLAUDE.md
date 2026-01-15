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

| Category | Tools |
|----------|-------|
| People | `list_people`, `get_person`, `create_person`, `update_person`, `delete_person`, `search_people` |
| Companies | `list_companies`, `get_company`, `create_company`, `update_company`, `delete_company`, `search_companies` |
| Notes | `list_notes`, `get_note`, `create_note`, `update_note`, `delete_note` |
| Reminders | `list_reminders`, `get_reminder`, `create_reminder`, `update_reminder`, `delete_reminder` |
| Groups | `list_groups` |
| Users | `list_users`, `get_current_user`, `get_user` |
| Deals | `list_deals` |
| Interactions | `create_interaction` |

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

## Local Testing with mpak

```bash
mpak config set @nimblebraininc/folk FOLK_API_KEY=your_key_here
mpak bundle run @nimblebraininc/folk
```

Claude Code config (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "folk": {
      "command": "mpak",
      "args": ["bundle", "run", "@nimblebraininc/folk"]
    }
  }
}
```

## Adding New Endpoints

1. Add response model to `api_models.py`
2. Add client method to `api_client.py`
3. Add MCP tool to `server.py`
4. Add unit test to `tests/`
