# SQLite Lab MCP Server (FastMCP + SQLite)

This repository contains a complete lab implementation of a database-backed MCP server with:

- tools: `search`, `insert`, `aggregate`
- resources: `schema://database`, `schema://table/{table_name}`
- validation for unsafe or invalid requests
- repeatable verification script and automated tests

## Project Structure

```text
implementation/
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  requirements.txt
  start_inspector.sh
  start_inspector_ui.bat
  inspector_ui.py
  client_configs/
    claude_mcp.json
    codex_config.toml
  tests/
    test_server.py
```

## Data Model

Seeded SQLite tables:

- `students(id, name, cohort, age, score)`
- `courses(id, code, title)`
- `enrollments(id, student_id, course_id, semester)`

## Setup

From repository root:

```bash
cd implementation
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Initialize the database:

```bash
python init_db.py
```

## Run the Server

Default stdio transport (for MCP clients):

```bash
python mcp_server.py
```

Optional network transports:

```bash
python mcp_server.py --transport sse --host 127.0.0.1 --port 8000
python mcp_server.py --transport streamable-http --host 127.0.0.1 --port 8000
```

## Tool Descriptions

### `search`

Arguments:

- `table` (string, required)
- `columns` (list[string], optional)
- `filters` (list[object], optional)
- `limit` (int, default `20`, max `100`)
- `offset` (int, default `0`)
- `order_by` (string, optional)
- `descending` (bool, default `false`)

Supported filter operators:

- `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `like`, `in`

### `insert`

Arguments:

- `table` (string, required)
- `values` (object, required, non-empty)

Returns inserted payload and generated `id` when available.

### `aggregate`

Arguments:

- `table` (string, required)
- `metric` (string, required): `count`, `avg`, `sum`, `min`, `max`
- `column` (string, required except when `metric=count`)
- `filters` (list[object], optional)
- `group_by` (string, optional)

## Resources

- `schema://database`: full schema snapshot for all tables
- `schema://table/{table_name}`: schema for one table

## Validation and Safety

The server rejects:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate requests
- empty inserts
- unsafe pagination values (`limit <= 0`, `limit > 100`, `offset < 0`)

SQL values are bound with parameters where applicable.

## Verification

### Repeatable verification script

```bash
cd implementation
python verify_server.py
```

This verifies:

1. server object can be initialized
2. tools are discoverable
3. resources/templates are discoverable
4. valid calls succeed
5. invalid calls return clear errors

### Automated tests

```bash
cd implementation
pytest -q
```

## MCP Inspector

From `implementation/`:

```bash
./start_inspector.sh
```

Equivalent manual command:

```bash
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector python mcp_server.py
```

## Local Inspector UI (for demo/screenshots)

Run a browser-based Inspector-style UI:

```bash
cd implementation
python inspector_ui.py --host 127.0.0.1 --port 8088
```

Then open:

- http://127.0.0.1:8088

Windows helper:

```bat
cd implementation
start_inspector_ui.bat
```

Suggested screenshot checklist for grading:

1. Tools panel shows `search`, `insert`, `aggregate`.
2. Resources panel shows `schema://database`.
3. Resource Templates panel shows `schema://table/{table_name}`.
4. Tool call panel shows one valid result and one invalid error result.
5. Read Resource panel shows full schema or `schema://table/students`.

## Client Configuration Examples

### Codex

See [`implementation/client_configs/codex_config.toml`](implementation/client_configs/codex_config.toml).

### Claude Code

See [`implementation/client_configs/claude_mcp.json`](implementation/client_configs/claude_mcp.json).

### Gemini CLI

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use sqlite-lab MCP: search A1 students and count students."
```

## Demo Checklist (2-minute recording)

- Start server
- Show tool discovery (`search`, `insert`, `aggregate`)
- Call valid search/insert/aggregate
- Read `schema://database` and `schema://table/students`
- Trigger one invalid request and show clear error
- Show at least one client connected successfully
