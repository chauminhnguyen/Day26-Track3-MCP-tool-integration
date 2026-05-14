from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import uvicorn
from fastmcp import Client
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

try:
    from .init_db import DEFAULT_DB_PATH, create_database
    from .mcp_server import create_server
except ImportError:
    from init_db import DEFAULT_DB_PATH, create_database
    from mcp_server import create_server


logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
logging.getLogger("mcp").setLevel(logging.CRITICAL)

_db_path = create_database(DEFAULT_DB_PATH, reset=True)
_server = create_server(_db_path)


def _as_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_as_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: _as_dict(item) for key, item in value.items()}
    return value


async def _list_tools(_: Request) -> JSONResponse:
    async with Client(_server) as client:
        tools = await client.list_tools()
    payload = []
    for tool in tools:
        item = _as_dict(tool)
        payload.append(
            {
                "name": item.get("name"),
                "description": item.get("description"),
                "inputSchema": item.get("inputSchema"),
            }
        )
    return JSONResponse({"tools": payload})


async def _list_resources(_: Request) -> JSONResponse:
    async with Client(_server) as client:
        resources = await client.list_resources()
    payload = []
    for resource in resources:
        item = _as_dict(resource)
        payload.append(
            {
                "name": item.get("name"),
                "uri": str(item.get("uri")),
                "mimeType": item.get("mimeType"),
                "description": item.get("description"),
            }
        )
    return JSONResponse({"resources": payload})


async def _list_templates(_: Request) -> JSONResponse:
    async with Client(_server) as client:
        templates = await client.list_resource_templates()
    payload = []
    for template in templates:
        item = _as_dict(template)
        payload.append(
            {
                "name": item.get("name"),
                "uriTemplate": item.get("uriTemplate"),
                "mimeType": item.get("mimeType"),
                "description": item.get("description"),
            }
        )
    return JSONResponse({"templates": payload})


async def _call_tool(request: Request) -> JSONResponse:
    body = await request.json()
    name = body.get("name")
    arguments = body.get("arguments", {})
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    if not isinstance(arguments, dict):
        return JSONResponse({"error": "arguments must be a JSON object"}, status_code=400)

    async with Client(_server) as client:
        result = await client.call_tool(name, arguments, raise_on_error=False)

    content = []
    for part in result.content:
        part_item = _as_dict(part)
        content.append({"type": part_item.get("type"), "text": part_item.get("text")})

    return JSONResponse(
        {
            "is_error": result.is_error,
            "data": _as_dict(result.data),
            "structured_content": _as_dict(result.structured_content),
            "content": content,
        }
    )


async def _read_resource(request: Request) -> JSONResponse:
    body = await request.json()
    uri = body.get("uri")
    if not uri:
        return JSONResponse({"error": "uri is required"}, status_code=400)

    async with Client(_server) as client:
        result = await client.read_resource(uri)

    payload = []
    for item in result:
        row = _as_dict(item)
        payload.append(
            {
                "uri": str(row.get("uri")),
                "mimeType": row.get("mimeType"),
                "text": row.get("text"),
            }
        )
    return JSONResponse({"result": payload})


async def _index(_: Request) -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SQLite MCP Inspector UI</title>
  <style>
    :root { --bg: #f3f7fb; --card: #ffffff; --line: #d9e3ef; --ink: #0f172a; --muted: #475569; --accent: #0ea5e9; }
    body { margin: 0; font-family: "Segoe UI", sans-serif; background: linear-gradient(120deg, #e8f5ff, #f8fbff); color: var(--ink); }
    .wrap { max-width: 1100px; margin: 28px auto; padding: 0 16px; }
    .hero { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
    .hero h1 { margin: 0 0 8px; font-size: 24px; }
    .hero p { margin: 0; color: var(--muted); }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px; }
    .card h2 { margin: 0 0 10px; font-size: 17px; }
    button { background: var(--accent); border: 0; color: #fff; border-radius: 8px; padding: 8px 12px; cursor: pointer; }
    button:hover { filter: brightness(0.95); }
    textarea, input { width: 100%; box-sizing: border-box; border: 1px solid var(--line); border-radius: 8px; padding: 8px; font-family: Consolas, monospace; }
    textarea { min-height: 130px; resize: vertical; }
    pre { background: #0b1020; color: #e2e8f0; padding: 10px; border-radius: 8px; overflow: auto; max-height: 300px; }
    .full { grid-column: 1 / -1; }
    .row { display: flex; gap: 8px; margin-bottom: 8px; }
    .status { display: inline-block; margin-left: 10px; padding: 2px 8px; border-radius: 999px; background: #d1fae5; color: #065f46; font-size: 12px; }
    @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>SQLite MCP Inspector UI</h1>
      <p>Inspect tools/resources and run MCP calls for demo evidence.</p>
      <span class="status">Local Server Loaded</span>
    </div>

    <div class="grid">
      <section class="card">
        <h2>Tools</h2>
        <button onclick="loadTools()">Refresh Tools</button>
        <pre id="toolsOut"></pre>
      </section>

      <section class="card">
        <h2>Resources</h2>
        <button onclick="loadResources()">Refresh Resources</button>
        <pre id="resourcesOut"></pre>
      </section>

      <section class="card">
        <h2>Resource Templates</h2>
        <button onclick="loadTemplates()">Refresh Templates</button>
        <pre id="templatesOut"></pre>
      </section>

      <section class="card">
        <h2>Read Resource</h2>
        <input id="resourceUri" value="schema://database" />
        <div style="margin-top:8px;">
          <button onclick="readResource()">Read</button>
        </div>
        <pre id="readOut"></pre>
      </section>

      <section class="card full">
        <h2>Call Tool</h2>
        <div class="row">
          <input id="toolName" value="search" />
        </div>
        <textarea id="toolArgs">{
  "table": "students",
  "filters": [{"column": "cohort", "op": "eq", "value": "A1"}],
  "order_by": "score",
  "descending": true,
  "limit": 5,
  "offset": 0
}</textarea>
        <div style="margin-top:8px;">
          <button onclick="callTool()">Run Tool</button>
        </div>
        <pre id="toolCallOut"></pre>
      </section>
    </div>
  </div>

  <script>
    const pretty = (x) => JSON.stringify(x, null, 2);

    async function getJson(url) {
      const res = await fetch(url);
      return await res.json();
    }

    async function postJson(url, body) {
      const res = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
      });
      return await res.json();
    }

    async function loadTools() {
      const data = await getJson("/api/tools");
      document.getElementById("toolsOut").textContent = pretty(data);
    }

    async function loadResources() {
      const data = await getJson("/api/resources");
      document.getElementById("resourcesOut").textContent = pretty(data);
    }

    async function loadTemplates() {
      const data = await getJson("/api/resource-templates");
      document.getElementById("templatesOut").textContent = pretty(data);
    }

    async function readResource() {
      const uri = document.getElementById("resourceUri").value;
      const data = await postJson("/api/read-resource", { uri });
      document.getElementById("readOut").textContent = pretty(data);
    }

    async function callTool() {
      const name = document.getElementById("toolName").value;
      const raw = document.getElementById("toolArgs").value;
      let args;
      try {
        args = JSON.parse(raw);
      } catch (e) {
        document.getElementById("toolCallOut").textContent = "Invalid JSON in arguments.";
        return;
      }
      const data = await postJson("/api/call-tool", { name, arguments: args });
      document.getElementById("toolCallOut").textContent = pretty(data);
    }

    loadTools();
    loadResources();
    loadTemplates();
  </script>
</body>
</html>
        """
    )


routes = [
    Route("/", _index),
    Route("/api/tools", _list_tools),
    Route("/api/resources", _list_resources),
    Route("/api/resource-templates", _list_templates),
    Route("/api/call-tool", _call_tool, methods=["POST"]),
    Route("/api/read-resource", _read_resource, methods=["POST"]),
]

app = Starlette(debug=False, routes=routes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local MCP Inspector-style UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8088, help="Port to bind.")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
