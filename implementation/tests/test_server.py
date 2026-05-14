from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from init_db import create_database
from mcp_server import create_server

TEST_DB_DIR = Path(__file__).resolve().parents[1] / ".test_runtime"


def run(coro):
    return asyncio.run(coro)


def build_server(test_name: str):
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    db_path = TEST_DB_DIR / f"{test_name}.db"
    if db_path.exists():
        db_path.unlink()
    create_database(db_path, reset=True)
    return create_server(db_path)


def test_tools_discovery():
    server = build_server("tools_discovery")

    async def scenario():
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools}
            assert names == {"search", "insert", "aggregate"}

    run(scenario())


def test_resources_discovery():
    server = build_server("resources_discovery")

    async def scenario():
        async with Client(server) as client:
            resources = await client.list_resources()
            resource_uris = {str(resource.uri) for resource in resources}
            assert "schema://database" in resource_uris

            templates = await client.list_resource_templates()
            template_uris = {template.uriTemplate for template in templates}
            assert "schema://table/{table_name}" in template_uris

            schema = await client.read_resource("schema://table/students")
            payload = json.loads(schema[0].text)
            assert payload["table"] == "students"

    run(scenario())


def test_search_insert_aggregate_success():
    server = build_server("search_insert_aggregate")

    async def scenario():
        async with Client(server) as client:
            search = await client.call_tool(
                "search",
                {"table": "students", "filters": [{"column": "cohort", "value": "A1"}]},
            )
            assert search.data["row_count"] >= 2

            inserted = await client.call_tool(
                "insert",
                {
                    "table": "students",
                    "values": {
                        "name": "Test User",
                        "cohort": "A3",
                        "age": 20,
                        "score": 87.2,
                    },
                },
            )
            assert inserted.data["inserted"]["name"] == "Test User"
            assert "id" in inserted.data["inserted"]

            aggregate = await client.call_tool(
                "aggregate",
                {"table": "students", "metric": "count"},
            )
            assert aggregate.data["rows"][0]["value"] >= 5

    run(scenario())


def test_invalid_requests_return_errors():
    server = build_server("invalid_requests")

    async def scenario():
        async with Client(server) as client:
            missing_table = await client.call_tool(
                "search",
                {"table": "not_real"},
                raise_on_error=False,
            )
            assert missing_table.is_error

            bad_column = await client.call_tool(
                "insert",
                {"table": "students", "values": {"bad_column": 1}},
                raise_on_error=False,
            )
            assert bad_column.is_error

            bad_operator = await client.call_tool(
                "search",
                {
                    "table": "students",
                    "filters": [{"column": "score", "op": "contains", "value": 90}],
                },
                raise_on_error=False,
            )
            assert bad_operator.is_error

            bad_aggregate = await client.call_tool(
                "aggregate",
                {"table": "students", "metric": "median", "column": "score"},
                raise_on_error=False,
            )
            assert bad_aggregate.is_error

    run(scenario())
