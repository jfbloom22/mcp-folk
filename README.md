> [!WARNING]
> **This repository is archived and no longer maintained.**
>
> This MCP server has been removed from the [mpak registry](https://mpak.dev).

---

# Folk CRM MCP Server

[![CI](https://github.com/NimbleBrainInc/mcp-folk/actions/workflows/ci.yml/badge.svg)](https://github.com/NimbleBrainInc/mcp-folk/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An MCP (Model Context Protocol) server that provides access to [Folk CRM](https://folk.app) functionality, allowing AI assistants to manage contacts, companies, notes, reminders, and more.

## Features

- **Smart Search**: Find people and companies by name with minimal token usage
- **Two-Phase Lookup**: Quick search returns IDs, then fetch full details as needed
- **Contact Management**: Create, update, and delete people and companies
- **Notes & Reminders**: Attach context to your contacts
- **Interaction Logging**: Track emails, meetings, and calls
- **Built-in Skill Resource**: Serves a `skill://folk/usage` resource that teaches LLMs correct tool routing, ID format rules, and situational handling patterns

## Adding to Claude Code

### From Registry (Published)

```bash
# Configure your Folk API key
mpak config set @nimblebraininc/folk api_key=your_api_key_here

# Add to Claude Code
claude mcp add folk -- mpak run @nimblebraininc/folk
```

### Local Development

```bash
# Clone and enter the repo
git clone https://github.com/NimbleBrainInc/mcp-folk.git
cd mcp-folk

# Install dependencies
uv sync

# Build the bundle
make pack

# Configure your API key
mpak config set @nimblebraininc/folk api_key=your_api_key_here

# Add to Claude Code (use absolute path)
claude mcp add folk -- mpak run --local /path/to/mcp-folk/mcp-folk-0.1.0-darwin-arm64.mcpb
```

## Configuration

### Getting Your Folk API Key

1. Log in to your Folk workspace
2. Go to **Settings > API**
3. Create a new API key
4. Copy the key and configure with `mpak config set`

### HTTP Transport Security

When deploying over HTTP (not stdio), configure:

- `Authorization: Bearer <folk_api_token>` on every request (except `/health`)
- `MCP_HTTP_RATE_LIMIT_PER_MIN` (default: `120`): Per-minute limit per `IP + token`
- `MCP_HTTP_NOAUTH_RATE_LIMIT_PER_MIN` (default: `40`): Per-minute limit for requests missing/invalid auth by IP
- `MCP_HTTP_MAX_BODY_BYTES` (default: `1048576`): Reject requests larger than this via `413`

## HTTP Deployment

This server exposes an ASGI app at `mcp_folk.server:app` for HTTP deployments.

### Docker

```bash
docker build -t mcp-folk .
docker run --rm -p 8000:8000 mcp-folk
```

The included image:

- Starts `uvicorn mcp_folk.server:app`
- Binds to `0.0.0.0`
- Uses `PORT` (default `8000`)
- Exposes `/health` for container health checks

### Docker Compose

```yaml
services:
  mcp-folk:
    image: mcp-folk
    build: .
    ports:
      - "8000:8000"
    environment:
      FOLK_API_KEY: ${FOLK_API_KEY}
      PORT: 8000
```

Run it with:

```bash
docker compose up --build
```

### Runtime Expectations

- Send `Authorization: Bearer <folk_api_token>` on every request except `/health`
- Terminate TLS in front of this app when exposing it outside a trusted network
- If you run a reverse proxy, forward the `Authorization` header unchanged
- The built-in rate limiter is an in-process safety net for a single instance, not edge protection or DDoS mitigation

## Available Tools

### Search (Use First)

| Tool | Purpose |
|------|---------|
| `find_person(name)` | Find people by name, returns `{found, matches: [{id, name, email}]}` |
| `find_company(name)` | Find companies by name, returns `{found, matches: [{id, name, industry}]}` |

### Details (After Finding)

| Tool | Purpose |
|------|---------|
| `get_person_details(person_id)` | Full person info including all fields |
| `get_company_details(company_id)` | Full company info including all fields |

### Browse

| Tool | Purpose |
|------|---------|
| `browse_people(cursor, limit)` | Cursor-based list of people |
| `browse_companies(cursor, limit)` | Cursor-based list of companies |

Start with `cursor=None`, then keep passing `next_cursor` from the prior response:

```json
{
  "people": [],
  "cursor": null,
  "next_cursor": "next-token",
  "limit": 20,
  "has_more": true
}
```

### Groups & Filtering

| Tool | Purpose |
|------|---------|
| `list_groups()` | List all groups in the workspace |
| `find_people_in_group(group_name, status, custom_field, custom_value)` | Find people in a group, optionally filtered by Status or another custom field |
| `find_companies_in_group(group_name, status, custom_field, custom_value)` | Find companies in a group, optionally filtered by Status or another custom field |

### Actions

| Tool | Purpose |
|------|---------|
| `add_person(first_name, ...)` | Create new person |
| `add_company(name, ...)` | Create new company |
| `update_person(person_id, ...)` | Update person fields |
| `update_company(company_id, ...)` | Update company fields |
| `delete_person(person_id)` | Delete a person |
| `delete_company(company_id)` | Delete a company |

### Notes & Reminders

| Tool | Purpose |
|------|---------|
| `add_note(person_id, content)` | Add note to person |
| `get_notes(person_id)` | Get notes for person |
| `set_reminder(person_id, reminder, when)` | Set a reminder |
| `log_interaction(person_id, interaction_type, when)` | Log an interaction |

### Utility

| Tool | Purpose |
|------|---------|
| `whoami()` | Get current authenticated user |

## Common Use Cases

**Look up contacts**
- "Is Sarah Chen in my CRM?"
- "Find everyone at Acme Corp"
- "What's John's email?"

**Add contacts after meetings**
- "Add Mike Johnson from today's meeting, he's a PM at Stripe"
- "Create a contact for lisa@example.com"

**Take notes**
- "Add a note to Sarah: discussed Q2 roadmap, she's interested in enterprise plan"
- "What are my notes on the Acme deal?"

**Set follow-ups**
- "Remind me to follow up with John next Tuesday"
- "Set a reminder to check in with Sarah in 2 weeks"

**Log interactions**
- "Log that I had a call with Mike today"
- "Record my meeting with the Acme team"

**Browse contacts**
- "Show me my recent contacts"
- "List all companies in my CRM"

**Query groups and pipelines**
- "Show me leads in 'Demos Management' with status 'Follow up 1'"
- "List all people in my Investors group"
- "Find active clients in my Customers group"
- "What groups do I have in Folk?"

## Example Flow

```
User: "I just had coffee with Alex Rivera, she's interested in our API. Remind me to send her docs next week."

AI: find_person("Alex Rivera")
→ {"found": true, "matches": [{"id": "abc123", "name": "Alex Rivera", "email": "alex@techco.io"}]}

AI: add_note("abc123", "Had coffee - interested in API, wants to see docs")
→ {"id": "note456", "added": true}

AI: log_interaction("abc123", "meeting", "2024-01-15T10:00:00Z")
→ {"id": "int789", "logged": true}

AI: set_reminder("abc123", "Send API docs to Alex", "2024-01-22T09:00:00Z")
→ {"id": "rem012", "set": true}

AI: "Done! I've added a note about your coffee chat, logged the meeting, and set a reminder for next Monday to send her the API docs."
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest tests/ -v

# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type check
uv run mypy src/

# Run all checks
make check

# Build bundle for testing
make pack
```

## API Reference

This server uses the [Folk REST API](https://developer.folk.app). Key endpoints:

- Base URL: `https://api.folk.app/v1`
- Authentication: Bearer token
- Rate limits apply (see Folk documentation)

## License

MIT
