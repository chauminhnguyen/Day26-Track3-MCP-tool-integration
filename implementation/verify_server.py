from __future__ import annotations

import asyncio
import json
import logging

from fastmcp import Client

try:
    from .init_db import create_database
    from .mcp_server import create_server
except ImportError:
    from init_db import create_database
    from mcp_server import create_server


def configure_logging() -> None:
    # Invalid-call checks in this verifier are expected failures, so keep output concise.
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)


async def verify() -> None:
    db_path = create_database()
    server = create_server(db_path)

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert tool_names == {"search", "insert", "aggregate"}, tool_names
        print(f"Tool discovery OK: {sorted(tool_names)}")

        resources = await client.list_resources()
        resource_uris = {str(resource.uri) for resource in resources}
        assert "schema://database" in resource_uris, resource_uris
        print("Resource discovery OK: schema://database")

        templates = await client.list_resource_templates()
        template_uris = {template.uriTemplate for template in templates}
        assert "schema://table/{table_name}" in template_uris, template_uris
        print("Resource template discovery OK: schema://table/{table_name}")

        search_ok = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": [{"column": "cohort", "op": "eq", "value": "A1"}],
                "order_by": "score",
                "descending": True,
                "limit": 10,
                "offset": 0,
            },
        )
        print(f"Valid search rows: {search_ok.data['row_count']}")

        insert_ok = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {
                    "name": "Eden Vu",
                    "cohort": "A1",
                    "age": 19,
                    "score": 92.0,
                },
            },
        )
        print(f"Valid insert id: {insert_ok.data['inserted']['id']}")

        aggregate_ok = await client.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"},
        )
        print(f"Valid aggregate groups: {len(aggregate_ok.data['rows'])}")

        db_schema = await client.read_resource("schema://database")
        print(f"Full schema size: {len(db_schema[0].text)} chars")

        student_schema = await client.read_resource("schema://table/students")
        print(f"Students schema: {json.loads(student_schema[0].text)['table']}")

        bad_table = await client.call_tool(
            "search",
            {"table": "missing_table"},
            raise_on_error=False,
        )
        assert bad_table.is_error, "Expected invalid table to fail"
        print(f"Invalid table check OK: {bad_table.content[0].text}")

        bad_operator = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": [{"column": "score", "op": "between", "value": 90}],
            },
            raise_on_error=False,
        )
        assert bad_operator.is_error, "Expected invalid operator to fail"
        print(f"Invalid operator check OK: {bad_operator.content[0].text}")

        bad_aggregate = await client.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg"},
            raise_on_error=False,
        )
        assert bad_aggregate.is_error, "Expected bad aggregate to fail"
        print(f"Invalid aggregate check OK: {bad_aggregate.content[0].text}")


if __name__ == "__main__":
    configure_logging()
    asyncio.run(verify())
